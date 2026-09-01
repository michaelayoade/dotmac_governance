# 0021. A dependency floor is installed, not declared

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository that publishes a distribution another repository installs, or composes distributions other repositories publish
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

**Three further measurements, on 2026-09-01, are about the LANE rather than the
floor.** Two of them come from a gate in an unrelated domain, and that is
precisely why they belong here: they are properties of how a lane is written,
not of what it measures, so a floor lane inherits them whole. The third is the
first measurement of this record's shape from the CONSUMER's side, and it does
not fit the record as written, because the record is written for a publisher.

**A lane may not borrow a condition it advertises.** The gate measured is
`dotmac_starter_mt` ADR-0072's `rollback_key_failures`, and it advertised that
a retained rollback key is INCAPABLE OF AN INTERACTIVE SHELL. That property is
a conjunction —
`restrict`, a forced command, and no PTY — and the gate enforced `restrict` as
its own named condition while the PTY clause was covered TRANSITIVELY, by a
different function: the inventory-row parser refuses `restrict = present` beside
any permitted capability, so no row the gate could see was able to permit a PTY.
Airtight on every input the gate could receive, and the wrong shape. Relax that
parser check for an unrelated and perfectly ordinary reason and the gate keeps
its colour while a member of its advertised conjunction goes dead, and nothing
fails anywhere. Repaired in `dotmac_starter_mt` pull request #572, merged
`e729ebebedb0b16f7b743bc3862e2152b64ddefc`, where the PTY became its own named
refusal.

One detail of that repair is what makes the rule useful rather than obvious, and
it is the easiest part to lose. **The three-way decomposition did not exist in
the tree before the repair.** What existed was one advertised property whose
conjunctive structure was implicit, and one check over a member of it; naming
the three conditions was the repair's first act rather than its premise. A
conjunction nobody has written down is still a conjunction, and its unwritten
members are exactly the ones nothing covers.

**A coordinate every non-empty string satisfies is not a coordinate.** The same
record's host-observed evidence coordinate required `host`, `observed_at`,
`observed_by` and `method`, and validated each only as a non-empty string. So
`host = "unknown"`, `observed_at = "recently"` and `method = "assumed"` all
passed, and the gate would then report a retained credential SAFE ON THE
STRENGTH OF NOBODY HAVING LOOKED. Repaired in the same pull request, which
refuses a placeholder vocabulary at parse, requires `observed_at` to be an ISO
date, and requires the observation to name the host the row names.

The second instance of that shape is a different lane in the same repository,
and its detail is the instructive one. `dotmac_starter_mt`
`scripts/declared_publication_sweep.py` emitted `TODO: state why this version is
not installable` as a ledger row's own reason, and its reconciler DID read that
field — it rejected an empty one. The placeholder is not empty. So the field was
required, the check existed, the check ran, and it was satisfied by the exact
string the tool itself wrote to mean "no answer yet" (repaired in
`dotmac_starter_mt` pull request #559, merged
`7a8c22df3538f3965cf48a2a5a1aa3e60fd82474`, by hoisting the marker to one
constant and refusing it by containment). **A required field a filler satisfies
is worse than a missing one**, because it reads as an answer and nobody goes
back to look — and in both instances the check was present, ran, and was green,
which is where this defect always hides.

**The third measurement is the consumer's, and this record could not have caught
its own opening failure where that failure actually appeared.** The instance in
the first paragraphs above did not surface in the publisher. It surfaced in a
DIFFERENT repository, at container boot, in the assembly that composed the
distribution — and §§ 1 through 6 give that assembly nothing to run, because
every property they state is a property of a publisher proving its own
declaration. An assembly does not declare a lower bound for its own imports. It
pins ONE VERSION EXACTLY and composes several independently released modules,
each carrying a bound of its own, and the question it has to answer is whether
that single pin satisfies all of them.

