"""The four gate verdicts, and the aggregator that must not collapse them.

Every proof here plants one of the three failures observed on 2026-08-29 and
asserts the vocabulary reports it correctly. A verdict enum with no aggregator
honouring it is the `enforcement: none yet` gap in a different costume, so the
enum is never asserted on its own.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gate_control import (
    NO_TESTS_EXECUTED,
    CheckConclusion,
    GateVerdict,
    MergeDecision,
    admission_message,
    aggregate,
    check_run,
    exit_code,
    parse_results,
    render,
)
from gate_control.cli import main
from gate_control.engine import GateResultError, load_results


def report(*entries: tuple[str, str, str]) -> list[dict[str, str]]:
    return [
        {"gate_id": gate, "verdict": verdict, "detail": detail}
        for gate, verdict, detail in entries
    ]


class GateVerdictTests(unittest.TestCase):
    # ── the vocabulary maps onto conclusions, not exit codes ──────────────

    def test_every_verdict_has_exactly_one_check_conclusion(self) -> None:
        """The mapping is the reason a shell job cannot express this.

        GitHub treats `success`, `skipped` AND `neutral` as satisfying a
        required check, and a conditionally skipped job reports `success`. An
        exit code can say blocked or not blocked; it can never say "did not
        run".
        """
        self.assertEqual(
            {verdict: verdict.conclusion for verdict in GateVerdict},
            {
                GateVerdict.EXECUTED_PASSED: CheckConclusion.SUCCESS,
                GateVerdict.EXECUTED_FAILED: CheckConclusion.FAILURE,
                GateVerdict.NOT_APPLICABLE: CheckConclusion.NEUTRAL,
                GateVerdict.INCOMPLETE: CheckConclusion.ACTION_REQUIRED,
            },
        )

    def test_not_applicable_maps_to_a_conclusion_that_PERMITS_merging(self) -> None:
        """Correct by design: a gate that legitimately does not apply must not
        block. Which is exactly why the evidence below is load-bearing."""
        self.assertEqual(GateVerdict.NOT_APPLICABLE.conclusion, CheckConclusion.NEUTRAL)

    def test_incomplete_maps_to_a_conclusion_that_BLOCKS_merging(self) -> None:
        """`action_required` does not satisfy a required check, and it is not
        `failure`, so nobody hunts a test defect that does not exist."""
        self.assertEqual(
            GateVerdict.INCOMPLETE.conclusion, CheckConclusion.ACTION_REQUIRED
        )

    def test_incomplete_is_never_published_as_a_failure(self) -> None:
        self.assertNotEqual(GateVerdict.INCOMPLETE.conclusion, CheckConclusion.FAILURE)

    # ── instance 3: a cancelled shard is not a test failure ───────────────

    def test_a_cancelled_shard_blocks_and_is_not_called_a_failure(self) -> None:
        """The PostgreSQL Gate that read "failed" for a job never allowed to
        finish. Its log said exactly `INTEGRATION_RESULT: cancelled`, and no
        PostgreSQL test failed."""
        outcome = aggregate(
            parse_results(
                report(
                    ("unit", "executed_passed", ""),
                    ("postgres", "incomplete", "INTEGRATION_RESULT: cancelled"),
                )
            )
        )
        self.assertIs(outcome.decision, MergeDecision.BLOCKED)
        self.assertEqual(outcome.failed, ())
        self.assertTrue(outcome.blocked_without_failure)
        self.assertIn("incomplete", outcome.headline)
        self.assertIn("not a test failure", outcome.headline)
        self.assertNotIn("executed_failed", outcome.headline)
        self.assertEqual(check_run(outcome)["conclusion"], "action_required")

    def test_the_collapse_that_caused_instance_3_cannot_be_reproduced(self) -> None:
        """The one-line bug: `success if all(r == "success")`, which makes
        `cancelled` and `failed` the same word. The buckets are carried to the
        caller so a renderer that wants to say "failed" has to find something
        in the failed bucket."""
        outcome = aggregate(
            parse_results(report(("postgres", "incomplete", "cancelled mid-flight")))
        )
        self.assertEqual(len(outcome.incomplete), 1)
        self.assertEqual(len(outcome.failed), 0)
        self.assertEqual(exit_code(outcome), 2)

    def test_a_real_failure_is_distinguishable_from_a_cancellation(self) -> None:
        """The negative control. Two different blocked states must not render
        the same, or the vocabulary has bought nothing."""
        failed = aggregate(
            parse_results(report(("unit", "executed_failed", "3 assertions")))
        )
        cancelled = aggregate(
            parse_results(report(("unit", "incomplete", "cancelled")))
        )
        self.assertIs(failed.decision, MergeDecision.BLOCKED)
        self.assertIs(cancelled.decision, MergeDecision.BLOCKED)
        self.assertFalse(failed.blocked_without_failure)
        self.assertTrue(cancelled.blocked_without_failure)
        self.assertEqual(exit_code(failed), 1)
        self.assertEqual(exit_code(cancelled), 2)
        self.assertNotEqual(failed.headline, cancelled.headline)

    # ── instance 1: fourteen greens that meant "did not run" ──────────────

    def test_a_filtered_out_suite_is_not_applicable_and_not_passed(self) -> None:
        """All fourteen green E2E Gate runs on 2026-08-29 skipped Playwright,
        and every run that executed it failed. A live production defect rode
        through a full day of merges on those greens."""
        outcome = aggregate(
            parse_results(
                report(
                    ("unit", "executed_passed", ""),
                    ("e2e", "not_applicable", "no UI path in the diff"),
                )
            )
        )
        self.assertEqual(len(outcome.passed), 1)
        self.assertEqual(len(outcome.not_applicable), 1)
        self.assertNotIn("e2e", [item.gate_id for item in outcome.passed])
        self.assertFalse(outcome.not_applicable[0].executed)

    def test_not_applicable_permits_merging(self) -> None:
        outcome = aggregate(
            parse_results(report(("e2e", "not_applicable", "no UI path")))
        )
        self.assertIs(outcome.decision, MergeDecision.ALLOWED)
        self.assertEqual(exit_code(outcome), 0)

    def test_a_permitted_skip_still_says_NO_TESTS_EXECUTED_where_it_is_seen(
        self,
    ) -> None:
        """The property that makes the permitted skip safe.

        `neutral` satisfies a required check by design, so this evidence is the
        ONLY thing standing between a legitimate skip and an invisible one. It
        goes in the summary — the line a reader sees without opening anything —
        not merely in the detail body.
        """
        outcome = aggregate(
            parse_results(report(("e2e", "not_applicable", "no UI path")))
        )
        payload = check_run(outcome)
        output = payload["output"]
        assert isinstance(output, dict)
        self.assertEqual(payload["conclusion"], "neutral")
        self.assertIn(NO_TESTS_EXECUTED, str(output["summary"]))
        self.assertIn(NO_TESTS_EXECUTED, str(output["title"]))

    def test_an_all_passed_run_does_not_claim_NO_TESTS_EXECUTED(self) -> None:
        """The sensitivity proof for the marker. If it appeared unconditionally
        it would carry no information, and a reader would learn to ignore it."""
        outcome = aggregate(parse_results(report(("unit", "executed_passed", ""))))
        payload = check_run(outcome)
        output = payload["output"]
        assert isinstance(output, dict)
        self.assertEqual(payload["conclusion"], "success")
        self.assertNotIn(NO_TESTS_EXECUTED, str(output["summary"]))

    def test_a_not_applicable_gate_is_named_in_the_summary_even_when_allowed(
        self,
    ) -> None:
        outcome = aggregate(
            parse_results(
                report(
                    ("unit", "executed_passed", ""),
                    ("e2e", "not_applicable", "no UI path"),
                )
            )
        )
        self.assertIn("e2e", outcome.headline)
        self.assertIn("unproven", outcome.headline)
        self.assertIn("e2e", render(outcome))

    # ── a verdict has to state its reason ─────────────────────────────────

    def test_not_applicable_without_a_reason_is_refused(self) -> None:
        """A gate that did not run is making a claim a reader cannot
        reconstruct without being told why."""
        with self.assertRaises(GateResultError):
            parse_results(report(("e2e", "not_applicable", "")))

    def test_incomplete_without_a_reason_is_refused(self) -> None:
        with self.assertRaises(GateResultError):
            parse_results(report(("postgres", "incomplete", "  ")))

    def test_executed_passed_needs_no_reason(self) -> None:
        """The asymmetry is deliberate: a gate that passed has its evidence in
        its own logs."""
        self.assertEqual(len(parse_results(report(("unit", "executed_passed", "")))), 1)

    def test_a_verdict_outside_the_vocabulary_is_refused(self) -> None:
        with self.assertRaises(GateResultError) as caught:
            parse_results(report(("unit", "success", "")))
        self.assertIn("must be one of", str(caught.exception))

    def test_an_empty_report_is_refused_rather_than_allowed(self) -> None:
        """A run that reported no verdict has established nothing. Answering
        `allowed` for it is the fourteen-greens defect with the filter removed
        entirely."""
        with self.assertRaises(GateResultError):
            parse_results([])

    def test_a_duplicate_gate_id_is_refused(self) -> None:
        with self.assertRaises(GateResultError):
            parse_results(
                report(("unit", "executed_passed", ""), ("unit", "incomplete", "x"))
            )

    # ── the fallback, and its stated tradeoff ─────────────────────────────

    def test_the_fallback_message_is_unambiguous_for_incomplete(self) -> None:
        """A required job that fails for `incomplete`. The red colour is
        unavoidable and accepted: a wrong colour with an unambiguous message is
        strictly better than a right colour that lies."""
        outcome = aggregate(
            parse_results(report(("postgres", "incomplete", "cancelled")))
        )
        message = admission_message(outcome)
        self.assertIn("INCOMPLETE — NO TEST VERDICT", message)
        self.assertIn("postgres", message)

    def test_the_fallback_message_still_surfaces_a_permitted_skip(self) -> None:
        outcome = aggregate(
            parse_results(report(("e2e", "not_applicable", "no UI path")))
        )
        self.assertIn(NO_TESTS_EXECUTED, admission_message(outcome))

    # ── the CLI, which is what a workflow actually calls ──────────────────

    def _run(self, entries: object) -> int:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gates.json"
            path.write_text(json.dumps(entries), encoding="utf-8")
            return main(["aggregate", "--results", str(path)])

    def test_the_cli_exits_zero_when_everything_executed_and_passed(self) -> None:
        self.assertEqual(self._run(report(("unit", "executed_passed", ""))), 0)

    def test_the_cli_exits_one_for_an_executed_failure(self) -> None:
        self.assertEqual(self._run(report(("unit", "executed_failed", "boom"))), 1)

    def test_the_cli_exits_two_for_incomplete(self) -> None:
        """Distinct from 1, because the two ways of being blocked are
        different. A caller that only checks non-zero still blocks."""
        self.assertEqual(self._run(report(("pg", "incomplete", "cancelled"))), 2)

    def test_the_cli_exits_zero_for_a_permitted_skip(self) -> None:
        self.assertEqual(self._run(report(("e2e", "not_applicable", "no UI"))), 0)

    def test_an_unreadable_report_is_incomplete_not_a_failure(self) -> None:
        """Fails closed, and says which kind of closed. A report that cannot be
        parsed has established nothing, which is `incomplete` rather than a
        failure of whatever the gates were about."""
        self.assertEqual(self._run({"not": "an array"}), 2)

    def test_a_missing_report_file_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "absent.json"
            self.assertEqual(main(["aggregate", "--results", str(missing)]), 2)
            with self.assertRaises(GateResultError):
                load_results(missing)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
