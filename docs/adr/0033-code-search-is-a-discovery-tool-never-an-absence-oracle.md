# 0033. Code search is a discovery tool, never an absence oracle

- Status: Accepted
- Date: 2026-09-01
- Effective: 2026-09-01
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository, lane or record that asserts the absence of something across a corpus it does not hold
- Classification: Internal
- Amends: 0013 — how a negative claim is OBTAINED; § 4 governs a negative claim's form and adds no requirement on the instrument that established the absence

## Context

### The measurement

During the `dotmac-ticketing` consumer census, `gh search code` returned **zero
hits for a string present in hundreds of files in a public repository**.

Nothing about the query was wrong. Nothing about the tool was broken in a way an
operator could see. The result was well-formed, fast, and empty, and an empty
result set is exactly what a consumer census is looking for — which is why this
is worth a record rather than a bug report. **The tool's failure mode and the
tool's answer are the same shape.**

The lane caught it for one reason. Before reading its own silence as absence, it
had run the same query against consumers it already knew existed, and that
control came back empty too. Having established that the instrument could not
find a thing known to be there, it **refused to rely on the tool at all** and
re-took the census through authenticated `gh api` contents fetches with the HTTP
status of each fetch verified.

The refusal is the part worth generalising. The lane did not downgrade its
confidence, annotate the finding, or report a smaller number with a caveat. It
declined to make the claim with that instrument.

### Why a code search cannot carry a negative claim

The measured failure was probably indexing delay, and it does not matter, because
the instrument has at least five independent ways to return an empty result for a
subject that is present:

- **Indexing delay.** The index is not the repository. A file that exists is not
  searchable until something has indexed it, and nothing in the response says
  when that was.
- **Default-branch scope.** The index covers a default branch. A subject on any
  other ref is absent from the answer and present in the repository.
- **Access boundaries.** The result set is filtered by what the calling token can
  see. A private repository, an org the token does not belong to, or a scope the
  token lacks all subtract silently — they do not error.
- **Result caps.** The API truncates. A capped result set and a complete one are
  the same JSON with a different length, and a lane that reads a count is reading
  the cap.
- **Unsearched surfaces.** Artefacts, release assets, submodule contents, vendored
  trees and history are not in the index at all. "It is not in code search" and
  "it is not in the repository" are different propositions.

Each is sufficient on its own, and none of them announces itself. A zero result
is therefore indistinguishable from *not indexed yet*, *not on that branch*, *not
visible to this token*, *truncated*, and *not in the searched surface*. **An
instrument that cannot separate "absent" from "not looked at" returns silence,
and silence is not a measurement.**

One further fact needs no oracle to check, because the tool says it about itself.
`gh search code --help` states that its results are "powered by what is now a
legacy GitHub code search engine" and that they "might not match what is seen on
github.com". The vendor already declines to guarantee correspondence between the
index and the repository. Anyone can re-read that line by running the command.

### What ADR 0013 already covers, and the gap this record fills

ADR 0013 § 4 separates permanent positive evidence from temporal negative claims,
and requires an absence to be recorded either as an as-of observation carrying
oracle coordinates, an observation date and a **named refresh responsibility**,
or replaced by a repository-local positive fact. That is a rule about a negative
claim's **form**, and it is the right rule: an absence describes a moment, and a
moment expires.

It says nothing about the **instrument**. A negative claim can satisfy § 4
perfectly — dated, coordinate-bearing, with a named owner who will re-observe it
before the decision it gates — and be false at the moment it was taken, because
the reading it faithfully records was taken with something that could not see the
subject. **§ 4 makes an absence claim expire. It does not make it true when it
was made.** The `dotmac-ticketing` census would have produced an impeccably
formed § 4 observation of an absence that was not there.

This record amends ADR 0013 on exactly that point and on no other. The four
oracle kinds in its § 2 are unchanged and this record adds no fifth. Its § 5
refusal to build a generic prose scanner stands and is reaffirmed below.
`dotmac_starter_mt` `AGENTS.md` rule 30, which restates ADR 0013 fleet-wide at
merge `2d711cd594979ba0bc368382b7f5ea69bf21eaa4`, is narrowed by this record in
the same way and by the same clause.

### The neighbouring draft

ADR 0021 § 9 requires a coordinate to be **sensitivity-tested**: demonstrated to
go red on an absent coordinate, a dead one and a filler. The positive control
below is that idea moved from a coordinate to an instrument. The two were reached
independently, one day apart, from unrelated measurements, which is some evidence
that the shape is real. ADR 0021 is `Proposed` and is cited here as a draft, not
as policy.