Measured in `dotmac_platform_control_plane` pull request #111, on 2026-09-01:
the pin was already an exact `0.1.0a98`, and reading each composed artefact's
`Requires-Dist` out of its INSTALLED metadata gave `>=0.1.0a56`, `>=0.1.0a67`,
`>=0.1.0a68`, `>=0.1.0a77`, `>=0.1.0a77` and `>=0.1.0a98` across the six
distributions that assembly composes. The pin EQUALS that maximum, so it was
neither under- nor over-constrained — and nothing had been computing it. Two
canonical documents in the same tree still stated `0.1.0a77`, which the pin had
not been for some time; nothing broke, and nothing could see it.

**That pull request is OPEN and green, not merged, and this record says so
rather than rounding it up.** Its `kernel-pin` job is a required check and
passed; the mechanism is proven by execution, on a branch. That is a weaker
provenance than § 4's publisher exemplar, which shipped, and the difference is
stated here because a record that generalises an unlanded branch while sounding
like it generalises a release is making the same kind of claim this record
exists to refuse.

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
7. Every condition the lane advertises enforced inside the lane as its own
   named check, planted separately, reporting a distinct finding — § 8.
8. Every coordinate the lane depends on checked to resolve, checked to name the
   subject the claim is about, and shown to go red when it does not — § 9.
9. Where the repository is an ASSEMBLY rather than a publisher, a pin equal to
   the maximum of the floors derived from its composed distributions'
   `Requires-Dist` AND the floor its own direct imports require, proven by a lane
   of its own that runs against its exact resolved lock or image candidate and
   has been shown RED on a planted assembly import first shipped above that
   floor — § 10, §§ 10.1 and 10.2. A repository that both publishes and composes
   owes both.

### 8. A lane enforces every condition it advertises

The mutation lane's verdict is a CONJUNCTION, and § 4 already names its parts:
the resolver refused the excluded version, AND forcing it in produced a failure,
AND that failure named the derived module. A lane conforms only when each part
is its own named check inside the lane — failing on its own account, and
reporting WHICH part failed rather than that the lane is unsatisfied.

A condition may not be inherited from an invariant held somewhere else, however
reliably that invariant holds today. The measured instance is in another domain
and that is the point, because the shape is a property of how a lane is written
rather than of what it measures: a gate advertised a conjunctive property,
enforced one member of it, and was correct on every input it could receive
because a different function refused the inputs that would have violated the
rest. **A borrowed condition is an unmonitored region wearing another function's
guard.** The day that other function is relaxed for an unrelated and entirely
ordinary reason, the lane keeps its colour and loses part of its meaning, and
nothing anywhere goes red. If a lane states a property, the lane checks it.

Two consequences, and the second is the one that gets skipped:

- Each condition is planted SEPARATELY, with the others left intact, and exactly
  one finding is asserted per plant. One test that strips everything at once and
  passes when anything trips cannot say which property it enforces, and stays
  green after two of three enforcement paths have silently died.
- The findings must be asserted DISTINCT. Three conditions all reporting "the
  mutation did not prove the floor" would satisfy three separate tests while
  enforcing one property, and the separation is then cosmetic.

Where the domain's own grammar makes a single-condition plant UNCONSTRUCTIBLE,
the lane records that rather than manufacturing a fixture that can only exist
outside the grammar. The clause is observed by DIFFERENCING instead: hold the
co-dependent condition at its failing value, move only the clause under test,
and require the finding set to grow by exactly one finding naming it. A fixture
built outside the grammar proves the plant, not the property.

The scope is a lane's ADVERTISED conjunction and nothing wider. This is not a
requirement that every check be decomposed; it is a requirement that a check
which states a compound property enforce each of its parts. A property whose
conjunctive structure has never been written down is inside the scope, because
the unwritten members are exactly the ones nothing covers.

### 9. A coordinate is checked to point at something

Every fact this record requires a lane to DERIVE arrives as a coordinate into
something outside the lane: a version the index lists, an artefact's
`Requires-Dist`, a module file under `site-packages`, a run that happened. A
coordinate is evidence only when the lane checks that it RESOLVES, that it
resolves to the subject the claim is about, and when that check has itself been
shown to fail on a coordinate that does not.

