# 0017. Module migrations retire compatibility state

- Status: Accepted
- Date: 2026-08-29
- Effective: 2026-09-05
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Governance-enrolled Dotmac repositories that migrate product behavior into installable modules
- Classification: Internal

## Context

Moving an authoritative decision or state transition into an installable module
does not by itself complete a migration. A product can route new decisions to
the module while its displaced local writer, legacy table, fallback path,
reverse feed, or foreign-key dependency remains live. Calling that state
complete hides a second owner and makes the compatibility surface permanent by
accident.

This proposal applies only to repositories enrolled in the Governance
conformance programme. It does not claim authority over an unenrolled
repository merely because that repository belongs to Dotmac.

Compatibility relations are sometimes needed while consumers drain. They
include legacy tables, views, materialized views, caches, or read models kept
solely to preserve a displaced shape or identity. They are scaffolding, not a
second source of truth. A relation that remains a product-owned business record
for an independent reason is not silently reclassified as compatibility; the
migration must name its owner and intended steady state.

Michael directed this fleet rule during the 2026-08-29 working session. That
direction is not the repository's required GitHub approval record. Under
[ADR-0001](0001-governance-authority-model.md), this record therefore remains
Proposed and non-normative until the named human approval is recorded in the
controlled GitHub workflow and the approved change is merged to canonical
`main`.

## Decision

### Completion means retirement, not only activation

If this proposal is accepted, a module migration is complete only when all of
the following displaced state has been retired:

1. local decision writers and state-transition paths;
2. compatibility relations and their grants, triggers, functions, repair jobs,
   and fallbacks;
3. reverse feeds that let the displaced surface decide or overwrite module
   state; and
4. static and live dependency edges, including readers, imports, ORM
   relationships, foreign keys, and constraints.

Authority activation is an intermediate milestone. Migration reports and
cutover records must distinguish **authority activated** from **migration
complete**.

Every displaced relation must have an explicit outcome: migrate to the module,
remain as a named product-owned record with its own reason and owner, or be
deleted with the displaced writer. High fan-in is a reason to stage the drain,
not to wholesale-retarget a legacy hub and its foreign keys into a module
schema.

### Temporary compatibility projection contract

A compatibility projection may remain after authority activation only for a
named, concrete consumer need. Its migration record must identify:

- the authoritative source and exactly how the compatibility shape derives
  from it;
- every current consumer and why that consumer cannot yet use the owner;
- provenance and freshness semantics;
- an exact two-directional ratchet for callers and other static dependency
  edges;
- a separately exercised two-directional live-catalog ratchet for foreign
  keys, constraints, triggers, grants, and other database dependencies that
  actually exist;
- the retirement condition, accountable owner, and deletion migration; and
- proof that the projection neither feeds decisions back to the owner nor
  becomes a fallback writer.

An ordinary, non-materialized view has one canonical derivation: its owned
query definition. It stores no projected rows, therefore has no projection
writer or repair loop; its record instead proves that the definition reads only
the authoritative source and states its query-time freshness semantics. A
stored table, cache, materialized view, or other persisted projection has one
canonical writer or refresher, a measurable drift invariant, and an idempotent
repair path back to the authoritative fixed point. A materialized view's
refresh owner is its writer for this purpose.

"Two-directional" means the checked inventory fails when an unreviewed edge is
added and when a removed edge is not also removed from the baseline. A falling
count without a lowered baseline is a failure, because otherwise stale debt can
be mistaken for continuing evidence. Static caller evidence and live-catalog
evidence are separate: source inspection cannot prove that a deployed foreign
key or trigger is absent.

A view can provide a read shape, but it does not satisfy foreign-key identity
requirements and does not become authoritative merely because consumers can
query it. An externally supported API or export may keep its wire shape through
a thin adapter that reads the module owner; that wire contract does not require
the old database relation to survive.

### Consumers migrate semantically

Consumers move according to what the dependency means, rather than by replacing
one table name with another:

- a decision uses the owning module's typed port;
- an independent local module stores a tenant-scoped opaque reference and has
  the assembly validate it, instead of creating a cross-module foreign key;
