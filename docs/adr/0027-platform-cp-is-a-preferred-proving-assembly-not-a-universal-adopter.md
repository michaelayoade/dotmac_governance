# 0027. Platform CP is a preferred proving assembly, not a universal adopter

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide module adoption sequencing, and every enrolled repository that publishes a module Platform CP could compose
- Classification: Internal

## Context

This record carries **one** decision. Michael was precise that it is the only
new decision in a large instruction, and everything surrounding it is already
supported by checked-in policy: `dotmac_starter_mt`
`docs/adr/0057-the-vendor-control-plane-composes-existing-owners.md`
(`Accepted`) and `dotmac_starter_mt` `AGENTS.md` hard rule 24, the
product-first extraction rule. Those are cited here, not restated. A governance
record that re-narrates an accepted product decision creates a second copy of
it, which is the drift ADR 0006 § 5 and that same hard rule exist to prevent.

The formulation:

> Platform CP is Dotmac's preferred first proving assembly for modules with a
> real platform-plane consumer — not the universal first adopter for every
> module.

**The value is entirely in the second clause.** Read the first alone and it is a
licence to compose everything into Platform CP, which is the failure this
formulation exists to prevent. Michael's own words alongside it:

> Do not turn it into an assembly of every Starter package.

> Green tables with no production act are not adoption.

The pull toward that failure is structural rather than careless. Platform CP is
the newest assembly and has the fewest existing writers, so it is
simultaneously the **cheapest place to compose a module** and the **hardest
place to prove one** — there is little there yet to be a real consumer. Cheap
composition plus a green test table reads exactly like adoption while
establishing nothing, and "preferred first proving assembly" is the phrase that
would authorise it.

The repository, product identity and frozen coordinates for Platform CP are
[ADR 0016](0016-the-operator-facing-control-plane-is-dotmac-platform.md); this
record says nothing about naming.

## Decision

### 1. The formulation, both clauses

Platform CP is Dotmac's **preferred first proving assembly for modules with a
real platform-plane consumer**. It is **not the universal first adopter for
every module.**

The second clause is operative and is not a caveat on the first. A module with
no real platform-plane consumer is not a Platform CP candidate that is waiting
its turn; it is not a candidate.

### 2. The operative test: a REAL platform-plane consumer

The distinguishing criterion is a real platform-plane consumer, and the test is
deliberately narrow:

> Does a **production path in Platform CP actually READ AND WRITE** the module,
> and is a **local writer RETIRED** as a consequence?

Three things that look like qualification and are **insufficient**, each of them
the reason a module gets composed somewhere it should not be:

- **composability** — that the module *can* be mounted in the assembly;
- **schema readiness** — that its migrations run and its tables exist;
- **plane compatibility** — that its declared persistence plane matches one
  Platform CP has.

All three are properties of the module and the assembly in isolation. None is a
statement that anything uses it. A module can satisfy all three, be composed, be
migrated, pass every test, and have no production path touch it — which is the
state Michael's second sentence names: green tables with no production act.

The writer-retirement half is what makes the test hard to satisfy accidentally.
Adoption that adds a reader adds a consumer; adoption that **retires a local
writer** changes where a decision is made, and only the second is evidence that
authority actually moved.

### 3. Eligibility is a checked-in dossier, and its absence DISQUALIFIES

A module is eligible only with a **checked-in dossier** naming:

1. **Platform CP** as the intended proving assembly;
2. the **real consumer** — the production path that will read and write it;
3. the **persistence plane** it will occupy;
4. the **writer-retirement gate** — which local writer stops, and what proves it.

**An absent dossier disqualifies rather than defers.** The distinction is the
whole clause. *Defer* would mean the module is a candidate whose turn has not
come, and would have Platform CP holding a slot for work nobody has specified.
*Disqualify* puts the burden where it belongs: produce the dossier, and the
question can then be asked. Until then there is nothing to sequence, and a
module without one may not be composed into Platform CP on the strength of this
record.

