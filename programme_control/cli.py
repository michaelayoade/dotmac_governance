"""Command-line adapter for programme matrix validation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from programme_control.engine import verify_repository


def build_parser() -> argparse.ArgumentParser:
    """Build the programme-control command parser."""
    parser = argparse.ArgumentParser(
        prog="dotmac-programme",
        description="Validate canonical Dotmac programme matrices.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Governance repository root (default: current directory).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate every programme matrix below the selected repository root."""
    args = build_parser().parse_args(argv)
    errors = verify_repository(args.root)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    matrices = sorted((args.root / "programmes").glob("*.json"))
    print(f"ok: {len(matrices)} programme matrix/matrices valid")
    return 0
