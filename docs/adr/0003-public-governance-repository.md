# 0003. Public governance repository and enforced branch protection

- Status: Proposed
- Date: 2026-07-26
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: `https://github.com/michaelayoade/dotmac_governance`
- Classification: Internal
- Amends: 0001 — the private-visibility rule and the branch-protection enforcement gap

## Context

ADR 0001 records that the current GitHub plan cannot enforce branch protection
on a private repository. The attempt returned HTTP 403. Green CI and human
approval therefore operate as a rule with a documented enforcement gap: nothing
technically prevents a direct push to `main`, and `README.md` rule 4 — every
substantive change arrives as a pull request with a named human approver — is
honour-system.

This repository was previously made public as a workaround for unavailable
hosted Actions, and that was reversed on 2026-07-24 because CI availability is
not a reason to publish the governance source of truth. ADR 0001 hard rule 5
states that directly. The replacement control was a repository-scoped Seabone
self-hosted runner, which closed CI availability but not enforcement.

The reason now is different, and the distinction is the whole basis for
revisiting a decision made two days earlier. CI availability is a convenience;
it had an alternative, and the alternative worked. An unenforceable approval
gate is a control failure with no alternative on the current plan. Under
ADR 0002 every adopted process depends on gates at the default branch, so an
unenforced `main` degrades not one rule but the entire development model.

Four of the six repositories in ADR 0002's governed scope — `dotmac_sub`,
`dotmac_crm`, `dotmac_erp`, and `dotmac-integration-client` — are already
public. Governance being private is not a consistent boundary; it is one repo
treated differently from the systems it governs.

Michael directed this change on 2026-07-26.

## Decision

`dotmac_governance` becomes a public repository, and protected `main` is
configured and verified.

### Hard rule 5 is narrowed, not deleted

The rule was written as a statement about repository visibility. It is replaced
by a statement about content, which is what it was actually protecting:

- Secret values never appear here, in any form. Only an approved OpenBao path
  or a controlled local pointer. Unchanged and absolute.
- ISO standard text is never reproduced. Unchanged and absolute.
- Material classified `Confidential` or `Restricted` does not belong in this
  repository. It is referenced from the controlled system that holds it.
- Hosted-CI availability remains an invalid reason to change visibility. That
  part of rule 5 stands as written; this ADR is not an appeal to it.

`Classification` therefore stops being descriptive metadata and becomes an
admission control. A record that must carry `Confidential` or `Restricted`
belongs somewhere else.

### What becomes publicly readable

This is accepted deliberately, not overlooked. Publishing makes readable: that
Dotmac's approval gates were unenforced until this change; that agents act
through a personal GitHub account and cannot be distinguished from the human;
the `claude_knowledge` deployment defects cited in ADR 0001; the Seabone runner
labels; and every unresolved item in `docs/open-decisions.md`.

Honest records of open gaps are the point of this repository. A governance repo
that could not survive being read is not recording gaps truthfully.

### Self-hosted runner exposure

`governance-checks.yml` triggers on `pull_request` and targets the Seabone
self-hosted runner. On a public repository any GitHub user may fork and open a
pull request, and workflow approval defaults are weaker than this warrants.
Untrusted code executing on a self-hosted runner reaches the host, not a
disposable container.

This is a condition of the change, not a follow-up. Two controls, because the
first cannot be configured before publication — the fork-approval API rejects
the call on a private repository, which leaves a window between the visibility
change and the setting taking effect:

1. **Actions requires approval for all outside contributors**
   (`all_external_contributors`), not the `first_time_contributors` default.
   Set immediately after publication and verified by API. **This is the only
   control that holds against a hostile fork.**
2. **`governance-checks.yml` refuses to run for a pull request whose head
   repository is not this repository.** A job-level condition.