### 4. The established first-adopter order is NOT overridden

The formulation's practical content is that it changes none of the following.
These are the accepted sequencing decisions, and this record cites rather than
re-decides them:

| Module | First adopter | Platform CP |
| --- | --- | --- |
| Brand Profiles | **Sub** | second |
| Files | **ERP** | — |
| Collections | **Sub** | second |
| Durable Timers | **Sub** | later |
| Integrator | separately deployed control plane | **never embedded** |

Integrator is a different kind of entry and is not a sequencing position: it is
a separately deployed control plane and is **never embedded** in Platform CP.
That is ADR-0024's independence rule as applied in `dotmac_starter_mt` ADR-0057
§ 8 — Platform CP's deployment-control module imports no Integrator model and
shares no database with one.

Where a module's first adopter is another product, "preferred proving assembly"
does not promote Platform CP ahead of it. The preference applies **among
candidates that pass § 2**, not against an existing accepted order.

### 5. What this record does not do

- It does not re-decide anything in `dotmac_starter_mt` ADR-0057, whose
  composition and ownership rules stand unchanged.
- It does not weaken hard rule 24. A module still comes from a qualifying
  production implementation; this record governs **where it is proved**, never
  **where it comes from**, and the two are routinely confused because a proving
  assembly is a tempting place to originate code.
- It does not make Platform CP an owner of anything. Composing a module is not
  acquiring its decisions.
- It does not authorise a single composition. Every candidate needs its own
  dossier under § 3.

## Consequences

- Some modules currently reasoned about as Platform CP work will turn out to have
  no real platform-plane consumer, and will stop being Platform CP work. That is
  the record functioning, and it will read as descoping.
- A dossier becomes a precondition rather than a deliverable, which front-loads
  work onto whoever proposes the composition. That cost is deliberate: it is
  cheaper than discovering after migration that nothing reads the tables.
- "Preferred" still means something. Among modules that pass § 2, Platform CP is
  the first assembly to try — this record narrows the population, it does not
  remove the preference.
- The writer-retirement requirement will occasionally be impossible to meet
  because the local writer is load-bearing elsewhere. That is a finding about the
  module's readiness, not a reason to relax the gate.
- Cross-repository propagation is not automatic. This record's scope is
  organization-wide, but whether `dotmac_starter_mt`'s own records gain a matching
  statement is a change in a repository Governance does not own — the same
  situation as open decision 20, and recorded here as open decision 31 rather
  than assumed.

## Drift prevention

**Enforcement status: none, and none is proposed here.**

Nothing in `standards_control` evaluates this record, and this record does not
ask for a rule family. The reason is a property of the subject rather than a
scheduling choice: **"a production path actually reads and writes it" is not
decidable from repository content.** A composed module, a migrated schema and a
passing test suite are exactly what an ineligible module also has — that is §
2's whole argument — so a static check over an enrolled repository would
confirm the three insufficient properties and could not observe the sufficient
one.

What IS decidable, and is the honest limit of automation here: whether a module
composed into Platform CP has a checked-in dossier naming the four items in §
3. That is a declaration check. It would catch a composition nobody specified,
and it would pass a dossier whose stated consumer does not exist — so it must
never be reported as evidence that § 2 holds.

Whether a running Platform CP production path reads a given module, and whether
a local writer was retired, are facts about deployed systems and about another
repository's records. ADR 0013 § 1 puts them outside repository-local
derivation and § 5 permits automation only through a declared oracle; a
writer-retirement claim is `adoption_evidence`-shaped, and where such evidence
exists it belongs in the owning repository's `EXTRACTION.toml` rather than
being re-asserted here.

This is therefore **stated review discipline**, which ADR 0013 § 5 permits so
long as it is said plainly rather than implied. It is said plainly: there is no
guard, and a module composed into Platform CP without a dossier is an
unreviewed composition, not a covered one.
