# 0042. Kernel adoption is conformance over product source, and the profile keeps one verifier

- Status: Proposed
- Date: 2026-09-05
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards, and the three assemblies enrolling in the Kernel-adoption programme
- Classification: Internal

## Context

### The ruling this record implements

Michael ruled on 2026-09-05, in three parts:

- `dotmac-deployment-foundation` owns `ApplicationFoundationProfile.v1` — its
  schema, semantics, canonicalization, digest, validation, refusals and version
  evolution.
- Governance owns conformance and adoption evidence. It requires the released
  Foundation contract and records immutable adoption/retirement receipts. It
  does not implement another parser or verifier.
- Each product owns only its profile instance and its evidence bindings.

An earlier framing had Governance define a second, smaller document for the
per-import adoption declaration. That framing is withdrawn. Two documents behind
one subject is the defect the ruling exists to prevent, and a second parser that
exists but is unused is still a second parser.

### What was measured, and where

Read on 2026-09-05.

`dotmac_starter_mt` `origin/main`:
`packages/dotmac-deployment-foundation/src/dotmac_deployment_foundation/application_profile.py`
is 1,072 lines and declares `APPLICATION_PROFILE_SCHEMA = "ApplicationFoundationProfile.v1"`
at line 139, thirteen closed `FoundationConcern` members, a closed
`BINDING_FIELDS` frozenset of exactly `{implementation, version, coordinates,
displaces, retirement}`, and the coordinate regexes `_IMMUTABLE_COORDINATE` and
`_MOVING_REFERENCE`.

Three facts follow from that reading, and each is load-bearing.

**One. The verifier is not released.** `dotmac_starter_mt` carries exactly three
`dotmac-deployment-foundation` tags — `v0.1.0a1`, `v0.2.0a1` and `v0.2.0a2`,
peeled to `c072e1f51548dca04ab182d653d032bb481f4b79`,
`ac21c9ae382ac866ec8f2ab21e5970e1ac8cc844` and
`55750e104df3dd94b6f9f70bf8c8db53986394c7`. **`application_profile.py` is absent
from all three.** It was added by commit
`22a40d14d93ce5e49a3fd14e63092bb74810716d` on 2026-09-04, after the newest tag
(2026-08-28). The package declares `version = "0.4.0a1"` on `main`, and that
line is not evidence of publication: this repository's own ADR 0013 § 3 and
`dotmac_starter_mt` AGENTS.md rule 30 both say a version present in
`pyproject.toml` or on `main` is not evidence it is published or pinnable.

So Governance cannot today "require the released Foundation contract and invoke
its verifier", because no release contains one.

**Two. The contract rests on a `Proposed` record that deliberately builds no
gate.** `ApplicationFoundationProfile.v1` is stated by this repository's own
ADR 0039, which is `Proposed`. Its § 11 says, in its own words, that it creates
"no check, no gate and no `standards-profile.schema.json` surface". Its § 12
holds it `Proposed` until a report-only implementation "can admit a real
candidate and reject planted defects", and separates authoring, holding and
activation into three acts. Open decision 44 records the consequence: "ADR 0039
may not be cited as a gate."

**Three. The concern model has no room for the adoption facts.** The closed
`BINDING_FIELDS` set carries no field for a Kernel surface classified
consumed / transitional / prohibited, none for a public-import inventory, and
none for a legacy session, engine, GUC or facade baseline. That is not an
oversight in Foundation's model; ADR 0039 § 10 refuses exactly this kind of
addition, and adding one would be a redefinition of a closed v1 rather than an
extension of it.

### What is already owned, and must not be built twice

The surviving half of "a receipt coordinate must be immutable" **already
exists** in this repository and has an owner. `tools/check_receipts.py`
implements ADR 0018 § 3 and ADR 0019: `COMMIT` refuses anything that is not a
peeled 40-character commit, `NON_COORDINATES` names a branch alias, an unpeeled
tag and an image tag so the refusal says which one was used, the registry is
append-only against the merge base, it fails closed when the merge base cannot
be established, and an empty registry reports `not_applicable` rather than a
pass. Building a second immutable-coordinate checker for Kernel adoption would
be the duplicate-verifier defect arriving in the half of the system that already
solved it.

One divergence is recorded rather than repaired here. Governance's
`NON_COORDINATES` alias list is `latest|current|head|main|master`; Foundation's
`_MOVING_REFERENCE` is `latest|main|master|HEAD|stable|edge`. `stable` and
`edge` are still REFUSED by Governance's 40-hex rule, so this is a difference in
how precisely the message names the mistake, not a difference in what is
admitted. Aligning the two lists belongs to ADR 0018's owner.

### What is genuinely unowned

Searched on 2026-09-05: none of `standards_control`'s 59 `DiagnosticCode`
members covers a Kernel import, a Kernel pin or a product-local Kernel facade.
The two that come closest do not: `TESTING_KIT_IMPORT_FORBIDDEN` is
`dotmac_kernel.testing` locality under ADR 0008, and `DEPLOYMENT_IMAGE_NOT_PINNED`
is a container image digest under ADR 0014. So Kernel-adoption conformance over
product source is new capability rather than an extension of an existing rule
family.

