# 0045. Co-deployed internal engines are explicit runtime authorities

- Status: Proposed
- Date: 2026-09-29
- Owner: Michael Ayoade
- Approver: Michael Ayoade (intended while Proposed)
- Scope: Organization-wide engineering standards and explicitly enrolled Dotmac repositories
- Classification: Internal
- Amends: 0011 — distinguishes one Governance-authorized co-deployed internal engine from a direct external connector without weakening the Integrator boundary

## Context

ADR 0011 makes Dotmac Integrator the runtime authority for provider connectors,
credentials, ingress and egress. That remains correct for third-party SaaS,
independently hosted or public APIs, messaging/calendar systems, payment APIs
and every integration crossing the approved deployment trust boundary.

Traccar has a different topology. It is deployed inside the ERP production
environment as Fleet's private GPS protocol engine. It has no user-facing
product surface; users and browsers never authenticate to or call it; ERP owns
the business decisions. Calling every private service exempt, however, would
turn a network label into a general escape from ADR 0011. The distinction needs
a Governance-owned exact authorization, never product prose or a self-declared
profile exception.

## Decision

### Co-deployed internal engine

A co-deployed internal engine satisfies every condition:

1. lifecycle-managed with one product's production environment;
2. not independently user-facing;
3. application API reachable only on an approved private network;
4. consumed through one product-owned domain service;
5. credentials and sessions never exposed to browsers or users;
6. product RBAC remains authoritative;
7. owns technical engine data, not product business entities; and
8. unavailability degrades only the owning product feature.

A hostname, Compose project, common owner or the word `internal` proves none
of these conditions.

### Governance owns every grant

`policies/external-connector-runtime-authority.json` is the only authorization
source. Version 2 names every coordinate: product, engine, runtime role, client
and service symbols, network, endpoint, ingress/database exposure, secret path
and capabilities, failure scope and data ownership. Wildcards are forbidden.
A product-authored copy is ignored. Source outside the exact client path stays
inside ADR 0011's ratchet.

### ERP Fleet to Traccar

The one authorization is:

```
dotmac_erp_app
    -> private dotmac_traccar_api
    -> http://traccar:8082
    -> FleetTrackingService -> TraccarClient
```

TCP/5001 is public GPS103 device ingress. TCP/8082 and TCP/5432 remain private.
Browser-to-Traccar is forbidden. Only the ERP `app` role may consume the API.
Worker and beat gain no permission.

ERP runtime may read exactly
`secret/data/dotmac/traccar/erp-service`, with exactly `read`. Create,
update, delete, list, metadata, policy administration and sibling access remain
forbidden. Provisioning authority stays separate.

ERP owns vehicles, drivers/employees, tracker mappings, Fleet RBAC and business
workflow. Traccar owns GPS protocol handling, raw positions, telemetry, GPS
history and raw tracker events. No duplicate full ERP telemetry store is
required or authorized.

### Integrator remains mandatory

ADR 0011 is unchanged for third-party SaaS, independently hosted/public APIs,
external messaging/calendar systems, payment/provider APIs and every trust-
boundary crossing. This record creates no product-selectable classification.
Another engine needs another complete Governance-owned policy entry.

## Consequences

- Only the exact authorized client source may be discounted from the connector
  ratchet after its boundary checks succeed.
- An arbitrary direct public API remains `connector.baseline.exceeded`.
- ERP must adopt the immutable accepted Governance revision before activation.
- Network attachment, OpenBao deployment and client activation remain later
  implementation work.
- Traccar failure may degrade Fleet only, never global ERP readiness.

## Drift prevention

- The policy parser rejects patterns, duplicate grants, public engine/API/DB
  exposure, browser/user access, non-ERP RBAC, broad secret paths and any
  capability other than read.
- Tests admit only the exact ERP/Traccar path and refuse another product,
  arbitrary module, public provider, public 8082/5432 and broad/sibling secret.
- A product profile cannot add an exemption.
- Until a named human accepts this record and ERP pins that commit, this record
  is non-normative and Step 3.5/4 remain blocked.
