# 0013. Repository-local claims and external oracles

- Status: Accepted
- Date: 2026-08-21
- Effective: 2026-08-22
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and every enrolled Dotmac repository
- Classification: Internal

## Context

A repository's automated checks are trusted in proportion to how precisely they
say what they cover. That trust is misplaced when an assertion's *shape*
suggests it enforces something outside the repository while its *derivation*
reads only a local file.

On 2026-08-21 that happened in `dotmac_vendor_control_plane`. A declaration
named `AWAITING_RELEASE_TAG` listed `dotmac-deployment-control`, an architecture
test asserted the name was absent from `pyproject.toml`, and the surrounding
prose described it as "an executable gate on the release tag — the pin waits for
the tag". The test read `pyproject.toml` and nothing else. The tag
`dotmac-deployment-control-v0.1.0a2` was published, and the assertion stayed
green, because nothing in it could observe a registry. It proved intent — this
repository has not pinned that distribution — and was presented as proving
availability.

Two aggravating details are part of the record, because both recur:

- The absence of the tag was checked against a **stale local tag set with no
  fetch**. A local clone is not an oracle for a remote ref.
- The declaration's name encoded the external subject (`RELEASE_TAG`), which is
  how a reviewer came to read a local membership test as a release gate. Naming
  is part of the claim.

Dotmac already separates these concerns in principle. `docs/evidence-model.md`
(draft) requires evidence to be produced by a named source system and cited by
immutable reference, and says an agent's or a document's own assertion is not
evidence. ADR 0006 gives this repository the organization-wide engineering rule
catalogue and the repository profile that carries machine-readable contracts.
What is missing is the narrow, decidable statement of which claims a repository
may derive for itself, and what a claim about the outside world must carry.

The tempting remedy — scan documents for sentences that look like external
claims — is the wrong instrument. A prose scanner cannot distinguish a claim
from a description of a claim, from a quotation of a retracted claim, or from
this ADR's own recital of the incident above. It decays into an exception list,
and an exception list is what a control looks like just before it stops
measuring anything.

## Decision

### 1. The standard

> Repository-local transition claims must be derived from repository-local
> facts. Release, registry and production-adoption claims require an
> authoritative external oracle.

This is the normative fleet standard. It applies to enrolled repositories'
architecture tests, declaration modules, ADRs, and any document a reader treats
as authoritative.

A **repository-local fact** is one the repository contains and a check can
derive from it: declared table names, symbol references and their call sites,
dependency-table contents, the decision a checked-in ADR recorded, a file's
presence. These may be asserted directly, and should be derived rather than
restated in prose that a later change can silently falsify.

An **external claim** is any assertion about a state this repository does not
contain: that a version is released, that a reference exists in a registry, that
an artefact deployed, that another product runs a module. An external claim is
permitted only with an oracle of a kind defined in § 2, carrying complete
coordinates per § 3, cited in the claim itself.

Naming is part of the claim. A local declaration may not be named for the
external subject it does not observe.

### 2. Typed oracle kinds

Four kinds. Each names the source system that produces the fact, and the fields
that make the citation re-checkable by someone who was not present.

**`release_run` — a version was published and is installable.**

| Field | Meaning |
| --- | --- |
| `repository` | Repository whose workflow published the artefact |
| `run_id` | The workflow run that published, installed the artefact back from the private index, registered it, and then tagged |
| `distribution` | Distribution name as published |
| `version` | Exact version string |

The run must be the one that performed publish → install-back → register → tag.
A run that only built, or only tested, is not this kind and may not be cited as
one. Installability is what the claim asserts, so the oracle must be the step
that demonstrated it.

**`peeled_tag` — a distribution version is pinnable.**

| Field | Meaning |
| --- | --- |
| `repository` | Repository holding the tag |
| `tag` | Full tag name, e.g. `<distribution>-v<version>` |
| `commit` | The **peeled** commit SHA the tag resolves to |

