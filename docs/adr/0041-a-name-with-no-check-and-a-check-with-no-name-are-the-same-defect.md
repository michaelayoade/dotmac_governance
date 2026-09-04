# 0041. A name with no check and a check with no name are the same defect

- Status: Proposed
- Date: 2026-09-04
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository that publishes or consumes a cross-party verification vocabulary — recovery receipts first
- Classification: Internal
- Amends: 0022 — § 3's enumeration and § 4's "the verdict IS the enumerated set", as applied to an externally executed restore whose receipt vocabulary cannot express four of those properties

## Context

### What was measured

Read on 2026-09-04 from `dotmac_starter_mt` `origin/main` at `b0be4340`, in
`packages/dotmac-deployment-foundation/src/dotmac_deployment_foundation/` —
named by symbol, because a line number decays.

`recovery.VERIFICATION_CHECKS` performs **twelve** comparisons:

```
roles · memberships · ownership · direct_privileges · effective_privileges ·
default_privileges · row_security · security_definer_routines · schema ·
extensions · migration_heads · isolation_invariants
```

`spec.BackupDataset.VERIFICATIONS` — what a descriptor may **require**, and
therefore what a receipt may **claim** — holds **seven**: `schema`,
`row_counts`, `migration_heads`, and `recovery_identity.PRIVILEGE_VERIFICATIONS`
(`roles`, `ownership`, `memberships`, `effective_privileges`).

The two sets disagree in both directions, and the package already knows it:

- `recovery.EXTERNAL_ONLY_VERIFICATIONS = {"row_counts"}` — **declarable and not
  performed here.** Already repaired: `spec.py` refuses it at parse for a
  dataset with no external executor, so the refusal lives in one place instead
  of in every descriptor.
- `recovery.UNDECLARED_COMPARISONS` — **performed and not declarable**, six
  members, carried as *frozen debt rather than a design*:
  `direct_privileges`, `default_privileges`, `row_security`,
  `security_definer_routines`, `extensions`, `isolation_invariants`.

`tests/unit/test_deployment_foundation_verification_registry.py` asserts both
differences exactly — `PERFORMED - DECLARABLE == UNDECLARED_COMPARISONS` and
`DECLARABLE - PERFORMED == EXTERNAL_ONLY_VERIFICATIONS` — so the gap is
ratcheted in both directions and cannot widen quietly. **The debt is measured,
declared and held.** This record is not reporting a discovery; it is deciding
what to do about a gap its owner already wrote down.

### What the gap costs, against this repository's own accepted standard

ADR 0022 § 3 enumerates **nine properties** a rehearsal must prove. Mapping the
six undeclarable checks onto them:

| Undeclarable check | ADR 0022 § 3 property |
| --- | --- |
| `direct_privileges` | 4 — GRANTs |
| `default_privileges` | 4 — DEFAULT PRIVILEGES, named in the property |
| `row_security` | 5 (RLS enabled **and** forced) and 6 (policies present, attached to existing roles) |
| `extensions` | 7 — the extension set |
| `isolation_invariants` | 9's declared-invariant half, classified as restore defect or pre-existing drift |
| `security_definer_routines` | **none** |

So **four of § 3's nine properties — 4, 5, 6 and 7 — cannot be claimed by an
external receipt at all**, and property 9 is claimable only through
`effective_privileges`, not through its declared-invariant half.

Stated as the thing a relying party actually faces: **an externally executed
restore can satisfy every verification its descriptor is capable of requiring
and still have proved five of nine properties.** The receipt is not lying. Its
vocabulary has no word for the other four, so the omission is indistinguishable
from a restore that verified them and simply had no way to say so.

**That is § 4's forbidden summary verdict**, arriving through a vocabulary
rather than through anybody's choice:

> A recovery verdict is the property set in § 3, reported per property. It may
> not be redefined as a smaller set of checks that stands in for them.

### The sixth check, which is a gap in § 3 rather than in the vocabulary

`security_definer_routines` maps onto no § 3 property, and its own docstring
says why it matters: it is *"the path a privilege walk does not see"* — a role
whose only access runs through a `SECURITY DEFINER` routine **holds no table
privilege**, so property 9's effective-privilege method, which this repository
required precisely because listings miss membership and `PUBLIC`, misses this
one too. The implementation found a property the standard does not enumerate.

### The mirror, which is why this record is about vocabularies and not about six names

`row_counts` was **a name with no check**: a receipt could claim it and nothing
here could observe it. It was repaired by refusing the name where it cannot be
answered.

These six are **a check with no name**: a real verification runs and no document
can carry it.

