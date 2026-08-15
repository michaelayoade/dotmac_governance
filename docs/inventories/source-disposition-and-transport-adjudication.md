# Source disposition and outbound transport — independent adjudication

- Date: 2026-08-15
- Adjudicator: independent audit pass, separate from the sessions that
  implemented Decision 1 and Decision 2
- Subject: `worktrees/gov-ratchet`, branch `feat/external-connector-ratchet`,
  working tree at base commit `fbd47b8965002943bd5799992f4b29b04e361582`
- Status of the thing being adjudicated: ADR-0011 **Proposed**; all four
  adopters **PENDING-APPROVAL**; nothing committed, pushed, published or
  approved by this pass either

---

## Bottom line, unhedged

**There are NO lost true positives. Bypass D is still closed.**

Across a six-repository corpus, measured with one parse per file and two
classifiers applied to the same syntax tree:

- **Category losses: 0.** Not one measured source lost a category it held
  before, in any of the six categories, in any of the six repositories.
- **Category gains: 8, across 7 modules.** Every one is a genuine SMTP surface,
  verified by reading the source. Zero new false positives.
- **HTTP arm movement: 0.** All seven gained modules have
  `_uses_an_http_transport == False`. The HTTP arm could not have moved them,
  and it moved nothing else.
- **Untracked errors removed: 3,525.** Every single one resolves inside a
  directory that an INDEPENDENT re-implementation of the four-arm predicate
  also proves is a dependency environment. Zero product sources, zero tracked
  files, zero files failing containment.

Two caveats that do not change the verdict but that the approver should carry,
both stated in full in "Residual risk" below: (1) on this corpus the
disposition's *output* is indistinguishable from `--exclude-standard`'s, so the
corpus alone cannot discriminate the two rules — the fixtures and the in-situ
liveness test are what discriminate them, and they do; (2) all four adopter
candidate profiles name an ADR path that does not exist, which blocks the
adoption step (not these two decisions).

---

## Method, and where it is honest about its limits

### The "before" engine could not be a git blob, so it is grafted

`HEAD` (`fbd47b8`) contains **no connector code at all**:

```
$ git show HEAD:standards_control/engine.py \
    | grep -c "ConnectorCategory\|_classify_connector\|connector_scope\|_dependency_environment"
0
$ git show HEAD:standards_control/engine.py | wc -l
879        # vs 4395 in the working tree
```

The entire external-connector ratchet — both decisions — lives in one
uncommitted change set. There is no prior revision that contains the engine
minus the SMTP arm, so **"before" is reconstructed by grafting**, and this is
stated rather than glossed: the prior predicates are re-expressed against the
*current* pipeline, so the git inventory, the reachability/exclusion
derivation, the conservation ledger and the factory tracing are literally the
same objects on both sides, and **only the classifier differs**.

The grafted `classify_before` restores exactly two things to their pre-Decision-2
form, because the SMTP arm was added in exactly two places:

```python
http = outbound or (E._uses_an_http_transport(tree) and E._issues_a_request(tree))
if http:                                      # was: if http or _speaks_smtp(tree)
    found.add(C.OUTBOUND_TRANSPORT)
...
if E._declares_retry_policy(tree) and (       # _owns_delivery_retry, SMTP leg removed
    outbound or E._uses_an_http_transport(tree) or E._is_webhook_surface(tree)
):
    found.add(C.DELIVERY_RETRY)
```

### Single pass, so byte-identity is structural

Each measured source is read and parsed **once**; both classifiers are then
applied to the same `ast.Module` object. There is no second read that could
disagree, so "the two runs saw identical bytes" is a property of the harness's
shape rather than an assertion about it. `_trace_client_factories` is likewise
computed once over the shared tree map and consulted by both classifiers.

### The engine's own inventory, never a directory walk

Populations come from `E._git_paths(root, "--others")`, `E._tracked_python_sources`,
`E._untracked_python_populations`, `E._environment_home` and
`E.connector_scope` — the real functions. No `app/**/*.py` glob was used
anywhere; that is what previously produced numbers reconciling with no
revision pair.

### Pinning

Every corpus worktree is **dirty**, so a SHA does not pin the measured bytes.
Each repo is therefore recorded by SHA *and* by a sha256 over the exact ordered
measured file set, taken before and after classification and compared
(`digest_stable`).