§ 4 already carries one instance — an empty index answer FAILS LOUDLY — and says
why the mutation lane is the surface most exposed to it. This is the general
form, and the general form is what the special case cannot supply, because the
next dead coordinate will be a different one.

Three properties, and the third is the one usually absent:

- **Live.** A run identifier, a peeled tag, an index listing or an artefact path
  is RESOLVED, not merely well-formed. ADR 0013 § 3 already refuses a branch
  name, "latest" and an unpeeled tag as coordinates, which rules out the
  malformed ones; it does not require anybody to check that a well-formed one
  still points at something. A coordinate that has STOPPED resolving fails no
  differently from one that never did, and a dead run, tag or artefact
  coordinate is not weak evidence but no evidence.
- **Exact.** The coordinate names the subject the claim is about — this
  distribution, this version, this module, this host — and one that resolves to a
  DIFFERENT subject is refused rather than accepted as near enough. This is
  § 2's "exactly the minimum" discipline stated as a property of the coordinate
  rather than as a flag on one command.
- **Sensitivity-tested.** The check is DEMONSTRATED to go red on an absent
  coordinate, on a dead one, and on a filler. Without that demonstration the
  coordinate check is itself a lane whose passing colour nobody has earned,
  which is this record's own defect one level up.

The filler is the half worth naming explicitly, because it is the one that reads
as compliance. A required field validated as a non-empty string is satisfied by
`unknown`, `n/a`, `tbd`, `pending`, `assumed` and `recently`, and a claim with no
moment is not re-resolvable at all — a reading taken before the subject changed
is indistinguishable from one taken after. **A required field a filler satisfies
is worse than a missing one**, because it reads as an answer and nobody goes back
to look.

The scope is a coordinate that is supposed to point at something real. It is not
a rule about every string a lane records: a human-written rationale is prose and
is judged as prose. What is in scope is any field whose whole purpose is to be
followed back to a run, a tag, an artefact, a file or an observation.

### 10. The consumer form — an ASSEMBLY's floor is the maximum its composition and its own imports require

§§ 1 through 9 are written from the PUBLISHER's side: a distribution declaring a
lower bound for its own imports, and proving that declaration honest. An
assembly asks a different question, and porting the publisher form to it answers
the wrong one — while the assembly is where this record's opening failure
actually arrived.

> An assembly's dependency floor is the MAXIMUM of every floor derived from
> the `Requires-Dist` metadata of its composed distributions AND the floor the
> assembly's OWN direct imports require, and the assembly's pin must EQUAL that
> maximum.

The second input was added on 2026-09-01 by the settlement in § 10.1 below,
which also fixes what makes it more than a declaration. Read § 10.1 before
reading this quotation as a rule about two numbers.

The word "floor" is doing two jobs across this record and the difference is
load-bearing here. A library DECLARES a floor, as a `>=` lower bound on its own
imports. An assembly does not declare one at all: it pins `==`, and its floor is
a quantity it must DERIVE — from what it composes and from what it itself
imports — and then compare its pin against. Nothing in an assembly's own
declaration states this number, which is why nothing in an assembly notices
when the pin and the number part company.

Both directions are defects, and neither is visible from the pin alone:

- **Under it** — this record's opening failure, arriving through a composed
  module's requirement rather than through the assembly's own imports. The
  assembly pins a version something it composes cannot run against, and learns
  at boot.
- **Over it** — a dependency upgrade taken on nobody's behalf. It is the smaller
  harm and it is still a harm: it owes whatever migration rehearsal that upgrade
  owes, taken without anyone having decided to take it.

Two readers are involved and they read different things, which is worth stating
because collapsing them is how this goes wrong. The composed SET is enumerated
from the assembly's own dependency declaration — the tree legitimately answers
"what does this product compose" — rather than listed by hand, so a module pinned
in a later change is included without anybody remembering to add a row. Each
composed distribution's FLOOR is then read from that distribution's INSTALLED
artefact metadata, never from its source tree and never from a document that
transcribed it. The reason is § 5's, applied one layer out: a transcription is a
second authority for a fact the artefact already fixes, and a composition census
that lists floors by hand is a table somebody must remember to update.

