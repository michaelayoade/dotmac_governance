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

This is a condition of the change, not a follow-up. Before or at the moment of
publication, Actions must require approval for **all** outside contributors,
not first-time contributors only. If that control cannot be set, the repository
does not become public.

## Consequences

- Branch protection becomes technically enforceable, closing the enforcement
  gap recorded in ADR 0001 and open decision 7, and giving ADR 0002's process
  gates something real to rest on.
- Dotmac's governance gaps become public. Accepted.
- The Seabone runner moves from a private trust boundary to a public one, and
  depends on an Actions approval policy that must be verified rather than
  assumed.
- Any future record needing `Confidential` or `Restricted` classification
  forces a location decision instead of defaulting here.
- The 2026-07-24 reversal is not undone. Its reasoning — that CI availability
  does not justify publication — remains correct and is preserved above.
- Visibility becomes a governed property. Changing it back requires an ADR, not
  a settings click.

## Drift prevention

- Branch protection on `main` is verified by API after the change and its
  configuration recorded in the pull request. A 403 or a missing required check
  is a failed change, not a partial success.
- The Actions fork-approval policy is verified as requiring approval for all
  outside contributors. This is checked at publication and re-checked whenever
  workflow configuration changes.
- `README.md` hard rule 5 is rewritten in the same change as this ADR, so the
  front page cannot state a visibility rule the repository contradicts.
- A record carrying `Confidential` or `Restricted` in a public repository is a
  classification error. This is a candidate control for the ADR validator once
  the classification vocabulary is fixed.
- Secret scanning and push protection are enabled, so the secrets rule has a
  mechanism behind it rather than only a prohibition.