| repo | SHA | branch | dirty entries | measured | excluded | digest stable |
|---|---|---|---|---|---|---|
| `starter-spi-modes` | `86ff3033719d` | `feat/spi-mode-specific-plugin-protocols` | 7 | 264 | 228 | yes |
| `sub-adopt` | `71b712397ad3` | `chore/adopt-connector-ratchet` | 6 | 2959 | 1768 | yes |
| `erp-adopt` | `381eb7b16d5b` | `chore/adopt-connector-ratchet` | 8 | 2140 | 585 | yes |
| `academy-adopt` | `01e80e3d8383` | `chore/adopt-engineering-standards` | 6 | 156 | 207 | yes |
| `vcp-adopt` | `7cd553e6a8b4` | `chore/adopt-connector-ratchet` | 3 | 87 | 28 | yes |
| `gov-ratchet` | `fbd47b896500` | `feat/external-connector-ratchet` | 10 | 20 | 0 | yes |

Zero unparseable sources in all six.

### Evidence discipline

Everything below is a **library probe** driving `standards_control.engine`
functions directly, plus **one** test method driven directly via
`unittest.TestSuite`. The pytest/unittest **suite was not run**. **None of this
is CI evidence.** CI remains the acceptance owner. `ruff` and `mypy` are not
installed in this session and the submitted record's static-check claims were
**not reproduced** — see "What I did not verify".

---

## Question 1 — SOURCE DISPOSITION

> How many untracked errors disappeared, and is EVERY one of them inside a
> semantically proved environment?

### How many

**3,525 untracked errors disappeared**, all in two repositories.

| repo | untracked before | visible after | ignored after | dispositioned | partition exact |
|---|---|---|---|---|---|
| `starter-spi-modes` | 3121 | 2 | 0 | **3119** | yes |
| `sub-adopt` | 2 | 2 | 0 | 0 | yes |
| `erp-adopt` | 2 | 2 | 0 | 0 | yes |
| `academy-adopt` | 2 | 2 | 0 | 0 | yes |
| `vcp-adopt` | 407 | 1 | 0 | **406** | yes |
| `gov-ratchet` | 0 | 0 | 0 | 0 | yes |

`partition exact` is checked as a set identity, not an arithmetic one:
`before == visible ∪ ignored ∪ dispositioned`, with all three pairwise
intersections empty. Nothing was double-counted and nothing fell out of the
accounting. This reproduces the submitted record's table exactly.

The seven survivors are all genuine untracked product sources and all still
error — the adoption scaffolding each repo is mid-way through adding:

```
starter-spi-modes  scripts/guard_proof_backlog.py
                   tests/architecture/test_guard_proof_ratchet.py
sub-adopt          tests/architecture/external_connector_surface.py
                   tests/architecture/test_external_connector_ratchet.py
erp-adopt          scripts/check_connector_adoption.py
                   tests/architecture/test_connector_surface_adoption.py
academy-adopt      scripts/check_governance_pin.py
                   tests/architecture/test_engineering_standards_adoption.py
vcp-adopt          tests/architecture/test_external_connector_ratchet.py
```

### Is every one inside a semantically proved environment — YES

The engine's own answer was not taken on trust. A **second, independent
implementation** of A1–A4 was written from the ADR text and run against every
root the engine dispositioned into. Both agree, on both roots:

| repo | root | A1 marker | A2 layout | A3 interpreter | A4 containment | version | engine count | independent walk |
|---|---|---|---|---|---|---|---|---|
| `starter-spi-modes` | `.venv` | pass | `lib/python3.13/site-packages` | `bin/python` | pass | 3.13 | 3119 | 3119 |
| `vcp-adopt` | `.venv` | pass | `lib/python3.13/site-packages` | `bin/python` | pass | 3.13 | 406 | 406 |

And per file, across all 3,525:

- **dispositioned into a root that failed the independent proof: 0**
- **dispositioned files failing per-file containment (A4): 0**
- **dispositioned files that are TRACKED: 0**
- `engine_roots_match_walk`: true in all six repos

### The bypass-D probe

The question is not whether the two `.venv` trees are real — they obviously are
— but whether any **ordinary ignored package** or any **product source** rode
out with them.

**Q2 — is any dispositioned file product code?** No. 0 tracked. 103 files
across the two repos are byte-identical to a tracked source, and every one is a
**zero-length `__init__.py`** (sha256 `e3b0c442…b855`, the empty-file digest) —
a trivial collision between empty package markers, not a duplicated source.

