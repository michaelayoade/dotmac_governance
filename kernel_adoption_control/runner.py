"""The Kernel-adoption runner: one command, one format, no per-product adapter.

Until this module existed, `kernel_adoption_control` had an engine, a
declaration contract and a reader, and nothing that called them. A product
could write `.dotmac/kernel-adoption.json` and **nothing evaluated it** — the
"declared and never read" defect standing inside the package built to catch it.
ADR 0042 § 4 recorded that as a deliberate report-only decision rather than an
omission; Michael Ayoade authorised activation on 2026-09-05, and this is it.

## Where a run happens, and why it is not here

`read_declaration` reads a file in a PRODUCT's checkout. Under ADR 0013 § 1 a
claim about another repository needs an external oracle, and Governance holds
none — so Governance may not run this over `dotmac_erp` and publish the
verdict. The run therefore happens **in the product's own CI, over the
product's own checkout**, where every input is a repository-local fact and no
oracle is required. Governance owns the runner; the product owns the run.

This repository additionally runs it over ITSELF, on exactly the footing
ADR 0044 § 4 established for `tools/check_local_action_workspace.py`: a
repository-local subject, derived from repository-local facts.
`dotmac_governance` has its own `.dotmac/kernel-adoption.json`, so it is a
subject of the standard and not merely its author.

## The whole product-side surface

One callable, `(Path) -> ProductObservation`, named to the runner as
`package.module:function`. It observes; it does not classify, and it CANNOT:
`ProductObservation` has no declaration field, so a product cannot hand the
runner a declaration and therefore cannot hand it a clean one. The runner reads
the declaration itself, through Governance's own reader, and the four refusals
are Governance's to make.

Nothing here is parameterised by product. There is no product name, no branch
and no adapter — the observer REFERENCE is data the caller supplies, which is
the opposite of a per-product code path. Michael's acceptance test for this
design holds: *"one build-once validator and one declaration format across
every product, not a per-product adapter."*

## What the runner executes, and the boundary on that

Resolving an observer IMPORTS and CALLS product code. That is the product's own
code in the product's own job, which is why the run belongs there — but it is
also why the workspace must hold the product's trusted commit and never a
caller-supplied ref. That property is ADR 0044's subject, not this module's,
and this module does not check it.

## Binding, and how an unenforced enrolment stays visible

A report names the exact Governance revision that produced it and the exact
product revision it measured, both derived from Git rather than supplied. A
product cannot state a Governance revision it did not run, because the runner
reads its own checkout.

**Citability is asked of a REPORT OBJECT, never of a document.** `citability`
takes a `RunReport` that `run()` produced in this process; `inspect_report_document`
takes a mapping and can only ever call it self-consistent, because its return
type has no citable value in it. That split is open decision 52 (5)'s repair
and its boundary both: a run report written to disk is not self-authenticating,
and the citable claim lives in the exit code of the job that ran, not in the
artifact. A product pinning a Governance revision from before this module
existed produces no report at all, and no report is not a pass.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import re
import subprocess
import sys
import weakref
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path, PurePosixPath

from standards_control.contracts import (
    GovernanceSourceKind,
    KernelAdoptionBinding,
    PinnedGovernanceModelRef,
)
from standards_control.profile import (
    ProfileError,
    parse_governance_model,
    parse_kernel_adoption_binding,
)

from .contracts import (
    AdoptionReport,
    DeclarationOutcome,
    DeclarationPresent,
    KernelAdoptionApplicability,
    KernelAdoptionDeclarationV2,
    KernelAdoptionInputs,
    KernelSurfaceCatalogue,
    PinSite,
    PredecessorObservation,
    Severity,
)
from .declaration import DECLARATION_PATH, read_declaration
from .declaration_contract import KERNEL_ADOPTION_CONTRACT
from .declaration_contract_v2 import KERNEL_ADOPTION_CONTRACT_V2
from .engine import evaluate
from .surface import CATALOGUE_DIGEST_ALGORITHM

__all__ = [
    "CANONICAL_GOVERNANCE",
    "RUN_CONTRACT",
    "Citability",
    "DocumentVerdict",
    "ProductObservation",
    "Provenance",
    "RunReport",
    "RunnerError",
    "citability",
    "inspect_report_document",
    "main",
    "resolve_observer",
    "run",
]

#: The one repository whose code may claim to be Governance. A vendored copy of
#: this package sitting inside a product gets that product's remote, so it
#: cannot satisfy this and cannot assert it is Governance. Before this constant
#: existed, `GOVERNANCE_ROOT` was derived from the package's own file location
#: alone: a copied package produced its own root, its own peeled HEAD and
#: a citable verdict naming a revision that is not a Governance commit --
#: including from a MODIFIED copy, which is the interesting case.
CANONICAL_GOVERNANCE = "https://github.com/michaelayoade/dotmac_governance"

#: The run report's own contract string. A consumer that cannot find this key
#: is not looking at a Kernel-adoption run, and must not treat what it has as
#: one.
RUN_CONTRACT = "KernelAdoptionRun.v1"

_PEELED_COMMIT = re.compile(r"^[0-9a-f]{40}$")
#: `package.module:callable`. A colon, so the module and the attribute cannot
#: be confused when either contains a dot.
_OBSERVER_REFERENCE = re.compile(r"^[A-Za-z_][\w.]*:[A-Za-z_]\w*$")

#: Where the Governance checkout that is executing lives. Derived from this
#: file, never from an argument: a product that could name the Governance root
#: could name a revision it did not run.
GOVERNANCE_ROOT = Path(__file__).resolve().parent.parent

PROFILE_PATH = PurePosixPath(".dotmac/standards-profile.json")


class RunnerError(Exception):
    """The run could not be made. Distinct from the run finding something.

    A refusal to run and a run that found violations both fail, and they fail
    for opposite reasons — one says nothing was measured, the other says
    something was. They carry different exit codes so a workflow log can be
    read without opening the report.
    """


@dataclass(frozen=True)
class ProductObservation:
    """Everything a product supplies. Deliberately not a classification.

    There is no declaration field and there will not be one. If a product could
    return a `DeclarationOutcome`, it could return `DeclarationPresent` with
    empty tuples, and the five refusals this package exists for would become
    advisory — an absent declaration would read as "nothing is prohibited"
    exactly as if nobody had written the refusals at all.

    `catalogue` is `KernelSurfaceCatalogue | None` and `None` is a STATED
    absence: a repository that consumes no Kernel has no catalogue to state,
    and inventing one would put a version and a revision nobody read into a
    report. Every Kernel import measured without a catalogue is reported
    `kernel.catalogue.absent`, so the absence cannot buy silence.
    """

    sources: dict[PurePosixPath, str]
    catalogue: KernelSurfaceCatalogue | None
    pin_sites: tuple[PinSite, ...] = field(default_factory=tuple)


#: The whole product-side contract.
Observer = Callable[[Path], ProductObservation]


def resolve_observer(reference: str) -> Observer:
    """Import `package.module:callable` and return it, or refuse.

    Every failure is a refusal rather than a fallback. There is no default
    observer, because a default would let a product whose observer failed to
    import be measured over an inventory somebody else chose — which is a clean
    run over the wrong subject, the worst of the available outcomes.
    """
    if not _OBSERVER_REFERENCE.fullmatch(reference):
        raise RunnerError(
            f"the observer reference {reference!r} is not "
            "`package.module:callable`. A reference that cannot be resolved "
            "exactly would be guessed, and a guessed observer measures a "
            "subject nobody chose"
        )
    module_name, _, attribute = reference.partition(":")
    try:
        module = importlib.import_module(module_name)
    except Exception as error:  # noqa: BLE001 - product code, any failure refuses
        raise RunnerError(
            f"the observer module {module_name!r} could not be imported: "
            f"{error!r}. Refusing to continue: a run with no observation is a "
            "run over nothing"
        ) from error
    try:
        candidate = getattr(module, attribute)
    except AttributeError as error:
        raise RunnerError(
            f"{module_name!r} declares no {attribute!r}. The product-side "
            "surface is exactly one callable, and this reference names none"
        ) from error
    if not callable(candidate):
        raise RunnerError(
            f"{reference} is not callable; the product-side surface is a "
            "callable returning a ProductObservation"
        )
    observer: Observer = candidate
    return observer


def _git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise RunnerError(
            f"git could not be executed to bind the report to a revision: "
            f"{error}. An unbound report names no particular bytes"
        ) from error
    if completed.returncode != 0:
        raise RunnerError(
            f"`git {' '.join(arguments)}` failed in {root}: "
            f"{completed.stderr.strip()}. Refusing to emit a report that names "
            "no revision"
        )
    return completed.stdout.strip()


def _revision(root: Path, what: str) -> str:
    """The peeled commit at `root`'s HEAD, or a refusal.

    Fails closed on purpose. ADR 0013 § 3 refuses a coordinate that can move,
    and a report with no coordinate at all is worse than one with a moving
    coordinate: nothing about it can be re-derived, so nobody can say it was
    wrong.
    """
    revision = _git(root, "rev-parse", "HEAD")
    if not _PEELED_COMMIT.fullmatch(revision):
        raise RunnerError(
            f"the {what} revision {revision!r} is not a peeled 40-character commit"
        )
    return revision


def _worktree_clean(root: Path) -> bool:
    """Whether `root` holds exactly the bytes of its own HEAD.

    Recorded rather than refused, and then REQUIRED by `citability`. A local
    run with edits is useful and must stay possible; a report from one must not
    be citable as enforcement, because the revision it names is not the bytes
    it measured.
    """
    return _git(root, "status", "--porcelain") == ""


class Provenance(str, Enum):
    """How this run established that the code measuring is Governance's.

    Two values and no third. There is deliberately no "unverified" member: a
    run whose provenance cannot be established is a `RunnerError`, not a
    report carrying a caveat, because a caveat in a field is exactly what a
    later reader stops noticing.
    """

    #: Governance measuring itself. The measured root IS the Governance
    #: checkout, and that checkout's remote is the canonical repository.
    SELF = "self"
    #: A product measuring itself with a Governance checkout beside it, whose
    #: remote is canonical AND whose HEAD is the exact revision the product's
    #: own profile pins under `governance_model`.
    PINNED = "pinned"


#: The three spellings of a forge remote this accepts, and no fourth. Each
#: captures `host` and `path`, and everything else -- `file://`, a relative
#: path, a bare directory, an unrecognised scheme -- is REFUSED rather than
#: guessed at, because a spelling nobody wrote a rule for is a spelling nobody
#: reviewed.
_ORIGIN_SPELLINGS = (
    re.compile(r"^https://(?P<host>[^/]+)/(?P<path>.+?)/?$"),
    re.compile(r"^ssh://(?:[^@/]+@)?(?P<host>[^/]+)/(?P<path>.+?)/?$"),
    re.compile(r"^[^@/]+@(?P<host>[^:/]+):(?P<path>.+?)/?$"),
)


def _normalise_origin(url: str) -> str | None:
    """One canonical spelling of a forge remote, or None if it is not one.

    Host is lower-cased; the owner/repo path is NOT, and the comparison against
    `CANONICAL_GOVERNANCE` is therefore case-sensitive on it. That is
    deliberate and fail-closed: whether `Owner/Repo` and `owner/repo` are the
    same repository is a per-forge question, and a case-folding rule that is
    right for GitHub and wrong elsewhere is worse than a refusal whose repair
    is writing the canonical spelling.
    """
    raw = url.strip()
    for pattern in _ORIGIN_SPELLINGS:
        match = pattern.fullmatch(raw)
        if match is None:
            continue
        host = match.group("host").lower()
        path = match.group("path").removesuffix(".git").strip("/")
        if not path:
            return None
        return f"https://{host}/{path}"
    return None


def _observed_origin(root: Path) -> tuple[str, str]:
    """Return (literal, normalised) `remote.origin.url` as CONFIGURED at `root`.

    `git config --local --get`, deliberately, and NOT `git remote get-url`.
    `get-url` applies `url.<base>.insteadOf`, so a single rewrite rule in the
    runner's GLOBAL git config makes any remote report as the canonical one --
    a bypass that leaves nothing at all in the tree and is cheaper than
    modifying the checkout. Measured on 2026-09-06: with an `insteadOf` rule
    present, `get-url` returned the canonical URL for a remote configured to
    `dotmac_erp`, and `config --local --get` returned `dotmac_erp`. The plant
    is a permanent control.

    **What this is: configured-origin EVIDENCE.** It is a local configuration
    value that says which repository this checkout was set up to talk to. It is
    NOT proof that the checkout descends from the canonical repository, and
    nothing here observes ancestry, signatures or the remote itself. What it
    stops is a product that COPIES this package into its own tree and thereby
    inherits the ability to assert it is Governance -- a mistake somebody makes
    by accident. It does not stop anyone who controls the checkout and writes
    the value they want.
    """
    completed = subprocess.run(
        ["git", "-C", str(root), "config", "--local", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RunnerError(
            f"{root} configures no local remote.origin.url, so which repository "
            "supplied this runner is unobserved. Refusing to assume it is "
            f"{CANONICAL_GOVERNANCE}"
        )
    literal = completed.stdout.strip()
    normalised = _normalise_origin(literal)
    if normalised is None:
        raise RunnerError(
            f"the configured remote.origin.url {literal!r} is not a spelling "
            "this recognises (https://, ssh:// or user@host:path). Refusing to "
            "compare an unrecognised spelling: a guess here is the whole "
            "provenance claim"
        )
    return literal, normalised


def _governance_pin(root: Path) -> PinnedGovernanceModelRef | None:
    """The Governance revision `root`'s own profile pins, or None if it is local.

    Read through `standards_control`'s field parser rather than
    `parse_profile`: that function requires `schema_version` 11 exactly, and
    the three enrolled products are still at 9, so a whole-profile parse would
    refuse every product for a reason that has nothing to do with the pin.
    """
    path = root / PROFILE_PATH
    if not path.is_file():
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} does not exist, so this repository "
            "states no governance_model and the Governance revision it claims "
            "to be governed by is unknown. A run that cannot say which "
            "Governance measured it is not bindable"
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} could not be read: {error}"
        ) from error
    if not isinstance(document, dict) or "governance_model" not in document:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} states no governance_model, so the "
            "Governance revision this repository is governed by is unknown"
        )
    try:
        model = parse_governance_model(document["governance_model"])
    except ProfileError as error:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} governance_model does not parse: {error}"
        ) from error
    if model.kind is GovernanceSourceKind.LOCAL:
        return None
    assert isinstance(model, PinnedGovernanceModelRef)
    return model


def _provenance(
    governance_root: Path, product_root: Path, governance_revision: str
) -> tuple[Provenance, str, str]:
    """Establish that the code doing the measuring really is Governance's.

    Two admissible shapes, and everything else refuses:

    - **self** -- the measured root and the Governance root are the same
      directory, and its remote is `CANONICAL_GOVERNANCE`. This is Governance
      running its own gate. A product that VENDORED the package would also see
      the two roots coincide, which is why the remote is checked here and not
      only on the pinned path: the vendored copy carries the product's remote.
    - **pinned** -- the measured repository's own profile pins Governance by
      canonical URL and revision, the Governance checkout's remote is
      canonical, and its HEAD is exactly that revision. A run against a
      Governance revision the product did not pin is refused, so a product
      cannot be measured by code it never agreed to be measured by, and cannot
      claim enforcement from a Governance checkout it silently moved.
    """
    literal, observed = _observed_origin(governance_root)
    if observed != CANONICAL_GOVERNANCE:
        raise RunnerError(
            f"the checkout supplying this runner configures origin {literal!r} "
            f"({observed}), not {CANONICAL_GOVERNANCE!r}. Only the canonical "
            "Governance repository may assert that a run was performed by "
            "Governance; a vendored copy of this package is a copy of the code "
            "and not the authority behind it"
        )
    if governance_root.resolve() == product_root.resolve():
        return Provenance.SELF, literal, observed
    pin = _governance_pin(product_root)
    if pin is None:
        raise RunnerError(
            f"{product_root} states governance_model kind 'local', which only "
            "the Governance repository itself may state, and it is not the "
            "repository being measured here. A product states a PINNED "
            "governance_model or it has not said which Governance governs it"
        )
    if str(pin.canonical_url) != CANONICAL_GOVERNANCE:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} pins governance at "
            f"{str(pin.canonical_url)!r}, not {CANONICAL_GOVERNANCE!r}"
        )
    if str(pin.revision) != governance_revision:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} pins Governance at {str(pin.revision)} "
            f"and this runner is at {governance_revision}. Refusing to measure "
            "a repository with a Governance revision it has not pinned: the "
            "report would name a revision the measured repository never agreed "
            "to, and a product that pinned an older Governance would appear "
            "enforced by a newer one it has not adopted"
        )
    return Provenance.PINNED, literal, observed


def _declaration_binding(root: Path) -> KernelAdoptionBinding | None:
    """This repository's Kernel-adoption binding, or `None` if it states none.

    The binding is read through `standards_control`'s own parser rather than by
    reaching into the JSON here, because that contract has an owner and a
    second reader of it is a second parser. What comes back is the WHOLE
    binding, not just the path: `contract_version` is the other half, and until
    2026-09-06 it was parsed, validated against a vocabulary and then compared
    with nothing -- a declared field no arm read, inside the package that
    exists to catch declared fields no arm reads.

    A profile that exists and cannot be read is a REFUSAL, not a fall back to
    the default path: if the binding may name a non-default location, then an
    unreadable profile means the declaration's location is unknown, and reading
    the default path would be answering a question that could not be answered.
    """
    path = root / PROFILE_PATH
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} exists and could not be read: {error}. "
            "It may bind the declaration to a non-default path, so where the "
            "declaration lives is now unknown; refusing to read the default "
            "path as though the binding had been checked"
        ) from error
    if not isinstance(document, dict) or "kernel_adoption_binding" not in document:
        return None
    try:
        return parse_kernel_adoption_binding(document["kernel_adoption_binding"])
    except ProfileError as error:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} states a kernel_adoption_binding that "
            f"does not parse: {error}"
        ) from error


def _location_for(binding: KernelAdoptionBinding | None) -> PurePosixPath:
    """Where the declaration lives: the bound path, or the default if unbound.

    ONE writer of this rule, called by both `run` and `_declaration_location`.
    Two spellings of "which file do we read" is precisely the shape that lets a
    fall-back reappear on one of them.

    The default is reached ONLY when `binding` is `None` -- an explicit absence
    of a binding. There is no path on which a STATED binding resolves here: a
    binding that does not parse raises in `_declaration_binding`, and a binding
    that names a file refuses on that file. A product that names a document and
    gets a different one evaluated is worse off than one that names nothing,
    because it has been told its own choice was honoured.
    """
    return DECLARATION_PATH if binding is None else binding.declaration_path


def _declaration_location(root: Path) -> PurePosixPath:
    """`_location_for` over this repository's own binding. Read by tests."""
    return _location_for(_declaration_binding(root))


