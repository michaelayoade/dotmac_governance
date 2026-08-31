# 0030. A framework's default-on surface is a decision nobody made

- Status: Accepted
- Date: 2026-08-31
- Effective: 2026-08-31
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Governance-enrolled Dotmac repositories, and every assembly built on a framework that enables a surface by default
- Classification: Internal

## Context

### The measured instance

`dotmac_platform_control_plane` (Platform CP), pull request #94, *The API
documentation of a production control plane is a decision, not a FastAPI
default*, merged `7373f1ded82e580ff3729d89584e3dc864438265` at
2026-08-31T08:06:10+01:00. The product's own record is its ADR-0016, *API
documentation exposure is a declared assembly policy, not a FastAPI default*,
`ACCEPTED` 2026-08-31. Every claim below was read from the repositories, at the
merge commit and at the current default branches.

The cause is one line in the shared kernel.
`packages/dotmac-kernel/src/dotmac_kernel/app_factory.py:654`, read at
`dotmac_starter_mt` `origin/main` `da710bd7e744800fa42ae8fd5d6a2730decc2ce3`:

```python
app = FastAPI(title=spec.name, lifespan=lifespan)
```

None of `docs_url`, `redoc_url`, `openapi_url` or
`swagger_ui_oauth2_redirect_url` is passed — those four identifiers do not occur
anywhere in the kernel package. FastAPI's defaults therefore apply, and **every
assembly over `dotmac_kernel.create_app` mounts `/docs`,
`/docs/oauth2-redirect`, `/redoc` and `/openapi.json`.** That is
`dotmac_starter_mt`'s reference app, `dotmac_sub`, `dotmac_erp`,
`dotmac_workspace` and Platform CP, from one line none of them wrote.

**What is evidenced, and what is not.** The route mounting is derivable from the
construction and is proved in the repository: Platform CP's own test asserts
that auditing `create_app(build_spec())` before the policy is applied finds the
complete documentation path set. What a production host actually served is a
`deployment_run`-shaped fact under ADR 0013 § 1, and this record does not assert
it. What the repository does show is that the production vhost forwards `/`
wholesale and that no vhost mentions a documentation path — asserted in
`tests/architecture/test_api_documentation_ingress.py` — so nothing in the
ingress layer stood between the default and a request.

Platform CP's ADR-0016 § 7 does state present-tense outcomes on the production
host, and no deployment-run record for that host exists in the repository. Under
ADR 0013 § 1 those are claims this repository may not adopt, and it does not
adopt them. The rule below does not depend on them.

### The plane defect, arriving from both directions

Platform CP repaired the same underlying confusion twice in two days, from
opposite ends, and the pair is more instructive than either alone.

- ADR-0014 there, *One browser authentication owner for the platform console*
  (`ACCEPTED` 2026-08-31), came at it from the **browser page** side: a console
  page that needs a session.
- ADR-0016 comes at it from the **machine document** side: an OpenAPI document
  that needs a bearer token.

The shared defect is treating "authenticated" as one property. It is two, and
the transport is what separates them. They are one family, not two incidents.

### Authority status

Michael Ayoade ratified the rule below on 2026-08-31 and directed the same
ordering as [ADR 0028](0028-a-deployment-verifies-only-what-it-can-repair-or-prove-provisioned.md)
and [ADR 0029](0029-a-production-accepted-profile-never-publishes-a-simulation.md):
the ruling lands here before the corresponding Knowledge entry is promoted, so
the checked-in record is the authority and Knowledge is discovery support. The
approval is his; § "Acceptance — 2026-08-31" records it as an attributable
event and is transcribed, not made, by the drafting agent.

## Decision

### 1. The standard

> A framework's default-on surface is an undeclared decision, and must be
> refused.

The defect is not that a framework has defaults. It is that **"forgot to think
about it" and "decided to publish it" are the same bytes.** A reviewer reading
an assembly cannot tell them apart, and neither can a test, because there is
nothing to read: the decision is expressed as an absence.

