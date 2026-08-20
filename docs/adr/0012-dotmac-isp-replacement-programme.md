# 0012. The Dotmac ISP replacement is one controlled programme

- Status: Proposed
- Date: 2026-08-20
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Dotmac ISP replacement across Governance, Starter, Sub, the future target assembly, and participating product sources
- Classification: Internal

## Context

Dotmac's accepted engineering direction makes products thin assemblies over
independently released Starter owners. Legacy `dotmac_sub` still owns the
production ISP runtime and database. Starter now contains or audits many of the
replacement owners, but package construction has moved faster than real
adoption: a package can be merged, green and even released while no product has
composed it, moved data, switched authority or retired the displaced writer.

The replacement spans multiple repositories and cannot be governed by a plan in
any one product. Starter's fleet decomposition matrix is the measured evidence
base and its ADRs own technical boundaries. It explicitly assigns the programme
matrix and approvals to Governance. Knowledge records aid discovery but are not
the programme record. Without one stable-ID matrix, branches can silently use
different cohort names, count package completion as adoption, start a later
cohort before its dependencies, or claim a cutover without naming the exact
evidence that sealed it.

Michael named `https://github.com/michaelayoade/dotmac-isp` as the canonical
target repository in the 2026-08-20 working session. Its candidate runtime is
the independent `asm-dotmac-isp` thin assembly and its database boundary is
independent. The production deployment owner remains unassigned; naming a
repository does not authorize a host or a cutover. The programme must not force
a false choice between constructing that target and preparing Sub for a safe
cutover: both are required, and each has different evidence. Accepting that
coordinated direction still requires an attributable GitHub approval record;
this proposed record and matrix preserve that open control rather than treating
an agent-authored source update as approval evidence.

## Decision

If accepted, Governance owns the programme identity
`pgm-dotmac-isp-replacement`, its stable control/cohort/decision identifiers,
ordering, approval state and references to controlled evidence. The canonical
record is
[`programmes/dotmac-isp-replacement.json`](../../programmes/dotmac-isp-replacement.json).
Changing a stable identifier's meaning is forbidden; a replacement identifier
and explicit history are required.

Governance does not become an application or domain owner. Starter continues to
own reusable implementation, module composition contracts, measured fleet
inventories and technical ADRs. Legacy Sub remains authoritative until a
cohort-specific sealed switch. The future Dotmac ISP assembly will own its own
runtime, database, migrations, sessions and authorization. It shares no Sub
tables, ORM models, sessions or transactions.

The programme has two declared tracks that may advance concurrently:

1. `track-isp-target-build` constructs, releases, composes and verifies the
   independent `asm-dotmac-isp` target runtime and database.
2. `track-isp-sub-cutover` makes `asm-dotmac-sub-legacy` cutover-ready by
   completing source dispositions, idempotent replay, bounded shadow
   comparison, sealed cohort switches and displaced-writer retirement.

Concurrent work does not create concurrent production authority. For each
cohort, Sub remains the sole production decision and write owner until the
sealed switch. Shadow paths record and compare observations only; they do not
decide lifecycle state or feed production consequences. After the switch, the
Dotmac ISP assembly is the sole authority for that cohort and the displaced Sub
writers and fallbacks must ratchet to zero.

Selective in-place module adoption inside Sub is allowed only as bounded
source-track work: containment, evidence repair, migration or shadow adapters,
or an explicitly justified change that retires one local parallel writer. It
does not count as target adoption or a cohort cutover. If the same installable
module is composed by Sub and Dotmac ISP, each application runs its own pinned
copy and lineage and owns separate rows in its own database; neither application
shares the other's module tables.

The programme uses eight ordered cohorts:

1. foundation, Party and Customers;
2. acquisition, qualification, Sales, Orders and Subscriptions;
3. the network suite as one sealed cohort;
4. Fulfillment, activation and service lifecycle;
5. Usage, rating, Billing, Collections and service-access policy;
6. communication, Ticketing, support operations and Workforce;
7. retained Sub vNext parity capabilities; and
8. analytics adjudication, final reconciliation and legacy retirement.

The matrix assigns every named component to one cohort so a capability cannot
appear complete in two parallel programme lanes. A component's `build`,
`release`, `adopt`, `reuse`, `adjudicate` or `retire` disposition is the required
programme action, not a claim about its current implementation state. Starter's
exact source audits remain authoritative for that state.

Every cohort is blocked by the same cutover controls: human approval; a named
target assembly; an enforced legacy transition rule; immutable releases and
exact pins; real target catalog/runtime proof; complete source-row dispositions
and idempotent replay; complete-cohort shadow comparison at an immutable
watermark; a sealed one-writer switch with rollback conditions; and a
bidirectional old-writer/fallback ratchet reaching zero before rollback closure.

Shadowing is bounded verification, not a second authority. Unknown source facts
remain typed quarantine with consequences disabled. A copy, green suite,
published package or deployed target never advances an authority state on its
own. Each verified control cites an immutable controlled-source reference; an
agent-authored assertion is not evidence.

## Consequences

- This record and matrix are non-normative while `Proposed`. Every control and
  cohort remains blocked; no authority, deployment or data changes.
- Governance gains one programme state instead of a competing implementation
  plan. Product technical facts stay in product repositories and are cited by
  exact revision.
- The target-build track may construct a non-authoritative candidate in the
  named repository before a production deployment owner is assigned. It need
  not wait for Sub source-readiness, but no deployment or cohort authority can
  advance without that owner and the complete cutover-control set.
- The Sub cutover track is first-class programme work rather than legacy
  maintenance. Permanent new Sub domain logic remains barred; a separately
  approved transition rule may admit containment, evidence repair, migration or
  shadow adapters, and bounded in-place adoption that retires one local writer.
- Running both tracks in parallel shortens elapsed migration time without
  weakening the single-authority boundary.
- Referrals and Reseller Management remain constructed but unadopted. The seven
  other retained parity owners remain build work; Fleet Control reuses
  Deployment Control.
- Later progress changes the matrix in small reviewed slices. It does not edit
  this ADR into a false history of when approval or cutover occurred.

## Drift prevention

- `programme_control` rejects unknown fields, malformed or duplicate stable
  identifiers, missing or misbound source-cutover and target-construction
  tracks, dependency cycles, out-of-order cohorts, duplicate components,
  mutable external revisions, invalid authority identities and references to
  missing controls or cohorts.
- A `verified` control requires an immutable evidence reference. A proposed
  programme cannot claim any verified control, and an active cohort cannot
  precede the complete verified cutover-control set.
- Unit sensitivity tests introduce a missing track, a track bound to the wrong
  assembly, duplicate IDs, a dependency cycle, missing evidence, a mutable
  revision, duplicate component ownership, forward cohort dependency, an
  unknown block target and an unassigned target masquerading as assigned; each
  must fail.
- Governance CI validates every matrix. CI proves structural consistency for
  the evaluated revision; it does not approve the decision or declare a
  production cutover.
- Starter's technical replacement ADR must cite the immutable accepted
  Governance revision. Until that exists, conflicting local first-cutover
  statements remain unchanged and authoritative for their current scope.
