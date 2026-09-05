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
