# 0006. Cross-repository engineering conformance control plane

- Status: Accepted
- Date: 2026-08-03
- Effective: 2026-08-03
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories
- Classification: Internal

## Context

Dotmac's strongest engineering controls are currently implemented separately in
product repositories. Starter rejects unguarded routes and untyped payloads;
Sub checks feature and source-of-truth boundaries; ERP carries finance and
tenant-specific canaries; the kernel owns shared runtime contracts. Domain
behavior belongs locally, but organization-wide standards should not require
each product to reinvent rule schemas, finding codes, CI output, and rollout.

Prose alone cannot enforce "fully typed contracts" or "one canonical writer".
It cannot identify exact boundary paths, refuse `Any`, distinguish immutable
wire evidence from mutable ORM state, or detect two owners claiming one
resource. ADR 0001 already assigns organization-wide governance records to
this repository, CI to evidence production, Knowledge to discovery, Issues to
corrective actions, and local technical decisions to affected repositories.
ADR 0005 implements the same pattern for agent configuration, but is purposely
limited to one non-production endpoint and is not a product-code checker.

Michael directed on 2026-08-03 that `dotmac_governance` own cross-repository
policy and enforcement, and subsequently directed activation after the source
identity controls were merged. The acceptance record below preserves that
approval separately from the agent-authored implementation.

## Decision

### Ownership

`dotmac_governance` owns the organization-wide engineering rule catalogue,
strict repository profile/schema, stable diagnostics and report contracts,
development-only `standards_control` engine, activation criteria, rollout
order, and future waiver contract.

The boundary stays one-way:

- `dotmac-kernel` owns reusable runtime business and wire contracts;
- `dotmac-ui` owns presentation primitives and UI contracts;
- product repositories own domain decisions, services, migrations, and local
  ADRs;
- product CI owns results for its revision; and
- Knowledge projects discovery pointers, never policy or evidence.

Products consume the checker only in development and CI. Application runtime
code must not import it.

CI distribution uses the repository's composite `standards-check` action pinned
to an exact accepted Governance commit. Products do not copy the engine or
follow a mutable branch/tag. The action calls the one engine against the caller
workspace; local development uses the same CLI.

### Typed profile and activation

An enrolled repository carries `.dotmac/standards-profile.json`. A strict,
immutable parser and matching JSON schema reject missing, unknown, ambiguous,
absolute, and parent-traversing values. The profile names canonical Git URL and
default branch, governing ADR/status, enforcement mode, protected authorities,
and exact typed contract surfaces. CI passes the trusted repository default
branch from event metadata; local checks use `origin/HEAD` when available.

Schema version 2 has two closed governance-source variants. `local` is admitted
only when the evaluated repository is the canonical `dotmac_governance`
control plane. Every product uses `pinned`, naming that canonical repository,
an exact lower-case 40-character Git revision, the ADR path, and status. The
composite action reports its actual `github.action_repository` and
`github.action_ref` plus its source root; missing or mismatched identity fails.
A product cannot authenticate copied policy prose from its own tree, another
repository, or a mutable Governance branch/tag.

`candidate` proves internal consistency but is not normative. `required` is
representable only with an `Accepted` checked-in governance source. A green
candidate is never described as activated policy or compliance.

### Initial ownership gate

Every protected resource in profile scope has exactly one authority record: one
owner component and implementation, one typed decision interface, canonical
writer paths, thin adapter paths, and drift tests. The owner must be a writer;
an adapter cannot also be a writer; paths and the interface must exist; and a
resource cannot appear under two authorities.

This validates ownership declarations, not exhaustive framework-specific write
discovery. Product drift tests still prove actual business behavior. A generic
checker must not claim it can recognize every ORM or SQL write.

### Fully typed contract gate

Every new or changed wire, command, event, acknowledgement, configuration,
policy, and public service-boundary contract is added to a typed surface. The
initial gate can require:

- all public parameters and returns annotated;
- no `Any` and no bare container annotations;
- all record fields annotated; and
- immutable dataclass and Pydantic boundary records.

This targets semantic boundaries, not ORM models or incidental locals. Money,
digest, identity, version, status, and timestamp values use closed types,
enums, frozen dataclasses, or strict Pydantic records appropriate to their
runtime. Mypy strict remains complementary.

### Enforcement roadmap

Further reusable gates land in risk order, each with stable diagnostics and a
known-bad sabotage proof: transaction/outbox authority; tenant/RLS/cache
isolation; migration namespaces/grants; authenticated admission and actor
provenance; idempotency/replay/locking/retry/concurrency; secret and signing-key
custody; exact money/currency/digest/version boundaries; compatibility floors,
zero-skip canaries and release identity; then configuration ownership and
reusable defaults.

A rule is extracted only with the same contract, a named owner, a migration
path, and a detector that fails under sabotage. Similarity is insufficient.
Schema version 2 has no waiver field. A future waiver mechanism requires a
separate accepted decision and at least a named owner, Issue, scope, rationale,
expiry, and shrink-only review.

## Consequences

- One engine can enforce structural standards across Sub, ERP, starter, vendor,
  kernel and later products while domain ownership stays local.
- The control-plane profile validates this repository in required mode.
  Product activation additionally needs a pinned profile, green product CI,
  and protected-branch configuration.
- Explicit inventories add review friction and make undeclared scope visible.
- Product-specific canaries remain necessary; the ownership gate does not
  overclaim exhaustive source analysis.
- Existing products may initially fail later rules. Rollout inventories and
  repairs them instead of weakening the standard.

## Drift prevention

- Strict schema/parser checks and closed enums reject malformed profiles and a
  Proposed source cannot select required mode.
- Immutable reports use stable diagnostic codes.
- Known-bad tests cover duplicate ownership, owner/adapter overlap, owner not in
  writer set, missing paths/interfaces, URL/branch/status drift, `Any`, missing
  and bare annotations, and mutable dataclass/Pydantic records.
- The checked-in required profile uses the production engine; CI has no second
  decision path.
- A temporary removal of duplicate-resource detection makes its canary fail.
- Product activation requires local profile, CI job, required-check readback,
  and source-linked behavior canaries. Central CI cannot attest a product SHA.
- Governance CI exercises the same composite action products consume, so a
  broken distribution adapter cannot hide behind direct engine tests.
- Future rules require their own stable findings and sabotage proof.

## Acceptance record

On 2026-08-03, Michael Ayoade explicitly approved activation after the product
source-identity hardening was merged in Governance PR 10. This amendment makes
the local profile required and this ADR effective when the acceptance change
reaches canonical `main`. Agent-authored code and records remain distinct from
the named human approval recorded here.