Four parts. They generalise past the measured surface, and they fail separately.

### 2. The declaration is typed, and its absence REFUSES

Where a framework enables a surface by default, the assembly declares that
surface's exposure as a **typed value, per environment**, and the **absence of a
declaration refuses the build.**

**A nullable field defaulting to the framework's behaviour reproduces the bug
with extra ceremony.** If the null case means "whatever the framework does",
then the undeclared case is still the published case, and the type has bought
nothing but the appearance of a decision. Absence must be a refusal — the same
shape as an unbound migration prerequisite, which fails rather than assuming.

Publishing is **opt-in by name**. An unrecognised, unset or blank environment
takes the most restrictive policy, so a typo withholds a surface rather than
publishing one. The reference shape
(`src/vendor_cp/api_documentation.py:275-284`) matches development and test
values explicitly and returns production for everything else, including unset
and blank.

The type also carries a **rationale that cannot be empty**
(`:196-200`): a published surface is a decision someone must be able to review,
and a declaration with no stated reason is a value, not a decision.

**Stated exactly, because the difference matters:** the measured repair ships
the typed policy and four construction-time refusals, but *absence of a
declaration* refuses only in that product's **CI**, for that **one** assembly —
an assembly that simply never applies the policy is refused by nothing at
runtime and serves the framework's defaults. The construction-time form this
section requires is specified in Platform CP ADR-0016 § 6 item 2, as a kernel
spec field whose null case "must NOT mean FastAPI's default […] `create_app`
refuses to build, the way an unbound migration prerequisite refuses" — and it is
**not implemented anywhere**. So § 2 is, today, a requirement no assembly in the
fleet fully satisfies. Recording that is the point; a standard written to match
what already exists would have asked for nothing.

### 3. The gate reads the LIVE ROUTE INVENTORY, never configuration attributes

The check walks the constructed application's real routes and locates the
surface **by path**. It does not read the framework's configuration attributes.

Clearing an attribute such as `app.docs_url` does not unmount a route already
sitting at that path, so an attribute check can be satisfied while the surface
is still served — a gate that passes over the live defect. The path set the gate
looks for is the union of the framework's defaults and whatever the application
currently declares, because a policy **nobody applied** must fail the same gate
as a policy **applied wrongly**.

The reference shape is `documentation_routes`
(`src/vendor_cp/api_documentation.py:340-360`), which iterates
`app.router.routes` and says why in its own docstring:

> Derived from the mounted routes, never from the `FastAPI` attributes: the
> attributes are what an assembly meant, the routes are what it serves.

Two precisions, so the rule is implementable rather than slogan-shaped.
Attributes may be read to **widen** the candidate path set — the reference shape
unions the framework's hardcoded defaults with the current attribute values — but
never to **decide**; the decision is always "is a route mounted at this path".
And a gate that iterates one router does not descend into a **mounted
sub-application**: neither the reference implementation nor its CI smoke does, so
a documentation surface inside a sub-app is invisible to both. No such mount
exists in the measured assembly today, which makes it an unmonitored region
rather than a covered one, and it is named here rather than left to be
discovered.

### 4. An ingress rule is NEVER the authority

The application refuses to serve what it must not serve. An ingress rule may add
defence; it may never be the thing that makes the property true.

An ingress `location` block is one deployment artifact among several. A second
ingress, a container port published on loopback, an operator's port-forward, or
a block that simply matches first each removes it **with no signal** — and it is
not versioned, reviewed or tested alongside the application whose surface it
defines. This is the same lesson as
[ADR 0023](0023-identity-covers-every-byte-that-reaches-a-user.md) (`Proposed`,
cited as a draft and not as policy) reaching it from the other direction: there
an ingress served MORE than the image contained; here an ingress would be
trusted to serve LESS than the application publishes. Both say the ingress layer
is part of the surface and is not the authority for it.

