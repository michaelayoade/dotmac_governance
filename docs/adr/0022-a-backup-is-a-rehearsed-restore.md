# 0022. A backup is a rehearsed restore, and the role layer is part of it

- Status: Proposed
- Date: 2026-08-30
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Organization-wide engineering standards, and every enrolled Dotmac repository whose deployment owns a PostgreSQL database
- Classification: Internal

## Context

On 2026-08-30 the newest production backup of the vendor control plane was
restored into a disposable, network-isolated PostgreSQL 16 container. This was
an execution, not an inspection.

`pg_restore` exited **1** with **114 errors**, every one of them a missing
role: `app_admin` 56, `platform_api` 34, `app_user` 20, `outbox_dispatcher` 2,
`platform_outbox_dispatcher` 2.

It did not stop. It left behind **45 user tables, 23 of 26 RLS policies, and 16
tables with row-level security enabled** — and underneath them no roles, no
grants, and every object owned by whoever ran the restore.

The cause is one flag. A single-database `pg_dump --dbname` captures
object-level `GRANT`s and RLS policies but **never role definitions**, because
roles are cluster-level objects. The dump's table of contents shows the
asymmetry exactly: **55 ACL entries, 26 POLICY entries, ZERO role objects.**
Nothing in the fleet runs `pg_dumpall --globals-only`, and the same shape is
present in ERP, in `dotmac_sub` (two scripts), and in SON.

**Why this is worse than a backup that fails outright.** A failed backup is a
known gap. This produces a database that LOOKS restored. Under the dual-plane
persistence rule (`dotmac_starter_mt` ADR 0023), the REVOCATION of `platform_api`
from tenant tables IS the plane isolation — there is no policy to see, because
the control is a grant. An operator who checks `pg_policies` after a recovery
sees 23 policies and concludes the isolation model came back. It did not. The
policies are inert without the roles they name, and the plane whose isolation is
a revocation has no isolation at all.

The repair method already exists and was proven elsewhere. The Workspace
recovery drill established three PostgreSQL facts that reasoning had not:
role MEMBERSHIPS are cluster-level and absent from a database dump, so a
restored database served `permission denied for table tenants` while holding a
complete copy of its data; PostgreSQL 16 memberships carry their own `INHERIT`
option, which is a separate fact from the role's; and `pg_dump` under FORCEd
RLS fails LOUDLY as the owner rather than silently truncating. Workspace's
backup now emits a role and membership prelude computed from a CLOSURE of what
that database actually references — deliberately not `pg_dumpall --roles-only`,
which would copy ERP's and Sub's role inventory into the Workspace's backup —
and deliberately excludes passwords and superusers.

This record is here rather than in a product because five estates share the
defect and none of them can bind the others, and because the facility that
should carry the fix — `dotmac-deployment-foundation` — is already the declared
owner of stateless deployment execution and recovery for the fleet.

## Decision

### 1. The standard

> A backup is DEFINED BY A REHEARSED RESTORE into a fresh, isolated instance.
> The existence of a dump file is not a backup, and a dump that omits the role
> layer is not a restore point at all.

### 2. What is backed up is a BUNDLE, not a dump

A recovery bundle is:

- the database dump;
- a **role and membership prelude**, computed from a closure of the roles the
  database actually references — never a cluster-wide role export, which would
  carry a neighbouring estate's inventory into this bundle, and never including
  passwords or superuser attributes;
- the extension set the database requires;
- the migration head it was taken at;
- a manifest binding the digest of each of the above.

The manifest is not bookkeeping. A bundle is assembled from independently
produced parts, and any three of them agreeing proves nothing about the fourth
— the same argument ADR 0014 § 6 makes for a deployment authorization, applied
to the artefact a recovery reads.

### 3. What the rehearsal must PROVE, enumerated

Into a fresh instance with no pre-existing roles, the restore proves:

1. every referenced role EXISTS, with its declared attributes;
2. role MEMBERSHIPS, and for PostgreSQL 16 the `INHERIT` option carried by each
   membership rather than by the role;
