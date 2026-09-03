# 0039. A foundation binding is installed, and an inapplicable one is proved absent

- Status: Proposed
- Date: 2026-09-03
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository that composes a deployable assembly
- Classification: Internal

## Context

### What was measured, and where

Read on 2026-09-03 from `dotmac_starter_mt` `origin/main` at
`d096e64c13fe3cd8ab89f4a15edd1ce1bc046e2a`, which is the tree that holds the
fleet's extraction dossiers.

- **95** `EXTRACTION.toml` dossiers.
- Package-level `status`: **85** `audit-complete`, **9** `adopted`, **1**
  `historical-pre-rule`.
- **No package-level status is `reuse-proven`.** The phrase appears **16 times
  across 10 dossiers**, almost always as prose in `next_action` describing what
  has not been earned — *"Hold at `adopted`; `reuse-proven` requires a second
  real control plane."*

One precision the measurement adds to the review that prompted this record, and
it matters because a governance record that overstates its own measurement is
the defect this repository exists to catch: **two `dotmac-ui` SLICE statuses do
declare `reuse-proven`** — `tokens` and `components` — while the package
headline is `audit-complete`, derived by that dossier's own gate as *the weakest
of its slices*. So "zero declaring `reuse-proven`" is exactly true of the 95
package-level statuses and is not true of every status value in the tree. The
slice mechanism is the honest one; it is the reason the headline understates
rather than overstates.

- **340** `[[product_writers]]` rows. `writer_state`: **193** `inventory_only`,
  **78** `qualifying_source`, **62** `legacy_writer`, **7** `no_writer`.
- **140** rows carry `retirement_required = true`; 200 carry `false`.
- `[[adoption_evidence]]` rows, by `kind`: **15** `pinned_at`, **8**
  `live_observation`, **5** `image_digest`, **5** `deploy_run`, **2**
  `composed_at`, **1** `workflow_run`, **1** `contract_binding`, **1**
  `adopted`.

### The finding that decides § 9

Every one of the 340 writer rows carries exactly five keys — `product`,
`writer_state`, `revision`, `retirement_required`, `evidence_paths` — each
appearing 340 times. **There is no field anywhere in the schema that records
that a retirement HAPPENED.** A row can say a retirement is owed. It cannot say
it is done, by whom, in which revision, or against what evidence. The 140 owed
retirements are therefore countable and the completed ones are not: closure
exists only as prose inside 95 free-text `local_copy_retirement` paragraphs,
which is why the estate's own adoption state has to be read rather than
computed.

And that prose is **already ruled out as the evidence**, in the implementing
repository, for a measured reason — see § 9. So the gap is not a missing
convention that better writing would close. It is a missing typed field: three
of the four properties § 9 requires exist today and the fourth exists nowhere.

That is the exact shape of the problem, because the programme metric Michael
stated on 2026-09-03 is

> **"local writers/executors retired", not "new reusable packages created."**

A metric whose numerator is unrepresentable is not a metric. The stated risk —
*"creating more packages while existing shared owners remain unadopted"* —
is what an unmeasurable numerator produces, since the denominator (packages) is
trivially countable and grows on its own.

### Why a profile, and why now

Nine universal concerns are unfinished across the fleet, and each is being
solved again per assembly. The proposed repair is a typed
**`ApplicationFoundationProfile.v1`**: one profile per assembly, naming the
selected implementation and version for each universal concern.

The failure mode this record is written against is not that the profile is a
bad idea. It is that a profile is the single most attractive place in an
architecture to put a value that has nowhere else to live, and a profile which
accumulates policy values becomes the everything-framework the design
explicitly refuses. § 10 is that refusal, written so the first person tempted is
stopped by the contract rather than by a reviewer's memory.

## Decision

### 1. The standard

> An assembly declares one **`ApplicationFoundationProfile.v1`** naming, for
> every universal concern, the implementation and version bound to it. A
> **missing binding refuses composition.** A binding may be `inapplicable` only
> with a reason and an **executable absence proof**. Every binding is resolved
> from the **installed candidate artifact**, never from a source checkout, and
> the profile's digest travels with the release and is read back from the
> running system and compared — never derived from it.

### 2. The thirteen concerns, as a closed set