**On this side the mutation's module name is derived by DIFFERENCE, and that is
better than the publisher form it ports.** § 4 derives the name from a recorded
`module → first release that shipped it` table. Such a table is incomplete by
construction: an import added without a matching row is invisible, and the floor
then goes under-constrained in exactly the shape this record opens with. An
assembly does not need the table, because it can obtain a real install of the
excluded version and compute:

> (every submodule of the dependency the composed source ACTUALLY imports, read
> as code) minus (the submodules that installation actually HAS, read as files)

Real imports on one side, real files on the other, and no row for anyone to
forget. An EMPTY difference is itself the finding and the command exits non-zero
saying so, because it means the pin is higher than anything the composition
needs — the over-constrained half above, reported rather than passed over.
Where a real install of the excluded version is obtainable, this is the
PREFERRED form of § 4's third derived fact.

The assembly's mutation drives its REAL BOOT rather than a synthetic import,
for § 3's reason: the boot is the path that died.

One corollary belongs with this section because it was measured with it. A
version stated in canonical PROSE is a claim like any other. An assembly's
as-built architecture document and its pin-state table both stated a kernel
version the pin had not carried for some time; nothing broke, and nothing could
see it. A version literal in a canonical document is derived from the
declaration, or the regions of that document which are not derived are named as
unmonitored.

This section previously carried two edges it deliberately did not settle: whether
an assembly's own imports join the maximum, and where an assembly's lane runs
when it publishes no distribution. **Michael Ayoade settled both on 2026-09-01.**
The rulings in §§ 10.1 and 10.2 are his, transcribed rather than made here.
Settling what a rule SAYS creates no control that checks it — the enforcement
statement for this section is unchanged and is in § Drift prevention.

#### 10.1 An assembly's own imports join the maximum

> The effective floor is the MAXIMUM of every composed distribution's INSTALLED
> `Requires-Dist` and the assembly's own declared direct constraint on that
> dependency.

Two readers become three, and the third has never been read anywhere. The
composed SET still comes from the assembly's own dependency declaration, and each
composed FLOOR still comes from installed artefact metadata. The assembly's own
contribution comes from ITS OWN SOURCE — § 1's derivation, "what the code IMPORTS
AND CALLS", turned on the assembly instead of on a library.

The declaration is where that contribution is STATED, and stating is not
establishing. The temptation to confuse the two is sharper here than anywhere
else in this record, because an assembly's declared direct constraint on the
dependency **is the `==` pin**: a maximum that reads the pin as its own third
input returns the pin, agrees with itself, and proves nothing. So the settlement
comes with the half that makes it fail:

> **A planted assembly import first shipped ABOVE that floor must turn the lane
> RED.**

That sentence is the rule. Everything the lane computes about the assembly's own
side is judged by it, because it is the only part of § 10 that cannot be
satisfied by a number somebody wrote down. § 8 applies to the plant as it applies
to every other condition here: it is planted SEPARATELY from the composed-set
plants, with those left intact, and the finding it produces is DISTINCT — an
assembly that out-imports its composition must not be reported as a composed
module having raised its floor, because the two are repaired in different
repositories by different people.

**The coincidence is now a checked property, and converting it is the whole
reason this edge needed settling.** In the measured instance —
`dotmac_platform_control_plane` pull request **#111**, still OPEN — the pin
equals the maximum over the composed set ONLY because nothing in the assembly's
own source imports a kernel symbol newer than what its modules already demand.
That is a true statement about one tree on one day, and it was an UNSTATED
PREMISE of the equality the lane reported: the lane did not read the assembly's
imports, so it could not have noticed. The day the assembly adds a direct import
of a newer symbol, the derived floor is wrong and the lane stays green — no edit
to the lane, no diff, nothing to review. This is the pin-decay consequence below
arriving through a second door, and the plant is the door's lock. **A premise
nothing checks is not a premise. It is a coincidence that has not expired yet.**

