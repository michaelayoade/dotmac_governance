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

### 3. The declaration is its own document, and the profile carries a pointer

Michael ruled on 2026-09-05 — the third and settled position — that the
classifications live in a dedicated product-owned file,
`.dotmac/kernel-adoption.json`, under the Governance-owned
`KernelAdoptionDeclaration.v1` contract. Ownership is split four ways: the
PRODUCT owns the instance, GOVERNANCE owns the schema, refusal rules,
validation and the conformance action, KERNEL owns a provider-neutral
surface/provenance catalogue, and `standards-profile.json` carries **only a
typed binding to the declaration path and contract version — not the
declaration's contents.** The Foundation profile is unchanged.

Two earlier positions were tried and are recorded because the reasons matter: a
Governance-owned second document was refused as a duplicate contract, and a
content-bearing section of `standards-profile.json` was refused because it puts
classifications where a policy value arrives as a plausible line in a
conformance-profile diff, and because it forced a `schema_version` bump on
every enrolled repository.

**The binding is DECLARED-OPTIONAL, and that is what kept the enrolment cost
flat.** `_keys` now takes an enumerated `optional` set; closedness is unchanged
because every admissible key is still listed and reviewed, and a key outside
`required | optional` is refused exactly as before — asserted by
`test_the_closed_key_discipline_is_unchanged`, which plants an arbitrary key
and requires the refusal. A required key would have forced a bump, and the
three products are still at v9.

Optionality is safe ONLY because the refusal that matters moved with the
contents. `read_declaration` reads the bound path, or
`.dotmac/kernel-adoption.json` when no binding is stated, and returns one of
three outcomes:

- **applicable** — required surfaces with their proven floors, prohibited
  surfaces each carrying the governing citation, and transitional surfaces
  carrying owner, expiry, retirement issue, replacement and an exact
  path/symbol baseline.
- **not applicable** — an explicit typed absence with a reason, CHECKED
  against the repository's own imports rather than accepted.
- **missing or unreadable** — a REFUSAL. An absent file, an unopenable one,
  invalid JSON and a document that does not parse are all errors. None becomes
  an empty list, because "this product prohibits nothing" and "nobody has said
  what this product prohibits" are different facts.

The baseline is a RATCHET rather than a note, and it is two-directional: a use
outside the baseline is growth in a surface being retired, and a baseline entry
with no measured use is a list that has stopped describing anything. A
declaration field nothing compares would be the "declared and never read"
defect this repository exists to catch.

One format, one parser, one evaluator. Nothing is parameterised by product —
no product name, no branch, no hook — which is Michael's stated acceptance
test: *"one build-once validator and one declaration format across every
product, not a per-product adapter."*

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
- **When the three products clear their pre-existing 9 → 10 → 11 profile
  debt.** It is unchanged by this record and is not a prerequisite for
  declaring Kernel adoption.
- **Any Kernel-adoption gate.** Activation is a separate, deliberate act, as
  ADR 0039 § 12 requires of its own subject.

## Amendment, 2026-09-05: the runner exists and the gate is activated

### A1. What § 4 above now gets wrong, stated before anything else

§ 4 says this package "ships no CLI, no `__main__`, no composite action". That
was true when it was written and is **false as of this amendment**: the package
ships `kernel_adoption_control.runner` and `python3 -m kernel_adoption_control`,
and this repository's CI runs it. § 4's *reasoning* stands — it explains why
activation had to be a separate deliberate act — but its factual sentence does
not, and a record that keeps a stale fact is how a reader comes to believe a
gate is inert.

The defect this closes was found during Platform's enrolment: the package had
an engine, a declaration contract and a reader, and **nothing that called
them**. A product could write `.dotmac/kernel-adoption.json` and nothing would
evaluate it — the "declared and never read" failure standing inside the package
built to catch it.

### A2. The authority for activating

Michael Ayoade authorised activation on 2026-09-05, ruling that the missing
runner was an explicit report-only decision rather than an accidental omission,
and that it be resolved **in Governance** rather than by a Platform-owned
verifier. That is the authority; it is not inferred from ADR 0042 having been
written, and this record remains `Proposed` — a `Proposed` record may carry a
working repository-local validator, which is ADR 0019's and ADR 0020's
precedent and is recorded as decision 51(c).

### A3. Where a run happens, and why not here

`read_declaration` reads a file in a product's checkout. ADR 0013 § 1 permits a
repository to derive claims from repository-local facts and requires an oracle
for anything else, and a file in `dotmac_erp` is not a fact `dotmac_governance`
contains. **So Governance does not run this over another repository and does
not publish a verdict about one.** The run happens in the **measured
repository's own CI, over its own checkout**, where every input — the
declaration, the source inventory, the pins, the Git HEAD — is repository-local
and no oracle is required. Governance owns the runner; the product owns the run
and the claim.

