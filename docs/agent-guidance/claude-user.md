# Claude-specific additions

- Never add `Co-Authored-By`, `Assisted-By`, `Generated-By`, model attribution or
  another AI authorship trailer to a commit. Author and committer remain
  accountable human identities. Pull-request bodies may retain the Claude Code
  trailer.
- Keep shared Dotmac guidance in the managed system `CLAUDE.md`; do not duplicate
  it in this user-specific file.
- Use Sonnet for the primary orchestrator and normal implementation, Haiku for
  bounded Knowledge, Fleet, repository and CI reads, Opus for complex analysis,
  and Fable only after Opus is insufficient or Michael explicitly requests it.
- The compact session-start Knowledge index is discovery context. Use the Haiku
  Knowledge reader to fetch only relevant full records; the primary alone may
  write durable memory.
- Use OpenAI's `codex@openai-codex` Claude Code plugin for Claude-to-Codex review
  and handoff. Keep its stop-time review gate disabled. Do not invoke its rescue
  agent proactively: the primary may start one bounded Codex review, or a write
  rescue only after Michael's task authorizes edits and assigns non-overlapping
  paths. A Codex child may not call Claude or another bridge.
- Treat `/codex:review` and `/codex:adversarial-review` as advisory read-only
  review. `/codex:rescue` is a distinct implementation handoff, not approval or
  an automatic fix loop. Record the plugin version and source revision when it
  changes.
