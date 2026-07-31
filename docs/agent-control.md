# Agent bootstrap, conformance, and pilot activation

`dotmac-agent` is the repository bootstrap, validation, and endpoint adapter
accepted by ADR 0005 for `michael-workstation` only. It never retrieves a
credential or authorizes another endpoint.

## Commands

From the repository root:

```bash
python3 -m agent_control verify
python3 -m agent_control doctor
python3 -m agent_control bootstrap
python3 -m agent_control bootstrap --apply
python3 -m agent_control render --kind agents
python3 -m agent_control render --kind claude
python3 -m agent_control deploy \
  --endpoint /path/to/reviewed-endpoint.json \
  --output /path/to/empty-or-matching-stage-directory
python3 -m agent_control reconcile \
  --endpoint /path/to/reviewed-endpoint.json \
  --target-root /path/to/offline-or-live-endpoint-root
sudo python3 -m agent_control activate-local \
  --endpoint .dotmac/endpoints/michael-workstation.json \
  --backup-root /var/backups/dotmac-agent/michael-workstation-0.1.0 \
  --migrate-existing
sudo python3 -m agent_control rollback-local \
  --manifest /var/backups/dotmac-agent/michael-workstation-0.1.0/manifest.json
```

`tools/dotmac-agent` is an equivalent repository-local launcher.

- `verify` checks the strict profile contract, canonical Git identity,
  committed revision and dirty state, governance source/status, instruction
  structure and byte budget, authority routing, validation paths, secret-like
  literals, managed projection drift, and rollout gates.
- `doctor` adds local Codex and Claude executable/version discovery. It never
  reads or prints credential values.
- `bootstrap` is a dry-run unless `--apply` is present. It creates missing
  instruction files. It updates an existing file only in `managed` render mode
  and only when the generated-file marker proves the file belongs to the
  renderer.
- `render` writes one deterministic projection to standard output.
- `deploy` parses the accepted pilot policy and one attributable endpoint
  enrollment, then stages content-addressed Codex/Claude artifacts plus a
  non-secret attestation. It preflights every output and refuses conflicting
  files without partially writing. Generic `--apply` remains disabled.
- `reconcile` is read-only. It compares each installed managed artifact with
  its desired SHA-256 identity, checks only whether the named credential
  environment variable is present, and emits the same typed activation gates.
  It never reads or prints the credential value. The report is suitable for a
  future read-only MCP adapter.
- `activate-local` is the accepted endpoint-management owner for this pilot. It
  requires a clean canonical-`main` source, exact endpoint allowlist match,
  root privileges for live paths, explicit migration authorization, and a new
  or empty backup root. It backs up every replacement and writes a strict
  manifest before atomic installation.
- `rollback-local` changes nothing unless every activated target and backup
  still matches that manifest; post-activation drift causes a complete refusal.

Use `--format json` with every reporting, deployment, activation, or rollback
command for a stable machine-readable report.

## Development validation

The runtime engine uses only the Python standard library. Development and CI use
the pinned validators in `requirements-dev.txt`:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m ruff check --select E4,E7,E9,F,I,B,UP agent_control tests/test_agent_control.py tools/dotmac-agent
python3 -m ruff format --check agent_control tests/test_agent_control.py tools/dotmac-agent
python3 -m mypy --strict agent_control tools/dotmac-agent
python3 -m unittest discover --start-directory tests --verbose
python3 tools/check_adrs.py
python3 -m agent_control verify
```

## Profile ownership

The repository profile is `.dotmac/agent-profile.json`. Its schema is
`agent_control/schema/agent-profile.schema.json`, and `agent_control/profile.py`
is the executable strict parser used by every adapter.

The accepted pilot endpoint policy is `.dotmac/managed-agent-policy.json`. Its
contract and endpoint enrollment contract are:

- `agent_control/schema/managed-agent-policy.schema.json`
- `agent_control/schema/endpoint-enrollment.schema.json`
- `agent_control/schema/activation-manifest.schema.json`
- `agent_control/managed.py`, the executable strict parsers, renderer, source
  gate, and staging owner

The managed policy records every configurable decision; the renderer does not
hide policy values in caller-specific branches. Semantic identifiers, endpoint
classes, platforms, client surfaces, policy states, diagnostic codes,
projection actions, permissions, update channels, deployment plans, artifacts,
attestations, and outcomes are closed immutable types. JSON and TOML exist only
at adapter boundaries.

The profile separates four concerns:

1. Git identity and governance model reference.
2. Repository instruction structure and context budget.
3. Exact repository validation commands.
4. Endpoint rollout state and blockers.

Do not put credential values, headers, tokens, passwords, or private material in
the profile. Name only an approved pointer or owner.

## Endpoint deployment staging

An endpoint enrollment is checked JSON shaped like this:

```json
{
  "schema_version": 1,
  "endpoint_id": "named-developer-workstation",
  "endpoint_class": "developer-workstation",
  "platform": "macos",
  "principal": "agent:named-developer-workstation",
  "local_user": "developer",
  "credential_pointer": "openbao:secret/claude-knowledge#client_field_name",
  "credential_environment_variable": "DOTMAC_KNOWLEDGE_MCP_TOKEN",
  "user_home": "/Users/developer",
  "allowed_surfaces": [
    "codex",
    "claude-code"
  ],
  "policy_id": "dotmac-agent-baseline"
}
```

The first selected pilot is checked in at
`.dotmac/endpoints/michael-workstation.json`. Michael selected this workstation
on 2026-07-31 and then accepted ADR 0005, the local installer, and backup-backed
guidance migration for this endpoint only.

This file contains identity and pointers, never a credential value. The
principal and credential must already be provisioned by the Knowledge bootstrap
owner. `user_home` makes the Codex global-instruction target explicit. A
hostname is deliberately absent: vendor host matching may select a policy but
is not authenticated endpoint identity.

The staged bundle contains:

- Codex global `AGENTS.md`, `requirements.toml`, and `managed_config.toml`;
- Claude managed `CLAUDE.md`, `managed-settings.json`, and
  `managed-mcp.json`;
- a user `CLAUDE.md` containing Claude-specific additions only;
- `attestation.json` with policy/source/artifact hashes and no secret.

The attestation is not activation authority while the working tree is dirty or
not on canonical `main`.
Claude's managed MCP artifact uses documented `${VAR}` expansion, matching the
already deployed per-user environment loader. Reconciliation proves file
identity and environment presence only. A deployment owner must additionally
run vendor-native diagnostics such as Claude `/status`, `/doctor`, and `/mcp`
against the effective configuration before claiming an active client is healthy.
See `docs/agent-client-contracts.md` for the official vendor behavior behind
each artifact.

## Onboarding another repository

Onboarding is a reviewed change to that repository's canonical default branch:

1. Add the versioned profile and authority-routing sources.
2. Run bootstrap in dry-run mode.
3. Review generated files before `--apply`, or retain existing files in
   `validate` mode and correct the reported structure.
4. Run the repository's prescribed checks plus `dotmac-agent verify`.
5. Keep rollout in `pilot` until the governing ADR is accepted, identity is
   attributable, blockers are closed, and the endpoint class is authorized.

Copying a local profile, adding a Knowledge entry, or running the command in an
unreviewed clone does not enroll a repository.
