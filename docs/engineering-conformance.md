# Cross-repository engineering conformance

`standards_control` is the development-only engine accepted by ADR 0006. The
checked-in Governance profile is `required`; a green run is conformance
evidence for the evaluated revision, not a certification or compliance claim.

Each strict schema-version-11 profile names repository URL/default branch, its
governance source, protected resources with one owner/writer boundary, drift
tests, exact Python contract surfaces, its module-declared vocabularies, the
kernel testing-kit import boundary, its external-connector surface, and its
deployment-artefact surfaces. The typed gate rejects `Any`, missing or bare
public annotations, unannotated record fields, and mutable boundary records.
Schema version 11 has no waiver mechanism and no exemption mechanism. Schema
versions 7 and 8 are withdrawn and never accepted: both fail to load rather
than upgrading.

Schema versions 9 and 10 are **superseded rather than withdrawn**, and the
loader distinguishes them. Versions 7 and 8 refused because a number measured
under the old rule would have been wrong under the new one. Nothing measured
changed at 10: ADR 0014 added a surface a version-9 profile simply did not
declare. Version 11 likewise does not reinterpret a version-10 measurement:
every v11 profile explicitly declares `compatibility_retirements` and
`retirement_history`. An empty list enrolls no retirement slice; it is not
evidence that a product has no compatibility state. Each superseded-version
error names the required mechanical edit, and the loader still refuses the old
profile because defaulting a new key would enroll a repository in a standard
it never declared.

## Compatibility-state retirement (ADR 0017, ACCEPTED)

The v11 contract describes a named product-local retirement slice, its current
authority binding, exact static and catalogue baselines, deletion lineage and
the four mandatory external exit dispositions. Governance compares declarations
and supplied product-produced evidence; it does not collect a database
catalogue, authenticate a workflow record, observe a target, or authorize a
drop. A non-empty enrollment therefore requires a separately generated
`RetirementObservationBundle.v1`; absence is a failure rather than an inferred
zero. Reports expose qualified repository, product-revision and target evidence
states and enrolled identifiers. They never emit `deletion_authorized`,
`migration_complete`, or an unqualified completion verdict.

A declared deletion reference must resolve to a Python `upgrade` entry point in
a repository-relative `migrations` or `versions` path, and its declared owner
must equal the relation lineage. The product-produced
`deletion_lineage_owned` check supplies the product-specific lineage evidence;
Governance validates that closed claim but does not authenticate its artifact.
Artifact authentication remains ADR 0013 open decision 18.

The JSON schemas constrain UTC timestamps lexically and annotate them with
`date-time`; Draft 2020-12 consumers may treat that format as annotation. The
Governance parser is therefore the semantic acceptance authority and rejects
impossible calendar dates. A producer or consumer must not treat schema-only
validation as retirement-evidence acceptance.

The first product adoption remains a separate change. Synthetic comparison
fixtures prove parser and comparator sensitivity only; they do not prove a
PostgreSQL fence, transaction rollback, or `DROP ... RESTRICT` behavior.

A strict schema-v9 or schema-v10 trusted base may adopt v11 directly. The
history gate validates the prior shared profile body under v11 after adding
only the fields introduced later, then starts the retirement ledger empty.
Later-version fields smuggled into the older profile are refused. Products do
not merge a v10 bridge solely to reach the v11 retirement contract.

## Deployment artefact surface (ADR 0014, PROPOSED)

ADR 0014 is `Proposed`. Its carrying revision must merge to canonical `main`
before a product may pin its exact commit, exactly as ADR 0011 requires. What
follows is the adoption instruction; each product still migrates its profile
and proves the pinned revision independently.

A profile declares `deployment_artefact_surfaces`, one entry per deployable the
repository ships:

| Key | Meaning |
| --- | --- |
| `surface_id` | stable slug, unique within the profile |
| `subject` | what this deployable is |
| `declaration_paths` | the artefact that must carry NO environment fact |
| `rendered_paths` | the deterministic output of that declaration |
| `render_check_workflow` | the workflow that compares the render byte-for-byte |
| `render_check_command` | the exact command that workflow must run |

