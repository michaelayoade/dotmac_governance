# Dependency provenance and connector precision repair

- Date: 2026-08-16
- Decision under review: ADR 0011 (`Proposed`, non-normative)
- Adoption state: all product profiles remain `PENDING-APPROVAL`
- Implementation state: local working tree; not committed, pushed, merged or pinned
- Acceptance state: static checks pass; the integrated suite, eight audit shards
  and Git-hosted CI remain required

This inventory holds the attack detail behind ADR 0011's file-proven source
disposition and three precision boundaries. The ADR holds the normative rules;
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

## Three systemic false-positive families

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

### Local synchronisation is not connector scheduling

`sync` names a relationship. It does not say one side is external. Local
Postgres projections and cache reconciliation were counted when a scheduler
decorator supplied the evidence half and the bare verb supplied the subject.

The repair requires a generic external qualifier in the scheduled subject or
another independently proven connector surface in the module. The rule does
not grow a product/provider proper-name list. Existing
`sync_provider_invoices`-shaped canaries remain red.

## Evidence still required before acceptance

1. Run the full integrated unit suite in the approved Git-hosted environment.
2. Rerun the eight short audit shards against the final engine revision.
3. Produce the per-repository before/after finding inventory and adjudicate
   every change; no unexplained loss is acceptable.
4. Run the final pull-request CI from the exact pushed tip.
5. Keep ADR 0011 `Proposed` and every adopter `PENDING-APPROVAL` until Michael
   explicitly accepts the record after that evidence is reviewed.
