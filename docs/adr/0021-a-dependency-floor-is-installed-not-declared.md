# 0021. A dependency floor is installed, not declared

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository that publishes a distribution another repository installs
- Classification: Internal

## Context

`dotmac-deployment-control` 0.1.0a5 was published on 2026-08-30 and
independently verified on seven properties. The bytes were sound. The wheel and
sdist digests matched the release evidence exactly. A clean install into an
empty environment succeeded. Every public import resolved.

It cannot run in its consuming assembly.

`service.py:73` imports `dotmac_kernel.transactions`, a module first shipped in
`dotmac-kernel` 0.1.0a98. The distribution declares `dotmac-kernel >=0.1.0a77`.
The floor is under-constrained by **21 alphas**, and it passed every gate the
release had:

- resolution succeeded, because a77 is a true lower bound and `>=` selects the
  NEWEST release rather than the declared minimum;
- the lockfile wrote cleanly;
- the resolved artefacts matched the published bytes byte-for-byte.

The failure surfaced in a different repository, at container boot, as a
`ModuleNotFoundError`.

**A hash comparison proves you got the bytes that were published. It cannot
prove those bytes will import.** The two questions are unrelated, and a release
verdict assembled entirely from the first kind of evidence reads as complete
while answering nothing about the second.

The near miss is the instructive part. Control already runs behavioural
canaries against the INSTALLED wheel — the right shape, and the reason its
other six properties are worth believing. They run against whatever kernel the
environment resolves, which is the current one. A canary that installs "some
compatible version" proves the wheel works in *an* environment. It says nothing
about whether the DECLARED FLOOR is honest, and the declared floor is the only
thing a consumer can actually pin against.

There is a second measurement from the same distribution. `0.1.0a4` was
published reporting `__version__ = "0.1.0a2"`, and five identity proofs passed,
because every one of them ran against the SOURCE TREE — where two version
literals disagreed in two files that nothing compared. A checkout on
`sys.path` satisfies imports that the installed artefact would not, and it
answers questions about the working copy while appearing to answer them about
the release.

**The instance was closed the same day, and that changes what this record is
for.** `dotmac-deployment-control` `0.1.0a6` declares `dotmac-kernel >=0.1.0a98`
and proves the floor falsifiable in both directions inside a required merge
context: pinned at exactly a98 the canaries pass; the resolver refuses a97 beside
the artefact with a real dependency conflict; a97 forced in with `--no-deps
--force-reinstall` makes the same canaries fail naming the missing symbol. So
this record does not propose an unbuilt idea. It generalises a mechanism that
already exists, in the direction `dotmac_starter_mt` ADR-0006's product-first
rule requires: name the qualifying production implementation and port it, rather
than reinventing a fleet version beside it.

**The next bump measured that same lane, and found a THIRD fact nobody had
derived.** `0.1.0a7` moves the floor from `>=0.1.0a98` to `>=0.1.0a100`, because
a new source file imports `dotmac_kernel.product_database_catalog` — absent
from the published `dotmac-kernel` `0.1.0a99` wheel, present in `0.1.0a100`. The
excluded version therefore became a99, and **a99 contains
`dotmac_kernel.transactions` perfectly well.** The a6 lane grepped the forced
failure for that name as a STRING LITERAL, and neither of its two outcomes is
the proof: it demands a failure that cannot occur, so the lane goes red for the
wrong reason; or the name appears in the output for some unrelated reason and
the lane goes GREEN having established nothing about the new boundary. The
second is the worse half, and both are silent — nothing about the literal
announces that it expired the moment the floor moved.

The shape has a name already, and it is two named defects at once.
`dotmac_starter_mt` ADR-0018's 2026-08-26 amendment states that a guard must
test the property it is NAMED for; a grep for a written module name tests
whether that string appears, which is a different property that used to
coincide with it. And that record's original observation applies unchanged: a
premise true when written and false later, with nothing in the lane able to
re-check it. **Two derived facts beside one written one is not two-thirds of a
control.** It is a lane that is correct until the next bump and vacuous
afterwards, in the colour of a lane that passed.