The peeled commit is required and is not interchangeable with the tag object's
own SHA: an annotated tag is a distinct object, and a tag reference is mutable
until protected. The peeled commit is what stays comparable after a retag.

**`deployment_run` — a named target ran an exact artefact.**

| Field | Meaning |
| --- | --- |
| `repository` | Repository deployed |
| `run_id` | Deploy workflow run |
| `commit` | Exact source commit deployed |
| `image_digest` | Immutable registry digest, never a mutable tag |
| `target` | The explicitly named host or environment |

`target` is required and must be the name a human gave. A target inferred from
deployment history is not a coordinate; it is a guess about which system the
evidence describes, and it is the guess that makes deploy evidence unusable
after the fleet changes shape.

**`adoption_evidence` — a product RUNS a module.**

| Field | Meaning |
| --- | --- |
| `repository` | Repository owning the module's dossier |
| `commit` | Exact commit at which the dossier was read |
| `path` | Path to the dossier, e.g. `packages/<distribution>/EXTRACTION.toml` |
| `field` | The field read, e.g. `adoption_evidence` or `contract_consumers` |

Adoption is asserted by the owning dossier, never by the consuming repository
about itself. A consumer citing its own belief that it is adopted is the
self-asserting document `docs/evidence-model.md` already excludes.

### 3. Immutable coordinates

Every oracle citation carries the repository, an exact commit, tag or run
identifier, and the source path where the claim is read from a file. A citation
lacking any applicable coordinate is incomplete and the claim it supports is
unsupported.

The following are **not** coordinates: a branch name; "current `main`"; "latest";
a floating or unpeeled tag; "the dossier"; a run described without its id; an
image described by tag rather than digest.

Run identifiers, peeled tag commits and image digests already supply immutable
identity and need no additional hash. A file-backed claim needs commit *and*
path together: either alone leaves the reader unable to re-read what was read.

### 4. Permanent positive evidence versus temporal negative claims

A positive existence claim backed by an oracle is **permanent**. That a
particular run published a particular version does not stop being true.

A negative or absence claim is **temporal**. "No first adopter is recorded",
"the table is empty", "no consumer exists" describe a moment. An oracle can
witness that moment; it cannot extend it. Such a claim is therefore permitted in
exactly two forms:

**(a) An as-of observation.** It carries its oracle coordinates, the observation
date, and a named **refresh responsibility**: who re-observes it, and the event
before which it must be re-observed — typically the decision it gates. An as-of
observation with no refresh owner is a permanent claim wearing a date.

**(b) Replaced by a repository-local positive fact.** Where the absence is being
used to justify local restraint, state the local decision instead. "Vendor
remains deferred by ADR decision" is derivable here, permanent until the ADR
changes, and needs no oracle — whereas "another product has no first adopter
yet" is a temporal claim about a repository this one cannot see.

Form (b) is preferred wherever it is available, because it moves the claim
inside the boundary where it can be checked. Form (a) is for the cases where the
absence itself is load-bearing — an empty legacy estate before a cutover, for
instance — and there the refresh responsibility is the control.

### 5. Scope of automation

Automate a claim only where **both** hold:

1. the claim is represented in a machine-readable contract — a repository
   standards profile, a typed declaration module, a dossier field — rather than
   in prose; and
2. that representation carries a declared oracle kind.

Where both hold, the check is decidable and narrow: every external claim in the
contract carries an oracle of a permitted kind, with complete coordinates, and
temporal negatives carry a refresh owner.

**No generic prose scanner is to be built.** It cannot separate a claim from a
description of one, it would flag this ADR's own recital of the incident, and
its exception list would grow until it measured nothing. Claims outside a
machine-readable contract remain review discipline, and this ADR says so rather
than implying coverage that does not exist.

## Consequences

- Enrolled repositories gain a stated boundary for what their own checks may
  claim, and a vocabulary for citing what they cannot check.
