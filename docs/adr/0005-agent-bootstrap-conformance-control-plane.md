# 0005. Agent bootstrap and conformance control plane

- Status: Accepted
- Date: 2026-07-31
- Effective: 2026-07-31
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: `michael-workstation` non-production managed-agent pilot only
- Classification: Public

## Context

Dotmac uses Codex and Claude Code across repositories and developer machines.
Their durable instruction surfaces overlap without being identical. Codex loads
`AGENTS.md`; Claude Code loads `CLAUDE.md` and can import the shared file. Both
also support client configuration, hooks, permissions, skills, and MCP tools.

The existing configuration grew through three separate paths:

- repository files maintained independently, sometimes with shared rules in the
  vendor-specific file;
- a workstation-oriented Claude fleet bundle that merges user settings;
- the Knowledge client bootstrap in `claude_knowledge`, which correctly owns
  attributable Knowledge credentials and transport configuration.

No one mechanism proves that a new session loaded the intended instruction
version. An MCP-only design cannot close that gap: MCP is available after a
client starts, can be unavailable or disabled, and is itself configuration that
needs validation. Copying governance logic into an MCP server would also create
a second policy owner.

ADR 0001 already places organization-wide governance in this repository,
Knowledge in discovery, CI in evidence production, and Issues in corrective
actions. It also requires the vendor-neutral instruction boundary:
`AGENTS.md` owns shared rules and `CLAUDE.md` imports it with Claude-specific
additions only.

ADR 0002 proposes the agent-participation process and records identity
separation as a prerequisite to verifiable managed rollout. It is still
`Proposed` on the canonical default branch. Michael accepted a deliberately
narrow exception for the already attributable `agent:michael-workstation`
principal and this single non-production endpoint. This record does not close
the organization-wide identity or rollout decisions.

## Decision

### One owner and one engine

`dotmac_governance` owns the agent profile schema, instruction structure,
templates, conformance rules, and reusable `dotmac-agent` engine. Every adapter
uses that engine:

- `verify` evaluates a repository and is the CI entry point;
- `bootstrap` plans or applies safe repository instruction projections;
- `doctor` reports non-secret client availability, conformance, and rollout
  blockers;
- `render` emits a deterministic instruction projection;
- `deploy` stages a typed, content-addressed managed-client bundle or refuses a
  direct activation request;
- `reconcile` reports desired-versus-observed endpoint state without changing
  it;
- `activate-local` applies only the accepted exact endpoint after a complete
  backup-backed preflight; and
- `rollback-local` restores only targets that still match the activation
  manifest.

The engine consumes immutable typed profile contracts and returns typed
diagnostics and reports. JSON, Git, files, subprocesses, and CLI output are
adapters. No adapter owns parallel policy decisions.

Every semantic cross-module value is closed: profile/policy/endpoint IDs,
repository URLs, branches, Git revisions, model versions, endpoint classes,
platforms, client surfaces, blocker references, permission/update modes,
diagnostic codes, projection actions, deployment artifacts, attestations, and
outcomes use immutable value objects, enums, or frozen dataclasses. Mypy strict
checks Python boundaries; behavior tests and schema-enum parity tests cover
runtime JSON adapters.

### Per-repository profile

An enrolled repository carries `.dotmac/agent-profile.json`, validated against
`agent_control/schema/agent-profile.schema.json` and the executable strict
parser. It names:

- canonical repository URL and default branch;
- governance model version, Git source, and lifecycle status;
- `AGENTS.md` and `CLAUDE.md` paths, structural markers, import direction, and
  combined context budget;
- checked-in authority-routing sources and exact validation commands;
- allowed agent surfaces;
- rollout mode, managed-configuration state, authorized endpoint classes, and
  every open blocker.

Unknown keys fail. A local directory name never establishes repository identity;
the verifier compares the profile to the Git remote. The report includes the
observed commit identity and dirty state, but the commit itself remains owned by
Git. A dirty local report is diagnostic and cannot identify committed source.

### Instruction structure

`AGENTS.md` is the shared repository instruction boundary. It contains only
high-signal authority routing, ownership and safety invariants, the working
agreement, exact validation, and required reporting. Large manuals stay in
their owning checked-in documents and are routed to rather than copied.