This record belongs here rather than in a publishing product. A floor is a
contract between two repositories, and a rule defined inside one of them cannot
bind the other or be pinned by it. One product having the mechanism is not a
standard — it is one product having the mechanism.

## Decision

### 1. The standard

> A published distribution's dependency floor is a CLAIM about the oldest
> environment its code can run in. The claim is honest only when a release lane
> INSTALLS EXACTLY THAT MINIMUM, EXERCISES A REAL CODE PATH against it, and is
> paired with a MUTATION at one release below that is required to FAIL.

### 2. Exactly the minimum — `>=` is the defect, not the notation

The canary resolves with every Dotmac-owned dependency pinned to `==` its
exact declared floor. Installing from the declared `>=` constraint normally
selects the newest release, so the canary passes on an environment no consumer
is obliged to provide.

Third-party floors are pinned where the resolver permits it. Where it does not,
the exception is RECORDED with the constraint that forced it, never dropped:
an unpinned dependency inside a floor canary is an unmeasured floor, and
silence about it reproduces this defect one layer down.

**The minimum is DERIVED, never written down twice.** It is read from the
published artefact's own dependency metadata — not from `pyproject.toml`, which
lives in the source tree the canary exists to exclude, and not from a literal in
the workflow. A literal is a second authority for one fact, and two authorities
for one fact drift the moment somebody bumps the one they happen to be looking
at.

### 3. A real code path, not an import sweep

The canary imports the distribution's public surface AND executes at least one
path that reaches each dependency whose floor it is asserting.

An import sweep would have caught this instance, and that is exactly why it is
not sufficient. The next floor error will be a signature that changed, an
argument that became required, or a behaviour that moved — none of which an
import observes. A canary calibrated to the last failure catches the last
failure.

Import success and correct behaviour are **two facts**, and two facts that can
only fail together are one fact wearing two names.

### 4. The mutation, which is the half that fails in practice

The same canary runs against the release IMMEDIATELY BELOW the declared floor,
and that run is REQUIRED TO FAIL.

Without it the canary establishes only that the floor is sufficient. Two
distinct defects hide in that gap, and the mutation separates them:

- the mutation FAILS — the floor is tight and the canary is live;
- the mutation PASSES — either the declared floor is higher than the code
  needs, or the canary exercises nothing that depends on the floor at all.

Both are findings, and both are reported. A green canary with no paired red is
not evidence that the floor holds; it is evidence that nobody has learned
whether the canary can fail.

Three details decide whether the mutation is real, and each is here because
omitting it produces a lane that proves nothing while looking identical to one
that passed:

- **The target is asked of the INDEX, not hard-coded.** "The version below" written
  as a literal can name something never published, and the lane then fails on a
  resolver error while reporting the floor proven.
- **Versions are ordered NUMERICALLY.** `0.1.0a97` sorts above `0.1.0a100` as
  text, so a string comparison picks the wrong near-miss.
- **An empty answer FAILS LOUDLY.** A mutation lane is the most exposed surface
  in this arrangement, because it EXPECTS a failure: a lane that never ran and a
  lane that passed are the same colour.

Two independent observations are required of the mutation, not one. The resolver
must REFUSE the excluded version with a real dependency conflict — any non-zero
exit would also be satisfied by a network error or a mistyped index URL — and
forcing it in anyway must make the canaries fail **naming the missing symbol**,
because accepting any failure lets an unrelated breakage stand in for the proof.

