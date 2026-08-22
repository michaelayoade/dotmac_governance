"""Check a roster claim against the module dossier it cites.

`programme_control` validates one repository's records against each other. This
module is the half that cannot: a `no_product_writer` roster rationale asserts a
fact about a product's writers, and the only artifact that can refute it lives
in `dotmac_starter_mt` at a pinned revision.

Two rationales in `pgm-dotmac-isp-replacement` said Sub had no writer and
nothing scheduled. Sub's own dossiers named Sub writers requiring retirement and
Sub as cutover 1. Both survived review, because prose in one repository cannot
be compared to prose in another.

## What is compared

Not prose. `source_repositories` says which products were INVENTORIED, not which
hold a writer — reading it as "has a writer" makes every inventoried-but-clean
product look like debt, and parsing `local_copy_retirement` sentences is
brittle in the other direction. The dossier instead declares
`[[product_writers]]`, and this module compares typed field to typed field:

    roster: rationale_code = "no_product_writer", subject_repository = "X"
    dossier: product X -> writer_state, retirement_required

A `no_product_writer` claim holds only when the dossier says `no_writer` or
`inventory_only` AND `retirement_required` is false.

## Unknown is a failure, not a pass

Every way of not getting an answer — no dossier at the pinned path, no
`product_writers` table, no entry for the subject product, an unparseable file,
an unreachable checkout — resolves to `UNKNOWN` and fails the check. That is the
whole point: the original defect was a claim nobody could refute, and a checker
that treats "I could not tell" as "no problem" reproduces it exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

import tomllib

#: The same shape `engine` uses for a parsed record.
JsonObject = dict[str, Any]

#: States under which "this product does not write the capability" is true.
#: `inventory_only` counts because it records that somebody LOOKED and found
#: nothing, which is what makes the claim checkable rather than merely
#: unrefuted. `no_writer` counts for the same reason.
CLEAR_WRITER_STATES: Final[frozenset[str]] = frozenset({"no_writer", "inventory_only"})

CHECKED_RATIONALE_CODE: Final = "no_product_writer"


class ClaimVerdict(StrEnum):
    """Outcome of comparing one roster claim to one dossier."""

    UPHELD = "upheld"
    REFUTED = "refuted"
    #: Distinct from REFUTED on purpose. A refuted claim says the dossier
    #: disagrees; UNKNOWN says nothing could be read. Both fail, and collapsing
    #: them would hide a missing pin behind a wording argument.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClaimCheck:
    """One roster claim, checked."""

    component_id: str
    subject_repository: str
    evidence_record_id: str
    verdict: ClaimVerdict
    detail: str

    @property
    def ok(self) -> bool:
        return self.verdict is ClaimVerdict.UPHELD


def _dossier_records(matrix: JsonObject) -> dict[str, JsonObject]:
    return {
        record["record_id"]: record
        for record in matrix.get("records", [])
        if isinstance(record, dict)
        and record.get("role") == "module-dossier"
        and isinstance(record.get("record_id"), str)
    }


def _read_product_writers(
    path: Path,
) -> tuple[list[JsonObject] | None, str]:
    """Return the declared claims, or `None` with the reason none were read."""

    if not path.is_file():
        return None, f"no dossier at {path.name} in the pinned checkout"
    try:
        dossier = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        return None, f"dossier could not be parsed: {error}"
    entries = dossier.get("product_writers")
    if entries is None:
        return None, (
            "dossier declares no [[product_writers]]; silence is not a claim "
            "that no product writes this"
        )
    if not isinstance(entries, list):
        return None, "product_writers is not a list of tables"
    return [entry for entry in entries if isinstance(entry, dict)], ""


def check_claim(
    *,
    component_id: str,
    subject_repository: str,
    evidence_record_id: str,
    dossier_path: Path,
) -> ClaimCheck:
    """Compare one `no_product_writer` claim to its pinned dossier."""

    def verdict(result: ClaimVerdict, detail: str) -> ClaimCheck:
        return ClaimCheck(
            component_id=component_id,
            subject_repository=subject_repository,
            evidence_record_id=evidence_record_id,
            verdict=result,
            detail=detail,
        )

    entries, reason = _read_product_writers(dossier_path)
    if entries is None:
        return verdict(ClaimVerdict.UNKNOWN, reason)

    matching = [
        entry for entry in entries if entry.get("product") == subject_repository
    ]
    if not matching:
        return verdict(
            ClaimVerdict.UNKNOWN,
            f"dossier declares product writers but none for "
            f"{subject_repository!r}; the claim is about a product the dossier "
            "does not answer for",
        )
    if len(matching) > 1:
        return verdict(
            ClaimVerdict.UNKNOWN,
            f"dossier declares {len(matching)} entries for "
            f"{subject_repository!r}; a product's state must be one answer",
        )

    entry = matching[0]
    state = entry.get("writer_state")
    retirement = entry.get("retirement_required")
    if not isinstance(state, str) or not isinstance(retirement, bool):
        return verdict(
            ClaimVerdict.UNKNOWN,
            "the dossier entry is untyped; writer_state must be a string and "
            "retirement_required a boolean",
        )
    if state not in CLEAR_WRITER_STATES:
        return verdict(
            ClaimVerdict.REFUTED,
            f"roster claims no writer in {subject_repository}; the dossier says "
            f"writer_state={state!r}",
        )
    if retirement:
        return verdict(
            ClaimVerdict.REFUTED,
            f"roster claims no writer in {subject_repository}; the dossier says "
            f"writer_state={state!r} with retirement_required=true, so there is "
            "retirement work the roster is not scheduling",
        )
    return verdict(
        ClaimVerdict.UPHELD,
        f"dossier declares writer_state={state!r} with no retirement required",
    )


def check_matrix(matrix: JsonObject, *, checkout_root: Path) -> list[ClaimCheck]:
    """Check every `no_product_writer` claim in one programme matrix.

    `checkout_root` is a tree of the cited repository at the PINNED revision.
    Reading a moving branch would make the result depend on when it ran, which
    is the property a controlled record cannot have.
    """

    records = _dossier_records(matrix)
    checks: list[ClaimCheck] = []
    for entry in matrix.get("capability_roster", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("rationale_code") != CHECKED_RATIONALE_CODE:
            continue
        component_id = str(entry.get("component_id", "<unknown>"))
        subject = entry.get("subject_repository")
        evidence_id = entry.get("evidence_record_id")
        if not isinstance(subject, str) or not isinstance(evidence_id, str):
            checks.append(
                ClaimCheck(
                    component_id=component_id,
                    subject_repository=str(subject),
                    evidence_record_id=str(evidence_id),
                    verdict=ClaimVerdict.UNKNOWN,
                    detail="claim is missing subject_repository or evidence_record_id",
                )
            )
            continue
        record = records.get(evidence_id)
        if record is None:
            checks.append(
                ClaimCheck(
                    component_id=component_id,
                    subject_repository=subject,
                    evidence_record_id=evidence_id,
                    verdict=ClaimVerdict.UNKNOWN,
                    detail=f"no module-dossier record {evidence_id!r}",
                )
            )
            continue
        checks.append(
            check_claim(
                component_id=component_id,
                subject_repository=subject,
                evidence_record_id=evidence_id,
                dossier_path=checkout_root / str(record.get("path", "")),
            )
        )
    return checks


def failures(checks: list[ClaimCheck]) -> list[str]:
    """Human-readable lines for every claim that did not hold."""

    return [
        f"{check.component_id}: {check.verdict.value} — {check.detail}"
        for check in checks
        if not check.ok
    ]