They are the same defect twice and they mislead in opposite directions. A name
with no check makes a **false claim** — the relying party trusts more than was
verified. A check with no name makes a **true verification unclaimable** — the
relying party trusts less than was verified, and, worse, **cannot distinguish
"row security was checked" from "row security was not checked."** The second is
the more dangerous of the two, because nothing about it looks wrong: every
required name is present, and the document is complete on its face.

## Decision

### 1. The standard

> A verification vocabulary is a **published contract**, and every check a
> facility performs on a relying party's behalf must be **nameable in it**. A
> check with no name is not a weaker claim — it is an unclaimable one, and the
> relying party cannot tell it from a check that never ran.

### 2. The six become separately declarable names

Michael's ruling, 2026-09-04, transcribed:

> Add these as **separately declarable verification names**:
> `direct_privileges`, `default_privileges`, `row_security`,
> `security_definer_routines`, `extensions`, `isolation_invariants`.
>
> **Update Foundation and the external-recovery/Governance contract together.**
> A signed external receipt must report each one **separately, including
> evidence digest and an explicit unknown state. Do not collapse them into one
> recovery boolean.**
>
> **Do not reopen a6 for this.** These become mandatory before: production
> `recover` is reintroduced · recovery is called complete · the legacy executor
> is retired.

### 3. Separately, with an evidence digest — never one boolean

Each name reports **its own outcome**, and each outcome carries **the digest of
the evidence that answered it**.

"Do not collapse them into one recovery boolean" is the anti-pattern named, and
it deserves its own sentence because collapsing is how the gap arose: six facts
behind one flag is indistinguishable from one fact, and a flag cannot be
partially true. A receipt reporting `recovery: true` has told the relying party
nothing about which of the six were looked at.

The evidence digest is what stops the wider vocabulary from becoming a wider
surface for unfalsifiable claims. `external_recovery.VERIFICATION_EVIDENCE`
already answers *what each verification is answered BY* for the existing seven,
and states the reasoning: *"a receipt claiming `effective_privileges` is
claiming something about a specific body of evidence, and a reader deciding
whether to trust it needs to know which."* Six new names inherit that
requirement rather than being exempted from it by newness.

### 4. UNKNOWN is a value, and it is the load-bearing half

A verification that **could not be performed says so**. Not absent. Not `false`.

Three documents that must stay distinguishable:

| The receipt | Means |
| --- | --- |
| omits the name | the executor makes **no claim** about it |
| reports it **unknown** | the executor **tried and could not answer** |
| reports it **failed** | the executor **answered, and the answer was bad** |

Collapsing any two of those recreates the defect this record repairs, one level
in. `false` for "could not check" is the worst of the three, because it will be
read as a finding and chased; and absence for "could not check" is the one that
passes silently, which is exactly how four of nine properties came to be
unclaimable without anybody deciding it.

**This is the third instance of one rule in this fleet, and it is stated as the
rule rather than as a receipt detail:** the Knowledge health surface's
`UNMEASURED` separates *dropped* from *never sent*; a first deployment is a
positive claim rather than an empty prestate; and this repository's ADR 0040 § 6
(`Proposed`, cited as a draft rather than as policy) refuses a null that means
both *anonymous* and *unrecorded*. **One absence must not carry two facts.**

### 5. Both halves move together, because neither can move alone

The vocabulary spans a **party** boundary, not merely a repository one: a
receipt is produced by an external executor —
`recovery_identity.EXECUTOR_KINDS` is `managed_database_service`,
`backup_platform`, `operator_team`, `sibling_product` — and read by the
deployment that is deciding whether it has a backup.

Widening therefore requires, in one coordinated change:

1. **Foundation** — the six names join the declarable vocabulary
   (`BackupDataset.VERIFICATIONS`) and gain evidence mappings
   (`external_recovery.VERIFICATION_EVIDENCE`); `UNDECLARED_COMPARISONS` shrinks
   by exactly the names that moved.
2. **The receipt schema** — per-name outcome, evidence digest, and the explicit
   unknown state of § 4. A schema that can only carry a name-list cannot express
   § 4 and is not sufficient for this.
3. **The descriptor** — a dataset may require the new names, so a product can
   say which of them its recovery depends on.
4. **Acceptance** — a receipt that omits a required name is refused, which
   already holds, and a receipt that reports one **unknown** does not satisfy a
   requirement for it.

**Neither side can move first without breaking the other**, and that is the
whole finding rather than a scheduling inconvenience: Foundation widening alone
produces names no receipt can carry; a receipt schema widening alone produces
claims no descriptor can require and no acceptance path checks.