This repository additionally runs it **over itself**, on exactly the footing
ADR 0044 § 4 established for `tools/check_local_action_workspace.py`.
`dotmac_governance` carries `.dotmac/kernel-adoption.json` declaring
`not_applicable`, so it is a subject of the standard and not only its author,
and the `not_applicable` premise is now checked here rather than asserted.

### A4. What activation is, and what it deliberately is not

Activated: one module entry point, `python3 -m kernel_adoption_control`, exit
`0` on a conforming run, `1` on findings and `2` on a refusal to run; and one
step in `.github/workflows/governance-checks.yml`, held in agreement with
`AGENTS.md`, `.dotmac/validation-contract.json` and `.dotmac/agent-profile.json`
by `tools/check_validation_contract.py`.

**Not** activated, deliberately and by the same reasoning ADR 0044 § 4 used: no
`standards_control` rule family, no `standards-profile.schema.json` surface, no
`schema_version` bump, and nothing changed for any other enrolled repository.
This matters for **open decision 44, which this amendment does NOT close.** That
decision's blocking sentence is that "a `standards_control` rule family
enforcing an unapproved standard would activate policy without approval" — and
this activation creates no such family, so the obstacle is not engaged rather
than resolved. Decision 44's three actual parts are all about
`ApplicationFoundationProfile.v1`: profile completeness and its schema surface
(a), installed-artifact resolution and post-deployment read-back in other
repositories (b), and the retirement disposition field in `dotmac_starter_mt`'s
`EXTRACTION.toml` (c). None of them is a Kernel-adoption question and none is
resolved by anything here. Closing decision 44 on the strength of this change
would assert three resolutions that do not exist.

### A5. The product-side surface is one callable, and it cannot classify

A product supplies exactly one thing: a callable
`(Path) -> ProductObservation`, named to the runner as
`package.module:callable`. `ProductObservation` carries `sources`, `catalogue`
and `pin_sites` — and **no declaration field**, which is the load-bearing
absence. A product that could return a `DeclarationOutcome` could return
`DeclarationPresent` with empty tuples, and the refusals below would become
advice a product may decline. The runner reads the declaration itself, through
Governance's reader, at the path the profile's optional
`kernel_adoption_binding` names or the default when it names none.

Nothing is parameterised by product. The observer REFERENCE is data the caller
supplies, which is the opposite of a per-product code path: there is no product
name, no branch and no adapter anywhere in the package. Michael's acceptance
test holds — *"one build-once validator and one declaration format across every
product, not a per-product adapter."*

`catalogue` may be an explicit `None`, and that is a stated absence rather than
a default: a repository consuming no Kernel holds no evidence of the Kernel's
published module lists, and inventing a version and a revision to fill the
field would put a coordinate nobody read into a bound report. The absence
cannot buy silence — every Kernel import measured without a catalogue is
reported `kernel.catalogue.absent`.

### A6. What "now" is, for expiry

A `TransitionalSurface` carried an `expiry` that was syntax-checked and
**compared to nothing**. It is now compared, and two choices are recorded
because each could otherwise be changed by someone who thought it made no
difference.

**"Now" is an injected run date, not a clock.** `KernelAdoptionInputs.as_of` is
required and has no default; `--as-of` is required and has no default; and
`date.today()`, `datetime.now()` and `datetime.utcnow()` appear nowhere in the
package, which is asserted by a test rather than promised. A clock read inside
the check would make a verdict depend on when the job started and would be
untestable without freezing time. CI supplies the UTC date of the run —
`--as-of "$(date -u +%F)"` — and the run report records it, so re-running with
the same date gives the same answer forever.

**Expiry is judged against the run date, not against something in the
evidence** — because there is nothing in the evidence to judge it against.
`KernelAdoptionDeclaration.v1` carries `product_revision`, a commit id, and no
date at all. Reading that commit's timestamp would mean querying the product's
Git history, which is an oracle over a repository rather than a fact in the
document. **This is the v1 gap this amendment reports and does not edit:** a
declaration cannot be checked against its own age, so a five-year-old
declaration whose expiries are all in the future is indistinguishable from one
written yesterday. A `declared_at` field would close it and would be a v2
question. A v1 is never redefined.

**The boundary is `expired iff expiry < as_of`.** `expiry` is the LAST DAY the
surface may exist, so a surface expiring on the run date is not yet expired and
one expiring the day before is. Both neighbours are planted and asserted, and
so is the same declaration flipping verdict when only `as_of` moves.

One defect was found and repaired in passing. The contract's `_DATE` regex
admits `2026-13-45`, which has the shape of an ISO date and is not one, so it
could be written, stored and ordered against nothing — an expiry that can never
pass. The parser now requires the string to be a real calendar date. **This is
a tightening within the same stated format, not a redefinition:** no ISO
YYYY-MM-DD date is newly refused, only strings that were never one. The engine
refuses an unorderable expiry a second time, for a dataclass built without
going through the parser.

