# Two-arm correction: before/after adjudication

Status: EVIDENCE FOR A HUMAN APPROVAL DECISION. Nothing here is approved, merged
or pushed. ADR 0011 remains **Proposed**.

Subject: the rewrite of two `standards_control.engine` detector arms so that
neither reads raw source text any more —

* `connector_task` (`_schedules_a_connector`), now keyed on imports,
  decorators, registrations and task-dispatch calls;
* `delivery_retry` (`_owns_delivery_retry` / `_declares_retry_policy`), now keyed
  on identifiers, attributes, keywords and configuration literals in
  retry-relevant call or configuration contexts.

The visible signature change is `_classify_connector(tree, source)` →
`_classify_connector(tree)`.

Date of measurement: 2026-08-15. All measurement was performed as **library
probes** driving engine functions directly. **No test suite was run**, locally or
otherwise; nothing in this document is CI evidence.

> **Vocabulary note, added 2026-08-15 after this adjudication closed.** The
> category recorded throughout this document as `http_client` was renamed to
> `outbound_transport` in the same day's later change, which also gave it a
> second, SMTP arm and moved the profile schema to version 9 (version 8
> withdrawn). The label has been updated in place so that a search for the
> retired name finds nothing live — but **every count below is the HTTP arm
> alone**, measured before the SMTP arm existed. Where a figure is attached the
> text says so. Nothing in the HTTP arm's behaviour changed in that later work:
> re-measuring the four adopters with the SMTP arm forced off reproduces the
> `now` column of this document exactly, which is how "unchanged" was checked
> rather than asserted.

---

## 0. Bottom line

**Are there any lost true positives? NO.**

Twelve findings changed under the isolated boundary. Seven disappeared and five
appeared. Every one of the seven disappearances is a false positive with a named
mechanism, evidenced by the exact line in the real file that produced it:

* four came from **prose** — a docstring, a comment, a drift-check import or a
  UI listing call supplying the word the old first conjunct scanned for;
* two came from the **`async` ⊃ `sync` false friend** in the subject half;
* one came from **test-function names** containing `dead_letter`.

The five appearances are real `.delay(...)` / `.apply_async(...)` dispatches of
connector-shaped tasks that the text-scan rule could not see because the word
`celery` did not happen to appear in those files.

Two secondary facts a reviewer should carry with the "no" (neither is a lost
true positive, both are recorded here rather than buried):

1. `erp-adopt app/tasks/email.py` leaves the measured set entirely — it now holds
   no category at all. It is a real scheduled outbound delivery task (`smtplib`
   under `@shared_task`), but it was only ever caught because `send_email_async`
   contains the letters `sync`. **No arm of ADR 0011 covers SMTP delivery**,
   before or after. That is a pre-existing coverage bound the correction makes
   visible, not coverage the correction removed. See § 6.1.
2. Three further findings moved in categories the two-arm correction does not
   touch. All three belong to a **different, later** change (the HTTP-client and
   webhook path/method work), which sits outside this comparison boundary and is
   attributed precisely in § 7.

---

## 1. The comparison boundary, and why

### 1.1 The problem

The correction is uncommitted work layered on other uncommitted work. `HEAD`
(`fbd47b8`) predates the entire external-connector engine, so there is nothing to
check out: a `HEAD`-vs-worktree diff would compare the arms against their own
non-existence and would silently fold in every other edit made that day.

### 1.2 What was recoverable

`git fsck --lost-found` in `gov-ratchet` recovered three dangling WIP (dropped
stash) commits on `feat/external-connector-ratchet`, all with `fbd47b8` as
parent:

| dangling commit | time | `standards_control/engine.py` blob | size |
| --- | --- | --- | --- |
| `769901b` | 2026-08-15 14:40:03 +0100 | `627eac02557a9b69e7a76c4bd7bbd69c94b6fd82` | 125 787 |
| `59e5084` | 2026-08-15 14:45:21 +0100 | `627eac02557a9b69e7a76c4bd7bbd69c94b6fd82` | 125 787 |
| `d60f0e4` | 2026-08-15 19:21:13 +0100 | `e5a8be1ee114558a89471570e8c4cbfffac67f15` | 149 812 |

Blob `627eac0` still carries `_classify_connector(tree, source, *, …)` and the
text-scanning `_schedules_a_connector(tree, source)`. Blob `e5a8be1` carries both
arms already rewritten. So the correction is **fully contained** in the
14:40 → 19:21 window. Call those revisions `v1440` and `v1921`; the working tree
is `now`.

A top-level definition-by-definition diff (`ast.get_source_segment` per named
top-level statement) gives the exact contents of each window:

* **`v1440` → `v1921`** — `TASK_HINTS` removed; 24 names added
  (`SCHEDULING_DECORATOR_HINTS`, `TASK_DISPATCH_ATTRS`,
  `SCHEDULER_REGISTRATION_ATTRS`, `SCHEDULE_TABLE_NAMES`, `SYNC_PREFIX`,
  `RETRY_DECORATOR_HINTS`, `_declares_retry_policy`, `_is_connector_shaped`,
  `_mentions`, `_hint_pattern`, `_is_retry_word`, `_is_retry_literal`,
  `_literal_arguments`, `_dispatch_subjects`, `_registration_subjects`,
  `_schedule_table_subjects`, `_imports_a_scheduler`, `_is_scheduling_decorator`,
  `_named_within`, … ); 8 changed (`_schedules_a_connector`,
  `_owns_delivery_retry`, `_classify_connector`, `_conserved_findings`,
  `_derive_scope`, `_external_connector` — the last three only to stop passing
  `source` — plus `_is_checkpoint_class_name` picking up the shared `_mentions`,
  and `_reads_an_inbound_request` **reformatted only**, verified by diff).
* **`v1921` → `now`** — the HTTP-client and webhook work:
  `_imports_http_transport` replaced by `_uses_an_http_transport` +
  `_caught_client_positions`, `ROUTE_DECORATOR_ATTRS`, `MUTATING_ROUTE_ATTRS`,
  `GENERIC_ROUTE_ATTRS`, `AMBIGUOUS_WEBHOOK_PATH_HINTS`, `_route_mounts_a_mutation`,
  `_is_webhook_surface`, `_decorator_path_literals`, `_trace_client_factories`.
  Inside this window the two arms changed **only** by the
  `_imports_http_transport` → `_uses_an_http_transport` rename and a docstring
  paragraph (diff reproduced in the working notes).

### 1.3 The boundary chosen

> **BEFORE** = the current working-tree engine with *only* `_schedules_a_connector`
> and `_owns_delivery_retry` (and the constants `TASK_HINTS` / `TASK_SUBJECT_HINTS`
> / `RETRY_HINTS` they read) restored **verbatim** from blob `627eac0`, and
> `_classify_connector` restored to its `v1440` body — which is structurally
> identical to the current one apart from those two calls.
>
> **AFTER** = the current working-tree engine, unmodified.

This is Michael's suggested reconstruction: the pre-correction predicates are
re-declared in a probe module and driven through the **same** discovery,
reachability, tracing and attribution pipeline, so the classifier is the only
difference. Nothing in the `gov-ratchet` worktree was reverted to produce the
"before"; `git status --porcelain` is byte-identical before and after this whole
exercise (§ 9).

The grafted arms call the **current** `_uses_an_http_transport` and
`_is_webhook_surface`, not their `v1440` equivalents. That is deliberate and it
is what makes the boundary isolating: any movement caused by the HTTP/webhook
work then lands identically on both sides and cancels, leaving only the two arms.

### 1.4 The webhook false-positive fix: outside the boundary, and further out
### than expected

The brief expected the `webhook_surface` false positive (an offline Ed25519
licence verifier scoring `webhook_surface` because a function is called
`verify_signature`) to sit slightly *before* the correction and to account for
about one finding. Measured:

* `erp-adopt app/licensing/validator.py` — `def verify_signature(license_file)` —
  classifies `webhook_surface` **False in `v1440` already**, and `v1440` already
  contains `WEBHOOK_SUBJECT_HINT` and the `_reads_an_inbound_request` split. That
  fix therefore **predates 14:40** and is invisible in every revision this
  adjudication can reconstruct. It accounts for **zero** of the movement measured
  here.
* What *did* move in `webhook_surface` is a **later, different** webhook change
  (the ambiguous-`callback` + route-method qualification), which removed **two**
  `erp-adopt` findings in the `v1921 → now` window. Attributed in § 7.

Both are outside the boundary. Neither is confounded with the two arms.

---

## 2. Pinned inputs

Every measured repository is dirty, so a commit SHA alone does not pin the bytes.
Two things pin them instead:

1. the SHA and working-tree dirt count below;
2. a **corpus digest** — `sha256` over the sorted `path\0sha256(bytes)` of every
   file in that repository's derived measured universe.

Additionally, the comparison itself is **single-pass**: all four classifiers run
in one process over one parse of each file, so before and after see literally the
same `ast.Module` object. Byte-identity of inputs is guaranteed by construction
rather than by re-checkout.