**The declaration and the render are checked differently, on purpose.** A
declaration must carry no environment fact at all. A render is that declaration
plus one environment, so a derived loopback literal is expected there and an
address check over rendered output would refuse the correct result. What both
must hold is an immutable image digest.

Eight diagnostics, each with a planted-violation proof and a conforming control:

- `deployment.surface.missing` — a declared path the repository does not
  contain. Checked before content: a surface naming nothing passes every other
  check for the wrong reason.
- `deployment.surface.unreadable` — fails closed. A surface the engine cannot
  read is reported, never skipped.
- `deployment.image.not-pinned` — a mutable tag, or an image deferred to a
  deploy-time substitution. The substitution arm is not pedantry: without it,
  every digest could be replaced by a variable and the repository would stay
  green.
- `deployment.environment.literal` — an address or CIDR in a DECLARATION,
  decided by `ipaddress` rather than matched by a regex, so a version string
  and a port range are not findings.
- `deployment.credential.filename` — a credential-shaped basename, which
  ADR 0014 § 4 excludes alongside the value because a redaction sweep shaped
  for values passes straight over it. Read as a VALUE, not as a mention: in a
  TOML declaration a basename standing as a bare string, an array element, an
  inline-table field or a key is refused, while the same characters in a `#`
  comment are prose and stay silent — see ADR 0014's 2026-09-05 amendment for
  the measured instance and for why a multiline string counts as a value.
- `deployment.declaration.unparseable` — a TOML declaration the engine cannot
  parse. It is a refusal and never a fall back to text scanning, because a
  scanner that skips what it cannot read is a check that cannot refuse: an
  unparseable file would evaporate the rule above while the report stayed
  green.
- `deployment.render-check.absent` — the declared workflow does not run the
  declared comparison. A render nobody compares is a deployment nobody
  approved.
- `deployment.surface.undeclared` — the repository ships a recognised
  deployment declaration the profile does not name. This closes the loophole an
  empty array would otherwise open: declare nothing, ship a deployment, go
  green by declining to mention it. The detector reads file NAMES only and
  never inspects content, so it cannot drift into guessing.

**What it does not check, stated rather than implied.** Whether a pipeline
produced all four digests, and whether an authorization named them, are facts
about workflow runs and about another repository's records. ADR 0013 § 1 puts
those outside repository-local derivation and § 5 permits automation only where
a machine-readable contract carries a declared oracle kind. They remain review
discipline.

## External connector surface (ADR 0011, ACCEPTED)

ADR 0011 is `Accepted`. Its carrying revision must merge to canonical `main`
before a product may pin its exact commit. What follows is the adoption
instruction; each product still migrates its profile and proves the pinned
revision independently.

### Connector runtime dependency authority (S2)

The syntax ratchet and the package boundary are different controls. The
ratchet inventories product source; the S2 dependency gate reads the committed
`poetry.lock` and fails before a product can load a
`dotmac-connector-*` distribution.

The answer to "which repository may resolve one?" is not a profile field.
It is the Governance-owned
`policies/external-connector-runtime-authority.json`:

- the declared Integrator host may resolve connectors in `main`;
- declared source repositories may resolve them only outside `main`, so
  conformance and release tests can execute connector source without composing
  it into a product runtime;
- every other pinned repository may resolve none, including in development
  groups.

The engine normalizes distribution names using the PEP-503 spelling, so an
underscore cannot evade the `dotmac-connector-` prefix. It reads every lock
entry, not only direct `pyproject.toml` dependencies, so a transitive
connector fails too. A missing/malformed authority or lock fails closed.
Product-authored copies of the authority file are ignored.

**What a green run means, and the three things it does not.** This family
INVENTORIES AND FREEZES the direct connector surfaces a product still holds
while it migrates them behind the Integrator. A green run is evidence that the
MEASURED SPELLINGS did not grow, and nothing more.

- It is DEFENCE IN DEPTH, NOT RUNTIME ISOLATION. Nothing here stops a running
  product opening a socket, reading a provider secret, or terminating a
  provider callback. The controls that do are deployment-enforced — connector
  manifests declaring destinations, products unable to load
  `dotmac-connector-*`, provider secrets granted only to the Integrator
  workload identity, default-deny product egress, provider-agnostic Integrator
  ingress, and versioned inbox/outbox exchange instead of shared databases.
  ADR 0011's amendment of 2026-08-16 names them and makes this family's ending
  conditional on them.
