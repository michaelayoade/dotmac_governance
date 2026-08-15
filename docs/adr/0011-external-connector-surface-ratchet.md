# 0011. Direct external-connector surfaces are measured and ratcheted centrally

- Status: Proposed
- Date: 2026-08-14 (scope layer replaced 2026-08-15 after an adversarial audit;
  derivation hardened later the same day after a second audit against the
  replacement — see "The index is the authority, not the working tree";
  detectors widened with bounded tracing 2026-08-15 — see "Bounded tracing:
  one hop of project-local indirection"; exclusion conservation added and this
  record renumbered from 0010 to 0011 on 2026-08-15 — see "Exclusion
  conservation: what leaves the universe is recorded" and "The record number";
  three tracing repairs after a tracing-evasion audit 2026-08-15 — a false
  positive in the module-local request arm, the submodule import spelling, and
  `__all__` in the star re-export clause, see "The slash that was not a URL"
  and "What is traced"; three classifier repairs after a false-positive sweep
  2026-08-15 — a celery task name read as a route path, `callback` split off as
  an ambiguous path word, and a client that is only CAUGHT no longer counted as
  used, with two further proposed repairs refused on measured evidence, see
  "Three more names taken for evidence, and two repairs that were refused";
  the category `http_client` RENAMED to `outbound_transport` and given a second,
  SMTP arm 2026-08-15, schema version 9 with version 8 withdrawn — see "The
  category is the concept, not one transport")
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories
- Classification: Internal
- Amends: 0006 — adds the external-connector-surface rule family to the conformance profile and engine

## Context

Dotmac applications integrate through versioned APIs and webhooks, and the
Integrator sequence retires provider clients, provider credentials, provider
webhook verification, connector scheduling, feed checkpoints and delivery retry
machinery from each product's own runtime. Whether that is happening is
currently an assertion. Nothing counts the surfaces, so nothing notices a new
one landing.

The starter proved the measurement first, product-side: `scripts/
external_connector_sweep.py` classifies six categories from the parse tree, and
`tests/architecture/test_external_connector_ratchet.py` freezes the result. That
sweep also produced the correction this record carries. It miscounted
`InboxTeamRoundRobinCursor` in `dotmac_sub` — durable per-team ROTATION state
for inbox assignment, with a foreign key to local `service_teams`, a
`last_assigned_person_id`, a `rotation_count`, and zero external references. It
matched only because `cursor` was a substring hint.

A product-local copy of the detector in every repository would recreate exactly
the drift class ADR 0006 exists to prevent: six detectors, six thresholds, six
independently-weakened exemption lists. The accepted Governance engine owns it,
as it already owns the testing-kit boundary under ADR 0008.

The exemption discipline is inherited from starter ADR 0018: an exemption must
state an ENFORCEABLE premise, the ratchet moves in both directions, and every
detector carries a sensitivity proof rather than an assertion.

## Decision

Schema version 9 adds one mandatory `external_connector_surface` object to every
enrolled repository profile. It holds six baselines and the conserved exclusions
the repository has already reviewed, and nothing else.

Schema versions 7 AND 8 are WITHDRAWN AND NEVER ACCEPTED. Version 7 carried the
six baselines without conservation, so an exclusion was a silent subtraction.
Version 8 named one of those six `http_client`, after a single transport rather
than the concept, so a genuine SMTP delivery surface could hold no category at
all. Neither upgrades: each fails to load with a message saying it was
withdrawn, rather than silently gaining a rule family — or a vocabulary — it was
never reviewed against. Every adopter was pending approval when version 9
landed, so there is no migration path to preserve, which is exactly why both
invalidations were taken now rather than after a product had pinned one.

### Measured scope is DERIVED, never declared

An adversarial audit of the version-6 design produced `PASS mode=required`,
exit 0, on a repository holding six live provider connectors. The detectors
were not the weakness — all fifteen sensitivity mutants were caught. The SCOPE
layer was not a contract at all: `runtime_roots` was an unconstrained
self-declaration that needed only to be non-empty, to exist, and not to be
literally named `tests`. Six routes to a fully-green run were demonstrated:

| # | Route | Why it worked |
| --- | --- | --- |
| A | Declare only a clean corner of the source tree. | Scope was whatever the product said it was. |
| B | Declare a runtime root holding no Python. | Same, with the measured set empty. |
| C | Put the connectors in a directory named `migrations`. | A blanket name skip. |
| C2 | Put them in a package named `test`. | A blanket name skip. |
| C3 | Put them in a package named `alembic`. | A blanket name skip. |
| D | Keep them out of the index behind a `.gitignore` entry. | The inventory applied the product's own exclude rules. |

C, C2 and C3 were violations of this record's own inherited discipline. Nothing
checked that a directory named `migrations` contained migrations, so that region
was UNMONITORED, not exempt. This repository was vulnerable to the same class:
dropping two of its three declared roots hid a planted connector while all 159
tests passed, because the production-engine test asserted a `PASS` and nothing
whatsoever about what had been measured.

The repair is structural. A product no longer states what is measured:

1. The universe is the repository's own tracked Python inventory —
   `git ls-files --cached`, with NO exclude rules applied — plus every tracked
   extensionless file that is Python, because a repository's real entry points
   are routinely extensionless (this one ships two). Using the index rather than
   a directory walk means an untracked file cannot smuggle code into a count,
   and a `.gitignore` entry cannot smuggle code out of one.
2. A Python source on disk but outside the index reports
   `repository.source.untracked`. Unmonitored, not exempt.
3. If the inventory cannot be read, the run reports
   `repository.inventory.unavailable` and fails. An unmeasurable repository is
   not a conformant one.
4. There is no list of directory names that are "never runtime". A connector in
   a migration is a finding.

### The index is the authority, not the working tree (2026-08-15)

A second adversarial audit landed a live connector on a green tree seven more
ways. None of them touched a detector and none of them declared anything; every
one exploited the DERIVATION. The repairs are all of one shape — the index
entry decides, and reachability is not only an import edge:

| # | Route | Why it worked | Repair |
| --- | --- | --- | --- |
| E | A shebang that never says `python` (`uv run --script`, `pypy3`, `nix-shell`). | Python-ness was a word match against an open vocabulary. | A file claiming Python stays Python; one that does not is admitted by PARSING. |
| F | A `.pyw` source. | Any suffix but `.py` was rejected unread. | `.py` and `.pyw` both count. |
| G | A submodule, or a symlink to a directory outside the repository. | One index entry grafts a whole tree; `--cached` never lists it and `--others` never descends into it. | `repository.tree.unmeasured`, unconditionally. |
| H | Delete a tracked `.py` from the working tree; let a tracked symlink dangle; omit it from a sparse checkout. | Python-ness was `source.is_file()`, so the working tree decided what the index measured. This flipped a RED tree green with no diagnostic at all. | Suffix decides from the index entry; absent bytes fail closed as `connector.syntax.invalid`. |
| I | Wire a public connector through an `importlib` string or an assembled f-string path, and give it one honest unit test. | Only import edges counted as reachability, so the grow pass removed it. Writing the test bought the exemption; deleting the test turned CI red. | A dotted name in a string is an edge; an assembled dotted package prefix reaches everything under it. |
| J | `class TestFlightPaymentGateway`, a public runtime gateway. | A bare `Test` prefix made the module both "declares a test" and "offers no public surface". | A test class needs a `TestCase` base or a real `test_*` method. |
| K | A `test_connection` health probe, or a `test_delivery` method on a private alerter; the class hidden from `tree.body` by an optional-dependency guard. | The test declaration was found by walking the whole tree, and public surface was read only off `tree.body`. | Both are read at MODULE LEVEL, through `if`/`try`/`with` wrappers. |

Route H is the most serious of the seven, because it is the only one that turns
an already-failing build green rather than keeping a new surface invisible.

Route I also settles a question the first repair left open. There is no
structural difference between a test double reached only through a test helper
— which this record deliberately excludes — and a dynamically-wired production
connector reached only by its own test. Both are "nothing imports this but a
test". The line is drawn at REACHABILITY EVIDENCE rather than at intent: if
anything in the repository names the module, by import or by string, it is
reached. What remains outside that line is stated in the consequences below.

### A profile may not contradict itself

A path the profile itself declares to be runtime — an authority's owner
implementation, its canonical writers, its adapters, or a typed contract
surface — is never a candidate for the test-only exclusion. `drift_test_paths`
are deliberately not pinned, because the profile declares those to be tests.

Without this, a declared canonical writer holding a live provider client was
removed from the universe because the only source importing it was the drift
test the same profile declares. One half of a profile asserted the file was the
runtime owner of a business decision while the other half concluded it was test
scaffolding, and the disagreement resolved to a green build.

### The one exclusion, and the analysis that earns it

A connector faked inside a test is how a connector is verified, so test-only
code must leave the universe — but by PROOF, not by name or location. A source
is removed only when both hold:

- **Proven test-only.** It declares a test AT MODULE LEVEL — a module-level
  `test_*` function, or a module-level class a runner would actually collect (a
  `TestCase` base, or a `Test` prefix backed by a real `test_*` method) — offers
  no public module-level runtime definition beyond tests, pytest fixtures and
  `_`-prefixed helpers, and carries no `__main__` guard. The second clause is
  what stops a one-line `def test_ping()` bolted onto a live connector from
  buying it an exemption; the third is because an entry point runs without
  anyone importing it, so it can never satisfy the next clause.

  Both halves are read at module level and THROUGH `if`/`try`/`with` wrappers,
  and both are read as evidence rather than as a name. A `test_connection`
  health probe on a gateway is not a test declaration, a `Test`-prefixed product
  class is not a test class, and a public class defined under an
  optional-dependency guard is still public surface. Each of those three was a
  free exemption for an undisguised connector.
- **Unreachable.** Nothing outside the removed set reaches it, judged over the
  whole tracked inventory from imports — relative imports resolved and package
  prefixes counted — AND from dotted names held as strings, including a dotted
  package prefix assembled in an f-string, which reaches every module under it.
  Naming a module is treated as reaching it even when the string is incidental:
  the error lands on the side of measuring more, and costs only an exclusion
  nobody was owed.

The removed set is closed under the reachability rule and computed to a fixed
point in two monotone passes: seeds SHRINK while any of them has an importer
outside the set, then helpers GROW in while every importer of a helper is
already inside. That is what makes `A imports B imports C` work — removing the
provider double requires removing the helper, which requires removing the test.
A source that nothing imports at all is measured: being unreferenced is not
evidence of being a test.

Every removal is published as a `connector.scope.excluded` NOTICE naming the
file and the reason. Notices never fail a run; `conforms` counts errors alone.
The exclusion set is a reviewable output rather than an invisible skip.

### The six categories

| Category | Fires on |
| --- | --- |
| `outbound_transport` | Either of two arms. HTTP: a client library USED — named outside an `except` clause's exception type — AND a request-shaped call in the same module. SMTP: a transport library USED under the same `except` rule, OR a connection opened through `SMTP`/`SMTP_SSL` on a bound transport, OR a `sendmail` call (a `send_message` call only alongside a bound transport). |
| `webhook_surface` | A ROUTE decorator whose path literal reads as a provider callback — positional OR keyword, and a `callback`-shaped path only on a mutating route — or a signature-verification function that either NAMES a webhook or reads the inbound request (see "A name is not evidence" below). |
| `provider_credential` | An assignment naming BOTH a provider and secret material, whether bound to a name or an attribute. |
| `connector_task` | A scheduling framework, decorator, registration or dispatch in EXECUTABLE position, naming a connector-shaped subject. |
| `sync_checkpoint` | Durable position in an external feed — by class name, or by an actual watermark column in EITHER declaration style. |
| `delivery_retry` | A retry policy declared in an executable position — identifier, keyword, attribute, decorator or configuration literal — alongside a real outbound or inbound connector surface. |

The category list is closed and every profile declares a baseline for all six,
so a category cannot be dropped from a profile to make a count disappear.

#### Prose is inert in all six, and two of them were not (2026-08-15)

Acceptance check 4 — docstrings and comments remain inert — was run per
category and **failed for two of six**:

```
'celery' in a COMMENT only        -> ['connector_task']
'celery' in a DOCSTRING only      -> ['connector_task']
'max_retries' in a COMMENT only   -> ['delivery_retry', 'http_client']
(the second name is the category's spelling at the time; it is
`outbound_transport` from schema version 9 onward)
```

`_schedules_a_connector` and `_owns_delivery_retry` each opened with
`any(hint in source.lower() ...)` — a scan of the raw file text. Both rules are
CONJUNCTIONS, and that is why the defect outlived the existing inertness
proofs: a bare module with a connector word in prose never fired for any
category, because the second conjunct was unmet. The failing shape is prose
supplying the TEXT conjunct while ordinary, innocent code supplies the other:

* `connector_task` — a comment reading "unlike the celery path we retired" over
  `@functools.cache def sync_local_cache()`. An in-process cache refresh,
  scheduled by nothing, measured as a scheduled connector.
* `delivery_retry` — a comment reading "no max_retries here: the caller owns
  the retry policy" in a module that genuinely calls a provider. The second
  conjunct is satisfied by the very client the comment is disclaiming a policy
  for, so it could not catch the error; the module was measured as owning
  delivery machinery it explicitly does not own.

This is the error class already recorded in "A name is not evidence": something
that merely LOOKS like the thing taken as the thing. It is repaired the same
way — by reading context — and is NOT documented as a limitation, because a
governance rule a repository can only satisfy by rewording a comment is not a
governance rule.

**Both arms now read executable AST context only.** The vocabulary did not
change; where it is read did, so a corpus difference is attributable to context
alone. `connector_task` reads four arms — a scheduling-shaped DECORATOR on a
connector-shaped function, a `.delay()`/`.apply_async()`/`send_task()`
DISPATCH, a scheduler REGISTRATION call, and a `beat_schedule`-shaped TABLE
whose `task` entry names a connector. Importing a scheduling framework is
deliberately not a fifth arm: an import names no subject, and the
connector-shaped subject is the whole precision of the rule, so the import
serves as the QUALIFIER that promotes the two ambiguous spellings (`@app.task`,
`add_job`/`enqueue`) which mean nothing alone. `delivery_retry` reads five — a
retry identifier BOUND, a retry KEYWORD in a call, a retry ATTRIBUTE read, a
retry DECORATOR, and a retry-shaped string in a CONFIGURATION LITERAL.

That last arm is why the repair is not "stop looking at strings", and getting
it wrong would have traded one false negative for another. A retry policy
carried as data is the ordinary spelling: `{"max_retries": 3}` handed to a
client, or `IntegrationDelivery.state.in_(("dead_letter", ...))` selecting the
dead-lettered rows. What separates those from prose is POSITION and EXACTNESS,
and both are needed. Position: a mapping key, a subscript index and a call
argument are places a comment can never be, and a docstring — one
`ast.Constant` in statement position — reaches none of them. Exactness: a
configuration key or a state value IS the token, so the string must EQUAL a
retry word rather than contain one, which is what keeps
`log.info("no max_retries configured")` silent while `"dead_letter"` counts.
The retry DECORATOR arm is the one vocabulary addition (`@retry`,
`@backoff...`), confined to decorator position, because a decorated retry
policy has no identifier, keyword or mapping anywhere in the module to find.

**The corpus corrected the first draft of this repair, which is the point of
running it.** Measured over every readable worktree, the first draft dropped
two LIVE surfaces in `dotmac_sub`, and both were true positives wrongly lost
rather than false positives correctly cleared:

* `app/services/meta_pages.py` holds `_request_with_retry` — `max_retries:
  int = 1` in the signature, `while True`, `if retries >= max_retries: return
  response`, `Retry-After` honoured, `retries += 1` — a complete retry loop
  around an `httpx.AsyncClient` that BINDS nothing. Reading only bindings lost
  it. The identifier arm now reads any executable identifier position,
  parameters (`ast.arg`) and loads (`ast.Name`) included. "It accepts a policy
  rather than declaring one" is a distinction the code does not make: the loop
  is here.
* `app/services/web_integrations.py` selects the dead-lettered deliveries with
  `state.in_(("dead_letter", "reconciliation_required"))`. The token is a state
  VALUE in a call argument, which the mapping-key-only literal arm did not
  reach.

Neither would have been visible from the bench fixtures, and a repair validated
only against its own fixtures would have shipped both losses. That is the same
"correct on its fixture, inert on its subject" failure recorded for bounded
tracing, caught this time because the corpus diff is adjudicated FILE BY FILE
rather than by counts — a count would have shown the drop and hidden which two
files it was.

**The classifier no longer receives the source text at all.** `source` was
removed from `_classify_connector` and `_conserved_findings`, and the `sources`
dictionaries that fed them were deleted. That is a contract, not a tidy-up: a
rule cannot read what it is not given, so the regression is now
unrepresentable rather than merely absent. It also closed a live inconsistency
— the per-unit attribution path was passing `ast.unparse(unit)` as its
"source", a text channel that drops comments and keeps docstrings, so the two
analysis paths did not even agree on what prose was.

Inertness is now proved PER CATEGORY, in both prose forms, and in both
directions: six silence proofs paired with six bite proofs over the same words
in executable position, since a silence whose subject is invisible for an
unrelated reason proves nothing.

#### Liveness is proved PER ARM, not per category

A category-level proof lets a live arm conceal an inert one — the failure that
left bounded tracing resolving ZERO spellings across 5,626 real sources while
its direct arm looked precise. The six categories decompose into **21 arms**,
and each carries three legs: SENSITIVITY (a representative violation fires),
SPECIFICITY (the near-miss stays silent), and LIVENESS (the arm reaches and
correctly classifies REAL corpus code). An arm whose legitimate corpus count is
zero proves liveness by IN-SITU MUTATION inside the real repository scan —
plant, measure, remove — rather than by waiting for debt to exist.

Swept over the 6,584 measured sources of the seven repositories, the arms that
reach real code and the count of modules each reaches:

| Arm | Modules |
| --- | --- |
| `outbound_transport` / HTTP / client USED (named outside an `except` type) | 96 |
| `outbound_transport` / HTTP / request-shaped call | 2894 |
| `outbound_transport` / HTTP / DIRECT arm fires (both conjuncts) | 94 |
| `webhook` / unambiguous route path | 27 |
| `webhook` / verify fn NAMING its subject | 4 |
| `webhook` / bare verify fn READING the request | 1 |
| `credential` / name-bound | 20 |
| `credential` / attribute-bound | 1 |
| `task` / DECORATOR on a connector-shaped function | 60 |
| `task` / DISPATCH (`.delay`/`.apply_async`/`send_task`) | 26 |
| `task` / dispatch ATTRIBUTE handed by reference | 31 |
| `checkpoint` / CLASS NAME | 5 |
| `checkpoint` / COLUMN name | 41 |
| `retry` / policy declared in an executable position | 97 |
| `retry` / OVER a real connector surface (the finding) | 20 |

The SMTP arm was added later the same day and is swept separately, over 6,571
measured sources across the same seven repositories (the corpus moved slightly
between the two runs, so the two tables are not summed). Its three legs are
each LIVE in real code — the requirement is per leg, and an HTTP arm at 94
modules would otherwise have concealed all three:

| Leg | Modules |
| --- | --- |
| `outbound_transport` / SMTP / transport library USED | 7 |
| `outbound_transport` / SMTP / connection OPENED (`SMTP`/`SMTP_SSL`) | 6 |
| `outbound_transport` / SMTP / mail SENT (`sendmail`, qualified `send_message`) | 6 |
| `outbound_transport` / SMTP / ARM fires (any leg) | 8 |

The eight are `sub-adopt` `app/services/email.py`,
`app/services/web_system_export_tool.py`, `app/team_inbox_smtp.py` and
`scripts/one_off/send_important_account_batch.py`; `erp-adopt`
`app/services/email.py` and `app/tasks/email.py`; `academy-adopt`
`app/services/email.py`; and `crm-guardrails` `app/services/email.py`.

Two of those eight are worth naming individually. `erp-adopt/app/tasks/email.py`
is the witness this arm exists for — reached by the USED leg alone, since it
opens no connection and spells no send. `sub-adopt/scripts/one_off/
send_important_account_batch.py` is the mirror image: it is the one module
reached by the SENT leg WITHOUT the USED leg, calling `sendmail` on a relay it
did not construct and naming `smtplib` nowhere but an `except` clause. Neither
would be measured by the other's leg, which is the concrete reason the arm is a
disjunction of three rather than one rule with a second conjunct.

Three arms reach NOTHING in this corpus and are named rather than left to be
discovered: `task` / REGISTRATION call, `task` / SCHEDULE TABLE, and `webhook`
/ AMBIGUOUS path on a MUTATING route. The first two are pre-existing and hold
their liveness by in-situ mutation as above. The third is new, and its
emptiness is the intended shape: it exists to keep a POSTed `/callback` from
being retired along with the browser redirects, so having no live instance
today is the reason it is written as a qualification rather than as a deletion
of the word.

The three shapes the repairs of 2026-08-15 made inert are measured in the same
sweep: 8 modules hold a webhook-shaped literal on a NON-route decorator, 3 hold
an ambiguous `callback` path on a non-mutating route, and 2 name a client only
inside an `except` clause. Most of the first group keep `webhook_surface`
through a genuine route elsewhere in the same file; the modules that actually
LOSE a finding are the seven named in the gate above, and each was read at its
source before the rule moved.

### The category is the concept, not one transport (2026-08-15)

`erp-adopt/app/tasks/email.py` is a `@shared_task` that owns outbound mail
delivery. It holds tables of permanent and transient SMTP response codes,
classifies a failure into one or the other, and declares
`max_retries`/`retry_backoff`/`retry_jitter` over the send. It held NO CATEGORY
AT ALL.

It was never really seen. Until the false-friend repairs of the same day it
scored `connector_task`, because `send_email_async` contains the letters
`sync` — and when `sync` stopped matching inside `async`, the module went dark.
The repair was correct and the module was a true positive it happened to be
carrying; losing it was a real recall loss disguised as a false-positive fix.

The reason there was nowhere to put it is the NAME. `http_client` is a
transport, not a concept. Two ways out were available and both were refused:

- **Accept a documented blind spot.** Record in this ADR that SMTP is not
  measured and move on. Refused: a stated gap in the category list is exactly
  the "unmonitored rather than exempt" failure this record already forbids for
  directories, and a delivery task is the single most consequential outbound
  surface a product owns after HTTP.
- **File it under `http_client`.** Refused, and this is the worse of the two: a
  count is only useful if its name is true. A reviewer reading `http_client: 22`
  would be reading a claim about HTTP that includes a module which speaks no
  HTTP at all, and the next protocol would arrive with the same problem.

So the abstraction was fixed rather than worked around. The category is
`outbound_transport` — the concept, "this module reaches an external system
over the wire itself, rather than asking a control plane to" — and each
PROTOCOL is an arm beneath it. That costs a vocabulary change and therefore a
schema version; see "Version 8 is withdrawn" below.

#### The two arms are shaped DIFFERENTLY, on purpose

Reusing the HTTP arm's shape for SMTP would have re-lost the witness on the
first day, so the difference is stated rather than smoothed over.

The HTTP arm is a CONJUNCTION — a client library used AND a request-shaped call
— because `Client`, `Session` and a bare `.get(...)` all collide with things
that are not transports. The import alone overcounts; the call alone overcounts
far worse.

The SMTP arm is a DISJUNCTION of three legs, because `smtplib` and `aiosmtplib`
speak one protocol and nothing else, so naming one is already evidence:

| Leg | Fires on | Isolating witness |
| --- | --- | --- |
| USED | a bound transport name appears anywhere outside an `except` clause's exception type | `import smtplib` + `isinstance(exc, smtplib.SMTPResponseException)` — the real witness's shape, which opens no connection and spells no send |
| OPENED | `SMTP(...)`/`SMTP_SSL(...)` whose callee root is a bound transport module, or an alias imported directly from one | `from smtplib import SMTP_SSL as Relay` + `Relay(host, port)` — the module alias is never bound, so only this leg can answer |
| SENT | a `sendmail(...)` call, or a `send_message(...)` call in a module that has bound a transport | `relay.sendmail(...)` with no import at all — a relay handed in under a name this analysis cannot resolve |

Requiring a send as a second conjunct — the "make it look like the HTTP arm"
repair — is proved RED against the witness leg: it makes
`SMTP_RESPONSE_CLASSIFIER` silent again, which is the whole defect.

Three deliberate boundaries:

- **`sendmail` stands alone; `send_message` does not.** The same split the
  webhook path hints make between `webhook` and `callback`. `sendmail` is
  smtplib's own verb and nothing else in the corpus spells it; `send_message` is
  spelled by asyncio queues, websocket connections and broker clients, so it is
  qualified by a bound transport.
- **An imported CONSTRUCTOR name is not bound as a transport name.** Binding it
  in both places would make the OPENED leg unreachable on its own and its
  liveness unprovable — the failure ADR 0018 names. Nothing is lost: a module
  that constructs is measured by the leg that owns constructions.
- **The inert position is shared in CODE, not restated.** Both arms consult
  `_caught_client_positions`. `except smtplib.SMTPServerDisconnected` says
  somebody else opened the socket, exactly as `except httpx.HTTPStatusError`
  does, and a future change to that judgement cannot land in one arm only.

What the SMTP arm does NOT see, in the conservative direction: a mail API
reached over HTTP (SendGrid, Mailgun, SES) is measured by the HTTP arm and not
this one, which is correct — the transport really is HTTP. `email.message` and
`email.mime` BUILD a message and send nothing, so they are deliberately absent:
constructing a MIME part is not a transport surface. A module that hands a
message to a queue for something else to relay is not measured here at all.

#### One neighbour moved, and it had to

`delivery_retry`'s second conjunct asks whether a retry policy sits over a REAL
outbound or inbound surface. It read HTTP and webhooks only, so a retry policy
over a mail relay looked like a retry loop around a local queue. SMTP joined
that conjunct in the same change; leaving it out would have reproduced the
blind spot one category over, and the witness is precisely a module that
declares a retry policy over an SMTP send.

#### Version 8 is withdrawn

The vocabulary is part of the profile, so the schema moves to version 9 and
version 8 FAILS TO LOAD with a message saying it was withdrawn and never
accepted — exactly as version 7 does, and by the same mechanism rather than a
parallel one.

It does not upgrade quietly, and the reason is not tidiness. A version-8
profile declares a baseline under `http_client`, and that NUMBER was measured
by a rule that could not see SMTP. Renaming the key on the product's behalf
would carry a count forward as though it had covered a surface nobody counted,
which ratchets a gap into a green build. The message says what to do instead:
move to version 9, rename the key to `outbound_transport`, and RE-MEASURE it.
No accepted consumer exists — all four adopters were PENDING-APPROVAL when
version 9 landed — so this is the last moment at which fixing the abstraction
costs nothing.

### Both column declaration styles count

A watermark column declared the modern way
(`last_synced_at: Mapped[datetime] = mapped_column(...)`, an `ast.AnnAssign`)
and the classic way (`last_synced_at = Column(DateTime)`, an `ast.Assign`) is
the same column. Reading only the annotated form was blind to every pre-2.0
SQLAlchemy model — and that column net is precisely what the "narrowing the
bare `*Cursor` rule costs no recall" claim below rests on, so the blind spot
was load-bearing. The same assignment-shape correction applies to provider
credentials bound to an attribute (`self.stripe_webhook_secret = ...`), and the
same argument-shape correction to a route mounted with `path=` rather than
positionally.

One blind spot of the SAME family was found OUTSIDE these six categories and is
deliberately NOT fixed here: `_closed_storage`, the ADR 0007 module-declared
vocabulary check, also inspects only `ast.AnnAssign`, so a classic
`topic = Column(sa.Enum(...))` re-closes an open vocabulary invisibly. That is a
finding against ADR 0007, raised rather than silently widened into this change.

### Bounded tracing: one hop of project-local indirection (2026-08-15)

The consequence this record carried — that the undercount is far larger than
"deliberate precision" implies, and that the record is not adoptable until that
is settled — is addressed here for the INDIRECTION class of misses. It is not
addressed by widening the vocabulary of names, which is what produced five
docstring false positives in the earlier prototype. It is addressed by
resolving, semantically and within a stated bound, the one hop that hid two
thirds of a real connector.

The demonstration case is a genuine ERPNext connector:

```python
from myapp.settings import settings
from myapp.transport import make_client
from sqlalchemy import Column, DateTime

def _client():
    return make_client(base_url=settings.erpnext_url, token=settings.erpnext_token)

class SupplierMirror:
    last_synced_at = Column(DateTime)

def sync_suppliers():
    return _client().get("/api/resource/Supplier")
```

The engine reported `sync_checkpoint` and nothing else. The module holds an
HTTP client and an ERPNext credential, but it BINDS neither: the client arrives
from a project-local factory and the credential arrives as an attribute read.
Every rule read what a module bound, so one level of ordinary structure was a
complete hiding place. It now reports `outbound_transport`,
`provider_credential` and `sync_checkpoint`.

#### The bound, normatively

Tracing is bounded in five stated ways, and the bound is part of the contract
in exactly the way the six categories' blind spots are:

1. **Project-local only.** A name resolves only into a module in this
   repository's own tracked inventory — the same inventory the reachability
   graph is built over. A name imported from a package the inventory does not
   contain is third-party and is not followed. The engine does not model
   dependencies it cannot read.
2. **Two rounds.** Resolution runs `MAX_TRACE_ROUNDS = 2` monotone rounds
   outward from a direct HTTP client constructor. That reaches
   `caller -> factory -> constructor`. A third link in the chain is NOT
   resolved. The undercount is stated rather than discovered.
3. **Cycle-safe by construction.** Rounds are a fixed point over a finite set
   of names, so mutually recursive factories terminate instead of recursing.
4. **Node shapes only.** Nothing added here reads raw source text or sweeps
   string constants. A docstring is one `ast.Constant` and a comment is not in
   the parse tree at all, so both are inert — proved directly, in both
   directions, against the connector above.
5. **No type inference.** A receiver resolves only when it is literally a call
   to a name already proved to yield a client, or a local name assigned from
   exactly such a call. There is no attempt to know what an arbitrary
   expression evaluates to.

#### What is traced

- **A client factory.** A module-level function whose own `return` constructs a
  client — `httpx.Client(...)`, `requests.Session()`, `http.client.HTTPConnection()`
  — is a factory. The constructor's ROOT must be a client module this file
  imported, under whatever alias, because the bare attribute name `Session` is
  shared with `sqlalchemy.orm.Session` and matching it alone makes every ORM
  session a client. Returns are read per scope: a closure's return is not its
  enclosing function's.
- **A MEMOISING client factory.** A function that binds the client to a local
  and returns the local is a factory too, provided the binding sits in that
  same function body and its right-hand side is itself a client construction or
  an already-resolved factory call. This clause is not a convenience. Matching
  only the textbook `return <constructor>` shape left the entire trace
  resolving ZERO spellings across 5,626 measured real sources — 39 of which
  construct a client, and none of which returns one directly. Every real
  factory in the subject repositories memoises, because a pooled or lazily
  built client is the point of having a factory at all (`dotmac_sub`'s
  `crm_client._pooled_client` and `core_router_metrics._get_client`). A
  detector correct on its fixture and inert on its subject is worse than an
  honest undercount, because it reads as coverage. It costs no bound — the
  binding must be in the SAME function body, so this is still one function and
  still two rounds, not a third link — and it is proved in both directions: a
  memoising factory over a MAPPING is the identical statement shape and must
  stay unresolved. It added no new hit in any repository (see the gate below);
  it is recall held against the next connector, not a count today.
- **A factory across the import graph.** THREE spellings of one import edge,
  and they are spellings rather than links: `from p.transport import
  make_client` carries the factory as `make_client`; `import p.transport`
  carries it as `p.transport.make_client`; and `from p import transport` binds
  the MODULE and carries it as `transport.make_client`.

  The third was missing until the tracing-evasion audit, and it is the spelling
  this fleet actually writes — 19,155 such calls across 1,542 modules in
  `sub-adopt`, 1,056 in the starter, 660 in `academy-adopt`, 495 in
  `erp-adopt`, 387 in `vcp-adopt`. Its absence was the re-export blind spot
  again, in a commoner idiom: driven end to end through `verify_repository`
  over two git fixtures holding the same connector, `from erpnext.transport
  import make_client` produced `connector.baseline.exceeded` and `from erpnext
  import transport` produced a conformant report. A caller's import style is
  not a fact about whether the product holds a connector.

  Bounded like the other two: the submodule must be in the repository's own
  tracked inventory and must already own or republish a name proved to yield a
  client. Gated over six repositories — every measured count identical, and one
  real factory newly reached (`sub-adopt app/web/admin/network_core_devices.py`
  now sees `core_router_metrics._get_client`, which it holds without calling,
  so nothing was added to a baseline).
- **A RE-EXPORTED factory.** A package that publishes its transport through its
  own `__init__.py` — `from p.transport import make_client` at the package
  root, so callers write `from p import make_client` — republishes the factory
  under its own module name, and the republished spelling is traced. What
  travels between modules is a module's EXPORTED set: the factories it defines
  plus the ones it republishes.

  This closed a hole that was not a bound but a BLIND SPOT, and the distinction
  is why it had to be fixed rather than stated. Resolution read the factories a
  module DEFINES; a pure re-export module defines none, so the factory died at
  the package root. Raising `MAX_TRACE_ROUNDS` did not reach it — measured
  directly at 2, 3, 5, 10 and 50 rounds, all unresolved — because a module with
  no `def` never becomes a factory owner in any number of rounds. The
  observable effect was that the detector was conditional on a product's
  PACKAGING STYLE. Driven end to end through `verify_repository` over two real
  git fixtures holding the same ERPNext connector and differing only in whether
  the caller imported the factory from its defining module or from the package
  root, one produced `connector.baseline.exceeded` and the other a fully
  conformant report. Publishing a package's public API from its `__init__.py`
  is ordinary Python and not an evasion, which is exactly what made it a
  blocker: a product could adopt this contract, hold a real connector, and be
  green.

  It is a RENAME, not a link, and bounded as one: the source module must
  already OWN the name, so a re-export of a re-export is a third link and stays
  unresolved. Proved in both directions — a re-exported MAPPING factory is the
  identical statement in the identical place and must resolve nothing,
  otherwise the clause would read "trust every re-export" and make every
  package root a client source.

  `from p.transport import *` republishes the same names as listing them one by
  one, and is read the same way: reading only explicit aliases would have left
  a one-word evasion of the clause. Its own bound is Python's rule rather than
  a chosen one — and Python's rule is `__all__` FIRST, with the underscore
  convention applying only in its absence. The first spelling of this clause
  read the underscore alone and stated the bound as "the language will not
  carry a private name", which is not true and therefore not enforceable: with
  `__all__ = ["_build"]` in the defining module, `import *` DOES bind `_build`
  at the package root and `from chain import _build` runs. Verified against the
  interpreter, and it left the clause evadable by one line — in a corpus whose
  real factories (`_pooled_client`, `_get_client`) are exactly the private
  names `__all__` would carry. `__all__` is now read, once per module, outside
  the rounds; an `__all__` this analysis cannot evaluate (built by
  concatenation or comprehension) falls back to the underscore rule, which is
  the conservative direction. Naming a private factory explicitly in the
  re-export still carries it, which is what makes the star proof a proof of the
  star rule and not merely of the underscore.

  Measured through the gate below: zero new hits and zero lost hits in all six
  repositories, because none re-exports a factory today. The star clause was
  gated separately and more sharply — it can only add a name where a module
  star-imports from a project-local module owning a PUBLIC factory, and that
  condition holds nowhere in the corpus. Like the memoising clause, this is
  recall banked against the next connector rather than a count now.
- **A request through a resolved factory.** `_client().get(...)` and
  `client = _client(); client.get(...)` are outbound requests without this file
  importing any client library. The local-name form is name-level and
  scope-blind, which is the documented cost of clause 5.
- **A request through a module-local factory that ADDRESSES A REMOTE URL.**
  `_client().get("https://erp.example.com/api/resource/Supplier")` counts even
  when the transport underneath is third-party and therefore unresolvable. This
  is the one rule that does not terminate at a constructor, so the URL literal
  carries the whole claim — and it must therefore be a string that only a
  remote address can be. A SCHEME is that. A leading slash is not: see "The
  slash that was not a URL" below. A decorator call is excluded — mounting a
  route is not issuing a request.
- **A credential READ, not only a credential BOUND.**
  `settings.erpnext_token` names both a provider and secret material, and a
  module that reads it holds it. The receiver must be configuration-shaped —
  `settings`, `cfg`, `config`, `environ`, `tenant_config`, `get_settings()` —
  matched EXACTLY against a name part rather than as a substring, so `envelope`
  is not `env`. That is the bound: `payload.stripe_api_key` is somebody else's
  credential passing through an inbound request, not one this repository holds,
  and it is deliberately not followed.
- **Delivery retry around a traced request.** Retry machinery counted only
  alongside an imported client or a webhook route; it now also counts alongside
  a TRACED outbound call, because that is the same surface reached one hop away.

#### The false-positive gate this widening had to pass

Recall may only be bought with evidence that precision holds, and the earlier
prototype failed exactly there. The measurement, taken against six real
repositories before and after the change, over the derived measured universe:

| Repository | Category | Before | After | New |
| --- | --- | --- | --- | --- |
| academy-adopt | provider_credential | 2 | 3 | 1 |
| erp-adopt | provider_credential | 4 | 6 | 2 |
| sub-adopt | provider_credential | 2 | 3 | 1 |
| all six repos | every other category | — | unchanged | 0 |

No count FELL anywhere, which matters on its own: a fall is what emits
`connector.baseline.stale` and instructs a product to lower its baseline.

All four new hits were opened and judged, and all four are true positives —
each one a module that reads a provider secret out of configuration and uses it
in the product's own runtime:

| File | Expression | Verdict |
| --- | --- | --- |
| `academy-adopt app/services/email.py:84` | `smtp.login(cfg.smtp_user, cfg.smtp_password)` | True positive: authenticates an outbound SMTP session with a held provider credential. |
| `erp-adopt app/services/storage.py:61` | `Minio(..., secret_key=settings.s3_secret_key)` | True positive: constructs a provider client from a held provider credential. |
| `sub-adopt app/services/object_storage.py:291` | `S3StorageService(..., secret_key=settings.s3_secret_key)` | True positive: same shape, same category. |
| `erp-adopt app/dependency_health.py:172` | `bool(... and settings.s3_secret_key)` | True positive, and the weakest of the four: the module only tests the secret for truthiness. It still reads provider secret material in product runtime, which is what the category measures. |

The memoising-factory clause was measured through the same gate, separately,
and moved no count in any repository: it makes the trace resolve where it
previously resolved nothing (`sub-adopt` goes from 0 to 2 modules with a
resolved factory spelling, 1 of which fires the traced-request rule), and every
module it newly reaches was ALREADY counted by the direct import rule. Zero new
hits, zero lost hits. That is the honest description of it: precision proved,
recall banked, count unchanged.

The RE-EXPORT clause was gated the same way and also moved no count. It was
measured over each repository's WHOLE tracked inventory rather than the derived
measured universe — a superset, so a zero delta over it is a zero delta over
any subset the derivation produces, and it does not inherit the derivation
defect recorded below:

| Repository | Modules | Categories before | Categories after |
| --- | --- | --- | --- |
| starter-spi-modes | 492 | 1 / 0 / 0 / 0 / 2 / 0 | identical |
| sub-adopt | 4,727 | 50 / 4 / 5 / 18 / 12 / 13 | identical |
| erp-adopt | 2,725 | 23 / 14 / 6 / 13 / 16 / 7 | identical |
| academy-adopt | 363 | 3 / 0 / 3 / 0 / 0 / 0 | identical |
| vcp-adopt | 115 | all zero | identical |
| gov-ratchet | 20 | all zero | identical |

Counts are `outbound_transport / webhook_surface / provider_credential /
connector_task / sync_checkpoint / delivery_retry`, and every figure in this
table predates the SMTP arm, so the first column is the HTTP arm alone. They are the counts as this
clause was gated; the signature-arm repair recorded below subsequently moved
`erp-adopt`'s `webhook_surface` from 14 to 13, and nothing else. The reason the
delta is
zero is worth stating rather than celebrating: no repository in the corpus
re-exports a client factory today, and only `sub-adopt` defines one at all.
That is the same shape as the memoising clause — the hole was real and
end-to-end demonstrable, and closing it costs nothing now because no product
has yet written the code it catches. It is precisely the code a product WILL
write when it moves its transport behind a package boundary, which is the
migration this record exists to watch.

The three tracing-evasion repairs (the submodule import spelling, `__all__` in
the star clause, and the scheme requirement in the module-local request arm)
were gated together over the same six repositories, both universes, with the
before and after engines run alternately in ONE process against the SAME parsed
trees so a loaded machine cannot masquerade as a delta:

| Repository | Measured | Counts before → after | Conserved before → after |
| --- | --- | --- | --- |
| sub-adopt | 2,959 | 41 / 4 / 3 / 18 / 11 / 8 → identical | 16 → 13 |
| erp-adopt | 2,140 | 21 / 10 / 6 / 12 / 15 / 5 → identical | 8 → 8 |
| academy-adopt | 156 | 2 / 0 / 3 / 0 / 0 / 0 → identical | 1 → 1 |
| vcp-adopt | 87 | all zero → identical | 0 → 0 |
| gov-ratchet | 20 | all zero → identical | 0 → 0 |
| starter | 277 | 0 / 0 / 0 / 0 / 2 / 0 → identical | 1 → 0 |

Every measured count is identical: zero new hits and zero lost hits, in all six
categories of all six repositories. The four conserved records that disappear
are the four false ones — the `TestClient` call sites described under "The
slash that was not a URL" — and none appears. One real factory spelling is
newly reached (`sub-adopt app/web/admin/network_core_devices.py` now sees
`core_router_metrics._get_client` through `from app.services import
core_router_metrics`), which is recall banked without a count.

**No exception ledger was required.** The governance-owned exact exception
ledger this record's decision reserves for an unavoidable false positive was
not built. Two false positives were later confirmed on real code — the
signature arm below, and the slash rule above — and both were repaired by
making the RULE precise, which is the repair the decision asks for first; a
ledger is for a false positive that cannot be ruled out, and neither could.
Nothing in this change gives a product local suppression authority, and the
mechanism is still absent by design.

#### A name is not evidence, and the signature arm forgot it (2026-08-15)

The `webhook_surface` category has two arms. A route decorator whose path
literal reads as a provider callback is a mounted receiver and is evidence on
its own. The second arm existed because a real provider callback is routinely
SPLIT — the route in one module, the signature verification beside the secret
in another — so a route-literal rule alone measures the half that does not hold
the credential. That arm read a FUNCTION NAME: any `verify_signature`,
`verify_webhook` or `check_signature` made its module a webhook surface.

That is a name rule with no premise, which is the discipline this record
enforces on the exclusion side and had not applied to itself. It produced a
confirmed false positive on real code:

`erp-adopt/app/licensing/validator.py` is an offline Ed25519 licence-file
verifier. It loads a file from a `Path`, checks a detached signature against an
embedded public key, imports no HTTP client, mounts no route and touches no
socket. It was measured `webhook_surface` because a correctly named function is
called `verify_signature`.

This is the most serious defect shape this record can carry, because there is
no product suppression and there never will be: the only repair available to
that repository was to rename a correct function to satisfy a governance rule.
An unfixable finding in somebody else's repository is how a guard gets switched
off wholesale.

The repair splits the arm by how much the NAME commits to:

- a verification function whose name carries the word `webhook` names its own
  subject, and stays evidence by itself;
- a bare `verify_signature` or `check_signature` names nothing, and must earn
  the finding by ALSO reading the request it verifies — a `request`, `headers`,
  `header`, `raw_body` or `request_body` identifier in the same function.

Measured over every git-tracked Python source in the six repositories — 8,440
modules, a strict superset of every derived measured universe — exactly ONE
file changes classification, and it is the false positive:

| | Before | After |
| --- | --- | --- |
| `webhook_surface` | 18 | 17 |
| every other category | 77 / 14 / 31 / 30 / 20 | identical |
| files whose classification changed | — | 1 (`erp-adopt/app/licensing/validator.py`) |
| true positives lost | — | 0 |

The three unrouted verifiers that the arm exists for stay measured, and they
prove the split rather than merely surviving it: `mono_client.verify_webhook`
and `paystack_client.verify_webhook_signature` carry the word and take the
header or the raw payload as a bare parameter, so a premise written only as
"reads a request object" would have LOST both — that was the first attempt, and
the corpus measurement caught it. `crm_webhooks._verify_signature` carries no
word and reads `request.headers`, so an arm written only as "the name says
webhook" would have lost that one instead. Both halves are load-bearing.

The bound is stated, and it is the conservative one: a bare-named verifier that
reaches its request through a spelling not in the list is UNDERCOUNTED. Given
there is no product suppression, an undercount is a miss the ratchet can be
raised for later, while a false positive is unfixable by the repository holding
it. Those two errors are not symmetric and this arm is not tuned as if they
were.

#### Three more names taken for evidence, and two repairs that were refused (2026-08-15)

A false-positive hunt across the fleet found the same error class three more
times. All three are fixed at their source; there is no exception ledger, and
a rule a repository can only satisfy by renaming its own code is not a rule.

**A celery task name is not a route path.** The path arm harvested string
constants from ANY decorator call, so
`@celery_app.task(name="app.tasks.webhooks.retry_failed_deliveries")` reached
the webhook rule looking exactly like a mounted path. It is a queue
identifier. It COMPOUNDED, which is what makes it a blocker rather than a
miscount: a phantom webhook surface satisfies the second conjunct of
`delivery_retry` — the guard whose whole job is to stop a retry loop around a
LOCAL queue counting as delivery machinery — so one string constant
manufactured two findings in a module holding neither surface. Driven
directly, the same module with only the task-name string changed classified as
nothing at all. The path arm now reads ROUTE decorators only, matched on the
final dotted part (`@router.post`, `@app.get`, `@blueprint.route`). Measured
across seven repositories, exactly two modules rested their `webhook_surface`
on a non-route decorator — `crm-guardrails/app/tasks/webhooks.py` and
`app/tasks/webhook_health.py`, both celery task names — and both keep their
genuine `outbound_transport`, `connector_task` and `delivery_retry`.

**`callback` is an ambiguous path word.** `webhook`, `/hooks`, `notify-url`
and `ipn` name a provider callback and nothing else. `callback` is equally the
URL a BROWSER is redirected to after an OAuth consent screen or a hosted
checkout, and all three real matches across the adopters are exactly that:
`erp-adopt/app/web/auth.py`'s `/auth/oidc/callback`, its Paystack
payment-return page, and `crm-guardrails`'s Meta OAuth return. The
discriminator is the one this record already applies to a bare `*Cursor` and
to `@app.task` — an ambiguous word must be qualified — and the qualification
is the route's METHOD.

The qualification is confined to the ambiguous word DELIBERATELY, and that
boundary is the counter-direction proof. Meta verifies a webhook subscription
with a GET carrying `hub.challenge`; `crm_webhooks.whatsapp_webhook_verify`
and `inbox_webhooks.verify_meta_webhook` are both genuine receivers mounted on
GET. A blanket "a webhook route must be mutating" rule — which is the repair
the false-positive sweep proposed — would have retired them. That is the
wrongly-lost-true-positive error, and it is the worse of the two, because
nothing announces it.

**A client that is CAUGHT is not a client that is CALLED.** The category
(then called `http_client`) asked whether a client library was IMPORTED and whether anything named
`get`/`post`/… was called; neither question reads a receiver. A module that
delegates every outbound call elsewhere and imports the library only to name
its exception classes therefore scored the surface off its own
`payload.get(...)` accessors. Two real modules, the same shape:
`crm-guardrails/app/services/crm/conversations/comments.py` (one `httpx`
reference in the file, `except httpx.HTTPStatusError`; all 33 request-named
calls are mapping accessors; the requests are `meta_pages`', and `meta_pages`
is measured on its own account) and `sub-adopt/app/tasks/notifications.py`.
The arm now requires the client to be named outside an `except` clause's
exception type.

That boundary was found by PROOF, not argued, and it is worth recording
because the wider rule looks like the same idea. Excluding ANNOTATIONS as well
reads as this record's own long-standing claim that "importing a client for a
type annotation is not a connector" — but an annotated parameter is how an
already-constructed client is handed in, and `client.post("https://…")` under
`def deliver(client: httpx.Client)` is an outbound request in every sense. The
wider rule silently retired three of this record's own fixtures
(`PLANTED_DELIVERY_RETRY`, `CONFIG_MAPPING_RETRY`, `DECORATED_RETRY`) while
costing nothing in the corpus, so the corpus gate alone would not have caught
it. `INJECTED_CLIENT_CALLED` pins the boundary. The annotation-only module
stays silent through `_issues_a_request`, which is where the separation always
lived.

**The gate.** 6,584 measured sources across seven repositories, before and
after. Exactly seven modules moved and every one is one of the three shapes
above: `outbound_transport` (HTTP arm) 96 → 94, `webhook_surface` 21 → 16,
`delivery_retry`
21 → 20; `provider_credential` 20 → 20, `connector_task` 47 → 47,
`sync_checkpoint` 33 → 33. All 111 pre-existing fixtures in the record's test
module classify identically.

**One new undercount, stated.** `sub-adopt/app/tasks/notifications.py` owns a
real retry policy over a real delivery, but the outbound call lives one module
away in `meta_pages`, so the module now holds neither conjunct and loses
`delivery_retry` as well. Recognising it needs cross-module dataflow the
engine does not do; the alternative — counting a module because it catches
somebody else's exceptions — is precisely the false positive.

**Two repairs the sweep proposed are REFUSED, each with the counter-example
that blocks it.** Neither is an exemption: both findings are real, and both
proposed rules were measured to cost more than they buy.

* `sync_checkpoint` reads a bare local binding. Three measured modules hold no
  checkpoint and are counted for one: `crm-guardrails/app/web/admin/
  billing_risk.py` (`last_synced_at = _latest_subscriber_sync_at(db)`, a local
  in a dashboard route), `sub-adopt/app/services/
  team_inbox_audit_reconstruction.py` (`watermark = "|".join(…)`, a staleness
  token over local tables), and one more. The proposed narrowing — drop bare
  function-local bindings — ALSO drops `sub-adopt/app/services/
  integration_sync.py`, which reads and writes a real `IntegrationCheckpoint`
  over a CRM feed and whose only column-hint binding is the local
  `watermark = _checkpoint_watermark(db, job)`. Adding dict-key and keyword
  positions to compensate reinstates `billing_risk.py`, whose template context
  is `{"last_synced_at": …}`. No discriminator separating the three from the
  one has been demonstrated, so the arm is unchanged and the overcount is
  recorded here instead of a rule being guessed at.
* Test doubles are measured as connectors. `sub-adopt/tests/
  test_dotmac_erp_outbox.py` stays in scope because it offers a public
  `FakeERPClient`; `erp-adopt/tests/conftest.py` and `tests/e2e/conftest.py`
  stay because a `conftest.py` declares no test. The implied repair — stop
  letting a public runtime definition disqualify a scope candidate — was
  measured directly and excludes LIVE RUNTIME CODE in three of seven
  repositories: `dotmac_starter_mt/app/features/parties/service.py` and
  `web.py`, `erp-adopt/app/web/admin_dotmac_sub_sync.py`,
  `app/services/people/payroll/lifecycle.py`. That is a silent coverage
  reduction and is exactly what the `offered` clause exists to prevent. The
  derivation is unchanged.

#### The cost of a rule that reads imports, and why it is paid once

Adding the re-export clause naively MORE THAN DOUBLED the trace on the largest
measured repository: `_trace_client_factories` over `sub-adopt`'s 4,727 tracked
modules went from a 29.4s median to 64.4s. The cause is structural rather than
incidental — both import-reading rules walked the whole parse tree, inside the
round loop, so the cost scaled with the NUMBER OF RULES THAT READ IMPORTS
rather than with the repository. A third such rule would have cost as much
again.

Imports are therefore walked and resolved ONCE per module, before the rounds,
into a `_ModuleImports` record both rules consume. Nothing about what resolves
changes — the same nodes, the same targets — so it is a hoist and not a
widening, and every tracing assertion plus the adversarial evasion and
reverse-direction probes return identical verdicts across it.

One measurement discipline is worth recording with it, because the first
attempt got it wrong. Scaling was initially measured on sorted path PREFIXES of
the corpus, which is not a sample: the alphabetically first eighth of
`sub-adopt` is mostly small migration modules, and the resulting curve showed
an alarming superlinearity that was an artifact of the sampling rather than a
property of the analysis. Scaling is measured on RANDOM subsets.

#### The slash that was not a URL

The module-local request arm is the one rule with no constructor underneath it,
so its string literal is its entire evidence. It first accepted any literal
beginning with `/`, and shipped one counter-example: `_rows().get("key", "")`
must stay silent. That counter-example passes for the wrong reason. `"key"` is
not path-shaped, so it never reaches the discriminator at all, and the rule was
never tested against the string it actually turns on.

A leading slash is not evidence of a remote resource. `"/admin"` in a
permission map, `"/health"` in a route table and `"/api/v1/..."` handed to an
in-process ASGI test client are the same string as a request path, and the
receiver — a module-level function this analysis could not resolve — says
nothing either way. Measured over every tracked source in six repositories, the
slash rule found five call sites and all five were
`starlette.testclient.TestClient`: `sub-adopt
tests/test_field_expense_categories.py` (twice),
`tests/test_integration_installation_api.py`, `dotmac_starter_mt
tests/unit/test_brand_projection.py` (twice). An in-process call to the
application under test is the definitional opposite of an external connector,
and this record's own scope rule says so: a test that fakes a provider is how a
connector is verified, not a connector.

Those five did not sit in the measured universe — they are test files, which
the derivation excludes — so they surfaced where the exclusion path publishes
them: as `connector.conserved` records, three in `sub-adopt` (including a
`delivery_retry` riding on the same false outbound) and one in the starter,
where it was the ONLY conserved record that repository publishes. A ledger
entry is an instruction to a reviewer to transcribe and re-review a finding, so
a false one is not a rounding error. The same shape in a measured file emits
`connector.baseline.exceeded`, which is an error, and no product suppression
exists: reproduced end to end, a module holding nothing but

    def _permissions() -> dict[str, str]:
        return {"/admin": "staff"}

    def required_role() -> str:
        return _permissions().get("/admin")

reports `outbound_transport: 1 measured sources exceed the declared baseline 0`, and
adding an unrelated `MAX_RETRIES = 3` adds `delivery_retry` on top, because a
traced outbound satisfies the second conjunct of the retry rule. That is the
unfixable red this record has refused everywhere else.

The rule now requires a SCHEME. The bound this buys is stated in the
conservative direction: a project-local transport wrapper the factory trace
could not resolve, called with a RELATIVE path against a client library not in
`HTTP_TRANSPORTS`, is UNDERCOUNTED. It costs nothing measured — the arm
contributed zero hits to the measured universe of all six repositories, and the
flagship ERPNext fixture still scores `outbound_transport` because its `_client` is
resolved as a factory rather than through the URL — and the two errors are not
symmetric.

#### What is still not traced, and stays stated

A factory three links from its constructor, counting from the CALLER: the
factory itself resolves at that depth, its caller does not (measured directly:
`caller -> f2 -> f1 -> constructor` resolves, one link further does not). A
client bound to a module-level name and imported as a VALUE rather than
produced by a call. A client constructed inside a METHOD and held on `self` —
`self._client = httpx.Client(...)` behind a `_get_client(self)` accessor, which
is the second real shape found in the subject repositories (`erp-adopt
paystack_client.PaystackClient`) — because a factory is module-level here and
resolving an instance attribute is the type inference clause 5 refuses. A
memoising factory that binds its client through an INTERMEDIATE local
(`client = httpx.Client(...)`, then `_CACHED = client`, then `return _CACHED`):
the binding clause reads one assignment, not a chain of them. A client
constructed inline in a `with` block. A transport wrapper whose own client
comes from a third-party dependency and whose call sites address no remote URL
literal. A credential read off a receiver that is not configuration-shaped.
Each is an honest, stated undercount, and each is the same trade this record
has made throughout: an undercount that shrinks beats an overcount that gets
switched off.

One refinement is worth recording, because it says where the remaining recall
actually sits. Adversarial probing of the receiver shapes — a client held on
`self`, kept in a registry dict, wrapped in `functools.partial`, or bound to a
class attribute — found that in every one of them the FACTORY now resolves and
only the RECEIVER does not. The trace reaches the transport; what it declines
to do is decide that `self._client`, `CLIENTS["erpnext"]` or `partial(make)()`
evaluates to it, which is clause 5 doing exactly its job. That makes the
receiver rule, not the factory trace, the next place recall can be bought — and
it must be bought the same way the clauses above were: a widening, a
counter-direction proof, and the six-repository gate, because attribute and
subscript receivers are far commoner than factory calls and the precision risk
is correspondingly larger.

None of those undercounts hides a surface today: every one of the 39 measured
sources that constructs a client also imports the client library and issues a
request in the same file, so the DIRECT rule counts all of them. The trace is
what keeps that true once a product moves its transport one module away.

### Exclusion conservation: what leaves the universe is recorded

The consequence this record carried — that an exclusion is a SILENT
SUBTRACTION, that the counts of what left are not ratcheted, and that every
route found so far has been closed at the classifier, which is a defence that
must hold perfectly rather than one that fails safe — is answered here.

A source proven test-only left the universe with nothing but a
`connector.scope.excluded` notice, indistinguishable from every other notice.
Nothing recorded WHAT left. An unsound classifier could remove a live provider
client and the only trace was one more line in a list nobody diffs.

Conservation records it. Every connector-shaped surface inside an excluded
source becomes a `ConservedFinding`, and the profile declares the set it has
reviewed. Conformance is set equality.

#### Only connector-shaped findings are conserved

Not every test file. A test module holding no connector surface records
nothing at all. Conserving the whole suite would put hundreds of entries in
every profile and bury the one a reviewer has to look at, which is the same as
recording nothing while feeling thorough. The narrowness is the mechanism.

#### The record: four coordinates, all of them load-bearing

| Field | What it pins |
| --- | --- |
| `path` | The exact tracked source removed. A literal file, never a pattern. |
| `symbol` | The module-level definition holding the surface, or `<module>`. |
| `category` | Which of the six the finding was classified as. |
| `fingerprint` | A SHA-256 over the NORMALIZED parse tree of the WHOLE excluded module. |

The match is keyed on the first three and the fingerprint is checked on every
match, so mutating any one of the four breaks the entry. An entry that matched
on path alone would be a file-level waiver wearing a fingerprint.

A symbol's UNIT is the module's own imports plus that one definition, which is
what makes a per-symbol classification meaningful: a request call means nothing
without the import that types it. The `<module>` unit is the imports plus every
module-level statement that is not a definition, and it is also the fallback —
a category no single definition accounts for is recorded against `<module>`
rather than dropped, so the conserved set always covers exactly what the module
was classified as. The module's own classification is authoritative;
attribution may name which symbol holds a category, never invent one.

A unit decides the SYMBOL only. **The fingerprint is the whole module's**, and
that is a correction to an earlier draft of this record rather than a
preference. The units of a file do not cover the file, so a per-unit hash left
three holes. Each was demonstrated against the engine — declared, reviewed,
green — before it was closed:

| Hole | Ordinary code that opens it | What could then be rewritten under a declared entry |
| --- | --- | --- |
| A module-level statement sits only in the `<module>` unit, which becomes a RECORD only when some category falls back to it | a base URL and a token bound at module scope, the call in a function | the endpoint and the credential: a sandbox double re-pointed at a production host with a live secret |
| A definition shadowed by a later one of the same name sits in NO unit | a `try`/`except ImportError` definition pair guarding an optional dependency | the whole first body: a stub swapped for a live exfiltration call |
| The unit builder flattens `with`/`if`/`try` and keeps only the wrapped statements | a module-level request inside a mocking context manager | the mock itself, whose removal makes the call live at import time |

In all three the path, the symbol and the category were identical before and
after, so only the fingerprint could carry the change — and it did not: the run
stayed green with zero findings. Hashing the module closes all three at once,
because it stops depending on a decomposition being exhaustive.

#### What "normalized" means, and what it costs

Source positions are dropped, docstrings are stripped, comments were never in
the tree, and local bindings are rewritten to POSITIONAL placeholders carrying
their scope depth. Positional rather than name-derived: a mapping built by
sorting names would move every other local whenever one was renamed, which is
the churn normalization exists to prevent. A reformat, a docstring, a comment
and a renamed local therefore leave a record standing; a changed URL, a changed
call, a changed import and a changed constant do not.

The serialization is the engine's own, explicitly enumerated, and NOT
`ast.dump`. `ast.dump` prints whatever fields the running interpreter's AST
carries, and those move between releases: 3.12 added `type_params` to every
definition and 3.13 stopped printing fields holding their default, so the same
source produced three different digests on 3.11, 3.12 and 3.13. A ledger entry
is transcribed from a run, so a digest that depends on which interpreter ran it
means a product regenerating its ledger anywhere but on the pinned CI Python
gets `connector.conserved.changed` for every record it declared, with no local
way to produce a value CI accepts. That is how a reviewer learns to
re-transcribe a ledger without reading it, which is the failure this whole
mechanism exists to prevent, arriving through the back door. The encoding is
therefore a governance artefact with its own compatibility, pinned by golden
digests in the test suite: changing it re-surfaces every conserved record in
every adopter, so it is a deliberate edit and never a side effect of an
interpreter upgrade.

Three costs, all stated rather than discovered:

- Any behavioural edit ANYWHERE in a conserved file re-surfaces EVERY conserved
  record in it, including adding an import. That is the price of the
  fingerprint covering the file, and it is the conservative direction:
  over-invalidating costs a re-read and a re-declaration, both mechanical
  because the notice carries the measured record; under-invalidating is the
  silent subtraction this exists to end.
- Imports are part of the tree, deliberately: they are what make a request call
  a client call, and a fingerprint that ignored them would not pin the surface
  it claims to pin.
- There is no dataflow analysis, so hoisting a subexpression into a temporary
  is a structural edit and invalidates the record. That errs toward surfacing a
  conserved file for review rather than letting one drift, which is the
  direction this record errs in everywhere else.

#### The placeholder namespace is reserved, and it was not

A fourth bypass of the same family, found by attacking conservation rather than
the classifier, and fixed in this record. Locals are rewritten to
`_l{depth}_{index}`; module-level names are left standing, because a global is
API. Nothing reserved the spelling, so a global SPELLED like a placeholder
normalized to the same token a local did, and these two modules — which call
DIFFERENT hosts — shared one digest:

```python
_l0_0 = "https://api.production.example/v1/charge"

def provider(sandbox_url):  return httpx.get(sandbox_url)   # the caller decides
def provider(sandbox_url):  return httpx.get(_l0_0)         # always production
```

Path, symbol and category are identical before and after, so the fingerprint
was again the only coordinate that could carry the change, and again it did not:
declared, swapped, and the run stayed green with zero findings. A reviewed
sandbox double could be re-pointed at production underneath its own unchanged
ledger entry — conservation with the ratchet taken out.

The fix is an ESCAPE rather than a refusal, because the two obvious
alternatives buy the collision back as churn: refusing to fingerprint a module
that mentions such a name would invalidate a record on a rename, and folding the
original local names into the digest would move it on every rename. The prefix
grows an underscore until no identifier in the module can be read as a
placeholder in it. It is per-module, deterministic, and measured: across the six
repositories, **8,440 tracked Python sources parsed and 0 digests moved** by the
change — no identifier anywhere in the corpus is placeholder-shaped — so no
adopter ledger churns. Both directions are proved
(`test_a_placeholder_shaped_global_cannot_freeze_a_fingerprint`,
`test_reserving_the_placeholder_namespace_is_not_churn`), and the three golden
digests are unchanged.

One stated cost, in the conservative direction: renaming a local TO a
placeholder-shaped name moves the prefix, and therefore the digest, for the
whole module. That re-surfaces the record for review rather than hiding an edit.

#### Three arms, and what each catches

| Arm | Fires when | What it catches |
| --- | --- | --- |
| `connector.conserved.undeclared` | Observed, not declared | The same trick in a different file: a second test-only connector nobody has reviewed. |
| `connector.conserved.stale` | Declared, not observed | A conservation that stopped happening — indistinguishable from a classifier that stopped seeing something. |
| `connector.conserved.changed` | Matched, different fingerprint | The conserved code now does something else. |

Every conserved finding is also published as a
`connector.conserved.recorded` NOTICE carrying the exact JSON object to
transcribe, so the ledger is regenerated from a run rather than hand-assembled.

#### A conserved entry is an acknowledgement, never a waiver

This is the property that keeps conservation from becoming the exemption
mechanism this record refuses to build. Declaring an entry removes nothing from
the measured universe: the derivation does that, the derivation reads no
profile key, and an entry naming a MEASURED source suppresses nothing — the
baseline still fails upward and the entry itself reports stale, because no
conserved finding backs it. There is no spelling of `conserved_exclusions` that
takes a file out of scope. All the key can do is admit a subtraction that has
already happened, which is what makes an unadmitted one an error.

### The record number

Two branches picked 0010 and both were correct when they branched — the
collision `docs/adr/README.md` names explicitly, using `dotmac_sub`'s two ADR
0004s as the precedent. Neither had merged, so the tie-break is chronological:
the askable-decision contract is ADR 0010 at schema version 6, and THIS record
is ADR 0011 at schema version 9. ADR 0010 is not edited by this change; this
one stops colliding with it. The two schema lines are independent because they
version different profiles.

### The corrected cursor classification

This is normative, and narrower than the obvious rule:

- `checkpoint`, `syncstate` and `synccursor` NAME durable progress over a
  stream and count on their own.
- A bare `*Cursor` must ALSO name a feed — `sync`, `external`, `integration`,
  `connector`, `feed`, `ingest`, `import`, `poll`, `replicat`, `upstream`,
  `remote`, `mirror`, `provider`, `webhook`, `erp`, or a provider name —
  because "cursor" is equally the ordinary word for a pagination cursor, a
  DBAPI cursor and a rotation pointer.
- The COLUMN net is unchanged: a class that actually stores a watermark
  (`last_synced_at`, `sync_cursor`, `last_cursor`, `watermark`) counts
  regardless of its name, in both declaration styles.

The third clause is why the second costs no recall. `meta_` qualifies a
credential name but never a class name, so `MetadataCursor` is not a feed
cursor.

### Two-directional ratchet

An observed count above its baseline fails: a new direct connector surface
landed. An observed count BELOW its baseline also fails: retirement is
legitimate only when the profile baseline is lowered in the same change that
deletes the code, so the reviewer sees it. A count that quietly falls is
indistinguishable from a detector that stopped seeing something.

At an all-zero baseline the downward arm is unreachable, so this repository's
own profile proved only half the claim. The down direction is therefore tested
against the REAL repository with each baseline raised to one in turn, and that
category alone must report `connector.baseline.stale`.

### There is no exemption mechanism

Version 6 carried an `exclusions` list whose premises the engine verified. That
was still checkable in FORM and not in CLAIM: both premise kinds were satisfiable
by a one-line edit to the excluded file — add a `@generated` marker to the top
of a hand-written client, or add an import of the owning authority to a surface
that does not delegate to it. The mechanism is REMOVED, not tightened. Version 8
has no waiver and no exemption.

A future exemption requires two properties. Conservation builds ONE of them and
deliberately does not build the other, and the distinction is the whole reason
`conserved_exclusions` is not that mechanism under another name:

- a FINGERPRINT of the file, so editing it invalidates the record rather than
  re-justifying it — BUILT, by exclusion conservation above; and
- a GOVERNANCE-OWNED semantic predicate, so the claim is not something the
  product can make true by editing the exempted file — NOT BUILT. There is no
  claim in a conserved entry to make true. It asserts nothing about the code
  and grants nothing to it; it records that a subtraction the engine already
  made has been seen.

Until the second exists, a false positive is raised against this record and the
detector is corrected once, centrally — which is how `InboxTeamRoundRobinCursor`
was resolved.

### Untracked Python is two populations (2026-08-15)

`git ls-files --others` with no `--exclude-standard` made every gitignored
Python file a `repository.source.untracked` error: 3119 in `starter-spi-modes`
(3119 of them under `.venv/`), 407 in `vcp-adopt` (406 under `.venv/`). The
ratchet was unusable in both.

Adding `--exclude-standard` is REFUSED, and the refusal was verified
empirically rather than argued: with it, a gitignored untracked connector and
the environment noise vanish TOGETHER. The untracked error is exactly what
closes bypass D, so deleting it to fix a count would trade the control for the
convenience.

The enumeration is therefore SPLIT rather than filtered. `untracked_visible` is
what a plain checkout shows; `untracked_ignored` is what the repository's own
ignore rules hide. Both are errors and both carry
`repository.source.untracked`; the message says which population a file is in.
Collapsing them into one number is what hid the problem, and the ignore query
is run separately, used only to label. When it cannot be answered, nothing is
labelled ignored — the split fails toward the louder half.

### A governance-owned source disposition (2026-08-15)

The count is answered by CLASSIFYING the source, not by exempting it. Code
inside a TOOL-OWNED DEPENDENCY ENVIRONMENT is dependency material rather than
repository source. It is dispositioned out of the untracked population and
published as a `repository.dependency-environment` NOTICE naming the
environment root, the evidence that proved it, and its FILE COUNT — visible and
auditable from the output, never silent.

This is the governance-owned semantic predicate the section above says a future
exemption needs, built for exactly one narrow classification and nothing else.
It satisfies that bar because the product cannot make its claim true by editing
the file: the claim is about a WHOLE DIRECTORY's tool-written metadata and
structure, and forging it means constructing a real environment. Accordingly:

- Products cannot configure it. There is no profile key, no path a product can
  name, no predicate a product can supply, and no schema change accompanies it.
  Adopter-configured exclusions stay deleted.
- It is independent of `.gitignore` in BOTH directions. A genuine environment is
  dependency material whether or not it is ignored, and being ignored disposes
  of nothing by itself.

The predicate is CLOSED. No wildcard, no name match, no "looks like": a
directory called `.venv` earns nothing by being called that. All four arms must
hold for a repository-relative directory `E`.

| Arm | Requirement | Why it is not guessable |
| --- | --- | --- |
| A1 MARKER | `E/pyvenv.cfg` is a regular file (never a symlink, never over 64 KiB) parsing as `key = value` lines, carrying `home` as a non-empty ABSOLUTE path, `include-system-site-packages` as exactly `true`/`false`, and at least one of `version`/`version_info` beginning `MAJOR.MINOR`. Both version keys present must AGREE. | The two keys are the two real dialects — `virtualenv` writes `version_info`, the stdlib `venv` writes `version`. A third spelling is a new governance decision, not something the predicate already grants. |
| A2 LAYOUT | a real directory (never a symlink) at exactly `E/lib/python<MAJOR>.<MINOR>/site-packages` or `E/Lib/site-packages`. | The directory name is DERIVED from the marker's version rather than discovered by globbing. That derivation IS the internal-consistency check: a marker claiming 3.13 over a 3.11 tree proves nothing. |
| A3 INTERPRETER | a regular file at exactly `E/bin/python`, `E/bin/python<MAJOR>.<MINOR>`, or `E/Scripts/python.exe`. | A real environment symlinks this OUT to the base installation, which is expected and permitted — an interpreter is not measured material, so only sources are subject to A4. |
| A4 CONTAINMENT | `E` is not itself a symlink and resolves inside the repository, and every dispositioned file must RESOLVE inside `E`. | A symlink inside a genuine environment pointing out of it must not launder a file into dependency material. An unresolvable link — dangling, or a cycle — fails closed and stays untracked. |

Three negatives are proved, because a disposition that fires is not a
disposition that discriminates: a directory MERELY NAMED `.venv` with the layout
and the interpreter but no marker, an INCOMPLETE MARKER (eleven mutilations, one
per required field), and an ORDINARY IGNORED PACKAGE all keep reporting
`repository.source.untracked`. Bypass D is proved to stay closed in the same run
in which a genuine environment beside it is dispositioned away.

OUT OF SCOPE, deliberately: code inside a recognised environment is dependency
material, and whether that dependency's provenance is DECLARED and PINNED is a
SEPARATE control. Constructing a real environment around a connector is
therefore a conceded residual route — it costs building a genuine environment,
and it is the undeclared-dependency control's business, not this one's. That
control is not built here.

### The four adopter baselines under schema version 9 (2026-08-15)

Recomputed by library probe, read-only, in the adopter worktrees; NOT written
there, since all four remain PENDING-APPROVAL and none may be edited by this
change. Each repository was measured twice with the same engine — once whole,
and once with the SMTP arm forced off — so the delta is attributable to the arm
and not to anything else that moved.

| Repository | `outbound_transport` HTTP only | `outbound_transport` v9 | SMTP delta | `delivery_retry` v8 → v9 | other five |
| --- | --- | --- | --- | --- | --- |
| `sub-adopt` | 40 | **44** | +4 | 7 → 7 | unchanged (4 / 3 / 18 / 11) |
| `erp-adopt` | 21 | **23** | +2 | 5 → **6** | unchanged (8 / 6 / 12 / 15) |
| `academy-adopt` | 2 | **3** | +1 | 0 → 0 | unchanged (0 / 3 / 0 / 0) |
| `vcp-adopt` | 0 | **0** | 0 | 0 → 0 | unchanged (all zero) |

The HTTP-only column reproduces the pre-rename numbers EXACTLY in all four,
which is how "the HTTP arm is unchanged" was checked rather than asserted. No
category fell anywhere: nothing was traded for the recall.

Every one of the seven gained modules is a real SMTP surface, named rather than
counted: `sub-adopt` `app/services/email.py`,
`app/services/web_system_export_tool.py`, `app/team_inbox_smtp.py` and
`scripts/one_off/send_important_account_batch.py`; `erp-adopt`
`app/services/email.py` and `app/tasks/email.py`; `academy-adopt`
`app/services/email.py`.

`erp-adopt`'s `delivery_retry` 5 → 6 is the one non-`outbound_transport`
movement, and it is a single module: `app/tasks/email.py`, the witness. It
declares `max_retries`, `retry_backoff`, `retry_backoff_max` and `retry_jitter`
over an SMTP send, and until SMTP joined the retry rule's outbound conjunct
that policy read as a retry loop around a local queue.

### Diagnostics

| Code | Severity | Fires when |
| --- | --- | --- |
| `repository.inventory.unavailable` | error | The tracked Python inventory cannot be read, so no universe can be derived. |
| `repository.source.untracked` | error | A Python source is on disk but outside the index, in either untracked population — visible, or hidden by the repository's own ignore rules. The message says which. |
| `repository.tree.unmeasured` | error | An index entry grafts a tree the index does not contain: a submodule, or a symlink to a directory outside the repository. |
| `repository.dependency-environment` | notice | A directory was proved to be a tool-owned dependency environment, published with the evidence that proved it and the FILE COUNT the disposition removed from the untracked population. |
| `connector.scope.excluded` | notice | A tracked source was proven test-only and unreachable, and removed from the universe. |
| `connector.conserved.recorded` | notice | A connector-shaped surface inside an excluded source, published with the exact entry to declare. |
| `connector.conserved.undeclared` | error | A conserved finding no `conserved_exclusions` entry declares. |
| `connector.conserved.stale` | error | A declared conservation matching nothing observed — including one naming measured code. |
| `connector.conserved.changed` | error | A conserved finding whose normalized fingerprint no longer matches the declaration. |
| `connector.syntax.invalid` | error | A measured Python source cannot be parsed and therefore cannot be measured. |
| `connector.baseline.exceeded` | error | A category's observed count rose above its declared baseline. |
| `connector.baseline.stale` | error | A category's observed count fell below its declared baseline without the profile being lowered. |

## Acceptance record

None. This record is `Proposed` and non-normative. It was drafted by an agent;
no named human has approved it, and an agent-run local validation is not
governance evidence. The rule family reaches a product only when Michael Ayoade
accepts this record, the carrying revision merges to canonical `main`, and that
product repins and migrates its profile to schema version 9 in one change.

## Consequences

- Enrolled repositories migrate to schema version 9 in the same change that
  repins the accepted Governance commit. `runtime_roots` and `exclusions` are
  refused as unknown keys, so a version-6 profile fails loudly rather than
  losing meaning quietly, and a version-7 profile fails with the message that
  version 7 was withdrawn and never accepted.
- The first run of a version-9 profile in a repository with real test doubles
  will report `connector.conserved.undeclared` for each of them. That list is
  the migration work: transcribe the published records into
  `conserved_exclusions` and re-run. It is the same shape as measuring the
  baselines, and for the same reason — the floor is read out of the engine
  rather than guessed.
- The migration diff is no longer the review surface for what a repository
  calls application runtime — there is nothing left to declare. The published
  `connector.scope.excluded` notices are that surface instead, and they are
  regenerated on every run rather than written once.
- A repository that keeps a vendored dependency tree or generated Python inside
  its working tree without tracking it will report `repository.source.untracked`
  for every such file. This is the deliberate cost of refusing name-based skips:
  those regions genuinely are unmonitored. A TOOL-OWNED DEPENDENCY ENVIRONMENT
  is the one case that is now resolved, by the governance-owned source
  disposition below — and only because it can be PROVED rather than named.
- A test module that offers a public module-level helper stays IN the measured
  universe. That is the safe direction — it can raise a count and fail loudly,
  never hide one — but adopters should expect their first run to measure more
  test code than they assumed.
- Dynamic wiring is visible only where the repository NAMES the module. An
  importlib string, an entry-point string, a Django settings string, a plugin
  registry map and an assembled `f"package.{name}"` path are all edges now. What
  is still not an edge is a name that never appears in tracked Python: wiring
  held only in `pyproject.toml`, in a non-Python config file, or in an
  environment variable, and `celery.autodiscover_tasks` scanning a package it
  does not spell out. The remaining attack therefore costs a fake test,
  all-private public names, and a module no tracked Python source names — which
  an earlier draft of this record wrongly claimed was already the cost, when
  the true cost was only the last of the three.
- **That cost is not a cost at all for an ordinary ASGI application, and the
  first conservation run against real adopters is what showed it.** In
  `academy-adopt`, `app/main.py` is
  `from app.kernel_runtime import create_academy_app` and
  `app = create_academy_app()`. It offers no public runtime DEFINITION —
  `_public_runtime_definitions` reads `def` and `class`, and this is an
  assignment — and no tracked Python source imports it, because `uvicorn
  app.main:app` lives in a container image rather than in a module. Its only
  importers are tests, so the grow pass removes it, and the whole import
  closure beneath it cascades out: `kernel_runtime`, `assembly`, and 60 of the
  152 files under `app/`, including `app/web/labs.py`, which proxies HTTP and
  WebSocket traffic to a lab console. The same shape removes
  `app/services/coach/insight_engine.py` in `erp-adopt`, which holds an HTTP
  client and delivery-retry machinery.

  Three things follow and none of them is comfortable. The grow pass requires
  nothing of the source it grows in — not a test name, not a test declaration,
  only that every importer is already out — so it is not bounded by anything a
  product would have to do deliberately. The MEASURED baselines of every
  adopter were therefore computed over a universe missing part of the
  application, which is a defect in the numbers already recorded in this
  record's gate table, not only in the ones ahead. And it is exactly the
  bypass route I this record claims to have closed, arriving by accident
  rather than by attack.

  It is stated here and NOT fixed here. Widening the derivation changes the
  measured universe in every repository and therefore every baseline, so it
  needs its own before-and-after gate against the same six repositories, the
  way the detector widening got one. Conservation is what made it visible —
  under version 7 all 67 of those application files (60 in `academy-adopt`,
  7 in `erp-adopt`) left in silence — and that is the
  clearest evidence available that the mechanism does the job it was built for.
  Until the derivation is repaired, an adopter transcribing
  `conserved_exclusions` must read each entry: an entry naming a file under
  `app/` is this defect, not a test double.

  The findings themselves used to work against that instruction. Both the
  `connector.conserved.recorded` notice and the
  `connector.conserved.undeclared` error said the surface had left the measured
  universe **as test-only** — a false statement of fact about
  `academy-adopt app/web/labs.py`, a router `app/assembly.py` mounts, and about
  `example/doubles.py` in this repository's own fixtures, which declares no
  test either. A ledger whose only enforcement is that a human reads it may not
  mislabel what that human is approving, so neither finding asserts what a file
  IS any more: they state the subtraction and point at the
  `connector.scope.excluded` notice on the same path, which carries the
  derivation's actual reason.
- An exclusion is no longer a silent subtraction: it is conserved, per surface,
  with a fingerprint. What conservation does NOT do is bound the classifier. A
  file the analysis wrongly proves test-only still leaves the universe; the
  difference is that leaving is now recorded, so the wrong proof has to be
  admitted in a profile diff instead of passing as one more notice. That turns
  a defence which had to hold perfectly into one that fails visibly, which is
  not the same as one that cannot fail.
- Conservation is only as good as the classifier that decides what is
  connector-shaped. A test double holding a surface none of the six categories
  sees is excluded AND conserves nothing — the same blind spot the measured
  side has, on the other side of the partition. The honest statement is that
  conservation closes the gap between "excluded" and "reviewed", not the gap
  between "connector" and "detected".
- **Conservation roughly doubles the derivation cost, and that is stated rather
  than absorbed.** Measured against the largest subject repository,
  `connector_scope` on `sub-adopt` (2,959 measured, 1,768 excluded) goes from
  80.2s to 174.6s. The cost is classifying every excluded source — the same
  eight-rule sweep the measured half already pays, now paid on both sides of
  the partition, which is the arithmetic consequence of conserving a partition
  rather than half of one. The measured/excluded partition is byte-identical
  with conservation on and off, so the cost buys records and moves no count.
  It was not optimised by sharing one factory trace between the two halves:
  the conserved half resolves over the WHOLE inventory and the measured half
  over the measured set alone, and merging them would widen what the measured
  counts can resolve — a change to the numbers riding along inside a
  performance fix, which is precisely the kind of thing this record refuses.
- The conserved-record volume is small, which is the narrowness paying off.
  Across the six subject repositories: 35 records over 14 files in
  `sub-adopt` (from 1,768 excluded), 11 over 1 file in `academy-adopt`, 9 over
  6 files in `erp-adopt`, 1 in `starter-spi-modes`, 0 in `vcp-adopt` and 0
  here. A ledger of that size is readable; one entry per excluded test file
  would have been 1,768 lines in one repository alone.
- Precision is chosen over recall deliberately, and what each rule does not see
  is part of the contract: an HTTP call through an unusual wrapper, a webhook
  route whose path literal is computed, and a credential named for a provider
  this list does not know are all invisible. An honest undercount that shrinks
  beats an overcount that gets switched off.
- **The undercount is far larger than "deliberate precision" implies, and this
  record is NOT adoptable until that is settled.** An adversarial audit scored
  40 idiomatic spellings of the six categories and the engine missed 37, with
  zero control failures. A clean repository holding an ordinary ERPNext + Stripe
  integration — outbound `httpx` with `tenacity` retries, a Stripe webhook
  receiver doing HMAC verification, `ERPNEXT_API_TOKEN`, a celery-beat
  reconciliation task and an `erp_feed_position` watermark — declared all six
  baselines at zero and passed `mode=required` with exit 0. Every file was
  MEASURED and classified empty, so this is not a scope miss: each rule reads
  only what a module BINDS (assignments) or DECORATES, never what it NAMES in a
  call argument, keyword, parameter, or registration string.

  The second-order effect is worse than the misses. A refactor from a visible
  spelling to an invisible one makes a count FALL, so the engine emits
  `connector.baseline.stale` and instructs the product to lower the baseline in
  the same change. Followed faithfully, the baseline reaches zero and the
  ratchet has helped disarm itself. A guard that only ratchets against the
  spellings it already sees is not yet a ratchet.

  Widening the detectors is not attempted here, and doing it carelessly makes
  things worse rather than better: a prototype that swept every string constant
  produced five false positives, all of them DOCSTRINGS — including prose
  explaining why a look-alike is a look-alike. With no exemption mechanism in
  this release, a false positive is unfixable by the adopter and must be
  corrected centrally, so recall may only be bought with evidence that precision
  holds.
- A repository pinned to an earlier Governance revision is unaffected until it
  repins.

## Drift prevention

- The parser and JSON schema are closed at version 9: the surface object is
  mandatory, its only keys are `baselines` and `conserved_exclusions`, the six
  categories are an enum, and there is no waiver or exemption mechanism to
  weaken. Versions 7 AND 8 fail to LOAD, each with a message saying it was
  withdrawn and never accepted, rather than upgrading into a rule family — or a
  vocabulary — it never carried. The version-8 refusal is proved in both
  directions: a v8 profile carrying the OLD baseline key is refused at the
  VERSION before its vocabulary is read, so a v8 body carrying the NEW key is
  refused too and there is no spelling of a version-8 profile that loads; and a
  v9 profile that keeps `http_client` fails as an unknown key and a missing key
  at once, rather than defaulting the category it dropped to zero.
- `outbound_transport` names the CONCEPT and carries one arm per protocol, and
  each arm holds all three ADR 0018 legs separately. The HTTP arm reaches 94
  real modules and the SMTP arm 8, so a category-level proof would have let the
  first conceal the second entirely. Every SMTP leg is live in real corpus code
  — USED 7, OPENED 6, SENT 6 — and each is additionally planted into THIS
  repository's real scan in turn, since this repository holds neither protocol.
  The design decisions are held RED-first by in-situ mutation of the engine:
  giving the SMTP arm the HTTP arm's conjunction silences the witness leg;
  promoting `send_message` to an unqualified verb fires on a queue; ignoring
  the `except`-type position fires on a module that only catches; binding an
  imported constructor as a transport name destroys leg isolation; and dropping
  SMTP from `delivery_retry`'s outbound conjunct loses the witness's retry
  policy. Each was confirmed failing before the code that prevents it.
- The conservation ledger is exact and governance-shaped. A conserved entry
  holds four literal coordinates the engine itself published and nothing else:
  no reason, no premise, no predicate a product could satisfy by editing its
  own file, no glob, no dotted symbol, no truncated digest, and no two entries
  naming the same path, symbol and category.
- Conservation carries its own two-directional proofs, including the one that
  matters most: a conserved entry cannot suppress a MEASURED connector. The
  same entry re-pointed at a measured file leaves the baseline failing upward
  AND reports itself stale, so there is no spelling of the key that removes a
  file from the universe. Alongside it: the blessed transitive double is
  conserved and accepted; a test file with no connector surface conserves
  nothing; a second test-only connector nobody declared is an error; a
  reformat, a docstring, a comment and a renamed local leave a record standing;
  a changed URL does not; and each of the four coordinates is mutated in turn
  and must break the match.
- Both conservation arms are exercised against the REAL repository, which
  excludes nothing and therefore has an empty ledger — the same vacuity problem
  the all-zero baselines have, answered the same way. Declaring one entry
  against the real tree must report `connector.conserved.stale` exactly once,
  and removing it must return the tree to green, so the failure is attributable
  to the declaration.
- Scope cannot be self-declared, so it cannot be argued away. `runtime_roots`
  and `exclusions` are unknown keys and fail at PROFILE LOAD.
- The inventory is the Git index with no exclude rules applied, so a
  product-authored `.gitignore` is not an input to measurement.
- Baselines fail upward AND downward, and the downward arm is exercised against
  this repository at a non-zero baseline, where it is not vacuous.
- `tests/test_standards_control.py` carries a sensitivity proof for EVERY
  category in both directions: a planted surface must raise its own category
  alone, and a plausible look-alike must stay silent. The rotation-pointer case
  is proved as its own control, alongside the feed-named cursor that must count
  and the watermark column that counts whatever its class is called, in both
  declaration styles.
- All six demonstrated bypasses are sensitivity tests in their own right. Each
  was confirmed RED against the pre-repair engine before the repair landed; a
  bypass test that never failed is not a proof. The seven routes of the second
  audit (E to K above) are held the same way, each RED against the engine as it
  stood before that repair, and each paired with the counter-direction that has
  to stay green: a shell script is still not Python, a broken file that claims
  Python is still a finding, an in-repository symlink grafts nothing, a
  connector no source names at all is still excluded, an interpolated URL is not
  a module reference, and both shapes of a real test module — `unittest` and a
  pytest `Test` class — are still excluded.
- The scope analysis carries its own two-directional proofs: a real test faking
  a connector is excluded WITH a published reason, the same bytes without the
  `test_` prefix are measured, a fake test on a live connector buys nothing, a
  double reached only through a test helper is excluded transitively, and one
  runtime import of that helper puts the double back in scope.
- The production-engine test asserts the SCOPE, not just the verdict: the
  measured and excluded sets must partition the tracked `*.py` inventory
  computed independently by `git ls-files`, there must be no untracked source,
  and named runtime files must be present in the measured set.
- Prose inertness is held PER CATEGORY, in both forms, in both directions. The
  whole-connector quote and comment-out proofs stay, but they are not
  sufficient on their own: they were green throughout the period in which two
  arms scored prose, because a bare module with a connector word in prose never
  fires for any category. The four negatives added with the repair each pair
  real executable code satisfying the non-prose premise with the category's
  word in a comment, and again in a docstring — the shape that actually bites.
  Every one was confirmed RED against the pre-repair engine.
- The two rewritten detectors are held PER ARM, not per category, because a
  live arm otherwise conceals an inert one. `CONNECTOR_TASK_ARMS` (decorator,
  dispatch, registration, schedule table) and `DELIVERY_RETRY_ARMS`
  (identifier, keyword, attribute, decorator, configuration literal) each pair
  a firing source with a near-miss differing ONLY in the property that arm
  reads: the same decorator over a non-connector subject, the same outbound
  client with no retry policy. The configuration-literal arm is the recall
  control on the repair itself — `{"max_retries": 3}` handed to a client must
  keep counting, since a repair that silenced prose by refusing string
  constants would have traded one false negative for another.
- The classifier is not given the source text, so a text scan cannot be
  reintroduced without also reintroducing the parameter. That is the structural
  half of the guarantee; the per-category inertness proofs are the behavioural
  half, and neither is sufficient alone.
