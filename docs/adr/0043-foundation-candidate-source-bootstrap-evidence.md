# 0043. Foundation candidate source bootstrap is bridge evidence only

- Status: Proposed
- Date: 2026-09-05
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Governance's temporary reachability path for the Foundation contract
- Classification: Internal
- Amends: 0039 — temporary bootstrap reachability only; installed-artifact and runtime-adoption rules remain unchanged

## Context

ADR 0039 is Proposed and deliberately does not activate an
`ApplicationFoundationProfile.v1` surface in Governance. The candidate source
and its GitHub run nevertheless provide a bounded bridge needed to keep the
Foundation contract reachable while its real release path is unfinished.

The bridge evidence is the exact source, tree, contract member, canonical
symbols, candidate wheel, receipt artifact, run and expiry recorded in
`policies/foundation-profile-bootstrap.json`. The source coordinate alone is
insufficient: the record binds source and run evidence to immutable artifact
digests and a materialized wheel check.

## Decision

Governance adds a report-only, Proposed `FoundationContractBootstrap.v1`
record and a strict validator for that bridge evidence. It may validate the
record and the raw candidate/receipt artifact ZIPs' hashes, safe members,
sizes, exact `CandidateArtifact.v1` receipt linkage, wheel/sdist digests and
the named wheel contract using AST presence only. It must not parse,
canonicalize, digest,
validate or refuse `ApplicationFoundationProfile.v1`, and it does not modify
`.dotmac/standards-profile.json`, its schema or version, `standards_control.engine`,
CI, or runtime adoption.

The claims are explicitly `released=false`, `published=false`,
`installed=false`, and `runtime_adoption_authorized=false`. Status remains
`proposed`; the intended approver is Michael Ayoade. A future accepted
transition is a separate act. The bridge cannot outlive its artifact evidence
expiry. Its lifecycle owner/action is Starter issue
`https://github.com/michaelayoade/dotmac_starter_mt/issues/642`, and its
retirement trigger is exactly a valid successor Foundation release containing
the canonical contract.

Retirement is a manual Proposed action until Governance has a declared oracle
for successor-release evidence. The bridge cannot be used after the candidate
or receipt artifact evidence expires.

This record does not rehabilitate, rebuild, or publish `0.4.0a1`. It is not a
Foundation profile or a release receipt, and it does not weaken ADR 0039's
installed-artifact or runtime read-back/adoption rules.

## Consequences

The candidate contract has a typed, closed evidence shape and fail-closed
materialized-artifact checks, while Foundation profile composition remains
outside Governance. The open decision about profile enforcement, dossier
ownership and digest surfaces remains open; this bridge narrows none of those
questions. The bridge keeps its contract in the policy record and validator;
it does not create a second JSON Schema surface.

## Drift prevention

The policy record pins source commit, tree, run/attempt, both artifact IDs and
archive digests, wheel and receipt digests, contract paths, symbols, expiry and
false claims. Unknown fields and changed values refuse. The validator is a
report-only helper and is intentionally not imported by the standards engine.

The four false claims are structural rather than defaulted. The loader compares
the whole parsed record against a module-level expected value, so a record
asserting `released`, `published`, `installed` or `runtime_adoption_authorized`
does not load at all; nor does one that omits a claim, or states a truthy
non-boolean in its place. There is no flag that relaxes this.

## The two Foundation coordinates, and the ordering between them

Governance names the same Foundation contract path twice, at two different
revisions, in two packages that do not import each other:

| Where | Revision | `application_profile.py` blob |
|---|---|---|
| this bridge's `SOURCE_COMMIT` | `753a004e7f8dbab034d5d6ca565c680d931a5309` | `b940826665d3…` |
| `kernel_adoption_control.foundation_binding.FOUNDATION_APPLICATION_PROFILE` | `ee07c42261e791fde3035e7682a8e2fb77ba4603` | `9ee491b35254…` |

Both are correct and they answer different questions. The bridge binds what the
immutable candidate artifact ACTUALLY CONTAINS, and may never move, because
moving it would describe a different artifact than the one whose digests are
pinned here. The binding points at the contract AS IT CURRENTLY STANDS, and is
expected to move — to the peeled tag of a Foundation release, which open
decision 50 owns.

So their relationship is an ORDERING rather than an equality: the evidence
revision is an ancestor of the pointer revision on one mainline. Stating it
matters because the failure it prevents is silent — two constants naming two
unrelated files under one path, with nothing comparing them.

The ordering is a fact about `dotmac_starter_mt`'s history, which this
repository does not have, so it is NOT re-derived here and
`standards_control.foundation_bootstrap` runs no Git, opens no socket and
imports no HTTP client. Under ADR 0013 § 4 it is recorded as an as-of
observation carrying its coordinates, its instrument
(`git merge-base --is-ancestor`, in a checkout of that repository, both
revisions reachable from its `origin/main`), its date and a named refresh
owner. What IS checked locally is that the observation still describes the two
live coordinates: `coordinate_disagreements` reads the pointer's real
`ContractBinding` rather than a transcription and names the field that moved.
That converts a silent divergence into a loud one. It does not claim the
ancestry was verified today, and a checker that pretended otherwise would be
making a claim about another repository that ADR 0013 § 1 does not admit.
