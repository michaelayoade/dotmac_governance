"""Immutable records for the gate-verdict contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType

GateId = NewType("GateId", str)


class GateVerdict(str, Enum):
    """What a gate is allowed to say about itself.

    Four values, closed. A gate that cannot express its state in one of them is
    a gate whose colour does not mean what its name says, which is the defect
    this vocabulary exists to remove.
    """

    EXECUTED_PASSED = "executed_passed"
    EXECUTED_FAILED = "executed_failed"
    NOT_APPLICABLE = "not_applicable"
    INCOMPLETE = "incomplete"

    @property
    def conclusion(self) -> CheckConclusion:
        """The check-run conclusion this verdict must be published as.

        `not_applicable` maps to `neutral`, which SATISFIES a required check —
        that is correct by design, because a gate that legitimately does not
        apply must not block. It also means the `NO TESTS EXECUTED` evidence is
        the only thing distinguishing a legitimate skip from an invisible one.

        `incomplete` maps to `action_required`, which does NOT satisfy a
        required check. It blocks, and it is not `failure`, so nobody goes
        hunting a test defect that does not exist.
        """
        return _CONCLUSIONS[self]


#: The evidence string a `not_applicable` gate MUST carry into its summary.
#: A constant rather than a convention: `neutral` satisfies a required check by
#: design, so this text is the only thing standing between a legitimate skip
#: and an invisible one, and something has to be able to assert it is there.
NO_TESTS_EXECUTED = "NO TESTS EXECUTED"


class CheckConclusion(str, Enum):
    """The GitHub check-run conclusions the four verdicts map onto.

    This mapping is the reason the vocabulary cannot be expressed by a shell
    job's exit code. GitHub treats `success`, `skipped` AND `neutral` as
    satisfying a required check, and a conditionally skipped job reports
    `success` — which is exactly how fourteen green E2E gates came to mean "did
    not run".

    Getting `neutral` and `action_required` deliberately requires publishing a
    check run through the Checks API. See ADR 0015 for the fallback when that
    is unavailable, and for why the fallback's wrong colour is accepted.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"


class MergeDecision(str, Enum):
    """The aggregate answer, kept SEPARATE from the reason for it.

    Collapsing the two is instance 3: `blocked` was rendered as "failed", and a
    reader went looking for a PostgreSQL defect that did not exist.
    """

    ALLOWED = "allowed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict, and the evidence it is entitled to claim.

    `detail` is REQUIRED for every verdict except `executed_passed`, and that
    asymmetry is deliberate: a gate that passed has its evidence in its own
    logs, while a gate that did not run, did not finish, or failed is making a
    claim a reader cannot reconstruct without being told why.
    """

    gate_id: GateId
    verdict: GateVerdict
    detail: str

    @property
    def executed(self) -> bool:
        """Whether the work this gate names actually ran.

        The question instance 1 could not answer. A green that did not execute
        and a green that did are the same colour and different facts.
        """
        return self.verdict in (
            GateVerdict.EXECUTED_PASSED,
            GateVerdict.EXECUTED_FAILED,
        )


@dataclass(frozen=True)
class AggregateOutcome:
    """The decision, and the four buckets it was derived from.

    The buckets are carried rather than summarised so a renderer cannot
    reconstitute the collapse this contract exists to prevent: a caller that
    wants to say "failed" has to look at `failed` and find it non-empty.
    """

    decision: MergeDecision
    passed: tuple[GateResult, ...]
    failed: tuple[GateResult, ...]
    not_applicable: tuple[GateResult, ...]
    incomplete: tuple[GateResult, ...]

    @property
    def blocked_without_failure(self) -> bool:
        """Blocked, and NOT because anything failed.

        The state instance 3 had no word for. A caller that renders a headline
        must consult this before writing the word "failed", because a cancelled
        shard blocks a merge and did not fail a test.
        """
        return self.decision is MergeDecision.BLOCKED and not self.failed

    @property
    def headline(self) -> str:
        """One line that says what happened, in the reader's own vocabulary.

        `not_applicable` is named here even when everything else passed. That
        is the whole of instance 1's repair: fourteen greens meant "did not
        run", and the only thing that would have caught it is a summary saying
        so where the reader is already looking.
        """
        if self.failed:
            names = ", ".join(item.gate_id for item in self.failed)
            return f"BLOCKED — executed_failed: {names}"
        if self.incomplete:
            names = ", ".join(item.gate_id for item in self.incomplete)
            return (
                f"BLOCKED — incomplete (not a test failure): {names}. "
                "These gates were cancelled, timed out, were blocked or never "
                "reported; nothing about the properties they name has been "
                "established"
            )
        if self.not_applicable:
            names = ", ".join(item.gate_id for item in self.not_applicable)
            return (
                f"ALLOWED — executed_passed: {len(self.passed)}; "
                f"NOT APPLICABLE, so unproven: {names}"
            )
        return f"ALLOWED — executed_passed: {len(self.passed)}"


#: Defined after the enums so both names resolve. A table rather than a chain
#: of conditionals, so the mapping can be read — and asserted — in one place.
_CONCLUSIONS: dict[GateVerdict, CheckConclusion] = {
    GateVerdict.EXECUTED_PASSED: CheckConclusion.SUCCESS,
    GateVerdict.EXECUTED_FAILED: CheckConclusion.FAILURE,
    GateVerdict.NOT_APPLICABLE: CheckConclusion.NEUTRAL,
    GateVerdict.INCOMPLETE: CheckConclusion.ACTION_REQUIRED,
}
