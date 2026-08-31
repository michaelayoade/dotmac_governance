# 0032. A descriptor is never derived from a running system

- Status: Accepted
- Date: 2026-08-31
- Effective: 2026-08-31
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Governance-enrolled Dotmac repositories, and every deployment whose persistent state is authorised by a checked-in descriptor
- Classification: Internal

## Context

### The measured instance

`dotmac_platform_control_plane` (Platform CP), read at `main`
`d9b30ee4a501ce5b59e28c9d9965bcc4b9e211e0`. Every claim below is derived from
repository content; where a fact could only come from observing a host, it is
marked as such and is not asserted here.

A create-only bootstrap ran on 2026-08-31. Its launcher is
`scripts/bootstrap/bootstrap_once.sh`, hand-run by the authoriser — the receipt
it writes says so in as many words: `"workflow_revision": "hand-run by the
authorizer; no workflow performed this bootstrap"`. It created schema
`mod_deploy`, applied migrations, and landed ADR-0011 § 4's revocation of
`platform_api`'s DELETE on `public.licence_delivery_targets`.

**It updated no declaration.** The descriptor it bound is a fixed literal in the
launcher (`:48`):

```bash
DESCRIPTOR_SHA256="sha256:99eef0cc82bc73065c17c543e7a3d8824e825d3c97da22bd4e73f648e0b2daeb"
```

