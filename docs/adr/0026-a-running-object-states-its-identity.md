# 0026. A running object states its identity

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and every enrolled Dotmac repository that deploys a running service
- Classification: Internal
- Amends: 0014 — the re-observation obligation in its Consequences, which requires the deploying facility to compare the target and never requires the running object to state what it is

## Context

This record describes something that EXISTS. Runtime `DeploymentIdentity.v1`
merged as `dotmac_starter_mt` #531 at `56f46f4c`, and the standard was drafted
afterwards. The ordering was deliberate: ADR 0006's product-first rule applied
to governance itself rather than only to code. A standard written first would
have specified a shape nobody had built and would have been wrong in the ways
ADR 0022 was wrong until an implementation contradicted it.

**Before #531 the absence was total.** Deployment identity labels had **zero
occurrences** on Starter `main` — while the controller read exactly those
labels. It was not reading identity and finding it stale. It was reading a
field nothing wrote, and identifying the running object from whatever else was
visible: the tag, the project name, the container name. A controller that
infers identity from what it can see will always find an answer, and the answer
is unfalsifiable.

Three measurements make the field list what it is rather than a preference.

**A tag is not identity.** ERP's runtime was identified by image tag while four
bind mounts from a mutable host checkout meant `git checkout <ref>` changed
what production served with **no image change and no new digest**. Removing the
mounts was then still insufficient: `sync-static.sh` rsynced the same checkout
into an nginx root served **ahead of the application**, and production ran a
stylesheet **198 insertions behind** the one the image had itself compiled. An
internal check of the image passed throughout. Only probing the **externally
served** artefact against a descriptor-recorded digest caught it.

**A digest alone is not identity either.** `dotmac-deployment-control` `0.1.0a4`
shipped reporting `__version__ = "0.1.0a2"` while being a4 — correct bytes,
correct hashes, wrong self-report. Every identity proof it had ran against the
source tree, where two version literals disagreed in two files that nothing
compared. An authorization recording that runtime would have recorded the wrong
version while every digest in it was right. That case is the whole argument for
**product identity and source revision being separate required fields** rather
than facts a reader is expected to derive from the artefact digest by looking
them up somewhere else.

**Refusal has to be the behaviour, not a warning.** A controller that logs a
mismatch and proceeds has identity as decoration: the fields are written, the
comparison runs, the deployment happens anyway, and the only thing produced is a
line in a log nobody reads during an incident. Refusal is what makes the other
four fields load-bearing.

This record amends ADR 0014 rather than superseding it. That record's
Consequences already state the obligation — *"the deploying facility must
re-observe the target and compare, rather than trusting that a correct artefact
produced a correct socket"* — and stop short of requiring the target to be
capable of being observed. A re-observation obligation with no stated readable
surface is discharged by reading a tag, which is how ERP's runtime came to be
identified by one.

## Decision

### 1. The standard

> A running object STATES its identity, and a controller NEVER INFERS it from a
> mutable tag or project name.

### 2. The five fields, runtime-readable

A running object exposes, readable at runtime from the object itself:

| Field | What it answers |
| --- | --- |
| **artifact digest** | which bytes are executing |
| **descriptor / configuration digest** | which environment those bytes were rendered against |
| **source revision** | which commit produced the artefact |
| **product / service identity** | what this object claims to BE |
| **authorization run and deployment receipt** | who permitted it to be here, and under which approval |

Runtime-readable is the operative constraint. A value recorded only in a
pipeline, a registry or a wiki is a fact about a past event; this record is
about what the object itself will say when a controller asks it, on a host,
during an incident, when the pipeline that produced it is not the system anyone
can reach.

### 3. What is NEVER a substitute

**Tags, project names and hostnames are never substitutes for any of the five.**

Each is stable-looking and independently mutable, which is the dangerous
combination: it reads as an identifier and can be changed without changing
anything it appears to identify. A tag can be moved. A project name is a
deployment-time string. A hostname survives the object it names. None of the
three is bound to the bytes, and a controller that accepts one has not
identified the running object — it has read a label somebody typed.

The prohibition is stated as its own clause because it is the clause that gets
eroded first, and always for a good local reason: the field is missing, the tag
is right there, and the deployment is urgent.

### 4. The controller REFUSES

A controller **refuses** a running object whose identity is **missing** or
**mismatched**. Both, and they are different failures:

