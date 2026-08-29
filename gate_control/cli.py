"""Command-line adapter for the gate-verdict aggregator."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from .engine import (
    GateResultError,
    admission_message,
    aggregate,
    check_run,
    exit_code,
    load_results,
    render,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dotmac-gates")
    commands = parser.add_subparsers(dest="command", required=True)
    verdict = commands.add_parser("aggregate")
    verdict.add_argument("--results", type=Path, required=True)
    verdict.add_argument(
        "--format",
        choices=("text", "json", "check-run", "admission"),
        default="text",
        help=(
            "`check-run` is the Checks API payload, which is the only form "
            "that can express neutral and action_required; `admission` is the "
            "fallback message for a runner that cannot publish one"
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        results = load_results(arguments.results)
    except GateResultError as error:
        # Fails closed, and says which kind of closed. A report that cannot be
        # parsed has established nothing, which is `incomplete` rather than a
        # failure of whatever the gates were about.
        print(f"INCOMPLETE — NO TEST VERDICT: {error}")
        return 2
    outcome = aggregate(results)
    if arguments.format == "json":
        print(json.dumps(check_run(outcome), indent=2, sort_keys=True))
    elif arguments.format == "check-run":
        print(json.dumps(check_run(outcome), sort_keys=True))
    elif arguments.format == "admission":
        print(admission_message(outcome))
    else:
        print(render(outcome))
    return exit_code(outcome)