### A7. Five refusals, and the line between the two that collapse

| Refusal | Code | What it means |
| --- | --- | --- |
| missing | `kernel.declaration.missing` | No file at the path. |
| empty | `kernel.declaration.empty` | The file exists and holds no document — zero bytes, or only whitespace. |
| incomplete | `kernel.declaration.incomplete` | A JSON object that never states a required key. |
| corrupt | `kernel.declaration.unreadable` | Anything else that cannot be understood: unreadable bytes, invalid JSON, a non-object, an unknown key, a value stated wrongly. |
| expired | `kernel.transitional.expired` | A transitional surface's stated expiry has passed. |

The middle two are the pair most likely to collapse into each other or into
"missing", so the line is stated once and held by the parser rather than by a
convention. **An obligation NEVER STATED is incomplete; an obligation STATED
WRONGLY is corrupt.** They are distinguishable in principle — absence of a key
is not the same fact as wrongness of a value — and the tie-break when a
document exhibits both is that absence is checked first, so it reports
incomplete. That ordering is asserted, because two codes that are
distinguishable in principle and undefined in practice are one code with two
names.

**Empty is not missing** — the path exists, so "write the declaration at this
path" sends the author to create something that is already there. **Empty is
not corrupt** — there are no bytes to fix. **`{}` is not empty** — it is a
document that states nothing, which is incomplete; that near-miss is planted
and required to report incomplete.

The four declaration refusals are the enforcement of the sentence this package
exists for: an absent declaration must not read as "nothing is prohibited", and
an unreadable one must not read as an empty list. `evaluate` raises rather than
falling through if a sixth outcome is ever added without a code, so a new
refusal cannot arrive as silence.

### A8. Binding, and how an unenforced enrolment stays visible

A run report is `KernelAdoptionRun.v1` and names the exact Governance revision
that produced it and the exact product revision it measured. Both are **derived
from Git, not supplied**: the Governance root comes from the package's own file
location, so a product cannot state a Governance revision it did not run.

`kernel_adoption_control.is_enforced` is the predicate anything citing an
enrolment must use. It requires the run contract, two peeled 40-character
commits, two clean worktrees, a non-empty source inventory and a conforming
run, and it returns the reason when it refuses.

**The sequencing this makes legible:** a product pinning a Governance revision
from before this amendment produces **no report at all**, and no report is not
a pass — `is_enforced({})` is `False` with the reason naming the missing
contract. A report that exists and fails a binding condition says which one.
Platform's enrolment is therefore not describable as "CI-enforced" until it
pins a Governance revision containing this runner and can exhibit a report the
predicate accepts.

### A9. What the runner executes, and the boundary on that

Resolving an observer imports and calls product code. That is the product's own
code in the product's own job, which is part of why the run belongs there — but
it is also why the workspace must hold the product's trusted commit and never a
caller-supplied ref. That property is ADR 0044's subject and this module does
not check it; naming the boundary is the point, because ADR 0044's own lesson
is that a true-sounding premise with an unstated qualifier is what survives
review.

### A10. Drift prevention added by this amendment

- Every arm above is proved by a planted defect and a paired near-miss required
  to stay silent. The production subject — this repository — is clean on every
  arm, so no arm's health may be inferred from the green step.
- The boundary sweep's module list is compared against the package directory,
  so a module added later fails the test until the sweep names it. That
  comparison immediately found `declaration_contract` outside the sweep; it is
  now a NAMED exemption from the digest arm with an enforced premise (its only
  digest-named attribute is enumerated, and the rest of the boundary still
  applies to it) rather than an omission.
- `kernel_adoption_control.__init__`'s `__all__` named
  `TransitionalSurfaceDeclaration`, which the package does not export, so
  `from kernel_adoption_control import *` raised. That is ADR 0041's defect —
  a name with no referent — and it is removed.

## Consequences

An enrolled repository's Kernel adoption is UNMONITORED rather than exempt
until it writes the declaration and a gate is deliberately activated. That is
stated plainly because the alternative failure — a package that exists, is
tested, and is quietly believed to be enforcing something — is the shape this
repository exists to catch.

**This change adds no migration stop, and that is the answer to the sequencing
question.** Read 2026-09-05 at each `origin/main`:
`dotmac_platform_control_plane`, `dotmac_erp` and `dotmac_sub` are all on
`schema_version` 9, pinned to Governance revision
`a19259b10568d29dc0a9617347498fea7f1e7a97`, and none declares
`deployment_artefact_surfaces`. That 9 → 10 → 11 debt is pre-existing and this
record does not touch it.

What matters for enrolment is that **a product can add its declaration today,
at schema 9, without touching its conformance profile at all** — the file has a
default path and the reader finds it there. Only the optional binding needs a
loadable profile, and stating a non-default path is the sole thing it buys.
Had the binding been required, the Kernel-adoption axis would have become a
fourth stop and would have blocked the stated merge order.

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