### 6. A receipt written under the narrow vocabulary keeps its narrow meaning

Widening the vocabulary **does not retroactively enlarge what an existing
receipt attests.** A receipt produced under the seven-name contract attests
those seven and is silent — not affirmative — about the six.

This is stated because the opposite is the convenient reading, and it would
convert a body of documents nobody re-examined into evidence of properties
nobody checked. An existing receipt does not become false. It becomes
**precisely bounded**, which it always was.

### 7. § 3 gains the property the implementation already proves

ADR 0022 § 3's enumeration becomes **ten** properties, the tenth being the
`SECURITY DEFINER` routine set. § 4 requires the verdict to be the enumerated
set, and a name that is declarable, claimable and performed while sitting
outside the enumeration would leave the two documents disagreeing about what a
rehearsal proves.

This is the one inference in this record rather than a transcription: the ruling
makes `security_definer_routines` declarable, and § 3 is where a declarable
recovery property lives. It is called out so it can be struck without disturbing
anything else.

### 8. The three preconditions are a gate

The six names are **mandatory before**:

- production `recover` is **reintroduced**;
- recovery is **called complete**;
- the **legacy executor is retired**.

A gate, not a note. Each of the three is a claim about the world that would be
false while four of § 3's properties remain unclaimable — most sharply the
second, since "recovery is complete" is exactly the summary verdict § 4 refuses.

### 9. What this record does not decide

- **Field names and wire shape** of the widened receipt. § 3 and § 4 state what
  it must be able to express; the schema belongs to its owner.
- **Who signs**, and how a key is bound to an executor identity. Unchanged.
- **Schedules.** The Foundation half is briefed to land in `0.4.0a1`, which this
  record notes rather than decides, and `a6` is explicitly not reopened for it.
- **The relying-party acceptance owner** and the legacy executor's retirement
  date — open decision 48.

## Consequences

**The estate's recovery evidence is narrower than its standard, and this record
makes the difference sayable rather than closing it.** Until the widening lands,
an externally executed restore's receipt attests five of nine properties, and
the honest reading of such a receipt is *"the declarable subset held"* rather
than *"the recovery was proved."* Any document, dashboard or dossier that reads
an accepted external receipt as a § 3 rehearsal is overstating it today.

**Six new names is six new ways to be silently unanswered**, which is why § 4 is
written before § 5. A vocabulary that gains names faster than it gains the
ability to say *unknown* has moved the defect rather than repaired it.

**The two-directional ratchet already in the implementation is what makes the
widening checkable.** `UNDECLARED_COMPARISONS` shrinking without the name
appearing in the declarable vocabulary already fails, so a partial widening
cannot be mistaken for a complete one. That property was built before this
record and is the reason the change can be verified at all.

**And one property was found by the implementation rather than by the
standard.** § 7's tenth property exists because somebody wrote a check for a
reach that § 3 never enumerated. That is the healthy direction for this kind of
disagreement, and it is worth noticing that the enumeration was incomplete in
the same document that forbids summarising it.

## Drift prevention

**Enforcement: none in this repository.** No check family, no
`standards_control` rule, no `standards-profile.schema.json` surface, no CI gate
is created here. The controls live where the vocabulary lives, and whether they
exist is a fact about another repository's tests under ADR 0013 § 1.

What must be true in the implementing repositories for this record to be more
than intent:

- **The registry ratchet keeps both directions** and is updated in the same
  change that moves a name, so `UNDECLARED_COMPARISONS` cannot shrink without
  the declarable vocabulary growing.
- **A negative control per new name** — a receipt claiming the name while the
  underlying evidence is absent is **refused**, and refused for that reason.
  ADR 0021 § 4's rule applies unchanged: a mutation that fails for any reason
  proves nothing about the one it was written for.
- **A control for UNKNOWN specifically**, because it is the value that will be
  implemented last and tested least: a receipt reporting a required name as
  unknown must **not** satisfy that requirement, and a test must exist that
  fails if it does. Omitting this leaves `unknown` as a synonym for `passed`.
- **The relying party's acceptance path is the subject**, not the producing
  facility's own test suite. A facility proving it can emit a name says nothing
  about whether a counterparty's document is refused when it omits one.

**The sensitivity trap for this record specifically:** a widened vocabulary over
an estate that has produced **zero external receipts** passes every check
trivially. Six names with no document to carry them is the same shape as the gap
being repaired — a contract nothing exercises — and the first real receipt is
the first evidence that the widening works.

Open decision 48 records what acceptance leaves undecided: the receipt schema's
shape, the relying-party acceptance owner, and the legacy executor's retirement
condition.
