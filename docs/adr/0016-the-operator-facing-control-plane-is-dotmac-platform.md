# 0016. The operator-facing control plane is Dotmac Platform

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: `michaelayoade/dotmac_vendor_control_plane` and every repository that cites its coordinate — `dotmac_starter_mt`, `dotmac_erp`, `dotmac_sub`, `dotmac_observability`, `dotmac_governance`
- Classification: Internal

## Context

On 2026-08-29 a decision was taken that the application owned by the Vendor
Control Plane is presented publicly as **Dotmac Platform** at
`platform.dotmac.io`, while the repository coordinate, distribution name,
import package, database, migration lineage, image, environment contracts and
OpenBao paths all stayed as they were. That decision was recorded in Knowledge
under `vendor-control-plane-public-identity-is-dotmac-platform` and never
became an ADR.

This record changes the repository half of it. It carries neither `Amends` nor
`Supersedes`, and the omission is deliberate rather than forgotten: both fields
point at a four-digit ADR number, and the earlier decision has none. Naming it
in prose is the honest available form. Anyone reading the Knowledge entry
should treat its "keep stable: repository `dotmac_vendor_control_plane`" line
as replaced by this record once this record is accepted.

**Why "Vendor" is the wrong word.** The repository's public identity is
`platform.dotmac.io`, and its role is the operator-facing assembly: the surface
through which a Dotmac operator sees and drives accounts, offers, commercial
agreements, licences, entitlement allocation, approvals, release evidence and
deployment targets. "Vendor" names a commercial relationship, which is one
subject among those, and it reads as a second party rather than as the
operator's own console.

**What the new word must not be taken to mean.** Platform is the operator-facing
assembly, **not the owner of every capability it presents.** The composition
below is what the name has to keep visible, and it is verified rather than
asserted:

- `dotmac-deployment-control` owns deployment plans, approvals, attempts and
  receipts. At `dotmac_vendor_control_plane` `main` commit `94c0b736`, it is
  exact-pinned at `0.1.0a2` (`pyproject.toml:84`), enforced by
  `tests/architecture/test_cutover_readiness.py::test_the_composed_modules_are_exact_pinned`,
  which requires every `dotmac-*` dependency to match `0\.\d+\.\d+a\d+`. Its
  migration lineage is composed through the module's own `versions_dir()`
  (`src/vendor_cp/migrations.py`), its manifest through the module's own
  `module` object (`src/vendor_cp/assembly.py`), and the only seam is the
  100-line read-only `src/vendor_cp/deployment/adapter.py`. No table of the
  module's is redeclared locally: `src/vendor_cp/deployment/` contains exactly
  `__init__.py` and `adapter.py`, and no `__tablename__` anywhere under `src/`
  belongs to `mod_deploy`.
- The deployment foundation (`dotmac-deployment-foundation`) owns target-side
  rendering and execution.
- ERP and Sub own their own runtimes and their own business decisions.

Renaming an assembly to "Platform" is exactly the moment at which those four
sentences stop being obvious, which is why they are recorded here rather than
left to the README.

**The rename is not free, and the cost is concentrated in one gate.** The
required status check `Dotmac engineering standards` runs the Governance
conformance engine pinned at `a19259b10568d29dc0a9617347498fea7f1e7a97`. That
engine compares `.dotmac/standards-profile.json`'s
`repository.canonical_url` against the repository's observed git origin
(`standards_control/engine.py`, `_git_origin`). The two must agree, and a
GitHub rename changes one of them.

## Decision

**1. The repository is renamed to `dotmac_platform_control_plane`.** GitHub
serves redirects from the old coordinate for web, git and API access. No
repository may be created at the old name, because creating one destroys those
redirects.

**2. The product identity becomes "Dotmac Platform".** The canonical hostname
`platform.dotmac.io` is retained unchanged from the 2026-08-29 decision.

**3. These coordinates are FROZEN by this record and are not renamed with the
repository.** Each is either persisted data, a wire value, or live host state,
and renaming any of them is a migration rather than a rename:

| Coordinate | Current value | Why frozen |
| --- | --- | --- |
| Distribution | `dotmac-vendor-control-plane` | `pyproject.toml` name; the private-index artifact identity |
| Import package | `vendor_cp` | every module path under `src/` and every consumer's evidence path |
| Migration lineage | `alembic/versions/v001…v018` | applied revision ids in the production `alembic_version` table |
| Database | `vendor_control_plane`; roles `app_admin` / `app_user` / `platform_api` | live production state |
| Compose project | `dotmac_vendor_control_plane` | container and volume names on the production host |
| Image | `ghcr.io/michaelayoade/dotmac_vendor_control_plane` | every published digest, and the digests cited as adoption evidence in Starter dossiers |
| Environment contract | the `VENDOR_*` variables, including the `production` environment's `VENDOR_PRODUCTION_HOST` / `_USER` / `_DEPLOY_DIR` / `_SSH_KEY` / `_KNOWN_HOSTS` | configured outside the tree |
| OpenBao | `secret/dotmac/vendor-control-plane/production/{database,runtime,deploy-ssh}` | held material; a path change is a re-creation |
| Deploy target | `vendor-cp-prod`, `/opt/dotmac/vendor-control-plane` on `149.102.158.144` | live host state |
| Audit vocabulary | the 24 `vendor.*` platform audit actions | written into `platform_audit_log` rows |
| Licence source contract | `APPLICATION = "dotmac-vendor-control-plane"` (`src/vendor_cp/licensing/source_contract.py`) | a field inside a digested contract; changing it changes the digest |