| # | Concern |
| --- | --- |
| 1 | identity / session |
| 2 | request evidence context |
| 3 | authorization |
| 4 | persistence / migrations |
| 5 | settings / secrets |
| 6 | audit / telemetry |
| 7 | health / runtime admission |
| 8 | worker execution |
| 9 | edge security |
| 10 | API / web interaction |
| 11 | data governance |
| 12 | integration |
| 13 | deployment / recovery |

The set is **closed at thirteen**. Adding a fourteenth is an amendment to this
record, not a field somebody adds to a schema, for the same reason ADR 0019 § 2
closed the receipt envelope: the pressure never arrives as *"let us make this an
everything-framework"*, it arrives as *"it would be so much more useful with
just this one more concern"*.

A profile that omits a concern is not a smaller profile. It is not one.

### 3. What a binding is

A binding names three things and nothing else:

1. **The implementation identity** — the distribution, module or facility that
   owns the concern in this assembly.
2. **Its version** — exact, and resolved as § 5 requires.
3. **Its artifact coordinates** — under ADR 0013 § 3, which already refuses a
   branch name, "latest", an unpeeled tag and an image tag as coordinates.

A binding carries no configuration, no threshold, no list, no key and no policy
value. See § 10, which states that as a refusal rather than a preference.

### 4. Missing refuses composition, and there is no warning path

An assembly whose profile omits a concern, or names one with no version, or
names a version that does not resolve, **does not compose**. It does not compose
with a warning, it does not compose in a degraded mode, and there is no knob
that admits it for one deployment.

The warning path is prohibited explicitly because it is what always gets built:
given a warning branch, every incomplete profile becomes a warning, and this
record survives as documentation of a control nobody is running. That reasoning
is not new here — it is the refusal clause of ADR 0026 (Proposed, and cited as
a draft rather than as policy), and it is stated again because a rule proven in
one place does not travel by implication.

### 5. Installed-artifact discovery

**Every binding resolves from the candidate image, not the source checkout.**

This is ADR 0021 § 2 applied to a second surface. That record requires a
dependency floor to be DERIVED from the published artefact's own dependency
metadata rather than read from `pyproject.toml`, *"which lives in the source
tree the canary exists to exclude"*. The same asymmetry holds here and is worth
naming precisely: a source tree states what an assembly INTENDS to compose; an
image holds what it WILL run. They differ routinely and innocently — an
uncommitted pin, a build argument, a dependency resolved to a newer compatible
release, a wheel that never reached the registry — and every one of those
differences is invisible to a profile checked against the checkout.

Two consequences, both load-bearing:

- The subject of the check is an **image digest**, and the profile verification
  names it. A verification that cannot say which bytes it read has not made a
  claim about an artifact; it has made one about a directory.
- The verifier **may not be the builder**. A job reporting on the bytes it just
  produced is not an independent witness of them — the split settled for the
  floor lane in open decision 24's second ruling, and it is the same split here.

### 6. `inapplicable` is an exemption, and an exemption states an enforceable premise

A binding may be declared `inapplicable` — this is the state that keeps the
profile honest for an assembly that genuinely has no worker runtime, no web
surface, no outbound integration. It is also the state that will be used to
avoid completing a profile, so it is constrained harder than any other part of
this record.

**`inapplicable` requires a reason AND an executable absence proof.** This is
`dotmac_starter_mt` AGENTS.md rule 25 and its `dotmac_starter_mt` ADR-0018
arriving in a new place, verbatim rather than by analogy:

> A guard exemption states an enforceable premise, or it is not an exemption.
> Guards enumerate ENTRY-POINT FAMILIES (tasks, scripts, CLI, workers, cron),
> never a single directory.

So *"no worker runtime"* is an admissible premise only when the proof enumerates
the **entry-point families** — worker, scheduler, cron, task, and any other
family by which work enters the assembly — and finds each empty. A proof that
looked in one directory has established a fact about that directory.

**And the absence proof is a negative claim about a corpus, so ADR 0033 governs
it in full.** Its five requirements are conjunctive and none is optional here:

1. a closed, authoritative subject inventory — the entry-point families,
   enumerated from the installed artifact before the proof runs, never from the
   proof's own result set;
2. exact refs — the image digest, not "the build";
3. complete enumeration — every family visited, each outcome individually known;
4. a **local, parser-aware scan** — the installed artifact is read by something
   that understands its grammar (entry-point metadata, an AST walk, a declared
   manifest), never a remote index and never a substring search;
