# Architecture decision records

An ADR records a decision that is expensive to reverse: an ownership boundary, a
control interpretation, an authority assignment, a cutover plan.

## Numbering

ADRs are numbered `NNNN-kebab-case-title.md`, zero-padded to four digits, and a
number is **permanent once merged**.

Two branches can each pick the next free number and both be correct at the time
they branch. This is not hypothetical: `dotmac_sub` merged two ADR 0004s in
July 2026 (`0004-automated-outage-notification-dispatch` and
`0004-external-connector-runtime`) and needed a follow-up PR to renumber one.
The rule that resolves it:

- The ADR that **merges first** keeps the number.
- The loser renumbers, and rewrites every in-code reference to it — scoped by
  *what the reference points at*, not by which files the PR happened to touch.
  A file can carry another ADR's reference.

CI enforces prefix uniqueness so the collision fails at merge time rather than
being noticed by a human afterwards.

## Status

Every ADR carries exactly one:

| Status | Meaning |
| --- | --- |
| `Proposed` | Drafted, not approved. Not normative. |
| `Accepted` | Approved by a named human. Normative. |
| `Superseded by NNNN` | Replaced. Kept for history. |
| `Rejected` | Considered and declined. Kept for the reasoning. |

An ADR authored by an agent is `Proposed` until a named human approver moves it
to `Accepted` through an attributable approval event. See
[AGENTS.md](../../AGENTS.md).

## Controlled metadata

Every ADR has exactly one value for:

- `Status`
- `Date`
- `Owner`
- `Approver`
- `Scope`
- `Classification`

`Proposed` records may name the intended approver, but that name is not an
approval. Approval is a separate human act recorded by the review process.

## Template

```markdown
# NNNN. Title

- Status: Proposed
- Date: YYYY-MM-DD
- Owner: Named human
- Approver: Named human (intended while Proposed)
- Scope: Affected organization, repositories, or services
- Classification: Public | Internal | Confidential | Restricted

## Context
## Decision
## Consequences
## Drift prevention
```

`Drift prevention` is required, not optional: a decision with no mechanism to
detect divergence is a preference, not a decision.
