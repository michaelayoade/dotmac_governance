# 0002. Standards-based development model

- Status: Proposed
- Date: 2026-07-26
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Canonical Dotmac engineering repositories listed under "Governed scope"
- Classification: Internal
- Amends: 0001 — the standards baseline and the conformity posture it implied

## Context

ADR 0001 established who owns which governance record and how approval works.
It also recorded a standards baseline — ISO/IEC 27001:2022 and
ISO/IEC 42001:2023 as the baseline, ISO/IEC/IEEE 12207:2026 and
ISO/IEC/IEEE 15289:2019 as engineering references — and left the reader to infer
that the destination was a certifiable management system.

That inference was wrong, and following it produced the wrong next steps. The
work queued after ADR 0001 was management-system machinery: organizational ISMS
and AIMS scope statements, a risk register, a Statement of Applicability, named
independent evidence verifiers, tamper-evident evidence export, management
review, internal audit, external audit. All of it is the correct build order
for certification. None of it changes how Dotmac software is designed, reviewed,
released, or operated.

The intended product is a **standards-based development model**: a named set of
life-cycle processes, each with defined inputs, required information items, an
approval gate, and a mechanism that detects when it was skipped. Certification
is not the goal.

Under that goal the reference ordering inverts. 12207 supplies the process
taxonomy, and its value is completeness — it prevents a model consisting of the
processes that happened to come to mind while omitting operation, maintenance,
configuration management, and disposal. 15289 supplies the information-item
discipline that turns "we have a process" into a record showing the process ran.
27001 and 42001 then apply as overlays on those processes rather than as a
parallel system.

Dotmac is not starting from nothing. Branch before commit, merge only on green,
formatter and type gates before push, named host before any production deploy,
OpenBao pointers instead of secret values, ADRs for expensive decisions, and the
`dotmac_sub` source-of-truth ownership standard are already an operating
development model. They are undocumented as processes, scattered across a
personal instruction file and per-repository `AGENTS.md` files, and applied
unevenly. This ADR makes that model explicit and checkable rather than
replacing it.

## Decision

### Adopted references

- **ISO/IEC/IEEE 12207:2026** is the process spine. Adopted processes are
  identified by its process identifiers and described in Dotmac's own words.
- **ISO/IEC/IEEE 15289:2019** is the information-item discipline. It governs
  which records a process must produce and what each must contain.
- **ISO/IEC 27001:2022** applies as a security overlay on adopted processes,
  by clause identifier.
- **ISO/IEC 42001:2023** applies as an AI overlay on adopted processes, by
  clause identifier, and governs agent participation in the life cycle.

ISO 9001 remains deferred on the terms set in ADR 0001. As required there,
standard text is never reproduced — identifiers, Dotmac interpretations,
implementation requirements, and evidence mappings only. Licensed access to
12207 and 15289 is a prerequisite for the detailed process and information-item
mapping and is not yet in place.

### Information items are not work products

A process declares two distinct things, and conflating them is the failure mode
this clause exists to prevent:

- **`required_information_items`** — records governed by 15289 that the process
  must produce, each with a defined location, owner, and content expectation.
  A pull-request description, an ADR, a release record, a review outcome.
  These are what a conformance check may demand.
- **`work_products`** — the engineering output itself: source, schemas,
  migrations, tests, infrastructure definitions, built artefacts. These are
  governed by the process, but they are not documentation and no information-item
  requirement is imposed on them.

A validator may require that an information item exists. It must never demand
that a work product take a documentary shape.

### Conformity posture

Certification against any adopted standard is **out of current scope**. Dotmac
does not claim conformity, does not maintain a Statement of Applicability, and
does not operate certification audit cycles. This is reconsidered only when an
external requirement — a customer, procurement process, regulator, or
interconnect partner — actually demands a certificate, applying the same test
that deferred ISO 9001.

Dropping certification machinery does **not** drop risk management. Lifecycle,
security, and AI risk activity is retained inside the adopted processes wherever
those processes require it: design and architecture decisions carry a security
and AI risk consideration, changes affecting authentication, billing
correctness, customer data, or network control carry an explicit risk statement,
and agent participation carries the human-oversight controls ADR 0001 already
established. What is dropped is the organizational apparatus that exists to
satisfy an auditor, not the analysis that exists to prevent defects.

### Governed scope

Scope is defined by **canonical repository URL and default branch**. A local
working copy, clone, worktree, archive snapshot, or reconstructed directory is
never in scope and is never authoritative, regardless of what it contains.

Initial governed set:

| Repository | Canonical URL | Default branch |
| --- | --- | --- |
| `dotmac_governance` | `https://github.com/michaelayoade/dotmac_governance` | `main` |
| `dotmac_sub` | `https://github.com/michaelayoade/dotmac_sub` | `main` |
| `dotmac_crm` | `https://github.com/michaelayoade/dotmac_crm` | `main` |
| `dotmac_erp` | `https://github.com/michaelayoade/dotmac_erp` | `main` |
| `dotmac-integration-client` | `https://github.com/michaelayoade/dotmac-integration-client` | `main` |
| `claude_knowledge` | `https://github.com/michaelayoade/claude_knowledge` | `master` |

