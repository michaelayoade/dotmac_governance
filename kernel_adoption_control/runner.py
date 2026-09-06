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
reads its own checkout. `is_enforced` is the predicate anything citing an
enrolment must use: a product pinning a Governance revision from before this
module existed produces no report at all, and a report failing any binding
condition is `enforced=False` with the reason named. "CI-enforced" is a claim
that must exhibit such a report; its absence is not a pass.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path, PurePosixPath

from standards_control.contracts import (
    GovernanceSourceKind,
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
    KernelAdoptionInputs,
    KernelSurfaceCatalogue,
    PinSite,
    Severity,
)
from .declaration import DECLARATION_PATH, read_declaration
from .engine import evaluate

__all__ = [
    "CANONICAL_GOVERNANCE",
    "RUN_CONTRACT",
    "ProductObservation",
    "Provenance",
    "RunReport",
    "RunnerError",
    "is_enforced",
    "main",
    "resolve_observer",
    "run",
]

#: The one repository whose code may claim to be Governance. A vendored copy of
#: this package sitting inside a product gets that product's remote, so it
#: cannot satisfy this and cannot assert it is Governance. Before this constant
#: existed, `GOVERNANCE_ROOT` was derived from the package's own file location
#: alone: a copied package produced its own root, its own peeled HEAD and
#: `is_enforced == True` naming a revision that is not a Governance commit --
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

    Recorded rather than refused, and then REQUIRED by `is_enforced`. A local
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


def _declaration_location(root: Path) -> PurePosixPath:
    """Where this repository's declaration lives, per its own profile binding.

    The binding is read through `standards_control`'s own parser rather than by
    reaching into the JSON here, because that contract has an owner and a
    second reader of it is a second parser.

    A profile that exists and cannot be read is a REFUSAL, not a fall back to
    the default path: if the binding may name a non-default location, then an
    unreadable profile means the declaration's location is unknown, and reading
    the default path would be answering a question that could not be answered.
    """
    path = root / PROFILE_PATH
    if not path.is_file():
        return DECLARATION_PATH
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
        return DECLARATION_PATH
    try:
        binding = parse_kernel_adoption_binding(document["kernel_adoption_binding"])
    except ProfileError as error:
        raise RunnerError(
            f"{PROFILE_PATH.as_posix()} states a kernel_adoption_binding that "
            f"does not parse: {error}"
        ) from error
    return binding.declaration_path


def _declaration_summary(outcome: DeclarationOutcome) -> dict[str, object]:
    if isinstance(outcome, DeclarationPresent):
        declaration = outcome.declaration
        return {
            "state": "present",
            "contract": declaration.contract,
            "applicability": declaration.applicability.value,
            "declared_product_revision": declaration.product_revision,
            "transitional_surfaces": len(declaration.transitional_surfaces),
        }
    return {"state": type(outcome).__name__, "detail": outcome.detail}


@dataclass(frozen=True)
class RunReport:
    """One run, bound to the two revisions that produced and were measured."""

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

    location = _declaration_location(root)
    outcome = read_declaration(root, location)

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

    report = evaluate(
        KernelAdoptionInputs(
            sources=observation.sources,
            catalogue=observation.catalogue,
            declaration=outcome,
            as_of=as_of,
            pin_sites=observation.pin_sites,
        )
    )
    return RunReport(
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


def is_enforced(document: Mapping[str, object]) -> tuple[bool, str]:
    """Whether a run report may be cited as CI enforcement, and why not if not.

    Every condition below is one an enrolment claim has been made without
    somewhere in this fleet. The predicate exists so that "Platform's Kernel
    adoption is CI-enforced" is a sentence with a checkable referent, and so
    that a product pinning a Governance revision predating the runner is
    VISIBLY unenforced rather than indistinguishable from an enforced one — it
    produces no document at all, and no document is not a pass.
    """

    def reject(reason: str) -> tuple[bool, str]:
        return False, reason

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
    #: The narrowing that makes everything above honest. An `applicable`
    #: declaration carries `product_revision`, `kernel_catalogue` and
    #: `required_surfaces`, and this runner reads NONE of them. A report over
    #: such a declaration therefore cannot be cited as enforcement of the
    #: declaration -- it enforces the part that is read, and the part that is
    #: read is not the whole document.
    #:
    #: A `not_applicable` self-run is citable, and NOT because it has no unread
    #: field -- it has one. `product_revision` is required of every declaration
    #: and compared with nothing, which is why it is now disclosed on both
    #: paths. It is citable because what such a declaration CLAIMS is a
    #: premise -- "this repository consumes no Kernel" -- and that premise IS
    #: evaluated, against the repository's own imports, and refused when false.
    #: An `applicable` declaration claims three further things that nothing
    #: reads, so citing it would assert coverage that does not exist.
    if declaration.get("applicability") != (
        KernelAdoptionApplicability.NOT_APPLICABLE.value
    ):
        return reject(
            "the declaration is 'applicable', and this runner does not "
            "evaluate product_revision, kernel_catalogue or required_surfaces. "
            "An applicable run is NOT citable as enforcement until the "
            "versioned successor contract exists (open decision 52); citing it "
            "would claim coverage of three declared fields nothing reads"
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
        if severity not in known:
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
    return True, (
        f"conforming run of Governance {revision} over product {measured}, "
        f"{count} source file(s), {len(items)} notice(s), no errors, as of "
        f"{document.get('as_of')}"
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
    - **3** -- the run conformed and is NOT citable. Today an `applicable`
      declaration always lands here, by decision rather than by defect: three
      of its fields are unread, so the run cannot be cited as enforcing the
      declaration, and open decision 52 owns the successor contract that fixes
      it. A dirty worktree lands here too.
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

    enforced, reason = is_enforced(document)
    print(
        f"kernel-adoption: governance {result.governance_revision} "
        f"({result.provenance.value}) over {result.product_root} at "
        f"{result.product_revision}, {result.source_count} source file(s), as "
        f"of {result.as_of.isoformat()}"
    )
    print(f"kernel-adoption: citable as enforcement: {enforced} ({reason})")
    if not result.report.conforms:
        return 1
    if not enforced:
        # `is_enforced` was printed and nothing acted on it, so a step could go
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
