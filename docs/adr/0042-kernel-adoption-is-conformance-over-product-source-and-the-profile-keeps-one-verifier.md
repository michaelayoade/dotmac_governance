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

One divergence was found and repaired. Governance's `NON_COORDINATES` alias
list was `latest|current|head|main|master`; Foundation's `_MOVING_REFERENCE` is
`latest|main|master|HEAD|stable|edge`. `stable` and `edge` were already REFUSED
by Governance's 40-hex rule, so the gap was in how precisely the message named
the mistake rather than in what the registry admitted — and a refusal that says
only "not 40 hex" leaves the author guessing whether they wrote a branch, a tag
or a typo. The two aliases are now named, `current` is kept, and the near-miss
`mainline` is proved to be refused WITHOUT being called a branch alias, because
widening a list is only safe if it did not quietly become a substring match.

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

### 3. The classifications live in a closed, versioned profile section

Michael ruled on 2026-09-05: *"Put Kernel-adoption classifications in a
versioned, closed section of `.dotmac/standards-profile.json`. Governance owns
the schema and evaluator; each product owns its instance. Do not add them to
`ApplicationFoundationProfile.v1` and do not create another document."*

That is narrower than the earlier "no adoption evidence in
`standards-profile.json`", and the distinction is the point: **classifications
are declarations, not evidence.** Receipts and runtime-adoption facts stay out
of that file.

Implemented as `schema_version` 12's `kernel_adoption` section, at
`section_version` 1. The section is versioned INDEPENDENTLY of the profile,
because a profile-wide bump forces every enrolled repository to move while a
section version lets one vocabulary evolve and say so.

Three states, and the third is the one this section exists for:

- **applicable** — prohibited surfaces, and transitional surfaces that each
  carry an owner AND an expiry. The parser requires both; the evaluator
  additionally rejects a present field holding whitespace, because a guard that
  only checks for absence passes a declaration whose owner is a space.
- **not applicable** — an explicit typed absence with a stated reason. It is
  CHECKED, not accepted: a repository declaring it consumes no Kernel and then
  importing one is named, with the file and line of the contradicting import.
  An exemption states an enforceable premise or the region is unmonitored
  rather than exempt.
- **missing or unreadable** — a REFUSAL. The section is REQUIRED rather than
  optional so that absence is refused at load; `read_declaration` turns an
  unopenable file, invalid JSON and a section that does not parse into typed
  refusals too. Neither ever becomes an empty list, because "this repository
  prohibits nothing" and "nobody has said what this repository prohibits" are
  different facts and one value must not carry both.

`standards_control.profile` remains the ONE parser for that file.
`kernel_adoption_control` reads the section by key and hands it to
`parse_kernel_adoption`; it adds no second parser, and it evaluates rather than
enforcing, so no `standards_control` rule family is created.

`KernelAdoptionInputs` still takes the declaration as a value rather than a
path, so the engine reads no filesystem and a caller cannot silently pick up a
working-tree edit.

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

### 5. The Foundation binding is a bootstrap that cannot be made to count

`kernel_adoption_control.foundation_binding` names the contract Governance
defers to, and holds nothing else: a repository, a peeled 40-character commit,
a path and a symbol. It parses nothing.

The intended end state is a RELEASED-VERSION binding. It is unavailable, and
the reason is measured rather than assumed — see § "What was measured". So the
binding is made to `ee07c42261e791fde3035e7682a8e2fb77ba4603`, the commit the
contract's bytes live at, and `released_version` is `None`.

That `None` is a STATED absence. `ContractBinding.requires_release` reports it,
so a reader sees that this binding is not yet by release without reading a
docstring. When a Foundation release carries `application_profile.py`, exactly
one literal changes: `released_version` becomes that version and `revision`
becomes the peeled commit of its tag. The coordinate KIND is what changes
later, not the shape of everything reading it.

Michael ruled on 2026-09-05 that the source coordinate is permitted *"only as a
temporary, report-only bootstrap"* and *"must never count as installed,
admitted, or adopted"*. That is enforced structurally, not documented:
`AdoptionClaim` REFUSES construction of an `installed`, `admitted` or `adopted`
claim over a revision-bound binding. There is no flag and no override, because
the failure being prevented is a later reader deciding the bootstrap was good
enough. A binding naming a released version may hold every state, which is what
keeps the refusal a property of the COORDINATE KIND rather than of the class —
a guard that refused everything would prove nothing about itself.

`0.4.0a1` is abandoned and refused BY NAME, with `0.3.0a5` and `0.3.0a6`, via
`ABANDONED_VERSIONS`. The replacement waits on a Foundation alpha that is built
once, published and verified; which alpha, cut by whom, and under which oracle
is what remains of open decision 50.

`ContractBinding` refuses a moving alias and a non-40-hex revision at
construction, so an unusable binding cannot sit in the tree waiting to be
noticed. `tools/check_receipts.py` remains the AUTHORITY for receipt
coordinates; the two alias vocabularies are asserted equal by
`test_the_alias_vocabulary_agrees_with_the_receipt_registry`, because two lists
that must match and are never compared are two lists that will not match.

### 6. What this record does not decide

- **Which Foundation alpha replaces the bootstrap, cut by whom, and under
  which oracle.** Michael has ruled that the replacement happens after the next
  alpha is built once, published and verified; none of those three has
  happened. This is what remains of open decision 50.
- **How the three products reach `schema_version` 12.** They are on 9 and must
  migrate 9 → 10 → 11 → 12; the 9 → 10 half requires an ADR 0014
  `deployment_artefact_surfaces` declaration each. That is a product-enrolment
  problem across three repositories and is deliberately not solved here.
- **Any Kernel-adoption gate.** Activation is a separate, deliberate act, as
  ADR 0039 § 12 requires of its own subject.

## Consequences

An enrolled repository's Kernel adoption is UNMONITORED rather than exempt
until it declares the section and a gate is deliberately activated. That is
stated plainly because the alternative failure — a package that exists, is
tested, and is quietly believed to be enforcing something — is the shape this
repository exists to catch.

The cost of the required section is a migration, and it is stated rather than
discovered. `dotmac_platform_control_plane`, `dotmac_erp` and `dotmac_sub` are
all on `schema_version` 9, pinned to Governance revision
`a19259b10568d29dc0a9617347498fea7f1e7a97`, and none declares
`deployment_artefact_surfaces` — read 2026-09-05 at each repository's
`origin/main`. Each must migrate 9 → 10 → 11 → 12, and the 9 → 10 half drags in
an ADR 0014 deployment-artefact declaration. There is no way to avoid it: the
loader's top-level key set is CLOSED, so a profile carrying `kernel_adoption`
under schema 9 is refused for the unknown key before its version is even
reached. Sequencing the three enrolment changes is Michael's, not this
record's.

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