`e8d5b543b410ff4a1e26767c05cbbc20edb08d5e` is a real commit in that repository —
*Discharge the a77 to a98 migration gate on restored production state* (#88),
2026-08-31T05:12+01:00 — and it is the bootstrap's **source** revision.

### What the receipt binds, stated precisely

The receipt is written to the host at
`/opt/dotmac/vendor-control-plane/BOOTSTRAP_RECEIPT.json` and is not a checked-in
artefact, so its bytes and its own digest are outside what this record may
assert. Its **schema is** repository-derivable, from the heredoc at
`scripts/bootstrap/bootstrap_once.sh:165-187`, and that is what matters.

`PlatformCpBootstrapReceipt.v1` carries exactly **one** descriptor field —
`product_descriptor_sha256`, set from the literal above. **There is no field
naming a promoted descriptor.**

A correction worth making, because the looser version of this claim is wrong and
would be caught: **the receipt is not silent about everything downstream.** It
records `migration_heads`, and it records `pre_bootstrap_revision`. What it lacks
is a *promoted declaration*. So the precise defect is not "the receipt says
nothing about the end state" — it is that **every descriptor coordinate in the
receipt points backwards.** The receipt records where the operation came from,
and no artefact anywhere was updated to say where it left things.

That is the crux, and it generalises: **a receipt binding only its starting
descriptor cannot answer "what should this system look like now?"** — which is
the one question a receipt exists to answer.

### The declaration that was already right, and still went stale

This is the part that makes the record necessary rather than obvious, and it cuts
against the easy reading.

`deploy/product.toml`'s header (`:18-52`) does not overlook atomicity. It states
it, at length, in both directions:

> So the deployment carries BOTH deltas ATOMICALLY — the migrations that create
> `mod_deploy` and apply `v017`'s revocation, and the two declarations above that
> describe them, in one change. Not a follow-up. Atomicity is what removes the
> window in which the database and its declaration disagree; a descriptor update
> scheduled "right after" the deploy is that window with a promise attached.

It then names the reverse failure — a descriptor advancing while a migration
rolls back — and requires the deploy to revert the lines if the migration does
not commit.

**So the rule was written down, in the very file that went stale.** What defeated
it was scope: every sentence above is about *"the pending deploy"*, and a
create-only bootstrap was not that deploy. The operation that realised the hazard
was the one the documentation was not pointed at.

The same header calls the two missing declarations
`ABSENCES OF FACT, not oversights` (`:29`) — correct when written, and the
sentence immediately following anticipates exactly what happened:

> Equally: leaving them absent AFTER the deploy breaks the first post-deploy
> recovery run, and it will read as a recovery defect rather than a stale
> declaration.

### The disagreement, as the repository records it

The accepted descriptor (`deploy/product.toml:208-218`) declares
`expected_schemas` as **`public` plus five module schemas** — `mod_agreements`,
`mod_approvals`, `mod_ealloc`, `mod_licensing`, `mod_rel` — with a comment
stating `mod_deploy` is absent. Its header records production at `v016` with
`v017`, `v018` and `dc_0001` unapplied, and no invariant denying `platform_api`
DELETE on `public.licence_delivery_targets`.

Platform CP's own ADR-0017, *Declarations, inventory, and knowing which
artifact validated them*, states the resulting position in that repository's
words. **That record is `Proposed`, is dated 2026-08-31, and is the product's
RESPONSE to this incident rather than a prior rule the bootstrap broke** — a
distinction worth keeping, because "there was already a rule and it was ignored"
is a different and less useful finding than "the rule was scoped to the
operations that look like deployments". Under `AGENTS.md` a `Proposed` record is
a draft and is cited here as evidence of the measurement, never as policy. Its
§ 2 reads: the descriptor "currently describes a deployment that exists — pre-bootstrap image `sha256:45715e42…`, revision `af9fcf6d…` — while a
bootstrap receipt on the same host records that `mod_deploy` was created and six
migration heads applied."

**A live measurement of `vendor-cp-prod` is reported to show seven schemas, six
heads and the seal applied.** Under ADR 0013 § 1 that is a `deployment_run`-shaped
fact this repository may not assert, and it is recorded here as a reported
observation rather than adopted. The rule does not depend on it: the divergence
is already established by the two checked-in artefacts above.

### Why it survived: nothing compared the two

Nothing compared the accepted descriptor to the live database. The divergence
surfaced because a relayed claim happened to be checked, which is not a control.

### The family this completes: state reachable by omission

Four records now describe one shape, and naming it is worth more than any of them
separately.

| Record | The omission | What arrived because of it |
| --- | --- | --- |
| [0028](0028-a-deployment-verifies-only-what-it-can-repair-or-prove-provisioned.md) | an environment variable nobody set | a repair half silently removed, and a verification nothing could satisfy |
| [0029](0029-a-production-accepted-profile-never-publishes-a-simulation.md) | a surface nobody withheld | a production host publishing fabricated results in the real shapes |
| [0030](0030-a-frameworks-default-on-surface-is-a-decision-nobody-made.md) | a framework parameter nobody passed | every assembly publishing its complete API documentation |
| this record | a declaration nobody promoted | a live system diverging from the descriptor that authorises it |

In every case the permissive or stale condition **arrived because nobody declared
anything**, and in every case **nothing compared the declaration to reality.**
Neither half is one team's accident: an omission produces no diff, no review
comment and no test failure, and a comparison that does not exist produces no
output to notice.

So each of these records carries a *declaration* requirement AND a *comparison*
requirement, and the comparison is always the half that survives longest. A
missing declaration is at least visible to someone who goes looking. A missing
comparison is invisible even to them, because the thing it would report is the
thing nobody knows to look for.

This record is also the mirror of [ADR 0026](0026-a-running-object-states-its-identity.md),
one level up. There a controller must never INFER a running object's identity
from what it can see; here a declaration must never be DERIVED from what the
system turned out to contain. Both forbid reading authority off the artefact that
authority is supposed to govern.

### Authority status

Michael Ayoade ratified the rule below on 2026-08-31, with the same ordering as
ADRs 0028-0031: the ruling lands here before the corresponding Knowledge entry is
promoted. The approval is his; § "Acceptance — 2026-08-31" records it as an
attributable event and is transcribed, not made, by the drafting agent.

## Decision

### 1. The standard

> A descriptor is never derived from a running system. An operation that
> advances a deployment's persistent state carries a candidate descriptor and
> promotes it atomically on success, or refuses to run — and its receipt binds
> both the descriptor it started from and the one it promoted. If an accepted
> descriptor and its live system disagree, either the deployment was
> unauthorised or a promotion failed; the repair records which.

Four parts. They fail separately and the last one is why the first three stayed
invisible.

### 2. Direction — the descriptor is the authority, never the transcript

An accepted descriptor is **not** edited to match what a running system turned
out to contain.

The edit is always available and always looks like tidying: the declaration is
wrong, the system is right there, and reconciling them takes a minute. What it
actually does is invert the relationship. **Once a descriptor is written from
the system, the system is the authority and the descriptor is a transcript of
it** — and from that moment **drift and correction are indistinguishable**,
because both arrive as the same commit, with the same diff, for the same stated
reason.

A descriptor that disagrees with its system is repaired by promoting a
**candidate through the mechanism**, which produces a receipt. It is never
repaired by an edit that produces only a diff.

### 3. Atomicity, and the operation class that is actually bound

An operation that advances a deployment's persistent state **carries a candidate
descriptor and promotes it atomically on success, or refuses to run.**

The binding is on **any operation that advances persistent state** — not on
operations that look like deployments. That distinction is the whole content of
this section, because the measured instance is precisely the operation nobody
classified as a deployment: it created a schema, applied migrations and changed
a privilege, and it felt too small to need a declaration.

"Too small to need a declaration" is not a property of an operation. It is a
property of how the operation was described.

### 4. A receipt binds BOTH descriptors

A receipt names the descriptor the operation **started from** and the descriptor
it **promoted**.

One binding is ambiguous between *"this is what I found"* and *"this is what I
made"*, and the two have opposite consequences for every later reader. A receipt
carrying only its starting state cannot answer **"what should this system look
like now?"** — which is the one question a receipt exists to answer.

### 5. Disagreement has exactly two causes, and the repair says which

If an accepted descriptor and its live system disagree, then either

- the deployment was **unauthorised** — something advanced state without a
  promotion; or
- a **promotion failed** — the operation was authorised and its declaration did
  not land.

There is no third reading, and in particular *"the descriptor was just out of
date"* is not one: being out of date is the consequence, not the cause. The
repair **records which of the two it was**. A repair that silently reconciles
the two has destroyed the only evidence distinguishing an unauthorised change
from a broken mechanism.

### 6. The comparison, in BOTH directions

A deployment's accepted descriptor is compared against its live system, and the
comparison reports both:

- **declared-but-absent** — the descriptor names something the system does not
  have;
- **present-but-undeclared** — the system has something the descriptor does not
  name.

**The second direction is the one that catches this class**, and it is the one a
naive implementation omits. A checker written to answer "did everything I asked
for arrive?" is satisfied by a system that also contains things nobody asked
for — and an operation that adds schemas, heads and privileges without
declaring them is invisible to it by construction.

### 7. What this record does not do

- It does not forbid measuring a running system. Measurement is how the
  comparison in § 6 works. What it forbids is **writing the measurement into the
  accepted descriptor** as though it were a decision.
- It does not require every operation to be a full deployment. A create-only
  operation stays create-only; it acquires a candidate descriptor and a
  promotion, not a redeployment.
- It does not define the receipt envelope. In particular the receipt in § 4 is a
  **deployment** receipt and is not this repository's authority-cutover receipt,
  whose envelope ([ADR 0019](0019-the-authority-cutover-receipt-registry-is-a-reviewed-append-only-directory.md),
  `Proposed`) is closed and scoped to authority movement and carries no
  descriptor field.
- It does not reconcile Platform CP's descriptor. That is done in that repository
  as a candidate promoted through the mechanism — which is § 2 — and doing it
  from here as an edit would be the exact inversion this record forbids.
- It creates no check and no CI gate. See § Drift prevention.

## Consequences

- Every operation that touches persistent state now needs an answer to "which
  descriptor does this promote?", including the small ones. Some will turn out to
  have no answer, which is the record functioning.
- A class of operation currently described as maintenance — a backfill, a grant
  change, a one-off schema create — is brought inside the promotion mechanism.
  That is a real cost and it is the intended one: the measured instance was
  exactly such an operation.
- Receipts gain a field, and existing receipts become identifiable as
  single-binding. `PlatformCpBootstrapReceipt.v1` is versioned, so the successor
  is `v2` rather than a reinterpretation of stored receipts.
- The two-direction comparison will report present-but-undeclared findings across
  the fleet on first run. Those are not new defects; they are existing ones
  becoming visible, and treating the first run's output as a regression would be
  the wrong reading.
- **A descriptor that disagrees with its system can no longer be quietly
  corrected.** Someone must decide, and record, whether it was an unauthorised
  change or a failed promotion. That is slower and it is the point: the choice
  was previously made by whoever wrote the reconciling commit, silently.
- Enrolled repositories acquire no new failing check from this record.
## Drift prevention

**Enforcement status: none yet**, and unusually there is a *named external
obstacle* rather than only an undecided design.

Re-confirmed at this repository's `main` `78ca303` rather than carried over from
ADRs 0028-0031: `standards_control._governance` resolves exactly the one path
each enrolled profile declares as `governance_model.source` and reads a single
`- Status:` line from it; nothing in `standards_control`, `gate_control`,
`agent_control`, `programme_control` or `.github/workflows/` reads the ADR
directory except `tools/check_adrs.py` and `tools/check_adr_references.py`, both
of which run in this repository's own CI. All seven enrolled profiles pin
`docs/adr/0006-cross-repository-engineering-conformance.md`, expecting status
`accepted`. **Adding this record turns no gate red in any enrolled repository.**

**The obstacle, stated rather than implied.** The type that would express a
declared database state is reported to be `DatabaseContract` in
`dotmac-deployment-foundation` `0.3.0a2`. That repository is not checked out
here and the package is not installed, so **the type's name and contents are not
verified by this record** and are attributed rather than asserted. What IS
verified, from Platform CP `docs/adr/0017-…:131`, is the hold and its reason:

> `0.3.0a2` is held: publishing before rehearsal would recreate the deadlock the
> candidate lane exists to break.

and that the resulting pin is dated — that record's § 6 states the bound
artifact **expires 2026-11-28**, making the arrangement "a dated obligation, not
a permanent arrangement".
That hold is not incidental to this record: it is the same hold that already
forced Platform CP's conformance gate into a dated gap. So the honest position is
that this rule can be **ratified and specified now and enforced when 0.3
publishes**, and that any enforcement claim before then would be describing a
control whose vocabulary does not exist.

This is worth distinguishing from the rest of the wave. ADRs 0028-0030 are
unenforced because the decidable form needs a receipt chain that has not been
built. This record is unenforced because a specific artefact is **held on
purpose** by a decision already taken elsewhere. The first is work not yet done;
the second is a dependency with an owner and a release.

What would be **decidable once that vocabulary exists**, stated in advance so a
future family cannot be built without its known-bad cases:

- an operation that writes persistent state and names no candidate descriptor —
  the § 3 shape, and the one the measured instance would have failed;
- a receipt schema carrying exactly one descriptor field, which is § 4 violated
  in a way visible in the type rather than in a run;
- a descriptor edit that is not the promotion half of a receipt — the § 2
  inversion, detectable as a change to the accepted descriptor in a commit that
  produces no receipt;
- a comparison implementation that reports only declared-but-absent, which is
  § 6 with the half that matters removed.

**Not decidable, and outside what this repository may assert** under ADR 0013
§ 1: what a host actually contains. The comparison in § 6 necessarily runs where
the database is, and its verdict is a `deployment_run`-shaped claim that no
machine-readable contract declares an oracle for (open decision 17, unchanged).
This record therefore governs what a deployment DECLARES and what its receipt
BINDS — both derivable from checked-in artefacts — and leaves the verdict itself
to the owning product's evidence.

**Non-vacuity, stated in advance.** Any future family must be shown RED on an
operation that advances state while naming no candidate, and RED on a
single-binding receipt schema — and it must be shown to report a
**present-but-undeclared** finding, not merely a declared-but-absent one. A
comparison demonstrated only against a missing object has not been shown to
catch this class at all: the measured instance is entirely
present-but-undeclared, so a checker exercised only in the other direction would
have passed it. That is the sensitivity case, and a family that cannot produce it
is not implementing this record.

Whether any of this is built, and by whom, is open decision 40. Acceptance of
this record does not make that decision and does not create the family described:
a standard being normative is not evidence that a control enforces it.

## Acceptance — 2026-08-31

Michael Ayoade approved this record on 2026-08-31. Under `AGENTS.md` an agent may
not occupy the approver role or approve its own output; neither happened here.
The standard in § 1 and the three properties in §§ 2-4 are his, transcribed; § 5
and § 6 state the consequences he directed, including that the second comparison
direction is the one that catches this class.

Acceptance covers the standard. It does not build a control, does not set a date
against the Foundation `0.3` publication that gates one, does not reconcile
Platform CP's descriptor — that is done in that repository as a candidate
promoted through the mechanism — and does not extend this repository's `Amends:`
relationship to Platform CP ADR-0011, ADR-0013 or ADR-0017, which are cited in
prose because that field is scoped to this repository's own ADR directory.
