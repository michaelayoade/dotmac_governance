# 0031. A cross-repository ADR reference names its repository

- Status: Accepted
- Date: 2026-08-31
- Effective: 2026-08-31
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Governance-enrolled Dotmac repositories, and every document, comment or test that cites an architecture decision record
- Classification: Internal

## Context

### The hazard, measured

An ADR number is unique within a repository and meaningless across the fleet.
Numbering restarts at `0001` in every repository, so the same token names a
different decision in each — and nothing in a citation says which one.

Three distinct `Accepted` ADR-0014s exist today:

| Repository | ADR-0014 |
| --- | --- |
| `dotmac_starter_mt` | At-most-once execution has one owner |
| `dotmac_governance` | Build once and bind the environment late |
| `dotmac_platform_control_plane` | One browser authentication owner for the platform console |

`dotmac_platform_control_plane`
`src/vendor_cp/commercial_backfill/planner.py:29` reads *"before the effect
(ADR-0014's shape, applied to a planner)"*. It means the kernel's — at-most-once
execution — in a repository that now holds its own ADR-0014. Two candidate
meanings, one bare token, one file.

**It was already three-way before the record that appeared to cause it.**
`dotmac_starter_mt` and this repository both held an ADR-0014 as of 2026-08-29,
and that repository already disambiguates by hand in
`docs/CONTROL_EXCEPTIONS.md:263` ("Governance ADR 0014") while other references
in the same tree mean its own.

**The next collision is already loaded, and it is larger.** `ADR-0018` occurs
eight times in `dotmac_platform_control_plane`. Seven are bare — `AGENTS.md:162`,
`docs/ARCHITECTURE.md:242`, `tests/architecture/test_stale_claims.py:43` and
`:146`, `tests/migration/test_composed_live_catalog.py:48` and `:258`, and
`docs/adr/0006-allocations-greenfield-authority-switch.md:119` — and every one of
them means `dotmac_starter_mt` ADR-0018, the exemption rule. They resolve today
only **by elimination**, because that repository's own numbering stops at 0016.
The day it writes an ADR-0018, all seven silently change meaning. No file
changes, no diff, no review: the citations simply begin pointing somewhere else.

That is the property that makes this worth a record. **A reference that decays
without any edit cannot be maintained by care.**

### The exhibit: the failure is inside the exemplar

The eighth occurrence is the one that settles it.
`dotmac_platform_control_plane` `docs/adr/0016-api-documentation-exposure-policy.md:11-12`,
in that record's controlled `Relates to:` header:

> ADR-0018 in `dotmac_governance` (a guard exemption states an enforceable
> premise)

**That is the wrong repository.** This repository's ADR 0018 is *Authority
cutovers leave receipts and decommissions retire delegations*. The rule quoted is
`dotmac_starter_mt` ADR-0018, *A guard exemption must carry an enforceable
premise*. Both headings were read to confirm it.

This is not a criticism of that record, whose substance is sound and which this
repository has already built on. It is the opposite. **It is the one place in
that document where the author stopped, noticed a reference crossed a repository
boundary, and qualified it — and it still went to the wrong repository.**

A convention that fails in the hands of someone actively thinking about it is
not a convention with a compliance problem. It is a missing requirement.

### Why the existing numbering rule cannot reach it

`docs/adr/README.md` § Numbering already handles a collision — but a different
one, and the difference is the whole matter. It handles two branches picking the
same free number **within one repository**, resolved by "the ADR that merges
first keeps the number", with the loser renumbering and CI enforcing prefix
uniqueness.

None of that applies here. **Neither repository is wrong.** Both numbered
correctly in their own sequence, renumbering either would be arbitrary, and
prefix uniqueness is per-repository by construction. There is no defect to
repair in the numbering; the defect is in the *citation*.

### The convention does not exist yet, in either direction

Measured across the two repositories surveyed: `ADR-NNNN` occurs 2,477 times in
`dotmac_starter_mt`'s `docs/` alone, overwhelmingly bare. Qualification is the
rare exception.

And the qualified minority agrees on nothing. Within `dotmac_starter_mt` alone,
the same repository is named three ways:

- `Governance ADR 0014` — `docs/CONTROL_EXCEPTIONS.md:263`
- `Governance ADR-0013` — `docs/inventories/inventory-cutover-scoping.md:181`
- `` `dotmac_governance` ADR 0013`` — `AGENTS.md:708`

There is a pattern. There is no rule, nothing enforces one, and a detector
cannot be written against three spellings that were never chosen.

### Authority status

Michael Ayoade ratified the rule below on 2026-08-31, resolving open decision 38,
and directed the same ordering as ADRs 0028, 0029 and 0030: the ruling lands here
before the corresponding Knowledge entry is promoted. The approval is his;
§ "Acceptance — 2026-08-31" records it as an attributable event and is
transcribed, not made, by the drafting agent.

## Decision

### 1. The standard

> A cross-repository ADR reference names its owning repository. A bare number
> refers only to a record in the citing repository.

Both halves are required and neither is sufficient alone. The first makes an
outward reference resolvable. The second makes a bare reference *mean*
something, rather than meaning "probably local, unless the author was thinking
about it".

### 2. A bare number is a claim about locality

`ADR-0014`, unqualified, asserts that the citing repository holds a record at
that number and that this is the record meant. Where the citing repository has no
such record, a bare number is **wrong** — not merely unhelpful — even when only
one candidate exists anywhere in the fleet.

This is the half that does the durable work. It is what makes Platform CP's seven
bare `ADR-0018` references defective **today**, while that repository's numbering
still stops at 0016 and every one of them still resolves by elimination. Under
this rule they are already wrong and can be repaired now, in a quiet change,
rather than becoming wrong on the day someone writes an unrelated record and
notices nothing.

**A rule that only bites after the collision arrives would have been useless
here**, because the collision arrives without an edit.

### 3. The qualified form

A cross-repository reference is written as the owning repository's name,
then `ADR`, then the number as that repository writes it:

```
dotmac_starter_mt ADR-0018
dotmac_governance ADR 0031
dotmac_platform_control_plane ADR-0016
```

The repository name is the canonical repository name. A well-established short
name is acceptable where it is unambiguous — `kernel` for the kernel package's
home repository, `Governance` for this one, `Platform CP` — and the number keeps
whatever hyphenation the owning repository uses in its own headings, because a
reader who follows the reference should find the string they were given.

**The qualifier is the load-bearing part; the punctuation is not.** This section
picks one spelling so that a future detector has something to match and so the
three-way variance measured above stops growing. Changing the chosen spelling
later is cheap; having no chosen spelling is what made the variance possible.

### 4. What the reference must survive

A citation is written to remain correct when the *cited* repository adds records,
and when the *citing* repository does. Concretely, a reference is defective if it
would change meaning as a result of any repository adding a record at a number it
does not currently use — which is exactly the seven-reference case above.

Where a reference points at something whose identity must not drift at all — a
rule being adopted, a control being inherited, a premise being relied on — it
carries the coordinates ADR 0013 § 3 already requires: the exact path and a
peeled commit. **This record does not extend that requirement to every citation.**
Most references are pointers for a reader, not evidence, and demanding a commit
for each would make citation expensive enough that people stop citing.

### 5. Scope, and what this does not require

- It governs references to **architecture decision records**. It says nothing
  about how code cites issues, runbooks, specifications or tests.
- It does not require renumbering anything. **No ADR number changes as a result of
  this record**, in any repository.
- It does not require a sweep. Existing bare cross-repository references are
  defective, and repairing them is ordinary maintenance done as files are
  touched — except where a reference is load-bearing for a control, which is
  worth repairing on its own.
- It does not make this repository the owner of other repositories' documents. It
  states a citation convention that each repository applies to its own text.
- It creates no check and no CI gate. See § Drift prevention.

## Consequences

- Cross-repository references become longer. That is the cost, it is small, and
  it is paid by the writer rather than by the reader who would otherwise guess.
- Platform CP's seven bare `ADR-0018` references are defective as of this record,
  and can be repaired before the collision rather than after. The `Relates to:`
  header in its ADR-0016 is defective in the other direction — qualified, and
  qualified wrongly — and repairing it needs a correction to that record rather
  than a search-and-replace.
- Some existing bare references will turn out to be ambiguous in ways nobody has
  noticed, because elimination has been doing the work silently. Finding them is
  the useful outcome.
- The rule creates a small, permanent obligation on every future ADR that cites
  another repository — including this one, which is why § 3 fixes a spelling
  rather than leaving each author to invent one.
- Enrolled repositories acquire no new failing check from this record.

## Drift prevention

**Enforcement status: none yet.** No `standards_control` rule evaluates this
record, no `standards-profile.schema.json` field represents ADR citations, and no
engine diagnostic exists for it. This is stated review discipline, which ADR 0013
§ 5 permits so long as it is said plainly rather than implied.

Confirmed at this repository's `main` `18f6386` rather than carried over from
ADRs 0028, 0029 and 0030: `standards_control._governance` resolves exactly the one
path each enrolled profile declares as `governance_model.source` and reads a
single `- Status:` line from it; a search across `standards_control/`,
`gate_control/`, `agent_control/`, `programme_control/`, `tools/` and
`.github/workflows/` finds nothing that reads the ADR directory except
`tools/check_adrs.py`, which runs in this repository's own CI. All seven enrolled
profiles pin the same source,
`docs/adr/0006-cross-repository-engineering-conformance.md`, expecting status
`accepted`. **Adding this record turns no gate red in any enrolled repository.**

This rule is unusually **well suited** to automation, which is worth stating
because most of this repository's recent records are not. The property is
decidable from repository content alone: a bare `ADR-NNNN` in a repository whose
own `docs/adr/` holds no record at `NNNN` is defective by § 2, with no oracle, no
runtime observation and no cross-repository lookup required. That check is
strictly local, and it is the one that would have flagged all seven Platform CP
references today.

Two further shapes, each decidable but harder:

- a qualified reference whose named repository has no record at that number — the
  ADR-0016 header case, which needs the cited repository's ADR listing and is
  therefore a fleet check rather than a local one;
- a qualified reference using a spelling § 3 does not name, which is a lint and
  should be a warning rather than a failure until the existing variance is
  drained.

**Non-vacuity, stated in advance.** A checker must be shown RED on a planted bare
reference to a number the repository does not hold, and green on the same
reference qualified — and it must be shown RED on the ADR-0016 header itself,
which is the known-bad case this record was written from. A detector that passes
that header is not implementing this record, whatever else it does. It must also
not fire on a bare reference to a number the repository DOES hold, which is the
overwhelming majority of the 2,477 occurrences measured above; a check that
flags those has made the convention unusable and will be turned off.

Whether the local check is built, and by whom, is part of open decision 32.
Acceptance of this record does not make that decision: a standard being normative
is not evidence that a control enforces it.

## Acceptance — 2026-08-31

Michael Ayoade approved this record on 2026-08-31, resolving open decision 38.
Under `AGENTS.md` an agent may not occupy the approver role or approve its own
output; neither happened here. The standard in § 1 is his, transcribed. The
spelling fixed in § 3 and the scope limits in § 5 are the drafting agent's
implementation of it, and are the parts most safely changed later.

Acceptance covers the citation convention. It does not build a checker, does not
mandate a repair sweep, does not change any ADR number anywhere, and does not
extend this repository's `Amends:` relationship to `docs/adr/README.md`
§ Numbering — that section governs number assignment within a repository and is
untouched; this record governs how a number is cited across one.
