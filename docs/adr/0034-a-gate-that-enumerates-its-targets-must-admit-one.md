# 0034. A gate that enumerates its targets must admit one

- Status: Accepted
- Date: 2026-09-01
- Effective: 2026-09-01
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository holding a gate whose targets are enumerated — a fixed dispatch choice list, a declared allowlist, a named service, module or host set
- Classification: Internal

## Context

### The measurement

`dotmac_sub`'s v2 published-port reconciliation requires immutable image
references. Read from that repository's `origin/main` at
`c40a914d99adb69e67bcc90b5e14881c18348268` on 2026-09-01,
`scripts/published_port_contracts.py:51-54`:

```python
ImageReference = Annotated[
    str,
    StringConstraints(pattern=r"^[^\s@]+@sha256:[0-9a-f]{64}$"),
]
```

Its PLAN workflow enumerates exactly two targets.
`.github/workflows/infrastructure-reconcile-plan.yml:10-16`:

```yaml
      service:
        description: One declared infrastructure service
        required: true
        type: choice
        options:
          - postgres-local
          - freeradius
```

**Both are tag-pinned in the production compose file.** `docker-compose.yml:91`
is `postgis/postgis:16-3.4-alpine` and `:583` is
`freeradius/freeradius-server:3.2.7`. `docker compose config` does not resolve a
tag to a digest, so for either dispatchable option the observer reads a tag and
refuses at `scripts/published_port_plan_observer.py:248-249` —
*"target service image is not immutable and digest-pinned"* — before a snapshot
exists.

The measurement went further and found it worse. The observer enumerates **every
project container** (`published_port_plan_observer.py:140-165`, `compose ps -q`
then `docker inspect`, taking `image_reference` from `.Config.Image`), and the
typed contract applies `ImageReference` to every one of them:
`PublishedPortContainerObservationV2.image_reference` at
`published_port_contracts.py:207`, inside a `containers` tuple with
`min_length=1` at `:235`, parsed strictly. In that compose file **no image is
digest-pinned at all** — `redis:7-alpine` (`:75`), `mediagis/nominatim:4.4`
(`:566`), `mongo:4.4` (`:657`), `victoriametrics/victoria-metrics:v1.96.0`
(`:672`), `grafana/promtail:3.0.0` (`:696`), `victoriametrics/vmagent:v1.96.0`
(`:838`). The application containers resolve `${APP_IMAGE}` from a `.env` this
repository cannot read, which is the only image whose form is not settled by the
checked-in file.

So **every possible dispatch refuses inside the observer**, twice over: once on
the target's own tag, and once on any of six non-target containers. The gate
cannot admit any artefact it will ever be asked to admit. It was discovered when a
production change authorization ran up against it — after the authorization had
been written.

Three precisions the measurement produced, each of which corrects the brief this
record was written from and none of which weakens it:

- The YAML key is `options:` under `type: choice`, not `choices:`. The
  enumeration is real; the spelling in the brief was not.
- APPLY does not require two plans, it requires **three**. Two archived
  successful PLAN runs, verified by run id, workflow path, attempt, conclusion,
  branch, head SHA and event (`infrastructure-reconcile-apply.yml:66`, `:92-117`)
  and typed as a two-tuple of distinct runs
  (`published_port_contracts.py:508-528`); then an immediate third plan taken on
  the APPLY runner under the deploy lock and required to be byte-identical
  (`published_port_reconcile_v2.py:465-470`). PLAN is the step that cannot
  succeed, so the count only deepens the trap.
- The gate is **merged and dispatchable, not yet exercised**. Its own runbook,
  `docs/runbooks/PUBLISHED_PORT_RECONCILE.md:100`, records *"No current run or
  receipt satisfies those gates. Do not dispatch production."* It is a production
  gate in the sense that matters here — written, reviewed, merged, wired to a
  production environment and offered as the managed path — and it had never been
  handed a real subject.

### The second-order failure: a gate can make its own repair unreachable

Clearing this needs a repository change **and** a container recreate, because the
running containers were created from tags and the digest has to come from
somewhere. But the recreate is the APPLY action, and APPLY cannot run without
PLAN runs that PLAN cannot produce.

