# 0028. A deployment verifies only what it can repair, or prove was provisioned by its owner

- Status: Accepted
- Date: 2026-08-31
- Effective: 2026-08-31
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Governance-enrolled Dotmac repositories, and every managed deployment path that verifies a prerequisite it does not itself establish
- Classification: Internal

## Context

### The principle this record refines

This is not a new invention. It is `dotmac_starter_mt` ADR-0018, *A guard
exemption must carry an enforceable premise* — `Accepted`, fleet-wide, path
`docs/adr/0018-an-exemption-must-be-enforceable.md`, read at commit
`2080fb12a1777b53961a455fe2e99f15f18c490c`, blob
`sha256:a1269caecee339f30121690b383d86fb0f9650ef8fd1a447247295c980f08260`
(byte-identical at that repository's `origin/main`
`6197022bbdda38c568fe5434da8dcdbae498ffc6`) — applied to deployment paths.
Its decision sentence:

> An exclusion from any check states its premise, and the premise is
> machine-checkable. An exclusion whose premise cannot be checked is not an
> exemption — it is an unmonitored region, and is not permitted.

Its 2026-08-26 amendment already extended that from *regions excluded from a
guard* to *regions formally inside a guard whose check does not test the
property the guard is named for*, observing that "both produce an unmonitored
region. Only one of them looks unmonitored." This record extends it once more,
along the same axis: a **deployment step that is present, named for a repair,
and silently inert in the only environments that matter.**

ADR-0018 is cited, not restated. A governance record that re-narrates an
accepted product decision creates a second copy of it, which ADR 0006 § 5
exists to prevent.

This record does **not** amend [ADR 0014](0014-build-once-and-bind-the-environment-late.md).
ADR 0014 § 2 places "databases — schema and data are governed by migration
rules" explicitly outside its scope. The region below is the one ADR 0014
declared out of scope, which is why it needed a record of its own rather than a
stretched reading of an existing one.

### The measured incident

`dotmac_sub`, `origin/main` `5ffdb1a945b4c50b63d787579d619b12e062e6bb`. Every
path below was read at that revision.

`scripts/deploy.sh` runs two adjacent steps, in this order (`:848`, `:849`):

1. `run_database_prerequisite_bootstrap` (`:403`) — the **repair** leg. Its
   first act:

   ```bash
   bootstrap_url="${BOOTSTRAP_DATABASE_URL:-$(env_value BOOTSTRAP_DATABASE_URL)}"
   if [[ -z "${bootstrap_url}" ]]; then
     log "No BOOTSTRAP_DATABASE_URL supplied; verifying existing database prerequisites only"
     return 0
   fi
   ```

2. `verify_database_prerequisites` (`:422`) — the **verification** leg,
   `scripts/bootstrap_commercial_module_prereqs.py --verify-only` under the
   restricted migration connection, exiting `1` on any violation.

The verification is not a shallow existence check. For every entry in
`COMMERCIAL_MODULE_SCHEMA_CONTRACT` it asserts four properties
(`app/commercial_module_prereqs.py:166-195`): the schema exists; its owner is
`dotmac_app`; `PUBLIC` holds neither `USAGE` nor `CREATE`; and `USAGE` is
granted to all three of `app_admin`, `app_user` and `platform_api`. A parallel
role check asserts four roles on the exact `(rolcanlogin, rolbypassrls,
rolsuper)` triple.

**Who supplies the credential decides which half runs.** Three CI workflows
supply it against a throwaway superuser database
(`.github/workflows/ci.yml:717-761` — a `postgis/postgis:16-3.4` container as
`postgres`, torn down in the same job; likewise `e2e.yml:108` and
`e2e-gate.yml:163`), and an architecture test
(`tests/architecture/test_ci_pipeline.py:531-542`) asserts they keep doing so.
Neither `staging-deploy.yml` nor `production-deploy.yml` supplies it, and
neither host `.env` carries it — proved not by reading a template but by both
deploy logs printing the `No BOOTSTRAP_DATABASE_URL supplied` line above
(staging run `33341053232`, 2026-08-30T23:11:08Z; production run
`33276207742`, 2026-08-29T21:32:19Z).

