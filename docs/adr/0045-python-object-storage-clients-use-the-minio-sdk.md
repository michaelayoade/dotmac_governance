# 0045. Python object storage clients use the MinIO SDK

- Status: Proposed
- Date: 2026-09-28
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Dotmac Python applications that use an S3-compatible object store
- Classification: Internal

## Context

Michael's 2026-09-28 instruction retains the existing `dotmac-s3` object store
and selects the MinIO Python SDK for Python S3 clients. The server decision and
the Python client decision are separate. This store is an
application-owned persistence resource, not an external application/data
connector: `dotmac_starter_mt` ADR-0024 expressly distinguishes a local
object-store `StorageProvider` beneath `dotmac-files` from an Integrator
connector. This decision applies only to that resource-driver boundary.

At the inspected 2026-09-28 revisions, ERP uses the MinIO Python SDK through
`dotmac_erp:app/services/storage.py` at
`28d23303cb1c002e20c7dedec12667126997d981`, while Sub uses boto3 through
`dotmac_sub:app/services/object_storage.py` at
`1bfa5b41b3aa4e48de398de7a96b89217e6ce853`. Academy's avatar code uses
`static/avatars` in `dotmac_academy_app:app/web/account.py` at
`22921f87c884aeacae55c7f6c4348a7be370a145`. Both ERP and Sub keep storage
behind product-owned service interfaces. A second client library for the same
Dotmac store duplicates error handling and stream lifecycle work.

## Decision

For a Python application that accesses `dotmac-s3` through the S3 protocol, use
the MinIO Python SDK as its standard client. ERP's existing storage
service is the reference for SDK choice and adapter placement; it is not a
claim that every ERP operation already meets the behavioral target below. Each
product keeps its own narrow adapter and its existing endpoint, bucket,
credentials, and object-key policy under that application's persistence owner.
Application callers depend on the adapter, not on SDK types or provider-specific
exceptions. This does not authorize a product to embed an external application
connector or its provider credential in its runtime.

The adapter contract covers bucket readiness, upload, complete download,
streamed download, existence, and deletion where the product needs them.
Behavioral parity is proven for each migrated product. Its adapter normalizes
missing-object failures on the operations whose callers rely on them, closes
and releases every response it opens, and preserves content metadata. Tests
exercise these behaviors with an injected fake client and at least one
sensitivity case for an error or response-lifecycle regression. A repository
pins and validates the SDK version it actually installs; a dependency
declaration alone is insufficient. ERP's unproven error mapping on other
operations remains a separate follow-up, not evidence for this migration.

Sub migrates `app/services/object_storage.py` in a product change. Academy adopts
this client standard only if it later adopts S3-compatible object storage.
There is no requirement to move Academy's existing files as part of this
decision. A shared distribution is a separate product-first extraction
decision, justified by proven repeated behavior and a consumer cutover.

This decision does not change the `dotmac-s3` server, configured endpoint,
bucket name, credentials, backups, or production configuration. Existing
bucket-readiness behavior may still create the configured bucket when it is
absent; that behavior is covered by the product's deployment verification.
The retained server's maintenance and recovery risks remain separately open.

## Consequences

The client implementations converge on one SDK while each app retains its own
storage authority and configuration. Sub's SDK replacement changes an I/O
boundary and needs product CI plus deployment verification before rollout.
Failure and streaming behavior must remain visible to existing callers.

## Drift prevention

Sub's migration includes focused tests for its storage adapter, and product CI
will evaluate them at the PR's exact revision. ERP's existing adapter remains
under its own product tests. A fleet-wide import/dependency guard and a shared
behavior-contract suite are **not implemented by this ADR**; until they are,
cross-repository convergence is review discipline with the precise product
revisions recorded above. A later enforcement slice must enumerate actual
consumers and prove it detects a planted direct SDK import outside the adapter
and a stale dependency. The Governance ADR remains proposed until a named
human approval is recorded; this draft claims neither fleet conformance nor
production validation.