#### 10.2 Where an assembly's lane runs when it publishes no distribution

> If the assembly publishes no distribution, the lane runs **in the assembly
> repository**, against its exact resolved lock or image candidate. It reads
> installed package metadata plus the assembly's declared constraint.

This answers § 6 for the assembly form rather than leaving § 6 written only for a
publisher. § 6's second bullet re-runs against the artefact the REGISTRY served,
because the registry is the thing a consumer will actually receive. An assembly
has no such artefact, and the subject that plays the same part is the exact
resolved candidate it is about to run: the lock it resolved, or the image
candidate about to be built. "Exact" is the load-bearing word and it carries § 5's
meaning — one named resolution, read as INSTALLED METADATA, not "whatever a fresh
install produces today". The measured instance's shape, a pre-merge run and an
admission gate before the image candidate is built, is therefore § 6's answer in
the assembly's own terms and not a gap.

**One clause of § 6 is not extended by this settlement, and is left open rather
than inferred.** § 6's third bullet excludes the PUBLISHING job as a witness,
because a publisher holding the credential with the bytes on its own disk cannot
testify to what a registry will serve. An assembly has no registry to be an
independent witness of, so the exclusion has no direct analogue, and whether an
assembly's lane may run inside the job that builds its image candidate is not
decided here. That residue stays in open decision 24, which the settlement of the
two edges otherwise narrows.

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
- Lanes get longer, and the length is the point. A conjunction enforced as named
  conditions is more code than one verdict over an AND, and it is planted one
  condition at a time rather than all at once. What that buys is the ability to
  say WHICH property stopped being enforced, which a single verdict cannot say
  at any price.
- A coordinate check that has never been shown to fail becomes a finding in its
  own right, and repositories will discover they have several. This is the
  uncomfortable half: the checks in question are green today, have always been
  green, and their greenness is exactly what is unproven.
- The record now binds a class of repository it did not previously reach. An
  assembly that composes distributions owes a lane even though it publishes no
  distribution, and a repository that both publishes and composes owes both —
  they answer different questions and neither substitutes for the other.
- An assembly's pin decays the same way a mutation lane's literal does, and
  without an edit either. A pin equal to the maximum today stops equalling it
  the moment any composed module raises its own floor in its own repository, on
  its own schedule. Nothing in the assembly changes, nothing in its history
  records the moment, and the pin is simply wrong from then on. Deriving the
  maximum is what makes that a red lane rather than a silent state.
- Since § 10.1, an assembly's floor also depends on a fact about the assembly's
  OWN source, so the equality can now be broken by a change that touches no
  dependency declaration at all. Adding one import line is enough, and that is
  the cheapest edit in the repository. It is why the assembly's own contribution
  is judged on a plant rather than on its declaration: the declaration is the
  `==` pin, and a maximum taken over the pin agrees with the pin.

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

**§§ 8, 9 and 10, added on 2026-09-01, are each enforced by NOTHING, here or
anywhere else, and they are not equally close to being enforceable.** Saying
"none" three times would hide the difference, and the difference is what a
future decision has to work from:

- **§ 8 — a lane enforces every condition it advertises.** Enforcement `none`.
  This is the FURTHEST from a Governance check of the three, and it is not
  merely an oracle problem. Deciding whether a lane's checks correspond to the
  conditions it advertises requires reading the lane's own source AND its own
  test suite AND the prose that advertises the property, and then judging a
  correspondence between them. The measured instance makes the difficulty
  concrete: before its repair the conjunction had never been written down, so
  no comparison of "advertised" against "enforced" had two sides to compare.
  This is stated review discipline, and it is decidable — if anywhere — inside
  the lane's own repository, by that repository's own tests, which is where the
  measured repair put it.