## Decision

### 1. The standard

> **Code search is a discovery tool, never an absence oracle.**

`gh search code`, the GitHub code search API, a forge's web search box and any
equivalent remote index may be used to FIND things. A negative claim — no
consumer exists, no caller remains, the symbol appears nowhere, the legacy writer
is retired — may not rest on one of them, whatever its result set.

This is a rule about what carries a claim, not about what an engineer may run.
Discovery is what these tools are for, they are good at it, and nothing here
discourages using them.

### 2. What an admissible negative claim requires

Five requirements. They are conjunctive; a claim missing any one of them is not a
weaker claim, it is not one.

1. **A closed, authoritative subject inventory.** The set of things being claimed
   empty is enumerated from an authority — an organization's repository listing, a
   declared composition, a dossier, a registry — before the search begins. A
   census whose subject set comes from its own result set proves only that it
   agrees with itself, and that is precisely the shape a zero-hit search produces:
   nothing found, therefore nothing to look at, therefore nothing there.
2. **Exact refs.** Each subject is read at a named immutable ref. "The default
   branch", "latest" and "current `main`" are already refused as coordinates by
   ADR 0013 § 3, and the default-branch failure above is the reason they are
   refused here specifically: the ref the index happens to cover is not the ref
   the claim is about.
3. **Complete enumeration.** Every subject in the inventory is actually visited,
   and each visit's outcome is individually known. A census that reached eleven of
   fourteen subjects has not made a smaller claim about a smaller estate; it has
   made no claim about the estate.
4. **A local, parser-aware scan.** The reading is performed over content that was
   fetched, by something that understands the file's grammar — an import
   collector, an AST walk, a declared-format parser — rather than by a remote
   index over a token. Fetching is what removes the index from the trust path;
   parsing is what stops a substring match in a comment, a fenced example or a
   changelog entry from counting as a use.
5. **An explicit refusal when enumeration is incomplete.** A lane that cannot
   reach a subject **refuses**. It does not report the subset, does not report a
   count with a caveat, and does not treat an unreachable subject as an empty one.
   This is the requirement that fails in practice, because a refusal looks like a
   worse result than a number, and reporting the number is always available.

### 3. The positive control

> **A search used for a negative claim must first be shown to find a thing known
> to exist.**

The control runs before the claim, against a subject the lane already knows is
present, using the **same instrument, the same query shape, the same credential
and the same scope** as the claim itself. A control run under different conditions
tests different conditions and says nothing about the ones the claim was taken
under.

If the control comes back empty, the instrument is refused. The claim is not
annotated or downgraded — it is not made with that instrument. That is what the
`dotmac-ticketing` lane did, and it is why the defect was caught rather than
recorded.

**A passing positive control is necessary and is not sufficient**, and this needs
saying because a green control is exactly the kind of thing that gets read as a
licence. It removes ONE of the five failure modes in § Context — the instrument is
not answering at all — and leaves the other four untouched: a token-filtered
result, a capped result, an off-branch subject and an unsearched surface all
survive a control that passed. The control is a cheap detector that stops a lane
from trusting a broken instrument. It is not a promotion of code search to an
oracle, and § 1 is not conditional on it.

### 4. Scope, and what this does not require

- It governs **negative claims about a corpus**: absence, emptiness, retirement,
  "no remaining caller", "no consumer". It does not govern positive findings, for
  which a search result that is confirmed by fetching the file is ordinary
  evidence.
- It adds **no oracle kind**. ADR 0013 § 2's four kinds are unchanged.
- It requires **no repair sweep**. Existing absence claims that rest on a search
  are unproven rather than refuted; restating them is ordinary maintenance, done
  first where a claim is load-bearing for a deletion or a retirement.
- It creates **no check and no CI gate**. See § Drift prevention.

## Consequences

- Consumer censuses, retirement claims and "nothing depends on this any more"
  statements become materially more expensive: an enumeration from an authority
  plus a fetch per subject, instead of one query. That cost is the finding, not a
  side effect — the cheap version was answering a different question.
- Some existing absence claims across the fleet rest on a search. They become
  **unproven**, not false. This is the same reclassification ADR 0022's acceptance
  applied to recoveries recorded under a weaker definition, and it is uncomfortable
  in the same way and for the same reason.
