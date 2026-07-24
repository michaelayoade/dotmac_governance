# 0001. Governance authority model

- Status: Proposed
- Date: 2026-07-24
- Approver: (unassigned — see docs/open-decisions.md)

## Context

Dotmac is adopting an ISO-aligned governance baseline (ISO/IEC 27001:2022 for
information security management, ISO/IEC 42001:2023 for AI management) across
repositories that are largely built with AI assistance.

The failure mode that motivates this ADR is not missing documentation. It is
**governance material with no single owner**: a policy stated in a Knowledge
entry, contradicted by a checked-in document, evidenced by an agent's assertion
that it ran a check, and approved by nobody in particular. Each artefact looks
authoritative in isolation. Together they cannot be audited, because there is no
answer to "which one is true?"

A second, sharper problem is specific to AI-assisted engineering: an agent that
drafts a control, reviews it, generates its evidence, and concludes compliance
has produced a closed loop with no independent check anywhere in it. The output
is indistinguishable from a genuine control regardless of whether the control
works.

## Decision

Governance authority is split across four systems, each with one job.

**Git (`dotmac_governance`) owns policy.** Policies, ADRs, control
interpretations, and evidence mappings are normative only where they are checked
in here. A statement that is not in this repository is not policy, however
confidently it is expressed elsewhere.

**CI owns evidence.** Evidence is *produced by a pipeline* and cited by
reference (run ID, artefact, commit). A human's or an agent's claim that a check
was performed is not evidence. If a control cannot be evidenced by CI, that gap
is recorded as a gap rather than closed with prose.

**Knowledge owns discovery.** The Knowledge server carries pointers, summaries,
and continuity across sessions. It is a retrieval aid. It is never cited as
evidence, and it never overrides a checked-in document. Where Knowledge and Git
disagree, Git is correct and the Knowledge entry is stale.

**Issues own actions.** Corrective actions, nonconformities, and improvements
live as Issues with an owner and a state. They are not tracked in prose inside
policy documents, where they become invisible once the document is skimmed.

**Agents draft and review; they never approve.** No agent occupies an approver
role, approves its own output, asserts evidence, or declares compliance.
Approval is an act by a named human, recorded in a commit distinct from the one
that authored the change.

## Consequences

- A policy change requires a pull request with a named human approver. This is
  slower than editing a Knowledge entry, which is the point.
- Some controls will sit visibly unevidenced for a while. That is a truthful
  state and preferable to a mapping that points at an agent's assertion.
- Knowledge entries about governance become derived data. A future reconciler
  should rebuild them from Git rather than have them edited directly; until that
  exists, a stale entry is expected and is not authority.
- ISO material stays out of the repository. Clause identifiers, Dotmac's own
  interpretation, and evidence mappings are stored; standard text is not,
  because it is copyrighted.
- The approver roles are currently unfilled, so nothing here is `Accepted` yet.

## Drift prevention

- CI enforces ADR prefix uniqueness and a valid `Status` on every ADR.
- An ADR in `Proposed` is not normative; tooling must not cite it as policy.
- Any change to this authority model is itself an ADR that supersedes this one —
  the model cannot be amended by editing a policy file or a Knowledge entry.
- Open, undecided items are tracked in `docs/open-decisions.md` rather than
  being resolved by assumption. An empty open-decisions list is a claim, and is
  reviewed as one.
