# 0015. A gate reports one of four verdicts

- Status: Proposed
- Date: 2026-08-29
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and every enrolled Dotmac repository
- Classification: Internal

## Context

Three gate failures on 2026-08-29, three different colours, one defect.

**A green E2E Gate that ran no browser.** Its relevance filter short-circuits to
success for a pull request touching no UI path. **All fourteen** green E2E Gate
runs that day skipped Playwright, and every run that executed it failed. A live
production defect rode through a full day of merges on those greens.

**A red E2E Gate caused by a calendar.** A `billing_day` seeded as today's
day-of-month went out of domain on the 29th, and the browser refused to submit
a form containing a hidden invalid control. Red, and not a code regression.

**A red PostgreSQL Gate caused by a cancellation.** Its log said exactly
`INTEGRATION_RESULT: cancelled`. No PostgreSQL test failed — one shard was
cancelled when the pull request closed mid-flight, and the aggregator treated
"not success" as failure. The page read "PostgreSQL Gate failed" for a job
never allowed to finish.

The shared cause is one sentence: **a conditional that removes work is
indistinguishable from work that succeeded, unless something asserts the work
happened.** That is the same defect as a secret-conditioned `if:` in a publisher
pipeline, and it is why the vocabulary belongs here rather than being defined
once per product.

There is a second, sharper reason it cannot be left to products. **A shell
job's exit code cannot express the distinction.** GitHub treats `success`,
`skipped` and `neutral` alike as satisfying a required status check, and a
conditionally skipped job reports `success`.[^1] A gate implemented as a script
therefore has two states available to it, and needs four.

[^1]: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks

## Decision

### 1. The four verdicts

Every gate reports exactly one:

| Verdict | Meaning |
| --- | --- |
| `executed_passed` | the work ran and the property held |
| `executed_failed` | the work ran and the property did not hold |
| `not_applicable` | the work did not run, for a stated reason, and nothing about the property is claimed |
| `incomplete` | the work was cancelled, timed out, was blocked, or never reported |

Two rules do the load-bearing work, and they pull in opposite directions:

- **`incomplete` BLOCKS a merge.** It is not green. A gate nobody let finish
  has established nothing, and merging past it is merging past the gate.
- **`incomplete` is NEVER described as a test failure.** It is not red either.
  Instance 3 sent a reader hunting a PostgreSQL defect that did not exist, and
  a verdict that misnames the problem costs the same time as no verdict.

### 2. The mapping onto check conclusions

| Verdict | Conclusion | Satisfies a required check? |
| --- | --- | --- |
| `executed_passed` | `success` | yes |
| `executed_failed` | `failure` | no |
| `not_applicable` | `neutral`, with visible `NO TESTS EXECUTED` evidence | **yes, by design** |
| `incomplete` | `action_required` (or `cancelled` / `timed_out`) | no |

`not_applicable` permitting a merge is correct: a gate that genuinely does not
apply must not block. That is precisely why the **`NO TESTS EXECUTED` evidence
is the only thing standing between a legitimate skip and an invisible one**, and
why § 4 makes it a tested property rather than a log line.

### 3. Publication, and the honest fallback

Reaching `neutral` and `action_required` deliberately requires publishing a
check run through the Checks API,[^2] not returning an exit code.

[^2]: https://docs.github.com/en/rest/guides/using-the-rest-api-to-interact-with-checks

Where that is unavailable, the accepted fallback is a **required admission job
that FAILS for `incomplete` and says `INCOMPLETE — NO TEST VERDICT`.** The red
colour is then unavoidable.

That tradeoff is recorded here rather than chosen silently: **a wrong colour
with an unambiguous message is strictly better than a right colour that lies.**
The fallback reintroduces exactly one of instance 3's two problems — the
misleading colour — while removing the other, which was that nobody could tell
a cancellation from a defect. Adopters using the fallback are choosing that
trade knowingly.

### 4. The aggregator

An aggregator **distinguishes** the four verdicts. It may not collapse "not
success" into failure: instance 3 was purely that collapse, and it is one line
of code (`success if all(r == "success")`).

Concretely: each verdict keeps its own bucket all the way to the caller, so a
renderer that wants to write the word "failed" has to look at the failed bucket
and find something in it. Exit codes are distinct — `0` allowed, `1` something
executed and failed, `2` blocked with nothing failed — so a caller that only
checks non-zero still blocks, while a caller that renders a headline can tell
instance 3 from a real defect.

A gate reporting `not_applicable` is **named in the summary a reader sees**,
even when the overall decision is `allowed`. Instance 1 was fourteen greens
that meant "did not run", and a summary that omits the unproven gates
reproduces it exactly.

### 5. Every verdict except `executed_passed` states its reason

The asymmetry is deliberate. A gate that passed has its evidence in its own
logs. A gate that did not run, did not finish, or failed is making a claim a
reader cannot reconstruct without being told why, and an unstated reason is how
instance 1 survived fourteen times.

A report with **no verdicts at all** is refused rather than treated as allowed.
A run that reported nothing has established nothing, and answering `allowed`
for it is the fourteen-greens defect with the filter removed entirely.

### 6. Before fleet adoption: rehearse the real protection, in both directions

Against actual branch protection, not against the enum:

1. `not_applicable` **permits** merging;
2. `incomplete` **blocks** merging;
3. neither is **displayed as an executed test result**.

The third is the one that fails silently if only the first two are tested, and
it is the assertion that catches a `neutral` whose evidence never reached the
summary.

## Consequences

- Products inherit the vocabulary; they do not each define one. A per-product
  enum would let a gate keep the two states an exit code offers and rename
  them.
- Every gate that today short-circuits to success must be changed to report
  `not_applicable` instead, which will make previously invisible skips visible
  and is expected to be uncomfortable at first.
- An aggregator that reads workflow conclusions must map them into this
  vocabulary before deciding, and the mapping is lossy in one direction:
  `skipped` and `success` are indistinguishable at the workflow level, which
  is exactly why gates must report their verdict explicitly rather than having
  it inferred.
- The fallback's red colour will occasionally be wrong. That is accepted and
  recorded, not discovered later.

## Drift prevention

`gate_control` implements the vocabulary, the mapping, the aggregator and both
publication forms, with `tools/dotmac-gates` as the entry point a workflow
calls.

The proofs plant the three observed instances rather than asserting the enum:

- a **cancelled shard** yields `incomplete`, blocks the merge, produces
  `action_required`, and its headline contains "not a test failure" and does
  not contain "executed_failed";
- a **filtered-out suite** yields `not_applicable` rather than
  `executed_passed`, permits the merge, and carries `NO TESTS EXECUTED` in the
  check-run **summary and title** — with a counter-proof that an
  all-passed run does **not** carry that marker, because a marker that always
  appears carries no information;
- a real failure and a cancellation are asserted to render **differently** and
  to exit with **different codes**, which is the property instance 3 lacked.

Fails closed: an unreadable, unparseable, empty or duplicate-bearing report is
`incomplete`, never allowed and never called a failure.

**What is not automated here.** Whether a given product's gate actually reports
its verdict rather than short-circuiting is a property of that product's
workflows, which this repository does not read (ADR 0013 § 1). The
branch-protection rehearsal in § 6 is a human-run procedure and is recorded as
such rather than implied.