3. object OWNERSHIP matches the intended owner, not the restoring identity;
4. GRANTs, and DEFAULT PRIVILEGES, which govern objects created afterwards;
5. row-level security ENABLED **and** FORCED — two separate facts, and a table
   that is enabled but not forced exempts its owner;
6. every POLICY present and attached to a role that exists;
7. the EXTENSION set;
8. the MIGRATION HEAD;
9. that a TENANT role cannot reach a PLATFORM table — asserted by ATTEMPTING
   the read as that role and requiring the refusal, never by reading a catalogue
   that would have looked identical before the roles were restored.

Property 9 is the one the vendor control-plane restore silently lost, and it is
the one no catalogue query can answer.

### 4. A validator may never create a role it is checking for

The rehearsal harness is forbidden from creating, altering or granting anything
from its own configuration in order to make its checks pass. A validator that
can manufacture a role can always make its own check green, and what it then
measures is its own configuration file rather than the bundle.

A missing role is a FAILED REHEARSAL. The repair belongs in the backup that
omitted it.

### 5. Exit status is insufficient in BOTH directions

The measured restore exited non-zero **and** produced a usable-looking
database. The Workspace drill shows the converse: a restore can exit zero and
leave a database that refuses every query its application makes, because the
memberships were never in the dump.

A recovery verdict is therefore the enumerated property set in § 3, reported
per property. Reading the process's exit code is not the check; it is one input
to it, and on its own it has been wrong in both directions on measured evidence.

### 6. Ownership

| Owner | Owns |
| --- | --- |
| `dotmac-deployment-foundation` | the bundle format, the closure computation, the rehearsal harness and its verdict |
| Product repository | declaring its database, its role contract and its expected plane boundaries |
| Deployment control | when a rehearsal is required, and what an expired rehearsal blocks |
| Governance | this standard |

A product may not implement its own rehearsal harness. Five per-product scripts
is how five estates arrived at the same defect independently.

### 7. A rehearsal EXPIRES

A recovery claim cites the last rehearsal by immutable reference — a run
identifier and the bundle digest it read. A rehearsal older than the declared
interval does not make the claim weaker; it makes the claim UNPROVEN, which is
a distinct verdict from proven-bad (ADR 0015 § 1) and must be reported as its
own.

## Consequences

- Every existing backup in the fleet is reclassified as a data copy, not a
  restore point, until its estate ships a bundle and passes a rehearsal. That
  is an uncomfortable statement about the present and an accurate one.
- Backups get larger and slower by the size of a prelude, which is negligible,
  and by the cost of computing a closure, which is not free.
- Rehearsal needs a disposable instance on a schedule, which is real
  infrastructure with a real bill.
- A restore that today "works" will start failing the rehearsal. That is the
  control functioning: the failure already existed and was being reported as
  success.
- Passwords are deliberately excluded from the bundle, so a recovery is not
  complete until credentials are re-supplied from their approved store. This
  record does not decide that path, and states the gap rather than implying the
  bundle closes it.

## Drift prevention

**Enforcement status: none yet, stated rather than implied.**

What is decidable from repository content, and could become a
`standards_control` family over a declared backup surface:

- a backup script invoking a single-database `pg_dump` with no companion role
  export in the same artefact — the exact shape measured in four estates;
- a declared backup surface that names nothing, which passes every content
  check for the wrong reason and must be a diagnostic rather than a skip;
- a rehearsal harness that issues `CREATE ROLE`, `ALTER ROLE` or `GRANT`
  against the instance it is validating, which is § 4 violated in a way a
  reader can see in the source.

What CANNOT be derived here: whether a rehearsal actually ran, what it proved,
and when. Those are facts about runs and about production artefacts. ADR 0013
§ 1 puts them outside repository-local derivation and § 5 permits automation
only through a declared oracle; a rehearsal verdict is a `deployment_run`-shaped
claim and no contract declares that oracle today.

Non-vacuity, stated in advance so the family cannot be built without it: each
diagnostic gets a planted-violation proof — a synthetic repository shown to go
RED — alongside a conforming one shown to go green. A restore check demonstrated
only against a clean tree passes for the wrong reason, which is the same defect
this record is about.

The ownership assignment in § 6 and the rehearsal interval in § 7 are named
decisions Michael has not made, recorded as open decision 25.
