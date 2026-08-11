# 0009. Vocabulary profiles model real member and storage shapes

- Status: Accepted
- Date: 2026-08-11
- Effective: 2026-08-11
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories
- Classification: Internal
- Amends: 0007 — the profile shape for primitive members and vocabularies with no persisted store

## Context

The first attempted starter adoption of schema version 4 found that ADR 0007's
profile shape could not describe two of the reference kernel vocabularies
truthfully.

`audit_actions` is intentionally a bare registered string vocabulary. Its
members are persisted in `audit_events.action`, but the hosting layer defines no
`AuditAction` class: the registry, not a host-enumerated type, decides whether a
code exists. `permissions` has the opposite shape. `PermissionSpec` is a real
declared member type and `PermissionCatalogue` validates it, but there is no
permission database store yet. The code-declared `default_roles` binding is the
only current decision; tenant-configurable grants are future work.

Schema versions 3 and 4 required every vocabulary entry to name both a custom
class path and a non-empty set of storage paths. A starter profile could
therefore pass only by omitting real vocabularies, inventing paths that do not
own the claimed concept, or creating a zero-consumer permission table. The
first two turn the review surface into fiction; the third violates the
product-first and zero-consumer rules. None is an admissible adoption path.

The failure is in the profile model, not in either registry. ADR 0007's
invariant remains correct: module-owned members stay open, are declared by
modules, and are validated by one registry; a backing column, when one exists,
must stay open.

## Decision

Schema version 5 carries every version-4 rule unchanged and replaces the
vocabulary member/storage fields with two explicit shapes.

`member_type` is a closed discriminated object:

- `{"kind": "declared", "name": "SettingDomain", "path": "..."}` names a
  repository-defined class. The engine proves the class exists and does not
  inherit from an enum family.
- `{"kind": "builtin", "name": "str"}` records a primitive open string
  vocabulary. `str` is the only admitted built-in; a wider arbitrary-type list
  would create a new unreviewed escape hatch.

`storage` is also explicit:

- `{"column": "action", "paths": ["..."]}` names the persisted surfaces. The
  engine continues rejecting database enums and literal `IN (...)` constraints
  that close the column.
- `null` states that the vocabulary has no persisted store. The key remains
  mandatory so absence is visible in every profile review rather than inferred
  from a missing field.

Registry interface, registry implementation, declaration field, and declaration
paths remain mandatory for both member shapes and both storage shapes. This is
not a waiver: a primitive member still needs one validating registry and a
module declaration point; a storage-less vocabulary still needs both as well.

The profile version increments rather than changing version 4 in place. A
repository pinned to the accepted version-4 revision keeps its immutable
contract. A repository adopting the revision that carries this record migrates
directly to version 5 in the same pin change.

On 2026-08-11, Michael Ayoade explicitly accepted this record after reviewing
the Starter adoption defect and the schema-version-5 correction. Agent-authored
implementation and local diagnostics are not approval or evidence of
organization-wide conformance.

## Consequences

- Starter can inventory `audit_actions` without inventing a class and
  `permissions` without inventing persistence.
- A real persisted vocabulary cannot hide its closed column behind
  `storage: null` by technical discovery; as with omitting a whole vocabulary,
  that is a profile-review failure. The engine enforces what the profile names
  and does not pretend heuristic discovery can distinguish genuinely closed
  sets from module-owned ones.
- Existing declared-type and persisted-storage checks keep their stable
  diagnostics and sabotage proofs.
- The testing-kit boundary introduced by ADR 0008 remains mandatory and
  unchanged in version 5.
- Products pinned to schema-version-3 or schema-version-4 Governance revisions
  are unaffected until their own explicit repin.

## Drift prevention

- The JSON schema and runtime parser both require one of exactly two member
  shapes and require `storage` to be either the closed storage object or `null`.
- A built-in member is restricted to `str`; extra keys, a source path on a
  built-in, or a missing path on a declared member fail the profile.
- `tests/test_standards_control.py` proves both starter shapes independently:
  a built-in string member with real storage (audit actions), and a declared
  member with `storage: null` (permissions). Unsupported built-ins, ambiguous
  member shapes, implicit storage absence, closed declared types, and closed
  persisted columns fail.
- Product adoption must inventory each real vocabulary in the profile diff. An
  omitted vocabulary or a false `storage: null` remains an explicit review
  finding, not a condition this syntax-only engine claims to discover.
