# 0014. Build once and bind the environment late

- Status: Accepted
- Date: 2026-08-29
- Effective: 2026-08-30
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

## Amendment — 2026-09-05: a credential filename is a value, not a mention

Michael Ayoade ruled on 2026-09-05, on the measured instance below, that the
scanner is what changes:

> fix the scanner. Do not create a new deployment candidate merely to remove
> explanatory prose.

The ruling is Michael's. This agent-authored section records it and does not
make the agent an approver. The amendment becomes normative only when Michael
merges this exact change through protected `main`. § 4's exclusion of a
credential **filename** is unchanged in substance; what changes is where the
exclusion is read to apply.

### The distinction

§ 4 excludes a credential filename because a basename is a **binding** —
something a deployment tool reads and acts on. A binding is refused wherever it
stands as a **value** in a declaration: a bare string, an element of an array,
a field of an inline table, or a key.

The same characters inside a `#` comment are a **mention**. The parser discards
them, no tool ever reads them, and a comment recording where a secret is held
and how it reaches the host is precisely what a reviewer should find in a
descriptor. A rule that refuses the artefact for explaining itself teaches
authors to delete the explanation, which costs the review the thing it needed
and removes no binding at all.

A **multiline string** is a value, not prose. The discriminator is whether the
parsed document retains the bytes: a comment does not survive parsing, while a
`"""…"""` block survives into a value something can read — a filename, a
command line, a rendered fragment. This is stated because it is arguable and
must be deliberate: reading a multiline string as prose would hand anyone a
quoting style in which a real credential binding is invisible to the rule.

The distinction is available only where the engine can parse the declaration's
grammar. A TOML declaration is read this way. A non-TOML declaration — a
compose file also names a deployment — keeps the plain-text sweep, which cannot
tell a value from a mention. That region is stated here as unimproved rather
than described as covered.

### An unparseable declaration is refused, not skipped

A declaration the engine cannot parse yields its own diagnostic,
`deployment.declaration.unparseable`, and the credential rule does **not** fall
back to scanning it as text. A scanner that silently skips what it cannot read
is a check that cannot refuse: making a file unparseable, by accident or by
intent, would evaporate the rule while the report stayed green. Refusing is
also the precondition for the comment reader being trustworthy at all, since a
lexer that separates comments from values is only meaningful over well-formed
input.

### The measured instance that forced it

`dotmac_platform_control_plane` `origin/main`
`522e2b0f702b529ea9a155daf2731bd4c1a95d57` ships a conformant
`deploy/product.toml`. The family refused it at line 178:

```
deployment.credential.filename  deploy/product.toml:178
.env names credential material; ADR 0014 § 4 excludes a credential FILENAME
```

Line 178 is prose inside a TOML comment, describing where the relay
dispatcher's OpenBao material goes:

> Its material is held in OpenBao at
> `secret/dotmac/vendor-control-plane/production/relay-dispatcher` and reaches
> the host only through the `.env` that `materialize_production_secrets.py`
> renders.

Measured through the engine's own function: one finding as shipped; zero when
the token is reworded to `environment file`; zero on the near-miss
`.environment`. It was that one token, in a comment.

It could not be repaired on the product side. `deploy/product.toml` and
`deploy/candidates/2026-09-04-activation-relay-service.toml` are the same blob,
`b7ddf4bfc9141599e3650e4a2b5be722a69ec584`, and that repository's
`tests/architecture/test_descriptor_promotion.py` enforces both the identity
and candidate immutability by digest. The alternative to fixing the scanner was
therefore to cut a new deployment candidate — an act of deployment authority —
in order to delete explanatory prose.

### Drift prevention for this amendment

The proofs live beside the family they constrain, in
`tests/test_standards_control.py`:

- the real Platform descriptor, carried byte-for-byte as a fixture whose git
  blob hash is asserted to be `b7ddf4bf…`, passes. A rule observed only
  refusing is indistinguishable from one that refuses everything;
- that same descriptor with `filename = ".env"` appended is refused, naming the
  file and the line, so admitting the real artefact costs the rule nothing;
- one proof per shape, each asserting named-or-silent explicitly: comment
  (silent), a `#` inside a quoted value (named — a stripper that split on `#`
  would truncate a real binding), array element, inline-table field, multiline
  string (all named), and unparseable input (its own diagnostic);
- the pre-change scanner, re-implemented verbatim and kept permanently, is
  asserted to fire on that comment at line 178, so "the old rule could not tell
  a value from a mention" is a check rather than a claim.