| repository (worktree) | HEAD | dirty files | tracked `.py` | measured | excluded | corpus sha256 (first 16) |
| --- | --- | --- | --- | --- | --- | --- |
| `gov-ratchet` | `fbd47b8965002943bd5799992f4b29b04e361582` | 9 | 20 | 20 | 0 | `9d80d006c0293961` |
| `starter-spi-modes` | `86ff3033719d1806eb198dafad319f58910c3ed3` | 3 | 492 | 264 | 228 | `7c4712af1ef00a26` |
| `sub-adopt` | `71b712397ad31484a8a129ef0c168dca5a9ab702` | 6 | 4727 | 2959 | 1768 | `4f49f2c377c5defe` |
| `erp-adopt` | `381eb7b16d5b1fcaba1ebac621a41ef8eba3b1da` | 8 | 2725 | 2140 | 585 | `339868ed8750b1cc` |
| `academy-adopt` | `01e80e3d838390b1b791d9379dcfee82273532dd` | 6 | 363 | 156 | 207 | `9c327d1b0ba9591b` |
| `vcp-adopt` | `7cd553e6a8b406439ed08c108a251817ba0ba2ec` | 3 | 115 | 87 | 28 | `b9a06291b783b1f0` |

Engine revisions under test:

| label | provenance | `standards_control/engine.py` |
| --- | --- | --- |
| `now` (AFTER) | `gov-ratchet` working tree, 2026-08-15 20:39:30 | 163 984 bytes |
| `graft` (BEFORE) | `now` + the two arms verbatim from blob `627eac0` | — |
| `v1440` | dangling stash blob `627eac0` | 125 787 bytes |
| `v1921` | dangling stash blob `e5a8be1` | 149 812 bytes |

`v1440` and `v1921` are run as whole engines (loaded as sibling packages against
the current `contracts.py` / `profile.py`) purely to attribute movement to its
window. The adjudicated boundary is `graft` → `now`.

### 2.1 Universe: the engine's own, never a glob

Discovery is the current engine's, for every classifier:
`_tracked_python_sources` (`git ls-files -z --cached`, suffix or shebang, index
only — no `--others`, no `--exclude-standard`) → `_untracked_python_sources` →
`_declared_runtime_paths(profile)` → `_derive_scope` (two monotone fixed-point
passes over the import graph) → `_trace_client_factories` over the measured
trees. `app/**/*.py` is **not** the engine's universe and was not used: the
counts in the brief that suggested movement in untouched categories came from
that glob and are, as suspected, an artefact of the wrong universe — they do not
reconcile with any pair of engine revisions (see § 7.4).

Note on profile loading: only `gov-ratchet` currently has a profile the current
loader accepts. The others raise `ProfileError` (`academy-adopt`:
`schema_version must be integer 8`; `sub-adopt` / `starter-spi-modes`: `profile
missing keys: external_connector_surface`; `erp-adopt`: also
`testing_kit_boundary`; `vcp-adopt`: also `module_declared_vocabularies`). Those
repositories were therefore measured with an **empty** declared-runtime pin set,
identically on both sides of the boundary. This is stated because it slightly
enlarges the excluded set relative to what those repositories will measure once
their profiles are updated; it cannot bias a before/after comparison.

---

## 3. Fleet counts, per classifier

Measured sources holding each category (`v1440` / `graft` / `now` / `v1921`):

| repository | category | v1440 | **graft (BEFORE)** | **now (AFTER)** | v1921 |
| --- | --- | --- | --- | --- | --- |
| `sub-adopt` | connector_task | 18 | **18** | **18** | 18 |
| `sub-adopt` | delivery_retry | 9 | **8** | **7** | 8 |
| `sub-adopt` | outbound_transport (HTTP arm) | 41 | **40** | **40** | 41 |
| `sub-adopt` | webhook_surface | 4 | **4** | **4** | 4 |
| `sub-adopt` | provider_credential | 3 | **3** | **3** | 3 |
| `sub-adopt` | sync_checkpoint | 11 | **11** | **11** | 11 |
| `erp-adopt` | connector_task | 13 | **13** | **12** | 12 |
| `erp-adopt` | delivery_retry | 5 | **5** | **5** | 5 |
| `erp-adopt` | outbound_transport (HTTP arm) | 21 | **21** | **21** | 21 |
| `erp-adopt` | webhook_surface | 10 | **8** | **8** | 10 |
| `erp-adopt` | provider_credential | 6 | **6** | **6** | 6 |
| `erp-adopt` | sync_checkpoint | 15 | **15** | **15** | 15 |
| `academy-adopt` | outbound_transport (HTTP arm) | 2 | **2** | **2** | 2 |
| `academy-adopt` | provider_credential | 3 | **3** | **3** | 3 |
| `academy-adopt` | (other four) | 0 | **0** | **0** | 0 |
| `starter-spi-modes` | sync_checkpoint | 2 | **2** | **2** | 2 |
| `starter-spi-modes` | (other five) | 0 | **0** | **0** | 0 |
| `vcp-adopt` | all six | 0 | **0** | **0** | 0 |
| `gov-ratchet` | all six | 0 | **0** | **0** | 0 |