- **§ 9 — a coordinate is checked to point at something.** Enforcement `none`,
  and it splits three ways. That a lane REQUIRES a coordinate field is
  decidable from that lane's own source, in its own repository. That a
  coordinate RESOLVES is by construction an external-oracle question: ADR 0013
  § 5 permits automation only through a declared oracle carrying immutable
  coordinates, and this repository declares none for a run, a tag, an index
  listing or an artefact path used this way. That the check is SENSITIVITY-
  TESTED is a fact about another repository's test suite, which ADR 0013 § 1
  places outside what this repository may assert. Nothing here changes; the
  observation is that the first third would be decidable in the lane's own
  repository, and the other two would not be decidable anywhere without an
  oracle that does not exist.
- **§ 10 — an assembly's pin equals the maximum its composition declares.**
  Enforcement `none`, and this one is not even declaration-checkable from a
  checked-in tree, which is worth saying because it looks like it should be.
  The maximum is derived from INSTALLED artefact metadata; that is a property
  of a resolved environment, not of any repository's content, and the whole
  point of § 10 is that reading it from a source tree instead is the defect.
  `standards-profile.schema.json` carries no field for a pin, a composed
  distribution set, a `Requires-Dist` reading or a floor lane — checked at this
  repository's `main` `d2066bcb` by enumerating the schema's property names,
  and re-checked at `79817a16` when §§ 10.1 and 10.2 were added — the schema's
  61 distinct property names still contain no pin, composed-set, `Requires-Dist`
  or floor-lane field, and its one name matching an import
  (`expected_import_count`) belongs to the testing-kit conformance probe and has
  nothing to do with a dependency floor. **Settling §§ 10.1 and 10.2 changed
  nothing here.** A rule with two fewer open edges is a clearer rule, not a
  checked one, and the planted-import requirement § 10.1 adds is itself enforced
  by nothing in this repository: like § 8's plants it is decidable — if
  anywhere — inside the assembly's own repository, by that repository's own
  tests, against a tree and an installed environment this repository never sees.
  The reference implementation is `dotmac_platform_control_plane` pull request
  **#111**, which is **OPEN, not merged**, re-read on 2026-09-01 and still open
  with no merge commit: its `kernel-pin` job is a required check and is green on
  the branch. That lane does not yet read the assembly's own imports at all,
  which is the gap § 10.1 names rather than one it closes. An open pull request is a weaker
  provenance than a merged one and much weaker than a release, and this record
  names it as what it is rather than as a landed exemplar. That pull request
  also cites this record NOWHERE, in any spelling, which is a fact about the
  port rather than an objection to it.

§ 10's two formerly unsettled edges — an assembly's own imports as an input to
the maximum, and where an assembly's lane runs when it publishes no
distribution — were settled by Michael Ayoade on 2026-09-01 and are now §§ 10.1
and 10.2. **That settlement is a decision about the rule and creates no check
anywhere**, which is the distinction this section exists to hold: open decision
24 asked which HALF of this record is automated, and the answer to that question
is unchanged and still owed. What the settlement removes from decision 24 is two
questions about what the rule says; what it leaves there is the automation
question in full, plus one residue it raises — § 6's exclusion of the publishing
job has no stated analogue for an assembly, so whether an assembly's lane may run
inside the job that builds its image candidate is undecided.

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
declared floor; a mutation lane whose index query returns nothing and reports
success; a lane advertising a conjunction while enforcing a proper subset of
it, with the remainder held only by another function's invariant; a coordinate
field a filler string satisfies, and a coordinate check never shown to go red
on a coordinate that does not resolve; an assembly whose pin is above or
below the maximum its composed distributions' `Requires-Dist` declare; and an
assembly whose OWN source imports a symbol first shipped above the floor its
composition declares — planted on its own, with the composed-set shapes left
intact, and required to produce a finding that names the assembly rather than a
module. Each
needs a synthetic repository shown to go RED. A floor check demonstrated only
against a conforming tree passes for the wrong reason, which is the defect this
whole record is about.
