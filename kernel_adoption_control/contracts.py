"""Typed inputs and the closed finding vocabulary for Kernel-adoption conformance.

Scope, stated first because this package's boundary is the reason it exists.

`ApplicationFoundationProfile.v1` is owned by `dotmac-deployment-foundation`:
its schema, semantics, canonicalization, digest, validation, refusals and
version evolution. **Nothing here parses, canonicalizes, digests or refuses a
profile document.** There is no schema string, no loader, no serializer and no
digest in this package, and adding one would create a second verifier for a
contract that has an owner.

What this package does own is conformance over PRODUCT SOURCE — the same thing
`standards_control` already does across its 59 diagnostic codes, none of which
covers Kernel imports, Kernel pins or product-local Kernel facades. Those
checks read Python and packaging files in a product checkout and say what is
there. They consult no profile.

The inputs below are a FUNCTION SIGNATURE, deliberately not a file format. A
caller supplies them; this package never reads them from a document, because
deciding where they live is an ownership question that is open (see ADR 0042
and open decision 46) and answering it by inventing a file would be the second
document this boundary exists to prevent.

`Severity` is imported from `standards_control.contracts` rather than
redeclared, following `tools/check_receipts.py`, which reuses
`gate_control.contracts` "so the repository does not acquire a second set of
words for the same distinction". The reuse asserts nothing about either
record's status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import PurePosixPath

from standards_control.contracts import Severity

from .declaration_contract import (
    KernelAdoptionApplicability,
    KernelAdoptionDeclaration,
    ProhibitedSurface,
    RequiredSurface,
    TransitionalSurface,
)
from .declaration_contract_v2 import (
    AnyKernelAdoptionDeclaration,
    KernelAdoptionDeclarationV2,
)

__all__ = [
    "KERNEL_ROOT",
    "AdoptionReport",
    "AnyKernelAdoptionDeclaration",
    "DeclarationEmpty",
    "DeclarationIncomplete",
    "DeclarationMissing",
    "DeclarationOutcome",
    "DeclarationPresent",
    "DeclarationUnreadable",
    "Finding",
    "FindingCode",
    "KernelAdoptionApplicability",
    "KernelAdoptionDeclaration",
    "KernelAdoptionDeclarationV2",
    "KernelAdoptionInputs",
    "KernelSurfaceCatalogue",
    "PinSite",
    "PredecessorObservation",
    "normalise_observed_path",
    "ProhibitedSurface",
    "RequiredSurface",
    "Severity",
    "TransitionalSurface",
]

#: The Kernel distribution's root package name. Defined HERE rather than in
#: `engine`, because `KernelSurfaceCatalogue.publishes` has to know which
#: module is the root façade and a second spelling of the name would be a
#: second writer of the one string every arm in this package matches on.
#: `engine` re-exports it, so no caller changed.
KERNEL_ROOT = "dotmac_kernel"


class FindingCode(str, Enum):
    """The closed vocabulary of this package. Report-only; no gate cites it.

    Every member names a property of product source. There is deliberately no
    member for a malformed profile, a bad digest or a stale profile version:
    those are Foundation's refusals, raised by Foundation's verifier, and a
    code here for any of them would be this package quietly becoming the
    second one.
    """

    #: The measurement could not be taken. Fails closed: a checker that reports
    #: "no findings" over source it could not read has reported a colour, not a
    #: result.
    SOURCE_UNREADABLE = "kernel.source.unreadable"
    #: No source was scanned at all. Its own verdict, because a sweep over an
    #: empty set passes for the wrong reason.
    INVENTORY_EMPTY = "kernel.inventory.empty"

    #: The declaration was absent. NOT an empty list: "nothing is prohibited"
    #: and "nobody said" are different facts, and one value must not carry both.
    DECLARATION_MISSING = "kernel.declaration.missing"
    #: The declaration existed, held bytes, and could not be understood. This
    #: is the CORRUPT refusal: something was stated and stated wrongly.
    DECLARATION_UNREADABLE = "kernel.declaration.unreadable"
    #: The declaration file exists and holds no document at all -- zero bytes,
    #: or nothing but whitespace. Its own code, because an EMPTY FILE is not an
    #: EMPTY CLASSIFICATION and is not a MISSING file either: "missing" would
    #: send the reader to create a file that already exists, and "corrupt"
    #: would send them to fix bytes that are not there.
    DECLARATION_EMPTY = "kernel.declaration.empty"
    #: The declaration is a JSON object and a REQUIRED key is absent. Kept
    #: apart from corrupt on one principled line: an obligation was never
    #: stated, rather than stated wrongly. The repairs differ -- write the key,
    #: versus fix the value -- and a diagnostic that names the wrong one sends
    #: the reader to the wrong edit.
    DECLARATION_INCOMPLETE = "kernel.declaration.incomplete"
    #: The declaration says `not_applicable` and the repository imports the
    #: Kernel. An exemption states an ENFORCEABLE premise, and this is the
    #: enforcement: the value cannot be used to leave the surface unmeasured.
    DECLARATION_PREMISE_FALSE = "kernel.declaration.premise-false"

    PIN_DISAGREES = "kernel.pin.disagrees"
    #: The pin arm was not given enough independent observations to be CAPABLE
    #: of reporting a disagreement. An ERROR for an `applicable` declaration,
    #: because a check that structurally cannot fail must not be counted as one
    #: that passed -- which is exactly what it was doing: a notice, and a
    #: report that stayed citable.
    PIN_UNDETECTABLE = "kernel.pin.undetectable"
    SURFACE_UNKNOWN = "kernel.surface.unknown"
    SURFACE_PRIVATE = "kernel.surface.private"
    SURFACE_PROHIBITED = "kernel.surface.prohibited"
    FACADE_LOCAL = "kernel.facade.local"
    TRANSITIONAL_UNOWNED = "kernel.transitional.unowned"
    #: The declared baseline and the observed sites disagree. Two-directional:
    #: a use outside the baseline is growth in a surface being retired, and a
    #: baseline entry with no use is a list that has stopped describing
    #: anything. Lowering the baseline is a reviewed edit, never a silent one.
    TRANSITIONAL_BASELINE_DRIFT = "kernel.transitional.baseline-drift"
    #: The stated expiry has passed. Until this code existed the expiry was
    #: syntax-checked and compared to nothing, which is a date field that
    #: cannot expire -- the "declared and never read" defect inside the very
    #: obligation that exists to make a retirement noticeable.
    TRANSITIONAL_EXPIRED = "kernel.transitional.expired"

    #: An `applicable` declaration carries three fields this runner does not
    #: read: `product_revision`, `kernel_catalogue` and `required_surfaces`.
    #: Published as a NOTICE on every applicable run rather than left silent,
    #: because declared-and-never-read inside the package built to catch
    #: declared-and-never-read is the defect wearing the guard's uniform. The
    #: repair is a versioned successor contract, not an edit to
    #: `KernelAdoptionDeclaration.v1`; it is open decision 52.
    DECLARATION_FIELDS_UNEVALUATED = "kernel.declaration.fields-unevaluated"

    #: A Kernel import was measured and no surface catalogue was supplied, so
    #: the unknown-surface arm could not run. A refusal rather than silence: a
    #: caller that supplies no catalogue must not thereby get a clean report
    #: over every import it made.
    CATALOGUE_ABSENT = "kernel.catalogue.absent"

    # --- KernelAdoptionDeclaration.v2 --------------------------------------
    # Every code below exists because a v2 field is READ. They are the repair
    # for `DECLARATION_FIELDS_UNEVALUATED`, which stays: a v1 `applicable`
    # declaration is still three unread fields and still non-citable.

    #: The declared `source_surface` digest and the digest derived from the
    #: measured source disagree. The declaration describes a Kernel surface the
    #: product no longer has -- or has not yet -- so every classification in it
    #: is being applied to source it was not written against.
    SOURCE_SURFACE_DRIFT = "kernel.source.surface-drift"
    #: An `applicable` declaration was measured over source containing NO
    #: Kernel import at all. Its own code, and the vacuity canary for the
    #: coordinate above: the digest of an empty surface set is a CONSTANT, so
    #: every Kernel-free product would share it and a declaration could match
    #: it by describing nothing. A product that declares Kernel adoption and
    #: imports no Kernel has stated something its own source contradicts.
    SURFACE_NONE_OBSERVED = "kernel.surface.none-observed"
    #: The declared `source_predecessor` is not an ancestor of the revision
    #: that was measured. Either the commit is not in this repository's history
    #: at all, or it is not behind what was measured.
    PREDECESSOR_NOT_ANCESTOR = "kernel.source.predecessor-not-ancestor"
    #: Ancestry could not be decided -- a shallow clone is the usual reason. A
    #: refusal, not silence: `fetch-depth: 0` is the repair, and a coordinate
    #: that cannot be checked is unmonitored rather than satisfied.
    PREDECESSOR_UNVERIFIABLE = "kernel.source.predecessor-unverifiable"

    #: The declared `kernel_catalogue` and the catalogue the observer supplied
    #: are not the same Kernel. Until this code existed a product could declare
    #: one Kernel and be measured against a self-authored catalogue for
    #: another, and every surface verdict would be taken against module lists
    #: nobody bound to the declared version.
    CATALOGUE_DISAGREES = "kernel.catalogue.disagrees"
    #: A v2 `applicable` declaration was run with no catalogue, or with one
    #: carrying no artifact digest, so the binding above could not be made.
    CATALOGUE_UNBOUND = "kernel.catalogue.unbound"
    #: The supplied catalogue publishes no modules. A sweep against an empty
    #: catalogue would report every import unknown OR, if the arm were written
    #: the other way, nothing at all; either way the catalogue is not one.
    CATALOGUE_EMPTY = "kernel.catalogue.empty"

    #: A root-façade import was measured and the supplied catalogue carries no
    #: root exports, so which names the façade publishes is unobserved. Its own
    #: code because its repair is its own: the OBSERVER must read the installed
    #: artifact's `dotmac_kernel.__all__`. Distinct from `catalogue.absent`,
    #: whose repair is to supply a catalogue at all, and it is a refusal rather
    #: than silence for the same reason: an unobserved publication authority
    #: must not buy a clean root arm over every root import made.
    ROOT_EXPORTS_UNOBSERVED = "kernel.root.exports-unobserved"
    #: A `from dotmac_kernel import X` named an `X` the installed artifact's
    #: `__all__` does not carry. This is what keeps normalising the root from
    #: becoming a blanket pass: the root is a PUBLISHED surface, and what it
    #: publishes is the enumerated list, not everything an importer can reach
    #: through the package object.
    ROOT_SYMBOL_UNEXPORTED = "kernel.root.unexported"

    #: A `required_surfaces` entry names a module the declared Kernel does not
    #: publish. A dependency on a name that is not there.
    REQUIRED_UNPUBLISHED = "kernel.required.unpublished"
    #: A `required_surfaces` entry names a module nothing in the measured
    #: source imports. A declared dependency with no use is the same defect
    #: this package exists for, one level in: a field somebody wrote and
    #: nothing reads.
    REQUIRED_UNUSED = "kernel.required.unused"
    #: A Kernel module IS imported and the declaration classifies it as
    #: nothing -- not required, not transitional, not prohibited. The other
    #: direction of the arm above, and the one that makes `required_surfaces`
    #: an inventory rather than a sample.
    SURFACE_UNCLASSIFIED = "kernel.surface.unclassified"
    #: A declared `floor` is HIGHER than the Kernel version the declaration
    #: itself binds. The product states it needs a Kernel it is not composing.
    REQUIRED_FLOOR_UNSATISFIED = "kernel.required.floor-unsatisfied"
    #: A `floor` or a Kernel version could not be ordered. Refused rather than
    #: guessed: an invented order reports a verdict over a question never asked.
    REQUIRED_FLOOR_UNORDERABLE = "kernel.required.floor-unorderable"
    #: `proven_by` names a path the run did not read, so the proof cannot be
    #: examined. A floor whose proof is unreadable is a number somebody typed.
    REQUIRED_PROOF_UNREAD = "kernel.required.proof-unread"
    #: `proven_by` names a file the run DID read, and that file never mentions
    #: the module it is offered as proof of. The weakest of the proof arms and
    #: stated as such -- it establishes that the proof is about the right
    #: subject, not that it proves anything.
    REQUIRED_PROOF_SILENT = "kernel.required.proof-silent"

    #: `declared_at` is after the date the run is asked about. A declaration
    #: cannot have been written after the run that reads it.
    DECLARED_AT_AHEAD = "kernel.declaration.dated-ahead"
    #: A transitional expiry had ALREADY passed on the day the declaration was
    #: written. Decidable without inventing a staleness policy, and it is the
    #: shape a copied declaration takes: the dates came with the file.
    TRANSITIONAL_EXPIRY_PREDATES_DECLARATION = (
        "kernel.transitional.expiry-predates-declaration"
    )


@dataclass(frozen=True)
class Finding:
    """One observation about product source, addressed to a file and a line.

    `path` and `line` are not optional decoration. A finding that says a rule
    was broken without saying where is a failure notice rather than a finding,
    and the reader ends up re-running the search by hand.
    """

    code: FindingCode
    severity: Severity
    message: str
    path: PurePosixPath | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.path is not None:
            result["path"] = self.path.as_posix()
        if self.line is not None:
            result["line"] = self.line
        return result


def normalise_observed_path(path: PurePosixPath) -> str:
    """One spelling of a caller-supplied path, for deciding INDEPENDENCE.

    Decision 52 (E), deferred on 2026-09-06 and repaired here because
    applicable activation is what makes the pin arm real enforcement.

    `PurePosixPath` does not resolve `..`, so `pyproject.toml` and
    `x/../pyproject.toml` compared unequal and counted as two INDEPENDENT
    observations of the pin. The arm requires two before it can report a
    disagreement, so one line of one file, written twice in two spellings,
    satisfied it. That catches accidental duplication and not a product that
    wants to pass -- and the data is caller-supplied, which is precisely the
    case where the second matters.

    Normalization is LEXICAL and deliberately not `Path.resolve()`: resolving
    would touch the filesystem, and the engine reads only its inputs. `.`
    segments are dropped and `..` pops the previous segment.

    It is also CASE-FOLDED, and that direction is chosen fail-closed. On a
    case-insensitive filesystem `PyProject.toml` and `pyproject.toml` are one
    file; on a case-sensitive one they are two. Collapsing them counts FEWER
    independent observations, so the arm refuses where it might have passed.
    The opposite choice would let a case change manufacture independence.

    What it does not catch, stated rather than left to be discovered: a symlink
    or a bind mount making two genuinely different paths the same file. The
    engine sees strings, and no lexical rule can see through a link.
    """
    parts: list[str] = []
    for part in path.as_posix().split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts).casefold()


@dataclass(frozen=True)
class PinSite:
    """One place a product states the Kernel version it adopts.

    A product may state the pin in several files, or several times in one file
    — Sub states it in four places in `pyproject.toml` alone. Each is a SITE,
    carried separately, so a disagreement can name the two sites that disagree
    instead of reporting that "the pin is wrong".
    """

    path: PurePosixPath
    line: int
    version: str
    #: What this site is: a dependency declaration, a lock resolution, a test
    #: constant, a bill-of-materials floor. Carried so the message can say
    #: which two KINDS disagree, which is usually the actual defect.
    kind: str

    @property
    def independence_key(self) -> tuple[str, int]:
        """What makes this observation DISTINCT from another one.

        The normalised path and the line. Never the raw path: see
        `normalise_observed_path`.
        """
        return normalise_observed_path(self.path), self.line


@dataclass(frozen=True)
class PredecessorObservation:
    """Whether the declared `source_predecessor` really precedes what was measured.

    Observed by the runner, which has the product checkout and Git; carried as
    DATA so the engine stays a pure function of its inputs and the verdict can
    be tested without a repository.

    `is_strict_ancestor` is a THREE-valued field on purpose. `True` and `False`
    are answers; `None` means the question could not be decided -- a shallow
    clone is the usual reason, and `fetch-depth: 0` the usual repair. There is
    no fourth state and no default, because a coordinate that could not be
    checked must be reported as unmonitored rather than read as satisfied.
    """

    declared: str
    measured: str
    is_strict_ancestor: bool | None
    detail: str


@dataclass(frozen=True)
class KernelSurfaceCatalogue:
    """The Kernel's own published module lists, at one exact Kernel revision.

    Supplied by the caller from the Kernel distribution's `SUPPORTED_MODULES`
    and `INTERNAL_MODULES`. Never hand-typed here: a hardcoded subset would
    make an unknown-surface finding an artefact of this file's staleness rather
    than a fact about the product.

    `revision` is the peeled 40-character commit the lists were read at, so a
    finding can be re-derived by someone who was not present.
    """

    revision: str
    version: str
    supported: frozenset[str]
    internal: frozenset[str]
    #: The digest of the Kernel DISTRIBUTION the observer found installed or
    #: locked -- for a Poetry product, the `sha256:` in `poetry.lock`. A
    #: repository-local fact the observer read, NOT a registry attestation:
    #: verifying it against a registry needs open decision 17's oracle.
    #:
    #: `None` is an explicit absence and never means "skip". A v2 `applicable`
    #: declaration binds this field, so an observer that supplies none is
    #: reported `kernel.catalogue.unbound` rather than passing the binding.
    #: Defaulted only so that every existing caller keeps compiling; a caller
    #: that omits it has stated an absence, not accepted a default.
    artifact_digest: str | None = None
    #: The installed artifact's `dotmac_kernel.__all__` -- the ROOT FAÇADE's
    #: own publication authority, and a list `SUPPORTED_MODULES` deliberately
    #: does not contain, because that set enumerates SUBMODULES.
    #:
    #: Read by the observer off the artifact the product resolved, exactly as
    #: `supported` and `internal` are. Never hand-typed here and never derived
    #: from the module lists: the root publishes NAMES and the lists publish
    #: MODULES, and conflating them would admit every root import rather than
    #: the named public exports.
    #:
    #: Empty is a STATED ABSENCE and never means "admit anything". A run that
    #: measures a root import against an empty set reports
    #: `kernel.root.exports-unobserved` and refuses, so an observer that never
    #: learned to read `__all__` cannot buy silence for the façade.
    root_exports: frozenset[str] = frozenset()

    @property
    def known(self) -> frozenset[str]:
        return self.supported | self.internal

    def publishes(self, module: str) -> bool:
        """Is `module` a surface this Kernel publishes, root façade included?

        `known` answers for submodules and CANNOT answer for the root: the bare
        `dotmac_kernel` is in neither `SUPPORTED_MODULES` nor
        `INTERNAL_MODULES` -- verified at `dotmac-kernel-v0.1.0a102` (peeled
        `7a3c128b06eaba09784a9d8409d036169b3caa68`), where the two lists carry
        89 and 4 names and neither is the bare root. So a product importing the
        root had no reachable verdict: declaring it required reported
        `kernel.required.unpublished`, and omitting it reported
        `kernel.surface.unclassified`.

        The root is normalised as a SEPARATELY published surface rather than
        added to a list that describes submodules. Its publication authority is
        `__all__`, so it is published exactly when that authority was observed
        -- and when it was not, the root arm refuses under its own code rather
        than this returning `True` and letting the façade through unmeasured.
        """
        if module == KERNEL_ROOT:
            return bool(self.root_exports)
        return module in self.known


@dataclass(frozen=True)
class DeclarationPresent:
    """The repository declared its Kernel-surface classifications.

    EITHER contract. `KernelAdoptionDeclaration.v1` is frozen and still
    parsed; `KernelAdoptionDeclarationV2` is the successor. The arms that were
    already honest read the attributes both carry; the arms that are new to v2
    ask for a v2 by type and say so when they get a v1.
    """

    declaration: AnyKernelAdoptionDeclaration


@dataclass(frozen=True)
class DeclarationMissing:
    """No declaration was found. A refusal, never an empty classification.

    The two sentences a reader must not be allowed to confuse are "this
    repository prohibits nothing" and "nobody has said what this repository
    prohibits". An empty list says the first while meaning the second, which is
    how a check comes to answer a question it cannot answer.
    """

    detail: str


@dataclass(frozen=True)
class DeclarationUnreadable:
    """A declaration existed and could not be understood. Also a refusal.

    Separate from `DeclarationMissing` because the repairs differ — one writes
    a section, the other fixes one — and a guard that reports the wrong one
    sends the reader to the wrong file.
    """

    detail: str


@dataclass(frozen=True)
class DeclarationEmpty:
    """The file exists and holds no document. A refusal, and its own one.

    An EMPTY FILE is not an EMPTY CLASSIFICATION, and it is the second half of
    that sentence this type protects: `DeclarationPresent` carrying empty
    tuples is a statement somebody made, and this is the absence of any
    statement at all in a file somebody created.

    It is also not `DeclarationMissing`: the file is there, so "write the
    declaration at this path" sends the reader to create a path that already
    exists and leaves them wondering what they did wrong. And it is not
    `DeclarationUnreadable`: there are no bytes to fix.
    """

    detail: str


@dataclass(frozen=True)
class DeclarationIncomplete:
    """A JSON object omitting a required key. A refusal, distinct from corrupt.

    The line between this and `DeclarationUnreadable` is the only one that has
    to be held in the head of whoever reads a report: an obligation NEVER
    STATED is incomplete, and an obligation STATED WRONGLY is corrupt. A
    document can be both, and the diagnostic names the refusal the parser
    reached FIRST -- absence is checked per object before any value in it is
    validated, so a document missing a key reports incomplete even when a key
    it did state is also wrong. That ordering is a property of the parser and
    is asserted, not left to be inferred.
    """

    detail: str


#: Five outcomes, four of them refusals, and no sixth. There is deliberately no
#: member meaning "an empty classification": a declaration that says nothing is
#: prohibited is `DeclarationPresent` carrying an empty tuple, which is a
#: statement somebody made, and every other shape in which a classification
#: could turn out to be absent is one of the four refusals below.
DeclarationOutcome = (
    DeclarationPresent
    | DeclarationMissing
    | DeclarationEmpty
    | DeclarationIncomplete
    | DeclarationUnreadable
)


@dataclass(frozen=True)
class KernelAdoptionInputs:
    """Everything the engine is told. It reads nothing else.

    `source_paths` is the ALREADY-DERIVED file inventory, passed in rather than
    globbed, for the reason `standards_control.ConnectorScope` documents: a
    product that can name what is measured is not measured, so the derivation
    belongs to the caller that also publishes it.

    `source_paths` may name files whose suffix is not `.py`. That is
    deliberate: `dotmac_platform_control_plane` keeps
    `src/vendor_cp/rotation_runtime_oracle.pyprogram`, which imports
    `dotmac_kernel.db` at line 17 and is not a `.py` file, so a `.py` sweep
    walks straight past it. A scan that only believes in one suffix has a blind
    spot the product already knows how to stand in.
    """

    #: Relative path -> source text. Text, not a root: the caller decides what
    #: revision it read, and the engine cannot silently pick up a working-tree
    #: edit.
    sources: dict[PurePosixPath, str]
    #: The Kernel's published module lists, or an EXPLICIT `None` when the
    #: caller has none. `None` is not a default and never means "skip": every
    #: measured Kernel import in a run with no catalogue is reported
    #: `kernel.catalogue.absent`. It exists so a repository that consumes no
    #: Kernel can be measured without inventing a catalogue it has no evidence
    #: for -- a fabricated version and revision would be worse than a stated
    #: absence, because the report would then carry a coordinate nobody read.
    catalogue: KernelSurfaceCatalogue | None
    #: The product's own classifications, or the refusal that stands in for
    #: them. Not defaulted: a caller that forgot to supply one would otherwise
    #: get the empty classification this type exists to make unrepresentable.
    declaration: DeclarationOutcome
    #: The date the run is asked about. Required, and deliberately not a clock
    #: read: nothing in this package calls `date.today()`, because a check that
    #: reads a clock inside itself cannot be re-run to the same answer by
    #: someone who was not present. The caller supplies it and the runner
    #: records it in the report, which is what makes an expiry verdict
    #: reproducible rather than merely correct on the day.
    as_of: date
    pin_sites: tuple[PinSite, ...] = ()
    #: The runner's Git observation of `source_predecessor`, or `None` when
    #: there was nothing to observe -- a v1 declaration, or a refusal, states
    #: no predecessor. `None` is NOT "it was fine": a v2 declaration evaluated
    #: with no observation is reported `kernel.source.predecessor-unverifiable`,
    #: because an engine invoked directly by a caller who skipped the probe
    #: must not thereby report the coordinate clean.
    predecessor: PredecessorObservation | None = None


@dataclass(frozen=True)
class AdoptionReport:
    """What one run observed. Report-only: nothing here is a verdict.

    `conforms` counts errors alone, matching `ConformanceReport`. It is a
    property of the findings, not a compliance statement — no gate consumes it
    today, by decision rather than by omission (ADR 0042 § 4).
    """

    findings: tuple[Finding, ...] = field(default_factory=tuple)

    @property
    def conforms(self) -> bool:
        return not any(item.severity is Severity.ERROR for item in self.findings)

    def codes(self) -> tuple[FindingCode, ...]:
        return tuple(item.code for item in self.findings)

    def to_dict(self) -> dict[str, object]:
        return {
            "conforms": self.conforms,
            "findings": [item.to_dict() for item in self.findings],
        }
