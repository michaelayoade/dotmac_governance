"""`KernelAdoptionDeclaration.v1` — one declaration format for every product.

Governance owns this contract: the schema, the refusal rules and the parser.
Each product owns only its instance, at `.dotmac/kernel-adoption.json`. The
conformance profile carries a POINTER to that file and none of its contents, so
a classification cannot arrive as a plausible line in a diff to the profile and
the two documents version independently.

Michael's acceptance test for this design, 2026-09-05: *"This is one
build-once validator and one declaration format across every product — not a
per-product adapter."* Nothing below is parameterised by product. There is no
product name, no per-product branch and no hook: a product that needed the
format to differ would be telling us the format is wrong.

This is NOT `ApplicationFoundationProfile.v1` and does not overlap it.
Foundation owns that contract, its digest and its verifier; nothing here
parses, canonicalizes or digests a Foundation profile, and no field below
restates a Foundation concern binding.

## The three states

- **applicable** — the surfaces this product requires, prohibits and is
  retiring.
- **not_applicable** — an explicit typed absence with a reason. It is CHECKED
  rather than accepted: the evaluator compares it against the repository's own
  imports.
- **missing or unreadable** — a REFUSAL, in `declaration`. Never an empty
  classification. "This product prohibits nothing" and "nobody has said what
  this product prohibits" are different facts, and one value must not carry
  both.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import PurePosixPath
from typing import Final

__all__ = [
    "KERNEL_ADOPTION_CONTRACT",
    "DeclarationError",
    "IncompleteDeclarationError",
    "KernelAdoptionApplicability",
    "KernelAdoptionDeclaration",
    "KernelCatalogueEvidence",
    "ProhibitedSurface",
    "RequiredSurface",
    "SurfaceSite",
    "TransitionalSurface",
    "parse_declaration",
]

#: The contract string a declaration must carry. A v2 would be a new string and
#: a new parser; a v1 is never redefined.
KERNEL_ADOPTION_CONTRACT: Final = "KernelAdoptionDeclaration.v1"

_PEELED_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
#: ISO date. An expiry that cannot be ordered cannot expire.
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_KERNEL_MODULE = re.compile(r"^dotmac_kernel(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")


class DeclarationError(ValueError):
    """The declaration could not be understood. Never softened to a default."""


class IncompleteDeclarationError(DeclarationError):
    """A required key was never stated. A SUBCLASS, so no caller loses a refusal.

    This does not redefine `KernelAdoptionDeclaration.v1`. The same documents
    are admitted and the same documents are refused; what changes is that one
    refusal can now be told from the other by its type instead of by reading
    the sentence. Every existing `except DeclarationError` still catches it,
    which is why the split could be made without a v2.

    The line: an obligation NEVER STATED is incomplete; an obligation STATED
    WRONGLY -- a bad module name, an impossible date, an unknown key, a
    non-object -- is plain `DeclarationError`, which the reader sees as
    corrupt.
    """


class KernelAdoptionApplicability(str, Enum):
    """Two values a product may declare, and no third.

    The state a reader keeps inventing — "not stated" — is deliberately
    unrepresentable here. It is not a value; it is the absence of the document,
    and `declaration.read_declaration` reports it as a refusal.
    """

    APPLICABLE = "applicable"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class SurfaceSite:
    """One exact place a transitional surface is used today.

    Path AND symbol, because a path alone cannot survive a file growing a
    second use, and a count alone cannot say which use was removed.
    """

    path: PurePosixPath
    symbol: str


@dataclass(frozen=True)
class RequiredSurface:
    """A Kernel surface the product depends on, and the floor it has PROVEN.

    `floor` is a version the product has demonstrated it needs, and `proven_by`
    names where that demonstration lives. A floor with no proof is a number
    somebody typed.
    """

    module: str
    floor: str
    proven_by: PurePosixPath


@dataclass(frozen=True)
class ProhibitedSurface:
    """A Kernel surface the product forbids itself, and the rule that says so.

    `citation` is required. A prohibition with no governing record is a
    preference, and the next reader cannot tell whether removing it needs a
    decision or a commit.
    """

    module: str
    citation: str


@dataclass(frozen=True)
class TransitionalSurface:
    """A surface being retired, with everything a retirement needs to happen.

    Five obligations, all required. `owner` and `expiry` make someone
    answerable by a date. `retirement_issue` is where the work is tracked, so
    the undertaking exists outside this file. `replacement` names what callers
    move to, because a retirement with no destination does not happen.
    `baseline` is the exact set of sites today, which is what makes this a
    RATCHET rather than a note: the evaluator refuses a use that is not in the
    baseline, so a surface being retired cannot quietly grow.
    """

    module: str
    owner: str
    expiry: str
    retirement_issue: str
    replacement: str
    baseline: tuple[SurfaceSite, ...]


@dataclass(frozen=True)
class KernelCatalogueEvidence:
    """External evidence of WHICH Kernel the declaration was written against.

    A version string alone is a repository-local claim. ADR 0013 § 1 puts a
    release outside repository-local facts, so the peeled commit and the
    artifact digest are carried too: they identify particular bytes, and a
    reader who was not present can re-derive the surface catalogue from them.
    """

    version: str
    revision: str
    artifact_digest: str


@dataclass(frozen=True)
class KernelAdoptionDeclaration:
    """One product's Kernel adoption, as declared by that product."""

    contract: str
    product_revision: str
    applicability: KernelAdoptionApplicability
    not_applicable_reason: str | None
    catalogue: KernelCatalogueEvidence | None
    required_surfaces: tuple[RequiredSurface, ...]
    prohibited_surfaces: tuple[ProhibitedSurface, ...]
    transitional_surfaces: tuple[TransitionalSurface, ...]

    @property
    def prohibited_modules(self) -> frozenset[str]:
        return frozenset(item.module for item in self.prohibited_surfaces)


