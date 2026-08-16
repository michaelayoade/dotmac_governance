# Dependency provenance and connector precision repair

- Date: 2026-08-16
- Decision under review: ADR 0011 (`Proposed`, non-normative)
- Adoption state: all product profiles remain `PENDING-APPROVAL`
- Implementation state: draft PR #16; not merged or pinned
- Acceptance state: the first pushed tip passed all 295 integrated tests and
  static checks; the recall correction and exact final tip still require CI

This inventory holds the attack detail behind ADR 0011's file-proven source
disposition and two accepted precision boundaries. The ADR holds the normative rules;
this file records why they exist and what must be rerun before approval.

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

## Corrected proof chain

An untracked Python source now leaves the error population only when all of the
following evidence joins on that exact file:

1. The existing A1–A4 predicate proves a contained Python environment and its
   derived `site-packages` directory.
2. A regular `*.dist-info/METADATA` declares one distribution name and version.
3. The normalized exact pair is present in tracked `poetry.lock`, `uv.lock`, or
   exact `requirements*.txt` authority.
4. That distribution's regular CSV `RECORD` names the relative Python file.
5. The RECORD's sha256 and size match the current regular, non-symlink file.
6. No second accepted distribution also claims the file.

The notice publishes the exact accepted distribution identities and proved
file count. It never reports an entire environment as trusted.

## Permanent escape canaries

| Escape family | Required verdict |
| --- | --- |
| Connector copied into a genuine environment root | `repository.source.untracked` |
| Connector copied into `site-packages` but absent from RECORD | `repository.source.untracked` |
| Marker/layout/interpreter shape without distribution evidence | `repository.source.untracked` |
| Valid METADATA/RECORD identity absent from tracked dependency authority | `repository.source.untracked` |
| Recorded file changed after installation | `repository.source.untracked` |
| RECORD entry with no sha256 | `repository.source.untracked` |
| Internal, escaping or dangling Python symlink | `repository.source.untracked` |

Counter-canaries prove that matching pinned distribution files are
dispositioned on POSIX and Windows layouts, while a tracked connector inside a
recognised environment remains in the measured universe.

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

The file-proven disposition also turns directory trust into explicit outcomes.
Starter proves 2,680 files from exact lock-pinned distributions and leaves 439
unproved files as errors: 402 unpinned `pip` sources, 34 generated console
scripts outside `site-packages`, two unpinned Ruff sources and one virtualenv
bootstrap source. Vendor Control Plane has no matching tracked dependency
authority, so its 402 `pip` sources, three console/bootstrap scripts and one
virtualenv bootstrap source remain errors. This is the intended F1/F3 verdict,
not a hidden exclusion; CI worktrees without local environments are unaffected.

## Evidence still required before acceptance

1. Rerun the integrated unit suite in the approved Git-hosted environment from
   the exact recall-corrected tip.
2. Keep the six-repository comparison artefact with the review evidence and
   confirm its measured-source digests remain equal after any rebase.
3. Keep ADR 0011 `Proposed` and every adopter `PENDING-APPROVAL` until Michael
   explicitly accepts the record after that evidence is reviewed.