- It PROMISES NO UNIVERSAL PROTOCOL RECOGNITION. `outbound_transport` carries
  one arm per protocol and today has two: HTTP over five named client
  libraries, and SMTP over two. Message brokers, gRPC, WebSocket, raw sockets,
  SSH/SFTP/FTP, SNMP/RADIUS/TFTP/NETCONF, database links and foreign data
  wrappers, and cloud SDKs whose transport is not one of the five are all
  UNMONITORED. `import boto3` holds no HTTP arm. A baseline of zero means zero
  in the protocols the engine measures.
- It is NOT a security control and may not be cited as one in an evidence
  mapping, a control interpretation, or a release note.

Three precision boundaries are fleet-wide and not configurable by adopters:
explicit `httpx` in-process transports do not count as egress; webhook-named
management routes must read callback material rather than merely configure a
registration; and a scheduled name containing bare `sync` needs a generic
external qualifier or another connector surface in the same module. Each has a
retained true-positive canary; the exact predicates are in ADR 0011.

The family has a stated END: once every enrolled baseline is zero AND the six
deployment conditions in ADR 0011 hold together, it becomes report-only and is
deleted a conformance cycle later. Treat it as migration scaffolding, not as a
permanent gate.

A repository declares two things here — a baseline for each of the six measured
categories, and the exclusions it has already reviewed — and nothing at all
about what is measured:

```json
{
  "baselines": {
    "outbound_transport": 4,
    "webhook_surface": 2,
    "provider_credential": 1,
    "connector_task": 3,
    "sync_checkpoint": 2,
    "delivery_retry": 1
  },
  "conserved_exclusions": [
    {
      "path": "tests/support/provider_double.py",
      "symbol": "provider",
      "category": "outbound_transport",
      "fingerprint": "07bbe424b25d530a6c6de386685ada83fa825883295885ae69200ebac8e611e9"
    }
  ]
}
```

The object is mandatory even when every baseline is zero and the ledger is
empty. All six categories must be present; a category cannot be dropped from a
profile to make a count disappear. Baselines are two-direction ratchets: a rise
is a new direct connector surface, and a fall without the profile being lowered
in the SAME change is a retirement nobody reviewed.

Lowering in the same change is necessary and NOT sufficient. The change must
also carry DELETION evidence (the surface gone from the tracked inventory,
visible as removed lines) or CUTOVER evidence (the surface moved behind the
Integrator SPI, with the connector distribution, manifest entry and
inbox/outbox contract named in the diff). A refactor from a spelling the engine
reads to one it does not ALSO makes a count fall and ALSO emits
`connector.baseline.stale`; followed literally, that instruction walks a
baseline to zero and disarms the ratchet. The engine cannot tell the three
apart, so a reduction the reviewer cannot attribute is refused whatever the
diagnostic says.

### Exclusions are conserved, not subtracted

An exclusion used to be a silent subtraction. A source proven test-only left
the universe with nothing but a notice, so an unsound classifier could remove a
live provider client and leave no signal a reviewer would ever diff.

Every connector-shaped surface inside an excluded source is now CONSERVED —
recorded with its path, the symbol that holds it, its category, and a
fingerprint of the normalized parse tree of the WHOLE MODULE. Only
connector-shaped findings are conserved: a test file holding no connector
surface records nothing, because putting a whole suite in a profile buries the
one entry that matters.

The symbol says where to look; the fingerprint pins the file. It hashes the
module rather than that symbol's own unit because the units of a file do not
cover the file — a module-level constant, a definition shadowed by a later one
of the same name, and the `with`/`if`/`try` wrapping a statement all fell
outside a per-unit hash, so each could be rewritten under a declared, reviewed
entry without moving a coordinate.

The ledger is set equality, so it fails in three directions:

| Diagnostic | Fires when | What it catches |
| --- | --- | --- |
| `connector.conserved.undeclared` | Observed, not declared | The same trick in a different file. |
| `connector.conserved.stale` | Declared, not observed | A conservation that stopped happening. |
| `connector.conserved.changed` | Matched, different fingerprint | The conserved code now does something else. |

