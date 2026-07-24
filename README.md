# dotmac_governance

Normative governance for Dotmac engineering: policies, architecture decisions,
control interpretations, and evidence mappings for the Dotmac management system.

**Status: bootstrapping. Nothing in this repository is approved yet.**

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

## Layout

- `docs/adr/` — architecture and governance decisions. See
  [`docs/adr/README.md`](docs/adr/README.md) for the numbering rule.
- `policies/` — normative policies.
- `docs/` — scope, evidence model, and open decisions.
