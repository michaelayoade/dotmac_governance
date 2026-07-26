# 0003. Private governance repository with enforced branch protection

- Status: Proposed
- Date: 2026-07-26
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: `https://github.com/michaelayoade/dotmac_governance`
- Classification: Internal
- Amends: 0001 — the branch-protection enforcement gap

## Context

ADR 0001 records that the GitHub plan in use could not enforce branch
protection on a private repository; the attempt returned HTTP 403. Rule 4 —
every substantive change arrives as a pull request with a named human approver
— was therefore honour-system, and under ADR 0002 every adopted process gate
rests on it.

An earlier draft of this ADR proposed closing that gap by publishing the
repository, on the reasoning that public repositories get protected branches at
no cost. That was the wrong trade, and it was acted on before it was approved.
The correct resolution is to pay for the capability on a private repository.

The reasons the published form fails:

- **It conflicts with accepted ADR 0001.** Private-by-default is an accepted
  rule. A `Proposed` record cannot authorize departing from an accepted one,
  and documentation was being reshaped to match a setting that had already been
  mutated. That is the inversion this repository exists to prevent.
- **Classification becomes decorative.** Every record here is classified
  `Internal`. Publishing them means either the vocabulary permits publishing
  `Internal` material — which makes the label meaningless — or the label was
  ignored. Redefining `Internal` to accommodate the action taken would be
  misleading, not a narrowing.
- **Self-hosted runners and public repositories are not a supported
  combination.** GitHub's own guidance is to use self-hosted runners only with
  private repositories, because once a fork's workflow run is approved,
  user-controlled code executes on the runner host. Approval gating reduces the
  chance of that happening; it does not change what happens when it does.
- **The cost argument was weak.** GitHub Pro provides branch protection on
  private repositories for a personal account. Trading the confidentiality
  boundary and the runner's trust boundary to avoid a subscription is not a
  defensible exchange.

## Decision

`dotmac_governance` is a **private** repository with **enforced** branch
protection on `main`.

- The personal GitHub account is upgraded to Pro, which provides protected
  branches on private repositories.
- Protected `main` requires a pull request and the `Governance record
  validation` check, applies to administrators, and forbids force pushes,
  deletions, and non-linear history.
- ADR 0001 hard rule 5 is **unchanged**. Private means private. This ADR
  amends only the enforcement gap ADR 0001 recorded in its consequences — it
  does not touch visibility, and it does not redefine `Classification`.
- The Seabone self-hosted runner remains the validation runtime, which is a
  supported configuration for a private repository and is not one for a public
  one.

### Approval strength is bounded by identity, not by protection

Protected `main` enforces *pull request and green check*. It does not enforce
*independent human approval*, because `required_approving_review_count` is `0`.

GitHub does not permit an author to approve their own pull request, and every
change — human-written or agent-drafted — currently arrives under Michael's
account. Requiring one approval would make merging impossible rather than
safer. Raising the count is therefore not a configuration choice; it is gated
on open decision 5 giving agents a distinct identity.

Until then, rule 4's named-approver requirement is honestly stated as a
pull-request-and-green-CI gate. Recording it as an approval gate would
overstate the control.

### Temporary publication

The repository was public on 2026-07-26 until its restoration to private. That
event, its failed sequencing, its verified impact, and its corrective actions
are recorded in [issue #3](https://github.com/michaelayoade/dotmac_governance/issues/3).
ADR 0001 assigns nonconformities and corrective actions to Issues; they are not
architecture and do not belong in this record beyond this reference.

## Consequences

- A paid GitHub subscription becomes a dependency of the governance control
  model. If it lapses, branch protection on a private repository lapses with
  it, and the enforcement gap returns. This is a recurring cost with a control
  attached, not a convenience.
- The confidentiality boundary and the runner's trust boundary are both
  restored to the state ADR 0001 assumed.
- `Classification: Internal` retains its ordinary meaning. No record here
  needed a redefinition to remain accurate.
- Open decision 12 — self-hosted runner exposure on a public repository —
  ceases to exist rather than being mitigated, because the condition that
  created it is removed.
- Open decision 7 closes once Pro is active and protection is verified by API
  on the private repository. It does not close on the strength of protection
  configured while the repository was public.
- The order of operations matters and is a condition of this decision: Pro must
  be active **before** visibility is restored. Restoring private on a plan
  without protected branches drops the rules, reopening the gap this ADR
  exists to close.

## Drift prevention

- Protected `main` is verified by API **after** the visibility change, on the
  private repository, and the verified configuration is recorded in the pull
  request. Protection verified while public does not evidence protection while
  private.
- Every settings change is verified by reading the setting back. The failed
  publication sequence proceeded because an HTTP 422 was not checked before the
  next step ran; a call that is not read back is not a control.
- Repository visibility is a governed property. Changing it requires an
  approved ADR, not a settings change followed by a record written to match.
- An accepted ADR is not departed from on the authority of a `Proposed` one.
  Where a proposal conflicts with an accepted rule, the conflict is resolved by
  approval or withdrawal before any action is taken.
- Subscription lapse is a control failure. The renewal is owned rather than
  assumed, and the loss of protection is detectable by the same API check that
  verifies it.