**Both halves of the coupling are asserted**, so relaxing either side fails. The
reference shape (`tests/architecture/test_api_documentation_ingress.py`) asserts
that no vhost mentions a documentation path in any directive, that the
production TLS block forwards `/` wholesale **on purpose**, that the bootstrap
vhost holds no documentation rule either, and — the premise that makes the whole
argument work — that the application is reachable **without any vhost at all**.

**Corollary, and it is not a nicety:** where the application now refuses, a
`location` block for the same path appearing later is itself a **regression
signal**, because it invites the next reader to treat the application-side
policy as redundant and delete it.

### 5. Browser pages and machine documents are separate authentication planes

The type must **refuse to mix them**, at construction.

An interactive documentation page is HTML a human navigates to. A machine
document is fetched by a client that can set headers. **A browser navigating to
a page sends no `Authorization` header — it cannot; the navigation is not made
by the page's own JavaScript.** So the only way anyone ever makes a
"bearer-protected" interactive page actually load is to accept a **session
cookie** on that path.

That is why the refusal is placed on the DECLARATION rather than on the request.
The reference shape (`src/vendor_cp/api_documentation.py:201-208`) refuses a
bearer-protected interactive plane in the policy's own constructor, and says why
in the error a future engineer will read.

Refusing the declaration is what stops someone adding the cookie fallback later
without knowing why the path is sensitive. **By the time the fallback is
written, the person writing it is fixing a page that will not load, not
weakening an authentication boundary** — and to them it will look like a bug
fix. The type is what tells them otherwise.

The same constructor refuses a public interactive page whose document is not
also public — a page that cannot load its own schema is "a broken surface
pretending to be a protected one" — because a half-published plane invites
exactly the cookie repair above.

### 6. The sensitivity proof runs TWICE, and has a MIRROR

`dotmac_starter_mt` ADR-0018 rule 5 already requires a detector to be shown
failing. This record states the shape that requirement takes here, because the
obvious version is insufficient in two independent ways.

**Twice.** Plant the framework's default configuration and require the
restrictive gate to FAIL — once on a **bare framework object**, and once on the
**real assembly audited before its policy is applied**, which is the exact state
the production host was in. A gate proven only against a toy has not been proven
against the product it guards. Both exist:
`test_a_planted_default_fastapi_configuration_fails_the_production_gate` plants
a bare `FastAPI()`; `test_the_planted_default_fails_on_this_assembly_too` audits
`create_app(build_spec())` and asserts its documentation path set is the
complete default set.

**Plus the mirror.** An application serving **no** documentation must FAIL the
**permissive** gate:
`test_the_gate_is_not_vacuous_for_the_development_policy_either` builds
`FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` and requires the
development audit to object. Without it the gate is one-sided — a check that
only ever objects to routes being PRESENT passes an application that serves
nothing, so the publishing assertion establishes nothing. **A negative control
that cannot discriminate is not a control.**

### 7. What this record does not do

- It does not decide any product's documentation policy. It requires the policy
  to be declared, typed, refused when absent, and gated against the live routes.
- It does not name the surfaces a framework defaults on. Documentation routes
  are the measured instance; the rule is about the class.
- It does not discharge the kernel obligation. Platform CP's ADR-0016 § 6 states
  plainly that the repair there is the CONSUMER half of a contract the kernel
  should own, and that the kernel defect is unrepaired. Every other assembly
  still inherits it — see Consequences.
- It creates no check, no standards-profile field and no CI gate. See
  § Drift prevention.

## Consequences

- **The kernel default is still live.** The measured repair is product-local to
  Platform CP; `dotmac_starter_mt`'s reference app, `dotmac_sub`, `dotmac_erp`
  and `dotmac_workspace` each still construct their application through the same
  unchanged line. This record makes that a named, open exposure rather than an
  unnoticed one, and each of those assemblies is an unmonitored region until
  either the kernel surface lands or the assembly declares its own policy.
