# 0040. An unauthenticated caller is anonymous, and the shape cannot carry a party

- Status: Proposed
- Date: 2026-09-03
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository that writes or projects an audit event under the Audit v2 actor contract
- Classification: Internal

## Context

### The gap

The Audit v2 actor taxonomy has **no truthful representation for an
unauthenticated login attempt**. Michael, 2026-09-03:

> Using `system` for an unknown login caller would manufacture attribution.

That is the defect class this fleet spent 2026-09 repairing in one instrument
after another: **reporting a value that was never observed**. `system` is not a
neutral placeholder in an audit trail — it is a positive claim that an internal
component performed the operation. A failed login by an unknown caller is a
real, security-relevant event about a caller whose identity was never
established, and the taxonomy currently forces whoever records it to say
something false or to record nothing.

### What the contract holds today

Read on 2026-09-03 from `dotmac_starter_mt` `origin/main` at
`d096e64c13fe3cd8ab89f4a15edd1ce1bc046e2a`, in
`packages/dotmac-kernel/src/dotmac_kernel/audit.py` — named by symbol rather
than by line, because line numbers decay:

- `ACTOR_TYPES` is a closed `frozenset` of **four** kinds: `system`, `user`,
  `api_key`, `service`. It is a Python constant over a `String` column rather
  than a database enum, deliberately, so that a versioned contract addition
  does not require enum surgery in every product database.
- The module already anticipates this record. Its own comment says a fifth kind
  is *"a contract change with an answer for what its `actor_id` means and
  whether it can carry a party — not a string a product invents at a call
  site."* This record is that contract change, and it answers both questions.
- `resolve_audit_actor` refuses a missing `actor_type`, refuses an unknown one,
  and refuses a non-`system` kind with no `actor_id`. `system` is the one kind
  whose `actor_id` may be absent.
- The per-kind party rule exists as a **comment table**: `system` no party,
  `service` no party, `api_key` optional owning party, `user` party when
  available.

### The measurement that decides § 4

**`resolve_audit_actor` takes `actor_party_id` as a keyword argument and never
reads it.** Its only appearances inside that function are the signature, the
docstring and the text of an error message. `write_audit_event` passes the same
value straight through to the row. `AuditEvent` declares no `__table_args__`
and therefore no `CheckConstraint`, though the same kernel uses
`CheckConstraint` freely elsewhere — `consent_models`, `delivery_models`,
`flag_models` and `machine_models` each pin a column's admissible values that
way.

So the per-kind party rule is, today, **four lines of comment enforced by
nothing**. A caller may write `("system", None)` with a party attached and the
row is accepted, stored and indexed. Nothing in the write path, and nothing in
the schema, objects.

That is the whole reason § 4 exists. Adding `anonymous` as a fifth line to that
comment table would place a new rule immediately below four rules nothing
enforces, in the file whose docstring explains why the actor pair must never be
inferred. The rule would be true, documented, cited in review, and inert.

## Decision

### 1. The standard

> **`anonymous` is the fifth actor kind. Its `actor_id` is absent, and the
> record cannot carry a party — not by rule, but by shape.**

### 2. What `anonymous` means, and what it is not

`anonymous` records a decision made **about a caller whose identity was never
established**. The unauthenticated login attempt is the motivating case; it is
not the only one. A rejected request bearing no credential, a refusal at the
edge, a public surface that made a decision worth recording — each has the same
truthful actor and the same absent identifier.

Three boundaries, and each is here because it is the one that erodes:

- **`anonymous` is not `system`.** `system` says an internal component acted.
  `anonymous` says a caller acted and was never identified. Collapsing them
  loses precisely the distinction a security review needs.
- **`anonymous` is not a fallback.** A caller that HAS an actor and does not
  supply one still fails: `resolve_audit_actor`'s existing refusal stands
  unchanged, and this record adds no path by which a missing actor becomes
  `anonymous`. The kind is **chosen** by the owner writing the event — for
  authentication events, the auth owner, which is already where the
  success/refusal event belongs rather than being inferred from an HTTP status.
  A defaulting path would convert every caller defect in the fleet into a
  plausible-looking row, which is the failure `MissingAuditActorError` was
  written to prevent.
