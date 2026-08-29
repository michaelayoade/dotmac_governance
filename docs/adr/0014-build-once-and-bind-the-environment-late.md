# 0014. Build once and bind the environment late

- Status: Proposed
- Date: 2026-08-29
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and every enrolled Dotmac repository
- Classification: Internal

## Context

Five Dotmac estates deploy five different ways, and the differences are not
stylistic. They are differences in what can be said afterwards about what ran.

Three measurements from 2026-08-29 fix the problem in place.

**A tag is not a release.** The observability host runs seven images pinned to
`:latest`. What ran yesterday and what runs after tonight's restart are two
different deployments with one description, and no artefact records which was
which. The host also has no version control on `/opt/observability` and 26
unordered `.bak` files serving as its rollback mechanism; a hand edit the same
day was refused by no gate and recorded by no receipt.

**An environment fact compiled into a shared artefact is a fact nobody can
change.** A product deployment descriptor carried CIDRs in `trusted_proxies`.
That list decides whose `X-Forwarded-For` is believed. It differs per
environment, and when it went stale nothing failed, because a value in Git does
not expire.

**An artefact that is silent about the environment still gets one.** A
short-form Docker port publication with no host IP publishes on every address
family the host has. Two ports were open to the internet over IPv6 while the
IPv4 rules written to contain them read, in review, as containment — and the
IPv6 rules that were supposed to cover them sat in a chain that cannot fire.
Nobody wrote a bad rule. The artefact declined to state a fact, and the runtime
supplied one.

These are two failure modes at opposite ends of one axis, and both are
avoidable at once. Hardcoding one environment into the shared artefact makes
the artefact wrong everywhere else. Rendering arbitrary mutable configuration
on the target host makes the running state unattributable. The escape is for
the artefact to carry no environment fact at all, and for the environment to
arrive as a separately produced, separately signed input at authorization time.

Dotmac has the pieces. ADR 0013 gives the vocabulary for claims about state a
repository cannot see. `docs/evidence-model.md` requires evidence from a named
source system, cited by immutable reference. `dotmac-deployment-foundation`
renders deployment assets deterministically and `dotmac-deployment-control`
owns authorization. What is missing is the stated property those pieces exist
to preserve, and a check that can fail when a repository stops holding it.

This record must be here rather than in a product. A standard defined inside
one of the deployments it governs cannot bind the others, and cannot be pinned
by them: it is the same category error `dotmac_observability` corrected by
deleting its local copy of the deployment-authorization schema.

## Decision

### 1. The standard

> Build the software and its policy ONCE, into an immutable artefact carrying
> no environment fact. Bind a separately signed environment inventory at
> AUTHORIZATION time. Deploy the deterministic result by EXACT DIGEST.

```
source ──▶ immutable artefact  ┐
                               ├─▶ deterministic rendered configuration
   signed private inventory ───┘        │
                                        ▼
                              authorization (binds every digest)
                                        │
                                        ▼
                                      host
```

### 2. Scope, stated before anything else

This standard binds **deployable software and operational configuration**:
release artefacts, container images, rendered deployment and ingress
configuration, infrastructure policy, and the deployment authorization itself.

It does **NOT** bind, and may not be cited against:

- **tenant data** — rows a tenant owns, created and changed at runtime;
- **domain decisions** — a subscription state, a work-order transition, a
  payout; these have their own owners and this standard says nothing about
  them;
- **databases** — schema and data are governed by migration rules;
- **logs and metrics** — observations, produced at runtime by construction;
- **ordinary product settings** — a tenant-scoped settings-as-data surface is a
  runtime read of a row, and deliberately so.

The boundary is part of the standard, not commentary on it. A rule stretched
over runtime data would forbid every settings resolver, audit log and domain
state machine in the fleet, and a rule that forbids the systems it governs gets
disabled rather than narrowed. **It governs what is DEPLOYED, never what is
RECORDED.**

### 3. What the immutable artefact contains

Schemas and typed models; templates and renderers; policy and alert catalogues;
conformance evidence from the real pinned tools; the promotion and rollback
manifest; **exact upstream image digests, never a tag**; the expected service
roster and the digests of the configuration it renders.