## Decision

### 1. The boundary

`ApplicationFoundationProfile.v1` has ONE verifier and it is Foundation's.
Governance holds no profile parser, no canonical serializer, no digest and no
profile refusal vocabulary. This is asserted structurally rather than promised:
`tests/test_kernel_adoption_control.py::BoundaryIsStructural` fails if the
package acquires a schema constant, a canonical-bytes function, any attribute
whose name contains "digest", or a finding code speaking about a profile,
schema, digest or canonicalization.

### 2. What Governance measures instead

Six properties of PRODUCT SOURCE, in `kernel_adoption_control`. Each reads
Python that a caller supplies and consults no document:

1. **Pin disagreement** — two sites naming two Kernel versions.
2. **Unknown surface** — a `dotmac_kernel.*` name the pinned Kernel does not
   publish.
3. **Private surface** — a `dotmac_kernel._*` import.
4. **Prohibited surface** — an import the product itself classifies prohibited.
5. **Product-local facade** — a module that re-exports the Kernel's own names.
6. **Unowned transitional surface** — a transitional classification with no
   owner or no expiry.

### 3. The inputs are a function signature, not a file format

`KernelAdoptionInputs` is a frozen dataclass a caller constructs. It has no
serialization, no version string and no loader, because deciding where these
facts live in a product is an ownership question that is OPEN (§ 5), and
answering it by inventing a file would be the second document this record
refuses.

Two consequences are deliberate. The Kernel's published module lists are an
INPUT (`KernelSurfaceCatalogue`), carrying the peeled commit they were read at,
so an unknown-surface finding is a fact about the product rather than about how
stale a hardcoded list in Governance has become. And the source inventory is
passed in rather than globbed, for the reason
`standards_control.ConnectorScope` already documents: a product that can name
what is measured is not measured.

### 4. Report-only, and not wired into any gate

`kernel_adoption_control` ships no CLI, no `__main__`, no composite action and
no entry in `.dotmac/standards-profile.json`. No enrolled repository's
conformance run consumes it. This is a decision, not an omission: open decision
44 states that a `standards_control` rule family enforcing an unapproved
standard would activate policy without approval, and ADR 0039 § 12 asks
precisely for a report-only implementation that can admit a real candidate and
reject planted defects. This is that implementation for the Kernel-adoption
axis.

Runtime-adoption evidence does not go into `.dotmac/standards-profile.json`.

### 5. What this record does not decide

- **Where the product states its prohibited and transitional classifications.**
  Arms 4 and 6 above are implemented and proved against supplied inputs, and
  have no production source of those inputs. Foundation's closed
  `BINDING_FIELDS` cannot carry them; a new Governance document is refused by
  the ruling; and a `standards-profile.schema.json` surface changes the schema
  for every enrolled repository, which is open decisions 26, 29 and 44. This is
  open decision 49 and it is Michael's.
- **Whether Governance depends on a released `dotmac-deployment-foundation`
  at all, and what oracle attests that release.** Until one exists the
  "require the released contract" half of the ruling is unexecutable, and this
  record does not pretend otherwise. This is open decision 50.
- **Whether Governance's and Foundation's moving-reference alias lists are
  aligned.** Recorded above; it belongs to ADR 0018's owner.
- **Any Kernel-adoption gate.** Activation is a separate, deliberate act, as
  ADR 0039 § 12 requires of its own subject.

## Consequences

An enrolled repository's Kernel adoption is UNMONITORED rather than exempt
until open decision 49 is made and a gate is deliberately activated. That is
stated plainly because the alternative failure — a package that exists, is
tested, and is quietly believed to be enforcing something — is the shape this
repository exists to catch.

The three product enrolment changes that follow this one cannot complete arms 4
and 6 without decision 49. Arms 1, 2, 3 and 5 need nothing further: their inputs
are a product's own packaging files, its source inventory, and the Kernel's own
published module lists.

Governance takes on no dependency on `dotmac-deployment-foundation` in this
change. Adding one before a release exists would pin a moving reference, which
ADR 0013 § 3 refuses.

## Drift prevention

- The boundary is a test, not a paragraph — see § 1.
- Every arm is proved by a PLANTED defect and a paired near-miss that must stay
  silent. No arm's health may be inferred from a green run, because the fleet is
  currently clean on all six: measured on 2026-09-05, no pin disagreement and no
  product-local Kernel facade exists in `dotmac_platform_control_plane`,
  `dotmac_erp` or `dotmac_sub`.
- The near-misses are drawn from real files a cruder detector would condemn:
  `dotmac_sub`'s `app/services/settings_kernel_bridge.py` (four Kernel imports,
  no `__all__`, an adapter), `dotmac_erp`'s import-boundary guard (which keeps
  the forbidden import as a string fixture), and `dotmac_kernel.display` (which
  is internal without being private).
- Two vacuity hazards report themselves: a run over no source is a
  `kernel.inventory.empty` error, and a pin arm given fewer than two sites emits
  a notice saying it established nothing rather than passing silently.
- Unparseable source is a `kernel.source.unreadable` error. An unmeasured file
  is never reported as a clean one.