- Lanes will start producing refusals where they used to produce zeroes. A refusal
  reads as a worse result and is a better one, and a reviewer who treats it as a
  lane defect will unbuild this record's only real control.
- The rule bites hardest on the claim people most want to be true — "nothing
  imports this any more" — which is the claim that immediately precedes a
  deletion. That is where it is worth the cost.
- The positive control belongs inside the lane, not in the reviewer's head. A
  reviewer cannot see that a query returned nothing for the wrong reason; the lane
  can, for the price of one extra query.

## Drift prevention

**Enforcement status: none.** No `standards_control` rule evaluates this record,
`standards-profile.schema.json` carries no field for a census, an inventory, a
positive control or a refusal path, and no engine diagnostic exists for it.
Confirmed at this repository's `main` `79817a16` in the same way ADR 0031's
drift-prevention section was: nothing under `standards_control/`, `gate_control/`,
`agent_control/`, `programme_control/`, `tools/` or `.github/workflows/` reads the
ADR directory except `tools/check_adrs.py` and `tools/check_adr_references.py`,
neither of which knows what a negative claim is. **Adding this record turns no
gate red in any enrolled repository.**

**A generic detector is refused, and the refusal is inherited rather than newly
decided.** ADR 0013 § 5 already rules out a prose scanner over documents: it
cannot separate a claim from a description of one, it would flag this record's own
recital of the `dotmac-ticketing` census, and its exception list would grow until
it measured nothing. That ruling covers this record's subject matter exactly, and
this record does not reopen it. Conformance in prose is **stated review
discipline**, which ADR 0013 § 5 permits so long as it is said plainly rather than
implied.

**The decidable half, and where it is decidable.** Where a census is a TOOL rather
than a paragraph — a script that enumerates subjects and reports emptiness — three
of its properties are decidable from that tool's own source and its own tests, in
its own repository:

- the positive control exists and runs **before** the claim, on the same
  instrument and credential;
- the enumeration is built from a declared inventory rather than from the search's
  own results;
- the incomplete-enumeration path **refuses** rather than returning a subset.

That is where the measured lane put its own repair, and it is where a future
family would have to live. This repository cannot observe it: whether another
repository's test suite demonstrates any of it is a fact about that suite, which
ADR 0013 § 1 places outside what this repository may assert. Whether such a family
is built, and by whom, is open decision 41.

**Known-bad case, required to fail.** A lane that issues one code-search query,
receives zero results, and records "no consumer exists" — with no inventory, no
per-subject fetch, no positive control and no refusal path. That is the exact
shape the `dotmac-ticketing` census would have had without its control, and a
checker that passes it is not implementing this record, whatever else it does.

**Non-vacuity, stated in advance.** Two shapes that must go red, because both pass
a naive implementation:

- a positive control run against a **different** query, corpus, credential or
  scope than the claim it licenses — it is present, it is green, and it tests
  conditions the claim was not taken under;
- a lane whose refusal path exists but is unreachable, because every enumeration
  failure is caught earlier and folded into an empty result.

And the ordinary one: a checker over zero absence claims passes for the wrong
reason. Until at least one enrolled repository declares a census subject to this
record and the checker is shown red when its positive control is removed, the
control is not evidenced — which is why the paragraph above says `none` rather
than `pending`.

## Acceptance — 2026-09-01

Michael Ayoade approved this rule on 2026-09-01 and directed that it live in
checked-in Governance rather than in Knowledge alone. Under `AGENTS.md` an agent
may not occupy the approver role or approve its own output, and neither happened
here: § 1's standard, § 2's five requirements and § 3's positive control are his,
transcribed. The drafting agent chose the record's placement — an amendment to
ADR 0013 § 4 at the next free number rather than an in-place edit of an `Accepted`
record — and wrote the reasoning, the scope limits in § 4 and the drift-prevention
analysis. Those are the parts most safely changed later.

**Acceptance makes § 1 normative and builds nothing.** There is no
`standards-profile.schema.json` field, no `standards_control` rule, no CI gate,
and no enrolled repository's profile changes. An enrolled repository whose absence
claims rest on a code search is an **unmonitored region**, not a covered one, and
this record may not be cited as a gate.

Acceptance also does not reopen ADR 0013 § 5's refusal of a prose scanner, does
not add an oracle kind, does not change any ADR number anywhere, and does not
mandate a sweep of existing absence claims.