- Extracting the kernel surface is the ADR 0006 product-first path: Platform CP's
  `api_documentation.py` is the qualifying implementation to port, and porting it
  is an extraction, not a second writer. Writing it again per product is the
  outcome that rule exists to prevent.
- Assemblies will discover other default-on surfaces once they look. That is the
  record functioning; the documentation routes are the instance, not the scope.
- § 5 will read as pedantry until someone tries to make an interactive page work
  behind a bearer token. The refusal is placed where it is precisely because that
  attempt looks reasonable from inside.
- § 6 raises the cost of every gate of this class by one test. The mirror is the
  cheap half and the one most likely to be dropped in review as redundant.
- Enrolled repositories acquire no new failing check from this record.

## Drift prevention

**Enforcement status: none yet.** No `standards_control` rule evaluates this
record, no `standards-profile.schema.json` field represents an assembly's
default-on surface declarations, and no engine diagnostic exists for it. This is
stated review discipline, which ADR 0013 § 5 permits so long as it is said
plainly rather than implied.

Confirmed at this repository's `main` `43b8c59` rather than carried over from
ADRs 0028 and 0029: `standards_control._governance` resolves exactly the one
path each enrolled profile declares as `governance_model.source` and reads a
single `- Status:` line from it; a search across `standards_control/`,
`gate_control/`, `agent_control/`, `programme_control/`, `tools/` and
`.github/workflows/` finds nothing that reads the ADR directory except
`tools/check_adrs.py`, which runs in this repository's own CI. All seven
enrolled profiles pin the same source,
`docs/adr/0006-cross-repository-engineering-conformance.md`, expecting status
`accepted`. **Adding this record turns no gate red in any enrolled repository.**

What would be **decidable from repository content**, stated in advance so a
future family cannot be built without its known-bad cases:

- a framework application object constructed without an explicit value for a
  parameter the framework defaults to ON — the § 2 shape, and the one that is
  hard to see precisely because there is nothing written down to inspect;
- a policy type whose field is nullable and whose null branch resolves to the
  framework's behaviour, which is § 2's stated non-conformance rather than an
  approximation of it;
- a gate reading a framework configuration attribute where the application object
  exposes a route collection — § 3 violated visibly in the source;
- an environment classifier whose unmatched branch resolves to the permissive
  policy rather than the restrictive one;
- a documentation-style route whose declared guard depends on cookie transport
  under any exposure — § 5's type-level refusal expressed as a check.

**Not decidable, and outside what this repository may assert** under ADR 0013
§ 1: what a running host actually served, and whether anyone fetched it. Those
are `deployment_run`-shaped facts and no machine-readable contract declares that
oracle (open decision 17, unchanged). This record therefore states what an
assembly PUBLISHES, which is derivable from its construction, and does not
assert what any host SERVED.

**Non-vacuity.** § 6 is itself the non-vacuity requirement, and any future family
inherits it verbatim: the planted default must go RED twice — bare object and
real assembly — and the mirror must go RED on an application that serves nothing.
A family shipped with only the first half would be the one-sided gate § 6 exists
to forbid, which is the failure this section exists to prevent.

Whether any of this is built, and by whom, is open decision 37. Acceptance of
this record does not make that decision and does not create the family described:
a standard being normative is not evidence that a control enforces it.

## A hazard recorded, not resolved: cross-repository ADR references

Writing this record surfaced a problem this repository's own numbering rule does
not cover, and it is recorded here because the cost lands on records that cite
each other.

The sharpest exhibit is in the exemplar itself. Platform CP ADR-0016's own
`Relates to:` header (`docs/adr/0016-api-documentation-exposure-policy.md:11-12`)
reads:

> ADR-0018 in `dotmac_governance` (a guard exemption states an enforceable
> premise)

