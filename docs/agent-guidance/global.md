# Global preferences — Michael

Michael runs Dotmac, an ISP operating AS328160 in Abuja and Lagos.

## Working agreements

- Branch before committing. Never commit directly to `main`.
- Commit, push, open or merge pull requests only when Michael asks.
- Merge only when the required CI checks are actually green.
- Keep changes and pull requests small, focused, and reviewable.
- When a repository requires it, add the appropriate `version:patch`,
  `version:minor`, or `version:major` label.
- Before pushing, run the repository's prescribed formatters, linters, type
  checks and record validators. Acceptance tests are owned by CI: do not run
  them locally, and never start a service, container or daemon to make one
  runnable. A local pass is diagnostic context, never evidence.
- Use immutable, fully typed contracts at every changed implementation and
  process boundary.
- Be direct: make a recommendation instead of presenting an unranked survey of
  options.
- Report failures honestly and include the relevant output.
- For production deployment or SSH work, Michael must name the target host
  explicitly. Never infer a production target.

## Sources of truth

- Treat checked-in requirements, schemas, API contracts, architecture
  decisions, and repository `AGENTS.md` files as authoritative for their scope.
- If authoritative sources conflict, report the conflict instead of guessing.
- Update the relevant source-of-truth documentation in the same change when
  behavior or contracts change.
- Durable memory is supporting context, not a replacement for checked-in
  project documentation.

## Secrets — hard rule

- Never put keys, passwords, tokens, or secret values in Git-tracked or
  synchronized files, prompts, reports, commits, pull requests, logs, or
  durable memories.
- Record only the secret's OpenBao path or approved local pointer.
- Never print secret values while retrieving or configuring them.

## Durable knowledge

Cross-machine knowledge lives in the `knowledge` MCP server at
`observability.dotmac.io/knowledge`.

- Before substantial work, use `memory_search` and `memory_get` to retrieve
  relevant global and project knowledge. Do not assume Claude's session-start
  index hook ran in Codex.
- Save genuinely durable facts with `memory_write`, upserting by a stable slug.
- Use scope `global` for Michael's preferences and recurring feedback.
- Use scope `project:<repository-directory-name>` for project-specific facts.
- Keep the one-line `description` useful because it is shown in future indexes.
- Never store credentials in memory. Store an OpenBao pointer instead.
- Do not create per-project memory files as a substitute for the Knowledge MCP.

## Agent orchestration and model routing

- One primary agent owns planning, decision integration, user communication and
  final acceptance. Worker reports are advisory evidence; they never become an
  approval, compliance attestation or risk acceptance.
- Use a star topology with the primary plus one worker by default. Add another
  worker only for a genuinely independent path or a required independent
  review. Parallelism is an elapsed-time tradeoff, not the default cost posture.
- Delegate the cheapest reliable bounded slice. Codex uses Sol/high as primary,
  Luna for Knowledge, Fleet, exploration, CI observation and clear execution,
  Terra for complex implementation or high-risk review, and Astra only for an
  exceptional hard analysis. Claude uses Sonnet as primary, Haiku for bounded
  reads and observation, Opus for complex analysis, and Fable only for the
  hardest long-running investigation or when Michael explicitly requests it.
- A task packet names the outcome, repository and worktree, starting revision,
  owned and read-only paths, permitted validation, authority limits and stop
  conditions. Spawn with no inherited conversation or the smallest useful
  recent context. Give corrections to the same worker before escalating.
- One writer owns each worktree and shared path. An agent that encounters
  another writer's change stops and reports it rather than resolving the
  ownership conflict silently.
- Knowledge and Fleet readers are read-only, tool-allowlisted and result-bounded.
  Fleet inventory never grants SSH. The primary owns every Knowledge write.
- Do not expose databases or observability backends through raw SQL, ORM, shell,
  SSH, credentials, unrestricted HTTP or unbounded logs. A cheap reader is
  admissible only after the owning application provides bounded, paginated,
  redacted, audited and rate-limited read operations with server-side identity,
  scope, timeout and write denial.
