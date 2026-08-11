# 0008. The kernel testing kit is development-only across products

- Status: Accepted
- Date: 2026-08-11
- Effective: 2026-08-11
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories
- Classification: Internal
- Amends: 0006 — adds the kernel testing-kit import-locality rule family to the conformance profile and engine

## Context

`dotmac_kernel.testing` deliberately ships inside the kernel runtime wheel. It
contains an RLS-free SQLite engine, a session factory outside the kernel's one
transaction authority, fake providers, and Ed25519 signing helpers. Packaging
therefore cannot keep it out of a product's runtime path: any installed product
can import it.

The starter originally controlled the risk with directory-shaped exemptions.
Security scanning skipped the whole testing-kit tree, and architecture checks
treated broad path families as harmless. That made the exemption list free: a
new finding or importer could inherit an old justification without changing the
line that granted it. Starter ADR 0018 established the fleet rule that an
exemption must enumerate its real entry-point family, enforce its premise,
ratchet in both directions, separate grandfathering from correctness, and prove
the detector under sabotage.

Starter removed its blanket security exclusions and proved an AST import
detector against the real floor probe. The remaining boundary is
cross-repository. Product-local copies would recreate the drift class ADR 0006
exists to prevent, so the accepted Governance engine owns it.

## Decision

Schema version 4 adds one mandatory `testing_kit_boundary` object to every
enrolled repository profile. The object declares:

| Field | Meaning |
| --- | --- |
| `test_roots` | Existing repository-relative directories whose final component is exactly `tests`. |
| `kit_source_roots` | Existing source directories whose final components are exactly `dotmac_kernel/testing`; only the repository that assembles the kit needs one. |
| `conformance_probes` | Exact non-test Python files that exercise the installed kit, each with its expected number of testing-kit import statements. |

The engine inspects every tracked and untracked, non-ignored Python source in
the evaluated repository. It parses syntax rather than matching text and
recognises all supported static spellings:

- `import dotmac_kernel.testing` and imports below it;
- `from dotmac_kernel.testing` and imports below it; and
- `from dotmac_kernel import testing`.

An import is admitted only when its file is under a declared structural test
root, under the kit's own declared source root, or is one exact conformance
probe. A whole `scripts/`, `app/`, `src/`, package, task, worker, command, or
other runtime directory cannot be declared as a test root. A kit source root
must end in the package path it claims to assemble.

Every probe declaration is a two-direction ratchet. Its path must exist and its
observed import count must equal the profile exactly. More imports are new debt;
fewer imports are progress whose stale exemption must be removed. A syntax
error fails closed rather than turning the detector into a green no-op.

Four stable diagnostics enforce the boundary:

| Code | Fires when |
| --- | --- |
| `testing-kit.path.missing` | A declared test root, kit source root, or exact probe does not exist. |
| `testing-kit.syntax.invalid` | A Python source cannot be parsed and therefore cannot be inspected. |
| `testing-kit.import.forbidden` | Runtime or other non-test code imports the kit without an exact probe declaration. |
| `testing-kit.probe.count-mismatch` | A declared probe's observed imports move above or below its pinned count. |

Products adopt the rule by pinning the accepted Governance commit that carries
this record and migrating their profile to schema version 4 in the same change.
That migration is the review surface for the repository's structural test
roots, kit ownership, and exact probes.

## Acceptance record

On 2026-08-11, Michael Ayoade directed implementation of this central
Governance slice after accepting the fleet-wide exemption rule in starter ADR
0018 and reviewing the testing-kit boundary's real floor-probe canary. This
record attributes that human decision; agent-authored implementation and local
test results are not an approval or a compliance claim.

## Consequences

- Shipping development helpers in the runtime wheel is a deliberate boundary
  with a central executable guard, not a packaging accident.
- `scripts/floor/probe.py` in the starter is admitted as one exact probe with
  one import statement; `scripts/` itself receives no exemption.
- Sub and ERP need only declare their structural test roots. Their current
  testing-kit imports are test-local.
- `dotmac_vendor_control_plane/src/vendor_cp/providers.py` currently imports
  `FakeProvisioningProvider` from the kit at runtime. Schema-version-4 adoption
  must repair that product defect; it is not a reason to weaken or pre-waive the
  central rule.
- A repository pinned to an earlier Governance revision remains on its earlier
  schema until its owning product schedules the repin.

## Drift prevention

- The parser and JSON schema are closed: schema version 4 requires the boundary
  and offers no waiver or arbitrary module-name substitution.
- Test roots and kit roots are structurally constrained, so a product cannot
  rename a runtime directory as an allowed category in its profile.
- Exact probe paths fail when missing, and exact positive import counts fail
  upward, downward, and stale.
- `tests/test_standards_control.py` plants all five import spellings in a real
  runtime fixture file and requires `testing-kit.import.forbidden` at that path
  and line. It separately proves allowed tests, kit self-assembly, the exact
  probe, both count directions, missing roots/probes, invalid root shapes,
  syntax failure, and near misses.
- The checked-in required Governance profile runs the production engine with
  the same mandatory boundary products consume. Product CI must consume that
  engine at the exact accepted commit; a copied detector is not a substitute.