- **`anonymous` is not unknown-attribution.** It is not a value to reach for
  when the actor could not be worked out. "We could not resolve it" has no
  representation in this taxonomy, deliberately, exactly as
  `resolve_event_attribution` refuses to record `"system"` or `"unknown"` for a
  process that never declared its identity.

### 3. `actor_id` absent, and `actor_label` absent too

`anonymous` carries **no `actor_id`**. It joins `system` as a kind whose
identifier may be absent, and unlike `system` its identifier must be absent:
there is no identifier, and a column holding one would be holding something
else.

**This record extends the amendment by one field, and says so plainly so the
extension can be rejected on its own terms.** `actor_label` — the write-time
display snapshot — is **also forbidden** for `anonymous`.

The reason is that the label is where the defect reappears one layer down. The
submitted username or email address of a failed login is unverified input: it is
a string a stranger typed. Putting it in the identity display slot renders an
unauthenticated attempt in every audit view as though someone were identified,
which is the same manufactured attribution the amendment repairs, arriving
through a field nobody was watching.

The submitted identifier is genuinely worth recording — it is how a credential
stuffing run is recognised. It belongs in the event's **declared details**,
under a name that says it is a submitted, unverified value, and never in
`actor_id`, `actor_label` or `actor_party_id`. A detail is data about the
attempt. The actor columns are claims about who acted.

### 4. Party enrichment is forbidden STRUCTURALLY, and what that can mean for a contract

Michael's amendment forbids Party enrichment on an `anonymous` actor. The
question put to this record was whether a contract may require that forbidding
to be **structural — a shape that cannot carry a party — rather than a rule
someone follows**, and whether a contract can mandate structure at all.

**It can, and it must here, and the boundary is precise:** Governance mandates a
**property** and the **seams** at which it must hold. It does not choose the
type, the class, the constraint name or the language construct — those belong to
the implementing owner, and a governance record that picks them is writing an
implementation in a repository it does not own.

The property:

> **No call site can express an `anonymous` actor carrying a party, and no
> stored row can hold one.**

Two seams, because they fail independently and each is reachable on its own:

1. **Construction.** Supplying a party alongside an `anonymous` actor is
   **unexpressible**, not rejected at runtime. The difference is the whole
   point: a runtime rejection is a rule, evaluated when the path is taken, on
   the paths somebody remembered to route through the check. An unexpressible
   call is refused before the program runs, everywhere, including on the path
   nobody thought about. The kernel's existing actor resolver already
   demonstrates the weaker form — it accepts the party argument and ignores it —
   which is how four documented per-kind rules came to enforce nothing.
2. **Persistence.** A stored row combining the `anonymous` kind with a party
   **is refused by the schema**. A Python seam governs one writer; a row can
   also arrive from a projection, a backfill, an import, a repair script or a
   direct statement. This is not a new demand on the kernel: the same package
   already constrains admissible column values this way in four other models.

**And structure is not sufficient**, which needs saying because a structural
claim is exactly the kind of thing that gets read as finished. Each seam carries
a **negative control**: a planted attempt to construct one, and a planted
attempt to store one, each **required to fail**. A shape nobody has proven
refuses and a shape that refuses are the same colour, and this repository has
ADR 0021 § 4's finding on precisely that point — a green lane with no paired red
is evidence that nobody has learned whether the lane can fail.

**What structure does not buy**, stated so the claim is not overread: it removes
one failure mode — an anonymous row carrying a party — and leaves every other
attribution defect untouched. A `user` actor with the wrong party, an
`api_key` actor attributed to the wrong owner, a caller choosing `anonymous`
when it knew who was calling: none of these is addressed here, and none becomes
less likely because this one is closed.

### 5. Projections carry the kind through

