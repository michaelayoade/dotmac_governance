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
    TransitionalSurface,
)

__all__ = [
    "AdoptionReport",
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
    "KernelAdoptionInputs",
    "KernelSurfaceCatalogue",
    "PinSite",
    "Severity",
    "TransitionalSurface",
]


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

    #: A Kernel import was measured and no surface catalogue was supplied, so
    #: the unknown-surface arm could not run. A refusal rather than silence: a
    #: caller that supplies no catalogue must not thereby get a clean report
    #: over every import it made.
    CATALOGUE_ABSENT = "kernel.catalogue.absent"


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

    @property
    def known(self) -> frozenset[str]:
        return self.supported | self.internal


@dataclass(frozen=True)
class DeclarationPresent:
    """The repository declared its Kernel-surface classifications."""

    declaration: KernelAdoptionDeclaration


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
