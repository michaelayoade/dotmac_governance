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
VALID_STATUS = re.compile(r"^(Proposed|Accepted|Rejected|Superseded by \d{4})$")
FIELDS = (
    "Status",
    "Date",
    "Owner",
    "Approver",
    "Scope",
    "Classification",
)
SECTIONS = (
    "Context",
    "Decision",
    "Consequences",
    "Drift prevention",
)


def _field_values(body: str, field: str) -> list[str]:
    pattern = re.compile(rf"^- {re.escape(field)}:\s*(.+?)\s*$", re.MULTILINE)
    return pattern.findall(body)


def validate_adrs(adr_dir: Path) -> list[str]:
    """Return every validation error for the ADR directory."""
    if not adr_dir.is_dir():
        return [f"{adr_dir} does not exist"]

    adrs = sorted(p for p in adr_dir.glob("*.md") if p.name != "README.md")
    if not adrs:
        return ["no ADRs found; refusing to report success"]

    errors: list[str] = []
    by_number: dict[str, list[str]] = defaultdict(list)

    for path in adrs:
        match = FILENAME.match(path.name)
        if not match:
            errors.append(f"{path.name}: filename must be NNNN-kebab-case-title.md")
            continue
        by_number[match.group(1)].append(path.name)

        body = path.read_text(encoding="utf-8")
        field_values = {
            field: _field_values(body, field)
            for field in FIELDS
        }
        for field, values in field_values.items():
            if len(values) != 1:
                errors.append(
                    f"{path.name}: expected exactly one '- {field}:' line, "
                    f"found {len(values)}"
                )

        statuses = field_values["Status"]
        if len(statuses) == 1 and not VALID_STATUS.fullmatch(statuses[0]):
            errors.append(f"{path.name}: invalid status {statuses[0]!r}")

        for section in SECTIONS:
            if not re.search(
                rf"^## {re.escape(section)}\s*$",
                body,
                flags=re.MULTILINE,
            ):
                errors.append(f"{path.name}: missing required section {section!r}")

    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            errors.append(f"ADR number {number} used by: {', '.join(sorted(names))}")

    return errors


def main() -> int:
    errors = validate_adrs(ADR_DIR)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    adrs = sorted(p for p in ADR_DIR.glob("*.md") if p.name != "README.md")
    print(
        f"ok: {len(adrs)} ADR(s), numbers unique, controlled metadata and "
        "required sections valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