- a person or actor reference uses the fleet Party/Principal contract where
  that is the actual meaning;
- a historical transaction keeps an opaque reference plus the immutable input
  snapshot needed to explain the past decision;
- display and search use a named, rebuildable consumer read model when a local
  query shape is required; and
- cross-application synchronization uses versioned APIs, outbox/inbox delivery,
  and Integrator evidence, never another application's database relation.

### Deletion gates

Deletion is a separately authorized, drained cutover. It is not an incidental
step in an ordinary application deploy. Evidence is split into three gates so
a preflight result cannot be reused after the database has changed.

A repository-built migration database proves the catalogue shape produced by
that revision; it does not prove the state of an already deployed target. When
a cutover claim concerns a deployed target, its authorization additionally
requires a fresh, bounded, read-only inventory from that explicitly named
target. The migration then repeats the database-checkable inventory inside its
own fenced transaction, and post-upgrade evidence is taken from the same named
target. CI evidence and target evidence remain distinct controlled records.

#### Pre-drop gate

Before authorizing the cutover, one reviewed gate must prove all of these
conditions against the product revision that will run after the drop:

1. displaced writers, reverse feeds, fallback paths, repair jobs, and stored
   projection refreshers are zero or are explicitly removed by the deletion
   migration;
2. static readers, callers, imports, ORM relationships, and dependency edges
   are zero;
3. named compatibility consumers are zero;
4. a fresh live-catalog inventory reports no inbound foreign keys, constraints,
   triggers, dependent relations, grants, or other objects except the exact
   teardown set declared by the deletion migration;
5. any stored projection is at its fixed point, and archival and
   external-client exit conditions are settled;
6. old application processes are drained and prevented from restarting, and
   the product revision removes every code path and model that used the
   compatibility relation; and
7. the product or assembly lineage that owns the compatibility relation
   contains the reviewed deletion migration. The installable module's lineage
   does not drop a product or assembly relation it does not own.

Passing this gate permits an operator to authorize the destructive cutover; it
does not prove that the relation is safe to drop later without rechecking.

#### Atomic teardown gate

The authorized deletion migration must fail closed in one database transaction:

1. before changing a grant, trigger, function, or relation, acquire a
   database-enforced exclusive, fail-fast fence on the compatibility relation
   and every relation needed to freeze the declared dependency set; for
   PostgreSQL relations this means an appropriate `ACCESS EXCLUSIVE ... NOWAIT`
   lock held through commit;
2. while that fence is held, recompute the live-catalog inventory and every
   database-checkable pre-drop invariant;
3. refuse the cutover if any dependency or teardown object differs from the
   reviewed set;
4. remove the declared grants, triggers, functions, refresh machinery, and
   compatibility relation in dependency order; and
5. use `DROP ... RESTRICT`, never `CASCADE`, so an unexpected dependency aborts
   the transaction rather than being erased.

A refusal or failed statement rolls the transaction back without a partial
teardown. Once module authority has moved, rollback must not recreate the
displaced authority, restore a reverse feed, or make the compatibility relation
a fallback. A failed cutover is repaired forward under a new reviewed migration
and authorization.

#### Post-upgrade gate

After the authorized transaction commits and the intended product revision is
running, evidence must prove:

1. the compatibility relation and its grants, triggers, functions, repair or
   refresh machinery, and declared dependencies are absent from the live
   catalog;
2. the product revision's exact two-directional inventories remain at zero for
   readers, writers, fallbacks, consumers, and dependency edges;
3. no drained pre-cutover process is running or eligible to restart; and
4. the module owner remains the sole decision writer and its typed paths pass
   the product's cutover checks without a compatibility fallback.

The migration is not complete until this post-upgrade gate passes, even when
the module has long been the active authority.

### Enforcement status

This proposal does not add a conformance claim. The current standards profile
has no typed inventory for product-local migration writers, compatibility
consumers, or live-catalog dependencies, and the Governance engine has no
database oracle that can evaluate the deletion gate. Product repositories may
enforce their own exact caller and live-catalog ratchets, but a green product
check is evidence only for the product revision it evaluated.

