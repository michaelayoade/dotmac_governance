"""The four gate verdicts, and the aggregator that must honour them.

A gate's colour has to mean what its name says. Three failures on 2026-08-29
were all the same defect wearing three colours:

1. **A green E2E Gate that ran no browser.** Its relevance filter
   short-circuits to success for a pull request touching no UI path. ALL
   FOURTEEN green E2E Gate runs that day skipped Playwright, and every run that
   executed it failed. A live production defect rode through a full day of
   merges on those greens.
2. **A red E2E Gate caused by a calendar.** A `billing_day` seeded as today's
   day-of-month went out of domain on the 29th, and the browser refused to
   submit a form containing a hidden invalid control. Red, and not a code
   regression.
3. **A red PostgreSQL Gate caused by a cancellation.** The log said exactly
   `INTEGRATION_RESULT: cancelled`. No PostgreSQL test failed — one shard was
   cancelled when the pull request closed mid-flight, and the aggregator
   treated "not success" as failure. The page read "PostgreSQL Gate failed" for
   a job never allowed to finish.

The shared cause: **a conditional that removes work is indistinguishable from
work that succeeded, unless something asserts the work happened.** That is the
same defect as a secret-conditioned `if:` in a publisher, and it is why this
vocabulary is Governance-owned rather than defined per product.

## The four verdicts

============================ ==================================================
``executed_passed``          the work ran and the property held
``executed_failed``          the work ran and the property did not hold
``not_applicable``           the work did not run, for a stated reason, and
                             nothing about the property is claimed
``incomplete``               the work was cancelled, timed out, was blocked or
                             never reported
============================ ==================================================

Two rules do the load-bearing work, and they pull in opposite directions:

**``incomplete`` BLOCKS a merge.** It is not green. A gate nobody let finish has
established nothing, and merging past it is merging past the gate.

**``incomplete`` is NEVER reported as a test failure.** It is not red either.
Instance 3 sent a reader hunting a PostgreSQL defect that did not exist. A
verdict that misnames the problem costs the same time as no verdict at all.

**``not_applicable`` is reported where a reader will see it.** Not as green.
Instance 1 was fourteen greens that meant "did not run", and the only thing
that would have caught it is a summary that says so in the place the reader is
already looking.
"""

from __future__ import annotations

from .contracts import (
    NO_TESTS_EXECUTED,
    AggregateOutcome,
    CheckConclusion,
    GateResult,
    GateVerdict,
    MergeDecision,
)
from .engine import (
    admission_message,
    aggregate,
    check_run,
    exit_code,
    load_results,
    parse_results,
    render,
)

__all__ = [
    "NO_TESTS_EXECUTED",
    "AggregateOutcome",
    "CheckConclusion",
    "GateResult",
    "GateVerdict",
    "MergeDecision",
    "admission_message",
    "aggregate",
    "check_run",
    "exit_code",
    "load_results",
    "parse_results",
    "render",
]
