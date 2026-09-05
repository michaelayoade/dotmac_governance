# 0044. A local action resolves against whatever the workspace root holds

- Status: Proposed
- Date: 2026-09-05
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: `dotmac_governance` workflows, with propagation to the enrolled estate undecided
- Classification: Internal

## Context

A GitHub Actions step written `uses: ./.github/actions/x` loads its action from
`$GITHUB_WORKSPACE`. Nothing in that reference names a repository, a commit or
a ref. It names a *directory*, and the directory holds whatever the job last
checked out into it.

Every workflow guard in this fleet that inspects `uses:` references exempts the
local form, and each states the same premise: a local action is this
repository's own code at this commit, so there is no external reference that
can move under it. The premise is true for a job whose workspace root holds the
commit that defines the workflow. It is false for a job that has checked out a
ref the *caller* chose.

That distinction was not theoretical. `michaelayoade/dotmac_platform_control_plane`'s
`.github/workflows/kernel-lock.yml` is a `workflow_dispatch` workflow taking a
commit SHA as an input, holding a read credential for the private package
index, and resolving a dependency lock against that commit. Its first version
checked out the dispatched ref — and nothing else — into the workspace root,
then ran a local composite action from it:

```yaml
- uses: actions/checkout@<sha>
  with:
    ref: ${{ inputs.ref }}
- uses: ./.github/actions/setup-poetry
```

The dispatched ref's own code therefore executed in a job holding the
credential, before anything had looked at that ref. The hash-pinned bootstrap
requirements file the composite action read came from the same untrusted tree,
so the pinning was pinned by whoever authored the ref. The repair, at
`origin/main` `522e2b0f702b529ea9a155daf2731bd4c1a95d57`, puts the trusted
commit at the root and the ref under resolution beside it:

```yaml
- uses: actions/checkout@<sha>
  with:
    ref: ${{ github.sha }}
- uses: actions/checkout@<sha>
  with:
    ref: ${{ inputs.ref }}
    path: work
- uses: ./.github/actions/setup-poetry
```

Two properties of the incident are why this becomes a record rather than a
one-repository fix. First, **the defect lived where a checker's exemption was**,
not where its assertions were: the action-pinning guard read the offending line
and skipped it by rule. Second, **the premise behind the exemption read as
obviously true**, which is why it survived review — the failure was an
unstated, unenforceable qualifier on an otherwise correct sentence.

Michael Ayoade ruled on 2026-09-05 that the check graduates into
`dotmac_governance` using that repository's implementation and tests, and that
its claim stays narrow.

## Decision

### 1. The rule

> A workflow job that checks out a caller-supplied ref into the workspace
> **root** must not afterwards load a local action (`uses: ./...`).

The repaired shape is the fleet's form: the workspace root holds the commit
that defines the workflow, and any caller-supplied ref is checked out beside it
under an explicit `path:` and read only as data.

### 2. What "caller-supplied" means, as a closed set

A ref is caller-supplied when its expression comes from a value the dispatcher
or the event's author chooses. The set is declared in
`tools/check_local_action_workspace.py` as `CALLER_CONTROLLED` and is closed:
`inputs.`, `github.event.inputs.`, `github.event.client_payload.`,
`github.event.pull_request.head.`, `github.head_ref`, and
`github.event.workflow_run.head_`.

`github.sha`, `github.ref` and a literal branch name are deliberately **not** in
it. Those are the event's own ref, which is the repaired shape's *trusted* root.
A rule that treated them as caller-supplied would report almost every workflow
in the fleet, including the ordinary `pull_request` shape where GitHub already
withholds secrets from forks — and a guard that reports everything is a guard
that gets switched off.

### 3. The claim is narrow, and the boundary is part of the rule

This rule covers exactly one mechanism: a local action loaded from a workspace
root a caller-supplied ref controls. It does **not** cover, and a job that
satisfies it has **not** been shown safe with respect to:

- **scripts invoked by `run:` steps** — `run: python work/scripts/x.py` and
  `run: ./script.sh` are shell text that nothing here reads;
- **Poetry and other plugins** — a `requires-plugins` table, or any plugin
  mechanism executing code during a tool's own start-up;
- **package build backends executed during dependency resolution** — a
  candidate with no wheel metadata has its build backend run by the resolver.
  That is the exposure an ordinary `poetry install` already carries in CI, and
  nothing here reduces it.

Those three are real and adjacent. Naming them is load-bearing rather than
modest: the failure this record exists to prevent is a *true-sounding premise
with an unstated qualifier*, and a graduated check whose boundary lived only in
a reviewer's head would reproduce that failure one level up. The boundary is
therefore carried three ways — in this section, in the module's `NOT_COVERED`
tuple, and in the line the checker prints on success, so a reader who sees only
a green CI step still sees what was not checked.

