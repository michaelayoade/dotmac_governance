# 0012. The Dotmac ISP replacement is one controlled programme

- Status: Accepted
- Date: 2026-08-20
- Effective: 2026-08-20
- Owner: Michael Ayoade
- Approver: Michael Ayoade
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
cutover: both are required, and each has different evidence. Michael explicitly
accepted this coordinated direction on 2026-08-20 and authorized the acceptance
amendment. The accepted record approves the programme boundary; it does not
approve a deployment, data movement or cohort authority switch.

## Decision

Governance owns the programme identity
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

## Acceptance amendment — 2026-08-20

Michael Ayoade explicitly accepted ADR 0012 and authorized this lifecycle
amendment on 2026-08-20. Acceptance authorizes the two coordinated work tracks
and the stable programme/control/cohort identities. It moves no production
authority, assigns no deployment host, verifies no target catalog or replay,
and opens no cohort. The matrix records the immutable acceptance revision for
`ctl-isp-001`; every downstream control remains blocked on its own evidence.

## Ordering amendment — 2026-08-21

Michael Ayoade approved this ordering amendment on 2026-08-21. The approval
covers the two corrections and the capability-scope control below. It moves no
production authority, assigns no deployment host, verifies no target catalog or
replay, and opens no cohort; every cohort remains blocked on its own evidence,
and `dec-isp-005` through `dec-isp-007` remain open.

Two matrix defects were found and corrected. Neither changes the eight-cohort
shape, the acceptance record, or any authority state.

`dotmac-fulfillment` sat in cohort 4 while `dotmac-durable-timers`, which its
manifest names in `dependencies=("durable_timers",)`, sat in cohort 5. Every
cohort `depends_on` edge was intact and the matrix validated, because cohort
edges order the *switches* and nothing ordered the *capabilities*. Durable
Timers moves to cohort 4, and components may now declare `requires`, checked
against the cohort sequence. Same-cohort requirements are permitted: a cohort
is one sealed switch whose members cut over together.

`dotmac-work-orders` was assigned to no cohort at all. It is a built module
with a kernel ledger allocation (`prefix="wo"`, schema `mod_workorders`) and a
package on Starter main, so its absence was omission rather than a decision.
Physical execution of a dispatched job is distinct from the work structure
Projects owns, the saga coordination Fulfillment owns and the capacity and
routing decisions Workforce owns; it joins cohort 4 and is required by
Workforce in cohort 6.

The omission is the more general lesson: a dangling reference fails loudly
while an unclaimed capability fails silently, and no check reading the matrix's
own contents can see something that was never mentioned. The matrix therefore
declares `capability_scope` — the capabilities this programme is answerable for
— and every entry must be carried by exactly one cohort or hold a
retain/replace/retire disposition with a rationale in `capability_roster`.
Adding a module to the scope forces the question instead of letting silence
answer it, and the two sets may not overlap: a capability is disposed of in one
place, not two.

The eleven Starter packages previously absent from this matrix — Campaigns,
Documents, Records, Content, Publishing, Sites, Surveys, Media Observations,
Web Analytics, Procurement and Expenses — now carry explicit dispositions. Ten
are `retain` (available, with no ISP-owned authority in scope) and Campaigns is
`replace` (Sub owns outbound campaign execution today). A roster disposition
moves no authority and schedules no cutover; it records that the question was
answered. Media Observations is retained specifically because Michael paused
its adoption on 2026-08-18 and it must not enter a cohort while paused.

## Decision amendment — 2026-08-21: five open decisions answered

Michael Ayoade granted standing authority across the programme on 2026-08-21
and supplied the decision set below. Each is recorded here in prose and, in the
programme matrix, as a `resolved_decisions` entry citing this revision. The
matrix previously had nowhere to record a decision that was *made* —
`open_decisions` accepts only `state: "open"`, so resolving one meant deleting
it, discarding the answer, its owner and the revision proving when. That is the
same loss this record's own drift-prevention clause forbids, so the schema
gained `resolved_decisions` with mandatory immutable evidence.

**dec-isp-003 — legacy Sub transition rule. Approved.** No new cohort writer
and no growth of an existing one; bounded in-place module adoption is admitted
only when it retires a local writer. Enforcement is not a promise: the
two-directional cohort writer ratchets in `dotmac_sub` fail the build on an
added or grown writer, and on a removed writer whose baseline was not lowered
in the same change.

