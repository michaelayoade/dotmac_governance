"""Command-line adapter for programme matrix validation."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from programme_control.dossier_claims import check_matrix, failures
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
    parser.add_argument(
        "--starter-checkout",
        type=Path,
        default=None,
        help=(
            "A dotmac_starter_mt tree at the revision the matrix pins. When "
            "given, every 'no_product_writer' roster claim is checked against "
            "the module dossier it cites. Omitting it skips that check — the "
            "structural validation above cannot see across repositories."
        ),
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

    if args.starter_checkout is None:
        return 0

    # The cross-repository half. A roster claim that a product has no writer is
    # settled by that product's dossier, which lives in another repository at a
    # pinned revision — so it is checked against a checkout of exactly that
    # revision, never a moving branch.
    claim_failures: list[str] = []
    checked = 0
    for path in matrices:
        matrix = json.loads(path.read_text(encoding="utf-8"))
        checks = check_matrix(matrix, checkout_root=args.starter_checkout)
        checked += len(checks)
        claim_failures.extend(f"{path.name}: {line}" for line in failures(checks))
    if claim_failures:
        for line in claim_failures:
            print(f"error: {line}")
        return 1
    print(f"ok: {checked} cross-repository writer claim(s) upheld")
    return 0
