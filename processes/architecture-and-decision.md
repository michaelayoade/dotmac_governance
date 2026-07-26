# Architecture and decision

- Status: Proposed
- Date: 2026-07-26
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Classification: Internal
- Model version: 0.1.0

## Purpose

Give every business decision, state transition, derived value, and side effect
exactly one named owner, and make a change of owner an explicit, staged,
reversible event rather than something that happens gradually and is noticed
afterwards.

The failure this prevents is not a bad decision. It is two systems that both
believe they decide the same thing, each correct in isolation, disagreeing only
under load or after a partial failure — at which point neither the code nor the
records can say which one was authoritative.

This process makes the source-of-truth standard already operating in
`dotmac_sub` explicit and applicable across the governed scope. It is a
consolidation of existing practice, not a new requirement.

## Standards mapping

Identifiers and Dotmac's interpretation only. No standard text is reproduced.

| Standard | Identifier | Status |
| --- | --- | --- |
| ISO/IEC/IEEE 12207:2026 | — | **Unmapped.** Licensed access is not yet in place; the process identifier is not guessed. Recorded as a known gap per ADR 0002. |
| ISO/IEC 27001:2022 | A.8.27, A.8.28, A.5.2 | **Provisional.** Identifiers believed applicable to architecture ownership, adapter discipline, and role assignment. Unverified against licensed text. |
| ISO/IEC 42001:2023 | — | **Unmapped.** Licensed access is not yet in place. |

Dotmac's interpretation, independent of any mapping: an architectural decision
is a security-relevant act, because an unowned decision boundary is where
authorization, validation, and audit are silently skipped by whichever caller
gets there first.

The mapping is completed when licensed copies are obtained. Until then this
process is enforced on its own terms; the mapping adds traceability, not
validity.

## Inputs

- A proposed change that creates, moves, or removes a decision boundary.
- The affected repository's relationship map or equivalent ownership record.
- Existing ADRs touching the same boundary.

### When this process is triggered

Any one of these:

- A business decision, state transition, or lifecycle rule gains or changes its
  owning service.
- A derived field, cache, external projection, or side effect gains a writer.
- An external system begins supplying or consuming operational state.
- A reconciler, importer, or resolver is added or changes what it repairs.
- An ownership boundary moves between services, repositories, or organizations.

Routine feature work inside an existing, already-owned boundary does **not**
trigger it. The test is whether the change alters *who decides*, not whether it
alters behaviour.

## Activities

1. **Name the owner.** One service or system owns the decision. If the answer
   is "both" or "it depends on the caller", that is the finding, and the work
   is to resolve it before proceeding.
2. **Separate observation from decision from consequence.** Collectors and
   importers write facts. Resolvers derive state. Policy and event services
   decide consequences. Reconcilers project the result. A component doing two
   of these is a boundary that has not been drawn yet.
3. **Keep adapters thin.** Routes, web handlers, jobs, webhooks, commands, and
   delivery integrations carry no decision logic. They call the owner.
4. **Assign one canonical writer** to every derived field, cache, projection,
   and side effect. Other callers change source state or request
   reconciliation; they do not maintain a parallel path.
5. **Treat external systems as transports.** A collaboration or delivery system
   is not a decision system, and an imported identifier is not the only copy of
   truth.
6. **Make reconcilers idempotent** and able to repair drift from authoritative
   inputs.
7. **Stage any migration of authority** — see below.
8. **Finish one coherent slice.** Name the owner, migrate the highest-risk
   callers, remove or gate parallel paths, add architecture and behaviour
   tests. A half-migrated boundary is worse than an un-migrated one, because it
   looks resolved.

### Migration of authority

Moving ownership requires all of: the old owner, the new owner, a shadow or
verification phase, a cutover gate, retirement of the fallback, and tests
proving the boundary holds. A migration that omits fallback retirement has not
moved authority; it has added a second authority.

## Outcomes

- The decision has one named owner, recorded where the affected repository
  keeps its ownership record.
- Parallel decision paths are removed or explicitly gated with a retirement
  date.
- Divergence is detectable by a test rather than by an incident.

## `required_information_items`

| Item | Location | Content expectation |
| --- | --- | --- |
| Architecture decision record | `docs/adr/` in the affected repository; `dotmac_governance/docs/adr/` when organization-wide | The controlled ADR contract, including `Drift prevention`. Required when the change is expensive to reverse: an ownership boundary, a control interpretation, an authority assignment, or a cutover plan. |
| Ownership record entry | The repository's relationship map — `docs/SOT_RELATIONSHIP_MAP.md` in `dotmac_sub` | The decision, its owning service, its canonical writer, and its reconciler where one exists. |
| Authority migration plan | The ADR that authorizes the migration | Old owner, new owner, shadow phase, cutover gate, fallback retirement, and the tests proving the boundary. Required only for a migration. |
| Deviation declaration | The repository's `.governance.yml` | Owning Issue and expiry date. Required only when this process is not followed. |