The control it blocks stays where it is. `ctl-isp-003` is programme-wide, and
those ratchets cover **cohort 1 only** — cohorts 2 through 8 have no writer
census at all, so the rule is approved and partly enforced rather than proved.
The same decision set makes controls and active authority cohort-scoped with
non-reusable evidence, and a cohort-1-scoped control is what this enforcement
can honestly verify. Until that scoping exists, the matrix keeps `ctl-isp-003`
`blocked`, and this record says so rather than claiming otherwise.

> Amended 2026-08-22. The first version of this paragraph ended "`ctl-isp-003`
> is verified on that basis" while the matrix left it `blocked`. Two controlled
> records disagreeing about one control is precisely what the drift-prevention
> clause below exists to stop, and nothing enforced it. `programme_control` now
> refuses an ADR that asserts a control state its own matrix contradicts.

**dec-isp-004 — analytics and reporting. Split into two owners.** Analytics
owns semantic measures and derived analytical datasets. Reporting owns saved
reports, execution, scheduling, exports and delivery. The `analytics-reporting`
placeholder is replaced in cohort 8 by `dotmac-analytics` and
`dotmac-reporting`, both `build`. There is no longer an unassigned
adjudication anywhere in the matrix.

**dec-isp-005 — three platform-plane modules. External.** Support Access,
Platform Health and Deployment Control remain Vendor-control-plane
dependencies consumed over versioned APIs. They leave cohort 7 and are rostered
`retain`. No supported platform assembly is introduced; `asm-dotmac-isp` keeps
`platform_surface_enabled=False` rather than growing a platform plane it would
then have to govern.

**dec-isp-006 — Inventory and Assets. ERP owns them.** ISP holds opaque
references only. Both leave cohort 3 and are rostered `retain`. ISP's network
stock and plant estate stay with the network modules that already own them, and
because ISP composes neither lineage the refused parallel-writer shape cannot
arise.

**dec-isp-007 — cohort-1 identity boundaries. Four owners.** Party owns
organization capacities, memberships and reachability. Customers owns the
account-to-Party binding. A new product-first `dotmac-addresses` owner owns
normalized address, geospatial data and verification history, and joins cohort
1 as `build`. Customers, Services and Billing hold typed purpose links to
address identities rather than copies of them. No product-owned link contract
is approved in place of a named owner.

### dec-isp-002 remains OPEN, and its question is narrowed

`selfcare.dotmac.io` was offered as the host on 2026-08-21 and is **refused as
stated**. It is the live `dotmac_sub` production host (`vmi3348415`) and the
compiled-in default API base URL of shipped field-mobile store builds, so it
names the system being replaced rather than an independent runtime — while
`ctl-isp-002` asks for a host operating the independent ISP runtime and its own
database.

The question now asks two things separately, because they have different
consequences and only one of them is a deployment decision:

1. which host runs `asm-dotmac-isp` and its own database; and
2. whether `selfcare.dotmac.io` is intended as the eventual cutover destination
   for customer traffic. That is not a DNS change: every installed field-mobile
   client resolves its API base to that name, so repointing it is a
   client-compatibility commitment that has to be sequenced against a mobile
   release.

`ctl-isp-002` therefore stays `blocked`, and cohort 1 with it.

## Conversion amendment — 2026-08-22: Sub is converted in place, not replaced

Michael Ayoade directed this amendment on 2026-08-22. It changes the programme's
**mechanism**, not its goal. Every earlier record above stands as written; this
section supersedes the specific clauses it names.

> **Retire legacy Sub implementations, not Dotmac Sub.**

### What changed

Dotmac Sub is **not** being retired. It remains the ISP product, runtime, API
identity, hostname and customer-facing application. What is being retired is its
monolithic domain implementations and its duplicate writers, as Sub itself
becomes the thin assembly.

The intended end state:

- `dotmac_sub` **is** the assembly.
- It pins `dotmac-kernel`, `dotmac-ui` and released domain modules.
- Modules run locally inside Sub and own their schemas, migrations, services
  and decisions.
- Existing Sub routes, UI and integrations become thin adapters.
- Each domain switches authority **internally**, from legacy Sub code to its
  module.
- Customers and mobile clients keep using the same product endpoints.

### What this makes irrelevant

Five requirements the replacement model carried are removed outright, and none
of them is deferred — the question stops applying:

- no separate `asm-dotmac-isp` production host;
- no second production database;
- no mobile API-base repoint;
- no cross-database sealing protocol;
- no external Sub-to-ISP synchronisation layer.

The `https://github.com/michaelayoade/dotmac-isp` walking skeleton is **frozen**.
It is not deleted — it is the record of a direction that was accepted and then
corrected — but no further construction happens there, and it holds no
programme control.

### What remains directly relevant