A central audit projection that maps `anonymous` to `system`, to `unknown`, or
to a null actor **re-manufactures the attribution this record removes**, in the
surface most people actually read.

The kind is carried through every projection, search index and export
unchanged. A projection that cannot represent the fifth kind is not ready to
receive Audit v2 events, and a projection remains rebuildable from the
application rows that own the truth rather than becoming a second authority for
them.

### 6. Scope, and one edge this record deliberately does not close

This record governs the **tenant** audit contract's actor taxonomy.

The **platform** audit trail is not covered, and the reason is a finding rather
than an omission. `write_platform_audit_event` identifies its actor as
`actor_admin_id: UUID | None` — a nullable administrator reference with no kind
column at all. An unauthenticated platform login attempt therefore has the same
gap in a worse form: a NULL admin id is indistinguishable from an event whose
actor was simply not recorded, and there is no place to say which. Whether the
platform trail gains a kind column, adopts the tenant taxonomy, or keeps a
separate shape is a contract decision this record does not make, and it is open
decision 45.

## Consequences

**A previously unrecordable event becomes recordable truthfully.** Failed
authentication by an unknown caller is currently written as a lie, written as
`system`, or not written; after this it has one correct representation. Login
refusal rates, credential stuffing patterns and lockout evidence stop depending
on which of those three a given product chose.

**The taxonomy stops being closed at four, and that is a cost.** Every consumer
that pattern-matches actor kinds — projections, exports, dashboards, access
filters, retention rules — gains a case, and any consumer written as an
exhaustive match over four kinds must be revisited. The kernel's choice of a
Python constant over a database enum is what keeps this from being a migration
in every product database; it does not keep it from being a review of every
consumer.

**Two of the four existing per-kind party rules remain unenforced**, and this
record does not repair them. `system` and `service` are documented as
party-free and nothing checks it. Closing the fifth kind structurally while
leaving those two as comments is an improvement and an inconsistency at the
same time, and stating it here is what keeps it from being discovered later as
a surprise. Whether the same structure is extended to them is left to the
implementing owner, who is the one who can measure how many existing rows would
violate it.

**Rows written before this contract are not backfilled.** The same reasoning the
kernel already applies to its nullable `actor_type` and `source_application`
columns applies here: an actor nobody can name from the row is not recoverable
by guessing, and a guess written into an audit column is indistinguishable from
a fact.

## Drift prevention

**Enforcement: none in this repository.** No check family, no
`standards_control` rule, no `standards-profile.schema.json` surface and no CI
gate is created here. The controls this record requires live in the implementing
repository, because both seams — a constructor shape and a table constraint —
are properties of code and a schema that Governance does not own.

What must exist in that repository for this record to be more than documented
intent, and each is a fact about another repository's tests under ADR 0013 § 1
rather than something this repository can observe:

- the two negative controls of § 4, each **required to fail**, and each failing
  for the stated reason rather than for any reason — ADR 0021 § 4's requirement
  that a mutation name the thing it is missing;
- a **positive control** that a conforming `anonymous` event is accepted and
  stored, so that the guard is known to admit what it must admit rather than
  refusing everything, which ADR 0034 exists because of;
- a check that `anonymous` is never produced by a default or fallback path,
  which is the § 2 boundary most likely to erode and the only one that is
  invisible in the resulting rows: a fabricated `anonymous` and a truthful one
  are byte-identical.

**The sensitivity trap specific to this record:** a test suite that never
attempts an anonymous-with-party write passes on a system where the shape does
not refuse it, and a projection test that never sees an anonymous event passes
on a projection that would map it to `system`. Both are the shape ADR 0033 § 3
addresses — an instrument that has never been shown to find what it is looking
for. The controls above are stated as required rather than recommended for that
reason.

Open decision 45 records what acceptance leaves undecided: who owns the
implementation of both seams and their controls, whether the platform audit
trail's actor gap in § 6 is closed the same way, and whether the two existing
unenforced per-kind party rules are repaired in the same change.