Every other repository under the account is **out of initial scope** and is not
implicitly governed. Several are active enough to need a deliberate decision
rather than silence — `dotmac_academy_app`, `dotmac_voice`, `dotmac_mobile`,
`dotmac_vtu`, `dotmac_starter_mt`, `dotmac_data`, and
`flutter-xcode-cloud-starter`. `dotmac_field` is referenced in operational
practice but was not found under this account or in any organization it belongs
to; its canonical location is unresolved. These are recorded in
`docs/open-decisions.md` rather than assumed either way.

### Adopted processes

Six processes are adopted first, chosen because drift in them already has a
demonstrated cost:

1. **Architecture and design** — decision ownership, the source-of-truth
   standard, ADR triggers.
2. **Change and review** — branch discipline, pull-request content, human
   approval, merge conditions.
3. **Verification** — formatter, lint, type, and test gates, and what a green
   result is permitted to mean.
4. **Release and deployment** — version labelling, release records, the
   named-host rule for production.
5. **Configuration and secrets** — configuration ownership, OpenBao pointer
   discipline, environment separation.
6. **Agent participation** — which life-cycle stages an agent may act in, what
   it may author, where the human gate sits, and how its output is attributed.

Each is defined in `processes/`, declaring: purpose; 12207 process identifier;
owner; inputs, activities, and outcomes; `required_information_items` and where
each lives; `work_products`; the approval gate and who holds it; agent
participation limits; 27001 and 42001 clause identifiers with Dotmac's
interpretation; and its enforcement mechanism.

Once these six exist, the remaining 12207 processes are reviewed for gaps rather
than adopted wholesale. Operation and maintenance feedback, and configuration
management across repositories, are the expected gaps.

### Enforcement rule

Every adopted process declares either a **CI check that verifies it** or an
**explicitly named human owner** who performs it manually. A process with
neither is deleted, not marked aspirational.

This is the same instinct that keeps `policies/` honestly empty. A process
document that nobody enforces and nobody owns describes a practice that is not
happening, and it is more damaging than its absence because it reads as
coverage.

### Relationship to ADR 0001

This ADR amends ADR 0001's standards baseline and conformity posture. It does
**not** supersede it. The authority model remains in force in full: the
four-system split across Git, CI, Knowledge, and Issues; human accountability
roles; agents draft and humans approve; the evidence boundary; controlled record
metadata; private-by-default; and the deployment provenance invariants. Those
controls are load-bearing for a development model and would have been discarded
by a supersession.

While this record is `Proposed` the amendment is not in force and ADR 0001's
baseline stands as written.

## Consequences

- The remaining work becomes consolidation with a completeness check, not a
  greenfield governance build. Most of what the six processes describe already
  happens.
- ISMS and AIMS organizational scope statements, the risk register, the
  Statement of Applicability, independent evidence verifiers, tamper-evident
  export, and audit cycles are no longer required work. Open decisions 1, 2,
  3, and 4 change shape or close.
- Dotmac gains no ability to answer a certification request. That is the
  accepted trade, and it reverses on an external requirement.
- The evidence model must be derived from adopted processes and their
  information items, not designed ahead of them. `docs/evidence-model.md`
  stays a draft until the six processes exist.
- Enforcement depends on protected default branches. Until branch protection is
  technically enforced, every adopted process gate is an operating rule with a
  documented enforcement gap, exactly as ADR 0001 records.
- Four of the six governed repositories are public while the governance
  repository is private. Whether a public default branch is compatible with the
  configuration-and-secrets process is a control question this ADR raises and
  does not decide.
- `claude_knowledge` uses `master` as its default branch. The conformance
  profile must carry the branch name rather than assume `main`.
- Agent participation cannot be fully evidenced while agents act through
  Michael's GitHub account. That process is definable now but not verifiable
  until identity separation lands.

## Drift prevention

- CI validates the `Amends` relationship to ADR 0001, rejects a relationship
  pointing at a missing or self-referencing record, and rejects an amendment
  that does not name the part it changes. Known-bad fixtures prove each control
  fails before it is trusted.
- The repository `README.md` standards-baseline section is updated in the same
  change as this ADR. A front page contradicting the record set is drift on day
  one.
- Each process definition carries a machine-readable enforcement declaration.
  A process with neither a CI check nor a named manual owner fails the
  conformance validator.
- The per-repository conformance profile keys on canonical URL and default
  branch. A local directory cannot satisfy a scope check, so stale copies cannot
  silently become governed systems.
- Scope additions require an amendment to this ADR. A repository does not become
  governed by being mentioned in a pull request, an Issue, or a Knowledge entry.
- The conformity posture is reviewed only on a named external requirement.
  Absent one, no drift toward certification work is expected or funded.
- Adopting a 12207 process without licensed access to the standard is a known
  gap. Process identifiers stay unmapped, and are recorded as unmapped, until
  that access exists.
