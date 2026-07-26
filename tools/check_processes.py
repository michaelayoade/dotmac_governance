#!/usr/bin/env python3
"""Enforce the process-definition contract from processes/README.md.

This validates that a process *definition* is well formed. It is not the
conformance validator: that one checks a repository against its
`.governance.yml`, is derived from accepted processes, and does not exist yet.
Keeping them separate matters — this check may run before any process is
accepted, and must not imply that anything conforms to anything.

Callable against a temporary directory so its known-bad controls can prove they
fail rather than merely asserting that the production directory passes.
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

PROCESS_DIR = Path(__file__).resolve().parent.parent / "processes"
FILENAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
VALID_STATUS = re.compile(
    r"^(Proposed|Accepted|Rejected|Superseded by [a-z0-9]+(?:-[a-z0-9]+)*)$"
)

REQUIRED_FIELDS = (
    "Status",
    "Date",
    "Owner",
    "Approver",
    "Classification",
    "Model version",
)
OPTIONAL_FIELDS = ("Effective",)
KNOWN_FIELDS = frozenset(REQUIRED_FIELDS + OPTIONAL_FIELDS)

SECTIONS = (
    "Purpose",
    "Standards mapping",
    "Inputs",
    "Activities",
    "Outcomes",
    "`required_information_items`",
    "`work_products`",
    "Approval gate",
    "Effectiveness verification",
    "Agent participation",
    "Enforcement",
    "Declaration",
)

# Declaration keys the derived .governance.yml schema will need. Checked
# textually rather than by parsing YAML, so the control carries no dependency
# the CI runner might not have.
DECLARATION_KEYS = (
    "process:",
    "model_version:",
    "status:",
    "enforcement:",
)

METADATA_LINE = re.compile(r"^- ([A-Za-z][A-Za-z ]*?):\s*(.*?)\s*$", re.MULTILINE)
SECTION_START = re.compile(r"^## ", re.MULTILINE)
DECLARATION_BLOCK = re.compile(r"^```yaml\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _metadata_region(body: str) -> str:
    """Everything before the first section: the controlled metadata block."""
    match = SECTION_START.search(body)
    return body[: match.start()] if match else body


def _fields(body: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = defaultdict(list)
    for key, value in METADATA_LINE.findall(_metadata_region(body)):
        found[key].append(value)
    return found


def _declaration_errors(name: str, slug: str, body: str, status: str) -> list[str]:
    match = DECLARATION_BLOCK.search(body)
    if not match:
        return [f"{name}: missing the fenced ```yaml Declaration block"]

    block = match.group(1)
    errors: list[str] = []

    for key in DECLARATION_KEYS:
        if not re.search(rf"^{re.escape(key)}", block, flags=re.MULTILINE):
            errors.append(f"{name}: Declaration is missing '{key}'")

    declared = re.search(r"^process:\s*(\S+)\s*$", block, flags=re.MULTILINE)
    if declared and declared.group(1) != slug:
        errors.append(
            f"{name}: Declaration says process {declared.group(1)!r} "
            f"but the file is {slug!r}"
        )

    declared_status = re.search(r"^status:\s*(\S+)\s*$", block, flags=re.MULTILINE)
    if declared_status and status:
        # The declaration carries the lifecycle keyword only: 'Superseded by
        # <slug>' normalizes to 'superseded', since the successor is already
        # named in the metadata and duplicating it invites the two copies to
        # disagree.
        expected = status.split()[0].lower()
        if declared_status.group(1) != expected:
            errors.append(
                f"{name}: Declaration status {declared_status.group(1)!r} does "
                f"not match '- Status: {status}' (expected {expected!r})"
            )

    # The enforcement rule from processes/README.md: a process declares a CI
    # check or a named human. A process with neither is deleted, so a
    # declaration asserting neither must fail rather than be recorded.
    if re.search(r"^enforcement:\s*none\s*$", block, flags=re.MULTILINE):
        errors.append(
            f"{name}: 'enforcement: none' is not a valid declaration; a process "
            "with neither a CI check nor a named manual owner is deleted"
        )
    else:
        enforcement = re.search(
            r"^enforcement:\n((?:[ \t]+.*\n?)*)", block, flags=re.MULTILINE
        )
        if enforcement and not re.search(
            r"^\s+(ci|manual):", enforcement.group(1), flags=re.MULTILINE
        ):
            errors.append(
                f"{name}: 'enforcement:' must declare 'ci:' or 'manual:'"
            )

    return errors


def validate_processes(process_dir: Path) -> list[str]:
    """Return every validation error for the process directory.

    An empty directory is valid. Processes are adopted deliberately, and
    ADR 0002 expects `processes/` to be empty until the first one is approved —
    unlike ADRs, where an empty set means the validator found nothing to check
    and should refuse to report success.
    """
    if not process_dir.is_dir():
        return [f"{process_dir} does not exist"]

    definitions = sorted(
        p for p in process_dir.glob("*.md") if p.name != "README.md"
    )

    errors: list[str] = []

    for path in definitions:
        name = path.name
        if not FILENAME.match(name):
            errors.append(f"{name}: filename must be kebab-case-slug.md")
            continue
        slug = path.stem

        body = path.read_text(encoding="utf-8")
        fields = _fields(body)

        for field in REQUIRED_FIELDS:
            count = len(fields.get(field, []))
            if count != 1:
                errors.append(
                    f"{name}: expected exactly one '- {field}:' line, found {count}"
                )

        for field in OPTIONAL_FIELDS:
            if len(fields.get(field, [])) > 1:
                errors.append(f"{name}: expected at most one '- {field}:' line")

        for field in sorted(set(fields) - KNOWN_FIELDS):
            errors.append(
                f"{name}: unknown controlled metadata field '- {field}:'; "
                f"known fields are {', '.join(sorted(KNOWN_FIELDS))}"
            )

        statuses = fields.get("Status", [])
        status = statuses[0] if len(statuses) == 1 else ""
        if status and not VALID_STATUS.fullmatch(status):
            errors.append(f"{name}: invalid status {status!r}")

        for section in SECTIONS:
            if not re.search(
                rf"^## {re.escape(section)}\s*$", body, flags=re.MULTILINE
            ):
                errors.append(f"{name}: missing required section {section!r}")

        errors.extend(_declaration_errors(name, slug, body, status))

    return errors


def main() -> int:
    errors = validate_processes(PROCESS_DIR)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    definitions = sorted(
        p for p in PROCESS_DIR.glob("*.md") if p.name != "README.md"
    )
    accepted = sum(
        1
        for p in definitions
        if _fields(p.read_text(encoding="utf-8")).get("Status", [""])[0] == "Accepted"
    )
    print(
        f"ok: {len(definitions)} process definition(s), {accepted} accepted, "
        "controlled metadata, required sections, and declarations valid"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
