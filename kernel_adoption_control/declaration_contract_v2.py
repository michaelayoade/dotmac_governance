"""`KernelAdoptionDeclaration.v2` — the successor contract for applicable products.

**v1 is frozen and this is not an edit to it.** Both parsers live side by side,
both are reachable, and a v1 document is admitted by `parse_any_declaration`
exactly as before, with exactly the same refusals. `parse_declaration` in
`declaration_contract` still refuses a v2 document, which is correct: a v1 is
never redefined, so a parser for one is not a lenient parser for both.

## What v2 is for

v1 requires three fields that nothing reads —
`product_revision`, `kernel_catalogue` and `required_surfaces` — which is the
"declared and never read" defect standing inside the package built to catch it.
An `applicable` v1 report is therefore explicitly non-citable (ADR 0042 § A8).
v2 exists so that an `applicable` report CAN be cited, and it earns that by
replacing each unread field with one a run can check.

| v1 | v2 | Why |
| --- | --- | --- |
| `product_revision` | `source_predecessor` + `source_surface` | A committed file cannot contain its own commit, so the self-reference is replaced by an ancestor coordinate the runner verifies against the product's own history, and a content digest the engine re-derives from the measured source. |
| `kernel_catalogue` (version, revision, artifact_digest) | the same, plus `catalogue_digest` | The lists behind the version are bound, so a product cannot declare one Kernel and be measured against a self-authored catalogue for another. |
| `required_surfaces` (parsed, unread) | the same shape, with executable semantics | The module must be published by the declared Kernel, must actually be imported, the floor must be satisfied by the declared Kernel version, and `proven_by` must name a file the run can read. |
| — | `declared_at` | v1 carries no date, so a five-year-old declaration whose expiries are all in the future is indistinguishable from one written yesterday (decision 52 (D)). |

## What v2 deliberately does NOT add

**No maximum declaration age.** `declared_at` makes the age of a declaration a
fact a report can carry and a reader can see. Whether a declaration older than
some number of days is stale enough to refuse is a POLICY, and this file is not
where a policy number gets invented. What is checked is what is decidable
without one: a declaration dated after the run is refused, and a transitional
expiry that had already passed when the declaration was written is refused.

**No signature.** Nothing here attests who wrote the document or that the bytes
were not altered. That is open decision 17's oracle, and a scheme invented here
would be a second one.

## Shape

Closed per applicability, as v1 is. A `not_applicable` v2 declaration carries
`declared_at`, `source_predecessor` and `not_applicable_reason` and nothing
else — in particular NOT `source_surface`, because the digest over an empty
surface set is a constant every Kernel-free product would share, and a field
whose only possible value is a constant is a field that passes for the wrong
reason. What a `not_applicable` declaration claims is a premise, and that
premise is evaluated directly against the repository's imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

# v1's field validators, reused rather than reimplemented. Two parsers with two
# copies of "what a peeled commit is" would drift, and the first sign of the
# drift would be one contract admitting a coordinate the other refused. The
# names are private to `declaration_contract` because nothing OUTSIDE this
# package may depend on them; the successor contract is inside it.
from .declaration_contract import (
    _DATE,
    _DIGEST,
    KERNEL_ADOPTION_CONTRACT,
    DeclarationError,
    IncompleteDeclarationError,
    KernelAdoptionApplicability,
    KernelAdoptionDeclaration,
    ProhibitedSurface,
    RequiredSurface,
    TransitionalSurface,
    _commit,
    _keys,
    _object,
    _prohibited_surface,
    _required_surface,
    _text,
    _transitional_surface,
    parse_declaration,
)
from .declaration_contract import (
    _sequence as _sequence,
)
from .surface import SOURCE_SURFACE_ALGORITHM

__all__ = [
    "KERNEL_ADOPTION_CONTRACT_V2",
    "AnyKernelAdoptionDeclaration",
    "KernelAdoptionDeclarationV2",
    "KernelCatalogueBinding",
    "SourceSurfaceCoordinate",
    "parse_any_declaration",
    "parse_declaration_v2",
]

#: A NEW contract string. A v2 document handed to v1's parser is refused by
#: name, and a v1 document handed to v2's parser likewise.
KERNEL_ADOPTION_CONTRACT_V2: Final = "KernelAdoptionDeclaration.v2"


@dataclass(frozen=True)
class SourceSurfaceCoordinate:
    """A digest over the product's Kernel-surface usage, and the rule that made it.

    `algorithm` is carried rather than assumed. A digest with no stated
    canonicalization is a hex string: the next reader cannot tell whether a
    mismatch means the source moved or the rendering rule did, and those have
    opposite repairs.
    """

    algorithm: str
    digest: str


@dataclass(frozen=True)
class KernelCatalogueBinding:
    """Which Kernel this declaration classifies surfaces against, bound four ways.

    `version` and `revision` say which Kernel. `artifact_digest` names the
    distribution bytes and is compared with what the observer read out of the
    product's own lock file — a repository-local fact, and NOT a registry
    attestation; verifying it against a registry needs open decision 17's
    oracle. `catalogue_digest` binds the module LISTS, which is the field that
    makes the other three mean something: without it a product may declare
    Kernel `0.1.0a98` and hand the run `0.1.0a50`'s module lists, and every
    unknown-surface verdict is taken against a catalogue nobody bound to the
    declared version.
    """

    version: str
    revision: str
    artifact_digest: str
    catalogue_digest: str


@dataclass(frozen=True)
class KernelAdoptionDeclarationV2:
    """One product's Kernel adoption, in the contract a run can check.

    Field names that also exist on `KernelAdoptionDeclaration` carry the same
    meaning, so the arms that were already honest read either version through
    the same attribute.
    """

    contract: str
    applicability: KernelAdoptionApplicability
    declared_at: date
    #: A commit that is an ANCESTOR of the measured revision, never the
    #: measured revision itself. See `runner._check_predecessor` for what the
    #: verification proves and what it does not.
    source_predecessor: str
    not_applicable_reason: str | None
    source_surface: SourceSurfaceCoordinate | None
    kernel_catalogue: KernelCatalogueBinding | None
    required_surfaces: tuple[RequiredSurface, ...]
    prohibited_surfaces: tuple[ProhibitedSurface, ...]
    transitional_surfaces: tuple[TransitionalSurface, ...]

    @property
    def prohibited_modules(self) -> frozenset[str]:
        return frozenset(item.module for item in self.prohibited_surfaces)


#: What a reader of `DeclarationPresent` may be handed. BOTH are real and both
#: stay parseable; the engine reads the shared attributes off either and asks
#: the v2-only questions only of a v2. A union rather than a base class,
#: because v1 is frozen: giving it a new base would be an edit to it.
AnyKernelAdoptionDeclaration = KernelAdoptionDeclaration | KernelAdoptionDeclarationV2


def _digest(value: object, where: str) -> str:
    raw = _text(value, where)
    if not _DIGEST.fullmatch(raw):
        raise DeclarationError(
            f"{where} must be 'sha256:' followed by 64 lower-case hex "
            "characters. A digest in any other spelling would be compared "
            "byte-for-byte against one in this spelling and never match, so a "
            "run would refuse for a reason that is not the reason it reports"
        )
    return raw


def _declared_at(value: object) -> date:
    where = "declaration.declared_at"
    raw = _text(value, where)
    if not _DATE.fullmatch(raw):
        raise DeclarationError(
            f"{where} is {raw!r}; it must be an ISO YYYY-MM-DD date. A "
            "declaration whose age cannot be ordered has no age"
        )
    try:
        return date.fromisoformat(raw)
    except ValueError as error:
        raise DeclarationError(
            f"{where} is {raw!r}, which has the shape of an ISO date and is "
            f"not one: {error}"
        ) from error


def _source_surface(value: object) -> SourceSurfaceCoordinate:
    where = "source_surface"
    data = _object(value, where)
    _keys(data, frozenset({"algorithm", "digest"}), where)
    algorithm = _text(data["algorithm"], f"{where}.algorithm")
    if algorithm != SOURCE_SURFACE_ALGORITHM:
        raise DeclarationError(
            f"{where}.algorithm is {algorithm!r}; this contract reads "
            f"{SOURCE_SURFACE_ALGORITHM!r} only. A digest taken under a "
            "canonicalization this run does not implement cannot be compared, "
            "and comparing it anyway would report 'the source moved' for a "
            "document whose rendering rule moved instead"
        )
    return SourceSurfaceCoordinate(
        algorithm=algorithm, digest=_digest(data["digest"], f"{where}.digest")
    )


def _kernel_catalogue(value: object) -> KernelCatalogueBinding:
    where = "kernel_catalogue"
    data = _object(value, where)
    _keys(
        data,
        frozenset({"version", "revision", "artifact_digest", "catalogue_digest"}),
        where,
    )
    return KernelCatalogueBinding(
        version=_text(data["version"], f"{where}.version"),
        revision=_commit(data["revision"], f"{where}.revision"),
        artifact_digest=_digest(data["artifact_digest"], f"{where}.artifact_digest"),
        catalogue_digest=_digest(data["catalogue_digest"], f"{where}.catalogue_digest"),
    )


def _one_class_per_module(
    required: tuple[RequiredSurface, ...],
    prohibited: tuple[ProhibitedSurface, ...],
    transitional: tuple[TransitionalSurface, ...],
) -> None:
    """v1's rule, unchanged: no module holds two of the three undertakings."""
    seen: dict[str, str] = {}
    for kind, modules in (
        ("required", [item.module for item in required]),
        ("prohibited", [item.module for item in prohibited]),
        ("transitional", [item.module for item in transitional]),
    ):
        for name in modules:
            previous = seen.get(name)
            if previous is not None:
                raise DeclarationError(
                    f"{name} is declared both {previous} and {kind}. A surface "
                    "the product depends on, one it forbids itself, and one it "
                    "is retiring on a stated date are three different "
                    "undertakings, and no module may hold two of them"
                )
            seen[name] = kind