def _check_bound_contract(
    binding: KernelAdoptionBinding | None, outcome: DeclarationOutcome
) -> None:
    """The profile bound a contract; is the document written under it?

    A `RunnerError` and not a `Finding`, deliberately, and the boundary is the
    reason. `FindingCode` is a closed vocabulary about PRODUCT SOURCE, and
    `test_no_finding_code_speaks_about_a_profile_document` holds it there --
    adding a code about a profile binding would be this package acquiring an
    opinion on a document `standards_control` owns. A binding that names the
    wrong contract is also not a finding in the ordinary sense: nothing was
    measured wrongly, the wrong document was measured.

    Silent when the repository states NO binding. That is not a loophole: an
    unbound repository is read at the default path and has claimed no contract,
    so there is nothing to disagree with. It is also silent when the
    declaration did not parse -- one of the four refusals already stands, and
    reporting that a refusal is not the bound contract sends the reader to the
    profile when the repair is in the document.
    """
    if binding is None or not isinstance(outcome, DeclarationPresent):
        return
    stated = outcome.declaration.contract
    if stated == binding.contract_version:
        return
    raise RunnerError(
        f"{PROFILE_PATH.as_posix()} binds "
        f"{binding.declaration_path.as_posix()} as "
        f"{binding.contract_version} and that document states {stated!r}. The "
        "repository is bound to one contract and has written another, so the "
        "fields the binding promised would be measured are not the fields the "
        "document carries. Refusing rather than reading the document under "
        "whichever contract it happens to name: a binding that is overridden "
        "by the file it points at is not a binding"
    )