Each conserved finding is also published as a `connector.conserved.recorded`
notice carrying the exact JSON object to transcribe, so the ledger is
regenerated from a run rather than hand-assembled.

The fingerprint is normalized: source positions dropped, docstrings stripped,
comments never in the tree, locals rewritten to positional placeholders. A
reformat, a docstring, a comment and a renamed local leave a record standing; a
changed URL, call, import or constant does not. The placeholder spelling is
RESERVED per module — the prefix grows an underscore until nothing in the module
can be read as a placeholder — because a global SPELLED like one used to
normalize to the same token a local did, which let a reviewed sandbox double be
re-pointed at production under an unchanged ledger entry. Renaming a local TO a
placeholder-shaped name is the one behaviour-preserving edit that moves a
digest, and it errs toward review. The serialization is the
engine's own and deliberately NOT `ast.dump`, which prints whatever fields the
running interpreter's AST carries and produced three different digests for one
source on 3.11, 3.12 and 3.13 — a ledger you cannot regenerate off the pinned
CI Python is one you re-transcribe without reading. Golden digests in the test
suite pin the encoding, so changing it is a deliberate edit and never an
interpreter upgrade.

Three costs are stated rather than discovered: ANY behavioural edit anywhere in
a conserved file re-surfaces EVERY record in it, which is the price of the
fingerprint covering the file and the direction that errs toward review;
adding an import does so too, because the imports are what make a request call
a client call; and hoisting a subexpression into a temporary invalidates a
record, because there is no dataflow analysis here.

**A conserved entry is an acknowledgement, never a waiver.** Declaring one
removes nothing from the measured universe — the derivation does that, and it
reads no profile key. An entry naming a MEASURED source suppresses nothing: the
baseline still fails upward and the entry itself reports stale. There is no
spelling of `conserved_exclusions` that takes a file out of scope.

### The measured universe is derived, never declared

There is no `runtime_roots` key and no `exclusions` key. Both were
product-authored scope, and a product that can name what is measured — or name
a file out of the measurement — is not measured. Six routes to a fully-green
run with live connectors present were demonstrated against the earlier design:
declare only a clean corner of the tree, declare a root holding no Python, park
the connectors under `migrations`, under `test`, or under `alembic`, or keep
them out of the inventory with a `.gitignore` entry.

The universe is now the repository's own tracked Python inventory:
`git ls-files --cached`, with no exclude rules applied, plus every tracked
extensionless file that is Python. A `.gitignore` entry therefore changes
nothing, and a Python source that is on disk but outside the index reports
`repository.source.untracked` — such a region is unmonitored rather than
exempt. If the inventory cannot be read at all, the run fails with
`repository.inventory.unavailable`; an unmeasurable repository is not a
conformant one.

Three things follow from deriving the universe from the INDEX rather than from
the working tree, and a second adversarial audit landed a live connector on a
green tree through each of them:

- A `.py` or `.pyw` path is a Python source on the strength of its index entry
  ALONE. Whether the bytes are in the checkout is not part of the question: a
  tracked source deleted from the working tree, a tracked symlink left dangling
  until the build materialises its target, and a path omitted by a sparse
  checkout each used to leave the universe in silence. They now fail closed as
  `connector.syntax.invalid`.
- An extensionless file that CLAIMS Python is Python, so a broken entry point is
  still reported; one that claims something else is admitted on the evidence of
  PARSING as Python. Matching the word `python` in the interpreter line was a
  guess at an open vocabulary — `uv run --script`, `pypy3`, `poetry run`,
  `hatch`, `nix-shell` and an sh/Python polyglot all launch Python without it
  ever appearing.
- An index entry that grafts a tree the index does not contain — a submodule at
  mode 160000, or a symlink to a directory outside the repository at mode
  120000 — reports `repository.tree.unmeasured`. `--cached` lists the entry and
  never its contents, and `--others` does not descend through it, so an entire
  importable package could be imported and run while appearing in no universe
  derived here.

### Untracked Python is two populations, with no disposition

Python on disk but outside the index is enumerated as TWO DISTINCT
POPULATIONS, and both are errors. `untracked_visible` is what a plain checkout
shows; `untracked_ignored` is what the repository's own ignore rules hide. The
split exists so the two can be SEEN, never so one can be forgiven — an ignore
file is product-authored and decides nothing about what is measured.

