# 0020. Commits carry an accountable human identity

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Every governance-enrolled Dotmac repository, and any repository an agent commits to on Michael's behalf
- Classification: Internal

## Context

A commit's `author` and `committer` are the repository's record of who did the
work. A model is not a *who*. It holds no account, cannot be asked what it
intended, and cannot be the person an approver is attesting against — which
`AGENTS.md` requires of every change and the pull request template restates on
its last line.

`AGENTS.md` already says an agent may not occupy an approver role and may not
approve its own output. An AI identity in the author or committer field defeats
both without touching either rule: the change arrives already signed by
something that cannot be held to them.

### The motivating evidence

On 2026-08-29 a local `user.email` override of `noreply@anthropic.com` in one
clone was found to be stamping that address onto commits. The override has been
removed.

The estate it left is larger than the discovery suggested, and the difference
matters to what this record can honestly decide. Observed in `dotmac_sub` at
commit `d5ed100404cbcb01d500b3d8951814673708c7ee` on 2026-08-30, read from a
local clone's `origin/main`:

| Measure | Count |
| --- | --- |
| Commits reachable from that revision | 5217 |
| …whose **author** email is `noreply@anthropic.com` | 1161 |
| …whose **committer** email is `noreply@anthropic.com` | 1143 |
| …carrying a `Co-Authored-By:` trailer | 4624 |
| Author-email date range | 2026-04-17 to 2026-08-29 |

This is an **as-of observation** under ADR 0013 § 4, not a standing claim. The
commit is immutable so the counts are re-derivable, but that revision was the
tip of a clone's remote-tracking branch on the observation date and may not be
the current tip. **Refresh responsibility:** whoever proposes a remediation of
`dotmac_sub`'s history re-observes against the canonical `main` at that time;
the counts above may not be used to size that work later without re-reading.

Three things follow, and they shape the decision rather than decorating it.

**It was never a one-day event.** The reported nine commits dated 2026-08-29
were the ones a reader happened to see. A misconfigured clone stamps every
commit it makes, in every repository it touches, until somebody reads a `git log`
carefully — and nothing in the ordinary review path shows it. The diff is right,
the message is right, CI is green, and the author line is the one field a
reviewer never checks. That is why the control has to be a gate and not a
practice.

**The author and committer fields diverge.** 1161 and 1143 are different
numbers, and some commits carry an Anthropic author with a *different human* as
committer. A rebase, a cherry-pick or a squash rewrites the committer and
preserves the author; the reverse happens too. A guard that checked one field
would miss roughly half of the ways the identity arrives.

**History cannot be repaired by a gate.** 1161 commits are on a shared `main`.
Rewriting them changes every downstream hash and is a far larger hazard than the
wrong author line. A gate over history would be permanently red, and a
permanently red gate is switched off — which is a worse outcome than no gate,
because the repository would then have a control it believes in and does not
have.

## Decision

### 1. A commit carries an accountable human identity

The `author` and `committer` of every commit name a person with an account.
Neither may name a model, a model vendor, or an assistant product — in the
display name or in the email address.

### 2. No AI attribution trailer, in any form

A commit message carries no `Co-Authored-By`, `Assisted-By`, `Generated-By`,
`AI-Assisted`, `Claude-Session` or equivalent trailer, and no prose attribution
such as a generated footer.

`Co-Authored-By` is refused **in full**, not only when its value names a model.
That is Michael's standing rule, and it is also the only version that can be
enforced: a co-author line is free text, so a check on whether the value named a
model would be a check on how the value was spelled. A genuine second human
author is recorded in the pull request, where it is attributable to an account.

Prose attribution is refused separately from trailers because it carries no
colon. A guard that parsed only trailers would pass the single most common
generated footer there is.

### 3. The gate's scope is the branch's own commits, and it says so

`tools/check_commit_identity.py` reads `head --not base` — the commits the branch
adds — and nothing else. The property it claims is **"nothing new arrives
wrong"**. It does not claim the history is clean, and it must never be cited as
though it did.

### 4. An unestablishable range FAILS

If the base or head ref is missing, is the all-zero SHA, does not resolve in the
checkout, or the commit list cannot be read, the gate **errors**. Not warns, not
skips.

This is the part most likely to be got wrong, and it is worth naming why. Every
convenient failure mode — an empty range, an unresolved ref, a shallow clone —
reads naturally as "nothing to check" and therefore as green. A guard that goes
green when it cannot determine what to inspect is worse than no guard, because
it reports a colour it did not earn, and it does so exactly when something is
unusual, which is when it is most needed.