def _predecessor_observation(
    root: Path, declared: str, measured: str
) -> PredecessorObservation:
    """Ask this repository's own history whether `declared` precedes `measured`.

    A repository-local Git query inside the measured repository's own job, so
    ADR 0013 § 1 needs no oracle for it: nothing here reaches a network or
    another repository.

    Three answers, and the third is the one that matters operationally.
    `git merge-base --is-ancestor` exits 0 for an ancestor and 1 for a
    non-ancestor, and ANY other exit is treated as undecided rather than as a
    refutation -- an unknown commit in a SHALLOW clone exits 128, and reading
    that as "not an ancestor" would report a false violation to every product
    using `actions/checkout`'s default depth.

    Equality is refuted here rather than delegated. A declaration naming the
    revision that contains it is claiming a file knows a hash over its own
    bytes, and `--is-ancestor` calls a commit its own ancestor, so the strict
    half has to be asked separately or the impossible case would pass.
    """
    if declared == measured:
        return PredecessorObservation(
            declared=declared,
            measured=measured,
            is_strict_ancestor=False,
            detail=(
                "the declared coordinate IS the measured revision. A committed "
                "file cannot contain its own commit, so a declaration naming "
                "the revision that contains it names something that could not "
                "have been written -- the coordinate is a predecessor or it is "
                "nothing"
            ),
        )
    shallow = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-shallow-repository"],
        capture_output=True,
        text=True,
        check=False,
    )
    if shallow.returncode == 0 and shallow.stdout.strip() == "true":
        return PredecessorObservation(
            declared=declared,
            measured=measured,
            is_strict_ancestor=None,
            detail=(
                "this checkout is SHALLOW, so most of its history is absent "
                "and ancestry cannot be decided here. Check out with "
                "`fetch-depth: 0`; a truncated history cannot refute an "
                "ancestor and must not be read as having done so"
            ),
        )
    completed = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", declared, measured],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return PredecessorObservation(
            declared=declared,
            measured=measured,
            is_strict_ancestor=True,
            detail=f"{declared} is a strict ancestor of {measured}",
        )
    if completed.returncode == 1:
        return PredecessorObservation(
            declared=declared,
            measured=measured,
            is_strict_ancestor=False,
            detail=("git reports it is not an ancestor of the measured revision"),
        )
    return PredecessorObservation(
        declared=declared,
        measured=measured,
        is_strict_ancestor=None,
        detail=(
            f"`git merge-base --is-ancestor` exited {completed.returncode}: "
            f"{completed.stderr.strip() or 'no diagnostic'}. The usual cause "
            "is that the commit is not present in this checkout at all. An "
            "exit code that is neither 0 nor 1 is not a refutation and is not "
            "read as one"
        ),
    )


