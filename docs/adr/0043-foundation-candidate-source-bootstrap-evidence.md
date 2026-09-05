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
