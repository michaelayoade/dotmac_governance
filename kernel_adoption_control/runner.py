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
import importlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

from standards_control.profile import (
    ProfileError,
    parse_kernel_adoption_binding,
)

from .contracts import (
    AdoptionReport,
    DeclarationOutcome,
    DeclarationPresent,
    KernelAdoptionInputs,
    KernelSurfaceCatalogue,
    PinSite,
)
from .declaration import DECLARATION_PATH, read_declaration
from .engine import evaluate

__all__ = [
    "RUN_CONTRACT",
    "ProductObservation",
    "RunReport",
    "RunnerError",
    "is_enforced",
    "main",
    "resolve_observer",
    "run",
]

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

    location = _declaration_location(root)
    outcome = read_declaration(root, location)

    observer = resolve_observer(observer_reference)
    try:
        observation = observer(root)
    except Exception as error:  # noqa: BLE001 - product code, any failure refuses
        raise RunnerError(
            f"the observer {observer_reference} raised {error!r}. A run whose "
            "observation failed reports nothing, and reporting nothing as "
            "clean is the failure this package exists to prevent"
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
    if not isinstance(count, int) or count < 1:
        return reject(
            f"the observation supplied {count!r} source files; a sweep over an "
            "empty inventory passes for the wrong reason"
        )
    findings = document.get("findings")
    if not isinstance(findings, Mapping):
        return reject("the report records no findings section")
    if findings.get("conforms") is not True:
        return reject("the run did not conform")
    return True, (
        f"conforming run of Governance {revision} over product {measured}, "
        f"{count} source file(s), as of {document.get('as_of')}"
    )


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
    sys.path.insert(0, str(root.resolve()))
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
        f"kernel-adoption: governance {result.governance_revision} over "
        f"{result.product_root} at {result.product_revision}, "
        f"{result.source_count} source file(s), as of {result.as_of.isoformat()}"
    )
    print(f"kernel-adoption: citable as enforcement: {enforced} ({reason})")
    if not result.report.conforms:
        return 1
    return 0