### 4. What the immutable artefact must not contain

A production endpoint; an IP address or CIDR; a host identity; a credential
value; or a credential **filename**.

The filename is not an oversight in this list. A basename is a binding, and a
redaction sweep that covers only value-shaped material passes straight over it
— which is the defect `dotmac_observability` PR #6 exists to correct.

### 5. What binds late

Environment target identities; resolved endpoints and address families; source
allowlists; authentication material; routing destinations; retention and
sizing; environment-specific topology. Stored privately and referenced **by
digest**.

A product declares **names** — a source set, a material, an endpoint role — and
the fleet-intent owner resolves those names to values. A product repository
holding the values has taken ownership of a fact it cannot keep current.

### 6. The authorization binds all of it, in one document

Release digest, private-inventory digest, rendered-configuration digest, exact
container image digests, target, approver and rationale.

**The load-bearing argument:** a deployment is assembled from four
independently produced things, and any three of them agreeing proves nothing
about the fourth.

Release digest and rendered digest stay **separate fields**. The artefact is
what was built once; the render is that artefact plus one environment.
Recording only one makes it impossible to say afterwards whether a difference
came from the software or from the environment — the question this arrangement
exists to answer.

### 7. Ownership

| Owner | Owns |
| --- | --- |
| Deployment foundation | portable specification, rendering, execution semantics |
| Deployment control | authorization and immutable approval evidence |
| Product adapter | product-specific declaration only |
| Observability | runtime health and drift evidence |
| Governance | this standard, and the check that enforces it |

An adopter may not define the authorization binding, and enforcement of this
standard may not be implemented inside a product.

### 8. What a conforming repository must be able to show

1. Every deployable image reference it declares is an immutable digest.
2. No environment address, CIDR or host identity appears in a declaration it
   ships.
3. Deployment assets are rendered deterministically and compared byte-for-byte,
   not produced on the target host.
4. The authorization names the release digest, the inventory digest, the
   rendered digest and the image digests — all four.

## Consequences

- Products declare more and resolve less. Work moves to the fleet-intent owner,
  which is the intended direction: one place knows the environment, many places
  do not.
- Two digests must be produced where one used to be, and both recorded. A
  pipeline recording only the release digest satisfies the letter of "deploy by
  digest" and loses the ability to attribute a change, so it does not satisfy
  this record.
- An artefact carrying no environment fact cannot be validated against a real
  environment by inspection alone. That cost is real and falls on execution:
  the deploying facility must re-observe the target and compare, rather than
  trusting that a correct artefact produced a correct socket.
- Enrolled repositories must declare the surface this standard is enforced over
  in their standards profile. A pin that does not name what is enforced cannot
  fail when enforcement stops covering something.

## Drift prevention

This record is enforced by a check family in `standards_control`, not by review
discipline and not by a prose scanner — ADR 0013 § 5 forbids the latter for the
reasons it gives.

The family reads a declared profile surface naming the deployment declarations
a repository ships. For each declared path the engine checks the properties in
§ 8 that are decidable from repository content:

- an image reference that is a mutable tag rather than an immutable
  `@sha256:` digest;
- an IP address or CIDR in a declared deployment surface, parsed as an address
  rather than matched as a pattern, so that a version string and a port range
  are not false positives;
- a credential-shaped filename, which § 4 excludes alongside the value;
- a declared path that does not exist, checked before its content — a surface
  naming nothing passes every other check for the wrong reason.

It fails closed: an unreadable or malformed declared surface is a diagnostic,
never a skip.

**What it does not check, stated rather than implied.** Whether a pipeline
produces all four digests, and whether an authorization names them, are facts
about workflow runs and about another repository's records. ADR 0013 § 1 puts
those outside what a repository may assert about itself, and § 5 permits
automation only where a machine-readable contract carries a declared oracle
kind. They remain review discipline, and this section says so rather than
implying coverage that does not exist.

The family carries planted-violation proofs: one synthetic repository per
diagnostic code, each shown to go red, alongside a conforming repository shown
to go green. A check demonstrated only against a clean tree passes for the
wrong reason.