Central enforcement requires a separate accepted design, a versioned standards
profile change, stable diagnostics, and known-bad sabotage cases. Until then,
the requirements in this ADR are review discipline if the ADR is accepted; they
must not be described as a Governance engine control.
The implementation action is owned by
[Governance issue 33](https://github.com/michaelayoade/dotmac_governance/issues/33).

## Consequences

- Compatibility projections may outlive authority activation, but their
  existence prevents the migration from being called complete.
- Migration work includes dependency drainage and deletion, not only routing
  new commands to the module.
- Legitimately retained product relations must have an explicit owner and
  steady-state reason, making them distinguishable from forgotten scaffolding.
- Products incur the cost of separate source and live-catalog evidence where
  database dependencies exist.
- This Proposed ADR changes no current policy or conformance result.

## Drift prevention

`tools/check_adrs.py` validates the ADR filename form, unique number, exact
controlled metadata and status form, required sections, and declared ADR
relationships. It does not enforce the proposed module-retirement behavior,
and no new test is added that would imply otherwise.

Any future central control must include stable failures for at least:

- a newly planted caller or consumer absent from the static baseline;
- a removed caller whose stale baseline was not lowered;
- an added or removed live foreign key or constraint without the corresponding
  live-catalog baseline change;
- a second writer or reverse feed;
- a deletion-ready claim while any gate remains non-zero;
- an unexpected live dependency that makes the fenced `DROP ... RESTRICT`
  transaction refuse without partial teardown; and
- planted caller and database-dependency canaries proving both detectors remain
  sensitive.

Promotion from Proposed requires the named human's approval to be recorded in
GitHub and the approved change to merge to canonical `main`. Only then may an
implementation change cite this ADR as normative, and only an implemented,
sabotage-tested control may claim automated conformance.

## Acceptance — 2026-09-05

Michael Ayoade approved this record on 2026-09-05 after the completion report
for Governance issue 3 stated that issue 33 remained blocked because ADR 0017
still required explicit approval. His response was:

> i approve

The approval is Michael's. This agent-authored section records it; it does not
make the agent an approver. Under ADR 0001, the promotion becomes effective only
when Michael merges this exact acceptance change through protected `main`.

Acceptance puts the module-migration retirement rules in force for the stated
scope. It changes no deployed system, authorizes no destructive deletion, and
does not claim that the Governance engine observes a product or production
database. The historical sentences above describing the record as Proposed
remain as the proposal record; for current status they are superseded by this
dated acceptance section and the controlled metadata.

Acceptance also creates no automated conformance result. Issue 33 remains the
implementation owner and its gates remain distinct:

1. this acceptance change merges to canonical `main`;
2. a reviewed, versioned profile design names the repository-local declarations
   and the external-evidence boundary;
3. the parser, stable diagnostics, and known-bad controls are implemented;
4. exact hosted-CI evidence exists for the merged implementation; and
5. one enrolled product adopts the control without copying Governance policy.

Until those gates pass, ADR 0017 is normative review discipline, not an
automated Governance conformance claim.

## Amendment — 2026-09-05: typed retirement control

Michael Ayoade approved this issue 33 design on 2026-09-05 with the instruction
quoted in ADR 0013's coordinated amendment. The approval is Michael's; this
agent-authored section records it and does not make the agent an approver. The
amendment becomes normative only when Michael merges this exact change through
protected `main`. It records the typed profile-design review required by issue
33. It changes no database, authorizes no deletion, and does not make Governance
a production observer.

### 1. Version 11 declares exact retirement contracts

Standards-profile schema version 11 adds two required top-level fields:

```json
{
  "schema_version": 11,
  "compatibility_retirements": [],
  "retirement_history": []
}
```

An empty array explicitly enrolls no retirement slice. It is not evidence that
the repository has no legacy state. Every non-empty member is one displaced
relation and carries exactly these fields:

| Field | Contract |
| --- | --- |
| `retirement_id` | Unique stable slug |
| `authority_transition` | Closed legacy/module authority and writer binding described below |
| `accountable_owner` | Non-empty human or team responsibility |
| `relation` | Closed object containing `kind`, `identity`, and `owner_lineage`; database identities are schema-qualified |
| `disposition` | One closed variant described below |
| `source_state` | Exactly `draining` or `drained`; this is repository-local state, not deployed completion |
| `requested_gate` | Exactly `none`, `pre_drop`, or `post_upgrade`; a request for evaluation, never authorization |
| `consumers` | Unique `consumer_id`, `need`, and `blocked_by` source-reference records |
| `static_baseline` | Exact static-edge records, never a count |
| `catalogue_baseline` | Exact catalogue-edge records, separate from static evidence |
| `collector` | Product-owned source reference, workflow path, stable producer id, and fingerprint-normalization version |
| `deletion` | `null`, or the reviewed migration, owning lineage, exact teardown set, and fence relations |
| `external_exit_conditions` | Exact four-way disposition of archival, external-client, process-drain, and restart-prevention obligations |

Relation `kind` is one of `table`, `view`, `materialized_view`, `cache`, or
`read_model`. `retirement_id` and relation identity are unique. Several
relations may share one deletion migration; no relation may have two answers.

The nested records are closed and have these exact keys:

```text
relation:
  {kind, identity, owner_lineage}
collector:
  {source, workflow_path, producer_id, normalization_version}
deletion:
  null | {migration, owner_lineage, teardown_set, fence_relations}
external_exit_condition:
  {condition_id, kind, status: "required", accountable_owner, requirement}
  | {condition_id, kind, status: "not_applicable", accountable_owner,
     rationale}
consumer:
  {consumer_id, need, blocked_by}
authority_transition:
  {state: "legacy_active", current_authority_id, current_writer,
   target_module_authority_id}
  | {state: "module_active", current_authority_id, current_writer,
     displaced_authority, activation_record}
displaced_authority:
  {authority_id, writer, historical_profile}
historical_profile:
  {repository, commit, path, sha256}
activation_record:
  {repository, commit, path, sha256, retirement_id, relation_identity}
```

`normalization_version` initially permits only `python-ast-v1`; the observation
bundle must declare the same version. A normalization change requires a profile
version whose migration re-measures every fingerprint rather than inheriting
numbers produced by a different detector.

Exactly one exit-condition record exists for each of `archival`,
`external_clients`, `old_process_drain`, and `restart_prevention`. `required`
names the source of the obligation; `not_applicable` names a checked rationale.
Absence never means not applicable. Each kind maps to its same-purpose required
check. `fence_relations` is a non-empty unique set of schema-qualified relations
and must include the compatibility relation. `teardown_set` is an exact
catalogue-edge set, not a count.

A source reference is one of two closed variants:

```text
{kind: "python_symbol", path: RepoPath, symbol: QualifiedPythonSymbol}
{kind: "document_section", path: RepoPath, anchor: NonemptyString}
```

The parser resolves the repository-relative path and symbol or section without
executing Python. Missing, unreadable, escaping, symlink-escaping, or unresolved
references fail closed.

Disposition is one of:

```text
{kind: "delete"}
{kind: "migrate_to_module", module_authority_id: AuthorityId}
{kind: "retain_product_record", authority_id: AuthorityId,
 reason: NonemptyString}
{kind: "temporary_projection", projection: ProjectionContract}
```

Projection variants are closed:

```text
ordinary view:
  {kind: "ordinary_view", derivation, provenance, freshness,
   retirement_condition}
stored projection:
  {kind: "stored", derivation, provenance, freshness, canonical_writer,
   drift_invariant, repair_path, retirement_condition}
```

A relation whose kind is `view` uses `ordinary_view`. A `table`,
`materialized_view`, `cache`, or `read_model` temporary projection uses
`stored`; a materialized view's refresher is its canonical writer. Every
temporary projection carries a non-null deletion contract. A retained
independent product record remains explicit; relabelling it does not discharge
a prior deletion claim.

`delete`, `migrate_to_module`, and `temporary_projection` require a deletion
contract. `retain_product_record` requires `deletion: null`. A deletion's
`owner_lineage` must equal the relation's owning product or assembly lineage;
the module lineage never deletes a relation it does not own.

Exactly one `current_authority_id` references a current `AuthorityContract` for
the protected resource. Its current writer source path is among that contract's
`canonical_writer_paths`, and the observed canonical-decision-writer set must
equal it. `legacy_active` therefore permits one specifically bound current
legacy writer while migration is staged; `target_module_authority_id` is a
stable future id, not a second current authority declaration. Baseline
membership alone never authorizes a writer.

Once `module_active`, the current authority and writer are the module owner.
The displaced authority and writer resolve against `historical_profile` at its
immutable commit, not against current source that successful retirement removes.
The activation record is non-null, and every current local decision writer,
reverse feed, and fallback writer is forbidden; only the declared writer or
refresher of a stored temporary projection may remain. A
`migrate_to_module.module_authority_id` must equal the legacy state's target id
and the module-active state's current id.
`source_state: drained` and every requested deletion gate require
`authority_transition.state: module_active`; `pre_drop` and `post_upgrade`
additionally require `source_state: drained`. This preserves ADR 0017's
distinction between authority activation and migration completion without
making every in-progress migration permanently non-conformant.

Each static edge carries `kind`, repository-relative `path`, qualified `symbol`,
`target`, a SHA-256 fingerprint of a versioned normalized syntax tree, and a
nullable `consumer_id`. Kinds are `local_decision_writer`,
`compatibility_writer`, `reverse_feed`, `fallback_writer`, `reader`, `caller`,
`import`, `orm_relationship`, `dependency`, `repair_job`, `refresh_job`, and
`consumer`. A consumer edge's id must match the declared consumer set in both
directions. A line number may appear in a diagnostic; it is never durable
identity. Static identity is the tuple `(kind, path, symbol, target,
consumer_id)`; its fingerprint is compared content, not part of identity.

Each catalogue edge carries `kind`, deterministic natural-key `identity`, and
`definition_sha256`. Kinds are `foreign_key`, `constraint`, `trigger`, `grant`,
`column_grant`, `dependent_relation`, `function`, `refresh_object`, and
`other_dependency`. PostgreSQL OIDs are forbidden as identity. A definition
change under the same identity changes its fingerprint. Unknown fields and
duplicate identities are rejected everywhere; booleans are never integers.
Catalogue identity is `(kind, identity)`; `definition_sha256` is compared
content, not part of identity.

Version 10 is superseded, not withdrawn. Its measurements are not reinterpreted
or defaulted. The parser reads `schema_version` before applying the
version-specific exact-key contract and gives v10 profiles one stable migration
diagnostic: declare `compatibility_retirements` and `retirement_history`, then
move to v11. Existing products remain on their immutable Governance pin until
their own reviewed enrollment changes both pin and profile.

`retirement_history` is the permanent reservation ledger that makes activation
one-way. Each closed entry is:

```text
{retirement_id, relation_identity, displaced_authority, current_authority_id,
 activation_record, closure_record}
```

`closure_record` is disposition-specific:

```text
deleted:
  {kind: "deleted", post_upgrade_observation}
retained product record:
  {kind: "retained_product_record", repository, commit, path, sha256,
   authority_id, reason}
```

The deleted form carries the full immutable coordinates of the linked
`target_retirement_observation` post-upgrade record. The retained form carries
an immutable product record establishing the relation's distinct business
purpose and owner and the removal of its displaced decision authority; it
invents no deletion observation. History entries are append-only and
byte-stable: they are never edited, removed, or reclaimed. After the applicable
closure is accepted by its external authorization owner, the active retirement
moves to this ledger in the same reviewed profile change. The old retirement id
and relation identity can never be enrolled again.

For active records, `legacy_active -> module_active` and `draining -> drained`
are one-way transitions. The action supplies the trusted pull-request base SHA
or push-before SHA; the engine loads the prior profile at that exact revision
and rejects a reversal, deletion without a matching history append, id rename,
or relation rename that attempts to evade the transition. A local CLI must
receive `--base-revision` for a history-sensitive change. If the declared base
cannot be read, the transition check fails closed. These checks establish the
evaluated revisions' declared authority arrangement; they do not prove which
revision is deployed.

### 2. Observations are generated, separate records

Current observations are never committed into the profile they claim to
evaluate: adding the observation would change the commit it names. A product
collector instead generates `RetirementObservationBundle.v1` and supplies it to
the Governance action or CLI. The input is optional only when
`compatibility_retirements` is empty; every enrolled slice requires exactly one
observation.

```text
RetirementObservationBundle.v1:
  schema_version: 1
  repository: CanonicalRepository
  product_revision: FullGitSha
  governance_revision: FullGitSha
  producer_id: Slug
  normalization_version: "python-ast-v1"
  observations: RetirementObservation[]

RetirementObservation:
  retirement_id: Slug
  source_inventory:
    coverage: "measured" | "unmeasured"
    measured_kinds: StaticEdgeKind[]
    edges: StaticRetirementEdge[]
    canonical_decision_writers: SourceRef[]
    unavailable_regions: RepoPath[]
  migration_database: ProductRevisionEvidence | null
  deployed_target: TargetRetirementEvidence[]
```

The bundle binds to trusted checkout and action context, not only to strings it
supplies. Unknown, duplicate, or missing retirement ids fail. `measured`
coverage cannot carry unavailable regions; `unmeasured` cannot establish zero.
`measured_kinds` must equal the closed static-edge vocabulary before coverage
can be `measured`, and the bundle normalization version must equal the declared
collector version. An unsupported family is unmeasured, never a
product-authored exclusion.

`ProductRevisionEvidence` uses ADR 0013's `product_revision_check` coordinates
and adds the observed catalogue edges, named admission-check results, and
`transaction_attempts`. Each attempt is a closed record containing `scenario`
(`lock_contention`, `inventory_mismatch`, or `drop_restrict_dependency`),
`transaction_outcome`, `refusal_stage`, `catalogue_coverage`, observed
catalogue edges, and its named check results. It describes a repository-built
migration database, never a deployed target.

Each `TargetRetirementEvidence` uses ADR 0013's
`target_retirement_observation` coordinates and adds observed catalogue edges
plus `catalogue_coverage: measured | unmeasured` and named check results.
Records form a phase-linked list with consistent target, product revision,
image digest, Governance revision, and deletion migration. Pre-drop evidence
cannot substitute for the fenced or post-upgrade phase. `transaction_outcome`
is `null` for pre-drop and post-upgrade; it is required for atomic teardown.
`refusal_stage` is null except on a refused or rolled-back atomic attempt, where
it names `fence_acquisition`, `inventory_validation`, or `teardown`.
Post-upgrade may follow only `committed`.

A check result is exactly:

```text
{check_id: RetirementCheckId,
 outcome: "pass" | "fail" | "unknown",
 evidence_selector: NonemptyString}
```

There is no summary `passed` boolean and no caller-selected `not_applicable`.
The evaluator derives applicability from the relation, projection, deletion
contract, and requested phase. The closed check vocabulary is:

- `source_edges_zero`, `consumers_zero`,
  `writers_absent_or_exact_teardown`,
  `catalogue_matches_reviewed_teardown`, `projection_fixed_point`,
  `archival_exit_settled`, `external_clients_exited`,
  `old_processes_drained`, `old_process_restart_prevented`, and
  `deletion_lineage_owned`;
- `exclusive_nowait_fences_held`, `inventory_rechecked_under_fence`,
  `teardown_in_dependency_order`, `drop_restrict_used`, and
  `failure_rolls_back_without_partial_teardown`; and
- `post_upgrade_objects_absent`, `owner_paths_pass_without_fallback`, and
  `intended_revision_running`.

Applicability is exact:

| Evidence | Required checks |
| --- | --- |
| Product-revision admission | `source_edges_zero`, `consumers_zero`, `writers_absent_or_exact_teardown`, `catalogue_matches_reviewed_teardown`, `deletion_lineage_owned` |
| Product lock-contention sabotage | `failure_rolls_back_without_partial_teardown`; refusal stage is `fence_acquisition` and catalogue coverage is `unmeasured` |
| Product inventory-mismatch sabotage | `exclusive_nowait_fences_held`, `inventory_rechecked_under_fence`, and `failure_rolls_back_without_partial_teardown`; refusal stage is `inventory_validation`, and no drop or teardown-order result is present |
| Product `DROP RESTRICT` sabotage | `exclusive_nowait_fences_held`, `inventory_rechecked_under_fence`, `teardown_in_dependency_order`, `drop_restrict_used`, and `failure_rolls_back_without_partial_teardown`; refusal stage is `teardown` |
| Target pre-drop | Product-revision admission checks plus applicable `projection_fixed_point`, `archival_exit_settled`, `external_clients_exited`, `old_processes_drained`, and `old_process_restart_prevented` |
| Target atomic, committed | `exclusive_nowait_fences_held`, `inventory_rechecked_under_fence`, `catalogue_matches_reviewed_teardown`, `teardown_in_dependency_order`, and `drop_restrict_used` |
| Target atomic refusal at fence acquisition | `failure_rolls_back_without_partial_teardown`; catalogue coverage is `unmeasured`, because the fence needed for a safe observation was never acquired |
| Target atomic refusal at inventory validation | `exclusive_nowait_fences_held`, `inventory_rechecked_under_fence`, and `failure_rolls_back_without_partial_teardown` |
| Target atomic refusal or rollback during teardown | `exclusive_nowait_fences_held`, `inventory_rechecked_under_fence`, `teardown_in_dependency_order`, `drop_restrict_used`, and `failure_rolls_back_without_partial_teardown` |
| Target post-upgrade | `post_upgrade_objects_absent`, `owner_paths_pass_without_fallback`, `intended_revision_running`, `old_processes_drained`, and `old_process_restart_prevented` |

`projection_fixed_point` is required only for stored projections. Pre-drop
always requires all four exit checks: a `required` condition proves settlement,
while a `not_applicable` condition proves the reviewed reason no obligation
exists. Post-upgrade always repeats process-drain and restart-prevention. Each
condition maps to exactly one check, and omission is a failure. A caller cannot
label any derived requirement inapplicable.

Every refused or rolled-back attempt proves no partial teardown and is
ineligible as a post-upgrade predecessor. Operations after its `refusal_stage`
are absent rather than falsely reported as passing. `catalogue_coverage:
unmeasured` never means an empty catalogue and cannot establish any zero or
exact-set claim. Pre-drop, committed atomic, inventory-validation refusal,
teardown refusal, and post-upgrade records all require measured catalogue
coverage.

### 3. Governance owns comparison, not collection or authorization

Governance supplies one pure evaluator. Products own source and catalogue
collectors, their migration-database fixtures, the actual fenced transaction,
and all target access. The evaluator:

1. compares observed and declared static identities as exact sets;
2. compares catalogue identities using phase-specific exact sets: ordinary
   observations use `catalogue_baseline`; deletion preflight and the fenced
   inventory use the immutable reviewed `teardown_set`; post-upgrade requires
   an empty set;
3. reports observed-minus-baseline additions, baseline-minus-observed stale
   entries, and same-identity fingerprint changes;
4. refuses equal-count identity substitutions;
5. after `module_active`, rejects local decision writers, reverse feeds, and
   fallback writers even if a baseline includes them;
6. permits only the declared canonical writer or refresher for a temporary
   stored projection;
7. requires zero relevant edges, zero consumers, and measured source coverage
   for `source_state: drained`;
8. requires applicable product-revision checks and correctly ordered target
   observations before a requested gate can be structurally consistent;
9. compares the inventory taken under the exclusive fence with the reviewed
   teardown set and requires refusal on any difference; and
10. requires linked post-upgrade evidence after a committed atomic observation,
    zero residual objects, drained old processes, and the intended revision
    running before a post-upgrade request is consistent.

The reviewed teardown set is bound unchanged across pre-drop, fenced, and
post-upgrade records. Its authorized removal is an explicit state transition,
not an unreviewed decrease of `catalogue_baseline`; a successful post-upgrade
observation therefore compares with the required empty set and does not emit a
stale-baseline finding for objects the reviewed transaction removed.

The evaluator establishes ordering and refresh obligations, not actual
freshness. `pre_drop` maps to `refresh_before: cutover_authorization`,
`atomic_teardown` to `fenced_teardown`, and `post_upgrade` to
`completion_claim`; timestamps increase through the linked chain. The named
authorization system must re-observe as required and decide whether an
observation is fresh enough before acting. Timestamp presence alone never
establishes freshness.

Reports expose three qualified verdicts:

```text
repository_contracts: pass | fail
product_revision_evidence: not_supplied | consistent | inconsistent
target_evidence: not_supplied | consistent | inconsistent
```

They also enumerate enrolled retirement ids. They never emit
`deletion_authorized`, `migration_complete`, or an unqualified completion
verdict. Structural consistency of supplied target evidence is not proof that
Governance observed the target or authenticated the producing run.

### 4. Stable diagnostics and sensitivity cases

Malformed shapes remain `profile.invalid`. Semantic failures use these stable
codes:

- `retirement.surface.duplicate`;
- `retirement.source.unmeasured`;
- `retirement.static.added`, `.stale`, and `.changed`;
- `retirement.catalogue.added`, `.stale`, and `.changed`;
- `retirement.authority.conflict`;
- `retirement.history.changed`;
- `retirement.writer.forbidden`;
- `retirement.projection.invalid`;
- `retirement.deletion.lineage-mismatch`;
- `retirement.gate.nonzero`;
- `retirement.evidence.missing`, `.binding-mismatch`, and `.unknown`;
- `retirement.teardown.inventory-mismatch`; and
- `retirement.completion.unsupported`.

Every message names the retirement id, the affected identity or check, and the
direction of drift. Missing target evidence is not an error while a slice is
merely `draining` with `requested_gate: none`; it blocks a requested deployed
gate.

Governance synthetic fixtures must demonstrate: a planted caller; a caller
removed while its baseline remains; a baseline lowered while its caller
remains; equal-count identity substitution; a changed fingerprint; a second
writer or reverse feed; added and removed catalogue dependencies; invalid view
and stored-projection contracts; a pre-drop request with live consumers;
migration-database evidence supplied as target evidence; wrong revision,
target, phase link, refresh owner, or required-check outcome; and an empty
bundle for an enrolled slice. Premature completion must fail for each distinct
shape: a post-upgrade request with a residual object, a restartable old process,
no committed atomic predecessor, or an intended revision not reported running.
Separate cases remove each mandatory exit-condition disposition, restore a
legacy authority state after module activation, rename the retirement id or
relation to evade that history, and remove or edit an append-only history row.
Refusal cases stop at fence acquisition, inventory validation, and teardown so
the evaluator proves only operations actually reached and always proves no
partial change.
Unknown profile keys such as `migration_complete`, `deletion_ready`, or
`deletion_authorized` are `profile.invalid`; `retirement.completion.unsupported`
is reserved for a post-upgrade request that supplies only repository or
migration-database evidence and therefore cannot establish deployed completion.

Synthetic catalogue data proves the comparator only. The first enrolled
product must use its real migration-database collector to exercise a conflicting
relation lock, an inventory mismatch that stops before teardown, and a separate
unexpected dependency that reaches and is refused by fenced `DROP ... RESTRICT`.
Each refusal proves no partial grant, function, trigger, or relation removal. A
Governance-only fixture cannot claim that database behavior.

### 5. First adoption and completion boundary

The first enrollment candidate is `dotmac_sub`, because the programme already
identifies its two-directional cohort-writer ratchets. No relation is selected
by name alone. Its separate adoption change must provide an immutable Sub
revision, one exact compatibility relation and authority, both static ratchet
arms, the relation-owning lineage and deletion migration, its real catalogue
collector, successful admission, refusals at all three stages — fence
acquisition, inventory mismatch, and `DROP RESTRICT` — no-partial-teardown
evidence, and the exact Governance action pin.

If Sub cannot supply that bounded slice, enrollment stops rather than declaring
an empty adoption; ERP is inventoried as the next candidate. Governance
implementation plus synthetic tests does not close issue 33. Closure also
requires exact hosted CI for the merged engine and one real product enrollment
without copied policy.
