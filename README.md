# dotmac_governance

Normative governance for Dotmac engineering: policies, architecture decisions,
control interpretations, and evidence mappings for the Dotmac management system.

**Status: public governance source of truth. ADR 0001 (authority model,
effective 2026-07-25) and ADR 0002 (development model, effective 2026-07-26)
are accepted. ADR 0003 (public repository and enforced branch protection) is
`Proposed` and non-normative. No policy has been approved yet.**

This repository exists so that governance has a single versioned owner before
any policy, control interpretation, or evidence claim is written down. Drafting
governance material anywhere else first would create a temporary authority and
guarantee migration drift later.

## Authority model

Four systems, four distinct jobs. None of them substitutes for another.

| System | Owns | Does not own |
| --- | --- | --- |
| **Git** (this repo) | Policies, ADRs, control interpretations, evidence mappings | Evidence itself; runtime state |
| **CI** | Evidence generation and attestation | Whether a policy is correct |
| **Knowledge** | Discovery and continuity — pointers and index | Authority; anything normative |
| **Issues** | Corrective actions, nonconformities, improvements | Approval of the fix |

Governance is normative only where it is checked in here. Knowledge entries aid
discovery; they never make something true, and they are never cited as evidence.

## Standards baseline

The product is a **standards-based development model**, not a certification
programme. ADR 0002 (`Proposed`) amends the ADR 0001 baseline to:

| Standard | Role |
| --- | --- |
| ISO/IEC/IEEE 12207:2026 | Process spine — which life-cycle processes exist |
| ISO/IEC/IEEE 15289:2019 | Information-item discipline — what record each produces |
| ISO/IEC 27001:2022 | Security overlay on those processes |
| ISO/IEC 42001:2023 | AI overlay, including agent participation |
| ISO/IEC 25010 | Product quality vocabulary — what a quality claim names |
| ISO/IEC 5055 | Automated source code measures — what a tool can assert |

ADR 0004 (`Proposed`) adds the quality references and states Dotmac's six
quality principles; they become binding only in the verification process.

Certification against any of these is out of current scope, reconsidered only on
an external requirement. ISO 9001 remains deferred on the same terms. Dropping
certification machinery does not drop risk management: lifecycle, security, and
AI risk activity stays inside the processes that require it.

Until ADR 0002 is approved and merged, the ADR 0001 baseline stands as written.

Only identifiers and Dotmac's interpretations belong here. This repository does
not reproduce standard text and does not itself establish conformity.

## Hard rules

1. **No ISO text.** ISO standards are copyrighted. This repository stores clause
   *identifiers*, Dotmac's own interpretation, implementation requirements, and
   evidence mappings — never reproduced standard text. This applies equally to
   prompts and Knowledge entries.
2. **No secrets.** Reference where a secret lives (an OpenBao path, a local
   path), never its value.
3. **Agents draft; humans approve.** See [AGENTS.md](AGENTS.md). An agent may
   author or review a change and may not occupy any approver role, approve its
   own output, or declare compliance.
4. **`main` changes by review.** Every substantive change arrives as a pull
   request with a named human approver.
5. **Public repository, `Public` records.** This repository is public so that
   branch protection is enforceable. Every record here is classified `Public`;
   anything requiring `Internal` or above is referenced from the system that
   holds it, never stored here. Validation runs on GitHub-hosted runners — no
   self-hosted runner while the repository is public. Hosted-CI availability
   remains an invalid reason to change visibility. See ADR 0003 (`Proposed`).

## Layout

- `docs/adr/` — architecture and governance decisions. See
  [`docs/adr/README.md`](docs/adr/README.md) for the numbering and relationship
  rules.
- `policies/` — normative policies.
- `processes/` — adopted life-cycle process definitions. Empty until ADR 0002
  is approved.
- `docs/` — scope, evidence model, and open decisions.
- `AGENTS.md` — vendor-neutral agent constraints.
- `CLAUDE.md` — Claude's import boundary for `AGENTS.md`.

## Validation

```bash
python -m unittest discover --start-directory tests --verbose
python tools/check_adrs.py
```

CI records the authoritative result. A local or agent-reported pass is useful
diagnostic context, not governance evidence.
