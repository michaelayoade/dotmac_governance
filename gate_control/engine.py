"""Parsing gate results, and aggregating them without collapsing the verdicts."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .contracts import (
    NO_TESTS_EXECUTED,
    AggregateOutcome,
    CheckConclusion,
    GateId,
    GateResult,
    GateVerdict,
    MergeDecision,
)

__all__ = [
    "GateResultError",
    "admission_message",
    "aggregate",
    "check_run",
    "exit_code",
    "load_results",
    "parse_results",
    "render",
]

#: A verdict that needs its reason stated. `executed_passed` is the exception:
#: its evidence is its own run. Everything else is a claim a reader cannot
#: reconstruct without being told why, and the unstated ones are exactly how
#: instance 1 survived fourteen times.
_DETAIL_REQUIRED = frozenset(
    {
        GateVerdict.EXECUTED_FAILED,
        GateVerdict.NOT_APPLICABLE,
        GateVerdict.INCOMPLETE,
    }
)


class GateResultError(ValueError):
    """A gate report that cannot be believed."""


def _result(value: object, location: str) -> GateResult:
    if not isinstance(value, dict):
        raise GateResultError(f"{location} must be an object")
    unknown = sorted(set(value) - {"gate_id", "verdict", "detail"})
    missing = sorted({"gate_id", "verdict", "detail"} - set(value))
    if missing:
        raise GateResultError(f"{location} missing keys: {', '.join(missing)}")
    if unknown:
        raise GateResultError(f"{location} has unknown keys: {', '.join(unknown)}")
    raw_id = value["gate_id"]
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise GateResultError(f"{location}.gate_id must be a non-empty string")
    raw_verdict = value["verdict"]
    if not isinstance(raw_verdict, str):
        raise GateResultError(f"{location}.verdict must be a string")
    try:
        verdict = GateVerdict(raw_verdict)
    except ValueError as error:
        permitted = ", ".join(item.value for item in GateVerdict)
        raise GateResultError(
            f"{location}.verdict must be one of {permitted}; a gate that cannot "
            "say which of these it is has a colour that does not mean what its "
            "name says"
        ) from error
    raw_detail = value["detail"]
    if not isinstance(raw_detail, str):
        raise GateResultError(f"{location}.detail must be a string")
    detail = raw_detail.strip()
    if verdict in _DETAIL_REQUIRED and not detail:
        raise GateResultError(
            f"{location}.verdict is {verdict.value} and states no reason. A "
            "gate that did not run, did not finish, or failed is making a claim "
            "a reader cannot reconstruct without being told why"
        )
    return GateResult(gate_id=GateId(raw_id.strip()), verdict=verdict, detail=detail)


def parse_results(value: object) -> tuple[GateResult, ...]:
    """Parse a gate report, refusing anything ambiguous.

    Fails closed on an EMPTY report. A run that produced no verdicts has
    established nothing, and an aggregator that answered `allowed` for it would
    be the fourteen-greens defect with the filter removed entirely.
    """
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise GateResultError("a gate report must be an array of results")
    results = tuple(
        _result(item, f"results[{index}]") for index, item in enumerate(value)
    )
    if not results:
        raise GateResultError(
            "a gate report with no results establishes nothing; a run that "
            "reported no verdict is incomplete, not allowed"
        )
    seen: set[GateId] = set()
    for item in results:
        if item.gate_id in seen:
            raise GateResultError(f"duplicate gate_id {item.gate_id}")
        seen.add(item.gate_id)
    return results


def load_results(path: Path) -> tuple[GateResult, ...]:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GateResultError(f"cannot read gate report {path}: {error}") from error
    return parse_results(value)


def aggregate(results: Sequence[GateResult]) -> AggregateOutcome:
    """Bucket the verdicts and decide, WITHOUT collapsing them.

    The bug this replaces is one line long: `success if all(r == "success")`,
    which makes `cancelled` and `failed` the same word. Here each verdict keeps
    its own bucket all the way to the caller, so a renderer that wants to say
    "failed" has to look at the failed bucket and find something in it.
    """
    buckets: dict[GateVerdict, list[GateResult]] = {
        verdict: [] for verdict in GateVerdict
    }
    for item in results:
        buckets[item.verdict].append(item)
    blocked = bool(
        buckets[GateVerdict.EXECUTED_FAILED] or buckets[GateVerdict.INCOMPLETE]
    )
    return AggregateOutcome(
        decision=MergeDecision.BLOCKED if blocked else MergeDecision.ALLOWED,
        passed=tuple(buckets[GateVerdict.EXECUTED_PASSED]),
        failed=tuple(buckets[GateVerdict.EXECUTED_FAILED]),
        not_applicable=tuple(buckets[GateVerdict.NOT_APPLICABLE]),
        incomplete=tuple(buckets[GateVerdict.INCOMPLETE]),
    )


def render(outcome: AggregateOutcome) -> str:
    """The summary a reader sees, with every verdict named.

    `not_applicable` gets a line of its own even when the decision is
    `allowed`. Instance 1 was fourteen greens that meant "did not run", and a
    summary that omits the unproven gates reproduces it exactly.
    """
    lines = [outcome.headline, ""]
    for label, bucket in (
        ("executed_passed", outcome.passed),
        ("executed_failed", outcome.failed),
        ("incomplete", outcome.incomplete),
        ("not_applicable", outcome.not_applicable),
    ):
        for item in bucket:
            suffix = f" — {item.detail}" if item.detail else ""
            lines.append(f"{label:<16} {item.gate_id}{suffix}")
    return "\n".join(lines)


def exit_code(outcome: AggregateOutcome) -> int:
    """Distinct codes, because the two ways of being blocked are different.

    ``0`` allowed, ``1`` something executed and failed, ``2`` blocked with
    nothing failed. A caller that only checks non-zero still blocks; a caller
    that reports a headline can tell instance 3 from a real defect.
    """
    if outcome.failed:
        return 1
    if outcome.decision is MergeDecision.BLOCKED:
        return 2
    return 0


def check_run(outcome: AggregateOutcome) -> dict[str, object]:
    """The check-run payload a Governance action publishes through the Checks API.

    A shell job cannot express this vocabulary. GitHub treats `success`,
    `skipped` and `neutral` alike as satisfying a required check, and a
    conditionally skipped job reports `success` — so an exit code can say
    "blocked" or "not blocked" and can never say "did not run". Publishing the
    check run directly is what makes `neutral` and `action_required` reachable.

    `NO TESTS EXECUTED` is placed in the SUMMARY, not only in the detail body,
    because the summary is the line a reader sees on the pull request without
    opening anything.
    """
    if outcome.failed:
        conclusion = CheckConclusion.FAILURE
    elif outcome.incomplete:
        conclusion = CheckConclusion.ACTION_REQUIRED
    elif outcome.not_applicable:
        conclusion = CheckConclusion.NEUTRAL
    else:
        conclusion = CheckConclusion.SUCCESS
    summary = outcome.headline
    if outcome.not_applicable and not outcome.failed and not outcome.incomplete:
        summary = f"{NO_TESTS_EXECUTED} for some gates — {summary}"
    return {
        "conclusion": conclusion.value,
        "output": {
            "title": summary[:255],
            "summary": summary,
            "text": render(outcome),
        },
    }


def admission_message(outcome: AggregateOutcome) -> str:
    """The FALLBACK, for a runner that cannot publish a check run.

    A required job that fails for `incomplete`. The red colour is unavoidable
    and is accepted deliberately: a wrong colour with an unambiguous message is
    strictly better than a right colour that lies. ADR 0015 records the
    tradeoff rather than leaving it to whoever wires the job.
    """
    if outcome.failed:
        return outcome.headline
    if outcome.incomplete:
        names = ", ".join(item.gate_id for item in outcome.incomplete)
        return f"INCOMPLETE — NO TEST VERDICT: {names}"
    if outcome.not_applicable:
        return f"{NO_TESTS_EXECUTED} — {outcome.headline}"
    return outcome.headline
