# 0018. Authority cutovers leave receipts and decommissions retire delegations

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Governance-enrolled Dotmac repositories, and any Dotmac system whose authority moves or which is decommissioned
- Classification: Internal

## Context

### The standard these rules extend

Dotmac already has an authority-migration standard. It is stated in three
places, none of which is a Governance record:

- The source-of-truth doctrine reproduced in
  [`docs/agent-guidance/global.md`](../agent-guidance/global.md): *"Migrate
  authority explicitly: document the old owner, new owner, shadow/verification
  phase, cutover gate, fallback retirement, and tests proving the boundary."*
- `dotmac_starter_mt` ADR-0031, *An authority cutover is sealed by its own
  evidence* — `Accepted`, fleet-scoped, read at commit
  `ed3ac864b350d4556808a69496f999f764682442`, path
  `docs/adr/0031-an-authority-cutover-is-sealed-by-its-own-evidence.md`. It is
  already pinned by this repository as programme record
  `rec-isp-cutover-standard` in `programmes/dotmac-isp-replacement.json`.
- Governance [ADR 0017](0017-module-migrations-retire-compatibility-state.md)
  (`Proposed`), which covers retirement of compatibility state inside a
  *module* migration.

Michael approved two additions to that standard in the 2026-08-30 working
session, in these words:

> - Every authority cutover leaves an immutable receipt naming old owner, new
>   owner, exact revisions, effective time, runtime observation, rollback
>   boundary and old-writer retirement.
> - A system cannot be declared decommissioned until every delegated authority,
>   writer, scheduled job, webhook, transport and downstream dependency is
>   retired or transferred with evidence.

He directed that they be recorded as **amendments to the existing standard, not
competing standalone records**, and that the normative language live in
Governance.

### Why this record carries no `Amends:` field

`docs/adr/README.md` scopes `Amends:` to a four-digit number in *this*
repository's ADR directory, and `tools/check_adrs.py` rejects a relationship
pointing at a record that does not exist here. The parent standard is
cross-repository, so the field cannot express the relationship without naming
the wrong parent. The relationship is therefore stated here explicitly, with
ADR 0013 § 3 coordinates, and the mechanical propagation into ADR-0031's own
in-document amendment mechanism is recorded as open decision 20 rather than
performed unilaterally in a repository this record does not own.

Neither rule narrows or replaces anything in ADR-0031. ADR-0031 governs the
evidence gathered *inside* the transaction that performs a switch — one
transaction, `SHARE MODE` locks, full-column typed digests, effective-privilege
assertions. Rule 1 below governs what survives *after* that transaction, and
rule 2 governs the disposition of everything the switch left behind. Both are
additive.

### The motivating evidence

The `dotmac_crm` deployment ("Omni") was decommissioned on 2026-08-29:
containers removed, `/opt/dotmac_omni/` deleted, and `crm.dotmac.io` now
resolves to a host serving an unrelated certificate. Three failures are the
reason for this record. They are recited here as an incident description, which
ADR 0013 § 5 distinguishes from a claim.

**A delegated authority survived its owner.** `dotmac_sub` had handed live-chat
authority to the CRM under an explicitly temporary arrangement
(`docs/runbooks/TEMPORARY_CRM_CHAT_AUTHORITY.md` and
`docs/adr/0006-temporary-crm-chat-authority.md`, both present in
`dotmac_sub` at commit `6c9a62895f565847290ad807bd6ae1b4f915ec4c`), whose
"Roll back to Selfcare" procedure was never executed. A full day after the CRM
ceased to exist, Sub production still carried `CHAT_LIVE_ENABLED=true`, a CRM
chat configuration identifier, and a CRM base URL pointing at the dead host.
Chat failed safe only because the setting's default and its invalid-value
fallback were both `selfcare` — a property of the setting, not a control that
was exercised. Retirement is tracked in Sub PR #2821, which is not observable
on that repository's canonical `main` at the commit above.

