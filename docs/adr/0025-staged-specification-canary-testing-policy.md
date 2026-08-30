# 0025. Strict-xfail plus an absence ratchet is valid only for a staged specification

- Status: Proposed
- Date: 2026-08-16
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories, for any test merged ahead of the thing it specifies
- Classification: Internal

## Context

**Provenance.** This record was drafted on 2026-08-16 and opened as pull
request #18 under the number 0013. It never merged. ADR 0013 was taken in the
meantime by the repository-local-claims-and-external-oracles standard, which is
`Accepted`, effective 2026-08-22, and already load-bearing for open decisions 17
and 18; under `docs/adr/README.md` the record that merges first keeps the
number, so this one renumbers. The decision text is carried over unchanged,
because a census against every `Accepted` record found nothing on `main` that
supersedes any part of it — `xfail` appears in no merged governance record, and
the five `canary` mentions on `main` are unrelated. Pull request #18 is closed
in favour of this one.

**Its observations are as-of 2026-08-16.** ADR 0013 § 4, now `Accepted`, governs
exactly this: every product citation below — file, line, revision and merge
commit — is an observation of another repository on the date given, not a claim
about its current state, and must be re-read against that repository's canonical
branch before it is relied on.

Dotmac routinely writes a test before the persistence, module or migration it
describes exists — a specification that happens to be executable. Parallel work
streams make this valuable: a team can freeze a contract in the suite while the
team that owns the dependency is still building it.

It is also the easiest way to put a permanently green, permanently meaningless
test into a repository. A bare `xfail` says only "this is allowed to fail". A
test that is allowed to fail, for any reason, forever, is not a specification;
it is a comment with a test runner attached. Two further failure modes sit
behind it:

- **The markers are forgotten.** The dependency lands, the canary would now
  pass, and nothing goes red to say so. The suite keeps reporting a block that
  no longer exists, and the specification is never actually verified.
- **The canary never reaches its own assertion.** `raises=<exact type>`
  constrains *what* was raised, not *where*. A canary can satisfy strict-xfail
  for its entire staged life while failing during setup, because setup happened
  to raise the expected type first. Nothing about the green run distinguishes
  the two.

The second is not hypothetical. In `dotmac-integration` PR #190 a receipt
canary sat behind `xfail(strict=True, raises=ProgrammingError)` for missing
columns. When the columns landed and the marker came off, it failed with
`InvalidRequestError`: the canary rolled its transaction back and then read the
row, which autobegan a new transaction, so the following explicit `begin()`
collided. That defect had been in the canary from the day it was written, and
no amount of green could have surfaced it.

`dotmac_starter_mt` ADR 0018 already established the fleet exemption rule this
depends on — a different repository's numbering, and not this repository's ADR
0018, which is the authority-cutover receipt registry:
an exemption states an enforceable premise, ratchets in both directions, keeps
"grandfathered" distinct from "reviewed and correct", and carries a sensitivity
proof. Michael approved the testing-specific standard below on 2026-08-15 and
recommended it be recorded as engineering-governance testing policy.

This record is `Proposed`. Nothing below is normative until a named human
approves it through the recorded process.

## Decision

A canary may be merged **red**, ahead of the thing it specifies, only as a
**staged specification**, and only with all three parts present together:

1. **`xfail(strict=True, raises=<exact blocker>)`.** `strict` means it must
   fail: a canary that starts passing without its dependency is an error, not a
   bonus. Naming the exact exception means it must fail *because of the
   blocker* — a typo, a bad fixture or a broken predicate raises something else
   and the suite goes red.
2. **An unmarked proof that the dependency is still absent.** Unmarked is
   load-bearing. It is the half that goes red the moment the block lifts, so
   the markers cannot be forgotten. This is `dotmac_starter_mt` ADR 0018's
   two-directional ratchet applied to staging.
3. **A harness-reachability / sensitivity proof.** The detector must be shown
   to bite, and the harness must be shown to run.

Michael's qualification, verbatim:

> Green means "the specification remains consistently blocked", never "the
> runtime works". The xfail and absence ratchet must disappear before
> publication or cutover. The expected failure must reach the intended blocker,
> not fail during test setup — as the transaction-autobegin defect
> demonstrated.

Four obligations follow from it, and none of them is optional:

**A green staged specification is not acceptance evidence.** It reports one
fact: the specification is still consistently blocked. It may never be cited as
evidence that the described behaviour works, in a pull request, a release note,
a readiness assessment, or a Knowledge entry.

**The markers are temporary by construction.** Both the `xfail` and the absence
ratchet must be gone before publication or cutover. A staged specification that
survives its own dependency is the failure this record exists to prevent.

