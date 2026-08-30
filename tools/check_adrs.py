#!/usr/bin/env python3
"""Enforce the controlled ADR contract from docs/adr/README.md.

The validator is intentionally callable against a temporary directory so its
known-bad controls can prove that they fail, rather than merely asserting that
the production directory passes.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
FILENAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
VALID_STATUS = re.compile(r"^(Proposed|Accepted|Rejected|Superseded by (\d{4}))$")
SUPERSEDED_STATUS = re.compile(r"^Superseded by (\d{4})$")

REQUIRED_FIELDS = (
    "Status",
    "Date",
    "Owner",
    "Approver",
    "Scope",
    "Classification",
)
OPTIONAL_FIELDS = (
    "Effective",
    "Amends",
    "Supersedes",
)
KNOWN_FIELDS = frozenset(REQUIRED_FIELDS + OPTIONAL_FIELDS)

SECTIONS = (
    "Context",
    "Decision",
    "Consequences",
    "Drift prevention",
)

# `Amends` names the record it changes and, after an em dash or hyphen, the
# part of it that changes. A bare number is rejected: an amendment that does
# not say what it narrows is indistinguishable from a supersession.
AMENDS = re.compile(r"^(\d{4})\s*[—–-]\s*(\S.*)$")
SUPERSEDES = re.compile(r"^(\d{4})$")

# The key class is deliberately WIDER than the set of legal field names. The
# unknown-field check below can only reject a key it can SEE, so a class that
# admitted only letters and spaces did not narrow what was legal — it decided
# what was invisible. `- Supersedes-Knowledge:` and `- Status2:` never matched,
# never entered `_fields()`, and were silently accepted, while the alphabetic
# `- Ammends:` was correctly rejected. Digits, underscores and hyphens are
# admitted here so that the closed set, and not the regex, is what refuses them.
METADATA_LINE = re.compile(
    r"^- ([A-Za-z][A-Za-z0-9 _-]*?):\s*(.*?)\s*$", re.MULTILINE
)
SECTION_START = re.compile(r"^## ", re.MULTILINE)


def _metadata_region(body: str) -> str:
    """Return the controlled metadata block: everything before the first section.

    Scoping the field scan to this region keeps prose from being read as
    controlled metadata, and lets an unknown-field check run without tripping
    over ordinary bulleted text in ``## Context``.
    """
    match = SECTION_START.search(body)
    return body[: match.start()] if match else body


def _fields(body: str) -> dict[str, list[str]]:
    """Return every ``- Key: value`` line found in the metadata region."""
    found: dict[str, list[str]] = defaultdict(list)
    for key, value in METADATA_LINE.findall(_metadata_region(body)):
        found[key].append(value)
    return found


def _record_errors(name: str, fields: dict[str, list[str]], body: str) -> list[str]:
    """Validate one record in isolation, ignoring cross-record relationships."""
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        count = len(fields.get(field, []))
        if count != 1:
            errors.append(
                f"{name}: expected exactly one '- {field}:' line, found {count}"
            )

    for field in OPTIONAL_FIELDS:
        count = len(fields.get(field, []))
        if count > 1:
            errors.append(
                f"{name}: expected at most one '- {field}:' line, found {count}"
            )

    for field in sorted(set(fields) - KNOWN_FIELDS):
        errors.append(
            f"{name}: unknown controlled metadata field '- {field}:'; "
            f"known fields are {', '.join(sorted(KNOWN_FIELDS))}"
        )

    statuses = fields.get("Status", [])
    if len(statuses) == 1 and not VALID_STATUS.fullmatch(statuses[0]):
        errors.append(f"{name}: invalid status {statuses[0]!r}")

    for section in SECTIONS:
        if not re.search(
            rf"^## {re.escape(section)}\s*$",
            body,
            flags=re.MULTILINE,
        ):
            errors.append(f"{name}: missing required section {section!r}")

    return errors


def _relationship_errors(
    name: str,
    number: str,
    fields: dict[str, list[str]],
    numbers: dict[str, str],
    amends: dict[str, str],
    supersedes: dict[str, str],
) -> list[str]:
    """Validate this record's declared relationships to other records.

    A relationship that points at a record which does not exist, points at
    itself, or is not mirrored by the other record is a drift the ADR
    discipline exists to catch. Prose describing the relationship is not
    checkable; these fields are.
    """
    errors: list[str] = []

    raw_amends = fields.get("Amends", [])
    if len(raw_amends) == 1:
        match = AMENDS.fullmatch(raw_amends[0])
        if not match:
            errors.append(
                f"{name}: '- Amends:' must be 'NNNN — what it changes', "
                f"found {raw_amends[0]!r}"
            )
        else:
            target = match.group(1)
            if target == number:
                errors.append(f"{name}: amends itself")
            elif target not in numbers:
                errors.append(f"{name}: amends ADR {target}, which does not exist")
            amends[number] = target

    raw_supersedes = fields.get("Supersedes", [])
    if len(raw_supersedes) == 1:
        match = SUPERSEDES.fullmatch(raw_supersedes[0])
        if not match:
            errors.append(
                f"{name}: '- Supersedes:' must be a four-digit ADR number, "
                f"found {raw_supersedes[0]!r}"
            )
        else:
            target = match.group(1)
            if target == number:
                errors.append(f"{name}: supersedes itself")
            elif target not in numbers:
                errors.append(
                    f"{name}: supersedes ADR {target}, which does not exist"
                )
            supersedes[number] = target

    if amends.get(number) and amends.get(number) == supersedes.get(number):
        errors.append(
            f"{name}: both amends and supersedes ADR {amends[number]}; "
            "a record is either narrowed or replaced, not both"
        )

    return errors


def _mirror_errors(
    numbers: dict[str, str],
    statuses: dict[str, str],
    supersedes: dict[str, str],
) -> list[str]:
    """Require supersession to be declared by both records, not just one."""
    errors: list[str] = []

    for number, target in sorted(supersedes.items()):
        if target not in numbers:
            continue
        status = statuses.get(target, "")
        match = SUPERSEDED_STATUS.fullmatch(status)
        if not match:
            errors.append(
                f"{numbers[target]}: superseded by ADR {number} but its status "
                f"is {status!r}; expected 'Superseded by {number}'"
            )
        elif match.group(1) != number:
            errors.append(
                f"{numbers[target]}: status claims supersession by ADR "
                f"{match.group(1)}, but ADR {number} supersedes it"
            )

    for number, status in sorted(statuses.items()):
        match = SUPERSEDED_STATUS.fullmatch(status)
        if not match:
            continue
        successor = match.group(1)
        if successor not in numbers:
            errors.append(
                f"{numbers[number]}: superseded by ADR {successor}, "
                "which does not exist"
            )
        elif supersedes.get(successor) != number:
            errors.append(
                f"{numbers[successor]}: must declare '- Supersedes: {number}' "
                f"because ADR {number} records it as the superseding record"
            )

    return errors


def validate_adrs(adr_dir: Path) -> list[str]:
    """Return every validation error for the ADR directory."""
    if not adr_dir.is_dir():
        return [f"{adr_dir} does not exist"]

    adrs = sorted(p for p in adr_dir.glob("*.md") if p.name != "README.md")
    if not adrs:
        return ["no ADRs found; refusing to report success"]

    errors: list[str] = []
    by_number: dict[str, list[str]] = defaultdict(list)
    parsed: list[tuple[str, str, dict[str, list[str]], str]] = []

    for path in adrs:
        match = FILENAME.match(path.name)
        if not match:
            errors.append(f"{path.name}: filename must be NNNN-kebab-case-title.md")
            continue
        number = match.group(1)
        by_number[number].append(path.name)

        body = path.read_text(encoding="utf-8")
        fields = _fields(body)
        parsed.append((path.name, number, fields, body))
        errors.extend(_record_errors(path.name, fields, body))

    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            errors.append(f"ADR number {number} used by: {', '.join(sorted(names))}")

    # Relationships are only checkable against an unambiguous record set. A
    # duplicate number means "ADR 0004" does not identify one record, so
    # resolve numbering before reporting relationship failures against it.
    if any(len(names) > 1 for names in by_number.values()):
        return errors

    numbers = {number: name for name, number, _, _ in parsed}
    statuses = {
        number: fields["Status"][0]
        for _, number, fields, _ in parsed
        if len(fields.get("Status", [])) == 1
    }
    amends: dict[str, str] = {}
    supersedes: dict[str, str] = {}

    for name, number, fields, _ in parsed:
        errors.extend(
            _relationship_errors(name, number, fields, numbers, amends, supersedes)
        )

    errors.extend(_mirror_errors(numbers, statuses, supersedes))

    return errors


def main() -> int:
    errors = validate_adrs(ADR_DIR)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    adrs = sorted(p for p in ADR_DIR.glob("*.md") if p.name != "README.md")
    print(
        f"ok: {len(adrs)} ADR(s), numbers unique, controlled metadata, "
        "declared relationships, and required sections valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