**And that name is DERIVED too — it is the third fact, not a caption on the
other two.** The module the mutation requires the failure to name comes from the
same source of truth the floor does: the package's own imports, read as code,
resolved against the recorded introduction of each imported module, and reduced
to the ONE module whose introduction equals the declared floor. A hand-written
name is a second authority for a fact the floor already fixes, and it drifts on
exactly the change that makes the lane matter — the floor bump — because
raising a floor changes which module the boundary is about. The derivation
refuses rather than guesses in each of the three ways it can be wrong: no recorded
module introduced this floor, more than one did, or the package no longer
imports the one that did. The last is the sensitivity half. A row that outlived
its import leaves the lane demanding a failure that can never happen.

This applies to a NEGATIVE lane that asserts an import failure, and to nothing
else. A test that merely mentions a version is not in scope; what is in scope is
a lane whose whole verdict is "the failure was the right failure", because that
verdict is carried entirely by the name it matches on.

So the mutation lane carries **no literal at all**: not the floor, not the
target, not the symbol. Any one of the three written by hand is correct until
the next floor bump and silently vacuous after it.

### 5. Installed artefacts only, asserted FIRST

The canary runs in an environment where the distribution is INSTALLED and no
source checkout is on `sys.path`. Its first assertion resolves the imported
module's file and requires it to be under `site-packages`, and REFUSES TO
CONTINUE otherwise.

The ordering is the control. Placed anywhere but first, the assertion runs
after other canaries have already reported green against the checkout, and the
run has produced misleading evidence before discovering it was invalid.
Property 5 is what makes properties 2 through 4 claims about the release rather
than about the working copy.

### 6. Where a floor canary runs, and where it may not

- **Pre-merge**, against a wheel built from the branch.
- **Post-publication**, against the wheel the REGISTRY served, as a property of
  the release verdict — a failing canary makes the release unproven, and an
  unproven release is not tagged.
- **Never inside the publishing job.** A publisher holding the credential, with
  the bytes already on its own disk, is not an independent witness of what the
  registry will serve. That exclusion is a tested property of the lane, not a
  convention.

### 7. What a conforming repository must be able to show

1. Every floor it declares for a Dotmac-owned dependency is derived from what
   its code IMPORTS AND CALLS, not from what happened to be installed when the
   constraint was written.
2. A canary that installs exactly those minima and executes a real path.
3. A paired mutation one release below the floor, required to fail.
4. A `site-packages` provenance assertion that runs first and refuses to
   continue.
5. A post-publication run against the registry-served artefact, distinct from
   the pre-merge run.
6. All three facts DERIVED — the floor from the artefact's own metadata, the
   mutation target from the index, and the module the mutation's failure must
   name from the package's own imports — with no version literal and no module
   literal in the workflow.

## Consequences

- Floors will be RAISED across the fleet, and a raise is a compatibility
  statement with consequences for consumers already pinned below it. Raising a
  floor to match reality is a correction, not a regression, and it is better
  paid at publish time than at a consumer's container boot.
- Release lanes get slower: at least two extra resolutions and installs per
  published distribution, and the mutation is deliberately a run that must go
  red.
- A canary can now report that a floor is too HIGH. That report was previously
  unavailable and will surface constraints that were written defensively rather
  than derived.
- Where a dependency's floor cannot be pinned because a transitive constraint
  forbids it, the repository must say so. The recorded exception is uncomfortable
  by design; it is the honest form of a gap that is otherwise invisible.
- A floor bump becomes a change that can invalidate a lane without editing it.
  Raising a floor moves which module the boundary is about, so every
  hand-written name in the negative lane expires at that moment and nothing
  says so. Deriving the name is what makes the bump a change to one declaration
  rather than a change to one declaration and an unwritten list of places that
  quietly agreed with it.
- A release record naming bytes and a commit answers "which artefact". The
  question a consumer loses on is "against which floor", so the floor becomes its
  own release coordinate — checked against the declaration rather than
  transcribed beside it. A floor RAISE also creates an obligation the publisher
  does not discharge: the upgrade the consumer now owes is recorded with the
  release, or it is owed by nobody.

## Drift prevention