**That is the wrong repository.** This repository's ADR 0018 is *Authority
cutovers leave receipts and decommissions retire delegations*. The rule quoted is
`dotmac_starter_mt` ADR-0018, *A guard exemption must carry an enforceable
premise*. Both headings were read to confirm it. This is not a criticism of that
record's substance — it is the most careful cross-repository citation in the
document, the one place its author stopped to qualify a reference, and it still
went to the wrong repository. If qualification by hand is unreliable when
someone is deliberately being careful, it is not a convention, it is a hope.

The unqualified case is the same defect without the visible tell.
`src/vendor_cp/commercial_backfill/planner.py:29` reads:

> before the effect (ADR-0014's shape, applied to a planner)

It means the KERNEL's ADR-0014, `dotmac_starter_mt`
`docs/adr/0014-at-most-once-execution-has-one-owner.md`. Since 2026-08-31 that
repository also has its own ADR-0014, *One browser authentication owner for the
platform console*, and this repository has a third, *Build once and bind the
environment late*. **Three distinct accepted ADR-0014s exist across the fleet,
two of them in scope for that one file**, and the reference does not say which.

**It was already three-way before the record that appeared to cause it.**
`dotmac_starter_mt` and this repository both held an ADR-0014 as of 2026-08-29,
and that repository already disambiguates by hand in
`docs/CONTROL_EXCEPTIONS.md` ("Governance ADR 0014") while other references in
the same tree mean its own. Platform CP's ADR-0014 made it three-way; it did not
create the problem.

**And the next one is already loaded.** `ADR-0018` occurs bare seven times in
Platform CP — tests, architecture documentation and its `AGENTS.md` — all meaning
the starter's. They resolve today only by elimination, because Platform CP's
numbering stops at 0016. **The day it writes its own ADR-0018, all seven silently
change meaning**, by the identical mechanism that just fired on 0014. A rule
written only for 0014 would be stale within two records.

`docs/adr/README.md` § Numbering already handles the collision case it was
written for — two branches picking the same free number **within one
repository**, resolved by "the ADR that merges first keeps the number", with CI
enforcing prefix uniqueness. That rule cannot help here. Neither repository is
wrong, renumbering would be arbitrary, and prefix uniqueness is per-repository
by construction.

**The recommendation, offered and not decided:** an ADR reference that crosses a
repository boundary should be repository-qualified — "kernel ADR-0014",
"Governance ADR 0014", "Platform CP ADR-0014" — and a bare `ADR-NNNN` should mean
"this repository's", nothing else. That is a documentation convention with a
plausible cheap detector (a bare reference in a file whose repository has a
record at that number AND whose imports reach another repository that also does),
and it is exactly the kind of rule that should not be adopted by inference.
Recorded as open decision 38.

Two facts should inform whoever decides it. Qualification today is the rare
exception rather than the convention — a survey of both repositories found the
overwhelming majority of `ADR-NNNN` references bare. And the qualified minority
uses no agreed spelling: some write `` `dotmac_governance` ADR 0013`` with a
space, others `kernel ADR-0003` with a hyphen. There is a pattern; there is no
rule, and nothing enforces either.

## Acceptance — 2026-08-31

Michael Ayoade approved this record on 2026-08-31. Under `AGENTS.md` an agent may
not occupy the approver role or approve its own output; neither happened here.
The standard in § 1, the four parts in §§ 2-5 and the sensitivity requirement in
§ 6 are his, transcribed.

Acceptance covers the standard and its parts. It does not discharge the kernel
obligation, does not assign an enforcement owner, does not decide the ADR
reference convention in § "A hazard recorded", and does not extend this
repository's `Amends:` relationship to `dotmac_starter_mt` ADR-0018 or to
Platform CP ADR-0014 and ADR-0016 — that field is scoped to this repository's own
ADR directory, so those relationships are stated in prose above, and their
propagation is the same situation as open decisions 20, 31, 34 and 36.