def parse_declaration_v2(value: object) -> KernelAdoptionDeclarationV2:
    """Parse a `KernelAdoptionDeclaration.v2` document, or refuse it.

    Absence is checked before wrongness, per object, exactly as v1 does, so a
    document that is both incomplete and corrupt reports INCOMPLETE. That
    ordering is the tie-break the two refusal codes need in order to be
    distinguishable at all, and it is asserted for v2 separately: a rule held
    by one parser says nothing about another.
    """
    data = _object(value, "declaration")
    for key in ("contract", "applicability"):
        if key not in data:
            raise IncompleteDeclarationError(f"declaration missing keys: {key}")
    contract = _text(data.get("contract"), "declaration.contract")
    if contract != KERNEL_ADOPTION_CONTRACT_V2:
        raise DeclarationError(
            f"declaration.contract is {contract!r}; this parser reads "
            f"{KERNEL_ADOPTION_CONTRACT_V2!r} only"
        )
    raw = _text(data.get("applicability"), "declaration.applicability")
    try:
        applicability = KernelAdoptionApplicability(raw)
    except ValueError as error:
        raise DeclarationError(
            "declaration.applicability must be applicable or not_applicable"
        ) from error

    if applicability is KernelAdoptionApplicability.NOT_APPLICABLE:
        _keys(
            data,
            frozenset(
                {
                    "contract",
                    "applicability",
                    "declared_at",
                    "source_predecessor",
                    "not_applicable_reason",
                }
            ),
            "declaration",
        )
        return KernelAdoptionDeclarationV2(
            contract=contract,
            applicability=applicability,
            declared_at=_declared_at(data["declared_at"]),
            source_predecessor=_commit(
                data["source_predecessor"], "declaration.source_predecessor"
            ),
            not_applicable_reason=_text(
                data["not_applicable_reason"], "declaration.not_applicable_reason"
            ),
            source_surface=None,
            kernel_catalogue=None,
            required_surfaces=(),
            prohibited_surfaces=(),
            transitional_surfaces=(),
        )

    _keys(
        data,
        frozenset(
            {
                "contract",
                "applicability",
                "declared_at",
                "source_predecessor",
                "source_surface",
                "kernel_catalogue",
                "required_surfaces",
                "prohibited_surfaces",
                "transitional_surfaces",
            }
        ),
        "declaration",
    )
    required = tuple(
        _required_surface(item, index)
        for index, item in enumerate(
            _sequence(data["required_surfaces"], "required_surfaces")
        )
    )
    prohibited = tuple(
        _prohibited_surface(item, index)
        for index, item in enumerate(
            _sequence(data["prohibited_surfaces"], "prohibited_surfaces")
        )
    )
    transitional = tuple(
        _transitional_surface(item, index)
        for index, item in enumerate(
            _sequence(data["transitional_surfaces"], "transitional_surfaces")
        )
    )
    _one_class_per_module(required, prohibited, transitional)
    if len({item.module for item in required}) != len(required):
        raise DeclarationError(
            "required_surfaces names one module twice. Two floors for one "
            "module is two answers to one question, and which one binds would "
            "be decided by list order"
        )
    return KernelAdoptionDeclarationV2(
        contract=contract,
        applicability=applicability,
        declared_at=_declared_at(data["declared_at"]),
        source_predecessor=_commit(
            data["source_predecessor"], "declaration.source_predecessor"
        ),
        not_applicable_reason=None,
        source_surface=_source_surface(data["source_surface"]),
        kernel_catalogue=_kernel_catalogue(data["kernel_catalogue"]),
        required_surfaces=required,
        prohibited_surfaces=prohibited,
        transitional_surfaces=transitional,
    )