Under the isolated boundary (`graft` → `now`) **the only categories that move are
`connector_task` and `delivery_retry`.** The remaining four are identical file for
file, not merely equal in count.

---

## 4. The changed-finding record

Every changed finding under the adjudicated boundary. `before` / `after` are the
finding's presence under `graft` / `now`. `symbol` is the attributed unit from
`_connector_units` (the module's imports plus one top-level definition);
`<module>` means no single definition held the surface, which for the
pre-correction arms is itself diagnostic — `ast.unparse` drops comments, so a
finding driven by a comment cannot attribute to any definition.

| repo | category | detector_arm | path | symbol | before | after | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| erp-adopt | connector_task | dispatch (`.delay`) | `app/services/finance/banking/mono_sync.py` | `MonoSyncService` | absent | present | intended recall gain |
| erp-adopt | connector_task | dispatch (`.apply_async`) | `app/services/people/hr/employees.py` | `EmployeeService` | absent | present | intended recall gain |
| erp-adopt | connector_task | subject false friend (`async` ⊃ `sync`) | `app/tasks/email.py` | `send_email_async` | present | absent | intended false-positive removal (see § 6.1) |
| erp-adopt | connector_task | subject false friend (`async` ⊃ `sync`) | `app/tasks/hooks.py` | `execute_async_hook` | present | absent | intended false-positive removal |
| erp-adopt | connector_task | prose/text scan | `tests/conftest.py` | `<module>` | present | absent | intended false-positive removal |
| sub-adopt | connector_task | prose/text scan | `app/main.py` | `<module>` | present | absent | intended false-positive removal |
| sub-adopt | connector_task | prose/text scan (docstring) | `app/services/tr069.py` | `<module>` | present | absent | intended false-positive removal |
| sub-adopt | connector_task | dispatch (`.delay`) | `app/services/web_integration_syncs.py` | `trigger_sync_job` | absent | present | intended recall gain |
| sub-adopt | connector_task | dispatch (`.delay`) | `app/web/admin/integrations.py` | `erp_connector_run_now` | absent | present | intended recall gain |
| sub-adopt | connector_task | dispatch (`.delay`) | `app/web/admin/system.py` | `user_profile_device_login`, `user_device_login_set` | absent | present | intended recall gain |
| sub-adopt | connector_task | prose/text scan | `app/web_domains.py` | `<module>` | present | absent | intended false-positive removal |
| sub-adopt | delivery_retry | literal exactness / identifier position | `tests/test_dotmac_erp_outbox.py` | `<module>` | present | absent | intended false-positive removal |

No entry is classified `lost true positive` and none is classified `new false
positive`. § 6 gives the evidence for each.

### 4.1 Conserved (excluded-source) records

A conserved record is a published finding too (`CONNECTOR_CONSERVED_*`), so the
arms move those as well in principle. Measured over the excluded half of every
universe under the same boundary — **2816 excluded sources, zero changed
records**:

| repository | excluded sources | conserved categories held (graft) | (now) | changed |
| --- | --- | --- | --- | --- |
| `sub-adopt` | 1768 | outbound_transport 7, delivery_retry 3, provider_credential 2, sync_checkpoint 1 | identical | **0** |
| `erp-adopt` | 585 | webhook_surface 3, outbound_transport 2, delivery_retry 2, sync_checkpoint 1 | identical | **0** |
| `starter-spi-modes` | 228 | none | none | **0** |
| `academy-adopt` | 207 | outbound_transport 1 | identical | **0** |
| `vcp-adopt` | 28 | none | none | **0** |
| `gov-ratchet` | 0 | — | — | **0** |

Neither arm holds a single conserved record anywhere in the fleet, before or
after, so the exclusion ledger is untouched by this correction.

---

## 5. Method

```
python3 scratchpad/gov-audit/adjudicate.py     # single pass, 4 classifiers
python3 scratchpad/gov-audit/members.py …      # per-category membership, current engine
python3 scratchpad/gov-audit/evidence.py <file> <category>   # per-file witness lines
python3 scratchpad/gov-audit/conserved.py …    # excluded-half movement
python3 scratchpad/gov-audit/insitu.py         # real-corpus mutation proofs
```

`adjudicate.py` took 7 min 59 s wall for the six repositories. `members.py`
re-derived the same `now` counts independently, which is the reproducibility
check on the whole harness (`sub-adopt {outbound_transport: 40, webhook_surface: 4,
provider_credential: 3, connector_task: 18, sync_checkpoint: 11, delivery_retry:
7}`, matching § 3 exactly).

---

## 6. Per-file verdicts, with the evidence

### 6.1 `erp-adopt app/tasks/email.py` — `send_email_async` — REMOVED

Pre-correction first conjunct (raw-text scan for `TASK_HINTS`):

```
L    2 [STRING/DOCSTRING] Email Module Background Tasks - Celery tasks for email sending.
L   16 [code            ] from celery import shared_task
L  209 [COMMENT         ] # Re-raise our classified errors for Celery to handle
```

Pre-correction second conjunct (any decorator on a subject-shaped name):

```
L  126 def send_email_async  decorators=['shared_task(bind=True, max_retries=3, …)']
```

`send_email_async` satisfied `TASK_SUBJECT_HINTS` only because `async` contains
`sync`. The post-correction rule requires the subject to be connector-shaped
through `_mentions`, whose `(?<!a)sync` pattern is exactly the guard for this
false friend.

**Verdict: intended false-positive removal**, and the removal is correct on the
rule as declared — `connector_task` has always required a connector-shaped
subject, and `send_email_async` is not one under any reading that does not also
make every `async` identifier a connector.

**But record the consequence honestly.** This module is a real scheduled outbound
delivery task: `@shared_task(bind=True, max_retries=3, autoretry_for=…,
retry_backoff=True)` over `smtplib`. After the correction it holds **no category
at all**. It is not caught by `delivery_retry` either — that arm's second
conjunct requires an HTTP client or a webhook surface, and SMTP is neither; it
was `False` in all four classifiers, so this is a pre-existing bound, unchanged
by the correction. Recommended (NOT applied): state the SMTP/queue-only delivery
bound explicitly in ADR 0011's "what this does not see" section, so the gap is
declared rather than discovered.

### 6.2 `erp-adopt app/tasks/hooks.py` — `execute_async_hook` — REMOVED

```
L   17 [code] from celery import shared_task
L  136 def execute_async_hook  decorators=['shared_task(bind=True, max_retries=3, default_retry_delay=60)']
```

Same false friend (`async` ⊃ `sync`); `hook` is not a hint (`webhook` is, and
`webhook` is not a substring of `execute_async_hook`). This is the precise case
the engine's own `SYNC_PREFIX` comment cites as the defect being fixed, now
confirmed against the real corpus rather than a fixture.

**Verdict: intended false-positive removal.** The module remains measured — it
still holds `delivery_retry` in `now` — so the ratchet has not lost sight of it.

### 6.3 `erp-adopt tests/conftest.py` — `<module>` — REMOVED

```
L 1090 [code] def scheduled_task(db_session):            <- a pytest fixture
L  249 def _noop_tenant_context_sync  decorators=['contextmanager']
L  255 def _noop_bypass_rls_sync      decorators=['contextmanager']
```

A fixture named `scheduled_task` supplied the text hint; `@contextmanager` on a
`*_sync` helper supplied the "decorator on a subject-shaped name". Nothing here
schedules anything. **Verdict: intended false-positive removal.**

### 6.4 `sub-adopt app/main.py` — `<module>` — REMOVED

```
L  301 [code] from app.celery_app import celery_app
L  302 [code] from app.services.scheduler_config import find_unregistered_scheduled_tasks
L  304 [code] drift = find_unregistered_scheduled_tasks(celery_app.tasks.keys())
L  650 def grafana_webhook_sink              decorators=["app.post('/api/v1/alerts/grafana-webhook', …)"]
L 1365 def api_sync_pressure_guard_middleware decorators=["app.middleware('http')"]
```

The text hint comes from a **drift check that audits the scheduler**; the subject
half is satisfied by an HTTP route and an HTTP middleware. Auditing a scheduler is
not scheduling a connector, and a route is not a task. **Verdict: intended
false-positive removal.**

### 6.5 `sub-adopt app/services/tr069.py` — `<module>` — REMOVED

```
L   76 [STRING/DOCSTRING] A Celery ``SoftTimeLimitExceeded`` is raised asynchronously and can land
L 1133 def sync_from_genieacs  decorators=['staticmethod']
```

The *only* occurrence of any `TASK_HINTS` word in the entire file is inside a
**docstring**, and the second conjunct is satisfied by `@staticmethod`. This is
the canonical instance of the defect: prose as evidence. **Verdict: intended
false-positive removal.** (The module's real GenieACS traffic is not lost — the
scheduling half lives in `app/tasks/tr069.py`, which holds `connector_task` and
`delivery_retry` in `now`.)

### 6.6 `sub-adopt app/web_domains.py` — `<module>` — REMOVED

```
L  388 [code] items = scheduler_service.scheduled_tasks.list(
L  310 def integrations_home  decorators=["router.get('/integrations', …)"]
L  324 def connectors_home    decorators=["router.get('/connectors', …)"]
```

An admin page that **lists** scheduled tasks, plus two GET routes whose names
contain `integration`/`connector`. Reading a list is not scheduling. **Verdict:
intended false-positive removal.**

### 6.7 `sub-adopt tests/test_dotmac_erp_outbox.py` — `<module>` — REMOVED (delivery_retry)

```
L  239 [code] def test_deliver_transient_dead_letters_at_attempt_budget(db_session):
L  254 [code] def test_deliver_permanent_error_dead_letters_immediately(db_session):
L  389 [STRING/DOCSTRING] "dotmac_erp_max_retries",
```

Post-correction: `_declares_retry_policy` is `False`. The two hits are **test
function names** (a `FunctionDef` name is not an executable identifier position),
and `"dotmac_erp_max_retries"` is refused by the literal arm's exactness rule
because it *mentions* the token rather than *being* it.

Checked, because a removed test finding can be a proxy for a missed
implementation finding: it is not. The subsystem under test,
`app/services/dotmac_erp/outbox.py`, contains **no** retry-vocabulary word at all
— not even textually, in any revision — so it was never counted by any of the
four classifiers; its sibling `app/services/dotmac_erp/client.py` still holds
`outbound_transport` in `now`. The delivery machinery there is spelled as an attempt
budget, which is a pre-existing, unchanged vocabulary bound, identical before and
after. **Verdict: intended false-positive removal.**

### 6.8 The five gains

| path | witness (real line) |
| --- | --- |
| `erp-adopt app/services/finance/banking/mono_sync.py` | L458 `sync_mono_account.delay(mono_account_id)` |
| `erp-adopt app/services/people/hr/employees.py` | L1358 `sync_employee_staff_account.apply_async(args=[…])` |
| `sub-adopt app/services/web_integration_syncs.py` | L381 `run_integration_job.delay(job_id, 'manual')` |
| `sub-adopt app/web/admin/integrations.py` | L207 `sync_erp_operational_domains.delay()` |
| `sub-adopt app/web/admin/system.py` | L1739, L2591 `sync_device_login.delay()` |

Each is a genuine queue dispatch of a connector-shaped task, in executable code.
The pre-correction rule missed all five because the word `celery` does not appear
in those files (`mono_sync.py` has it only in two docstrings, which cannot satisfy
the second conjunct because those modules define no decorated subject-shaped
function). **Verdict on all five: intended recall gain.** None is a new false
positive: `.delay` / `.apply_async` on a `sync_*` / `*_integration_job` target is
the textbook dispatch this arm exists to catch.

---

## 7. Movement outside `connector_task` and `delivery_retry`

**Under the adjudicated boundary there is none.** `outbound_transport`,
`webhook_surface`, `provider_credential` and `sync_checkpoint` hold exactly the
same files under `graft` and under `now`, in all six repositories. So the
correction is not defective in this respect, and the boundary is not leaking.

The movement the brief hinted at is real but belongs to other changes. Attributed:

### 7.1 `erp-adopt` `webhook_surface` 10 → 8 — the `v1921 → now` window

| path | route | v1440 | v1921 | now |
| --- | --- | --- | --- | --- |
| `app/web/auth.py` | `@router.get('/auth/oidc/callback')` | True | True | **False** |
| `app/web/finance/payments.py` | `@router.get('/callback')` | True | True | **False** |

Both are browser redirect targets, not provider callbacks: an OIDC consent return
and a hosted-checkout return page. Removed by `AMBIGUOUS_WEBHOOK_PATH_HINTS` plus
the route-method qualification, which landed **after** the two-arm correction.
Correct removals, and outside this boundary.

### 7.2 `sub-adopt` `outbound_transport` 41 → 40 and `delivery_retry` 9 → 8 — same window

`app/tasks/notifications.py` imports `httpx` at L11 and then uses it **only** in
`except` clauses (L973, L1068, L1083): `except (httpx.TimeoutException,
httpx.NetworkError)`, `except httpx.HTTPStatusError`. The actual requests are made
by `app/services/meta_pages.py`, which retains both `outbound_transport` and
`delivery_retry` in `now`. `_uses_an_http_transport` with `_caught_client_positions`
correctly declines the caught-only import; `delivery_retry` follows, because its
second conjunct then has no outbound surface in that module.

This single file is the *only* reason `graft` shows `delivery_retry` 8 where
`v1440` shows 9 — the graft deliberately uses the current HTTP predicate so that
this out-of-window change cancels instead of being misattributed to the arms.

### 7.3 The licence verifier

Already `False` at `v1440` (§ 1.4). Contributes nothing to any number here. The
brief's expectation of "roughly one finding" is not contradicted — that finding
was removed before the earliest revision this comparison can reconstruct.

### 7.4 Why the crude `app/**/*.py` numbers do not reconcile

They cannot, and not only because of the universe. The hinted pairs (e.g.
`sub-adopt outbound_transport 41 → 36`, `erp-adopt delivery_retry 5 → 6`,
`academy-adopt outbound_transport 2 → 3`) do not match **any** pair of the four
classifiers measured here over the engine's own universe, in which `academy-adopt
outbound_transport` is 2 in all four and `erp-adopt delivery_retry` is 5 in all four. A
glob over `app/**/*.py` differs from the derived universe in both directions: it
includes sources `_derive_scope` proves test-only, it excludes everything outside
`app/` (in `starter-spi-modes` the only findings at all are under `packages/`),
it ignores the tracked-index rule (untracked files inflate it; index entries whose
bytes are absent deflate it), and it never computes `_trace_client_factories`,
which is a repository-wide property that changes per-file HTTP classification.
Treated, as instructed, as a discarded hint.

---

## 8. Per-arm resolution table

Isolated boundary, whole fleet. "Resolutions" counts findings that changed state.

| arm | FP removals | recall gains | net | real witnesses |
| --- | --- | --- | --- | --- |
| `connector_task` | 6 | 5 | −1 (31 → 30) | removals: `sub app/services/tr069.py` (docstring-only `Celery` + `@staticmethod sync_from_genieacs`), `sub app/main.py` (scheduler **drift check** import), `sub app/web_domains.py` (`scheduler_service.scheduled_tasks.list(`), `erp tests/conftest.py` (fixture named `scheduled_task`), `erp app/tasks/email.py` + `app/tasks/hooks.py` (`async` ⊃ `sync`); gains: the five `.delay` / `.apply_async` dispatches in § 6.8 |
| `delivery_retry` | 1 | 0 | −1 (13 → 12) | removal: `sub tests/test_dotmac_erp_outbox.py` (`def test_..._dead_letters_...`, `"dotmac_erp_max_retries"`) |
| `outbound_transport` | 0 | 0 | 0 | no movement under this boundary — liveness proved in situ (§ 9) |
| `webhook_surface` | 0 | 0 | 0 | no movement under this boundary — liveness proved in situ (§ 9) |
| `provider_credential` | 0 | 0 | 0 | no movement under this boundary — liveness proved in situ (§ 9) |
| `sync_checkpoint` | 0 | 0 | 0 | no movement under this boundary — liveness proved in situ (§ 9) |

Retained-true-positive witnesses for the two changed arms (files that held the
category before **and** after, so the arms did not merely go quiet):
`connector_task` retains 13 `sub-adopt` task modules (`app/tasks/crm_ticket_pull.py`,
`dotmac_erp_outbox.py`, `gis.py`, `infrastructure_polling.py`,
`integration_delivery.py`, `integrations.py`, `profile_sync.py`, `radius.py`,
`radius_population.py`, `router_sync.py`, `topology_lldp.py`, `topology_uisp.py`,
`tr069.py`, …) and 10 `erp-adopt` ones (`app/tasks/crm.py`, `dotmac_sub.py`,
`exchange_rates.py`, `expense.py`, `finance.py`, `hr.py`, `payments_sync.py`,
`performance.py`, `staff_sync.py`, `app/api/dotmac_sub.py`); `delivery_retry`
retains `sub app/services/ai/client.py`, `ai/voice_transcription.py`,
`meta_pages.py`, `router_management/connection.py`, `web_integrations.py`,
`app/tasks/tr069.py`, `app/web/admin/integrations.py` and `erp
app/dependency_health.py`, `services/crm/client.py`,
`services/dotmac_sub/client.py`, `services/sync/inventory_push_service.py`,
`app/tasks/hooks.py`.

---

## 9. In-situ mutation proofs for the zero-resolution arms

Every one of ADR 0011's six arms declares a baseline of **0** in the repository
that owns the ADR (`gov-ratchet`, `.dotmac/standards-profile.json`), and four of
them resolved nothing in this correction. A zero from an arm nobody has ever seen
fire is indistinguishable from a zero from an arm that is not wired to anything —
and a `tmp_path` fixture proves the predicate, never the wiring. So each arm was
proved **in situ**, against the real corpus:

1. assert the arm's own discovery reached the real file — the path is in the
   universe derived from `git ls-files`, not from a list in the probe;
2. inject a representative violation into that real file's bytes on disk;
3. re-run the **real entry point** `verify_repository(root, profile_path)` and
   require the arm to fire, and the re-derived real universe to name that real
   path;
4. restore the bytes, and prove the corpus is byte-identical and Git-clean.

Baseline before any injection: all six categories 0, zero `CONNECTOR_*`
diagnostics.

| arm | real target (discovery reached) | fired via real path | real path named | diagnostic | bytes restored |
| --- | --- | --- | --- | --- | --- |
| `outbound_transport` | `agent_control/activation.py` | yes | `agent_control/activation.py` | `outbound_transport: 1 measured sources exceed the declared baseline 0` | yes (`495ab777…`) |
| `webhook_surface` | `agent_control/cli.py` | yes | `agent_control/cli.py` | `webhook_surface: 1 measured sources exceed the declared baseline 0` | yes (`f012cc74…`) |
| `provider_credential` | `agent_control/managed.py` | yes | `agent_control/managed.py` | `provider_credential: 1 measured sources exceed the declared baseline 0` | yes (`32117e4e…`) |
| `connector_task` | `agent_control/profile.py` | yes | `agent_control/profile.py` | `connector_task: 1 measured sources exceed the declared baseline 0` | yes (`7acfa628…`) |
| `sync_checkpoint` | `standards_control/cli.py` | yes | `standards_control/cli.py` | `sync_checkpoint: 1 measured sources exceed the declared baseline 0` | yes (`05ddbb1c…`) |
| `delivery_retry` | `tools/check_adrs.py` | yes | `tools/check_adrs.py` | `delivery_retry: 1 measured sources exceed the declared baseline 0` | yes (`c14f4c5f…`) |

Injections were the minimal representative violation for each arm — e.g.
`httpx.post("https://provider.example/v1/events", json={})` for `outbound_transport`,
`@_insitu_router.post("/webhooks/provider")` for `webhook_surface`,
`sync_provider_invoices.delay()` for `connector_task`, `class
ProviderSyncCursor: last_synced_at = None` for `sync_checkpoint`. Each write is
wrapped in `try/finally`; the corpus was restored and verified by `sha256` per
file, and `git status --porcelain` for `gov-ratchet` is identical to its value
before the exercise (the same 8 modified files and 1 untracked ADR).

Note on `connector_task`: the probe deliberately used the **dispatch** arm on a
file that imports no scheduler, which also proves that the arm does not silently
depend on the framework-import qualifier.

---

## 10. Residual items (recorded, NOT applied)

1. **State the SMTP/queue-only delivery bound in ADR 0011.** `erp-adopt
   app/tasks/email.py` is a real scheduled outbound delivery task that no arm
   covers. Declared bound, not a defect — but it should be declared.
2. **`_declares_retry_policy` does not read `FunctionDef` names.** Correct for
   tests; worth one line in ADR 0011's stated bounds, because a production helper
   named `deliver_with_max_retries` that binds nothing would also be missed.
3. **Adopter profiles do not load under the current schema** (§ 2). Until they
   do, those repositories are measured with an empty declared-runtime pin set,
   which slightly over-excludes. Fix in the adoption change, not here.
4. **`_untracked_python_sources` reports ignored files as errors.** It calls
   `git ls-files --others` **without** `--exclude-standard`, so every gitignored
   Python file becomes a `REPOSITORY_SOURCE_UNTRACKED` **error**. Measured:
   `starter-spi-modes` 3119 untracked sources of which 3086 are `.venv/…`
   (`git ls-files --others --exclude-standard` returns **0**); `vcp-adopt` 407;
   `sub-adopt` / `erp-adopt` / `academy-adopt` 2 each. The omission is correct
   and deliberate for `_tracked_python_sources` (a product `.gitignore` must not
   decide what is measured) but it does not follow that the *report* of untracked
   sources should include ignored build artefacts. Unrelated to this correction —
   the measured universe is `--cached` only and is unaffected — but it will make
   the ratchet unusable in two of the five adopters as it stands. Not fixed here.
5. **The unrelated fixture-only architecture proofs found in `dotmac_starter_mt`**
   are tracked separately in `docs/inventories/adr-0018-conformance-backlog.md`.
   They are NOT fixed here and this correction is not expanded into a fleet
   rewrite.
