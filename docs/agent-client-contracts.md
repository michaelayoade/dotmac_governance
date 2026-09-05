# Codex and Claude Code managed-client contracts

This is the vendor-contract reference for the accepted workstation pilot agent
control plane. It records the official client behavior that the typed adapters depend
on. It was reviewed against the live official documentation on 2026-09-05.
Re-check it before changing a rendered field or raising a client-version floor.

The review covers every official page that changes this control plane's
installation, instruction, policy, identity, MCP, hook, diagnostic, security,
network, observability, CI, or upgrade boundary. Product tutorials and Agent SDK
features that do not change those boundaries are outside this reference.

## Shared design rule

Instruction files influence model behavior; they are not deterministic security
controls. Put project conventions and routing in `AGENTS.md`/`CLAUDE.md`. Put
hard restrictions in managed settings, requirements, permissions, hooks,
sandboxing, device management, and CI. Initialization is a pre-launch endpoint
operation, so an MCP server can report state but cannot be the only bootstrap or
enforcement path.

## Codex

| Concern | Official contract | Control-plane consequence |
|---|---|---|
| Repository instructions | Codex builds one instruction chain at startup. It reads global `AGENTS.override.md` or `AGENTS.md`, then at most one instruction file per directory from the project root to the working directory. Nearer files appear later. The default combined project limit is 32 KiB. | Repository profiles own structure, routing, import direction, and byte budgets. A changed file requires a new session before it is effective. |
| Requirements | `/etc/codex/requirements.toml` on Unix and `%ProgramData%\OpenAI\Codex\requirements.toml` on Windows constrains values users cannot override. Cloud and MDM layers have higher precedence. | Render security allowlists into `requirements.toml`; do not treat `managed_config.toml` defaults as equivalent enforcement. |
| Managed defaults | `/etc/codex/managed_config.toml` on Unix supplies managed startup defaults. | Use it to install the approved Knowledge MCP definition, while `requirements.toml` separately allowlists the server name and exact URL identity. |
| Permission profiles | `allowed_permission_profiles` and `default_permissions` require Codex 0.138.0 or later. | Inventory versions before activation; the accepted pilot policy only admits `:read-only` and `:workspace`. |
| Hooks | Managed hook definitions can be enforced from `requirements.toml`, but their scripts are not distributed by Codex. | Device management must deliver scripts before `allow_managed_hooks_only` can safely become true. |
| MCP | A requirements `mcp_servers` table disables servers whose name and identity do not match. | The policy owns the allowlist; the existing Knowledge bootstrap owner remains responsible for attributable credential plumbing. |
| Host matching | `remote_sandbox_config` hostname matching is best-effort policy selection, not authenticated device proof. | Endpoint identity comes from an explicit enrollment and attributable principal, never a hostname inference. |
| Subagents | Local Codex supports custom user and project agents with independent model, reasoning, sandbox and MCP configuration. Every subagent consumes its own model and tool tokens; OpenAI recommends bounded read-heavy work as the starting point. | The primary remains the sole planner and final acceptor. Default to one Luna worker and explicit tool allowlists; use Terra/Astra only after an evidence-triggered escalation. |
| Claude Code integration | OpenAI deprecates `codex mcp-server` and directs Claude Code users to the official `openai/codex-plugin-cc`, which uses the Codex app server and the existing local Codex authentication/configuration. | Pin and inspect the plugin, keep automatic stop review disabled, and treat review, rescue and transfer as distinct authority modes. The plugin does not transfer Git, production or approval authority. |

The workstation pilot inspected and installed plugin version `1.0.6` from exact
source revision `db52e28f4d9ded852ab3942cea316258ae4ef346`. A later version or
revision needs a fresh contract review before its evidence replaces this row.

Official references:

- [Custom instructions with AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Managed configuration](https://learn.chatgpt.com/docs/enterprise/managed-configuration)
- [Configuration reference: requirements.toml](https://learn.chatgpt.com/docs/config-file/config-reference#requirementstoml)
- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex integration for Claude Code](https://learn.chatgpt.com/docs/mcp-server)

## Claude Code

| Concern | Official contract | Control-plane consequence |
|---|---|---|
| Repository instructions | Claude loads `CLAUDE.md`, not `AGENTS.md`. It supports `@path` imports; relative imports resolve from the containing file. Managed, user, project, and local instruction files concatenate. Anthropic recommends keeping each file below about 200 lines. | `CLAUDE.md` imports `@AGENTS.md` first and contains only Claude-specific additions. |
| Managed instructions | Managed `CLAUDE.md` lives in `/Library/Application Support/ClaudeCode/CLAUDE.md` on macOS or `/etc/claude-code/CLAUDE.md` on Linux/WSL. | Endpoint staging renders a distinct system-managed instruction artifact. |
| Managed settings | Managed sources have the highest precedence. Server-managed, OS/MDM, file, and Windows registry sources do not freely merge; the first non-empty managed tier wins, with documented cross-source locks. | Attestation must record the intended delivery channel, and reconciliation must inspect the effective source with `/status`, not merely file presence. |
| Managed MCP | `managed-mcp.json` is a standalone system file at the Claude managed root. When present, it exclusively controls the server set and suppresses other servers. It cannot be delivered through server-managed settings. | Device management must deliver this artifact separately. The bundle never embeds a token. |
| MCP authentication | Managed MCP files are readable by users. Anthropic directs administrators to `${VAR}` expansion, OAuth/per-user headers, or `headersHelper`. | This workstation already has the attributable environment loader, so the pilot uses `${DOTMAC_KNOWLEDGE_MCP_TOKEN}` expansion. Endpoint enrollment carries only the approved credential pointer and environment-variable name. The credential owner remains `claude_knowledge/ops/client-bootstrap`. |
| Permissions and hooks | `allowManagedPermissionRulesOnly`, `allowManagedHooksOnly`, and `allowManagedMcpServersOnly` are independent locks. Hook events have event-specific blocking behavior; `InstructionsLoaded` is observational and cannot block. | Model each lock separately. Do not claim instruction-load observation enforces policy. |
| Sandbox | Managed settings can require sandboxing, fail startup when unavailable, and forbid unsandboxed retry. Native Windows does not support the sandbox. | Schema version 1 stages managed endpoint bundles only for macOS and Linux. |
| Version gates | `requiredMinimumVersion`/`requiredMaximumVersion` can block startup, but older clients may ignore newer fields and invalid managed values may fail open. | Do not set a hard version floor until inventory proves every endpoint supports it; validate the pilot policy with `claude doctor`. |
| Diagnostics | `/context`, `/memory`, `/hooks`, `/mcp`, `/permissions`, `/doctor`, and `/status` expose different effective-state views. | Fleet attestation must collect bounded non-secret results from the appropriate diagnostic command. |
| Observability | OpenTelemetry can attribute auth, MCP connections, permissions, hooks, tools, errors, and usage when configured. | OTel is evidence input, not the policy owner. Prompt/tool detail logging remains off unless separately approved. |
| Subagent models | User agents may select `haiku`, `sonnet`, `opus`, `fable`, a full model ID or `inherit`, plus an effort and permission mode. Fable is intended for the hardest and longest-running tasks and may consume usage credits. | Sonnet is the normal primary, Haiku owns bounded reads, Opus is the first deep-analysis escalation, and Fable is exceptional. Model choice never grants authority. |
| Plugin hooks | A plugin may contribute session and Stop hooks without adding those hook bodies to model context. The OpenAI Codex plugin's optional Stop review can launch a long cross-model loop. | Install the plugin with the review gate disabled. Enabling it requires a separate explicit cost and authority decision plus loop/timeout evidence. |

Official references:

- [Administration setup](https://code.claude.com/docs/en/admin-setup)
- [Settings and precedence](https://code.claude.com/docs/en/settings)
- [Server-managed settings](https://code.claude.com/docs/en/server-managed-settings)
- [Managed MCP](https://code.claude.com/docs/en/managed-mcp)
- [MCP reference](https://code.claude.com/docs/en/mcp)
- [Memory and CLAUDE.md](https://code.claude.com/docs/en/memory)
- [Hooks reference](https://code.claude.com/docs/en/hooks)
- [Permissions](https://code.claude.com/docs/en/permissions)
- [Sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Authentication](https://code.claude.com/docs/en/iam)
- [Advanced setup and versions](https://code.claude.com/docs/en/setup)
- [Debug configuration](https://code.claude.com/docs/en/debug-your-config)
- [Monitoring](https://code.claude.com/docs/en/monitoring-usage)
- [Security](https://code.claude.com/docs/en/security)
- [Network configuration](https://code.claude.com/docs/en/network-config)
- [Subagents](https://code.claude.com/docs/en/sub-agents)
- [Model configuration](https://code.claude.com/docs/en/model-config)

## Current activation boundary

The checked-in policy is accepted only for `michael-workstation`. Staging
creates content-addressed, non-secret artifacts and an attestation. Local
activation fails closed until all of these are true:

1. The governing ADR is Accepted on the clean canonical default branch.
2. The exact endpoint ID and attributable principal match the accepted pilot.
3. A named non-production endpoint has a reviewed enrollment.
4. The Knowledge credential owner has provisioned the declared principal and
   environment loader without exposing a value.
5. The accepted local installer creates its backup and rollback manifest.
6. Version inventory and vendor-native doctor/status checks pass.
7. Candidate guidance preserves the current orchestration, attribution and
   cross-model authority rules without duplication, and any installed plugin is
   identified by version and source revision.

Production application hosts remain unrepresentable in schema version 1.