**A scheduled writer survived, and did not fail safe.** `CRM_TICKET_PULL_ENABLED`
remained enabled in production: a five-minute poller that creates support-ticket
rows and stamps a CRM identifier onto subscriber rows, running against a dead
host. `docs/designs/SUPPORT_TICKET_LIFECYCLE_SOT.md` in the same repository had
*already* declared CRM ticket import retired as an authority, so the boundary
was incomplete by Sub's own documentation while the writer kept running.

The decommission sweep that was performed enumerated Sub's **outbound**
dependencies *on* the CRM. It never asked what authority the CRM **held over**
Sub. Both survivors were invisible to it for the same reason: a scheduler entry
and a configuration flag are declarations elsewhere, not call sites, so a
source-level dependency sweep cannot see either.

**The cutover left no receipt, so a data-loss question is permanently
unanswerable.** The write barrier that moved chat authority raised a domain
error mapped to a 503 and wrote nothing — no audit row, no metric, no counter.
The exporter stamped nothing, the importer lived in the CRM, and Sub's inbox
tables carry no provenance column. No migration ever wrote an authority row.
The repository therefore **cannot** distinguish "the cutover was never executed"
from "it was executed and rolled back", and the CRM was deleted without a final
backup — a deliberate, recorded decision. If the cutover was executed, anything
that lived only in the CRM after the barrier is gone.

Four individually reasonable choices combined to make that question permanently
unanswerable. No single one of them was a defect. That is the argument for
rule 1: the receipt is the artefact that no individual choice produces.

### Authority status

Michael's direction above is not this repository's required GitHub approval
record. Under [ADR 0001](0001-governance-authority-model.md) and `AGENTS.md`,
an agent-drafted record remains `Proposed` and non-normative until the named
human approval is recorded in the controlled workflow and the approved change
merges to canonical `main`. This record is therefore `Proposed`, on the same
footing as ADR 0017, and must not be cited as policy before then.

## Decision

If this proposal is accepted, the following two rules extend the fleet
authority-migration standard.

### 1. Every authority cutover leaves an immutable receipt

A cutover moves authority over a named resource from one named owner to
another. When it completes, it writes **one receipt**, and the receipt carries
all seven fields below. A reviewer checks presence field by field; a receipt
missing a field is incomplete, and an incomplete receipt does not become
complete by being explained in prose.

| # | Field | What it names | Not this |
| --- | --- | --- | --- |
| 1 | `old_owner` | The service, module or system that held authority, **and the exact resource** — the table, decision or state transition — whose authority moved. | A repository or host name with no resource. |
| 2 | `new_owner` | The same pair for the acquiring owner. | "The new service." |
| 3 | `revisions` | Exact revisions on both sides: the commit, migration revision or released version and digest of the code that performs the switch, and of the code that runs after it. ADR 0013 § 3 coordinates. | A branch name, "current `main`", "latest", an unpeeled tag, an image tag. |
| 4 | `effective_time` | The instant authority moved, recorded **by the transaction that moved it**. | The date a document was written or a deploy was approved. |
| 5 | `runtime_observation` | Evidence that the barrier **engaged in the running system** — see below. | A restatement of intent. |
| 6 | `rollback_boundary` | The exact condition and window in which the switch can still be reversed; what becomes irreversible once it closes; the named owner of the reversal decision. | "We can roll back if needed." |
| 7 | `old_writer_retirement` | The disposition of every displaced writer, per rule 2's vocabulary: retired in a named revision, transferred to a named owner, or still live with a named retirement condition and owner. | Silence. "Not yet" is a permitted value; unstated is not. |

**Immutable** means the receipt is written by the cutover rather than composed
afterwards, is append-only in a controlled system, and stays addressable after
the counterparty is gone. A receipt that lives only in the system losing
authority is not a receipt; it is a hostage.

#### `runtime_observation` is the field that would have caught the CRM cutover

The CRM chat cutover already had a document naming the old owner, the new
owner, the switch and the rollback procedure. It was a runbook, and the runbook
was accurate. What no artefact anywhere recorded was whether the barrier ever
**fired**.

