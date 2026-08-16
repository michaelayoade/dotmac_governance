# 0012. Fleet integration architecture standard: ingress eligibility, event identity, and retention lifetimes

- Status: Proposed
- Date: 2026-08-16
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories, for every inbound provider transport
- Classification: Internal

## Context

Dotmac applications integrate through versioned APIs and webhooks. Inbound
provider transports therefore exist in `dotmac-integration` and its connector
plugins, in Sub's Meta/WhatsApp and social receivers, in CRM's `meta_webhooks`,
in ERP's webhook surface, and in PSP callbacks. Each was written separately,
and each had to answer the same three questions: who may send us this request,
what makes two arrivals the same fact, and how long the answer to the second
question survives.

They answered differently, and the divergences are not stylistic:

- A receiver that reuses one "is this binding usable?" predicate for both the
  provider's activation handshake and actual event delivery deadlocks its own
  activation. Sub hit this in production on 2026-08-06: Meta reached the
  WhatsApp callback, an installation error for `messaging.receive.v1` was
  raised before `hub.verify_token` was ever compared, and the binding could not
  be enabled until Meta was subscribed, which could not happen until the
  handshake was answered. The endpoint refused the one request that would
  unblock it. The usual field repair is an operator flipping state by hand,
  which bypasses whatever the enable path was meant to check.
- A receiver that keys deduplication on a digest of the raw HTTP request
  deduplicates only an exact retry. Providers batch, and batches regroup, so
  the same message in a differently-grouped batch records twice; and one
  malformed entry in a batch of twenty takes the other nineteen with it,
  because the whole request carries one identity.
- A retention sweep that destroys identity alongside content makes a later
  redelivery of the same event indistinguishable from a new one. The system
  silently re-applies a consequence it has already applied, and the audit trail
  cannot explain it.

Michael approved three fleet standards on 2026-08-15 addressing exactly these.
Each carries a qualification that is the load-bearing half of the rule, and
each qualification is reproduced verbatim below rather than summarised. This
record is where the three are written down.

It is `Proposed`. Nothing below is normative until a named human approves it
through the recorded process, and no part of it states that any Dotmac
repository conforms.

## Decision

### 1. Webhook handshake and delivery require separate eligibility

A provider activation handshake MAY run for a **configured-but-disabled**
binding, because the handshake is what enables activation. Actual **event
delivery** requires the installation AND the binding to be enabled.

Michael's qualification, verbatim:

> This does not weaken challenge/signature verification or permit disabled
> bindings to accept POST deliveries. Never reuse a universal `_usable`
> predicate for both operations.

The relaxation is about **lifecycle state only**, never about authentication.
A handshake still proves the challenge and, where the provider signs it, the
signature. Two predicates, each named for its operation; and the operation is
an explicit input to the eligibility decision rather than something inferred
from the HTTP method, the route, or the presence of a body.

### 2. Provider-event identity is never the request digest

Deduplicate each inbound provider event using **the provider's stable event
identifier, scoped to the receiving binding**. Where the provider assigns none,
derive identity from the **individual canonical event** — not the request — and
label it as derived, so a consumer knows that identity is weaker than a
provider-assigned one.

Michael's qualification, verbatim:

> The raw-request digest remains transport evidence and may short-circuit exact
> HTTP retries, but it cannot replace per-event identity — especially when one
> request contains multiple events.

Both layers exist and are not redundant. The digest answers "is this the same
HTTP request?"; the event identity answers "is this the same fact?". Keeping
the digest is correct; letting it stand in for event identity is the defect.
It follows that a malformed entry inside a batch is a **refused observation**
carrying whatever provider identity it has, not a `continue` that discards it —
so a redelivery of the same bad item still deduplicates.

### 3. Content retention and replay identity have separate lifetimes

Redacting payload **content** must preserve the minimal **identity, digest,
outcome evidence and tombstone** required to recognise a replay or a collision.
Content and identity are two retention subjects with two lifetimes, not one.

Michael's qualification, verbatim:

> This does not mean keeping identity forever. Replay evidence needs its own
> explicit, justified retention period. Use a tombstone rather than NULL where
> NULL can mean the provider supplied no content; never preserve provider
> payload keys merely because they look structural.

Three separate obligations follow:

1. **Identity is not exempt from retention policy.** "We kept it for replay
   detection" is a justification with a period attached, not a licence to keep
   it indefinitely. An unbounded identity table is still personal data
   accumulating.
2. **Tombstone, never NULL.** `payload_json = NULL` is ambiguous, because it
   also means "the provider sent no body". A tombstone states *redacted, when,
   under which policy*, so "empty" and "destroyed" stay distinguishable
   forever.
3. **Structural-looking keys are not exempt.** A key is retained because a
   named mechanism needs it, not because it looks like an envelope. Provider
   payload keys routinely carry content — phone numbers, display names, message
   previews — in fields that read as metadata.

### The replay-evidence period is stated here, and is not yet a control

Michael has stated the replay-evidence horizon as **180 days from
`received_at`**, alongside the already-ruled 30-day content period anchored on
the same column. This record states that figure so it is reviewable in one
place. Approving this record does **not** put the period in force and does not
authorize retirement of any replay evidence, because:

- 180 days is not encoded anywhere in the fleet today. The adoption record
  `dotmac_starter_mt docs/inventories/integration-retention-adoption.toml`
  carries `replay_evidence_period = "UNSET"` and lists it in `blocked_on`;
- `dotmac-integration` has no second-phase retirement at all, so filling the
  period in would name a control that does not exist;
- the Data Protection Officer role owns acceptance of the actual notice and
  ROPA revision, and that acceptance must record the real document revision,
  date and named human approver; and
- deleting a receipt currently cascades its legal-hold history, so an
  implementation must retire identifiers in place or preserve released-hold
  evidence behind its own migration.

Those are open decisions, recorded in `docs/open-decisions.md` rather than
resolved here.

## Consequences

- Every inbound provider transport in scope acquires an operation-aware
  eligibility decision. A receiver whose handshake and delivery paths share one
  predicate becomes a defect against this record once it is approved, rather
  than a style preference.
- The rule forbids one predicate answering both operations; it does not forbid
  a shared helper that only one arm reaches. In the reference implementation
  the delivery arm delegates to `selection._usable` and the handshake arm never
  reaches it, which satisfies the rule.
- Sub's Meta receiver keys on `meta:{sha256(raw_body)}` at
  `dotmac_sub app/api/inbox_webhooks.py:277` (revision `27c76aae`,
  2026-08-14). Under standard 2 that is a tracked defect needing a named repair
  owner and a migration path for identities already written in the digest form.
  Repairing it is not a prerequisite for approving this record; omitting it
  would be a governance failure.
- Products that already conform pay nothing. `dotmac-integration` was built to
  standards 1 and 3 and is the reference implementation, not an exemption from
  whatever enforcement is later chosen.
- Deriving identity where a provider assigns none requires the derived identity
  to be labelled. A product that derives silently is indistinguishable from one
  that received a provider identifier, which defeats a consumer's ability to
  reason about how strong its deduplication actually is.
- Retention work in any product must separate two subjects with two periods. A
  single "delete the row after N days" sweep does not satisfy this record even
  when N is short.
- Nothing here changes the `standards_control` profile, its schema version, or
  any enforcement mode. No product repin is required or implied.

## Drift prevention

The mechanisms that exist today are product-local, and this record does not
represent them as fleet-wide enforcement. Each is cited so a reviewer can read
the real thing rather than this record's description of it.

**Standard 1** — `dotmac_starter_mt`, merged as PR #188
(`5b91b674337e0d710b017603a625b3c4acf77ce7`, 2026-08-15):

- `packages/dotmac-integration/src/dotmac_integration/ingress.py` declares
  `IngressOperation` (line 283) with exactly `DELIVERY` and `HANDSHAKE`,
  `HANDSHAKE_INSTALLATION_STATES` (line 257) as `{draft, validating, enabled}`,
  and `_eligible` (line 702), which takes the operation as a parameter. The
  handshake arm consults installation state only; the delivery arm delegates to
  `selection._usable` (`selection.py:68`), which requires both the binding and
  the installation to be enabled.