**Reaching the blocker is a separate obligation from raising the right type.**
The exact-type constraint is necessary and not sufficient. Where a canary's
setup can plausibly raise the same class as its subject, the staged
specification needs an independent demonstration that the harness executes —
for example the identical harness pointed at a table that already exists.

**On lifting, invert the ratchet rather than delete it.** It asserted the
dependency was absent so the block could not be forgotten; it should then
assert the dependency is present, so a later migration cannot silently remove
it. Same guard, opposite polarity, no coverage lost.

Practical consequence for the change that lifts a block: treat every unblocked
canary as **unverified code**. Read its failures as possible harness defects
before reading them as findings about the implementation.

## Consequences

- A test merged red without all three parts is not a staged specification. It
  is an unmonitored region, and it should be described that way rather than
  counted as coverage.
- Reviewers of a staging change acquire a specific checklist: exact blocker
  named, unmarked absence proof present, harness proven to run, and a stated
  removal condition. Reviewers of the *lifting* change acquire a different one:
  markers gone, ratchet inverted rather than deleted, and every newly-running
  canary read as unverified.
- Prose is not part of the mechanism. Comments and docstrings describing a
  block routinely survive its removal — the reference implementation below
  still carries one such stale line — which is precisely why the ratchet is an
  unmarked executing test rather than a note.
- This record makes no claim about any repository's current conformance, and
  approving it does not make one.
- Nothing here changes the `standards_control` profile, its schema version, or
  any enforcement mode. No product repin is required or implied.
- `policies/` remains empty. This record is a decision with a status, not a
  normative policy document; whether a policy is later derived from it is a
  separate act under the lifecycle in `policies/README.md`.

## Drift prevention

The reference implementation is `dotmac_starter_mt`
`tests/test_integration_receipt_delivery_isolation.py`, staged and then lifted
across PR #190 (squash-merged as `b0956c8ea12da066b99eaf0623b5c1bdd544bc26`,
2026-08-15). All three parts and the lifting discipline are visible in it:

- **The marker.** `_BLOCKED = pytest.mark.xfail(strict=True,
  raises=ProgrammingError, reason=...)` guarded roughly thirteen canaries while
  the receipt-state columns were owned by another work stream. It is **not in
  the file today** — it was removed in PR #190 commit
  `442121b1624dcc7643f46d69b646c19ebae8362c` when the columns landed, which is
  the standard working rather than the standard being skipped. Because the pull
  request was squash-merged, that commit is reachable from the pull request
  rather than from `main`'s history. The module docstring records the shape:
  *"merged red — `xfail(strict=True, raises=ProgrammingError)`, a much narrower
  claim than 'allowed to fail': they had to fail, and to fail because the
  column was missing."*
- **The absence ratchet, inverted on lifting.**
  `test_every_column_the_engine_claims_against_exists` (line 167) is the same
  guard the staging carried, with its polarity reversed: it asserted
  `REQUIRED_COLUMNS` were absent so the block could not be forgotten, and now
  asserts they are present so a migration cannot silently remove one. It
  carries its own non-vacuity guard, so a lineage that was never applied fails
  for the right reason instead of passing on an empty set.
- **The harness-reachability proof.** `test_the_race_harness_actually_races`
  (line 250) points the identical concurrency harness at a table that already
  exists, so the harness is shown to execute independently of the staged
  subject.
- **The sensitivity proofs.**
  `test_the_claim_without_its_lease_predicate_lets_both_workers_win` (line 396)
  and `test_settlement_without_its_identity_guard_lets_the_stale_worker_win`
  (line 642) each remove the guard and observe the specific forbidden outcome.
- **The known limit, in the same file.** The harness-reachability test's own
  docstring states honestly that its outcome is correct whether the two
  statements genuinely collide or merely run in turn. The file also still
  carries a stale line asserting that "the receipt race below is blocked" when
  nothing is blocked any more — a live instance of the prose-survives-the-lift
  drift this record names, and the reason the ratchet may not be a comment.

Fleet-wide detection does not exist. The three parts are structurally
detectable in principle — an `xfail` whose arguments lack `strict=True` or
`raises=`, or a marked module carrying no unmarked test — and under ADR 0006
the mechanism would be a rule family in the `standards_control` engine with
stable diagnostics and its own sabotage proofs, carried by a schema-version
increment that each product adopts on its own repin. The third part, harness
reachability, is a review judgement that a syntax engine should not claim to
discover.

That work is deliberately not part of this record: `required` mode is
representable only with an `Accepted` checked-in governance source, so building
enforcement for a `Proposed` standard would activate policy without approval.
Whether the detectable parts become an engine rule family, and whether the
undetectable part stays a named review obligation, is recorded as an open
decision. Until it is answered, drift detection for this standard is that
review obligation plus the product-local guards above — a weaker mechanism than
an executable fleet rule, and recorded as weaker rather than overclaimed.