#: Every contract string this repository can read, and the parser for each.
#: A mapping rather than a chain of `if`s, so "which contracts are supported"
#: is one enumerable value a test can compare against the modules that exist.
_PARSERS: Final = {
    KERNEL_ADOPTION_CONTRACT: "v1",
    KERNEL_ADOPTION_CONTRACT_V2: "v2",
}


def parse_any_declaration(value: object) -> AnyKernelAdoptionDeclaration:
    """Dispatch on the stated `contract` and parse with the matching parser.

    Neither parser is made lenient. The document names its own contract and is
    routed to the one parser that reads it; a document naming neither is
    refused with both names, because "unknown contract" is a different repair
    from "wrong field".

    A `not_applicable` v1 declaration keeps working unchanged, which is the
    whole point of a successor: `dotmac_governance`'s own declaration is a v1
    and this change does not touch it or its citability.
    """
    data = _object(value, "declaration")
    if "contract" not in data:
        raise IncompleteDeclarationError("declaration missing keys: contract")
    contract = _text(data.get("contract"), "declaration.contract")
    if contract == KERNEL_ADOPTION_CONTRACT:
        return parse_declaration(value)
    if contract == KERNEL_ADOPTION_CONTRACT_V2:
        return parse_declaration_v2(value)
    raise DeclarationError(
        f"declaration.contract is {contract!r}; this repository reads "
        f"{', '.join(sorted(_PARSERS))} and nothing else. A document under an "
        "unknown contract is not read leniently by the nearest parser: the "
        "fields it does not share would be silently unmeasured, which is the "
        "shape this package exists to refuse"
    )