**A gate that cannot admit its real targets does not merely fail loudly — it can
make its own repair unreachable.** That is worth recording separately from the
defect, because it changes what the defect costs. An ordinary over-strict gate is
an inconvenience discovered at dispatch and relaxed in the next change. This one
sits in front of the only managed path to the state that would satisfy it.

A repair was in flight while this record was written, and is reported as observed
rather than adopted: branch `feat/legacy-image-pin-bootstrap`, commit
`25c5bbca3`, **unmerged**, observed 2026-09-01, splits the snapshot into a target
whose image identity must be immutable and non-targets carrying identity only,
and adds a one-time bootstrap carrying a service from its legacy tag to the digest
of the bytes already running. That worktree was being modified during the reading,
which is why every coordinate above is taken from `origin/main` out of git objects
rather than from a working tree. Under ADR 0013 § 4 this is an as-of observation
about another repository's unmerged branch and expires accordingly; it is recorded
because it shows the deadlock being broken, not because this record depends on it.
Note that it does not discharge this record's requirement: on that branch the
validator is still never handed an image reference read from a compose file.

### Why the disciplines already in force cannot see this

The suite is not absent and it is not lazy. It carries **synthetic acceptance** —
`tests/test_published_port_reconcile_v2.py:32-33` builds
`ghcr.io/dotmac/freeradius@sha256:<'5' * 64>` and plants it as the effective
compose image at `:131` — and it carries **planted refusals** observed failing
correctly, for instance the running-image-ID mismatch at `:586-591`. Both are
disciplines this fleet already demands.

Neither can detect this defect, and the reason is structural rather than a matter
of coverage:

- **A synthetic fixture is built to pass.** It is constructed from the pattern, so
  it demonstrates that the pattern accepts strings built from the pattern. It
  cannot report that no real subject is built that way, because no real subject
  was ever in the room.
- **A planted violation is built to fail.** It demonstrates a working refusal
  path. Over an estate none of whose members can pass, a working refusal path is
  exactly what a broken gate also has.

The missing observation is neither: it is **a real subject, drawn from the gate's
own declared target set, passing**. That observation is not a weaker form of
either discipline and is not implied by both together.

Two further facts sharpen it. First, for this particular property the suite has
only the synthetic half — grepping the five published-port test files for the
refusal strings, for `:latest`, or for any tag-shaped image finds nothing, so both
refusal branches (`published_port_plan_observer.py:249` and
`published_port_reconcile_v2.py:226`) are unexercised. Writing the missing planted
refusal would have been the natural repair, and **it still would not have caught
this.** Second, an admissible image reference did exist in the repository —
`deploy/shadow/docker-compose.shadow.yml:37` is digest-pinned — in a different
file, for a stack the workflow does not offer. An admit demonstrated against it
would have been green and meaningless, which is why § 2 requires the subject to
come from the declared set rather than merely to be real.

### The neighbouring records

`dotmac_starter_mt` ADR-0018 rule 5 requires a guard to be shown FAILING: *"A
newly-covered region that passes must be shown to FAIL without its ratchet.
Otherwise a clean run is indistinguishable from the guard having stopped
looking."* Its 2026-08-26 amendment covers the adjacent case of a guard named for
a property it does not test. Neither reaches this: the observer's name and its
check agree exactly, and it is not skipping anything.

That repository's guard-defect taxonomy — wrong subject, wrong extent, no expiry —
also does not contain this shape. The subject is right, the extent is right, and
nothing has expired. What is wrong is that the correct check was pointed at an
estate that cannot satisfy it, and nothing ever put the two in the same room.

This repository's ADR 0021 § 9 states the sensitivity property of a coordinate
check — demonstrated red on an absent coordinate, a dead one and a filler — and
ADR 0015 gives a gate four verdicts so that a skip cannot read as a pass. Both are
`Proposed` and are cited here as drafts, not as policy. ADR 0015's vocabulary is
worth naming because it is close and still does not catch this: a gate that
refuses everything reports `executed_failed` accurately, every time. Its verdict
is honest; its admissibility is the thing nobody measured. ADR 0033 is the same
family one step away — there an instrument could not see a subject that was
present; here a gate could not admit a subject it was built for.

