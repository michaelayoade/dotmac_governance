# 0023. Identity covers every byte that reaches a user

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards and every enrolled Dotmac repository
- Classification: Internal
- Amends: 0014 — the identity property, which binds the artefact and its rendered configuration and does not reach bytes served from outside the image

## Context

ADR 0014 fixed a deployment's identity to an immutable artefact, an immutable
rendered configuration, and exact image digests bound together by one
authorization. Measured on ERP on 2026-08-30, that is NOT SUFFICIENT.

ERP's mutable checkout bind mounts had been removed — the obvious path by which
a working tree reaches a running container, and the one an image-digest rule is
written against. A second path survived. `sync-static.sh` rsynced static assets
FROM THE SOURCE CHECKOUT into the nginx web root, and nginx serves that
directory AHEAD OF THE APPLICATION. Production served a stylesheet **198
insertions behind** a fresh build, missing the dark-mode and accent utilities,
while the image contained a correctly compiled copy that no request ever
reached.

Two properties of that failure matter more than the incident:

**An internal check of the image would have passed throughout.** The image was
right. Every digest in the authorization was right. The bytes a browser
received came from somewhere the identity model did not describe, so no amount
of rigour about the artefact could have detected it.

**An existence check stood in for an equivalence check.** The pre-existing
guard asserted the asset file was readable — `test -r`. A stale file is
readable. The check produced a green colour for a property nobody was testing,
which is worse than no check, because it created the impression of coverage
over the exact gap.

The generalisation is not "remove bind mounts". Bind mounts were one route, and
removing them left the defect standing. The routes are: an rsync or `docker cp`
into a served directory, a reverse-proxy document root pointing anywhere but
into the image, a staging step that reads the source tree, and a committed
build artefact that is served without ever being compared against a build.

This amends ADR 0014 rather than superseding it. Everything that record decides
remains in force; § 8's conformance list did not reach the last hop, and this
record extends it.

## Decision

### 1. The amended property

> Deployment identity covers EVERY BYTE THAT REACHES A USER, not only the bytes
> inside the artefact. A path that serves content to a user is part of the
> deployment's identity regardless of whether it passes through the image.

### 2. The routes this explicitly names

Naming them is the point; a rule stated only in the abstract is how the second
route survived the removal of the first:

- static asset COPY paths — `rsync`, `cp`, `docker cp`, or any staging step
  that populates a served directory;
- reverse-proxy DOCUMENT ROOTS, and any location block that serves from disk
  ahead of the application;
- shared volumes mounted into a serving process;
- committed build artefacts that are served rather than rebuilt.

### 3. A staging step copies out of the image, never out of the tree

Where content must be staged outside the container to be served, it is copied
OUT OF THE IMAGE or out of the RUNNING CONTAINER — never out of the source
checkout, which has no digest and no authorization.

Such a step REFUSES AN EMPTY COPY rather than proceeding. A synchronisation
using `--delete` that reads an empty source empties a live web root, converting
a stale-content defect into an outage.

### 4. The served artefact is PROBED from outside, and compared

The deployment descriptor records the digest of each externally served
artefact. Verification FETCHES IT THE WAY A USER WOULD — through the proxy, at
its public path — and compares the digest of what came back.

Probing from outside is load-bearing and is the half that would have caught
this. An in-container check inspects the file the application would have served
and cannot observe that something else answered first. The question is not "is
the right file present" but "is the right file the one being returned", and only
an external probe asks it.

### 5. Equivalence, never existence

A check that an asset EXISTS, is READABLE, or is NON-EMPTY does not satisfy § 4.
Every property in that list is true of a stale file. Where a build artefact is
committed to the repository, it is gated against a fresh build of its own
source and the comparison fails on drift.

### 6. Added to ADR 0014 § 8

A conforming repository must additionally be able to show:

5. Every path by which content reaches a user is enumerated in its deployment
   declaration, including served directories that are not the image filesystem.
6. No served directory is populated from a source checkout.
7. Each externally served artefact has a digest in the deployment descriptor
   and an external probe comparing against it.

## Consequences

- Deployments with an nginx or CDN document root must either move that content
  into the image or declare and probe it. Some will discover they do not know
  what is in those directories, which is the finding.
- Verification acquires a network dependency on the deployed surface, so it
  cannot run entirely inside the build. That cost is inherent: a property about
  what a user receives cannot be measured anywhere a user is not.
- Existence checks across the fleet must be re-read as uncovered regions. They
  will be replaced or removed; leaving one in place is worse than having none,
  for the reason § 5 gives.
- ADR 0014's conformance surface grows by three properties, and repositories
  already declaring the first four are not conforming to this record merely by
  having done so.

## Drift prevention

**Enforcement status: partially decidable, and none of it is built yet.**

ADR 0014's family already reads a declared deployment surface and could carry
the decidable half of this record:

- a served-directory population step that reads the SOURCE TREE — a copy whose
  origin is a repository-relative path and whose destination is a declared
  served directory;
- a synchronisation using `--delete` with no guard against an empty source;
- a declared served directory with no recorded artefact digest, which is § 4
  absent rather than satisfied;
- an asset check whose assertion is existence or readability where an
  equivalence check is required.

Each requires the deployment surface declaration to gain a served-directory
field, which is a `standards-profile.schema.json` change affecting every
enrolled repository and is therefore not made unilaterally by this record.

What CANNOT be derived from repository content: whether the external probe ran,
what it fetched, and whether the digest matched. That is a `deployment_run`
claim under ADR 0013 § 5 and needs an oracle carrying immutable coordinates.
It remains review discipline, said plainly rather than implied.

The planted-violation requirement applies in full: the ERP shape — bind mounts
removed, a `sync-static.sh` still reading the checkout — is the specific
synthetic repository the family must be shown to go RED against. A detector
built against bind mounts alone would pass that repository, which is precisely
what happened in production.

The schema change and the profile-field ownership are recorded as open
decision 26.