The second control is weaker than it looks, and the difference matters enough
to state precisely. A `pull_request` workflow executes the definition produced
by merging the head into the base, and a fork controls its own head — so a
malicious fork can delete the guard along with everything else it edits. The
guard defends against an accidental fork pull request and against a maintainer
approving a run without reading the diff closely. It does **not** defend against
an attacker who edits the workflow. Calling it a barrier that survives the
Actions setting being changed would be exactly the false assurance this
repository exists to prevent.

The approval policy is therefore not defence in depth behind the guard. It is
the barrier, and it must be re-verified after any change to Actions settings
rather than inferred from the workflow file.

A fork pull request runs no validation and cannot satisfy the required check.
That is intended for a repository where every merge is a governance act.

### What was actually done

Recorded because the intended sequence was not the executed one.

The plan was to disable Actions, change visibility, set the approval policy,
then re-enable. The disable call failed with HTTP 422 — a string where the API
required a boolean — and the failure was not caught before the visibility
change proceeded. The repository was therefore public with Actions enabled and
the approval policy still at the `first_time_contributors` default for the
interval between those two calls.

The exposure was bounded by that default, which requires approval for a
contributor who has not previously contributed, and by the absence of any
attacker with prior contribution history. Verified after the fact: zero forks,
and every workflow run in the repository's history originates from a branch in
this repository. No fork run occurred.

The window was real regardless of the outcome, and the durable correction is
sequencing that does not depend on a call succeeding silently: **verify the
disable took effect before changing visibility.** Recorded here rather than
tidied away, because a governance record that only documents the intended path
is not a record of what happened.

## Consequences

- Branch protection becomes technically enforceable, closing the enforcement
  gap recorded in ADR 0001 and open decision 7, and giving ADR 0002's process
  gates something real to rest on.
- Dotmac's governance gaps become public. Accepted.
- The Seabone runner moves from a private trust boundary to a public one, and
  depends on an Actions approval policy that must be verified rather than
  assumed. The workflow guard does not reduce that dependency.
- Protected `main` requires a pull request and a green check, but
  `required_approving_review_count` is **0**. GitHub does not let an author
  approve their own pull request, and every change — human-written or
  agent-drafted — currently arrives under Michael's account. Requiring one
  approval would make merging impossible rather than safer. The approval count
  rises to 1 when open decision 5 lands and agents hold a distinct identity;
  until then, `README.md` rule 4's named-approver requirement is enforced as a
  pull-request-and-green-CI gate, not as an independent review.
- `enforce_admins` is enabled, so the gate binds Michael too. An emergency
  bypass means deliberately disabling protection, which is itself an auditable
  act rather than a silent direct push.
- Any future record needing `Confidential` or `Restricted` classification
  forces a location decision instead of defaulting here.
- The 2026-07-24 reversal is not undone. Its reasoning — that CI availability
  does not justify publication — remains correct and is preserved above.
- Visibility becomes a governed property. Changing it back requires an ADR, not
  a settings click.

## Drift prevention

- Branch protection on `main` is verified by API after the change and its
  configuration recorded in the pull request. A 403 or a missing required check
  is a failed change, not a partial success. Verified 2026-07-26: required
  check `Governance record validation`, strict, `enforce_admins` enabled,
  linear history, no force pushes, no deletions.
- Any settings change made through the API is verified by reading the setting
  back. The publication sequence failed silently once because a 422 was not
  checked before the next step ran; a call that is not read back is not a
  control.
- The Actions fork-approval policy is verified by API as requiring approval for
  all outside contributors, and the workflow's fork guard is verified present.
  Both are re-checked whenever workflow configuration changes. Neither is
  assumed from the other: the setting can be changed without review, and the
  guard is what makes that survivable.
- `README.md` hard rule 5 is rewritten in the same change as this ADR, so the
  front page cannot state a visibility rule the repository contradicts.
- A record carrying `Confidential` or `Restricted` in a public repository is a
  classification error. This is a candidate control for the ADR validator once
  the classification vocabulary is fixed.
- Secret scanning and push protection are enabled, so the secrets rule has a
  mechanism behind it rather than only a prohibition.