`CLAUDE.md` must import `@AGENTS.md` as its first effective instruction and may
contain Claude-specific additions only. Exact shared bullet rules duplicated
into it fail validation. Nested, path-specific detail belongs in nested
`AGENTS.md` or `.claude/rules/`; reusable workflows belong in skills; dynamic
context belongs in Knowledge/MCP; deterministic controls belong in hooks,
permissions, and CI.

Profiles declare a warning and maximum combined byte budget. The initial
maximum is the current Codex default combined project-instruction limit of
32 KiB. The warning threshold is lower so routing can be corrected before
instructions are truncated or lose attention.

### Safe bootstrap behavior

Schema version 1 bootstraps repository files only. It does not write operating
system managed settings, install credentials, enroll identities, or deploy an
MCP server.

In `validate` render mode, bootstrap creates missing instruction files and
never overwrites existing ones. In `managed` mode, it may refresh only files
that carry the generated-file marker; it refuses to overwrite an unmarked file.
Running it again is idempotent.

The existing `claude_knowledge/ops/client-bootstrap` remains the sole owner of
Knowledge credential retrieval, validation, and Codex/Claude transport
registration. This engine may invoke a versioned owner interface in a future
accepted rollout; it never copies that credential logic and never prints secret
values.

### Managed endpoint staging

The accepted pilot policy is `.dotmac/managed-agent-policy.json`. A separate
strict endpoint-enrollment contract names one non-production endpoint,
attributable `agent:<slug>` principal, local operating-system user, platform,
allowed surfaces, policy ID, credential pointer, credential
environment-variable name, and explicit user home. It does not contain a
hostname or credential value.

Michael selected his attributable `agent:michael-workstation` macOS developer
workstation as the first pilot target on 2026-07-31. The checked-in enrollment
is `.dotmac/endpoints/michael-workstation.json`. Michael then accepted this
record, designated the local sudo-backed installer as the endpoint-management
owner, and authorized backup and migration of existing guidance for this pilot.

### Global-guidance authority migration

The current user-level Codex guidance and shared source-of-truth block are still
written by `claude_knowledge/ops/client-bootstrap`. That is the old writer. For
this pilot, the accepted new content owner is this repository's managed policy,
`docs/agent-guidance/global.md`, and renderer. The Knowledge bootstrap remains
the credential-transport owner.

During the shadow phase, reconciliation compares candidate output with the
existing user files and makes no change. Cutover requires complete rule-by-rule
content parity, a reviewed migration for the existing Codex and Claude user
instruction files, and tests proving that the effective client chains neither
lose nor duplicate shared rules. The installer backs up every replaced file and
writes a strict rollback manifest before changing a target. Only after a
successful pilot may the Knowledge bootstrap stop writing guidance and retain
credential transport as its sole responsibility. Rollback restores the prior
user instruction files and keeps the old bootstrap writer available until that
gate passes.

The deployment owner checks canonical repository URL, branch, commit, dirty
state, governance-source existence/status, endpoint/policy identity, endpoint
class, surfaces, managed-configuration state, and blockers. It renders:

- Codex global instructions, system `requirements.toml`, and
  `managed_config.toml`;
- Claude system-managed instructions, `managed-settings.json`, and the
  separately delivered exclusive `managed-mcp.json`;
- a minimal user `CLAUDE.md` containing only Claude-specific additions; and
- a typed attestation containing source identity and SHA-256 artifact identities.

Staging preflights all targets and writes only missing artifacts. Matching
artifacts are idempotent; conflicting artifacts cause a typed refusal before
any write. Candidate staging is allowed for review even when activation gates
are open, and the attestation reports those gates.

Read-only reconciliation compares installed artifacts with the exact desired
hashes and reports whether the named credential environment variable is present
without reading or printing its value. Its typed report can back a future MCP
status adapter. File identity and environment presence are not equivalent to
effective client health; the deployment owner must also collect vendor-native
post-install diagnostics before making that claim.

Generic `deploy --apply` still fails closed. The accepted pilot uses the
separate `activate-local` installer. It requires the exact endpoint ID, accepted
policy, clean canonical default branch, root privileges for live system paths,
explicit migration authorization, an absent or empty mode-0700 backup root,
and a strict manifest. It preflights every target, backs up every replacement,
writes atomically, and automatically rolls back a partial write failure.
`rollback-local` refuses if an installed target or backup hash drifted. Neither
path retrieves or prints a credential value.