Decisively: the product is installed **editable**, as `.pth` path pointers back
to the tracked checkout, not as copies inside `site-packages`:

```
dotmac_kernel.pth  -> .../starter-spi-modes/packages/dotmac-kernel/src
dotmac_files.pth   -> .../starter-spi-modes/packages/dotmac-files/src
   ... 9 such pointers; vcp-adopt has none at all
```

**No product bytes live inside either environment.** The tracked originals stay
fully measured.

**Q3 — does any dispositioned file hold a connector surface?** Four, all in
`starter-spi-modes`, and all four are third-party library code under
`site-packages`:

```
.venv/lib/python3.13/site-packages/dns/query.py            ['outbound_transport']
.venv/lib/python3.13/site-packages/dns/asyncquery.py       ['outbound_transport']
.venv/lib/python3.13/site-packages/dns/_trio_backend.py    ['outbound_transport']
.venv/lib/python3.13/site-packages/starlette/testclient.py ['outbound_transport']
```

`vcp-adopt`: zero. None is product code; `dnspython` and `starlette` are
declared dependencies. Critically, **none of these was ever measured**: untracked
files never enter the measured universe, only the untracked-error population.
So no connector *finding* was lost — what was removed is an error about
provenance, not a surface.

**The 37 dispositioned files that sit outside `site-packages`** were listed and
read individually, because that is the one place product code could plausibly be
parked. All 37 are pip-generated console-script shims and `activate_this.py`:

```
starter-spi-modes (34): .venv/bin/{pytest,mypy,alembic,uvicorn,gunicorn,pip,...}
                        .venv/bin/activate_this.py
vcp-adopt (3):          .venv/bin/{pip,pip3}, .venv/bin/activate_this.py
```

These are extensionless, which is why `_is_python_source` admits them on the
shebang/parse rule. They are tool-owned dependency material and correctly
dispositioned.

### Verdict on Q1

**Bypass D is closed.** 3,525 errors removed, 100% of them inside a
semantically proved environment under two independent implementations of the
predicate, 0 product sources, 0 tracked files, 0 containment failures. Not one
ordinary ignored package slipped into the excluded set — in this corpus there
were none to slip.

---

## Question 2 — OUTBOUND TRANSPORT

> Does the count change by exactly the SMTP arm's new witnesses, or did the
> rename move something unexpectedly? Any movement in the HTTP arm is
> presumptively a defect.

### The count changes by exactly the SMTP arm, and by nothing else

| repo | category | before | after | delta |
|---|---|---|---|---|
| `sub-adopt` | `outbound_transport` | 40 | **44** | **+4** |
| | `delivery_retry` | 7 | 7 | 0 |
| | `connector_task` / `provider_credential` / `sync_checkpoint` / `webhook_surface` | 18 / 3 / 11 / 4 | 18 / 3 / 11 / 4 | 0 |
| `erp-adopt` | `outbound_transport` | 21 | **23** | **+2** |
| | `delivery_retry` | 5 | **6** | **+1** |
| | `connector_task` / `provider_credential` / `sync_checkpoint` / `webhook_surface` | 12 / 6 / 15 / 8 | 12 / 6 / 15 / 8 | 0 |
| `academy-adopt` | `outbound_transport` | 2 | **3** | **+1** |
| | all five others | 0 / 3 / 0 / 0 / 0 | 0 / 3 / 0 / 0 / 0 | 0 |
| `vcp-adopt` | all six | 0 | 0 | 0 |
| `starter-spi-modes` | `sync_checkpoint` 2, all others 0 | — | identical | 0 |
| `gov-ratchet` | all six | 0 | 0 | 0 |

This reproduces the submitted record's table **exactly**, including
`erp-adopt`'s `delivery_retry` 5 → 6.

### The HTTP arm did not move — proved, not asserted

Two independent proofs:

1. **The before column IS the HTTP-only column**, computed in the same pass on
   the same trees. Every non-`outbound_transport` category is byte-stable, and
   `outbound_transport`'s before value equals the pre-change value in all six.
2. **Every one of the 7 gained modules has `_uses_an_http_transport == False`.**
   The HTTP conjunction is unsatisfiable in all of them, so the HTTP arm was
   not merely quiet — it was structurally incapable of contributing the gain.

There is no repository, category or file in which the HTTP arm's contribution
differs between the two runs.

### The two boundary witnesses are real, and they isolate the legs

The record's claim that the SMTP arm had to be a **disjunction** rather than a
copy of the HTTP conjunction rests on two modules. Both check out against the
actual source:

**`erp-adopt/app/tasks/email.py` — USED only.** This is PROBLEM 2, the genuine
`@shared_task` SMTP delivery task that previously held **no category at all**.

```
12:  import smtplib
73:      if isinstance(exc, smtplib.SMTPAuthenticationError):
77:      if isinstance(exc, smtplib.SMTPResponseException):
88:      if isinstance(exc, smtplib.SMTPRecipientsRefused):
96:      if isinstance(exc, smtplib.SMTPSenderRefused):
103-104:         smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected,   <- except type
```

It opens nothing and sends nothing, so a conjunctive arm would have missed it.
It reaches leg 1 through the `isinstance` positions, which are executable,
while lines 103–104 are the inert `except`-type position the arm deliberately
ignores. **Both sides of that specificity boundary are exercised by the same
real file** — which is unusually strong evidence for the boundary being right.
It gains `outbound_transport` and `delivery_retry` together.

**`sub-adopt/scripts/one_off/send_important_account_batch.py` — SENT only.**
The exact mirror image:

```
5:   import smtplib
92:      except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, OSError):
87,99:   server.sendmail(...)
```

`smtplib` appears **only** at the import and inside an `except` tuple, so
USED is correctly `False`; the module is recovered solely by the `sendmail`
leg, against a `server` object this analysis cannot resolve. The SENT leg is
therefore live on real code and not merely on a fixture.

### No new false positives

All 7 gained modules were read. Every one imports `smtplib` and genuinely
performs or governs mail delivery:

| module | evidence |
|---|---|
| `sub-adopt/app/services/email.py` | `smtplib.SMTP_SSL(host, port)` @937 |
| `sub-adopt/app/services/web_system_export_tool.py` | `smtplib.SMTP_SSL(...)` @1113, `server.sendmail(...)` @1122 |
| `sub-adopt/app/team_inbox_smtp.py` | `with smtplib.SMTP(host=..., port=...)` @55 |
| `sub-adopt/scripts/one_off/send_important_account_batch.py` | `server.sendmail(...)` @87, @99 |
| `erp-adopt/app/services/email.py` | `smtplib.SMTP_SSL(...)` @71, @350 |
| `erp-adopt/app/tasks/email.py` | SMTP error-class policy @73–104 |
| `academy-adopt/app/services/email.py` | `with smtplib.SMTP(...)` @80, `smtp.send_message(...)` @85 |

### Verdict on Q2

The count changes by **exactly** the SMTP arm's new witnesses. The rename moved
nothing. No HTTP-arm movement anywhere — no presumptive defect to investigate.

---

## Deterministic record of every changed finding

Format: `repo | category | detector_arm | path | symbol | before | after | verdict`

### Connector classification — 8 changed findings, 7 modules

```
sub-adopt     | outbound_transport | SMTP: USED+OPENED+SENT | app/services/email.py                             | _legacy_smtp_config      | absent | present | intended recall gain
sub-adopt     | outbound_transport | SMTP: USED+OPENED+SENT | app/services/web_system_export_tool.py            | _send_export_email       | absent | present | intended recall gain
sub-adopt     | outbound_transport | SMTP: USED+OPENED      | app/team_inbox_smtp.py                            | run_e2e_probe            | absent | present | intended recall gain
sub-adopt     | outbound_transport | SMTP: SENT only        | scripts/one_off/send_important_account_batch.py   | main                     | absent | present | intended recall gain
erp-adopt     | outbound_transport | SMTP: USED+OPENED+SENT | app/services/email.py                             | send_email               | absent | present | intended recall gain
erp-adopt     | outbound_transport | SMTP: USED only        | app/tasks/email.py                                | classify_email_error     | absent | present | intended recall gain
erp-adopt     | delivery_retry     | SMTP in outbound conj. | app/tasks/email.py                                | classify_email_error     | absent | present | intended recall gain
academy-adopt | outbound_transport | SMTP: USED+OPENED+SENT | app/services/email.py                             | send_email               | absent | present | intended recall gain
```

```
LOST TRUE POSITIVE : 0
new false positive : 0
```

### Source disposition — 3,525 changed findings, 2 roots

```
starter-spi-modes | repository.source.untracked | source-disposition A1-A4 | .venv/** (3119 files) | n/a | 3119 errors | 0 errors + 1 NOTICE | intended false-positive removal
vcp-adopt         | repository.source.untracked | source-disposition A1-A4 | .venv/**  (406 files) | n/a |  406 errors | 0 errors + 1 NOTICE | intended false-positive removal
```