Unchanged and still load-bearing: extracted Starter modules and their migration
lineages; product-first parity with existing Sub behaviour; the writer censuses
and one-writer enforcement; account-recovery decomposition;
`subscribers.metadata` and `organizations` ownership; address data repair when
that slice migrates; and per-module backfill, shadow comparison and legacy-path
removal.

The eight cohorts are unchanged. They order **which domains switch authority in
what sequence**, and that ordering never depended on where the code ran.

### Authority, restated

The programme's authority transfer is now *within* one runtime and one database:

| | Before | After |
|---|---|---|
| Source | `asm-dotmac-sub-legacy` — the whole legacy application | `asm-dotmac-sub-legacy-domains` — the legacy domain implementations inside Sub |
| Target | `asm-dotmac-isp` — an independent assembly | `asm-dotmac-sub-composed` — pinned modules composed inside the same Sub |
| Database boundary | `independent` | `shared-in-process` |

`shared-in-process` means one database, with isolation by module schema
(`mod_<code>`) and one authority per fact — **not** two writers. Every
single-authority clause above survives intact and applies per domain rather than
per assembly. Concurrent work still does not create concurrent authority.

### Controls: four superseded, three added

A control whose premise is removed is **superseded**, never deleted and never
repurposed — this record already forbids changing a stable identifier's meaning,
so a control that now asks a different question gets a new identifier and the
old one keeps its history.

| Control | Fate |
|---|---|
| `ctl-isp-002` target host, database and deployment owner | superseded — nothing separate exists to name |
| `ctl-isp-005` target database catalog, RLS and rehearsal | superseded by `ctl-isp-010` — there is no target database; the rehearsal is now against Sub's own |
| `ctl-isp-007` cohort shadow at an immutable source watermark | superseded by `ctl-isp-011` — no cross-database watermark exists when both paths read one database |
| `ctl-isp-008` sealed switch with delta capture and traffic drain | superseded by `ctl-isp-012` — nothing to drain and no delta to capture; the switch is a configuration change inside one transaction boundary |
| `ctl-isp-001`, `ctl-isp-003`, `ctl-isp-004`, `ctl-isp-006`, `ctl-isp-009` | unchanged in meaning |

`ctl-isp-009` — displaced writers and fallbacks ratchet to zero — is now the
programme's centre of gravity rather than its last step. It is the thing that
distinguishes a domain that was genuinely converted from one that merely gained
a module beside its legacy code.

`dec-isp-002` is **superseded, not answered**. It asked which host runs the
independent ISP runtime. Three hosts were offered between 2026-08-21 and
2026-08-22 and each already carried live production; that search is closed
because the question was wrong, not because it was won. Host procurement is no
longer a programme gate.

### Why this is the safer programme

The replacement model's hardest and least reversible step was the cross-database
sealed switch: drain the source, seal it, capture the delta, prove zero drift at
a watermark, then move authority to a different database on a different host —
with a rollback that must not create two writers. In-place conversion deletes
that step. A domain's switch becomes a configuration change between two
implementations that share one transaction, and rollback is the same
configuration change in reverse.

What it introduces instead is narrower and better understood: module lineages
must compose into Sub's live production database (`ctl-isp-010`), and each
domain's module path must be proven against its legacy path before the switch
(`ctl-isp-011`). Both are ordinary migration engineering. Neither requires a
maintenance window measured against customer traffic.

### Enforcement added with this amendment

- `superseded` is a control state, and it requires immutable evidence naming the
  amendment that removed the control's premise — the same bar `verified` carries,
  for the same reason.
- A live control may not depend on a superseded one. Such a control could never
  open, because nothing will ever advance its dependency; the gate would read as
  "not ready yet" forever instead of as a stale edge. Superseding a control now
  forces its dependents to be re-pointed in the same change.
- A superseded control may not remain in `cutover_control_ids`. A cohort reaches
  `in-progress` only when every cutover control is `verified`, and a superseded
  one never will be, so leaving it there is a permanent silent block on the
  whole programme.

## Consequences

- This record and matrix are normative for programme ordering and control
  identity. Every cohort remains blocked; acceptance alone makes no authority,
  deployment or data change.
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

- `programme_control` refuses an ADR that asserts a control state its own
  matrix contradicts. The pairing is read from the matrix's own
  `governing-decision` record rather than guessed, and the check is
  deliberately one sentence shape — a backticked control id followed by "is
  <state>" — so a record can still discuss its controls without arguing with
  the validator.
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
  Governance revision carrying this amendment before changing any conflicting
  local first-cutover statement.
