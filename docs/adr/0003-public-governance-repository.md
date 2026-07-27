# 0003. Public governance repository with enforced branch protection

- Status: Proposed
- Date: 2026-07-27
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: `https://github.com/michaelayoade/dotmac_governance`
- Classification: Public
- Amends: 0001 — the private-visibility rule, the record classification it implied, and the branch-protection enforcement gap

## Context

ADR 0001 records that the GitHub plan in use could not enforce branch
protection on a private repository; the attempt returned HTTP 403. Rule 4 —
every substantive change arrives as a pull request with a named human approver
— was therefore honour-system, and under ADR 0002 every adopted process gate
rests on it.

This decision has been revisited twice, and the reasoning of both earlier
positions is retained rather than discarded.

The repository was published on 2026-07-26 to obtain branch protection, and
that action was taken while the authorizing record was still `Proposed`. That
sequencing was wrong independently of the destination, and is recorded in
[issue #3](https://github.com/michaelayoade/dotmac_governance/issues/3). A
subsequent draft proposed restoring private and paying for the capability. This
ADR supersedes that draft's conclusion but not its analysis: the three
objections it raised were correct, and two of them are resolved here by
changing the configuration rather than by argument.

**Objection 1 — a self-hosted runner on a public repository.** Correct, and
GitHub's own guidance says so: once a fork's workflow run is approved,
user-controlled code executes on the runner host. It is resolved by removing
the self-hosted runner. Seabone existed only because hosted Actions were
unavailable on the *private* repository. A public repository gets hosted
runners at no cost, so the condition that created the exposure disappears
rather than being mitigated. There is no runner host to reach, no approval
policy to maintain, and no workflow guard whose assurance has to be qualified.

**Objection 2 — publishing `Classification: Internal` records makes the label
meaningless.** Correct, and it is resolved by classification, not by
redefinition. Records in this repository are classified `Public`. Anything that
must carry `Internal`, `Confidential`, or `Restricted` does not belong here and
is referenced from the system that holds it. This is a real admission control
with a real consequence, and it is the opposite of widening `Internal` to cover
what was already done.

**Objection 3 — an accepted rule was departed from on the authority of a
proposed one.** Correct, and not resolved by this ADR's conclusion. It is a
process failure, it is recorded as an incident, and its corrective actions
stand regardless of which visibility is chosen.

What remains is a genuine trade. Publishing makes Dotmac's governance gaps
readable by anyone. That is accepted deliberately: a governance repository that
could not survive being read is not recording its gaps truthfully, and every
open gap here is already written down as an open decision or an incident.

## Decision

`dotmac_governance` is a **public** repository with **enforced** branch
protection on `main`.

### Visibility

ADR 0001 hard rule 5 is amended. Its protected interest was never visibility
itself; it was that governance material not leak secrets, ISO text, or
confidential operational detail. Those are preserved as content rules:

- Secret values never appear here, in any form — only an approved OpenBao path
  or a controlled local pointer. Unchanged and absolute.
- ISO standard text is never reproduced. Unchanged and absolute.
- Records here are classified `Public`. Material requiring `Internal` or above
  is referenced, not stored.
- Hosted-CI availability remains an invalid reason to change visibility. That
  clause of rule 5 stands; this ADR does not appeal to it, and the reason here
  is enforceability plus the removal of the self-hosted runner.

Existing records carry `Classification: Internal`, which was never accurate for
a public repository. This ADR authorizes correcting that field on ADR 0001 and
ADR 0002 to `Public`. The correction changes a label to match reality and
changes no decision; it is recorded here rather than made silently.

### Validation runtime

Validation runs on GitHub-hosted runners. The Seabone self-hosted runner is
retired for this repository and must not be reintroduced while it is public.

This is a downgrade in one respect worth stating: the private runner was a
controlled host, and hosted runners are shared infrastructure. For a repository
whose entire content is public and which holds no secrets, that trade is
acceptable. It would not be for a repository that holds either.

### Branch protection

Protected `main` requires a pull request and the `Governance record validation`
check, applies to administrators, and forbids force pushes, deletions, and
non-linear history.

### Approval strength is bounded by identity, not by protection

Protected `main` enforces *pull request and green check*. It does not enforce
*independent human approval*, because `required_approving_review_count` is `0`.

GitHub does not permit an author to approve their own pull request, and every
change — human-written or agent-drafted — currently arrives under Michael's
account. Requiring one approval would make merging impossible rather than
safer. Raising the count is gated on open decision 5 giving agents a distinct
identity.

Until then, rule 4's named-approver requirement is honestly stated as a
pull-request-and-green-CI gate. Recording it as an approval gate would overstate
the control.

Public visibility introduces a second consideration for that decision: outside
contributors can now open pull requests. They cannot merge, because protection
requires the check and the repository has one maintainer, but the review burden
is real and is accepted.

## Consequences

- Branch protection is enforceable at no subscription cost, closing the gap
  recorded in ADR 0001 and open decision 7.
- The self-hosted runner exposure is removed rather than mitigated. Open
  decision 12 closes, and the fork-approval policy and workflow guard both
  become unnecessary.
- Dotmac's governance gaps, incidents, and unresolved decisions are publicly
  readable. Accepted.
- `Classification` becomes admission control for this repository: a record that
  needs `Internal` or above forces a location decision instead of defaulting
  here.
- Seabone's runner registration for this repository should be removed rather
  than left idle, so that a future workflow cannot select it by accident.
- Anyone may open a pull request or an issue. Triage is unowned and will need
  an owner if volume appears.
- Visibility is a governed property. Changing it again requires an approved
  ADR, not a settings change.

## Drift prevention

- Protected `main` is verified by API and the verified configuration recorded
  in the pull request. Verified 2026-07-26: required check `Governance record
  validation`, strict, `enforce_admins` enabled, linear history, no force
  pushes, no deletions.
- The workflow declares `runs-on: ubuntu-latest` with a comment stating why.
  Reintroducing a self-hosted runner requires a reviewed change to that file
  and contradicts this ADR on its face.
- Secret scanning and push protection are enabled, so the secrets rule has a
  mechanism behind it rather than only a prohibition.
- A record carrying `Internal` or above in this repository is a classification
  error. This is a candidate control for the record validators once the
  classification vocabulary is fixed.
- Every settings change is verified by reading the setting back. The failed
  publication sequence proceeded because an HTTP 422 was not checked before the
  next step ran; a call that is not read back is not a control.
- An accepted ADR is not departed from on the authority of a `Proposed` one.
  Where a proposal conflicts with an accepted rule, the conflict is resolved by
  approval or withdrawal before any action is taken.