Classified as *intended false-positive removal* rather than a recall loss: the
untracked-source control exists to police the provenance of **repository
sources**, and a tool-materialised dependency tree is not one. Nothing that was
ever *measured* changed; the removed diagnostics were provenance errors about
files the measured universe never contained.

Both roots emit an auditable `repository.dependency-environment` **NOTICE**
naming the root, the Python version, the marker/layout/interpreter evidence and
the file count — the subtraction is reported, not silent. Both untracked
populations remain `_finding` (errors) with distinct messages; verified at
`engine.py:4355` and `engine.py:4365`.

---

## Independent verification of two contested claims

### The §7 "pre-existing red" repair — CONFIRMED, with a precision correction

The submitted record admits changing another session's assertion
(`test_the_traced_connector_scores_without_its_project_halves`, renamed to
`test_the_untraceable_connector_holds_the_conceded_undercount`) and claims the
failure pre-dated both decisions. Verified without editing anything, by showing
the added disjunct is **inert** on that fixture:

```
ERPNEXT_CONNECTOR fixture:
  _speaks_smtp              : False
  _uses_an_smtp_transport   : False
  _opens_an_smtp_connection : False
  _sends_mail               : False
  _uses_an_http_transport   : False
  classify (no tracing)     : ['provider_credential', 'sync_checkpoint']
```

`_speaks_smtp` is `False`, so Decision 2's only change to the classifier cannot
affect this test; Decision 1 operates on untracked populations and cannot affect
a fixture's classification. The classification is exactly what the repaired test
now asserts. The ADR concedes the bound in writing at
`docs/adr/0011-…md:1033-1040`. **Claim confirmed.**

**Precision correction:** the record calls this red "pre-existing", which is
true only relative to Decisions 1 and 2 — **not** relative to `HEAD`, which
contains no engine at all. The red was introduced earlier in the same
uncommitted change set (by the scheme repair). An approver should read it as
"not caused by these two decisions", not as "inherited from main".

### The population-split liveness test — CONFIRMED live

This is the load-bearing test, because `untracked_ignored` is a legitimate zero
in all six corpora. Driven directly (one method, `unittest.TestSuite`; **not**
a suite run, **not** CI evidence):

```
test_the_population_split_liveness_classifies_real_repository_code
  (t.DependencyEnvironmentDispositionTests) ... ok
Ran 1 test in 0.718s
OK
```

Hygiene after the in-situ plant: `git status --porcelain` **IDENTICAL** to the
pre-run snapshot. The test plants into `__pycache__/`, which this repository's
own tracked `.gitignore` already covers, so it mutates no tracked file.

---

## Residual risk the approver should carry

### 1. This corpus cannot discriminate disposition from `--exclude-standard`

`.venv/` is gitignored in both repositories that have one:

```
starter-spi-modes/.gitignore:11: .venv/
vcp-adopt/.gitignore:3:         .venv/
```

and **100% of dispositioned files are gitignored** (3119/3119 and 406/406).
`untracked_ignored` is **0 in all six repositories**. So on this corpus the
disposition removes exactly the set `--exclude-standard` would have removed,
and the corpus **cannot tell the two rules apart by their output**.

What separates them is the semantic predicate and the surviving error
population — and that separation is proved only by the fixtures (an ordinary
ignored package still errors; a gitignored connector beside a real environment
still errors) and by the in-situ liveness test above. Those proofs exist and
pass. But it means the fixture suite is not decoration here: **it is the only
thing standing between this control and `--exclude-standard`**, and it must stay
green in CI. If `test_negative_3_an_ordinary_ignored_package_still_errors`,
`test_bypass_d_stays_closed_beside_a_recognised_environment` or the
population-split liveness test is ever weakened, bypass D reopens with no
corpus signal whatsoever.

### 2. All four adopter candidate profiles name an ADR that does not exist

Not raised in the submitted record; found in this pass. Every candidate profile
pins its governance source to `docs/adr/0010-external-connector-surface-ratchet.md`:

| adopter | governance source | revision | schema |
|---|---|---|---|
| `sub-adopt` (`.next.json`) | `0010-external-connector-surface-ratchet.md` | `PENDING-…` | 6 |
| `erp-adopt` (`.v6.json`) | `0010-external-connector-surface-ratchet.md` | `00000000…` | 6 |
| `academy-adopt` (live) | `0010-external-connector-surface-ratchet.md` | `PENDING-…` | 6 |
| `vcp-adopt` (`.pending-approval.json`) | `0006-cross-repository-engineering-conformance.md` | `PENDING-…` | 6 |

In `gov-ratchet` the ADR is **0011**; `docs/adr/0010*` does not exist (the
number is skipped entirely). Three of the four are unmistakably parked on
`PENDING-` placeholder revisions, so they cannot pass the governance pin and
genuinely stay PENDING-APPROVAL — the claim holds operationally. `erp-adopt`
uses an all-zeros placeholder instead and carries no `PENDING-APPROVAL` marker
string, which is a cosmetic inconsistency; the operative fact is that its live
profile is still schema 3 and this v6 file is not installed.

**This is an adoption-step blocker, not a defect in either decision.**

### 3. The held candidate profiles are stale and must not be used as a control

Their `http_client` numbers do **not** correspond to either column measured
here:

| adopter | held `http_client` | measured before (HTTP-only) | measured after (v9) |
|---|---|---|---|
| `sub-adopt` | 37 | 40 | 44 |
| `erp-adopt` | 21 | 21 | 23 |
| `academy-adopt` | 3 | 2 | 3 |
| `vcp-adopt` | 0 | 0 | 0 |

`academy-adopt`'s held `3` coincidentally equals its **post**-change value, and
its held `provider_credential` (2) differs from measured (3). These profiles
pre-date several engine repairs and are stale in more than the key name. The
submitted record does disclose the staleness; this table makes the trap
concrete. **A key rename from these numbers would ratchet in wrong baselines**
— which is precisely why the v8 refusal message says RE-MEASURE, and it is
right to say so.

### 4. PROBLEM 2 is closed; undeclared dependency provenance remains open

`erp-adopt/app/tasks/email.py` now holds `outbound_transport` and
`delivery_retry`. Confirmed above. Whether the dispositioned dependency trees
are declared, pinned and provenanced is a **separate control that does not
exist yet** — correctly stated in the code, the ADR and the NOTICE text.

---

## Defects found in the submitted record

None material. Three accuracy defects, listed so the record can be corrected:

1. **The Decision-2 §1 grep output no longer reproduces.** The record quotes 3
   surviving `http_client` hits; there are now **9**. The 6 extra are all
   `assertNotIn` negative assertions inside
   `test_the_retired_category_name_appears_in_no_live_position` — the pinning
   test the record itself added after running the sweep. Substantively correct;
   the quoted output is stale.
2. **Line-number drift.** The record cites the new liveness test at
   `tests/test_standards_control.py:5317`; it is at **5695**.
3. **"Scratchpad fixtures deleted" is false.** The audit scratchpad still holds
   roughly 180 entries from prior sessions. Immaterial — nothing is inside any
   repository — but the claim as written is untrue.

Everything numeric in both records reproduced exactly.

---

## What I did not verify

Stated so the gap is not mistaken for coverage:

- **The test suite was not run.** One method was driven directly. The 231-test
  and 24-test green runs the records report are **unreproduced here**. CI owns
  them.
- **`ruff` and `mypy` are not installed in this session**, so the records'
  static-check claims (clean `ruff`; 2 and 4 pre-existing `mypy` errors) are
  **unverified**. They were labelled as non-CI evidence in the records and
  remain so.
- **The 19 negative probes and the 7 RED mutations were not re-executed.** The
  fixtures were read and are correctly constructed; corpus-level and in-situ
  evidence was gathered independently instead.
- **No commit, push, publish or approval** was performed. ADR-0011 remains
  `Proposed`; all four adopters remain PENDING-APPROVAL.

## Hygiene

`git status --porcelain` in `gov-ratchet` is byte-identical to the 10-entry
session baseline apart from this file. All six corpus worktrees are at their
pre-audit entry counts (7 / 6 / 8 / 6 / 3 / 10). Probe-name sweep across all
six: clean. `dotmac_erp` and `dotmac_crm` were never touched.

## Gate recommendation

**Clear to push to CI.** No lost true positives, no new false positives, bypass
D closed under an independent re-proof. CI is the acceptance owner for the
suite, `ruff` and `mypy`. Before the *adoption* step — a separate gate — fix the
`docs/adr/0010-…` reference in all four candidate profiles and re-measure every
baseline rather than renaming keys.
