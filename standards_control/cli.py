"""Command-line adapter for engineering conformance."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .contracts import BranchName
from .engine import verify_repository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dotmac-standards")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, default=Path.cwd())
    verify.add_argument(
        "--profile", type=Path, default=Path(".dotmac/standards-profile.json")
    )
    verify.add_argument("--default-branch")
    verify.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = arguments.root.resolve()
    profile = arguments.profile
    if not profile.is_absolute():
        profile = root / profile
    branch = BranchName(arguments.default_branch) if arguments.default_branch else None
    report = verify_repository(root, profile, observed_default_branch=branch)
    if arguments.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        state = "PASS" if report.conforms else "FAIL"
        mode = report.enforcement_mode.value if report.enforcement_mode else "unknown"
        print(f"{state} profile={report.profile_id or 'invalid'} mode={mode}")
        for item in report.diagnostics:
            location = f" {item.path}" if item.path else ""
            if item.line is not None:
                location += f":{item.line}"
            print(f"{item.severity.value} {item.code.value}{location}: {item.message}")
    return 0 if report.conforms else 1
