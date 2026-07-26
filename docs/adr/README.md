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

And at most one value for:

- `Effective` — the date an `Accepted` record takes effect, when that differs
  from its decision date.
- `Amends` — see below.
- `Supersedes` — see below.

Controlled metadata is the bulleted block **before the first `##` section**. A
bulleted line inside a section is prose, not a field. A field name outside the
known set fails validation, so a typo cannot silently disable the control it
was meant to declare.

`Proposed` records may name the intended approver, but that name is not an
approval. Approval is a separate human act recorded by the review process.

## Relationships

A decision that changes an earlier decision must say so in a field, not only in
prose. Prose cannot be validated, and an unvalidated relationship is exactly the
drift this discipline exists to catch.

| Field | Form | Meaning |
| --- | --- | --- |
| `Amends` | `NNNN — what it changes` | The earlier record stays in force; a named part of it changes. |
| `Supersedes` | `NNNN` | The earlier record is replaced in full and retired. |

Choose deliberately. Amendment keeps controls that are still load-bearing;
supersession discards them. Recording a narrowing as a supersession quietly
retires every control the earlier record carried.

An amendment must name the part it changes. A bare number is rejected, because
an amendment that does not say what it narrows is indistinguishable from a
supersession.

**Supersession is declared by both records.** `0007` carries
`Supersedes: 0003`, and `0003` carries `Status: Superseded by 0007`. CI rejects
a half-declared pair in either direction, a mismatched pair, a relationship
pointing at a record that does not exist, and a record pointing at itself.
Amendment is one-directional: the amended record is unchanged, which is the
point.

## Template

```markdown
# NNNN. Title

- Status: Proposed
- Date: YYYY-MM-DD
- Owner: Named human
- Approver: Named human (intended while Proposed)
- Scope: Affected organization, repositories, or services
- Classification: Public | Internal | Confidential | Restricted
- Amends: NNNN — the part of that record this one changes (optional)
- Supersedes: NNNN (optional; requires the back-reference above)

## Context
## Decision
## Consequences
## Drift prevention
```

`Drift prevention` is required, not optional: a decision with no mechanism to
detect divergence is a preference, not a decision.