- **Missing** — the object does not state one or more of the five. Nothing is
  known, and a controller that proceeds has decided that unknown is acceptable.
- **Mismatched** — the object states an identity that disagrees with the
  authorization. Something is known and it is wrong, which is worse than unknown
  and must not be the case that degrades to a warning because it is noisier.

Refusal means the deployment does not proceed, not that it proceeds with an
annotation. A warning path is prohibited: given one, every mismatch becomes a
warning, and the standard survives as documentation of a control that is not
running.

### 5. Why five fields and not one digest

The fields are not redundant, and the temptation is to collapse them.

- Artifact and descriptor digests stay separate for ADR 0014 § 6's reason: the
  artefact is what was built once, the render is that artefact plus one
  environment, and recording only one makes it impossible to say afterwards
  whether a difference came from the software or the environment.
- Source revision is separate because a digest does not carry its provenance. The
  mapping lives in another system, and an identity that requires a second system
  to be reachable is not readable at runtime.
- Product identity is separate because a4 states the case exactly: an object can
  be wrong about what it is while being right about its bytes. It is also the
  field that distinguishes two services running the same image.
- The authorization run and deployment receipt are separate because the other
  four together answer *what is running* and none of them answers *whether
  anybody allowed it*.

### 6. Added to ADR 0014 § 8

A conforming repository must additionally be able to show:

8. Every running object it deploys exposes the five fields of § 2, readable from
   the object at runtime.
9. Its controller refuses a missing or mismatched identity, and has no path that
   proceeds on a warning.

## Consequences

- Every service in the fleet must emit five fields it does not emit today. #531
  makes that mechanical for anything built on the Starter runtime; anything else
  does it itself.
- Controllers acquire a refusal path, which means a deployment that would
  previously have completed will now stop. That is the control working, and the
  first few will look like the standard causing an outage rather than revealing
  one.
- A tag remains useful for humans and is now explicitly not evidence. Expect
  pressure to accept it "just for this one service", and expect the reason to be
  good each time.
- The authorization gains a counterpart it can be checked against. Until now an
  authorization named digests and nothing at the other end could be asked whether
  it agreed.
- An object that cannot state its identity cannot be deployed under this record.
  For a third-party or vendor image that may mean a wrapper, a sidecar or an
  exemption — and an exemption must state an enforceable premise under ADR 0018
  rather than being a named allowance.

## Drift prevention

**Enforcement status: partially decidable, newly implemented, and not yet in
production.**

Runtime `DeploymentIdentity.v1` exists as of `dotmac_starter_mt` #531 at
`56f46f4c`. **No product emits the labels in production yet**, so the fleet's
current state is the pre-#531 one this record describes: a controller reading
fields nothing writes. A record that reported this as covered because the
mechanism was merged would be making exactly the claim ADR 0013 § 1 forbids —
that a repository's content proves something about a running system.

What is decidable from repository content, and could become a
`standards_control` family over a declared deployment surface:

- a controller resolving identity from an image tag, a Compose project name or a
  hostname, which is § 3 violated in a form visible in the source;
- a controller with a warn-and-continue branch on identity mismatch, which is § 4
  violated the way § 4 predicts it will be;
- a declared runtime surface that emits fewer than the five fields of § 2.

What CANNOT be derived here: whether a running object actually advertises its
identity, and whether a controller actually refused. Those are facts about
deployed systems — a `deployment_run` claim under ADR 0013 § 5 — and no contract
declares that oracle today. They remain review discipline, said plainly rather
than implied by the presence of the three checks above.

**The planted-violation shapes, named in advance so the guard cannot be built
without them.** Two runtimes must each be shown to be REFUSED:

1. one advertising a **mismatched** digest — identity present and wrong;
2. one advertising **none at all** — identity absent.

Both, not either. A guard proving only the mismatch case passes a runtime that
says nothing, which is the pre-#531 fleet and therefore the exact condition this
record exists to end. A guard proving only the absent case passes the a4 shape.
And a conforming runtime must be shown to be admitted, because a controller that
refuses everything satisfies both refusal proofs for the wrong reason.

The ownership of the served-artefact probe that caught the ERP case is ADR 0023,
which is `Proposed`; this record does not depend on it and does not assume it.
Whether the five fields become a `standards-profile.schema.json` surface is open
decision 29.
