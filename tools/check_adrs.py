#!/usr/bin/env python3
"""Enforce the ADR rules from docs/adr/README.md.

Checks:
  1. Every ADR filename is NNNN-kebab-case-title.md.
  2. No two ADRs share a number (the dotmac_sub double-0004 collision).
  3. Every ADR declares exactly one valid Status.

This script fails loudly when it finds no ADRs at all. A check that passes over
an empty set is indistinguishable from a check that passes, and that has already
cost us one false "clean" result.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "adr"
FILENAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
STATUS = re.compile(r"^- Status:\s*(.+?)\s*$", re.MULTILINE)
VALID_STATUS = re.compile(r"^(Proposed|Accepted|Rejected|Superseded by \d{4})$")


def main() -> int:
    if not ADR_DIR.is_dir():
        print(f"error: {ADR_DIR} does not exist", file=sys.stderr)
        return 1

    adrs = sorted(p for p in ADR_DIR.glob("*.md") if p.name != "README.md")
    if not adrs:
        print("error: no ADRs found; refusing to report success", file=sys.stderr)
        return 1

    errors: list[str] = []
    by_number: dict[str, list[str]] = defaultdict(list)

    for path in adrs:
        match = FILENAME.match(path.name)
        if not match:
            errors.append(f"{path.name}: filename must be NNNN-kebab-case-title.md")
            continue
        by_number[match.group(1)].append(path.name)

        statuses = STATUS.findall(path.read_text(encoding="utf-8"))
        if len(statuses) != 1:
            errors.append(f"{path.name}: expected exactly one '- Status:' line, found {len(statuses)}")
        elif not VALID_STATUS.match(statuses[0]):
            errors.append(f"{path.name}: invalid status {statuses[0]!r}")

    for number, names in sorted(by_number.items()):
        if len(names) > 1:
            errors.append(f"ADR number {number} used by: {', '.join(sorted(names))}")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"ok: {len(adrs)} ADR(s), numbers unique, statuses valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