### 4. Where it is enforced, and where it is not

`tools/check_local_action_workspace.py` runs against **this repository only**,
as a local validation command and as a CI step, on the same footing as
`tools/check_adr_references.py` and `tools/check_commit_identity.py`. The
subject is repository-local — workflow files this repository contains — so
ADR 0013 § 1 permits the claim to be derived here without an external oracle.

It creates **no `standards-profile.schema.json` surface**, adds no
`standards_control` rule family, and changes nothing for any other enrolled
repository. Propagation is open decision 51 and is undecided; until it is
decided, **every enrolled repository other than this one is an unmonitored
region rather than a covered one**, and this record may not be cited as fleet
coverage.

### 5. What acceptance would add, and what it would not

Acceptance by a named human would make § 1–§ 3 normative for the enrolled
estate as a written standard. It would still not activate enforcement anywhere
but here: activation is a separate deliberate act, and it is decision 51.

## Consequences

**The gate is currently inert in this repository, and that is stated rather
than hidden.** No workflow here checks out a caller-supplied ref, so the
checker passes over an empty set. A check that passes over a clean tree proves
nothing about itself, which is why its value is prospective — it fails the
change that first introduces the shape — and why every proof of its behaviour
is planted rather than observed on production text.

**A workflow that genuinely needs a dispatched ref pays a two-checkout cost.**
That is the intended cost. The alternative shapes — trusting the ref, or
inlining the action's steps — either keep the exposure or duplicate code the
composite action exists to share.

**One near-miss must never become a finding.** A caller-supplied ref checked out
to a non-root `path:` while a local action loads from the trusted root *is the
repair*. A guard reporting it would be telling contributors to undo the fix.

**This is a port, not an invention** (`dotmac_starter_mt` AGENTS.md rule 22).
Owner: `dotmac_governance`. Contract: `scan`/`scan_text` and the `Finding`
shape in `tools/check_local_action_workspace.py`. Consumers: this repository's
CI. Source: `michaelayoade/dotmac_platform_control_plane` at `origin/main`
`522e2b0f702b529ea9a155daf2731bd4c1a95d57` —
`tests/architecture/test_kernel_lock_workflow.py`,
`tests/architecture/test_workflow_action_pinning.py` (whose docstring amendment
states the premise being graduated), and `.github/workflows/kernel-lock.yml`.
`dotmac_governance` has **no `EXTRACTION.toml`**; this paragraph and the
module's docstring are where the provenance is recorded, and adding such a
mechanism here is not decided by this record.

Two things were generalised in the port, and both widen the **subject** rather
than the **claim**: the scan covers every workflow rather than one named file,
and it is per **job**, because a workspace belongs to a job; and `inputs.ref`
became the closed `CALLER_CONTROLLED` set of § 2.

## Drift prevention

`tests/test_check_local_action_workspace.py` holds the controls, and the port
is only a port because it can be shown catching the original defect:

- **Parity.** The measured pre-repair shape of `kernel-lock.yml` is RED; the
  measured repaired shape is SILENT. Both fixtures are permanent.
- **The rule this replaced.** The blanket local-action exemption is
  re-implemented and shown **silent** on the shape the new check names, so
  "the old rule could not see this" is a check rather than a claim.
- **Three near-misses, each required to stay silent** — a local action with no
  caller-supplied ref; a caller-supplied ref with no local action; a
  caller-supplied ref at a non-root `path:` while the local action loads from
  the trusted root.
- **Positional and per-job sensitivity.** A local action *before* the untrusted
  checkout is silent; a trusted checkout takes the root back; two jobs do not
  contaminate each other — and the per-job split is shown still reporting the
  job that IS the defect, so isolation is not deafness.
- **Parser non-vacuity.** The parser is hand-rolled, because `requirements-dev.txt`
  carries no YAML library and adding one so a lint step can read one directory
  would be the worse trade. A parser returning nothing would make every
  assertion above pass, so it is shown reading this repository's own workflow:
  one job, sixteen steps, and the local action among them.
- **The boundary is asserted.** `NOT_COVERED` is required to be non-empty and
  to name all three families, the success message is required to carry every
  one of them, and a job executing an untrusted `run:` script is asserted **not**
  reported — the exclusion recorded as a control rather than as prose.
- **Corpus.** `.yaml` and nested workflow files are discovered; a tree with no
  workflow directory, or an empty one, REFUSES rather than reporting success.

`tools/check_validation_contract.py` holds the checker's presence in
`AGENTS.md`, `.dotmac/validation-contract.json`, `.dotmac/agent-profile.json`
and `.github/workflows/governance-checks.yml` in agreement, so the step cannot
be dropped from one of them silently.