def _declaration_summary(outcome: DeclarationOutcome) -> dict[str, object]:
    if isinstance(outcome, DeclarationPresent):
        declaration = outcome.declaration
        summary: dict[str, object] = {
            "state": "present",
            "contract": declaration.contract,
            "applicability": declaration.applicability.value,
            "transitional_surfaces": len(declaration.transitional_surfaces),
        }
        if isinstance(declaration, KernelAdoptionDeclarationV2):
            summary["declared_at"] = declaration.declared_at.isoformat()
            summary["source_predecessor"] = declaration.source_predecessor
            summary["required_surfaces"] = len(declaration.required_surfaces)
            # WHICH source-surface canonicalization this run compared under.
            # Since the contract admits both `dmg-kernel-surface-v1` and
            # `dmg-kernel-surface-v2`, the declared algorithm SELECTS the
            # evaluation, and a reader holding only this artifact could not
            # otherwise tell which of the two ran. Same reason
            # `catalogue_digest_algorithm` is recorded below, and the same
            # standing rule behind it: a v1 receipt is never v2 evidence.
            # `None` when the declaration states no coordinate, which is a
            # `not_applicable` document -- reported rather than omitted, so
            # "no coordinate" and "key absent" are not the same reading.
            summary["source_surface_algorithm"] = (
                None
                if declaration.source_surface is None
                else declaration.source_surface.algorithm
            )
        else:
            summary["declared_product_revision"] = declaration.product_revision
        return summary
    return {"state": type(outcome).__name__, "detail": outcome.detail}