Both endpoints are therefore passed to the gate **explicitly** by the workflow
rather than inferred. On a pull request the checkout is the merge commit, so
"HEAD's parent" is ambiguous, and a guard that guesses its own baseline is a
guard whose baseline nobody reviewed. The workflow also checks out full history,
because a shallow clone is the ordinary way the base becomes unreachable.

### 5. An unrecognised argument is refused, not ignored

The gate accepts `--base` and `--head` and nothing else. A stray token, a flag
with no value, or a flag given another flag as its value is an error.

This is the same fail-closed rule as § 4 applied one level up, and it is in this
record because the first CI wiring of the gate demonstrated why. The arguments
were wrapped across lines in a YAML **folded** scalar, which does not fold a
more-indented line; `--head` became a separate shell command and never reached
the tool. The step reported `executed_passed` for the half that ran, against a
default head, over the wrong range. A tolerant parser is what let a broken
invocation report success — the guard's own failure mode arriving in the guard's
own wiring.

### 6. An established but empty range is `not_applicable`

Distinct from § 4 and distinct from a pass. "There were no commits to check" and
"the commits checked were clean" are different facts, and reporting the first as
the second is the same defect as reporting an unestablishable range as green.

### 7. What this record does not do

It adds **no typed representation** to `standards-profile.schema.json` and no
`standards_control` rule, so the Governance engine reports no conformance result
for it. Propagating the gate to the other enrolled repositories, and whether it
becomes a profile-declared standard rather than a per-repository workflow step,
is recorded as an open decision rather than assumed.

It also decides nothing about remediating `dotmac_sub`'s existing history. That
is a separate change with its own risk assessment, and § 3 exists precisely so
that this gate can land without waiting for it.

## Consequences

- A misconfigured clone is caught on the first pull request it opens here,
  rather than after a thousand commits.
- The gate is only as good as its denylist, and a denylist is a ratchet: a new
  vendor address or product name is invisible until somebody adds it. Stated
  rather than glossed — this control reduces a recurring accident, it does not
  prove the absence of AI authorship.
- A contributor who legitimately wants to credit a second human is pushed to the
  pull request, which is the attributable place for it. That is a deliberate
  narrowing of `Co-Authored-By`, not an oversight.
- Enrolled repositories other than this one remain unguarded until the open
  decision is taken. Naming that is the point; an unchecked repository is an
  unmonitored region, never "covered by the standard".
- `dotmac_sub`'s existing 1161 commits stay as they are. The record of what
  happened is preserved, which is worth something on its own.

## Drift prevention

`tools/check_commit_identity.py` enforces §§ 1–6 in
`.github/workflows/governance-checks.yml`, on both `pull_request` and `push`.

`tests/test_check_commit_identity.py` **constructs** each prohibited shape as a
real commit in a throwaway repository and observes the guard firing on it,
rather than asserting that this repository's own commits are currently clean:

- the incident shape — `noreply@anthropic.com` — on the **author**, and again on
  the **committer**, separately, because the two fields diverge;
- a vendor subdomain, an assistant forge account, and a model display name;
- `Co-Authored-By` naming a model, `Co-Authored-By` naming a second human (both
  refused), a lowercase trailer key, `Claude-Session`, `Assisted-By`;
- a generated footer carrying no colon, which the trailer scan cannot see;
- a prohibited commit already on the base branch, which must **not** fire —
  the scope limit in § 3 is a tested property, not a comment;
- **the unestablishable-range cases**: an empty base, an unresolvable base, an
  unresolvable head, the all-zero SHA, a directory that is not a repository, and
  the library call raising rather than returning an empty list;
- an established-but-empty range reporting `not_applicable` and **not**
  `executed_passed`;
- **an unrecognised argument, a stray shell fragment, a flag with no value and a
  flag given another flag** — the § 5 cases, which exist because the gate's own
  first CI wiring went green on a half-delivered invocation.

Two sensitivity proofs guard against the guard being too eager, which is the
failure that gets a control switched off: `GitHub <noreply@github.com>` — the
committer of every squash merge — must pass, and a person named `Claudia` must
pass. The name patterns are word-bounded for that reason.

The command is declared `local` in `.dotmac/validation-contract.json`, which
binds `AGENTS.md`'s documented list, the agent profile's `validation_commands`
and the workflow together: `tools/check_validation_contract.py` fails if any of
them moves without the others, so this gate cannot be quietly dropped from CI
while remaining in the instructions, or the reverse.