### Rollout gate

The rollout contract has two states:

- `pilot` requires `managed_configuration=false`; it may carry open blockers;
- `managed` requires an `Accepted` governance source,
  `managed_configuration=true`, and an empty blocker set.

Schema version 1 rejects every endpoint class containing `production` or
starting with `prod-`. Production application hosts were deliberately cleared
of agent clients. A later version can represent a named, explicitly approved
production exception only through a separate accepted decision with rollout,
rollback, and blast-radius controls.

The repository-bootstrap profile stays in `pilot` for organization-wide
adoption. The separate managed policy is enabled only for endpoint ID
`michael-workstation` and endpoint class `developer-workstation`. Human-versus-
agent identity separation and managed rollout remain open for every other
endpoint.

### CI, evidence, and MCP

CI calls the same verifier and exercises known-good and known-bad controls.
This Accepted decision becomes an eligible activation source only after its
reviewed revision is on clean canonical `main`. CI proves the implementation
and pilot profile are internally consistent; it is not an organization-wide
conformance claim and does not activate policy on another repository or
endpoint.

No new MCP server is created in this slice. After an accepted rollout decision,
Knowledge may expose read-only views of effective policy, bootstrap plans,
repository conformance, drift explanation, and fleet status. Every response
must expose its authoritative Git source and model version. MCP never approves,
activates, or becomes the only enforcement path.

Issues own deviations, corrective actions, owners, and deadlines. CI and
controlled device-management systems produce status; Knowledge indexes pointers
and discovery metadata rather than manufacturing evidence.

## Consequences

- Dotmac gains a working control-plane runtime that uses only the Python
  standard library and has no service dependency. Ruff and mypy are pinned
  development/CI validators rather than runtime dependencies.
- New repositories can receive a safe instruction skeleton, while existing
  unmarked guidance is preserved for deliberate migration.
- Canonical repository identity, instruction direction, context size, routing
  sources, referenced validation paths, secret-like literals, and rollout gates
  become machine-checkable.
- `doctor` intentionally reports only executable path/version and profile state.
  It does not inspect or print environment values, headers, or credentials.
- The exact pilot endpoint can be activated by the accepted local installer,
  but never from a dirty feature branch or by an MCP server.
- The legacy Claude fleet bundle remains migration input, not authority. Its
  retirement waits for an accepted cutover and verified replacement.
- This decision does not resolve organization-wide human/agent identity
  separation, accept ADR 0002, enroll another endpoint or repository, authorize
  a production host, or create an MCP write path.

## Drift prevention

- The JSON schema and strict typed parser reject unknown, missing, malformed,
  or ambiguously typed fields.
- Tests prove known-bad profiles fail for wrong Git identity, missing sources,
  wrong Claude import direction, missing structural markers, instruction-budget
  overflow, managed-file drift, literal secret patterns, open managed-rollout
  blockers, and production endpoint classes.
- Deployment tests prove invalid principals/classes/default permissions fail,
  unlisted endpoint IDs cannot claim activation, production endpoint enrollment
  is unrepresentable, staged hashes match bytes, literal secrets are absent,
  repeated staging is idempotent, conflicting artifacts are preserved and
  refused, symlink escapes cause no partial write, reconciliation distinguishes
  matching/missing/drifted artifacts and credential-environment presence,
  activation backs up and migrates exact files, partial failures roll back, and
  rollback refuses post-activation drift without partial change.
- CI runs the full unit suite, ADR validation, and
  `python3 -m agent_control verify` against the checked-in pilot profile.
- The profile points to this record and declares its status. A mismatch between
  `Proposed`/`Accepted` in Git and the profile fails.
- Managed projections are compared byte-for-byte with their templates. Validate
  mode never claims that an existing file was generated.
- A repository is not enrolled by appearing in Knowledge, an Issue, a local
  clone, or a fleet inventory. Its canonical default branch must carry a
  reviewed profile.
- Adding any endpoint ID, moving organization-wide rollout from `pilot` to
  `managed`, admitting a production endpoint, or retiring the old guidance
  writer requires a reviewed change and the applicable accepted decision.
