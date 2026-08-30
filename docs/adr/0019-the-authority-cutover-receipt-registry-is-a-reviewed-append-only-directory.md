# 0019. The authority-cutover receipt registry is a reviewed append-only directory

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: This repository's receipt registry, and every governance-enrolled Dotmac repository whose authority moves
- Classification: Internal
- Amends: 0018 — § 4's statement that the registry directory does not exist and that nothing may be written to it

## Context

[ADR 0018](0018-authority-cutovers-leave-receipts-and-decommissions-retire-delegations.md)
is `Accepted`. Its § 3 assigns the cross-repository authority-cutover receipt
registry to Governance, fixes the envelope's contents, decides files-in-this-
repository over a service, and requires append-only enforcement that compares
bytes against the merge base rather than reading the diff's shape.

§ 3 then stops deliberately: *"The registry directory, its envelope schema, its
strict parser and its append-only validator are a **separate reviewed change**.
This record decides the owner, the contents and the discipline; it does not
create the store."* § 4 restates that as a prohibition — the directory does not
exist, and nothing may be written to a registry that does not yet exist.

This record is that separate reviewed change. It builds the store and leaves the
authorization to write the first receipt where ADR 0018 put it.

### Why this is an amendment and not a new standard

Nothing here decides anything ADR 0018 left open about *what a receipt is*. The
owner, the envelope's contents, the append-only discipline and the supersession
rule are all § 3's, unchanged. What changes is one factual clause: § 4 asserts
the non-existence of a directory that, after this change, exists. An assertion
of non-existence that survives the thing existing is not history, it is a
contradiction a reader has to resolve — and ADR 0018 § 4 is the paragraph a
reader consults precisely to find out whether the registry may be used.

`Amends` rather than `Supersedes` because every other control ADR 0018 carries
stays in force. Recording this narrowing as a supersession would quietly retire
rule 1's seven receipt fields, rule 2's six decommission categories and the
whole drift-prevention list, none of which this record touches.

### The residual decisions this record had to make

§ 3 fixed the envelope's *contents*. Turning contents into a checkable file
format still required choosing a serialization, a naming rule, a coordinate
form, a retirement-detail shape and a chain rule. Those are recorded in the
Decision below so they are reviewable as decisions rather than discovered as
implementation.

## Decision

### 1. The store

`receipts/`, one JSON file per receipt, named `<receipt_id>.json`, with
`receipt_id` in lowercase kebab-case and equal to the filename's stem. A receipt
addressed by two names cannot be superseded unambiguously, so the validator
compares the two and refuses a disagreement.

`receipts/README.md` documents the envelope for the person writing a receipt and
is not itself a receipt. Any other non-`.json` file in the directory is refused:
an undeclared file in a reviewed store is unvalidated content.

### 2. The envelope, as a closed field set

The eight required fields and two optional fields are exactly ADR 0018 § 3's
table, plus `schema_version`. The set is **closed** — a field outside it is
refused rather than ignored.

Closing it is the mechanism that answers the pressure § 3 predicted. That
pressure does not arrive as "let us put secrets in the registry"; it arrives as
*"it would be so much more useful with just this one field inlined"*. A closed
set makes the addition a reviewed change to this record instead of a plausible
line in a pull request.

`rollback_boundary` (rule 1 field 6) is deliberately **not** in the envelope, per
§ 3, and is therefore one of the fields the closed set refuses.

### 3. Coordinates are peeled commits

`coordinates.old` and `coordinates.new` each carry a `repository` and a peeled
40-character `commit`, optionally `path`, `released_version` and a
`sha256:`-prefixed `artifact_digest`.

ADR 0013 § 3 names what is not a coordinate: a branch name, "latest", a floating
or unpeeled tag, an image tag. The validator matches those shapes specifically
so the error can say *which* non-coordinate was supplied rather than only that
the value was not forty hex characters. A message that names the mistake is the
difference between a guard that teaches the rule and one that gets worked
around.

`effective_time` is RFC 3339 in UTC. A local offset would leave two receipts
unorderable without knowing which zone each was written in.

### 4. `old_writer_retirement_status` carries its detail

The vocabulary is rule 2's three values, and each names the detail that makes it
checkable: `retired` names the peeled `revision` that removed the writer,
`transferred` names the `new_owner` and that move's own `receipt`, `still_live`
names an `owner` and a `retirement_condition`.

A boolean is refused with an explicit message, and so is an absent status. Both
are the same defect: rule 2's *"absence is never a disposition"* re-entering
through the schema.

### 5. Supersession is the only correction, and a chain has one head

`supersedes_receipt` must name a receipt present in the registry, must not name
itself, and must not produce a cycle. Two receipts superseding the same receipt
are refused: a chain with two live heads leaves no single current receipt, which
is the ambiguity supersession exists to remove.

### 6. Append-only is enforced against the merge base, by bytes

`tools/check_receipts.py` reads every receipt present at the merge base and
compares its bytes with the working tree. A pre-existing receipt that differs, or
that is gone, fails.

Comparing bytes rather than reading the diff is the whole content of the control.
A rename plus a rewrite presents to a diff reader as one deletion and one
addition, and an addition is exactly what an append-only registry is for. A
delete plus an add presents as two unrelated edits. Both pass a shape check and
both destroy a receipt.

