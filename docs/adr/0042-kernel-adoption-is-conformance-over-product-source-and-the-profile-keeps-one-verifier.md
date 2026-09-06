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
`0` on a conforming and citable run, `1` on findings, `2` on a refusal to
run and `3` on a conforming run that is not citable; and one
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

### A8. Binding, provenance, and what activation actually covers

**This section was narrowed on 2026-09-06 after independent review, and the
narrowing is the substance of the second pass.** As first written it claimed
that any conforming run was citable as enforcement. Three findings invalidated
that claim, and each is repaired rather than argued with.

**Finding one: three declared fields are never read.** An `applicable`
declaration carries `product_revision`, `kernel_catalogue` and
`required_surfaces`, and this runner evaluates none of them —
declared-and-never-read inside the package built to catch
declared-and-never-read. Governance's own declaration names `f8f90aef…`, which
is not this branch's HEAD, and the run was clean.

The reviewer's proposed repair — compare `product_revision` against HEAD — is
**unimplementable as stated**, and Michael said why: *"a committed file cannot
contain its own commit."* Reaching for it would produce something worse than
the gap, because the only way to make the comparison pass is to weaken it into
something that no longer means what its name says. So the three fields are
handled two ways instead. They are **published** as a NOTICE
(`kernel.declaration.fields-unevaluated`) on every applicable run, naming each
one and citing decision 52, so no reader can infer from a clean run that they
were checked. And their real repair is a **versioned successor contract** —
a non-self-referential source coordinate, a catalogue digest comparison, and
required-surface/floor semantics — which is open decision 52 and is **not** an
edit to `KernelAdoptionDeclaration.v1`. A v1 is never redefined.

**Consequently, an `applicable` report is explicitly NON-CITABLE.**
`is_enforced` refuses it by name. This is the structural move that makes
everything else honest: a run that reads part of a declaration cannot be cited
as enforcing the declaration. Governance's own `not_applicable` self-run
remains citable, and **not because it has no unread field — it has one.**
`product_revision` is required of every declaration and compared with nothing,
so it is now disclosed on both paths rather than only the applicable one; an
unread field left silent in the one citable shape would be this package's own
defect in the one place it would have gone unseen. It is citable because what a
`not_applicable` declaration CLAIMS is a premise — "this repository consumes no
Kernel" — and that premise IS evaluated, against the repository's own imports,
and refused when false. An `applicable` declaration claims three further things
nothing reads. That is why this change is a **self-enforcement foundation** and
not a product gate. **Applicable-product
activation is the next change and is gated on the successor contract; Platform's
enrolment stays blocked until that change lands.** Nothing in this record may be
read as making enrolment available today.

**Finding two: CI stayed green when `is_enforced` was false.** `main` printed
the predicate and gated only on `conforms`, so a step could go green while its
own log announced that its result was not citable — and the badge is what gets
quoted. The exit code now consults it. Four codes: `0` conforming and citable,
`1` findings, `2` the run could not be made, `3` conforming and not citable.
An applicable declaration lands on `3` today, by decision rather than defect.

**Finding three: a vendored runner could claim to be Governance.**
`GOVERNANCE_ROOT` was the package's own parent directory, so a product that
copied the package got its own root, its own peeled HEAD and `is_enforced ==
True` naming a revision that is not a Governance commit — including from a
MODIFIED copy, which is the case that matters, because a modified copy can be
made to conform.

Provenance is now established and typed, with two values and no third:

- **self** — the measured root IS the Governance root, and that checkout's
  `origin` is `https://github.com/michaelayoade/dotmac_governance`. The remote
  is checked on this path too, precisely because a vendored copy also makes the
  two roots coincide.
- **pinned** — the measured repository's own profile states a `governance_model`
  pinning that canonical URL and an exact revision, and the Governance checkout
  is at that revision. **A run against a Governance revision the product did not
  pin is refused**, so a product pinning an older Governance cannot be reported
  as enforced by a newer one it never adopted. That is the sequencing claim made
  checkable rather than asserted.

There is no "unverified" provenance value: a run whose provenance cannot be
established is a refusal, because a caveat in a field is what a later reader
stops noticing. The pin is read through `standards_control`'s own field parser,
newly exposed as `parse_governance_model`, rather than reimplemented — the whole
profile parser could not be used, because it requires `schema_version` 11 and
the three products are still at 9.

**Provenance is OBSERVED, and that took a third pass.** Re-review found that
`to_dict` emitted the module constant `CANONICAL_GOVERNANCE` under
`canonical_url`. Every copy of this runner therefore reported the canonical URL
whatever its checkout actually said, so the predicate's vendoring arm **could
not fail on any report the runner produced** — it was satisfiable only by a
hand-built document. The run-side check was real; the predicate-side one was
decoration. The report now carries what was measured: `origin_configured` (the
literal configured value) and `origin` (its normalised form), and `is_enforced`
compares the latter.

