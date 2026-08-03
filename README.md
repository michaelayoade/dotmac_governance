# dotmac_governance

Normative governance for Dotmac engineering: policies, architecture decisions,
control interpretations, and evidence mappings for the Dotmac management system.

**Status: governance source of truth. ADR 0001 was accepted by Michael Ayoade
effective 2026-07-25. ADR 0005 is accepted only for the
`michael-workstation` non-production agent pilot. ADR 0002 (development model)
and ADR 0003 (repository visibility) remain `Proposed` and non-normative.
ADR 0006 (engineering conformance) is also `Proposed`; its profile runs only in
candidate mode.**

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
5. **Classification, not visibility.** Hosted-CI availability is never a reason
   to change this repository's visibility. Validation runs on the
   repository-scoped Seabone self-hosted runner. Material classified
   `Confidential` or `Restricted` does not belong here and is referenced from
   the system that holds it. ADR 0003 (`Proposed`) narrows this rule from the
   private-by-default form stated in ADR 0001; until it is approved, that form
   stands.

## Layout

- `docs/adr/` — architecture and governance decisions. See
  [`docs/adr/README.md`](docs/adr/README.md) for the numbering and relationship
  rules.
- `policies/` — normative policies.
- `processes/` — adopted life-cycle process definitions. Empty until ADR 0002
  is approved.
- `docs/` — scope, evidence model, and open decisions.
- `agent_control/` — typed repository, policy, endpoint, artifact, attestation,
  conformance, staging, reconciliation, backup-backed activation, and rollback
  contracts for the ADR 0005 pilot.
- `standards_control/` — typed, development-only ownership and contract-boundary
  conformance engine proposed by ADR 0006.
- `.dotmac/agent-profile.json` — this repository's checked-in pilot profile.
- `.dotmac/standards-profile.json` — the candidate engineering profile.
- `.dotmac/managed-agent-policy.json` — accepted Codex/Claude policy restricted
  to endpoint ID `michael-workstation`.
- `.dotmac/endpoints/michael-workstation.json` — reviewed non-production pilot
  enrollment; it contains identity and an OpenBao pointer, never a credential
  value.
- `AGENTS.md` — vendor-neutral agent constraints.
- `CLAUDE.md` — Claude's import boundary for `AGENTS.md`.

## Validation

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m ruff check --select E4,E7,E9,F,I,B,UP agent_control standards_control tests/test_agent_control.py tests/test_standards_control.py tools/dotmac-agent tools/dotmac-standards
python3 -m ruff format --check agent_control standards_control tests/test_agent_control.py tests/test_standards_control.py tools/dotmac-agent tools/dotmac-standards
python3 -m mypy --strict --scripts-are-modules agent_control standards_control tools/dotmac-agent tools/dotmac-standards
python3 -m unittest discover --start-directory tests --verbose
python3 tools/check_adrs.py
python3 -m agent_control verify --root . --profile .dotmac/agent-profile.json
python3 -m standards_control verify --root . --profile .dotmac/standards-profile.json --default-branch main
```

CI records the authoritative result. A local or agent-reported pass is useful
diagnostic context, not governance evidence.

See [`docs/agent-control.md`](docs/agent-control.md) for repository, staging,
reconciliation, activation, and rollback commands, and
[`docs/agent-client-contracts.md`](docs/agent-client-contracts.md) for the
official vendor behavior behind them. Activation remains impossible until this
accepted revision reaches clean canonical `main`; no command retrieves a
credential value.

See [`docs/engineering-conformance.md`](docs/engineering-conformance.md) for
the candidate standards contract and product rollout.
