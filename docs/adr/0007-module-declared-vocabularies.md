# 0007. Module-declared vocabularies, never host-enumerated lists

- Status: Accepted
- Date: 2026-08-07
- Effective: 2026-08-07
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories
- Classification: Internal
- Amends: 0006 — adds a third rule family to the conformance profile and engine

## Context

A layer that serves consumers it has never seen cannot enumerate the values
those consumers will need. Every list it hard-codes is a list that is wrong for
the second consumer, and every addition ships a migration to every deployment.

Dotmac hit this concretely in `dotmac-kernel`. `SettingDomain` was a five-member
Python enum backed by a `sa.Enum` CHECK constraint on `domain_settings.domain`.
Those five are the starter's own domains. `dotmac_erp` runs twenty-one
(`payroll`, `banking`, `gl`, `fleet`, `procurement`, …) and `dotmac_sub`
twenty-eight. Neither product could adopt the kernel's settings subsystem
without abandoning its own domains or landing a kernel migration per product —
and "the kernel ships a migration whenever a product invents a value" is not a
foundation, it is a bottleneck with a version number.

The kernel had already resolved the same pressure four times — permissions,
capabilities, audit actions, feature flags — each time by having modules DECLARE
their members on a manifest and a registry validate them, and each time as a
local decision rather than a stated rule. Four undocumented instances of a
pattern is precisely how the fifth came to be built as an enum. Michael accepted
the rule fleet-wide on 2026-08-07; the product-side record is
`dotmac_starter_mt` ADR 0008, which carries the reference implementation.

Prose cannot enforce this. "Do not enumerate your consumers' values" is
unfalsifiable without naming the type, the registry, the declaration slot, and
the column — which is what a conformance profile is for. ADR 0006 already owns
that mechanism for authority boundaries and typed contract surfaces; this record
adds a third rule family rather than a second engine.

## Decision

### The rule

A vocabulary whose members belong to modules is declared by those modules and
validated by a registry. The layer that HOSTS the vocabulary never enumerates
its members, and the backing column is never pinned to a fixed member list.

The rule is about ownership, not about enums. A closed enum remains the correct
type for a genuinely closed set — `INSERT`/`UPDATE`/`DELETE` on a trigger-backed
audit log has no module that owns a member of it and never will. What this
record constrains is a vocabulary whose members belong to somebody else.

### Profile contract

`standards-profile.json` moves to schema version 3 and gains a required
`module_declared_vocabularies` array. Each entry names, for one vocabulary:

| Field | Meaning |
| --- | --- |
| `vocabulary_id` | Stable identifier, unique within the profile. |
| `subject` | What the vocabulary means, in one sentence. |
| `member_type` + `member_type_path` | The type a member value has, and where it is defined. |
| `registry_interface` + `registry_implementation` | The symbol that validates a member, and the file that owns it. |
| `declaration_field` + `declaration_paths` | The manifest field a module declares members on, and the manifest definitions carrying it. |
| `storage_column` + `storage_paths` | The persisted column, and the model definitions that shape it. |

An empty array is legal and means "this repository hosts no module-declared
vocabulary". That is a claim reviewed in the profile diff, exactly as the
`authorities` list already is; see *Drift prevention* for what this does and
does not detect.

### Diagnostics

Seven stable codes, evaluated per declared vocabulary:

| Code | Fires when |
| --- | --- |
| `vocabulary.path.missing` | A declared path does not exist. |
| `vocabulary.syntax.invalid` | A declared path is not valid UTF-8 Python. |
| `vocabulary.member-type.missing` | The member type is absent from its declared path. |
| `vocabulary.member-type.closed` | The member type subclasses `Enum`/`IntEnum`/`StrEnum`/`Flag`/`IntFlag` — it enumerates its own members. |
| `vocabulary.registry.missing` | The registry interface is absent from its declared implementation. |
| `vocabulary.declaration.missing` | The declaration field is not an annotated field of any class in a declaration path, so no module can declare a member. |
| `vocabulary.storage.closed` | The storage column is pinned by a database enum type, or by a CHECK constraint naming the column with a literal `IN (...)` list. |

Schema version 3 keeps version 2's posture: strict, closed, no waiver
mechanism. A profile is either conformant or it is not.

### Rollout

Products repin to the accepted revision carrying this record and move their
profile to schema version 3 in the same change, per the ADR 0006 rollout
protocol — inventory, candidate profile, local repairs with sabotage proofs,
accepted governance plus required mode, green CI merge. A product pinned to an
earlier Governance revision is unaffected until it repins, which is what makes
this a schedule rather than a break.

## Consequences

- The three checks correspond to the three ways the rule is broken in practice:
  the member type is an enum again, nothing validates a member, or the column
  re-closes what the type opened. A repository that passes all three has an
  extension point, not a hard-coded list.
- Known non-conformances at the time of writing, recorded so adoption is
  scheduled rather than discovered: `dotmac_erp/app/models/domain_settings.py`
  (`SettingDomain`, 21 members, native Postgres enum) and
  `dotmac_sub/app/models/domain_settings.py` (28 members, same storage). Each
  owning repository decides when; neither blocks Governance.
- `dotmac-kernel` is the reference implementation: five vocabularies —
  `permissions`, `capabilities`, `audit_actions`, `feature_flags`,
  `setting_domains` — each declared on a module manifest and validated by its
  own registry.
- The engine reads syntax, never imports product code, and adds no runtime
  dependency to any product. It remains development-only.

## Drift prevention

- `standards_control` evaluates every declared vocabulary on every product CI
  run under `required` enforcement; a violation is an error diagnostic, and
  schema version 3 offers no waiver.
- `tests/test_standards_control.py` carries a sabotage proof per diagnostic
  code: each check is shown to fail on a planted violation and pass once the
  violation is removed, so a check cannot silently become vacuous.
- **What this does not detect:** a vocabulary that is never declared in the
  profile at all. The engine evaluates declarations, not discoveries, and a
  heuristic scan for "enums that look like vocabularies" would produce false
  positives on genuinely closed sets — the exact distinction this record turns
  on. The review surface is the profile diff, the same property ADR 0006's
  `authorities` list already has. A repository adding a vocabulary without
  declaring it is a review failure, not an engine failure, and the honest
  statement of that limit is preferable to a check that appears to cover it.