#: Every `RunReport` this process's `run()` produced, held weakly.
#:
#: This is the whole of the answer to "did the runner produce this, or did
#: someone write it?" -- see `citability`. A `WeakSet` rather than a list so a
#: long-lived process does not retain every report it ever made, and identity
#: membership rather than value membership, which is why `RunReport` is
#: `eq=False`: with dataclass equality, a hand-built report equal in every
#: field would test as a member of this set and the distinction would be
#: decoration.
_PRODUCED: weakref.WeakSet[RunReport] = weakref.WeakSet()


@dataclass(frozen=True, eq=False)
class RunReport:
    """One run, bound to the two revisions that produced and were measured.

    `eq=False` is load-bearing rather than an omission: identity is what
    `_PRODUCED` membership must test. Two reports with identical fields are
    still two reports, and only one of them came out of `run()`.
    """

    as_of: date
    provenance: Provenance
    governance_origin_configured: str
    governance_origin: str
    governance_revision: str
    governance_worktree_clean: bool
    product_root: str
    product_revision: str
    product_worktree_clean: bool
    declaration_path: PurePosixPath
    declaration: DeclarationOutcome
    observer: str
    source_count: int
    pin_site_count: int
    catalogue: KernelSurfaceCatalogue | None
    report: AdoptionReport

    def to_dict(self) -> dict[str, object]:
        return {
            "contract": RUN_CONTRACT,
            "as_of": self.as_of.isoformat(),
            "governance": {
                "provenance": self.provenance.value,
                # What was OBSERVED, never the module constant. Emitting
                # `CANONICAL_GOVERNANCE` here made every copy of this runner --
                # vendored or not -- report the canonical URL, so the
                # predicate's vendoring arm could not fail on any report the
                # runner actually produced. The run-side check was real and the
                # predicate-side one was decoration.
                "origin_configured": self.governance_origin_configured,
                "origin": self.governance_origin,
                "revision": self.governance_revision,
                "worktree_clean": self.governance_worktree_clean,
            },
            "product": {
                "root": self.product_root,
                "revision": self.product_revision,
                "worktree_clean": self.product_worktree_clean,
                "declaration_path": self.declaration_path.as_posix(),
                "declaration": _declaration_summary(self.declaration),
            },
            "observation": {
                "observer": self.observer,
                "source_count": self.source_count,
                "pin_site_count": self.pin_site_count,
                "catalogue": (
                    None
                    if self.catalogue is None
                    else {
                        "version": self.catalogue.version,
                        "revision": self.catalogue.revision,
                        "supported": len(self.catalogue.supported),
                        "internal": len(self.catalogue.internal),
                        # Reported for the same reason the other two are: the
                        # root façade is a published surface measured against
                        # its own list, and a reader must be able to see
                        # whether that list was observed at all.
                        "root_exports": len(self.catalogue.root_exports),
                        # WHICH canonicalization the digest comparison in this
                        # run was taken under, recorded on the artifact that IS
                        # the evidence. `kernel_catalogue` carries no
                        # `algorithm` field (unlike `source_surface`), so
                        # without this a stored receipt could not say whether
                        # its catalogue digest was a v1 or a v2 value.
                        #
                        # Relabelling a v1 receipt as v2 evidence is refused
                        # structurally as well as legibly: the algorithm name
                        # is the FIRST line of the bytes digested, so a v1
                        # value can never verify under v2 for any input. This
                        # field makes that legible; the domain separation is
                        # what makes it true.
                        "catalogue_digest_algorithm": CATALOGUE_DIGEST_ALGORITHM,
                    }
                ),
            },
            "findings": self.report.to_dict(),
        }