5. an explicit refusal when enumeration is incomplete — a family that cannot be
   reached makes the proof REFUSE, not report a subset.

And ADR 0033 § 3's positive control applies unchanged: **the absence proof must
first be shown to find a thing known to exist**, using the same instrument,
scope and credential as the claim. An absence prover that never finds anything
and an assembly that has nothing are the same colour.

An `inapplicable` binding whose proof does not meet all of this is not a weaker
binding. Under ADR 0033 § 2's own words it is not a claim at all, and the
concern is an **unmonitored region** in that assembly rather than an exempt one.

### 7. Positive and negative admission tests, for every binding

Each binding carries **two** tests, and the second is the one that fails in
practice.

- **Positive** — a conforming profile against a conforming candidate image is
  **ADMITTED**. ADR 0034 exists because a gate that enumerates its targets had
  been built which could not admit any artefact it would ever be asked to admit,
  and nobody learned this until a production authorization ran into it. A
  binding check that has never admitted anything is in that state now.
- **Negative** — a planted defect **REFUSES, naming the binding**. Three
  distinct defects, because they fail differently: the binding removed; the
  binding naming a version other than the one installed; the binding naming a
  version that is installed in the checkout but absent from the image.

Accepting any failure is not sufficient: ADR 0021 § 4 requires the mutation to
fail for the stated reason and to **name the missing thing**, because a resolver
error, a network failure or a typo will otherwise stand in for the proof. A
green admission lane with no paired red is not evidence that the profile holds;
it is evidence that nobody has learned whether the lane can fail.

### 8. The digest travels, and the read-back compares

The profile is **digested**, and that digest appears in exactly two places
downstream:

- the **signed release receipt** for the candidate, and
- the **Foundation execution plan** that deploys it.

A verification runs **before deployment** against the candidate image, and a
**read-back after deployment** takes the profile digest from the running system
and compares it against the authorized digest. A mismatch refuses.

Two precisions:

- **The read-back COMPARES; it never DERIVES.** ADR 0032 § 2 is directional and
  applies without modification: the profile is the authority and the running
  system is not the transcript it is written from. Editing an accepted profile
  to match what a deployed image turned out to contain inverts the relationship,
  and from that moment drift and correction arrive as the same commit with the
  same diff for the same stated reason. A disagreement is repaired by promoting
  a candidate through the mechanism, which leaves a receipt — never by an edit
  that leaves only a diff.
- **The release receipt in this section is the deployment lane's receipt, not
  this repository's `receipts/` registry.** ADR 0019 § 2 closed that envelope
  deliberately, and nothing in this record adds a field to it. Whether an
  authority cutover that displaces a local writer under § 9 also warrants a
  registry receipt is left to that record's own criteria and to open decision
  44.

### 9. Retirement evidence is a typed claim, and prose is not one

**A binding that displaces a local writer or executor owes retirement
evidence**, and that evidence is a **typed claim**. This record creates **no
parallel register**: a second place to record a retirement is a second
authority for one fact, and the fleet has paid for that shape more than once.

**The fleet has already ruled on the weaker form, and the ruling is cited here
rather than restated.** `dotmac_starter_mt`'s
`tests/architecture/test_product_first_extraction.py`, read on 2026-09-03 at
`d096e64c13fe3cd8ab89f4a15edd1ce1bc046e2a` — the reasoning sits above
`PRODUCT_WRITER_STATES` and in `_product_writer_problems`, named by symbol
because a line number decays:

> reading `local_copy_retirement` prose instead is worse — **a sentence is not
> a claim a checker can compare.**

**The measured failure that produced it** is preserved in that file as
`test_the_expenses_failure_would_now_be_refused`: **Expenses was rostered "no
ISP writer in scope" while Sub held two writers its own `local_copy_retirement`
required to ratchet to zero.** The prose field was present, it was correct, and
it did not prevent the roster from being wrong — because prose cannot be
compared. A future reader proposing *"why not just read the prose field, it is
right there"* should meet that, and not a preference.

So: **`local_copy_retirement` is the human account of the obligation.** It is
worth reading, it explains what a typed row cannot, and it is **not** the
evidence a profile is checked against.

#### The shape the profile requires

Stated as a shape rather than as a file, because a contract that names a path
imports one repository's layout into every assembly:

1. **A closed writer-state vocabulary** distinguishing at minimum: the
   implementation being extracted from; a writer that exists today and must
   stop; a product that does not write the capability; and a product that was
   **looked at** and writes nothing. The last two are separate states
   deliberately — the difference between them is *whether anybody checked*, and
   it is what makes a "no writer here" claim checkable rather than merely
   unrefuted.
2. **A retirement-required flag**, carried separately from the state.
3. **Evidence paths at an immutable revision**, pointing at the writer being
   claimed about. ADR 0013 § 3 coordinates; a claim measured against a moving
   branch is not a claim.
4. **A disposition, once the retirement happens** — in the vocabulary ADR 0018
   rule 2 already defines: **retired in a named revision**, **transferred to a
   named owner**, or **still live with a named retirement condition and a named
   owner**. *"Not yet"* is a permitted value. **Unstated is not.**

Properties 1–3 exist today. **Property 4 does not exist anywhere**, which is the
§ Context finding: 340 typed rows can say a retirement is owed and none can say
it happened.

**Silence is UNKNOWN, never "nothing to retire."** A missing writer claim says
nothing, and a consumer that needs an answer **refuses** rather than reading
absence as a clean bill of health. That rule is already written in the
implementing repository — it is the same requirement as ADR 0033 § 2's fifth,
arriving in the dossier's own terms — and the Expenses failure is what happens
when silence is read as clearance.

**`[[product_writers]]` in `dotmac_starter_mt`'s `EXTRACTION.toml` is the
fleet's current instance of this shape**, and the one Governance already cites
across the repository boundary; that file's own comment says so. It is **an**
instance and not the requirement. An assembly that carries the same four
properties elsewhere satisfies this section, provided the profile's binding
points at where they live.

#### Why the shape is the metric's load-bearing joint

The programme metric is *"local writers/executors retired"*. **If the contract
counts prose, the metric counts sentences; if it counts writer-state
transitions carrying evidence paths, the metric counts facts.** That is the
whole distance between a scoreboard and a slogan, and it is decided by which
field § 9 points at — not by how carefully anyone writes the paragraphs.

Two statements about the existing vocabulary, which this record adopts rather
than invents, because both are already written down in the tree and are worth
saying once in a place that governs:

- **`adopted` is installation-and-composition evidence, not completed
  replacement.** `dotmac_starter_mt` AGENTS.md rule 24's 2026-08-29 amendment
  already separates a pin from an adoption. The dossiers go further and say it
  about themselves: the deployment-foundation dossier records ERP as
  `adopted` while stating that ERP *"has not deployed to a host THROUGH this
  facility"* and that `scripts/deploy.sh` *"is still the executor and is not
  retired"*.
- **`reuse-proven` requires a second real consumer**, which is what every held
  dossier's own `next_action` already says. This record adds no new bar; it
  removes the option of a bar that is stated in prose and counted as met.

**The order is fixed: a binding is composed, then proven, then the writer it
displaces is retired.** Never the same change, and never on a consumer count —
the deployment-foundation dossier corrected itself on precisely this point, and
its correction is the general rule: a consumer that adopts a facility as
declarative input and a CI gate has proven nothing about its ability to replace
an executor.

### 10. Bindings, not policy values — and the refusal is structural

> **If two correct deployments of the same artifacts could hold different values
> for it, it is not a binding.**

That is the test, and it is decidable by the person writing the profile rather
than by the reviewer reading it. A rate limit, a retention period, a timeout, a
CORS origin list, a trusted-proxy range, a key, a quota, a feature flag, a
retry budget and a log level all fail it immediately: each varies by
environment, tenant or time while the artifacts stay identical. Each already
has an owner — settings and secrets, the product's deployment descriptor, or
the entitlement surface — and moving it into the profile creates a second
authority for a value that has one.

Three mechanical consequences, because a boundary stated only as a principle is
enforced only by whoever remembers it:

1. **The binding entry is a closed field set** — implementation identity,
   version, artifact coordinates, and the `inapplicable` reason-and-proof pair.
   A field outside the set is **refused, not ignored**, so proposing a policy
   value is a reviewed amendment to this record instead of a plausible line in
   a pull request. This is ADR 0019 § 2's mechanism, reused because it worked.
2. **No binding value is an input to a runtime decision.** The profile decides
   what is composed. It never decides what a request is allowed to do. A
   permission, an entitlement, a quota and a rollout flag remain separate
   decisions with their own owners.