## Decision

### 1. The standard

> **A gate enumerating real targets must demonstrate a real-target ADMIT — not
> merely synthetic acceptance and planted refusal.**

A gate whose targets are ENUMERATED — a dispatch input's fixed option list, a
declared allowlist, a named service, module, host or profile set, a registry of
subjects it is invoked against — has a finite, written-down set of things it will
ever be asked about. At least one member of that set must be shown to PASS, using
the subject as it actually exists rather than a fixture built to satisfy the
check.

The enumeration is what makes the obligation dischargeable. A gate that has
written its targets down has already done the hard half: the set is known, so
"can this gate admit anything it will be handed" is a question with an answer.

### 2. What counts as a real-target admit

Three properties. A demonstration missing any one of them is not a real-target
admit, and the second is the one that decays quietly.

- **Drawn from the declared set.** The subject is a member of the gate's own
  enumeration — the exact service, module, host or artefact a dispatch may name.
  Not a neighbouring one, and not a representative one. The shadow compose file
  above is the counter-example: real, digest-pinned, and not a target.
- **Read where production holds it.** The subject's value is READ at test time
  from the artefact production actually uses — the compose file, the manifest, the
  lockfile, the declaration — at a named path. It is not transcribed into a
  fixture. A transcribed value is a second authority for a fact the artefact
  already fixes, and it stops being a real-target admit on the day production
  repins, with nothing going red. A test that reads the file goes red on that day,
  which is the day the gate's admissibility actually changed.
- **Fed through the gate's real acceptance path.** The subject enters at the same
  entry point a dispatch reaches, and the gate ADMITS. An admit demonstrated on a
  helper that the real path wraps in an earlier refusal proves the helper. In the
  measured case the target's tag and any non-target's tag are refused by two
  different mechanisms, so an admit shown against only one of them would have
  passed while the dispatch still could not.

**Per-member coverage where the set is small.** § 1's requirement is one admit,
which is what catches a gate that can admit nothing. Where the enumeration is
short — a two-option dispatch list is the measured case — each further member
costs one more assertion, and covering each is what catches a gate that can admit
some of its targets and not others. This extension is the drafting agent's, not
part of the transcribed standard, and is the part most safely changed later.

**A member that cannot be admitted is a finding, not an exemption.** Where the
estate genuinely does not yet satisfy the gate, the repair is to bring the estate
to the requirement, to stage the gate, or to remove the member from the
enumeration — and the refusal then happens at DISPATCH, before any state is
touched and before an authorization is written against it, rather than from inside
the gate after it has been asked to work. Recording the member as known debt
follows `dotmac_starter_mt` ADR-0018 rule 3's two-directional ratchet. What is not
permitted is leaving a member enumerated, offered, undocumented, and refused from
within.

### 3. The bracket: this is the mirror of the sensitivity proofs

The sensitivity rules and this one measure opposite directions of the same gate,
and the pairing is the whole point of the record.

- A guard observed only **failing** is indistinguishable from a guard that refuses
  everything. Its planted violation goes red exactly as designed; so does every
  real subject it will ever see. That is the measured defect.
- A guard observed only **admitting** is indistinguishable from a guard that
  admits everything. That is the failure `dotmac_starter_mt` ADR-0018 rule 5
  already covers, and this record does not restate it.

Neither direction implies the other. A suite carrying only one has an unmeasured
half whichever one it carries, and the two halves fail in ways that look nothing
alike: the first ships a gate that blocks work forever, the second ships a gate
that blocks nothing. **Together they bracket it: the gate says no to what it must
refuse, and yes to what it will actually be handed.**

### 4. Scope

**In scope** — a gate that ENUMERATES its targets, where the enumeration is
checked in and finite: a dispatch input's fixed option list; a declared allowlist,
denylist or registry of subjects; a named service, module, host, distribution or
profile set; any check whose subjects are written down somewhere a reader can
count them.

**Out of scope, deliberately.** An over-broad rule is quietly ignored, so the
boundaries are stated rather than left to judgement.

- **An open-corpus check.** A guard over every file, every route, every commit or
  every request has no declared target set, and demanding a "real target" from it
  would mean inventing one. Those are governed by the sensitivity rules in § 3 and
  by nothing new here.
