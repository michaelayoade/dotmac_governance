"""Command-line adapter for engineering conformance."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path

from .contracts import BranchName, CanonicalRepository, GitRevision
from .engine import verify_repository


def _git_revision(value: str) -> GitRevision:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("must be a full lower-case Git SHA")
    return GitRevision(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dotmac-standards")
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, default=Path.cwd())
    verify.add_argument(
        "--profile", type=Path, default=Path(".dotmac/standards-profile.json")
    )
    verify.add_argument("--default-branch")
    verify.add_argument("--governance-root", type=Path)
    verify.add_argument("--governance-repository")
    verify.add_argument("--governance-revision")
    verify.add_argument(
        "--base-revision",
        type=_git_revision,
        help="Trusted base commit for history-sensitive checks.",
    )
    verify.add_argument(
        "--repository-revision",
        type=_git_revision,
        help="Trusted checked-out product commit.",
    )
    verify.add_argument("--retirement-observation", type=Path)
    verify.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    root = arguments.root.resolve()
    profile = arguments.profile
    if not profile.is_absolute():
        profile = root / profile
    branch = BranchName(arguments.default_branch) if arguments.default_branch else None
    governance_repository = None
    if arguments.governance_repository:
        raw_repository = arguments.governance_repository
        if "://" not in raw_repository:
            raw_repository = f"https://github.com/{raw_repository}"
        governance_repository = CanonicalRepository(raw_repository.removesuffix(".git"))
    governance_revision = (
        GitRevision(arguments.governance_revision)
        if arguments.governance_revision
        else None
    )
    governance_root = (
        arguments.governance_root.resolve()
        if arguments.governance_root is not None
        else None
    )
    report = verify_repository(
        root,
        profile,
        observed_default_branch=branch,
        governance_root=governance_root,
        observed_governance_repository=governance_repository,
        observed_governance_revision=governance_revision,
        observed_revision=arguments.repository_revision,
        base_revision=arguments.base_revision,
        retirement_observation_path=arguments.retirement_observation,
    )
    if arguments.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        state = "PASS" if report.conforms else "FAIL"
        mode = report.enforcement_mode.value if report.enforcement_mode else "unknown"
        retirements = ",".join(report.enrolled_retirement_ids) or "none"
        print(
            f"{state} profile={report.profile_id or 'invalid'} mode={mode} "
            f"repository_contracts={report.to_dict()['repository_contracts']} "
            f"product_revision_evidence={report.product_revision_evidence} "
            f"target_evidence={report.target_evidence} "
            f"enrolled_retirement_ids={retirements}"
        )
        for item in report.diagnostics:
            location = f" {item.path}" if item.path else ""
            if item.line is not None:
                location += f":{item.line}"
            print(f"{item.severity.value} {item.code.value}{location}: {item.message}")
    return 0 if report.conforms else 1