3. **The profile is verified, not consulted.** Reading a value out of the
   profile at request time is the shape that converts it into a configuration
   store; a profile is checked at composition, at release and at deployment,
   and the running system reads its own configuration from its own owner.

### 11. What this record does not decide

- It does not name the implementation of any binding. Kernel and the narrow
  facilities own those, and this record's scope is what the profile must
  contain and what may refuse it.
- It does not change `dotmac_starter_mt`'s dossier schema. § 9 states a
  property the schema must be able to express; the change belongs to that
  repository's owner and is open decision 44.
- It creates **no check, no gate and no `standards-profile.schema.json`
  surface**. See § Drift prevention.

## Consequences

**No assembly in the fleet can complete this profile today, and that is the
first useful result rather than an objection.** Nine of the thirteen concerns
have no fleet owner mature enough to be named as a binding, so a first pass
produces a profile that is mostly incomplete or `inapplicable`-without-proof.
That output is a measurement of the estate's real foundation coverage, taken
concern by concern against installed artifacts, and it is the measurement the
programme currently lacks.

**The refusal in § 4 is not deployable until the bindings exist.** Composing a
refusal into an assembly whose profile cannot be completed stops that assembly
from deploying. The staging is therefore forced and should be stated rather
than discovered: the profile is authored and verified in report-only form
first, and § 4's refusal is turned on per concern as that concern acquires a
real binding. What must NOT happen in the interim is the thing § 6 exists to
prevent — completing the profile by marking the unfinished concerns
`inapplicable`. An unfinished concern is missing, not absent, and the two are
different words for a reason.

**Adoption becomes countable.** With § 9's disposition in place, "local writers
retired" is derived from 340 typed rows instead of read out of 95 prose
paragraphs, and the programme's stated metric becomes something a reviewer can
compute rather than assert.

**A concern that has no owner is now visible as such.** Today an assembly with
no request-evidence context and an assembly with a mature one are
indistinguishable from outside; both simply have nothing to show. A profile
makes the first one carry an explicit hole.

**This record adds a way to be dishonest, and names it.** An `inapplicable`
binding with a plausible reason and no executable proof is cheaper than any
alternative and looks identical to a completed one in every summary. § 6 is
written at the length it is for that reason, and the two-directional ratchet in
§ Drift prevention exists because an exemption set that only ever grows is how
this failure accumulates.

## Drift prevention

**Enforcement: none.** No check family, no `standards_control` rule, no
`standards-profile.schema.json` field and no CI gate is created by this record,
here or anywhere. An enrolled repository without a foundation profile is an
**unmonitored region**, not one covered by this standard, and this record may
not be cited as a gate.

What is decidable, and where it would have to live:

- **Profile completeness and the closed field set** — decidable from repository
  content wherever the profile is checked in. That is the half a
  `standards_control` rule family could reach, and it is gated on this record
  being `Accepted`, since building enforcement for a `Proposed` standard
  activates policy without approval.
- **Installed-artifact resolution (§ 5)** and **the admission tests (§ 7)** are
  facts about another repository's workflow runs and about an image digest,
  which ADR 0013 § 1 places outside repository-local claims and ADR 0013 § 5
  admits only through a declared oracle. This repository has no oracle for a
  run, an artefact path or an image digest today; that is open decision 17.
- **The absence proofs (§ 6)** must themselves be ratcheted **two-directionally**
  in the assembly that holds them: the set of `inapplicable` bindings is exact,
  fails when it grows, and fails when an entry stops firing without being
  removed in the same change — an entry that no longer matches is an exemption
  nobody is checking. This is `dotmac_starter_mt` ADR-0018 rule 3 applied to the
  profile, and it is the mechanism that keeps § 6 from decaying into a list of
  historical assertions.
- **The read-back (§ 8)** is a `deployment_run` claim under ADR 0013 § 5 with no
  oracle, exactly as ADR 0026's runtime identity fields are.

**The sensitivity question this record must not dodge:** a profile checker run
over a fleet with no profiles passes, because there is nothing to fail. Any
implementation of § 7 therefore carries its own positive control — a conforming
profile it is shown to ADMIT — before its refusals are believed. That is ADR
0034's rule about this record's own enforcement rather than about its subject.

Open decision 44 records what acceptance would deliberately leave undecided:
which half of this standard is automated, who owns the dossier schema change
§ 9 needs, and whether the profile digest gains a declared surface in
`standards-profile.schema.json`.