- Behavioural proof: `tests/unit/test_integration_ingress.py:753`
  (a configured-but-disabled binding answers a handshake and refuses a
  delivery) and `:821`, which drives the full seven-row
  installation-state × binding-state matrix rather than the one interesting
  cell.
- Static proof: `tests/architecture/test_integration_ingress_hygiene.py:269`
  asserts by AST that the handshake branch cannot reach the delivery predicate,
  and `:313` asserts that both facades state their operation instead of
  inferring it. The pairing is the point — a comment saying "these are
  separate" survives the refactor that merges them, and an AST guard does not.

**Standard 2** — `dotmac_starter_mt`
`docs/superpowers/specs/2026-08-15-meta-whatsapp-ingress-conformance.md`
states WAI-20 to WAI-26 (lines 285–291): provider-assigned identity for
messages and statuses, derivation from the individual item where the provider
assigns none, a declared `identity_source` of `provider` or `derived`,
uniqueness within one request, identity stability across regrouped batches, and
an explicit prohibition on deriving identity from the raw request body. The
spec names the live anti-pattern (lines 305–320) and pins durable uniqueness on
`(capability_binding_id, provider_event_id)`. The spec names its executable
bindings; whether each named test currently exists and passes was not verified
for this record, and no claim is made that it does.

**Standard 3** — `dotmac_starter_mt`, merged as PR #192
(`aaa3b5435732f0b1bebdf894778d6615c05e3c12`, 2026-08-15):

- `packages/dotmac-integration/src/dotmac_integration/retention.py` defines the
  tombstone marker `REDACTION_MARKER = "__dotmac_redacted__"` (line 159) as a
  cross-repository wire contract and confines writes to `REDACTABLE_COLUMNS`
  (line 165): `payload_json`, `headers_json`, `consequence_json`. The tombstone
  records the redaction time, the period, the policy owner, a copy of the
  payload digest, and a key **count** — never provider key names.
- `resolve_retention_policy` ships no default period and raises
  `RetentionNotConfigured` when the period or the legal-policy owner is absent,
  so a deployment cannot destroy content by accident.
- `tests/unit/test_integration_retention.py:302` diffs the **whole** row before
  and after redaction and asserts that the changed set is a subset of the three
  redactable columns, so a column added to the receipt table later is covered
  the day it lands without anyone remembering to update the test. It then names
  digest, provider event id and binding explicitly, because "nothing changed at
  all" would also satisfy a subset assertion.
- The migration `ig_0006_retention`
  (`packages/dotmac-integration/src/dotmac_integration/migrations/versions/ig_0006_retention.py`,
  `down_revision = "ig_0005_receipt_delivery"`) adds no column to any existing
  table; it creates `mod_intg.receipt_legal_holds` with a unique partial index
  making "at most one active hold" a database fact.
- Adoption is tracked, and gated closed, in
  `docs/inventories/integration-retention-adoption.toml`: code is released
  (`dotmac-integration 0.1.0a3`) while `adopted = false`, blocked on a
  `PENDING` notice revision and the `UNSET` replay-evidence period.
  `tests/architecture/test_retention_adoption_gate.py:85` requires an unset
  replay-evidence period to block adoption rather than merely be noted, and
  `:110` keeps "code released" from being read as "policy adopted".

Fleet-wide detection does not exist. Under ADR 0006 the mechanism would be a
rule family in the `standards_control` engine with stable diagnostics and
sabotage proofs, carried by a schema-version increment that each product adopts
on its own repin. That work is deliberately **not** part of this record: an
engine rule family enforcing an unapproved standard would activate policy
without approval, and `required` mode is representable only with an `Accepted`
checked-in governance source.

Approval of this record is therefore conditional on the enforcement question
being answered, not on it being answered here. Until it is answered, drift
detection for this standard is a review obligation plus the product-local
guards above. That is a weaker mechanism than an executable fleet rule, and it
is recorded as weaker rather than overclaimed.