def _object(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DeclarationError(f"{where} must be an object")
    return value


def _keys(
    data: dict[str, object],
    required: frozenset[str],
    where: str,
    optional: frozenset[str] = frozenset(),
) -> None:
    missing = sorted(required - data.keys())
    unknown = sorted(data.keys() - required - optional)
    # Absence is checked BEFORE any stated value is validated, here and by
    # every caller of `_keys`, so a document that is both incomplete and
    # corrupt reports incomplete. That ordering is the tie-break the two codes
    # need in order to be distinguishable at all, and it is asserted by
    # `test_a_document_that_is_both_reports_the_refusal_the_parser_reached_first`.
    if missing:
        raise IncompleteDeclarationError(f"{where} missing keys: {', '.join(missing)}")
    if unknown:
        raise DeclarationError(f"{where} has unknown keys: {', '.join(unknown)}")


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeclarationError(f"{where} must be a non-empty string")
    return value.strip()


def _sequence(value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise DeclarationError(f"{where} must be an array")
    return value


def _relative(value: object, where: str) -> PurePosixPath:
    raw = _text(value, where)
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw == ".":
        raise DeclarationError(f"{where} must be a repository-relative path")
    return path


def _module(value: object, where: str) -> str:
    name = _text(value, where)
    if not _KERNEL_MODULE.fullmatch(name):
        raise DeclarationError(
            f"{where} is {name!r}, which is not a dotmac_kernel module path. A "
            "declaration classifies Kernel surfaces; a name outside that "
            "namespace would be classified and never measured"
        )
    return name


def _commit(value: object, where: str) -> str:
    raw = _text(value, where)
    if not _PEELED_COMMIT.fullmatch(raw):
        raise DeclarationError(
            f"{where} is {raw!r}, which is not a peeled 40-character commit. "
            "ADR 0013 § 3 refuses a branch name, 'latest', an unpeeled tag and "
            "an image tag: a claim measured against a reference that can move "
            "is not a claim about any particular bytes"
        )
    return raw


def _required_surface(value: object, index: int) -> RequiredSurface:
    where = f"required_surfaces[{index}]"
    data = _object(value, where)
    _keys(data, frozenset({"module", "floor", "proven_by"}), where)
    return RequiredSurface(
        module=_module(data["module"], f"{where}.module"),
        floor=_text(data["floor"], f"{where}.floor"),
        proven_by=_relative(data["proven_by"], f"{where}.proven_by"),
    )


def _prohibited_surface(value: object, index: int) -> ProhibitedSurface:
    where = f"prohibited_surfaces[{index}]"
    data = _object(value, where)
    _keys(data, frozenset({"module", "citation"}), where)
    return ProhibitedSurface(
        module=_module(data["module"], f"{where}.module"),
        citation=_text(data["citation"], f"{where}.citation"),
    )


def _transitional_surface(value: object, index: int) -> TransitionalSurface:
    where = f"transitional_surfaces[{index}]"
    data = _object(value, where)
    _keys(
        data,
        frozenset(
            {
                "module",
                "owner",
                "expiry",
                "retirement_issue",
                "replacement",
                "baseline",
            }
        ),
        where,
    )
    expiry = _text(data["expiry"], f"{where}.expiry")
    if not _DATE.fullmatch(expiry):
        raise DeclarationError(
            f"{where}.expiry is {expiry!r}; an expiry must be an ISO "
            "YYYY-MM-DD date. A date that cannot be ordered cannot expire, and "
            "'soon' has never retired anything"
        )
    # The shape check above is not the whole of "orderable". `2026-13-45`
    # matches it and is not a day, so it could be written, parsed, stored and
    # then compared to nothing -- an expiry that can never pass. This is a
    # tightening within the SAME stated format rather than a redefinition: no
    # ISO YYYY-MM-DD date is newly refused, only strings that were never one.
    try:
        date.fromisoformat(expiry)
    except ValueError as error:
        raise DeclarationError(
            f"{where}.expiry is {expiry!r}, which has the shape of an ISO date "
            f"and is not one: {error}. It would be stored, ordered against "
            "nothing and never expire"
        ) from error
    sites: list[SurfaceSite] = []
    for position, item in enumerate(_sequence(data["baseline"], f"{where}.baseline")):
        site_where = f"{where}.baseline[{position}]"
        entry = _object(item, site_where)
        _keys(entry, frozenset({"path", "symbol"}), site_where)
        sites.append(
            SurfaceSite(
                path=_relative(entry["path"], f"{site_where}.path"),
                symbol=_text(entry["symbol"], f"{site_where}.symbol"),
            )
        )
    if len({(site.path, site.symbol) for site in sites}) != len(sites):
        raise DeclarationError(f"{where}.baseline names one site twice")
    return TransitionalSurface(
        module=_module(data["module"], f"{where}.module"),
        owner=_text(data["owner"], f"{where}.owner"),
        expiry=expiry,
        retirement_issue=_text(data["retirement_issue"], f"{where}.retirement_issue"),
        replacement=_text(data["replacement"], f"{where}.replacement"),
        baseline=tuple(sites),
    )


def _catalogue(value: object) -> KernelCatalogueEvidence:
    where = "kernel_catalogue"
    data = _object(value, where)
    _keys(data, frozenset({"version", "revision", "artifact_digest"}), where)
    digest = _text(data["artifact_digest"], f"{where}.artifact_digest")
    if not _DIGEST.fullmatch(digest):
        raise DeclarationError(
            f"{where}.artifact_digest must be 'sha256:' followed by 64 hex "
            "characters; an installation adopts BY DIGEST"
        )
    return KernelCatalogueEvidence(
        version=_text(data["version"], f"{where}.version"),
        revision=_commit(data["revision"], f"{where}.revision"),
        artifact_digest=digest,
    )


def parse_declaration(value: object) -> KernelAdoptionDeclaration:
    """Parse a `KernelAdoptionDeclaration.v1` document, or refuse it.

    Closed per applicability, so a `not_applicable` declaration cannot carry a
    surface list that nothing will read — a list nobody reads is worse than no
    list, because it looks measured.
    """
    data = _object(value, "declaration")
    # Absence before wrongness, so a document that states no contract at all is
    # INCOMPLETE rather than corrupt. `_text(None, ...)` would say the value
    # "must be a non-empty string", which describes a key that is there and
    # blank, and sends the author to edit a line that does not exist.
    for key in ("contract", "applicability"):
        if key not in data:
            raise IncompleteDeclarationError(f"declaration missing keys: {key}")
    contract = _text(data.get("contract"), "declaration.contract")
    if contract != KERNEL_ADOPTION_CONTRACT:
        raise DeclarationError(
            f"declaration.contract is {contract!r}; this parser reads "
            f"{KERNEL_ADOPTION_CONTRACT!r} only. A v1 is never redefined, so a "
            "different contract is a different document and needs its own "
            "parser rather than a lenient one here"
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
                    "product_revision",
                    "applicability",
                    "not_applicable_reason",
                }
            ),
            "declaration",
        )
        return KernelAdoptionDeclaration(
            contract=contract,
            product_revision=_commit(
                data["product_revision"], "declaration.product_revision"
            ),
            applicability=applicability,
            not_applicable_reason=_text(
                data["not_applicable_reason"], "declaration.not_applicable_reason"
            ),
            catalogue=None,
            required_surfaces=(),
            prohibited_surfaces=(),
            transitional_surfaces=(),
        )

    _keys(
        data,
        frozenset(
            {
                "contract",
                "product_revision",
                "applicability",
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

    return KernelAdoptionDeclaration(
        contract=contract,
        product_revision=_commit(
            data["product_revision"], "declaration.product_revision"
        ),
        applicability=applicability,
        not_applicable_reason=None,
        catalogue=_catalogue(data["kernel_catalogue"]),
        required_surfaces=required,
        prohibited_surfaces=prohibited,
        transitional_surfaces=transitional,
    )