**The read is `git config --local --get remote.origin.url`, not `git remote
get-url`,** and the difference is a bypass rather than a detail. `get-url`
expands `url.<base>.insteadOf`, so **one rewrite rule in the runner's global
git config makes any remote report as the canonical one, leaving nothing at all
in the tree** — cheaper than modifying the checkout, which is what the previous
wording assumed an attacker would have to do. Measured 2026-09-06: with such a
rule present, `get-url` returned the canonical URL for a remote configured to
`dotmac_erp` while `config --local --get` returned `dotmac_erp`. The plant is a
permanent control and asserts both halves — the bypass working against the
rejected instrument, and failing against the chosen one.

Three spellings are accepted and normalised — `https://host/path`,
`ssh://[user@]host/path` and `user@host:path`, each with an optional `.git` and
trailing slash — and everything else is REFUSED rather than guessed at. Host is
lower-cased; the owner/repo path is not, so the comparison is case-sensitive on
it. That is deliberate and fail-closed: whether `Owner/Repo` and `owner/repo`
are the same repository is a per-forge question, and a case-folding rule that
is right for GitHub and wrong elsewhere is worse than a refusal whose repair is
writing the canonical spelling.

**What this is, stated so nothing downstream reads more into it: it is
configured-origin EVIDENCE, not cryptographic proof of remote ancestry.** A
remote URL is a local configuration value saying which repository a checkout
was set up to talk to. Nothing here observes ancestry, a signature, or the
remote itself. What it stops is a product that COPIES this package into its own
tree and thereby inherits the ability to assert it is Governance — a mistake
somebody makes by accident. It does not stop anyone who controls the checkout
and writes the value they want, and no wording in this record may imply
otherwise.

**`is_enforced` checks the report against ITSELF, not only its shape.**
`{"conforms": true, "findings": [ten errors]}` was citable, because `conforms`
was taken on trust — a summary verdict nothing recomputes, which is the same
defect as a declared field nothing reads, one level up. The predicate now
requires a well-formed findings list, refuses an unrecognised or malformed
severity rather than letting it read as harmless, refuses any error finding
whatever `conforms` says, and refuses a `conforms` that disagrees with the
findings in either direction. `source_count: true` no longer reads as one file
(`isinstance(True, int)`). The admit control is a notice-only report, which is
this repository's own citable shape — it discloses its unread `product_revision`
as a notice — so the arm is demonstrably not one that rejects everything.

**How an unenforced enrolment stays visible.** A report is
`KernelAdoptionRun.v1` and carries the observed origin, the provenance, the
Governance revision and the product revision — the revisions derived from Git,
never supplied. `is_enforced` returns `(bool, reason)` and requires all of that
plus two clean worktrees, a non-empty inventory, a present `not_applicable`
declaration, a self-consistent findings list and no error finding. A product
pinning a Governance revision from before this amendment produces **no report at
all**, and no report is not a pass.

**The gate is not in the pre-commit block, and that is a correction.** It
refuses a run it cannot bind to a committed revision, and a pre-commit tree is
by definition uncommitted — so documenting it as a pre-commit step made it fail
every time it was run as documented, which trains a reader to ignore the one
exit code whose point is that it means something. It is `ci-owned` in
`.dotmac/validation-contract.json`, runs in CI, and may be run by hand after
committing as a DIAGNOSTIC. A dirty-tree run exits 3 and is explicitly
non-citable.

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

Added in the second pass, after review:

- **The pin arm's sufficiency question is applicability-aware and can now
  fail.** It emitted a NOTICE below two sites and the report stayed conforming
  and citable — a check that structurally could not fail, counted as one that
  passed, which is this repository's own subject arriving in its own package.
  An `applicable` declaration now requires two INDEPENDENT observations —
  independence being a distinct `(path, line)`, because two entries at one line
  are one observation written twice — and fewer is an ERROR. A
  `not_applicable` declaration requires zero pin sites and zero Kernel imports;
  a pin under `not_applicable` is reported as the same premise-false code as an
  import, because it is the same fault. A declaration that could not be read
  gets neither requirement, and the refusal now names the pin arm among the
  unmonitored ones rather than letting its silence read as a pass.
- **The measured checkout is on `sys.path` only while the observer loads.**
  `main` inserted it at position 0 and left it there, making the measured tree
  the primary import root for the rest of the process — broader than the "an
  observer is called" exposure § A9 names, because any later import in the same
  process would resolve there first. It is scoped and restored, including on a
  refusal. What that does NOT undo is that the observer module stays in
  `sys.modules` and its import already ran the product's code; restoring a path
  cannot unrun that, and § A9's boundary still stands.
