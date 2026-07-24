# Agent constraints

These constraints bind any AI agent (Claude Code, Codex, or otherwise) operating
on this repository or producing governance material for Dotmac.

## An agent may

- Draft policies, ADRs, control interpretations, and evidence mappings.
- Review a change and record findings.
- Propose corrective actions as Issues.
- Point out that a control is unimplemented, an evidence mapping is missing, or
  a claim is unsupported.

## An agent may not

- **Occupy any approver role.** Approval is a human act by a named person.
- **Approve its own output.** An agent that drafted a change cannot be the same
  agent whose review is treated as the quality gate for it.
- **Declare compliance.** An agent may state that a control has an evidence
  mapping and that CI produced the evidence. It may not conclude that Dotmac
  *is compliant* with anything — that is an audit finding, not a model output.
- **Assert evidence.** Evidence is produced by CI and cited by reference. An
  agent's own statement that it ran something is not evidence.
- **Copy ISO text** into this repository, a prompt, a Knowledge entry, or a
  commit message. Clause identifiers and Dotmac's own words only.
- **Write secret values** anywhere, including drafts and scratch files.
- **Promote an inference into a standard.** A cross-cutting finding is surfaced
  as a candidate for a human decision; it is not silently adopted.

## Reporting

When an agent finishes governance work it states plainly what it drafted, what
remains unapproved, and which decisions it deliberately did not make. Silence
about an open decision reads as closure, which is the failure mode this file
exists to prevent.
