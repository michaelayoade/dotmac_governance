# Cross-repository engineering conformance

`standards_control` is the development-only engine accepted by ADR 0006. The
checked-in Governance profile is `required`; a green run is conformance
evidence for the evaluated revision, not a certification or compliance claim.

Each strict schema-version-5 profile names repository URL/default branch, its
governance source, protected resources with one owner/writer boundary, drift
tests, exact Python contract surfaces, its module-declared vocabularies, and the
kernel testing-kit import boundary. The
typed gate rejects `Any`, missing or bare public annotations, unannotated record
fields, and mutable boundary records. Schema version 5 has no waiver mechanism.

## Kernel testing-kit import locality (ADR 0008)

`dotmac_kernel.testing` ships in the runtime wheel but is development-only. The
engine AST-scans every repository Python source and admits its imports only
under structural `tests` roots, under the kit's own exact source roots, or from
an exact conformance probe with a pinned import count:

```json
{
  "test_roots": ["tests"],
  "kit_source_roots": [
    "packages/dotmac-kernel/src/dotmac_kernel/testing"
  ],
  "conformance_probes": [
    {
      "path": "scripts/floor/probe.py",
      "expected_import_count": 1
    }
  ]
}
```

The object is mandatory even when `kit_source_roots` and
`conformance_probes` are empty. Declared roots and probes must exist. Test roots
must end in `tests`; kit roots must end in `dotmac_kernel/testing`; probes must
be exact Python files outside both. Probe counts are two-direction ratchets, so
an added import and a stale exemption both fail. There is no blanket `scripts/`
or runtime-package exclusion.

## Module-declared vocabularies (ADR 0007)

A vocabulary whose members belong to modules is declared by those modules and
validated by a registry; the layer that hosts it never enumerates the members,
and a backing column, when one exists, is never pinned to a fixed member list.
Each `module_declared_vocabularies` entry names the member shape, the registry
symbol that validates a member, the manifest field a module declares members
on, and its explicit storage shape:

```json
{
  "vocabulary_id": "setting-domain",
  "subject": "Setting domains a module owns.",
  "member_type": {
    "kind": "declared",
    "name": "SettingDomain",
    "path": "packages/dotmac-kernel/src/dotmac_kernel/settings_models.py"
  },
  "registry_interface": "dotmac_kernel.setting_domains.SettingDomainRegistry",
  "registry_implementation": "packages/dotmac-kernel/src/dotmac_kernel/setting_domains.py",
  "declaration_field": "setting_domains",
  "declaration_paths": [
    "packages/dotmac-kernel/src/dotmac_kernel/features.py",
    "packages/dotmac-kernel/src/dotmac_kernel/modules.py"
  ],
  "storage": {
    "column": "domain",
    "paths": ["packages/dotmac-kernel/src/dotmac_kernel/settings_models.py"]
  }
}
```

The alternatives are independent. An audit-action-shaped vocabulary can use an
open built-in member and still name its real store; a permission-shaped
vocabulary can name its declared spec while stating that no override store
exists yet:

```json
{
  "member_type": {"kind": "builtin", "name": "str"},
  "storage": {
    "column": "action",
    "paths": ["packages/dotmac-kernel/src/dotmac_kernel/audit.py"]
  }
}
```

```json
{
  "member_type": {
    "kind": "declared",
    "name": "PermissionSpec",
    "path": "packages/dotmac-kernel/src/dotmac_kernel/permissions.py"
  },
  "storage": null
}
```

`str` is the only built-in member type. `storage` is required even when null;
that makes "no store exists" part of the review surface instead of an inference
from an omitted field.

The engine reads syntax and never imports product code. It reports
`vocabulary.member-type.closed` when the member type subclasses an enum,
`vocabulary.registry.missing` when nothing validates a member,
`vocabulary.declaration.missing` when no manifest carries the declaration field,
and `vocabulary.storage.closed` when a declared database store uses an enum type
or a `CheckConstraint` with a literal `IN (...)` list. An empty array is legal
and means the repository hosts no such vocabulary — a claim reviewed in the
profile diff, since the engine evaluates declarations rather than discovering
them. A false `storage: null` is the same class of review failure; the syntax
engine does not claim it can discover semantic ownership reliably.

`owner_implementation` is repository-relative while `decision_interface` is an
importable Python symbol. Flat layouts map directly; for a standard `src`
layout, the module begins after the nearest `src` segment. For example,
`src/vendor_cp/licensing/service.py` owns
`vendor_cp.licensing.service.issue_licence`, and
`packages/kernel/src/dotmac_kernel/db.py` owns `dotmac_kernel.db.get_db`.

Only `dotmac_governance` may select a `local` governance source. Every product
uses `kind: pinned`, naming the canonical Governance repository, exact
40-character accepted commit, ADR path, and accepted status. The composite
action supplies its actual repository and `github.action_ref`; mismatched,
missing, branch-named, or tag-named identities fail before product rules run.

Run locally (where `origin/HEAD` resolves the default branch):

```bash
python3 -m standards_control verify --root . \
  --profile .dotmac/standards-profile.json
```

CI passes trusted repository metadata explicitly:

```bash
python3 -m standards_control verify --root . \
  --profile .dotmac/standards-profile.json \
  --default-branch main --format json
```

Product CI consumes the composite action at the exact accepted Governance
commit; a mutable branch or tag is not an admissible policy identity:

```yaml
- name: Enforce Dotmac engineering standards
  uses: michaelayoade/dotmac_governance/.github/actions/standards-check@<accepted-40-character-sha>
  with:
    default-branch: ${{ github.event.repository.default_branch }}
```

The action invokes the Governance-owned engine against the caller workspace.
It installs nothing into the product runtime and retrieves no credential.
Repository access for private actions remains runner configuration, not logic
copied into the action.

A product profile's governance reference therefore has this shape:

```json
{
  "kind": "pinned",
  "canonical_url": "https://github.com/michaelayoade/dotmac_governance",
  "revision": "<accepted-40-character-sha>",
  "source": "docs/adr/0006-cross-repository-engineering-conformance.md",
  "status": "accepted"
}
```

Product rollout is inventory, candidate profile, local repairs with sabotage
proofs, accepted governance plus required mode, green CI merge, then protected
branch read-modify-write and independent readback. A product repins to the
accepted revision carrying the required rule family and moves its profile to
the matching schema version in the same change; a product pinned to an earlier
revision is unaffected until it repins. Git and product CI remain
authoritative; Knowledge may index only source pointers and structured results.