- Some existing assertions will be found to be local facts named for external
  subjects. The remedy is to rename and rescope them, not to weaken the check:
  `AWAITING_RELEASE_TAG` became `DEFERRED_BY_LOCAL_DECISION`, which holds a
  decision the repository actually took.
- Documents citing "the current dossier" or "main" must gain exact commits and
  paths. This is real work in existing records and is expected to surface
  citations that cannot be completed, which is the useful outcome.
- Absence claims acquire an owner. Several existing "the estate is empty"
  statements have no refresh responsibility today and will need one or will be
  restated as local decisions.
- The automation scope is deliberately narrow, so most conformance to this
  standard is review discipline. An implementation that claimed otherwise would
  be the same defect this ADR records.
- This record is `Proposed` and therefore not normative. It is cited here as a
  draft, not as policy, until a named human accepts it.

## Drift prevention

**Known-bad case, required to fail.** Any future implementation of § 5 must
reject a declaration that asserts an external condition while deriving only from
a local file — concretely, a declaration named for a release tag whose sole
derivation is dependency-table membership. That is the `AWAITING_RELEASE_TAG`
shape, and it is the sensitivity case: a checker that passes it is not
implementing this record, whatever else it does. The incident is recorded in
§ Context with enough detail to reconstruct the check that failed to catch it.

**Non-vacuity.** A checker over zero declared external claims passes for the
wrong reason. The control does not count as evidenced until at least one
enrolled repository declares at least one external claim with an oracle, and the
checker is shown to fail when that oracle's coordinates are removed.

**Coordinate completeness is machine-checkable; oracle truthfulness is not.**
This standard can verify that a citation carries a run id, a peeled commit, a
digest and a path. It cannot verify that the run did what the citation says.
That gap is stated rather than closed, and closing it — by resolving citations
against their producing systems — is a separate decision with its own access,
retention and rate-limit questions.

**Implementation status: unimplemented.** No `standards_control` rule, no
`standards-profile.schema.json` field, and no engine diagnostic exists for this
record. Representing the oracle kinds in the profile schema and enforcing § 3
and § 4 are a separate reviewed change, gated on this record being accepted.
Recording that plainly is required: a decision whose drift-prevention section
describes an unbuilt control as though it were running is the failure this
repository exists to prevent.

## Acceptance amendment — 2026-08-22

Michael Ayoade approved this record on 2026-08-22. The approval is his; this
section records it as an attributable event, written by the agent that drafted
the record. Under `AGENTS.md` an agent may not occupy the approver role or
approve its own output, and neither happened here — the decision was made by the
named human and is transcribed, not made, below.

### What acceptance changes

The standard in § 1 is now normative for enrolled repositories. In particular
`dotmac_vendor_control_plane` rule 17 stops binding on that repository's own
local authority and starts citing an accepted fleet record — which matters
because the work it governs now spans three repositories and its release,
registry and adoption claims are exactly the kind this record is about.

### What acceptance does NOT change

Nothing operational. § 5 and the drift-prevention section already state that the
control is **unimplemented**: no `standards-profile.schema.json` field, no
`standards_control` rule, no CI gate, and therefore no enrolled repository's
profile changes on acceptance. Conformance outside a machine-readable contract
remains review discipline, and saying so is part of the decision rather than a
caveat on it.

Open decisions **17** (machine-readable representation of the oracle kinds) and
**18** (resolving citations against their producing systems) are unchanged and
still require their own decisions. Accepting this record does not pre-approve
either.

### First application

The rule was applied before it was accepted, which is the ordinary way a
standard earns acceptance rather than a defect: `dotmac_vendor_control_plane`
retracted an `AWAITING_RELEASE_TAG`-shaped guard that asserted a release tag while
reading only `pyproject.toml`, and its cutover documents now carry release-run
ids, peeled tag commits and exact `EXTRACTION.toml` commit-and-path citations.
That is the § 2 vocabulary in use, and it is the evidence this record is
accepted on.

## Amendment — 2026-09-05: retirement evidence oracle kinds