- **The clock sweep is parsed rather than grepped.** The substring version
  failed on `contracts.py`'s own docstring — the sentence explaining that no
  clock is read contains the token the guard looked for, so the guard fired on
  the prose documenting the guard. Parsing also closed four routes the
  substring rule missed: an aliased import, `time.time()`, a stat `st_mtime`,
  and a Git `--format=%cI`. All four are permanent plants and the prose is a
  permanent near-miss.
- **`.gitignore` covers the tool caches.** `ruff` and `mypy` run before this
  step and write `.ruff_cache/` and `.mypy_cache/` into the root, and
  `_worktree_clean` counts untracked entries — so both `worktree_clean` fields
  would have read `False` and the step would have gone green while printing
  that its own result was uncitable. Found by review, settled by observation:
  CI now prints `True`.

## Amendment, 2026-09-06: the successor contract, and applicable activation

§ A8 said an `applicable` report is explicitly NON-CITABLE, and open decision
52 owned the repair. This is that repair. It is a **versioned successor**:
`KernelAdoptionDeclaration.v1` is frozen, both contracts are parsed, a v1
document is admitted with exactly the refusals it always had, and this
repository's own `not_applicable` v1 declaration is untouched and stays citable
on § A8's reasoning.

### B1. The non-self-referential source coordinate — decision 52 (A)

`product_revision` was required of every declaration and compared with nothing,
and it cannot be compared: *"a committed file cannot contain its own commit."*
v2 replaces it with **two** coordinates, because one cannot do both jobs.

**`source_predecessor`** is a peeled commit the runner verifies is a STRICT
ancestor of the revision measured, by `git merge-base --is-ancestor` inside the
measured repository's own job — a repository-local fact, so ADR 0013 § 1 needs
no oracle. Equality is refuted explicitly: `--is-ancestor` calls a commit its
own ancestor, so a declaration naming the revision that contains it would
otherwise pass while claiming something impossible. An exit code that is
neither 0 nor 1 — a shallow clone, the `actions/checkout` default — is
**undecided**, not a refutation: it reports `kernel.source.predecessor-unverifiable`
and names `fetch-depth: 0`. *Proves:* the coordinate exists in this
repository's history and is behind what was measured. *Does not prove:* that
the declaration was written at that commit, that the commit is related to the
declaration, or anything about the source. A product may name its first commit
and satisfy it forever.

**`source_surface`** is a digest the engine RE-DERIVES from the measured
source: the canonical sorted rendering of every `(path, module, symbols, star)`
Kernel fact, merged per file-and-module, with line numbers excluded. *Proves:*
the declaration was written against exactly this Kernel surface; any import
added, removed, renamed or moved refuses. It cannot be satisfied by editing the
declaration alone, which converts silent staleness into a reviewable diff.
*Does not prove:* a revision, a date, inventory completeness (it digests what
was MEASURED — an observer that never grew to cover a directory stays
invisible), any non-Kernel change (deliberately: a coordinate that refuses on
every commit is a coordinate that gets deleted), or authorship.

The empty surface digest is a CONSTANT every Kernel-free product would share.
That is a vacuity hazard rather than a feature, and the canary is its own
verdict: an `applicable` declaration over zero Kernel imports is
`kernel.surface.none-observed`.

### B2. The catalogue is bound four ways — decision 52 (B)

`kernel_catalogue` was never compared with the catalogue the observer supplies,
so a product could declare one Kernel and be measured against a self-authored
catalogue for another. v2 compares version, peeled revision, distribution
artifact digest, and **`catalogue_digest`** — a digest over the module LISTS
themselves. The fourth is what makes the first three mean anything: without it
a product may state the right version and hand the run another Kernel's lists,
and every surface verdict is taken against a catalogue nobody bound. The
planted defect is exactly that shape, and it is the only one the first three
comparisons miss. The artifact digest is compared with what the observer read
out of the product's own lock — a repository-local fact and **not** a registry
attestation; that needs decision 17's oracle.

### B3. `required_surfaces` is executable — decision 52 (C)

Five questions, the fifth in the opposite direction because a one-directional
inventory is a sample: the module must be PUBLISHED by the bound Kernel; it
must be IMPORTED; the `floor` must be satisfied by the bound Kernel version
(ordered by a narrow PEP 440 subset that REFUSES an epoch, a post-release, a
dev release or a local version rather than mis-ordering it); `proven_by` must
name a path the run READ; and every imported Kernel module must be classified
as something. The `proven_by` arm's second half — that the proof MENTIONS its
subject — is the weakest thing in this change and is labelled so rather than
dressed up: it establishes the proof is about the right subject and not that it
proves anything, and no check at this layer can read a test's meaning.

### B4. Pin-path independence — decision 52 (E)