**The check fails closed.** If no base ref is supplied, if the base does not
resolve in the checkout — a shallow clone is the usual cause — or if there is no
merge base, the validator reports an error rather than success. The workflow
therefore fetches full history and passes the base explicitly. A guard that goes
green when it cannot determine what to compare against is worse than no guard,
because it reports a colour it did not earn.

### 7. Secret detection is the existing instrument, extended to this directory

ADR 0018's drift-prevention names `agent_control`'s secret-like-literal detection
as the instrument that must cover the registry. `tools/check_receipts.py` imports
`agent_control.engine.SENSITIVE_PATTERNS` rather than copying it: a second copy
of a pattern set is a second thing to keep current, and the one that falls behind
is the one nobody is watching. `private_evidence_pointer` is additionally checked
to be an address in a controlled system (`bao://`, `knowledge://`, `github://`,
`s3://`) rather than a value wearing a pointer's punctuation.

### 8. An empty registry is `not_applicable`, never a pass

Every structural check above holds trivially over zero receipts. Reporting
`executed_passed` would mean the first green result read as "the discipline is
evidenced" while nothing had been measured — the exact defect ADR 0015 was
written about and that this repository refuses everywhere else.

The validator therefore reports occupancy as its own verdict: `not_applicable`
with the `NO TESTS EXECUTED` evidence string over an empty directory,
`executed_passed` only once a receipt exists. The verdict vocabulary is reused
from `gate_control.contracts` as **code**, so the repository does not acquire a
second set of words for the same distinction; that reuse asserts nothing about
ADR 0015's status, which remains `Proposed`.

### 9. What this record does NOT do

It does not write a receipt, and it does not authorize one.

The registry ships **empty**. Open decision 21 has two halves — build the store,
and authorize its first entry — and only the first is engineering. The one
cutover this repository has documented in detail, the CRM chat cutover in
ADR 0018's motivating evidence, is explicitly incapable of producing a valid
receipt: the barrier wrote no attributed record, so there is no
`runtime_observation` to digest. Manufacturing a digest over something that does
not exist would put a decoration in the registry on day one, and § 3's own
warning is that a registry of decorations passes every structural check it has.

It also adds no conformance claim. ADR 0018 § 4's second sentence — that the
standards profile has no typed representation for a receipt and the Governance
engine has no oracle that could evaluate one — is unchanged and unamended.
Whether the envelope is represented in `standards-profile.schema.json` remains
open.

## Consequences

- The registry can be used the moment Michael authorizes a receipt, rather than
  the authorization being blocked on building a store.
- The store ships empty and says so in its own verdict. A reader who checks CI
  sees `not_applicable` and the reason, not a green tick that means nothing.
- ADR 0018 § 4 gains a dated amendment note pointing here. The original text is
  preserved rather than rewritten: what § 4 asserted was true when it was
  written, and a record that quietly edits itself to stay true is the shape this
  discipline refuses.
- Governance takes on a standing obligation to keep the registry publishable.
  The closed field set is what makes that obligation cheap; relaxing it once
  makes it permanent.
- The first real receipt will exercise the validator against something other
  than a fixture, and is the point at which the non-vacuity verdict flips. Until
  then the registry's controls are proved by construction only, which is stated
  rather than glossed.
- A contributor who tries to fix a wrong receipt the obvious way — by editing it
  — is stopped by CI with a message naming supersession as the repair. That is
  the intended teaching moment, and it is why the error text carries the reason
  and not only the rule.

## Drift prevention

`tools/check_receipts.py` enforces §§ 1–8. `tests/test_check_receipts.py`
constructs each prohibited shape and observes the guard firing on it, rather than
asserting that the current tree is clean:

- a receipt edited in place, including a whitespace-only edit;
- a receipt deleted;
- **a rename plus a rewrite** — the case a diff reader cannot see, and the
  sensitivity proof that distinguishes this implementation from one that reads
  the diff's shape;
- an inlined secret, both as a token-shaped `private_evidence_pointer` and as a
  private-key header buried in an unrelated field;
- a pointer holding a value rather than an address;
- each required field removed individually, so the field set's completeness is
  visible rather than asserted;
- a field outside the closed envelope;
- a branch name, an unpeeled tag and an image tag as coordinates;
- a boolean, an absent, and an out-of-vocabulary `old_writer_retirement_status`,
  and a status carrying no detail;
- a dangling, self-referential, cyclic and two-headed supersession chain;
- **a registry with zero receipts**, which must report `not_applicable` and must
  not report `executed_passed` — the non-vacuity case, because a registry
  validator over an empty directory passes for the wrong reason;
- an unresolvable base ref, an empty base ref, and `merge_base` raising rather
  than guessing — the fail-closed cases.

The validator is registered in `.dotmac/validation-contract.json` as a `local`
command, which binds `AGENTS.md`'s documented command list and the workflow
together: `tools/check_validation_contract.py` fails if either side moves
without the other, so this control cannot be quietly dropped from CI while
remaining in the instructions, or the reverse.

What is **not** enforced, stated rather than left to be discovered: nothing
checks that a `runtime_evidence_digest` reproduces against the artefact the
product holds. That requires reading another repository's private evidence and
is the same gap open decision 18 already records for oracle citations. Until it
closes, a digest is checked for shape and committed to by review, and this
record does not claim otherwise.