def run(
    *,
    product_root: Path,
    observer_reference: str,
    as_of: date,
    governance_root: Path = GOVERNANCE_ROOT,
) -> RunReport:
    """Evaluate one product checkout. The declaration is read HERE, not supplied."""
    root = product_root.resolve()
    if not root.is_dir():
        raise RunnerError(f"{root} is not a directory")

    governance_revision = _revision(governance_root, "governance")
    product_revision = _revision(root, "product")
    provenance, origin_configured, origin = _provenance(
        governance_root, root, governance_revision
    )

    binding = _declaration_binding(root)
    location = _location_for(binding)
    outcome = read_declaration(root, location)
    _check_bound_contract(binding, outcome)

    with _import_root(root):
        observer = resolve_observer(observer_reference)
        try:
            observation = observer(root)
        except Exception as error:  # noqa: BLE001 - product code, any failure refuses
            raise RunnerError(
                f"the observer {observer_reference} raised {error!r}. A run "
                "whose observation failed reports nothing, and reporting "
                "nothing as clean is the failure this package exists to "
                "prevent"
            ) from error
    if not isinstance(observation, ProductObservation):
        raise RunnerError(
            f"the observer {observer_reference} returned "
            f"{type(observation).__name__}, not a ProductObservation"
        )

    predecessor: PredecessorObservation | None = None
    if isinstance(outcome, DeclarationPresent) and isinstance(
        outcome.declaration, KernelAdoptionDeclarationV2
    ):
        predecessor = _predecessor_observation(
            root, outcome.declaration.source_predecessor, product_revision
        )

    report = evaluate(
        KernelAdoptionInputs(
            sources=observation.sources,
            catalogue=observation.catalogue,
            declaration=outcome,
            as_of=as_of,
            pin_sites=observation.pin_sites,
            predecessor=predecessor,
        )
    )
    result = RunReport(
        as_of=as_of,
        provenance=provenance,
        governance_origin_configured=origin_configured,
        governance_origin=origin,
        governance_revision=governance_revision,
        governance_worktree_clean=_worktree_clean(governance_root),
        product_root=str(root),
        product_revision=product_revision,
        product_worktree_clean=_worktree_clean(root),
        declaration_path=location,
        declaration=outcome,
        observer=observer_reference,
        source_count=len(observation.sources),
        pin_site_count=len(observation.pin_sites),
        catalogue=observation.catalogue,
        report=report,
    )
    # The one place a report becomes citable-in-principle. Registered AFTER
    # construction succeeds, so a partially built report never enters the set.
    _PRODUCED.add(result)
    return result


class DocumentVerdict(str, Enum):
    """What can be established by reading a run report DOCUMENT, and no more.

    Two values, and the absent third is the point. There is deliberately no
    `CITABLE` member, because no property of a JSON document establishes that
    a run produced it: anyone who can write the file can write a well-formed
    one. A reader holding a document literally cannot obtain "citable" from
    this function, which is a stronger guarantee than a caveat in a docstring
    that the next reader skips.
    """

    #: Every internal-consistency condition holds. This says the document does
    #: not contradict ITSELF. It says nothing whatever about where it came from.
    WELL_FORMED = "well_formed"
    #: A condition failed. Not a run report, or one that disagrees with itself.
    MALFORMED = "malformed"


class Citability(str, Enum):
    """Whether a report may be cited as CI enforcement. Two values, no third."""

    CITABLE = "citable"
    NOT_CITABLE = "not_citable"