- **End-to-end integration testing.** This record does **not** require a gate to
  be exercised through its full runtime path, a live dispatch, a running service,
  a provisioned host or a real container. The admit is demonstrated at the level
  the refusal already is: feed the real value into the real validator. In the
  measured case that is one test reading one compose file and calling one
  function. A rule that demanded an integration environment per gate would be
  ignored, and would deserve to be.
- **Every member of a large enumeration.** § 2's per-member extension is scoped to
  a set short enough to enumerate in a test. A registry of hundreds is covered by
  § 1's one admit plus whatever sampling its owner judges right.
- **A gate deliberately ahead of its estate.** A requirement stated before the
  estate meets it is a policy, and staging it — warn now, enforce later, with the
  dispatch refusing early — is the honest form. This record makes that choice
  visible rather than forbidding it.

### 5. What this does not require

- **No sweep.** Existing gates that have never demonstrated a real-target admit
  are unproven, not refuted. Repairing them is ordinary maintenance, done first
  where a gate stands in front of a production change.
- **No new oracle kind.** ADR 0013 § 2's four kinds are unchanged.
- **No check and no CI gate.** See § Drift prevention.
- **No status change anywhere.** ADR 0021 and ADR 0015 remain `Proposed` and are
  cited here as drafts. No ADR number changes in any repository, and no other
  repository's records are amended by this one.

## Consequences

- Every enumerating gate acquires one more test, and it is the cheapest of the
  three it should have: a synthetic accept, a planted refusal, and a real-target
  admit. The third is usually a file read and a call.
- Some gates will turn out to be unable to admit anything. That is the finding,
  not a side effect, and it will be found in gates whose suites are green.
- A gate written before the estate it governs is a policy that was deployed as a
  gate. This record does not forbid that, it makes it visible at authoring time
  rather than at the first dispatch — which in the measured case was after a
  change authorization had already been written against it.
- The deadlock shape is now recorded and should be looked for deliberately: when a
  gate stands in front of the only managed path to the state that would satisfy
  it, an over-strict gate stops being an inconvenience and becomes a trap. The
  bootstrap that breaks such a deadlock is a legitimate, structurally single-use
  thing, and is better designed before the deadlock than during it.
- Writing the missing planted refusal will feel like the repair and is not. That
  is worth saying plainly, because it is the change a reviewer will ask for.

## Drift prevention

**Enforcement status: none.** No `standards_control` rule evaluates this record,
`standards-profile.schema.json` carries no field for a gate, a target enumeration
or an admit demonstration, and no engine diagnostic exists for it. **Adding this
record turns no gate red in any enrolled repository.**

Confirmed at this repository's `main` `1024cf9`, and the confirmation corrects the
form used by ADRs 0031 and 0033 rather than repeating it. Nothing under
`standards_control/`, `gate_control/`, `agent_control/`, `programme_control/`,
`tools/` or `.github/workflows/` ENUMERATES the ADR directory except
`tools/check_adrs.py` and `tools/check_adr_references.py`. Three further
mechanisms read INDIVIDUAL ADR files, each at a path something else declares:
`standards_control` resolves each profile's `governance_model.source`
(`docs/adr/0006-cross-repository-engineering-conformance.md` for all seven
enrolled profiles) and reads one `- Status:` line from it; `agent_control` reads
the authoritative sources `.dotmac/agent-profile.json` lists
(`docs/adr/0005-...`, `docs/adr/0001-...`, `docs/adr/README.md`); and
`programme_control._adr_state_claims` reads every record a programme matrix
declares with role `governing-decision`, which in this repository is
`docs/adr/0012-dotmac-isp-replacement-programme.md` alone, matching control-state
sentences against that matrix. None of the three can see a record at a new number,
because none of them looks for one.

**Where this property is decidable, and it is not here.** Deciding it requires
three things at once: the gate's target enumeration, the artefact production uses,
and the gate's test suite. All three live in the gate's own repository, and
Governance holds none of them. Whether another repository's suite demonstrates an
admit is a fact about that suite, which ADR 0013 § 1 places outside what this
repository may assert. **This record is stated review discipline, which ADR 0013
§ 5 permits so long as it is said plainly rather than implied, and it may not be
cited as a gate.**