A receipt asserting only intent is a runbook. `runtime_observation` is the half
that separates *declared* from *observed*, and it has three parts:

1. **The barrier writes an attributed record when it engages** — actor,
   timestamp, resource, old owner, new owner. An error returned to one caller
   is a response to that caller, not a fact about the system. A metric with no
   attribution answers "how often" and not "which".
2. **The rows whose authority moved carry a provenance discriminator** —
   `source_system`, an external identifier, or an origin marker — so "which era
   is this row from" remains answerable when the counterparty no longer exists.
   Without one, no later reconciliation can even be scoped.
3. **Non-engagement is itself an observation.** "The barrier never fired during
   the window" is a temporal negative claim under ADR 0013 § 4: it is permitted
   as an as-of observation carrying its coordinates, its observation date and a
   named refresh responsibility. Silence is not that observation. The CRM case
   is exactly the difference — nobody recorded that nothing happened, so
   "nothing happened" and "nobody looked" are now indistinguishable.

An interactive integration path that runs outside an outbox or inbox produces
no receipts of its own. Know which capabilities are in that class **before**
their configuration rows are deleted, because for those a binding row's
timestamps may be the only record the capability ever ran.

### 2. A system is not decommissioned until every delegation is retired

A system may be declared decommissioned only when every item in the inventory
below has an explicit disposition and none is still live. Removing the host is
not retiring the delegation. The declaration is a claim about the outside world
and is governed by ADR 0013: each category's negative is an as-of observation
with an oracle and a refresh owner, not an assertion.

#### The inventory is two-directional, and the inbound half is the one that gets missed

Enumerate in **both** directions:

- **Outbound** — what the surviving systems depend on *in* the departing system.
- **Inbound** — what authority the departing system *held over* the surviving
  systems, and what it wrote there.

The CRM sweep enumerated the outbound half and passed. Name the inbound half
explicitly, or it will be skipped again: the question is not only "what breaks
when this host goes away" but "what decisions and writes did this host own in
systems that are staying".

#### The six categories

| # | Category | Enumerated from |
| --- | --- | --- |
| 1 | **Delegated authority** — decisions and state transitions the departing system was authoritative for, including explicitly temporary handovers. | The surviving system's authority switches: settings whose allowed values name it, broker or dispatch indirections, capability bindings, ADRs and runbooks recording a handover. |
| 2 | **Writer** — anything that creates or updates rows in a surviving system, or stamps its identifiers onto them. | The surviving system's write paths and its columns holding foreign identifiers. |
| 3 | **Scheduled job** — pollers, cron entries, beat schedules, queue registrations and repair loops referencing it in either direction. | The scheduler's own registry and the settings or flag registry. **Not** a source grep. |
| 4 | **Webhook** — receivers the departing system calls, and receivers it registered elsewhere. | Receiver route tables and provider-side registrations on both sides. |
| 5 | **Transport** — outbound connectors, base URLs, credentials, message routes and DNS names pointing at it. | Connector manifests, configuration, and the credential store's inventory by pointer. |
| 6 | **Downstream dependency** — readers, imports, ORM relationships, foreign keys and stored identifiers that survive it. | Static source inventory plus a live-catalog inventory; source inspection cannot prove a deployed foreign key is absent. |

**Why scheduled jobs are their own category.** They failed twice in the CRM
case, and for a reason that generalises: a scheduler entry is a declaration in
a schedule, and an enablement flag is a row or an environment value. Neither is
a code reference, so a source-level dependency sweep — the instrument most
teams reach for — cannot see either, and the sweep comes back clean while a
writer runs every five minutes. Enumerate schedules from the scheduler and
flags from the flag registry.

#### Each item takes one of three dispositions

**RETIRED** — removed, naming the revision that removed it. **TRANSFERRED** —
moved to a named new owner, with that move's own receipt under rule 1. **STILL
LIVE** — retained, with a named owner and a named retirement condition; any
item at STILL LIVE blocks the decommission declaration.