def inspect_report_document(
    document: Mapping[str, object],
) -> tuple[DocumentVerdict, str]:
    """Check a run-report document against ITSELF. Never against reality.

    **This function cannot decide enforcement and no longer pretends to.**
    Until 2026-09-06 it was `is_enforced(document) -> (bool, str)`, and open
    decision 52 (5) named the defect precisely: `is_enforced` was a predicate
    over a REPORT, not over a repository, so anyone who could write the JSON
    could write a passing one. Its own test suite demonstrated it -- the admit
    control was a hand-built dictionary that returned `True`. A predicate whose
    positive case has only ever been exhibited by a fabricated input is not
    measuring what its name says.

    What was available to fix it, and what was chosen. Re-derivation from
    inputs is not possible here: the document's inputs are a product checkout
    at a revision this process may no longer hold. A coordinate only a real run
    could compute would be a signature, which is open decision 17's oracle and
    must not be invented here. So the third option is taken -- **the predicate
    refuses to answer outside a context it can verify** -- and it is
    implemented structurally: this function's return type has no citable value
    in it, and `citability` takes a `RunReport` OBJECT that must have come out
    of `run()` in this process.

    **The honest boundary, stated plainly: a run report written to disk is not
    self-authenticating and this change does not make it one.** The citable
    claim lives in the EXIT CODE of the job that performed the run, not in the
    artifact it left behind. A consumer reading a stored document gets
    `WELL_FORMED` at best, which means "this document does not contradict
    itself", and any further claim about it needs an oracle this repository
    does not have.

    Every condition below is one an enrolment claim has been made without
    somewhere in this fleet.
    """

    def reject(reason: str) -> tuple[DocumentVerdict, str]:
        return DocumentVerdict.MALFORMED, reason

    if document.get("contract") != RUN_CONTRACT:
        return reject(
            f"the document states contract {document.get('contract')!r}, not "
            f"{RUN_CONTRACT!r}: this is not a Kernel-adoption run report, and a "
            "Governance revision predating the runner produces none"
        )
    governance = document.get("governance")
    if not isinstance(governance, Mapping):
        return reject("the report names no governance revision")
    if governance.get("origin") != CANONICAL_GOVERNANCE:
        return reject(
            f"the report records observed origin {governance.get('origin')!r}, "
            f"not {CANONICAL_GOVERNANCE!r}: a vendored copy of this package is "
            "a copy of the code and not the authority behind it. This is "
            "configured-origin evidence and not proof of remote ancestry"
        )
    if governance.get("provenance") not in {item.value for item in Provenance}:
        return reject(
            f"the report states provenance {governance.get('provenance')!r}, "
            "which is not an established one. A run that cannot say how it "
            "knows the measuring code was Governance's is not enforcement"
        )
    revision = governance.get("revision")
    if not isinstance(revision, str) or not _PEELED_COMMIT.fullmatch(revision):
        return reject(
            f"the governance revision {revision!r} is not a peeled commit, so "
            "the bytes that produced this report cannot be re-read"
        )
    if governance.get("worktree_clean") is not True:
        return reject(
            "the Governance checkout that produced this report had "
            "uncommitted changes, so the revision it names is not the code "
            "that ran"
        )
    product = document.get("product")
    if not isinstance(product, Mapping):
        return reject("the report names no product revision")
    measured = product.get("revision")
    if not isinstance(measured, str) or not _PEELED_COMMIT.fullmatch(measured):
        return reject(
            f"the product revision {measured!r} is not a peeled commit, so what "
            "was measured cannot be re-read"
        )
    if product.get("worktree_clean") is not True:
        return reject(
            "the measured checkout had uncommitted changes, so the revision it "
            "names is not the source that was read"
        )
    observation = document.get("observation")
    if not isinstance(observation, Mapping):
        return reject("the report records no observation")
    count = observation.get("source_count")
    # `isinstance(True, int)` is True, so `source_count: true` read as one file
    # and satisfied this arm. A boolean where a count belongs is a malformed
    # report, not a small one.
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        return reject(
            f"the observation supplied {count!r} source files; a sweep over an "
            "empty inventory passes for the wrong reason, and a non-integer "
            "count is a malformed report rather than a small one"
        )
    declaration = product.get("declaration")
    if not isinstance(declaration, Mapping):
        return reject("the report records no declaration state")
    if declaration.get("state") != "present":
        return reject(
            f"the declaration was {declaration.get('state')!r} rather than "
            "present, which is a refusal"
        )
    findings = document.get("findings")
    if not isinstance(findings, Mapping):
        return reject("the report records no findings section")
    #: `conforms` was taken on trust, so `{"conforms": true, "findings": [ten
    #: errors]}` was citable: the predicate checked the report's SHAPE and
    #: never checked the report against ITSELF. A summary verdict that nothing
    #: recomputes is the same defect as a declared field nothing reads.
    items = findings.get("findings")
    if not isinstance(items, list):
        return reject(
            f"the findings section carries {type(items).__name__} where a list "
            "of findings belongs, so `conforms` summarises nothing"
        )
    known = {item.value for item in Severity}
    errors: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            return reject(f"findings[{index}] is not an object")
        severity = item.get("severity")
        #: `in` on a set hashes its operand, so a severity carried as a dict or
        #: a list raised TypeError here and the predicate CRASHED rather than
        #: refusing -- a malformed report escaping through the arm written to
        #: refuse malformed reports. Narrow to a string first: anything else is
        #: unrecognised by construction.
        if not isinstance(severity, str) or severity not in known:
            return reject(
                f"findings[{index}] states severity {severity!r}, which is not "
                f"one of {sorted(known)}. An unrecognised severity must not "
                "read as a harmless one: that is how a report comes to contain "
                "a failure nobody counted"
            )
        if severity == Severity.ERROR.value:
            errors.append(str(item.get("code")))
    if errors:
        return reject(
            f"the report carries {len(errors)} error finding(s) "
            f"({', '.join(sorted(set(errors)))}), so it is not citable "
            f"regardless of what `conforms` says — and it says "
            f"{findings.get('conforms')!r}"
        )
    if findings.get("conforms") is not True:
        return reject(
            f"the run states conforms {findings.get('conforms')!r} over "
            f"{len(items)} finding(s), none of them an error. A report that "
            "disagrees with itself is refused in both directions"
        )
    return DocumentVerdict.WELL_FORMED, (
        f"self-consistent run report: Governance {revision} over product "
        f"{measured}, {count} source file(s), {len(items)} notice(s), no "
        f"errors, as of {document.get('as_of')}. This says the document "
        "agrees with itself and NOTHING about who wrote it"
    )


def citability(report: RunReport) -> tuple[Citability, str]:
    """Whether a report `run()` produced in THIS process may be cited, and why not.

    Three conditions, in the order that makes each refusal name one repair.

    **1. This process produced it.** Identity membership of `_PRODUCED`. That
    is the narrow, honest thing item (5) of open decision 52 asked for: it
    distinguishes a runner-produced report from a caller-constructed one, and
    it does so within the only scope where the distinction is decidable at all.
    A `RunReport` a test or a caller builds by hand is refused however
    plausible its fields, which is exactly what a hand-built dictionary used to
    get away with.

    **What this does NOT prove**, because the boundary is the finding: it says
    nothing about a report in a file, in another process, or in another job.
    Serialising a citable report and reading it back yields a document, and
    `inspect_report_document` will only ever call a document well-formed.
    Crossing that boundary needs an oracle -- decision 17 -- and inventing a
    signature scheme here would be creating a second one.

    **2. The document agrees with itself.** Every arm of
    `inspect_report_document`, applied to this report's own serialization, so
    the two can never diverge: the thing checked is the thing published.

    **3. The declaration's contract is one whose fields are all read.** A
    `KernelAdoptionDeclaration.v1` `applicable` declaration carries
    `product_revision`, `kernel_catalogue` and `required_surfaces`, and no arm
    reads them, so a report over one cannot be cited as enforcing it. That
    refusal stands unchanged. A `v2` `applicable` declaration is citable
    because every field v2 requires has an arm -- which is what the successor
    contract is FOR. A `not_applicable` declaration of either version is
    citable on the reasoning ADR 0042 § A8 already settled: what it claims is a
    premise, and the premise is independently evaluated.
    """
    if report not in _PRODUCED:
        return Citability.NOT_CITABLE, (
            "this RunReport was not produced by run() in this process. A "
            "report is citable as enforcement only where the run that made it "
            "can be established, and constructing the type is not performing "
            "the run. A stored document can never satisfy this: the citable "
            "claim lives in the exit code of the job that ran, not in the "
            "artifact it left behind"
        )
    document = report.to_dict()
    verdict, reason = inspect_report_document(document)
    if verdict is not DocumentVerdict.WELL_FORMED:
        return Citability.NOT_CITABLE, reason
    outcome = report.declaration
    if not isinstance(outcome, DeclarationPresent):
        # Unreachable: `inspect_report_document` already refuses a declaration
        # state other than `present`. Kept because a refusal that depends on
        # another function's arm is a refusal that disappears when that arm
        # moves.
        return Citability.NOT_CITABLE, (
            f"the declaration was {type(outcome).__name__}, which is a refusal"
        )
    declaration = outcome.declaration
    applicable = declaration.applicability is KernelAdoptionApplicability.APPLICABLE
    if applicable and declaration.contract == KERNEL_ADOPTION_CONTRACT:
        return Citability.NOT_CITABLE, (
            f"the declaration is {KERNEL_ADOPTION_CONTRACT} and 'applicable', "
            "and no arm reads its product_revision, kernel_catalogue or "
            "required_surfaces. Citing it would claim coverage of three "
            "declared fields nothing compares. The repair is the successor "
            f"contract {KERNEL_ADOPTION_CONTRACT_V2}, whose every required "
            "field has an arm -- not an edit to v1, which is frozen"
        )
    return Citability.CITABLE, (
        f"{reason}; declaration {declaration.contract} "
        f"'{declaration.applicability.value}', produced by this run"
    )