So the provisioning path is exercised only where it cannot fail, and the
verification path only where nothing can fix a failure. **Neither half is ever
exercised in the configuration that decides whether a release ships.**

Composing one module made that structural. `tests/architecture/test_commercial_module_prerequisites.py:48-52`
requires set equality between the schema contract and the composed Alembic
lineages:

```python
def test_schema_prerequisite_manifest_matches_the_composed_lineages() -> None:
    contracted_imports = {
        item.import_name for item in COMMERCIAL_MODULE_SCHEMA_CONTRACT
    }
    assert contracted_imports == set(_declared_lineages())
```

That test is correct and is doing its job — it is what stops a composed lineage
from silently having no declared prerequisite. Its consequence, once
`20e1fb9a6` (*feat(inbox): compose dotmac-inbox*, #2819) added
`dotmac_inbox.migrations:versions` to `alembic.ini`, was to force a `mod_inbox`
contract entry that no target database satisfied and no armed path could
create. Two release candidates then failed identically:

```
==> No BOOTSTRAP_DATABASE_URL supplied; verifying existing database prerequisites only
==> Verifying commercial module prerequisites with the restricted migration connection
COMMERCIAL MODULE PREREQUISITE: schema 'mod_inbox' is missing
##[error]Process completed with exit code 1.
```

The remediation was a `workflow_dispatch` workflow added afterwards,
`.github/workflows/temporary-module-prereq-repair.yml` (#2840, merged
`e5b6a782`), which synthesizes an elevated connection on the target host and
runs the repair the managed path declined to run. Nothing in the repository
references it: it is absent from `test_ci_pipeline.py`'s workflow enumeration,
carries no expiry, and the word "temporary" appears only in its name.

### Five corrections the re-measurement produced

The account circulating before this record was drafted was checked statement by
statement against the repository and the run history. Five statements did not
survive, and they are recorded because the corrected version is the one this
decision rests on.

1. **The candidates died in STAGING, not production.** Both failures are `Deploy
   main to staging` (runs `33341053232` and `33346801026`). No production deploy
   was attempted for either revision. As an as-of observation under ADR 0013
   § 4: at 2026-08-31, production's last deploy remains `33276207742`
   (`58e986f7`, success, 2026-08-29), predating the composition; refresh owner
   Michael Ayoade. The gate stopped the pipeline before production, which is
   the gate working.
2. **The two named commits are bystanders, not causes.**
   `6ded8db083b42e951bab3754c7263a2727da07ee` extracts a `pg_dump` refusal guard;
   `43482aeb0a5a42488d435181a08ef4b3ce84d151` is an automated version bump
   authored by a different person. They are the head revisions of the two failed
   runs. The causal commit is `20e1fb9a6`.
3. **The hand-dispatched workflow is the de facto creator of STAGING state, not
   production state.** Its staging job succeeded once (`33352512378`); its
   production job has failed three times (`33352563053`, `33353640545`,
   `33357871419`) across three attempted fixes in about a hundred minutes, the
   most recent failing earlier than the first. The out-of-band repair mechanism
   is at present *less* proven than the gate it exists to unblock.
4. **The repair leg `return`s from a shell function; it does not exit.** The
   deploy continues into verification, which is what actually stops it. And the
   variable has a second source: `env_value BOOTSTRAP_DATABASE_URL` reads the
   deploy directory's `.env`, so a persistent elevated DSN placed there would
   silently convert every deploy into an auto-repairing one with no further
   gate. That the file is empty today is the entire safety property, and nothing
   enforces it.
5. **CI does not "always" supply the credential.** The step is conditional
   (`ci.yml:751-752`) and is skipped on docs-only changes and on every push to
   `main`. It is a PR-time gate, not something that runs on the merge commit
   that becomes a release candidate.

None of these weakens the finding. Corrections 1 and 3 narrow the blast radius
that was actually realised; correction 4 identifies a second, unmonitored way
into the *opposite* failure; correction 5 makes the asymmetry worse, not better.

### Authority status

Michael Ayoade ratified the rule below on 2026-08-31 and directed that it be
recorded here **before** the corresponding Knowledge entry is promoted, so that
the checked-in record is the authority and Knowledge is discovery support. The
approval is his; § "Acceptance — 2026-08-31" records it as an attributable
event and is transcribed, not made, by the drafting agent.

## Decision

### 1. The standard

> A managed deployment may not silently verify a prerequisite that its declared
> path can neither satisfy nor prove was satisfied by its named owner.

There are exactly two conforming forms. Which applies is decided by
**ownership**, and that decision is recorded — not left to whichever
environment happens to hold a credential.

### 2. Form A — the deployment owns the prerequisite

Repair and verification are **armed together in every environment**, and they
produce **one typed receipt**.

- *Armed together* is the operative half. A path carrying both steps but arming
  only one of them where it matters has not adopted this form; it has adopted
  Form A in CI and neither form in production.
- *Every environment* means the enumerated set the path actually runs in. An
  environment absent from that enumeration is not exempt, it is unmeasured.
- *One typed receipt* means a single typed result covering both halves — what
  was repaired, what was then verified, and against which target. Two exit codes
  are not a receipt: an exit code cannot distinguish work that ran and passed
  from work that did not run, which is the exact distinction this record turns
  on. Governance [ADR 0015](0015-a-gate-reports-one-of-four-verdicts.md)
  (`Proposed`, and cited as a draft rather than as policy) names that
  distinction `executed_passed` versus `not_applicable`; the repair leg above
  reports the first while meaning the second.

### 3. Form B — another system owns the prerequisite

**Verification-only is correct here, and is not the defect.** A deployment that
does not own a prerequisite must not acquire the power to repair it. That would
create a second writer for a decision with a named owner, which the fleet's
one-owner standard forbids, and flattening this rule into "always arm repair"
would force deployments to take ownership of things they should not own.

What Form B additionally requires is that the deployment **demand an immutable
provisioning receipt from that owner**, and refuse to proceed without one. The
receipt is produced by the owner, is immutable, and identifies the exact
provisioning act. A runbook sentence is not a receipt. A human's recollection is
not a receipt. Neither is the deploying system's own observation that the state
currently looks right: **verifying that a property holds says nothing about who
is accountable for it holding next time.**

This receipt is a product-local artefact between a deployment and its
prerequisite's owner. It is **not** an authority-cutover receipt and does not
enter this repository's `receipts/` registry, whose envelope
([ADR 0019](0019-the-authority-cutover-receipt-registry-is-a-reviewed-append-only-directory.md),
`Proposed`) is closed and scoped to authority movement.

### 4. An unset environment variable is not an exemption

> An unset environment variable that silently removes the repair half is never
> an exemption; it is an unmonitored deployment region.

This sentence is the enforceable core of the record and the one to cite.

A conditional that disables a step when a variable is absent does state a
premise — in the measured case, *"repair is opt-in so nobody grants
database-level `CREATE` casually"*, which `docs/runbooks/PRODUCTION_DEPLOYMENT.md:135`
states as policy and which is entirely sound as a reason. It is still not an
exemption, because nothing checks it and nothing records what the disabled half
was supposed to accomplish. The region it leaves — who provisions, when, under
what evidence — has no owner and no gate.

The diagnostic signature is three properties together, and a path exhibiting
all three is in this state whatever its steps are named:

- the repair path is exercised only where it cannot fail;
- the verification path is exercised only where nothing can fix a failure;
- neither is exercised in the configuration that decides whether a release
  ships.

Such a path is brought to Form A or Form B. Where neither has yet been done,
it is recorded as an unmonitored region — which is honest, and strictly better
than the current reading in which a green CI run is mistaken for evidence about
a gate CI structurally cannot exercise.

### 5. What this record does not do

- It does not require any deployment to acquire an elevated credential. Form B
  exists precisely so that it need not.
- It does not criticise a verification-only deployment, a strict prerequisite
  contract, or a test that forces a contract to match what is composed. All
  three were correct in the measured incident.
- It does not decide who repairs `dotmac_sub`'s path, or which form that path
  adopts. That is a decision in a repository Governance does not own, recorded
  as open decision 33.
- It creates no check, no standards-profile field and no CI gate. See
  § Drift prevention.

## Consequences

- A deployment path that verifies a prerequisite must now be able to say which
  form it is in. Some will find they are in neither, which is the record
  functioning.
- Form B makes a demand of the *owner*, not only of the deployment: an owner who
  provisions but emits no immutable receipt leaves every downstream deployment
  unable to conform. The obligation propagates upstream, and that is intended.
- Existing paths that pair a verify step with a credential-gated repair step will
  be reclassified as unmonitored regions rather than as covered. This will read
  as coverage being lost; nothing is lost, because the coverage was never there.
- The reflex fix — put the elevated DSN in the host `.env` — satisfies Form A's
  letter and defeats its purpose, because it arms an unbounded repair with no
  receipt and no gate. Correction 4 above records that this is one line away in
  the measured system today.
- A "temporary" out-of-band repair workflow with no expiry, no test and no
  reference from any inventory is itself an unmonitored region under the parent
  record. This ADR does not create an obligation to delete one, but a repository
  keeping such a workflow can no longer describe its managed path as covered.
- Enrolled repositories acquire no new failing check as a result of this record.
  Its acceptance changes what a reviewer may claim, not what any gate returns.

## Drift prevention

**Enforcement status: none, and none is proposed here.** No `standards_control`
rule evaluates this record, no `standards-profile.schema.json` field represents
a deployment prerequisite surface, and no engine diagnostic exists for it. This
is stated review discipline, which ADR 0013 § 5 permits so long as it is said
plainly rather than implied — and it is said plainly, because a decision whose
drift-prevention section describes an unbuilt control as though it were running
is the failure this repository exists to prevent.

The division is a property of the subject rather than a scheduling choice.

**Decidable from repository content**, and what a future family would have to
fail on, each stated in advance so it cannot be built without its known-bad
case:

- a deploy path in which a step reached only under a set environment variable
  returns success when that variable is unset, immediately followed by a step
  that verifies the same subject and exits non-zero — the exact adjacency at
  `scripts/deploy.sh:848-849`;
- a repair credential named in every CI workflow that exercises a database and
  in no deployment workflow or committed environment template — a presence
  asymmetry between two declared surfaces, which is a comparison rather than a
  scan;
- a declared prerequisite surface naming no prerequisite, which passes every
  content check for the wrong reason and must be a diagnostic rather than a
  skip;
- a `workflow_dispatch` workflow that writes database state on a deployment
  target and is absent from the repository's own workflow inventory.

**Not decidable, and outside what this repository may assert** under ADR 0013
§ 1: whether a host's `.env` carries the credential; whether a repair actually
ran; whether an owner's provisioning receipt is genuine. These are facts about
hosts and runs. The measured incident proved the *absence* only because two
deploy logs printed the fallback line — a `deployment_run`-shaped oracle that no
machine-readable contract declares today, which is open decision 17 unchanged.

**Non-vacuity, and the sensitivity proof.** Any future family gets a planted
violation shown RED beside a conforming repository shown green. The specific
trap: a checker that reads the deploy script and finds both a repair step and a
verify step present would pass the measured system, because both steps *are*
there. The property is whether the repair step can execute where the verify step
runs, and a check that cannot distinguish those has reproduced the defect it was
built to find.

Whether any of this is built, and by whom, is open decision 32. Acceptance of
this record does not make that decision and does not create the family
described: a standard being normative is not evidence that a control enforces
it.

## Acceptance — 2026-08-31

Michael Ayoade approved this record on 2026-08-31. Under `AGENTS.md` an agent
may not occupy the approver role or approve its own output; neither happened
here. The decision, in his words, is quoted verbatim as § 1's standard, § 2's
and § 3's two forms, and § 4's closing sentence. He additionally specified the
ordering — this record lands before the corresponding Knowledge entry is
promoted to approved — which is why the Knowledge entry is discovery support
and this file is the authority.

Acceptance covers the standard and its two forms. It does not assign the
remediation owner for the measured system, does not build or schedule any
enforcement, and does not extend this repository's `Amends:` relationship to
`dotmac_starter_mt` ADR-0018 — that field is scoped to this repository's own
ADR directory, so the parent relationship is stated in prose above and its
propagation is open decision 34, the same situation as open decisions 20 and
31.
