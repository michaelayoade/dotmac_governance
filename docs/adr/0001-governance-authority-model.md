# 0001. Governance authority model

- Status: Accepted
- Date: 2026-07-24
- Effective: 2026-07-25
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Dotmac organization-wide engineering governance
- Classification: Public

## Context

Dotmac is establishing an ISO-aligned engineering governance baseline using
ISO/IEC 27001:2022 and ISO/IEC 42001:2023. ISO/IEC/IEEE 12207:2026 and
ISO/IEC/IEEE 15289:2019 are engineering references. ISO 9001 certification is
deferred until a customer, procurement, or company-wide quality-management
requirement justifies it. These are identifiers and Dotmac interpretations;
standard text is not reproduced here.

The failure mode is governance material with no single owner: a policy stated
in Knowledge, contradicted by a checked-in document, supported by an agent's
claim that it ran a check, and approved by nobody identifiable. Each artefact
looks authoritative alone. Together they cannot answer which record is true,
who approved it, or what evidence supports it.

AI-assisted engineering sharpens that problem. An agent that drafts a control,
reviews it, generates its own evidence, and concludes compliance creates a
closed loop with no independent check. Deployment defects in
`claude_knowledge` demonstrated the underlying evidence risk: source-tree tests
were green while the deployable image was broken, a smoke test exercised a
different image than the one started, and a generic bootstrap flag bypassed the
contract question it was intended to control.

Michael has already directed that this repository is private and owns
organization-wide policies, control definitions, global ADRs, templates, and
generated indexes. Repository-local technical ADRs remain beside the affected
code. Michael explicitly accepted this ADR on 2026-07-25. This accepted
revision becomes authoritative when merged to `main`.

## Decision

### Authority boundaries

Each class of record has one owner:

- **Git (`dotmac_governance`) owns organization-wide governance.** Policies,
  accepted global ADRs, control interpretations, record schemas, and evidence
  mappings are normative only here.
- **Affected repositories own local technical decisions.** A repository-local
  ADR remains beside the code and names its technical owner.
- **GitHub and controlled source systems own approval and execution evidence.**
  Evidence is cited by immutable run, artefact, digest, commit, or attestation
  reference. Prose saying a check ran is not evidence.
- **Knowledge owns discovery and continuity.** It projects pointers and
  summaries from approved Git records. Direct agent writes may record
  observations and proposals; they cannot make policy effective.
- **Issues own corrective actions, nonconformities, improvements, owners, and
  deadlines.** Prose in an ADR is not an action tracker.

### Human accountability

The interim accountable roles directed by Michael are:

- Organization policy, AI use, risk acceptance, and exceptions: Michael.
- Repository-local ADRs: the named repository technical owner/CODEOWNER.
- Controls: a named control owner; Michael approves organization-wide controls.
- Evidence: the control owner attests; a different named human verifies
  effectiveness.
- Corrective action: the action owner completes it; the control owner verifies
  closure.

Agents may draft, review, reconcile, and report. They never occupy an approver
role, approve their own output, assert evidence, accept risk, or declare
compliance. Codex and Claude reviewing each other is advisory collaboration,
not independent human approval.

### Controlled records

Governed records use machine-validated metadata appropriate to the record kind:

- stable identifier and kind;
- owner and accountable approver;
- scope and information classification;
- lifecycle status;
- applicable standard/control identifiers;
- decision, rationale, consequences, and affected systems;
- effective, review, and expiry dates where applicable;
- source repository and commit/digest;
- typed evidence references and validity period;
- superseded records and relationships.

Initial kinds are policy, control, risk, ADR, exception, evidence, incident,
review, action, and AI use case. The schema and evidence implementation remain
a separate change; this ADR establishes the ownership and lifecycle boundary.

### Engineering and collaboration workflow

- **ADR:** an agent or human drafts from source-linked facts; CI validates the
  record; the CODEOWNER reviews; a named human approval and merge activate it.
- **Pull-request review:** agents provide advisory findings. The approval record
  is human and attributable.
- **Stand-up:** agents compile source-linked observations. Decisions promote to
  ADRs and actions become owned Issues; the stand-up itself creates no
  authority.
- **Management review:** agents assemble metrics and evidence references; a
  named human chairs, decides, and signs.
- **Dual-agent collaboration:** Codex and Claude may challenge each other's
  reasoning, but their agreement is not approval or evidence.

One vendor-neutral agent policy bundle will eventually be managed from this
repository. Codex consumes `AGENTS.md`. Claude imports `@AGENTS.md` from
`CLAUDE.md`, which contains Claude-specific additions only. Managed
configuration, permissions, and hooks enforce security controls that prose
alone cannot enforce.

### Evidence and deployment invariants

- Provenance claims require pre-replacement verification of the real artefact.
- The tested image identity must equal the running container identity.
- A bootstrap or break-glass authorization names the exact contract/version it
  permits and expires after that transition.
- A test asserting a control must be exercised against a known-bad case and
  proven to fail before it is trusted.
- Registry digest/signature verification remains an explicit open control; a
  commit label alone does not cryptographically prove running bytes.

## Consequences

- Governance changes are slower than editing Knowledge, because review and
  attributable human approval are deliberate controls.
- Proposed records are discoverable but non-normative.
- Some controls will remain visibly unimplemented or unevidenced. That is a
  truthful state and preferable to prose that claims closure.
- ISO standard text stays out of Git, prompts, and Knowledge; only identifiers,
  Dotmac interpretations, implementation requirements, and evidence mappings
  are stored.
- The private repository's current GitHub plan cannot enforce branch protection.
  Green CI and human approval therefore remain an operating rule with a
  documented enforcement gap until the plan or hosting control changes.
- The current GitHub account cannot by itself prove that a human action and an
  agent action using the same account are distinct. Identity and RBAC hardening
  must close that evidence gap before automated governance projection.

## Drift prevention

- CI validates ADR numbering, lifecycle status, controlled metadata, and
  required sections. Its tests include known-bad inputs for duplicate numbers,
  invalid status, missing ownership, missing drift prevention, and an empty
  record set.
- `CODEOWNERS` names the interim organization-wide approver. GitHub enforcement
  limitations are recorded rather than treated as successful controls.
- `Proposed` records are never indexed or cited as effective policy.
- A future reconciler projects only accepted Git metadata into Knowledge and
  reports stale or conflicting projections.
- Changes to this authority model require a superseding ADR; editing a Knowledge
  entry or local agent file cannot amend it.
- Open scope, identity, evidence-format, and reviewer decisions stay in
  `docs/open-decisions.md` until a named human resolves them.