`--exclude-standard` is refused. With it, a gitignored untracked connector and
a gitignored dependency tree disappear in the same stroke, which is exactly the
bypass the untracked error closes. The ignore query is run separately and used
only to label the report; when it cannot be answered, nothing is labelled
ignored.

There is no third outcome. A genuine virtualenv, a package below
`site-packages`, a console shim, and a file named by a matching `RECORD` all
remain untracked errors. The lock can anchor a distribution name/version, but
the environment's `METADATA` and `RECORD` are mutable files controlled by the
same working tree. A matching digest is therefore self-consistency, not an
independent premise that may remove source from measurement.

Canonical product CI evaluates a clean Git checkout, where an in-repository
environment does not exist. A local run with one fails deliberately; keep the
environment outside the repository, track the source, or remove it. Building
wheel retrieval and artifact attestation into a transitional syntax ratchet is
explicitly out of scope.

Exactly one thing leaves that universe, and an analysis has to earn it. A
source is removed only when it is PROVEN test-only and UNREACHABLE from
anything else:

- it declares a test AT MODULE LEVEL — a module-level `test_*` function, or a
  module-level class a runner would collect — and offers no public module-level
  runtime definition beyond tests, fixtures, and `_`-prefixed helpers, and
  carries no `__main__` guard; and
- nothing outside the removed set reaches it, judged over the whole tracked
  inventory from imports AND from dotted names held as strings.

Both clauses are narrower than they first read, because both were bought with a
name rather than with evidence:

- A class is a test class when it derives from a `TestCase` or when a `Test`
  prefix is backed by an actual `test_*` method. A bare prefix is a name, and a
  public runtime class called `TestFlightPaymentGateway` was read as a declared
  test AND as no public surface at all.
- The declaration must be at module level, read THROUGH `if`/`try`/`with`
  wrappers. A `test_connection` health probe on a live gateway is not a test
  declaration, and a public class defined under an optional-dependency guard is
  still public surface.
- Reachability counts a dotted name in a string, and a dotted package prefix
  assembled in an f-string reaches every module under it. A plugin registry, an
  `importlib` call, an entry point, a Celery autodiscover list and a Django
  settings string all reach a module by NAME; while only import edges counted, a
  public, undisguised provider client whose one static importer was its own
  honest unit test left the universe — so writing the test bought the exemption
  and deleting the test turned the build red.
- A path the PROFILE declares to be runtime — an authority's owner
  implementation, canonical writers or adapters, or a typed contract surface —
  is never a candidate. Otherwise one profile contradicts itself into a green
  build, which it did: a declared canonical writer holding a live provider
  client was removed because the only source importing it was the drift test the
  same profile declares.

The removed set is closed under the reachability rule and computed to a fixed
point, because a test that reaches its provider double through a helper only
justifies removing the double once the helper and the test are themselves
removed. Anything reachable from a source that stayed is measured, whatever it
is named and wherever it sits — a `migrations/` directory is measured, because
nothing checks that it contains migrations. Every removal is published as a
`connector.scope.excluded` notice naming the file and the reason, so the
exclusion set is reviewable rather than invisible; notices never fail a run.

The six categories and the classification rule for each are in ADR 0011. One
part is narrower than it looks and is stated there normatively: `checkpoint`,
`syncstate` and `synccursor` name durable progress over a stream and count
alone, while a bare `*Cursor` counts only when it also names a feed, because
"cursor" is equally the ordinary word for a pagination cursor, a DBAPI cursor
and a rotation pointer. The column net is unchanged, so anything that actually
stores a watermark counts whatever its class is called — in BOTH declaration
styles, annotated `x: Mapped[...] = mapped_column(...)` and classic
`x = Column(...)`.

A second part is narrower than it looks for the same reason. `webhook_surface`
fires on a route whose path literal reads as a provider callback, and also on a
signature-verification function — but the latter is a NAME, and a name is not
evidence. `verify_signature` is equally what you call the check over a licence
file, a JWT or a release artefact, and reading it unconditionally measured an
offline Ed25519 licence verifier as a webhook receiver. So a verification
function counts when its name carries the word `webhook`, or when it also reads
the inbound request (`request`, `headers`, `header`, `raw_body`,
`request_body`). A verifier that reaches its request through some other
spelling is undercounted, which is deliberate: with no product suppression, a
miss can be corrected later while a false positive cannot be fixed at all by
the repository holding it.