@contextlib.contextmanager
def _import_root(root: Path) -> Iterator[None]:
    """Put the measured checkout on `sys.path` for the observer load, then remove it.

    `main` used to insert it and leave it there, which made the measured
    checkout the PRIMARY import root for the rest of the process -- broader
    than the "an observer is called" exposure ADR 0042 § A9 names, because any
    later import in the same process, including a stdlib-shadowing name, would
    resolve there first.

    What this does NOT undo, and the reason it is a narrowing rather than a
    fix: the observer module stays in `sys.modules`, and its import already
    executed the product's code. Restoring the path cannot unrun that. The
    exposure is bounded by running in the measured repository's own job over
    its own trusted commit, which is ADR 0044's subject and not this module's.
    """
    entry = str(root.resolve())
    sys.path.insert(0, entry)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(entry)


def _as_of(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not an ISO YYYY-MM-DD date"
        ) from error


def main(argv: list[str] | None = None) -> int:
    """Run the check over one product checkout.

    `--as-of` is REQUIRED and has no default, which is the whole point of it.
    A default of "today" would be a clock read wearing an argument's clothes:
    the verdict would depend on when the job started, and no reader could
    reproduce it. CI passes the UTC date of the run and the report records it,
    so re-running with the same `--as-of` gives the same answer forever.

    Four exit codes, because "it failed" is four different facts here:

    - **0** -- conforming AND citable as enforcement.
    - **1** -- the run found violations.
    - **2** -- the run could not be made: no provenance, no observation, an
      unreadable profile. Nothing was measured.
    - **3** -- the run conformed and is NOT citable. A `KernelAdoptionDeclaration.v1`
      `applicable` declaration always lands here, by decision rather than by
      defect: three of its fields are unread, so the run cannot be cited as
      enforcing the declaration. A `v2` `applicable` declaration does NOT --
      that is what the successor contract activated. A dirty worktree lands
      here too.
    """
    parser = argparse.ArgumentParser(
        prog="kernel_adoption_control",
        description=(
            "Evaluate one repository's Kernel-adoption declaration against its "
            "own source. Runs in the measured repository's CI, over its own "
            "checkout."
        ),
    )
    parser.add_argument("--root", default=".", help="the measured checkout")
    parser.add_argument(
        "--observer",
        required=True,
        help="package.module:callable returning a ProductObservation",
    )
    parser.add_argument(
        "--as-of",
        required=True,
        type=_as_of,
        help="the date expiries are judged against, YYYY-MM-DD",
    )
    parser.add_argument(
        "--json", default=None, help="write the bound run report to this path"
    )
    arguments = parser.parse_args(argv)

    root = Path(arguments.root)
    try:
        result = run(
            product_root=root,
            observer_reference=arguments.observer,
            as_of=arguments.as_of,
        )
    except RunnerError as error:
        print(f"kernel-adoption: REFUSED: {error}", file=sys.stderr)
        return 2

    document = result.to_dict()
    if arguments.json is not None:
        Path(arguments.json).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    for finding in result.report.findings:
        location = ""
        if finding.path is not None:
            location = f" {finding.path.as_posix()}"
            if finding.line is not None:
                location += f":{finding.line}"
        print(
            f"{finding.severity.value}: {finding.code.value}{location}: "
            f"{finding.message}"
        )

    verdict, reason = citability(result)
    print(
        f"kernel-adoption: governance {result.governance_revision} "
        f"({result.provenance.value}) over {result.product_root} at "
        f"{result.product_revision}, {result.source_count} source file(s), as "
        f"of {result.as_of.isoformat()}"
    )
    print(f"kernel-adoption: citable as enforcement: {verdict.value} ({reason})")
    if not result.report.conforms:
        return 1
    if verdict is not Citability.CITABLE:
        # The predicate was printed and nothing acted on it, so a step could go
        # green while announcing that its own result was not citable. A
        # predicate no exit code consults is a comment.
        print(
            "kernel-adoption: FAILING because this run is not citable as "
            "enforcement. A green step that announces its own result is "
            "uncitable is worse than a red one: the log says so and the badge "
            "does not, and the badge is what gets quoted",
            file=sys.stderr,
        )
        return 3
    return 0