Independence was a distinct `(path, line)` over CALLER-SUPPLIED data, and
`PurePosixPath` does not resolve `..`, so `pyproject.toml` and
`x/../pyproject.toml` were two independent observations of one line. It caught
accidental duplication and not a product that wanted to pass. Normalization is
lexical (never `resolve()`, which would touch the filesystem) and CASE-FOLDED,
which is the fail-closed direction: collapsing counts FEWER observations, so
the arm refuses where it might have passed. It cannot see through a symlink,
and that is stated rather than left to be discovered. Two lines in one file
stay independent — Sub states the pin four times in `pyproject.toml` alone — and
that near-miss is asserted.

### B5. A document cannot establish that a run produced it — decision 52 (5)

`is_enforced` was a predicate over a REPORT, not over a repository: anyone who
could write the JSON could write a passing one, and **its own admit control was
a hand-built dictionary that returned `True`**. A predicate whose positive case
had only ever been exhibited by a fabricated input was not measuring what its
name said.

Three repairs were weighed. Re-derivation from inputs is unavailable — the
inputs are a product checkout at a revision the reading process may not hold. A
coordinate only a real run could compute is a signature, which is decision 17's
oracle and must not be invented here. So the third is taken: **the predicate
refuses to answer outside a context it can verify**, and it is implemented
structurally rather than by a caveat.

`inspect_report_document(mapping) -> DocumentVerdict` has **no citable member
in its value set**, so no amount of document-writing produces the claim.
`citability(RunReport) -> Citability` requires identity membership of the set
`run()` populates — `RunReport` is `eq=False` precisely so a hand-built report
equal in every field is not a member.

*What this proves:* within one process, that a report came out of `run()`
rather than out of a constructor. *What it does not prove, and cannot:*
anything about a report in a file, in another process, or in another job.
**A run report on disk is not self-authenticating and this change does not make
it one.** The citable claim lives in the EXIT CODE of the job that performed the
run, not in the artifact it left behind. Crossing that boundary needs decision
17's oracle. This is the smallest honest thing, not a closure.

### B6. Activation, and where its boundary is

A v2 `applicable` run is citable, and there is no
`kernel.declaration.fields-unevaluated` notice on that path — every field v2
requires has a named reader, asserted structurally by a field→reader map that
fails when the dataclass grows a field nobody reads. A **v1** `applicable` run
is still non-citable, still exits 3, and still publishes the notice.

The first acceptance subject is `dotmac_platform_control_plane` at `origin/main`
`f8865b1a43a6d6769d5fa3a3ab3eddfdf296cffb`, read READ-ONLY. Its real measured
Kernel surface — 17 modules, 85 symbols, eleven `dotmac_kernel.db` sites across
fourteen `(path, symbol)` pairs including
`src/vendor_cp/rotation_runtime_oracle.pyprogram`, which is not a `.py` file —
is in `tests/fixtures/platform-kernel-surface.json`, and the contract admits a
declaration of that shape with no findings. **What that establishes is that the
contract ADMITS a real product**, which a suite of refusals cannot establish
about itself.

**What it does not establish, and must not be read as:** Platform has no
`.dotmac/kernel-adoption.json`, Governance does not write in product
repositories, and none was created. No runner ran against Platform and no
report exists. **Platform enrolment still requires Platform to write its
declaration and add the step**, and until it does, Platform is an unmonitored
region for this property. Under ADR 0013 § 1 the run happens in Platform's own
CI or it does not happen.

### B7. Drift prevention added by this amendment

- Every new arm has a planted violation, a paired near-miss required to stay
  silent, and an admit control. The two vacuity hazards report themselves: the
  constant empty-surface digest, and an empty catalogue.
- The boundary sweep's "no attribute containing `digest`" proxy was REPLACED
  rather than exempted. The package now legitimately owns two digests of its
  own, and a blanket exemption for three more modules would have turned
  "reviewed and correct" into "unmonitored". Every digest-named attribute is
  enumerated per module with what it is, two-directionally, and the module list
  is derived from disk rather than hand-written.
- A field→reader map over `KernelAdoptionDeclarationV2` fails when the
  dataclass grows a field no engine arm names. That is the guard against v2
  becoming v1.

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
default path and the reader finds it there. **That is a fact about the FILE and
not an invitation:** a product that adds one today gets an `applicable` run,
which § A8 makes non-citable, exit `3`, and a red step. Enrolment becomes
available when applicable-product activation lands under the successor
contract, and not before. Only the optional binding needs a
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
  `kernel.inventory.empty` error, and a pin arm that cannot detect a
  disagreement refuses. **Superseded by § A10:** this originally said the pin
  arm "emits a notice", and a report carrying only that notice was citable —
  which made "the pin agrees" indistinguishable from "the pin was never
  compared". Under an `applicable` declaration, fewer than two INDEPENDENT
  observations is now `kernel.pin.undetectable`, an ERROR.
- Unparseable source is a `kernel.source.unreadable` error. An unmeasured file
  is never reported as a clean one.