Two more parts were narrowed for the same reason, and this one was a live
defect rather than a caution. `connector_task` and `delivery_retry` each opened
with a scan of the raw file text, so a COMMENT or a DOCSTRING could supply half
the rule while ordinary code supplied the other half: a comment saying "unlike
the celery path we retired" over an in-process `@functools.cache
sync_local_cache` was measured as a scheduled connector, and a comment saying
"no max_retries here: the caller owns the retry policy" in a module that really
does call a provider was measured as owning delivery machinery it explicitly
disclaims. Both now read EXECUTABLE positions only — imports, decorators,
registrations and dispatch calls for `connector_task`; identifiers, keywords,
attributes, decorators and configuration literals for `delivery_retry` — and
the classifier is no longer handed the source text at all, so no rule can fall
back to scanning it. A retry policy carried as data still counts —
`{"max_retries": 3}` in a mapping handed to a client, or `state.in_(
("dead_letter", ...))` selecting dead-lettered rows — because what separates
those from prose is POSITION and EXACTNESS, not the word: a mapping key, a
subscript index and a call argument are places a comment cannot be, and the
string must EQUAL a retry word rather than mention one, so
`log.info("no max_retries configured")` stays silent. Refusing string constants
outright would have silenced prose by losing a true positive. The first draft
of this repair did lose two, both found by adjudicating the corpus diff FILE BY
FILE rather than by counts; see ADR 0011, "Prose is inert in all six, and two
of them were not".

Both proof legs are held per ARM rather than per category, because a live arm
otherwise conceals an inert one: every arm of every category carries a firing
source, a near-miss that differs only in the property that arm reads, and
evidence it reaches real corpus code.

### There is no exemption mechanism in this release

The earlier `exclusions` list carried a premise the engine verified. It was
still checkable in FORM rather than in CLAIM: both premise kinds were
satisfiable by a one-line edit to the excluded file — adding a `@generated`
marker, or adding an import of the owning authority. The whole mechanism is
removed rather than tightened.

A future exemption requires two things. Conservation builds ONE of them: the
FINGERPRINT, so editing a recorded file invalidates the record. It deliberately
does not build the other: a GOVERNANCE-OWNED semantic predicate, so a claim is
not something the product can make true by editing its own file. That is the
distinction that keeps `conserved_exclusions` from being the exemption
mechanism under another name — a conserved entry makes no claim about the code
and grants it nothing. Until the predicate exists, a false positive is raised
against ADR 0011 and the detector is corrected once, centrally — which is how
`InboxTeamRoundRobinCursor` was resolved.

## Kernel testing-kit import locality (ADR 0008)

`dotmac_kernel.testing` ships in the runtime wheel but is development-only. The
engine AST-scans every repository Python source and admits its imports only
under structural `tests` roots, under the kit's own exact source roots, or from
an exact conformance probe with a pinned import count:

```json
{
  "test_roots": ["tests"],
  "kit_source_roots": [
    "packages/dotmac-kernel/src/dotmac_kernel/testing"
  ],
  "conformance_probes": [
    {
      "path": "scripts/floor/probe.py",
      "expected_import_count": 1
    }
  ]
}
```

The object is mandatory even when `kit_source_roots` and
`conformance_probes` are empty. Declared roots and probes must exist. Test roots
must end in `tests`; kit roots must end in `dotmac_kernel/testing`; probes must
be exact Python files outside both. Probe counts are two-direction ratchets, so
an added import and a stale exemption both fail. There is no blanket `scripts/`
or runtime-package exclusion.

## Module-declared vocabularies (ADR 0007)

A vocabulary whose members belong to modules is declared by those modules and
validated by a registry; the layer that hosts it never enumerates the members,
and a backing column, when one exists, is never pinned to a fixed member list.
Each `module_declared_vocabularies` entry names the member shape, the registry
symbol that validates a member, the manifest field a module declares members
on, and its explicit storage shape:

```json
{
  "vocabulary_id": "setting-domain",
  "subject": "Setting domains a module owns.",
  "member_type": {
    "kind": "declared",
    "name": "SettingDomain",
    "path": "packages/dotmac-kernel/src/dotmac_kernel/settings_models.py"
  },
  "registry_interface": "dotmac_kernel.setting_domains.SettingDomainRegistry",
  "registry_implementation": "packages/dotmac-kernel/src/dotmac_kernel/setting_domains.py",
  "declaration_field": "setting_domains",
  "declaration_paths": [
    "packages/dotmac-kernel/src/dotmac_kernel/features.py",
    "packages/dotmac-kernel/src/dotmac_kernel/modules.py"
  ],
  "storage": {
    "column": "domain",
    "paths": ["packages/dotmac-kernel/src/dotmac_kernel/settings_models.py"]
  }
}
```

The alternatives are independent. An audit-action-shaped vocabulary can use an
open built-in member and still name its real store; a permission-shaped
vocabulary can name its declared spec while stating that no override store
exists yet:

```json
{
  "member_type": {"kind": "builtin", "name": "str"},
  "storage": {
    "column": "action",
    "paths": ["packages/dotmac-kernel/src/dotmac_kernel/audit.py"]
  }
}
```

```json
{
  "member_type": {
    "kind": "declared",
    "name": "PermissionSpec",
    "path": "packages/dotmac-kernel/src/dotmac_kernel/permissions.py"
  },
  "storage": null
}
```

`str` is the only built-in member type. `storage` is required even when null;
that makes "no store exists" part of the review surface instead of an inference
from an omitted field.

The engine reads syntax and never imports product code. It reports
`vocabulary.member-type.closed` when the member type subclasses an enum,
`vocabulary.registry.missing` when nothing validates a member,
`vocabulary.declaration.missing` when no manifest carries the declaration field,
and `vocabulary.storage.closed` when a declared database store uses an enum type
or a `CheckConstraint` with a literal `IN (...)` list. An empty array is legal
and means the repository hosts no such vocabulary — a claim reviewed in the
profile diff, since the engine evaluates declarations rather than discovering
them. A false `storage: null` is the same class of review failure; the syntax
engine does not claim it can discover semantic ownership reliably.

`owner_implementation` is repository-relative while `decision_interface` is an
importable Python symbol. Flat layouts map directly; for a standard `src`
layout, the module begins after the nearest `src` segment. For example,
`src/vendor_cp/licensing/service.py` owns
`vendor_cp.licensing.service.issue_licence`, and
`packages/kernel/src/dotmac_kernel/db.py` owns `dotmac_kernel.db.get_db`.

Only `dotmac_governance` may select a `local` governance source. Every product
uses `kind: pinned`, naming the canonical Governance repository, exact
40-character accepted commit, ADR path, and accepted status. The composite
action supplies its actual repository and `github.action_ref`; mismatched,
missing, branch-named, or tag-named identities fail before product rules run.

Run locally (where `origin/HEAD` resolves the default branch):

```bash
python3 -m standards_control verify --root . \
  --profile .dotmac/standards-profile.json