A generic prose scanner is refused, and the refusal is inherited rather than newly
decided: ADR 0013 § 5 already rules one out, and it would flag this record's own
recital of the measurement.

**The decidable half, in the gate's own repository.** Three properties are
decidable from a gate's source, its tests and its declarations, with no oracle and
no runtime observation:

- every member of the declared enumeration appears as a subject in a test that
  asserts ADMISSION, not merely refusal;
- that subject is READ from the production artefact at a named path, rather than
  written as a literal in the test;
- the admit assertion is made against the entry point a dispatch reaches, not a
  helper beneath it.

**Known-bad case, required to fail.** The measured suite as it stands on
`dotmac_sub` `origin/main` `c40a914d9`: a two-option dispatch enumeration, an
image-reference validator, synthetic digest-shaped fixtures, a planted refusal on
a different field, and no test in which either enumerated service's real compose
image reaches the validator. A checker that passes that is not implementing this
record, whatever else it does. The unmerged `25c5bbca3` must also fail it, since
it changes which containers are checked without adding a real-subject admit.

**Non-vacuity, stated in advance.** Three shapes that must go red, because a naive
implementation passes all three:

- an "admit" test whose subject is a literal that HAPPENS to equal a production
  value. It is green today, it is a transcription, and it stops being a
  real-target admit on the day production repins with nothing going red — the
  measured suite would have passed such a check the moment somebody copied
  `postgis/postgis:16-3.4-alpine` into a fixture, while the gate stayed exactly as
  broken.
- an admit demonstrated on a subject that is real but not enumerated — the shadow
  stack's digest-pinned image is the exhibit, and it is the shape a well-meaning
  author reaches for first.
- an admit demonstrated below the dispatch's entry point, passing a validator the
  real path guards with an earlier refusal.

And the ordinary one: a checker over zero enumerating gates passes for the wrong
reason. Until at least one enrolled repository declares a gate subject to this
record and the checker is shown red with its admit removed, the control is not
evidenced — which is why the status above says `none` rather than `pending`.

## Acceptance — 2026-09-01

Michael Ayoade approved this rule on 2026-09-01 and directed that it live in
checked-in Governance rather than in Knowledge alone, on the standing ground that
Knowledge aids discovery and does not enforce. Under `AGENTS.md` an agent may not
occupy the approver role or approve its own output, and neither happened here:
§ 1's standard is his, transcribed, as is the finding that synthetic acceptance
and planted refusal cannot bracket a gate on their own.

The drafting agent chose the placement — a new decision at the next free number
rather than an amendment — and the reason is worth recording, because three
records sit close enough to have been candidates. ADR 0021 § 9 and ADR 0015 § 6
are the nearest in substance and both are `Proposed`; an `Accepted` record may not
rest on a draft, and amending one would either activate it by implication or
produce an accepted amendment to something non-normative. `dotmac_starter_mt`
ADR-0018 rule 5 is the true mirror, and it is in a repository this one does not
own — this repository's `Amends:` field is scoped to its own ADR directory, which
is the same situation as open decisions 20, 31 and 36. ADR 0033 amends ADR 0013 on
the INSTRUMENT of a claim; this record is about a gate's admissibility and changes
nothing in ADR 0013. So: a standalone decision, with every relationship stated in
prose and every cross-repository citation qualified per ADR 0031 § 3.

Also the drafting agent's: § 2's three properties and its per-member extension,
§ 4's scope boundaries, and the drift-prevention analysis. Those are the parts most
safely changed later.

**Acceptance makes § 1 normative and builds nothing.** There is no
`standards-profile.schema.json` field, no `standards_control` rule, no CI gate,
and no enrolled repository's profile changes. An enrolled repository holding an
enumerating gate that has never demonstrated a real-target admit is an
**unmonitored region**, not a covered one.

Acceptance does not mandate a sweep of existing gates, does not add an oracle
kind, does not change any ADR number or status in any repository, and makes no
claim about whether `dotmac_sub`'s in-flight repair is correct or complete.
