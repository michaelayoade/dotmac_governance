# Authority-cutover receipt registry

The cross-repository store decided by
[ADR 0018 § 3](../docs/adr/0018-authority-cutovers-leave-receipts-and-decommissions-retire-delegations.md)
and stood up by
[ADR 0019](../docs/adr/0019-the-authority-cutover-receipt-registry-is-a-reviewed-append-only-directory.md).

One JSON file per receipt, named `<receipt_id>.json`. The validator is
`tools/check_receipts.py`; its known-bad controls are
`tests/test_check_receipts.py`.

## What a receipt is, and is not

A receipt is an **envelope**. It commits to the product's evidence by digest and,
where a reader could not otherwise find that evidence, by an approved pointer.
It never carries the evidence itself.

That constraint is load-bearing rather than tidy. This repository is published
(ADR 0003). A registry that accumulated one contributor's private artefact would
inherit that contributor's confidentiality constraints and eventually have to be
split, redacted or moved — and a receipt that moves is a receipt that stops being
durable.

The pressure will not arrive as "let us put secrets in the registry". It arrives
as *"it would be so much more useful with just this one field inlined"* — a
hostname, a row count, an error message, a subscriber identifier. The answer is
always a digest plus, if necessary, an approved pointer. A field that cannot be
expressed as one of those two does not go in, and the envelope is closed so that
the validator refuses it rather than a reviewer having to notice.

## The envelope

| Field | Required | Content |
| --- | --- | --- |
| `schema_version` | yes | `1`. A change to the envelope's shape is a visible change, not a silent reinterpretation of stored receipts. |
| `receipt_id` | yes | Lowercase kebab-case, and equal to the filename without `.json`. |
| `old_authority` | yes | `{ "system": …, "resource": … }` — the system **and** the exact resource whose authority moved. Not a repository or host alone. |
| `new_authority` | yes | The same pair for the acquirer. |
| `coordinates` | yes | `{ "old": {…}, "new": {…} }`, each carrying `repository` and a peeled 40-character `commit`; optionally `path`, `released_version`, `artifact_digest`. |
| `effective_time` | yes | RFC 3339 UTC (`2026-08-30T09:15:00Z`), recorded by the transaction that moved authority — not the date a document was written or a deploy approved. |
| `runtime_evidence_digest` | yes | `sha256:<64 hex>` over the product-side `runtime_observation` artefact. A digest, never the artefact, and reproducible by the product holding it. |
| `old_writer_retirement_status` | yes | A status object — see below. |
| `private_evidence_pointer` | no | `bao://`, `knowledge://`, `github://` or `s3://` address. Never a value, never a credential. |
| `supersedes_receipt` | no | The receipt this one corrects. The only mechanism for changing what a receipt says. |

`rollback_boundary` deliberately stays in the product's own record. It is
operational detail about a window that has usually closed by the time the
receipt is durable, and it is the field most likely to carry host and
maintenance specifics — exactly what an envelope must not accumulate.

## `old_writer_retirement_status` is a status, not a boolean

A receipt is written when authority moves, and at that moment the old writer is
usually still live. A boolean pressures the author into recording a false
`retired` to produce a complete-looking receipt, which is the failure this
record exists to prevent, reintroduced by the schema. Absence is not a status
either.

| `status` | Also names |
| --- | --- |
| `retired` | `revision` — the peeled commit that removed it. |
| `transferred` | `new_owner`, and `receipt` for that move's own receipt. |
| `still_live` | `owner`, and `retirement_condition`. |

A receipt whose old writer later retires is updated the only way a receipt can
be: a new receipt superseding it. Supersession is the normal lifecycle, not an
exception, and the registry ends up showing that the retirement actually
happened, on a date, instead of a promise made at cutover time.

## Append-only

**A receipt is never edited, renamed or deleted.** An edited receipt is
byte-for-byte indistinguishable from an accurate one, so a registry that permits
editing has the *appearance* of durable evidence and none of the property. A
wrong receipt is corrected by adding a new one carrying `supersedes_receipt`;
the superseded receipt stays readable and the correction is legible as a
correction.

Git does not supply this — history can be rewritten and a file edited like any
other. It is enforced by review plus `tools/check_receipts.py`, which reads every
pre-existing receipt's **bytes** out of the merge base and compares them with the
working tree. Reading the diff's *shape* is not that check: a rename plus a
rewrite presents as one deletion and one addition, and an addition is exactly
what this registry is for.

If the merge base cannot be established the validator fails rather than passing.
A guard that silently goes green when it cannot determine what to compare
against is worse than no guard, because it reports a colour.

## The registry is currently empty, and that is a verdict

`tools/check_receipts.py` reports `not_applicable` over an empty registry — never
`executed_passed`. Every structural check holds vacuously at zero receipts, so a
green result would mean "nothing was measured" while reading as "the discipline
is evidenced".

Writing the **first** receipt is open decision 21 and belongs to Michael. The
directory, envelope, parser and validator exist so that the decision is about
authorizing a record rather than about building a store.