Absence is never a disposition. An item nobody found is not retired; it is
unexamined, and the distinction is the whole control.

**Failing safe is not retirement.** Sub's chat delegation survived the CRM's
deletion and caused no incident because the setting's default and its
invalid-value fallback were both the local owner. That was a property of the
setting, not evidence that the delegation had been closed, and it held by
construction rather than by test. A delegation that failed safe is still a
delegation, and it still blocks the declaration.

#### A dormant capability reads as an absent one

When authority is delegated away, the surviving implementation goes quiet — no
traffic, no logs, no active writer — and is easily read as *missing* rather than
*switched off*. Before concluding a capability must be built, establish whether
it exists and is disabled. The cheapest discriminator is a search for the
authority switch itself — the setting, the flag, the broker indirection — not a
search for the capability.

### 3. What these rules do not do

Neither rule adds a conformance claim. The standards profile has no typed
representation for a cutover receipt or a decommission inventory, and the
Governance engine has no oracle that could evaluate either. If accepted, both
rules are review discipline; describing them as a Governance engine control
would be the same defect ADR 0013 exists to prevent.

## Consequences

- A cutover acquires a durable artefact that outlives both parties. The cost is
  paid by the cutover, which is the only actor in a position to observe what it
  did.
- Some in-flight cutovers will be found to have no `runtime_observation`
  available, because the barrier they used writes nothing. The remedy is to
  make the barrier write before the switch, not to accept the runbook as the
  receipt.
- A decommission acquires a gate it did not have, and the gate is expected to
  fail first attempts. The CRM decommission would have failed it twice.
- Systems already decommissioned cannot be retro-evidenced. Where an inbound
  delegation is discovered after the fact, it is closed in the surviving
  repository and recorded as an incident, not as a completed inventory.
- Rule 2's inbound half requires the departing system's authority to have been
  written down while it existed. Where it was not, the surviving system's own
  authority switches are the only remaining index — which is why rule 1's
  receipt and rule 2's inventory reinforce each other and were approved
  together.
- This `Proposed` record changes no current policy and no conformance result.

## Drift prevention

`tools/check_adrs.py` validates this record's filename form, unique number,
controlled metadata, status form, required sections and declared relationships.
It does not enforce either rule, and no test is added that would imply
otherwise.

Any future control implementing these rules must fail on at least:

- a receipt missing any of rule 1's seven fields;
- a receipt whose `revisions` carries a branch name, "latest", an unpeeled tag
  or an image tag rather than an immutable coordinate;
- a receipt whose `runtime_observation` cites the runbook, ADR or deploy
  approval that declared the cutover, rather than a record written when the
  barrier engaged — this is the sensitivity case, because it is the shape the
  CRM cutover already had and a checker that passes it is not implementing this
  record;
- a decommission declaration with any of the six categories unenumerated, or
  any item at STILL LIVE, or any item with no disposition;
- an inventory assembled only from outbound source references: the required
  canaries are a planted **inbound** delegation expressed as a scheduler entry
  and a planted enablement flag, neither referenced by any import, both of
  which must be found;
- a two-directional ratchet failure in both directions — a newly planted
  delegation that the baseline does not carry, and a removed delegation whose
  baseline was not lowered.

**Non-vacuity.** A checker over zero receipts and zero decommission
declarations passes for the wrong reason. Neither rule counts as evidenced
until at least one real cutover has produced a receipt the checker reads, and
the checker is shown to fail when a field is removed from it.

Promotion from `Proposed` requires the named human's approval recorded in
GitHub and the approved change merged to canonical `main`. Only then may an
implementation cite this record as normative, and only an implemented,
sabotage-tested control may claim automated conformance. Where the receipt is
stored and who owns that store is open decision 19; propagating these
amendments into `dotmac_starter_mt` ADR-0031 through that record's own
in-document amendment mechanism is open decision 20.