**Enforcement status: none FLEET-WIDE, and one reference implementation.** The
distinction matters, because the two are routinely conflated and only one of
them is a control. **The third derived fact added on 2026-09-01 is enforced by
nothing here either.** No `standards_control` rule reads it, no
`standards-profile.schema.json` field represents it, and nothing in
`tools/check_adrs.py` or `tools/check_adr_references.py` — this repository's
only readers of the ADR directory — evaluates a floor lane. Stating it as a
requirement is what this record can do; asserting that something checks it
would be the failure this section names two paragraphs down.

No check in this repository evaluates this record, and no enrolled repository's
standards profile declares a surface for it. What exists is
`dotmac-deployment-control`: `scripts/kernel_floor.py`,
`scripts/artifact_canaries.py` (canaries `declared_kernel_floor` and
`conflict_savepoint_executes`), the floor and mutation steps in the `behavioural
canaries (installed wheel)` job, and `tests/architecture/test_kernel_floor.py`,
which asserts the shape rather than trusting it. The third derived fact landed
there in pull request #17, merged `6b1ce371b07220914696243647aeb0d3947b87cc`:
`FIRST_SHIPPED_IN` and the AST import collector moved out of the test module —
which a workflow step cannot import, which is why the second copy existed —
into `scripts/kernel_floor.py`, whose `symbol` subcommand the mutation step
greps for. The same pull request repaired a second instance of the identical
defect in the implementation's own tests:
`test_the_cli_prints_the_mutation_target` pinned `0.1.0a97` as a literal,
correct only while the floor was a98, and was about to rebuild the defect one
alpha on inside the record's exemplar. Under
`dotmac_starter_mt` ADR-0006's product-first rule that is the implementation to
PORT, and this record names it so that a future family is an extraction rather
than a second writer.

One product holding the mechanism is not coverage of the fleet, and an ADR that
describes a control it does not have is the failure mode this section exists to
prevent.

The properties divide cleanly, and the division is the reason enforcement is not
a single family:

- **Decidable from repository content.** That a declared floor for a
  Dotmac-owned dependency exists at all, and that the repository declares a
  floor-canary surface naming where its canary lives. This is declaration
  checking; on its own it proves a file exists and nothing about what the file
  does, which is precisely the vacuous pass `dotmac_starter_mt` ADR-0018
  refuses to call coverage. The third derived fact adds one shape to this
  bucket and it is the sharpest one here: a module-name LITERAL in the
  negative lane is visible in the publishing repository's own workflow file,
  with no oracle, no run observation and no cross-repository lookup. That makes
  it decidable — **in the publishing repository, not in this one**, which is a
  different repository's check and not a Governance gate.
- **Requires an external oracle.** Which release FIRST SHIPPED an imported
  module is a fact about another repository's tags. ADR 0013 § 5 permits
  automation here only through a declared `peeled_tag` oracle carrying immutable
  coordinates, and no machine-readable contract declares one for this question
  yet — that is open decision 17, unchanged by this record.
- **Facts about workflow runs.** Whether a lane installed the exact minimum,
  whether the mutation ran and went red, whether the provenance assertion ran
  first, and whether the publisher was excluded are all properties of runs in
  another repository. ADR 0013 § 1 puts them outside what this repository may
  assert, and they remain review discipline until an oracle carries them.

Acceptance of this record is therefore conditioned on a named decision about
which half is automated, recorded as open decision 24. Until that decision is
made, an enrolled repository without a floor canary is an UNMONITORED REGION,
not a covered one — and this record may not be cited as though it were a gate.

The planted-violation requirement is stated in advance so the family cannot be
built without it, and the shapes are already known from measurement: a
distribution whose declared floor predates a module it imports; a canary lane
carrying a version literal instead of a derived one; a mutation lane whose
failure-match names a module written by hand rather than derived from the
declared floor; and a mutation lane whose index query returns nothing and
reports success. Each needs a synthetic repository shown to go RED. A floor
check demonstrated only against a conforming tree passes for the wrong reason,
which is the defect this whole record is about.