Michael Ayoade approved the issue 33 design on 2026-09-05. His exact
instruction was:

> I approve the issue #33 design; commit and open the PR

The approval is Michael's. This agent-authored section records it and does not
make the agent an approver. The amendment becomes normative only when Michael
merges this exact change through protected `main`. It is the typed-design
prerequisite for [ADR 0017](0017-module-migrations-retire-compatibility-state.md)
and Governance issue 33. The existing four oracle kinds remain unchanged.

The existing `deployment_run` kind proves that a named target ran an exact
artefact. It does not prove which objects a migration database contained, what
a live catalogue reported while an exclusive fence was held, or whether an
unexpected dependency caused a teardown transaction to roll back. Two narrow
oracle kinds are therefore added.

### `product_revision_check` — a product revision produced controlled evidence

This kind describes a repository-built migration database or another
revision-bound product check. It never describes a deployed target.

| Field | Meaning |
| --- | --- |
| `repository` | Canonical product repository |
| `commit` | Exact 40-character product commit evaluated |
| `governance_revision` | Exact 40-character Governance revision whose evaluator produced the record |
| `run_id` | Positive workflow-run identifier |
| `run_attempt` | Positive attempt number, so a rerun is not conflated with its predecessor |
| `artifact` | Name, SHA-256 digest, and repository-relative record path of the produced evidence |
| `collector` | Typed local source reference naming the product-owned evidence adapter |
| `observed_at` | UTC timestamp carried by the produced record |

The kind identifies the producer and immutable record. It does not turn a CI
database into evidence about an already deployed database.

### `target_retirement_observation` — a named target produced bounded evidence

This kind describes one phase of a compatibility-state retirement observation
against a target explicitly named by a human.

| Field | Meaning |
| --- | --- |
| `repository` | Canonical product repository |
| `commit` | Exact 40-character product commit intended to run after the phase |
| `governance_revision` | Exact 40-character Governance revision whose evaluator produced the record |
| `run_id` | Positive controlled-run identifier |
| `run_attempt` | Positive attempt number |
| `image_digest` | Immutable image digest, never a tag |
| `target` | Explicit human-provided host or environment name |
| `phase` | Exactly `pre_drop`, `atomic_teardown`, or `post_upgrade` |
| `transaction_outcome` | `null` outside `atomic_teardown`; otherwise exactly `committed`, `refused`, or `rolled_back` |
| `refusal_stage` | `null` unless atomic teardown refused or rolled back; then exactly `fence_acquisition`, `inventory_validation`, or `teardown` |
| `observation_id` | Stable identifier for this observation |
| `preceding_observation_id` | Prior phase identifier, or `null` only for `pre_drop` |
| `deletion_migration` | Typed source reference to the reviewed product or assembly migration |
| `artifact` | Name, SHA-256 digest, and repository-relative record path of the evidence |
| `observed_at` | UTC timestamp |
| `refresh_owner` | Accountable owner for re-observation |
| `refresh_before` | Exactly `cutover_authorization`, `fenced_teardown`, or `completion_claim` |

The phase and link are load-bearing. A pre-drop observation cannot be relabelled
or reused as atomic-teardown or post-upgrade evidence, and a chain that changes
target, product revision, image digest, Governance revision, or deletion
migration is not one retirement sequence. A post-upgrade observation may follow
only an atomic observation whose transaction outcome is `committed`. A refused
or rolled-back atomic attempt is evidence of that attempt, never a completed
teardown.

Both kinds are external controlled records. A repository-local checker may
validate their closed shape, immutable coordinates, binding, phase order, and
internal consistency. It may not authenticate an artefact by trusting the
artefact's self-declared digest, assert that the cited run occurred, infer a
target, or claim that it directly observed a database. Retrieval,
authentication, target access, and destructive authorization remain with the
named producing and authorization systems. Open decision 18 remains open.
Open decision 17 also remains open for a generic standards-profile
representation of the original four oracle kinds; this amendment types only
the two records required by the retirement observation bundle.