- The primary reads and interprets every applicable skill. It may delegate only
  a bounded mechanical slice the skill permits. Secret retrieval, SSH,
  migrations, authorization and production workflows remain primary-owned and
  keep their existing human authority requirements.
- Cross-model delegation is one hop and primary-originated. It carries an exact
  task and repository/revision identity, read/write mode, path ownership,
  deadline, output bound, cost ceiling and stop conditions. A child cannot call
  another bridge, acquire more authority or start an automatic review/fix loop.
- Workers receive no secret, SSH, production, commit, push, pull-request, merge,
  release, deployment, approval, compliance-attestation or risk-acceptance
  authority unless Michael grants that exact action and the repository permits
  it. Git and release authority never follows from model strength.

## Dotmac source-of-truth standard

The source-of-truth architecture established in `dotmac_sub` is the default
standard for Dotmac systems. Its reference map is
`dotmac_sub/docs/SOT_RELATIONSHIP_MAP.md`.

- Give every business decision and state transition one named owning service or
  system.
- Keep routes, web handlers, jobs, webhooks, commands, and delivery integrations
  as thin adapters around the owner.
- Separate observations from decisions and consequences: collectors/importers
  write facts, resolvers derive state, policy/event services decide
  consequences, and reconcilers project the result.
- Give each derived field, cache, external projection, and side effect one
  canonical writer. Other callers change source state or request
  reconciliation; they do not maintain parallel decision paths.
- Treat external collaboration and delivery systems as transports, not decision
  systems. For operational customer, subscriber, ticket, work-order, outage,
  device, service, ownership, escalation, and official-timeline state, Sub is
  authoritative unless an approved contract explicitly assigns another owner.
- Make reconcilers idempotent and able to repair drift from authoritative
  inputs. Do not let a cache or imported identifier become the only copy of
  truth.
- Migrate authority explicitly: document the old owner, new owner,
  shadow/verification phase, cutover gate, fallback retirement, and tests
  proving the boundary.
- Finish one coherent domain slice per change: name the owner, migrate the
  highest-risk callers, remove or gate parallel paths, and add focused
  architecture and behavior tests.
- Apply these principles across Dotmac repositories. Reuse the pattern, not
  domain-specific implementation details.
- A deviation requires an explicit architecture decision recording the
  alternative owner, rationale, migration/cutover implications, and how drift
  is prevented.

## Cross-cutting issue extraction and preservation

Before completing substantial analysis, implementation, debugging, incident,
review, or planning work, run a durability scan.

Preserve a finding when any of these is true:

- Michael states a rule using language such as "standard", "always", "never",
  "across projects", or "source of truth".
- It affects two or more repositories, services, domains, teams, integrations,
  or operational workflows.
- It identifies or changes an ownership boundary, source-of-truth rule, control
  plane, security invariant, operational invariant, or customer-impact policy.
- It explains a recurring failure, incident class, drift mechanism, or review
  correction likely to recur.
- It is an unresolved cross-cutting risk or follow-up that could be lost when
  the current task ends.

For each candidate:

1. Classify it as an approved standard/decision, confirmed reusable fact,
   recurring preference/feedback, or unresolved candidate.
2. Search existing memory first and update the canonical entry instead of
   creating a duplicate.
3. Use a stable slug and the narrowest correct scope. Cross-Dotmac standards use
   `global`; implementation details use
   `project:<repository-directory-name>`.
4. Record status, owner/system of record, affected scope, evidence or source
   paths, decision/rationale, and next action when relevant.
5. Put normative project rules in the checked-in source-of-truth document or
   agent-guidance file as well as memory. Memory aids discovery; it does not
   replace enforcement or versioned documentation.
6. Do not silently promote an inference into a standard. Surface it to Michael
   as a candidate; preserve it as unresolved only when losing it would be
   costly.
7. In the final response, report what durable knowledge was created or updated
   and list any cross-cutting candidates still needing a decision.

If the Knowledge MCP is unavailable, explicitly report the pending durability
items so they can be written later. Do not create ad hoc memory files.
