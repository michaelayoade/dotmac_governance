# Untracked-source closure and connector precision repair

- Date: 2026-08-16
- Decision under review: ADR 0011 (`Proposed`, non-normative)
- Adoption state: all product profiles remain `PENDING-APPROVAL`
- Implementation state: withdrawal implemented locally on draft PR #16's
  branch; not committed, pushed, merged or pinned
- Acceptance state: `bb60968` passed 310 integrated tests and static checks,
  but the stronger forged-RECORD fixture blocked acceptance; the withdrawal
  implemented after that finding still requires exact-tip CI

This inventory holds the attack detail behind ADR 0011's withdrawn source
dispositions and two accepted precision boundaries. The ADR holds the
normative rules; this file records why they exist and what must be rerun before
approval.

## Blocker demonstrated by the sharded audit

The directory-level environment predicate was bypassable. Seven of eight
escape fixtures made a real connector disappear from all three outcomes: it
was not measured, did not appear in `untracked_visible`, and did not appear in
`untracked_ignored`. The cheapest attack created a genuine environment and
copied `connector.py` into it. The engine emitted only a notice, and notices do
not affect `conforms`.

The four environment arms correctly answered “is this a Python environment?”
They did not answer “which exact files did an accepted dependency install?”
Treating the first answer as the second was the defect.

## The file-proven repair was still self-authorization

The file-level repair closed all seven copy-only attacks, but the proof chain
terminated in worktree-controlled material. A stronger fixture:

1. kept `provider==1.0` in tracked dependency authority;
2. placed a live HTTP connector at
   `provider/copied_connector.py` below `site-packages`;
3. wrote `provider-1.0.dist-info/METADATA` and a matching `RECORD` sha256 and
   size; and
4. imported that connector from tracked application code.

Against `bb60968`, the result was `conforms=True`, `untracked=[]`, `errors=[]`,
with the environment recognised. The lock authenticated only a name/version;
the measured worktree supplied both the bytes and the digest used to excuse
them. That is consistency, not provenance.

## Final closed rule

No untracked Python source is dispositioned. Visible and ignored sources remain
separate report populations, but both produce `repository.source.untracked`.
Virtualenv markers, `site-packages`, exact locks, METADATA, RECORD, hashes and
sizes have no authority to remove a file. Tracked Python remains measured even
inside an environment.

Permanent canaries hold both directions:

| Shape | Required verdict |
| --- | --- |
| Visible copied connector | `repository.source.untracked` |
| Gitignored copied connector | `repository.source.untracked` |
| Genuine virtualenv source | `repository.source.untracked` |
| Forged pinned METADATA/RECORD plus tracked importer | `repository.source.untracked` |
| Tracked connector inside a virtualenv | measured connector finding |

Canonical CI runs from a clean checkout. Local in-repository environments fail
deliberately and belong outside the repository.

## Precision findings from the systemic false-positive audit

### In-process HTTP transports

`httpx.MockTransport` exercises the HTTP client interface entirely in memory.
A public runtime fake was counted because the old conjunction saw a client
import and `.get(...)` call but never inspected how the client was constructed.

The repair follows explicit `MockTransport`, `ASGITransport` and
`WSGITransport` wiring through direct client construction and the existing
bounded factory trace. A direct module request or any other client constructor
keeps the module measured. This is a constructor distinction, not a test-path
exclusion.

### Webhook administration is not callback ingress

An admin CRUD page for webhook registrations carried a webhook-named POST path
and a `max_retries` form field. The path manufactured `webhook_surface`; that
false surface then satisfied the context half of `delivery_retry`, producing a
second finding from the same page.

For exact management path segments, the handler must consume callback material
(headers, raw/request body, body, or a subscription challenge). A genuine
callback mounted beneath a management prefix remains measured. Non-management
webhook routes keep the existing rule.

### A bare scheduled sync cannot be narrowed by name

`sync` names a relationship. Local Postgres projection and live provider or
device work use the same scheduling shapes, so the attempted generic qualifier
repair was rejected rather than shipped. The six-repository comparison proved
that it removed fifteen real findings: Mono, Paystack, staff-account, GIS,
RADIUS, router and UISP work were among them. Product/provider proper names do
not belong in the Governance vocabulary, and the generic vocabulary did not
recover those call edges.

The detector therefore retains the bare scheduled `sync` finding. This leaves
known local-reconciliation false positives in a transitional inventory, but it
does not silently lose live connector work. A future precision change needs a
provider-agnostic call-edge proof and the same full-corpus comparison.

## Final corpus adjudication

The comparison used the engine's own Git-tracked inventory, reachability
exclusion, factory trace and classifier. Each adopter repository's ordered
measured paths and bytes had the same SHA-256 before and after, so changes below
are classifier changes over an identical adopter universe. Governance's digest
changes because the classifier under review is itself a measured source; its
six category counts remain zero in both revisions.

- Academy, ERP, Governance, Starter and Vendor Control Plane retain identical
  findings in all six categories.
- Sub retains identical findings except
  `tests/test_dotmac_erp_outbox.py`: its explicit `httpx.MockTransport` is an
  in-process fake, so its one `outbound_transport` finding is removed. The file
  remains measured; only that constructor arm changes.
- The management-webhook repair changes no real-corpus finding. Its positive
  and negative canaries establish the boundary without manufacturing a
  reduction to claim usefulness.

With no disposition, Starter's current developer worktree reports all 3,119
ignored Python sources below its in-repository environment; Vendor Control
Plane reports all 406. Those are local-worktree operability results, not product
CI results: Starter is audit corpus rather than one of the four product
adopters, and Vendor Control Plane's standards job uses a clean `ubuntu-latest`
checkout where the local environment is absent.

The final withdrawal rerun compared this engine with `bb60968` over the same six
repositories. All five adopter measured-source digests were byte-identical and
every connector-category finding was unchanged. Governance's digest changed
because its engine and tests are the sources under review; its six category
counts stayed zero. The untracked results were: Starter 2 visible / 3,119
ignored, Vendor Control Plane 1 / 406, Academy 2 / 0, ERP 2 / 0, Sub 2 / 0,
Governance 0 / 0. The visible files are the uncommitted adoption work in those
dedicated worktrees, not baseline inputs.

## Evidence still required before acceptance

1. Rerun the integrated unit suite in the approved Git-hosted environment from
   the exact disposition-withdrawal tip.
2. Keep the six-repository comparison artefact with the review evidence and
   confirm its measured-source digests remain equal after any rebase.
3. Keep ADR 0011 `Proposed` and every adopter `PENDING-APPROVAL` until Michael
   explicitly accepts the record after that evidence is reviewed.