An architecture change that needs no ADR — because it is neither expensive to
reverse nor an ownership change — still updates the ownership record if it adds
a writer. The ADR trigger and the record trigger are not the same trigger.

## `work_products`

Source, adapters, resolvers, reconcilers, schemas, migrations, and architecture
tests. Governed by this process; **not** subject to any information-item
requirement. No validator may demand that these take a documentary shape.

## Approval gate

| Scope | Approver | Attributable event |
| --- | --- | --- |
| Repository-local boundary | The repository's named technical owner / CODEOWNER | Pull request approval |
| Organization-wide boundary, or any cross-repository ownership move | Michael Ayoade | Pull request approval on `dotmac_governance` |

An ADR is `Proposed` until that approval occurs. A `Proposed` ADR never
authorizes an action — including the action it describes.

## Effectiveness verification

Per ADR 0002, a separate verifier is required only where this process declares
it. This process declares it in exactly one place:

- **Authority migration cutover.** A cutover that silently fails leaves two
  authorities and no signal. It requires a named human, different from the one
  who performed the migration, to verify that the fallback is retired and the
  boundary tests fail when the boundary is violated.

- **All other architecture activity:** no separate verifier. The architecture
  tests and the ADR's own `Drift prevention` section are self-evidencing.

**Declared gap:** the cutover verifier is currently **unnamed**. Every change
arrives under one account, and no second human is available to hold the role.
By ADR 0002's own rule this makes the process definition incomplete, and the
incompleteness is confined to authority-migration cutovers — those cannot be
declared complete under this process until the role is filled. Ordinary
architecture work is unaffected.

This is recorded rather than resolved by naming a nominal verifier, which is
the failure mode ADR 0002 narrowed the rule to avoid.

## Agent participation

An agent **may**: draft an ADR from source-linked facts; identify unowned
decisions, parallel decision paths, and adapters carrying decision logic;
propose an owner with reasoning; draft a migration plan; and report that a
boundary lacks a test.

An agent **may not**: assign ownership; approve an ADR; declare a migration
complete; retire a fallback; or state that a boundary is correct. Two agents
agreeing is not a second opinion in any sense this process recognises.

## Enforcement

| Mechanism | Kind | Covers |
| --- | --- | --- |
| `check_adrs.py` in the affected repository | CI | ADR structure, controlled metadata, declared relationships |
| Repository architecture tests — `tests/architecture/` in `dotmac_sub` | CI | Adapter thinness and boundary violations, where written |
| CODEOWNERS review on paths owning decisions | CI (branch protection) | That the named owner saw the change |
| Trigger judgement — whether a change alters *who decides* | **Manual — Michael Ayoade** | Whether this process applied at all |

The trigger is the honest weak point. No check can currently detect that a
change moved a decision boundary without saying so; that judgement is manual
and named, which is what the enforcement rule requires. Narrowing it is the
first candidate for the derived validator: a change touching a path listed in
the ownership record can require an explicit statement that ownership did or did
not move.

## Declaration

Input to the derived `.governance.yml` schema. Expect this shape to change once
a second and third process exist — that is the intended order.

```yaml
process: architecture-and-decision
model_version: 0.1.0
status: proposed
triggers:
  - decision_owner_change
  - derived_writer_added
  - external_state_source_change
  - reconciler_change
  - ownership_boundary_move
required_information_items:
  - id: adr
    location: docs/adr/
    condition: expensive_to_reverse
  - id: ownership_record_entry
    location: repository_relationship_map
    condition: writer_added_or_changed
  - id: authority_migration_plan
    location: authorizing_adr
    condition: ownership_boundary_move
approval:
  repository_local: codeowner
  organization_wide: michael_ayoade
effectiveness_verification:
  required_for: [authority_migration_cutover]
  verifier: null          # declared gap — see above
enforcement:
  ci: [check_adrs, architecture_tests, codeowners_review]
  manual:
    - control: trigger_judgement
      owner: michael_ayoade
```

`verifier: null` is deliberate and must fail a completeness check for the
activity it gates. A schema that accepts a missing verifier silently would
reproduce the standing-role problem ADR 0002 removed.