```

CI passes trusted repository metadata explicitly:

```bash
python3 -m standards_control verify --root . \
  --profile .dotmac/standards-profile.json \
  --default-branch main --format json
```

Product CI consumes the composite action at the exact accepted Governance
commit; a mutable branch or tag is not an admissible policy identity:

```yaml
- name: Enforce Dotmac engineering standards
  uses: michaelayoade/dotmac_governance/.github/actions/standards-check@<accepted-40-character-sha>
  with:
    default-branch: ${{ github.event.repository.default_branch }}
```

The action invokes the Governance-owned engine against the caller workspace.
It installs nothing into the product runtime and retrieves no credential.
Repository access for private actions remains runner configuration, not logic
copied into the action.

A product profile's governance reference therefore has this shape:

```json
{
  "kind": "pinned",
  "canonical_url": "https://github.com/michaelayoade/dotmac_governance",
  "revision": "<accepted-40-character-sha>",
  "source": "docs/adr/0006-cross-repository-engineering-conformance.md",
  "status": "accepted"
}
```

Product rollout is inventory, candidate profile, local repairs with sabotage
proofs, accepted governance plus required mode, green CI merge, then protected
branch read-modify-write and independent readback. A product repins to the
accepted revision carrying the required rule family and moves its profile to
the matching schema version in the same change; a product pinned to an earlier
revision is unaffected until it repins. Git and product CI remain
authoritative; Knowledge may index only source pointers and structured results.

## Adopting schema version 9 in a product

One change, six edits, in this order. Steps 1 and 2 are blocked until ADR 0011
is `Accepted` and merged to canonical `main`; there is no admissible way to pin
an unmerged or `Proposed` revision.

1. **Find the immutable commit.** Take the 40-character SHA of the Governance
   `main` commit that carries the accepted record — not a branch, not a tag,
   not a short SHA:

   ```bash
   git ls-remote https://github.com/michaelayoade/dotmac_governance refs/heads/main
   ```

2. **Pin the action in the product workflow** (`.github/workflows/
   engineering-standards.yml`). The `uses:` reference is the policy identity;
   the composite action reports its own repository and `github.action_ref` back
   to the engine, and a mutable ref fails before any product rule runs:

   ```yaml
   - name: Enforce the accepted Dotmac engineering standards
     uses: michaelayoade/dotmac_governance/.github/actions/standards-check@<40-char-sha>
     with:
       default-branch: ${{ github.event.repository.default_branch }}
   ```

   Nothing else in the workflow changes. The action installs nothing into the
   product runtime and retrieves no credential.

3. **Repin the profile's governance reference** to the same SHA, in the same
   commit, so the workflow and the profile cannot disagree:

   ```json
   {
     "kind": "pinned",
     "canonical_url": "https://github.com/michaelayoade/dotmac_governance",
     "revision": "<40-char-sha>",
     "source": "docs/adr/0006-cross-repository-engineering-conformance.md",
     "status": "accepted"
   }
   ```

4. **Move the profile to `"schema_version": 9`** and add the mandatory
   `external_connector_surface` object described above, with all six baselines
   at `0` and `"conserved_exclusions": []`. There is no scope to declare and no
   exemption to write. Read the published `connector.scope.excluded` notices in
   the first run — that list, not a profile key, is the review surface for what
   the repository does not measure.

   Neither version 7 nor version 8 upgrades. Both fail to load, saying they
   were withdrawn and never accepted: version 7 carried no conservation, so a
   subtraction under it left no trace, and version 8 named a category
   `http_client` — one transport rather than the concept — so a genuine SMTP
   delivery surface could hold no category at all. A version-8 baseline may not
   simply be renamed to `outbound_transport`: the number behind it was measured
   by a rule that could not see SMTP, so it is RE-MEASURED at step 5.

5. **Measure, do not guess, the baselines.** Run the engine against the
   working tree and read the reported counts out of the diagnostics, then set
   each baseline to the number the engine reports:

   ```bash
   python3 -m standards_control verify --root . \
     --profile .dotmac/standards-profile.json \
     --default-branch main --format json
   ```

   Start every baseline at `0`; each `connector.baseline.exceeded` diagnostic
   names its category and its measured count. Transcribe those counts, re-run,
   and the profile is at its true floor. Never raise a baseline afterwards to
   make a later change pass — that is the failure this rule family exists to
   catch. Lower one only in the change that DELETES the code it counted or CUTS
   IT OVER behind the Integrator SPI, with that evidence in the same diff. A
   count that fell because the code was respelled into something the engine
   does not read is not a retirement, and lowering the baseline for it spends
   the ratchet.

6. **Transcribe the conserved exclusions the same way.** The same run reports a
   `connector.conserved.undeclared` error and a `connector.conserved.recorded`
   notice for every connector-shaped surface that left the universe, each
   carrying the exact JSON object to declare. Copy those objects into
   `conserved_exclusions` verbatim and re-run.

   Read them before transcribing. This list is the review surface conservation
   exists to create: every entry is a connector the repository is asserting is
   test-only, and an entry that is not one is a live surface about to be
   ratcheted out of sight. Transcribing without reading is the one way to spend
   this mechanism and get nothing for it.

A product pinned to an earlier revision keeps its earlier schema and is
unaffected until it schedules the repin.