Renaming any frozen coordinate is a separate decision, taken only where the
benefit exceeds the migration risk, and each needs its own record.

**4. Historical evidence keeps the old coordinate and its exact commit.** An
adoption citation, a deploy run, a peeled tag, an inventory row or an ADR
narrative is a statement about a tree at a revision. At that revision the
repository was called `dotmac_vendor_control_plane`, and editing the name into
it makes the citation name a coordinate that did not exist. Only evidence
produced after the rename uses the new name. This applies to
`dotmac_starter_mt`'s `packages/*/EXTRACTION.toml` `adoption_evidence` and
`[[product_writers]]` blocks, `dotmac_observability`'s
`docs/inventories/observer-rule-provenance.md`, and this repository's own
ADR 0008 and ADR 0013.

**5. The rename and the profile update are ordered, and the order is not
symmetric.** `.dotmac/standards-profile.json` must be updated to
`https://github.com/michaelayoade/dotmac_platform_control_plane` **after** the
GitHub rename, never before. Updating it first produces a profile that
disagrees with a still-old origin, and the required check fails on a protected
branch with `enforce_admins` enabled — which is to say the fix would be
unmergeable. After the rename the same check fails in the opposite direction
until the update lands, so the update is the first merge after the rename and
every other open pull request is rebased onto it.

## Consequences

The assembly's `spec.name` — `ASSEMBLY_NAME` in `src/vendor_cp/assembly.py` —
is today only the OpenAPI title, because the pinned kernel `0.1.0a77` uses it
for nothing else (`FastAPI(title=spec.name)`, and no other reference in that
version's `app_factory.py`). It stops being only a title at kernel `0.1.0a95`,
which added `_install_attribution`: from that version `spec.name` is normalized
into the audit **source-application code**, written into audit rows and
required in peers' accepted-application sets. So a display-only change made now
becomes a data and cross-application-contract change at the next kernel bump,
silently, unless `SOURCE_APPLICATION` is set explicitly to hold the existing
code. Whichever way `ASSEMBLY_NAME` is set, the kernel bump past a95 must pin
`SOURCE_APPLICATION` in the same change.

The GHCR package `ghcr.io/michaelayoade/dotmac_vendor_control_plane` is not
renamed by a repository rename and is not intended to be. Its repository
linkage is what lets the deploy workflow's `GITHUB_TOKEN` push to it, and that
linkage was **not verified** while drafting this record: the available token
lacks `read:packages`, and the anonymous registry probe returns `DENIED` for a
name that exists and a name that does not, so it distinguishes nothing. This is
an open verification obligation on the rename, not a resolved question.

Everything attached to the repository's numeric id survives a rename and needs
no re-creation: classic branch protection on `main` with required contexts
`check`, `image`, `postgres`, `Dotmac engineering standards`, `enforce_admins`
enabled, force-push and deletion blocked; the `production` environment with its
branch policy, required reviewers, and its secrets and variables; the
repository secret `FORGEJO_READ_TOKEN`; Actions history; issues and pull
requests. The repository carries no rulesets, no webhooks and no deploy keys.
Required-check contexts are job names and are unaffected by the repository
name.

Consumers outside the repository keep working through GitHub's redirects, but a
redirect is a compatibility measure and not a coordinate. `dotmac_erp`'s
`app/bill_of_materials.py` carries `owner="dotmac_vendor_control_plane"` as a
live code identifier rather than as prose, and is the one cross-repository
reference that is neither historical evidence nor documentation.

## Drift prevention

The repository-identity control already exists and already bites. Running the
pinned conformance engine against `dotmac_vendor_control_plane` `main` at
`94c0b736` reports `PASS`; running it with only
`repository.canonical_url` changed to the new name reports
`error repository.identity.mismatch`. The gate therefore detects the mismatch
in either direction and cannot pass while the profile and the origin disagree,
which is what makes decision 5 enforced rather than remembered.

The frozen list in decision 3 is a list of things that must NOT change, so the
control over it is inspection at review time rather than a detector: a diff
that renames one of those coordinates is a diff that contradicts this record.
Two of them are additionally covered by existing repository tests —
`tests/architecture/test_production_deployment.py` pins the image coordinate
and the three OpenBao paths, and `tests/architecture/test_platform_audit_actions.py`
requires every `vendor.*` action to be declared by exactly one manifest and to
have a real caller.

Decision 4 has no automated detector and is not claimed to have one. An
evidence row is a string in a TOML file, and nothing distinguishes a corrected
name from a rewritten one by inspection of the row alone. The control is that
the rename is executed by a change that touches no `adoption_evidence`,
`[[product_writers]]` or dated inventory row, and a reviewer can check that
property of the diff.

The verification gap named in Consequences is tracked rather than closed: the
GHCR package linkage must be confirmed with a `read:packages`-scoped token
before the first post-rename image build is relied on, and a failed push after
the rename is the fallback signal.
