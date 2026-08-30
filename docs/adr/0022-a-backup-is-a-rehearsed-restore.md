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
Nothing in the fleet captures the role layer at all, and the same shape is
present in ERP, in `dotmac_sub` (two scripts), and in SON.

**The remedy is `pg_dumpall --globals-only --no-role-passwords`, and the flag
is the whole point.** Earlier drafts of this record named the bare form. The
bare form emits **SCRAM password verifiers** alongside the roles, which is the
exact material § 2 forbids the bundle to contain — so a record recommending it
would have instructed its readers to produce a bundle it prohibits.
`--no-role-passwords` substitutes a null password for every role, which is
precisely the shape wanted here: the structural role layer travels, and the
secret does not.

That is not a redaction step bolted on afterwards. The flag excludes the
material **at the source**, so no filtering pass exists to be forgotten,
misconfigured or outgrown — and the difference between the two forms is one
argument, which is why this record names the whole invocation rather than the
tool.

**Why this is worse than a backup that fails outright.** A failed backup is a
known gap. This produces a database that LOOKS restored. Under the dual-plane
persistence rule (`dotmac_starter_mt` ADR 0023), the REVOCATION of
`platform_api` from tenant tables IS the plane isolation — there is no policy
to see, because the control is a grant. An operator who checks `pg_policies`
after a recovery sees 23 policies and concludes the isolation model came back.
It did not. The policies are inert without the roles they name, and the plane
whose isolation is a revocation has no isolation at all.

**This record does not codify existing practice, and saying otherwise would be
the more comfortable error.** The Workspace recovery drill is real and
established three PostgreSQL facts that reasoning had not: role MEMBERSHIPS are
cluster-level and absent from a database dump, so a restored database served
`permission denied for table tenants` while holding a complete copy of its data;
PostgreSQL 16 memberships carry their own `INHERIT` option, which is a separate
fact from the role's; and `pg_dump` under FORCEd RLS fails LOUDLY as the owner
rather than silently truncating.

But **nothing in the fleet derives a role closure — Workspace included.** The
absence WAS the finding. The closure was written for
`PostgresRecoveryBundleV1`, not ported from a product, which means ADR 0006's
product-first rule is satisfied by having looked and found nothing rather than
by an extraction. A record describing this as codified practice would send the
next implementer looking for a reference that does not exist.

Why a closure at all, rather than a declared list: **every estate documents
three roles and the cluster has five.** `outbox_dispatcher` and
`platform_outbox_dispatcher` appear in the failed restore's error tally and in
no repository's role contract. A list is a statement about what someone
remembered; a closure derived from the source catalog is a statement about what
the database actually references, and only the second one survives a role being
added by an operator.

**The strongest argument for this whole record is what the old verdict would
have certified.** The pre-existing definition of a `proved` recovery was *schema
present, row counts within tolerance, migration heads match*. Read those three
against the database the failed restore actually produced: 45 tables present,
row counts intact because the data restored fine, heads matching because
`alembic_version` is an ordinary table. **All three pass.** The verdict would
have returned `PROVED` for a database with no roles, no grants, superuser
ownership and no isolation whatsoever.

None of the three checks can see the role layer, so none of them can fail when
it is missing. That is not a gap in an otherwise sound verdict; it is a verdict
measuring the half of a restore that was never at risk. Any restatement of that
definition, anywhere, inherits the defect — which is why § 4 below fixes the
verdict itself rather than only adding checks beside it.

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

**A record naming four parts invites a bundle with four parts.** An earlier
draft of this section named the dump, a role prelude, extensions and the
migration head, and the shipped `PostgresRecoveryBundleV1` has **thirteen**. The
enumeration is therefore normative and complete, not illustrative:

| # | Part | Why it is separate |
| --- | --- | --- |
| 1 | `dump` | the data and schema |
| 2 | `role_closure` | roles the database actually references, derived from the source catalog |
| 3 | `role_attributes` | per-role attributes, **never a password verifier** |
| 4 | `memberships` | including PG16 per-membership `INHERIT` and `SET`, which the role's own flags do not carry |
| 5 | `object_ownership` | ownership is a distinct fact from privilege, and a restore silently reassigns it |
| 6 | `default_privileges` | governs objects created AFTER the restore; invisible in any snapshot of current objects |
| 7 | `schema_privileges` | schema `USAGE` gates everything beneath it |
| 8 | `object_privileges` | table- and routine-level grants |
| 9 | `fine_grained_acls` | column ACLs, plus the role lists attached to policies |
| 10 | `row_security` | `ENABLE` **and** `FORCE` recorded separately — a table enabled but not forced exempts its owner |
| 11 | `extensions` | |
| 12 | `tablespaces` | an explicit decision: **`none` counts, silence does not** |
| 13 | `migration_heads` | |
| — | manifest | binds the digest of every part above |

Two of these carry a rule inside them. **Part 3 never includes a verifier** —
password material is absent by construction, not redacted afterwards, and a
bundle that filters is one bug away from a bundle that leaks. **Part 12 refuses
silence**: an absent tablespace section is indistinguishable from a bundle taken
before anyone thought about tablespaces, so `none` is a recorded answer and the
field's absence is a malformed bundle.

The manifest is not bookkeeping. A bundle is assembled from independently
produced parts, and any twelve of them agreeing proves nothing about the
thirteenth — the same argument ADR 0014 § 6 makes for a deployment
authorization, applied to the artefact a recovery reads.

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
9. that a TENANT role cannot reach a PLATFORM table — asserted by **EFFECTIVE
   TABLE OR COLUMN privileges**, evaluated across **all seven table privileges**
   (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`)
   with `has_table_privilege` / `has_column_privilege` semantics.

Property 9 is the one the vendor control-plane restore silently lost, and it is
the one no catalogue LISTING can answer. The method is part of the property
rather than an implementation note, because the wrong method **passes when the
system is broken**:

`information_schema.table_privileges` and its relatives enumerate **direct**
grants only. A role that reaches a platform table THROUGH A MEMBERSHIP appears
in that view as having no access at all, so the isolation assertion returns "no
privilege found" and goes green over exactly the leak it exists to detect. This
is not hypothetical and not a beginner's error: **Workspace's own isolation
tests carry this bug**, and the recovery lane's first draft inherited it before
catching it. Two independent implementations reached for the listing first.

`has_table_privilege` and `has_column_privilege` resolve membership,
inheritance and `PUBLIC` the way the executor does. Where a check has a listing
form and an effective form, this record requires the effective one — a privilege
question must be answered by the same machinery that will answer it at runtime.

Two narrowings are refused, because each leaves a real reach unmeasured:

- **`SELECT` alone is not the property.** A tenant role holding `INSERT`,
  `UPDATE`, `DELETE` or `TRUNCATE` on a platform table has crossed the plane
  without ever reading a row, and `REFERENCES` and `TRIGGER` are reach as well.
  All seven are evaluated, and the failing privilege is named.
- **Table granularity alone is not the property.** A column-level grant leaves
  `has_table_privilege` false while the column is readable, so a check stopping
  at the table reports isolation over a live path. Where a column grant can
  exist, `has_column_privilege` is the question asked.

### 4. The verdict IS the enumerated set, never a summary of it

A recovery verdict is the property set in § 3, reported per property. It may not
be redefined as a smaller set of checks that stands in for them.

This is the § 3 enumeration's whole point, and the Context states why: *schema
present, row counts in tolerance, heads match* returns `PROVED` for the database
the failed restore produced. A summary verdict is not a convenience over the
enumeration — it is a different, weaker claim wearing the same word, and the
three summary checks happen to be exactly the three that a missing role layer
cannot disturb.

Two consequences:

- **A verdict reports per property, so a reader can see WHICH property carried
  it.** An aggregate `PROVED` with no breakdown is unfalsifiable by inspection.
- **Adding a property is not a breaking change; dropping one is.** A bundle
  version that answers fewer properties than its predecessor is a narrowing of
  the claim and must be recorded as one, never absorbed as a refactor.

### 5. Credentials are post-restore bindings, never backup contents

A restore is five ordered steps, and the fifth is deliberately not a bundle
part:

1. provision a **fresh instance** with no pre-existing roles;
2. apply the **role and membership layer** — structural roles arrive with
   **null passwords**, per § 2 part 3 and the `--no-role-passwords` invocation;
3. restore the **dump**;
4. reconcile **ownership, privileges and row security** from the bundle's
   remaining parts;
5. **install credentials** from the environment's approved secret source.

Step 5 is the clause: **credentials are post-restore bindings, never backup
contents.** A restored role is a structural fact; the secret that authenticates
as it is an environment fact with its own lifetime and its own owner, and
binding the two into one artefact makes every copy of a backup a copy of a
credential.

Three rules follow, and the third is the one that gets negotiated away:

- **Production installs CURRENT credentials**, from that product's approved
  secret source — not the credentials that were live when the backup was taken.
  A restore is not a reason to resurrect a rotated secret.
- **An isolated rehearsal uses FRESH EPHEMERAL credentials, never production
  secrets.** A rehearsal that needs a production secret to pass has turned the
  rehearsal into a reason to hold one, which is the opposite of what a
  disposable instance is for.
- **A secret-source failure leaves the application STOPPED, never degraded.**
  No fallback, no cached last-known value, no reduced-function start. An
  application that starts without its credentials has either found another way
  in or is about to fail somewhere less observable, and both are worse than not
  starting.

Before the application starts, four things are proven, in this order:

1. **authentication** — each role can actually log in with the credential just
   installed;
2. **effective privileges** — the § 3 property 4 checks, now against the
   authenticating identity;
3. **RLS isolation** — § 3 properties 5, 6 and 9;
4. **wrong-credential REFUSAL** — a deliberately incorrect credential is
   rejected.

The fourth is not ceremony. The first three are all satisfied by an instance
that accepts anything — `trust` authentication in `pg_hba.conf` passes every one
of them — so without a negative case the suite proves the credentials work
without proving they are required.

### 6. A validator may never create a role it is checking for

The rehearsal harness is forbidden from creating, altering or granting anything
from its own configuration in order to make its checks pass. A validator that
can manufacture a role can always make its own check green, and what it then
measures is its own configuration file rather than the bundle.

A missing role is a FAILED REHEARSAL. The repair belongs in the backup that
omitted it.

### 7. Exit status is insufficient in BOTH directions

The measured restore exited non-zero **and** produced a usable-looking
database. The Workspace drill shows the converse: a restore can exit zero and
leave a database that refuses every query its application makes, because the
memberships were never in the dump.

A recovery verdict is therefore the enumerated property set in § 3, reported
per property, and § 4 forbids collapsing it into a summary. Reading the
process's exit code is not the check; it is one input to it, and on its own it
has been wrong in both directions on measured evidence.

### 8. Ownership

| Owner | Owns |
| --- | --- |
| `dotmac-deployment-foundation` | the bundle format, the closure computation, the rehearsal harness and its verdict |
| Product repository | declaring its database, its role contract and its expected plane boundaries |
| Deployment control | when a rehearsal is required, and what an expired rehearsal blocks |
| Governance | this standard |

A product may not implement its own rehearsal harness. Five per-product scripts
is how five estates arrived at the same defect independently.

### 9. A rehearsal EXPIRES

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
- Any recovery previously recorded as `PROVED` under the schema/row-count/heads
  definition is **reclassified as unproven**, not as failed. The old verdict
  could not see the role layer, so it never established the thing it was read as
  establishing — and a re-run, not a retraction, is what settles each case.
- Thirteen bundle parts is a larger artefact and a longer implementation than
  four. The count is not ambition: each part was added because a restore can be
  wrong in that specific way while every other part is right. Default
  privileges and per-membership `INHERIT` are the two that look redundant on a
  reading and are not.
- Passwords are excluded from the bundle at source by `--no-role-passwords`, so
  a recovery is not complete until § 5 step 5 installs credentials from the
  environment's approved secret source. That path is now DECIDED rather than
  left open, and it costs something: a rehearsal environment must be able to
  mint ephemeral credentials, and an application whose secret source is
  unreachable stays down instead of starting degraded.

## Drift prevention

**Enforcement status: none in this repository; one shipped implementation.**

`PostgresRecoveryBundleV1` is implemented in `dotmac_starter_mt` (pull request
#518, merged `d6b9aae5`) and is what § 2's thirteen parts and § 3's properties
are drawn from. Building it is what exposed the three defects this record
carried — the verifier-emitting flag, the four-part bundle and the
direct-grant isolation check — which is the ordinary and expected direction:
a specification survives contact with an implementation or it was not specific
enough to be wrong. It is a reference implementation, not fleet coverage.

What is decidable from repository content, and could become a
`standards_control` family over a declared backup surface:

- a backup script invoking a single-database `pg_dump` with no companion role
  export in the same artefact — the exact shape measured in four estates;
- a declared backup surface that names nothing, which passes every content
  check for the wrong reason and must be a diagnostic rather than a skip;
- a rehearsal harness that issues `CREATE ROLE`, `ALTER ROLE` or `GRANT`
  against the instance it is validating, which is § 6 violated in a way a
  reader can see in the source;
- an isolation assertion reading `information_schema.table_privileges` or
  another DIRECT-grant listing where § 3 property 9 requires effective-privilege
  semantics — the defect that passes while the system is broken, and which two
  independent implementations reached for first;
- a role or attribute export carrying password material — specifically a
  `pg_dumpall --globals-only` invocation WITHOUT `--no-role-passwords`, which is
  a one-argument difference and therefore exactly the drift a reviewer's eye
  slides over;
- a rehearsal harness naming a production secret path, which § 5 forbids: an
  isolated rehearsal mints ephemeral credentials, and a reference to the
  production source is visible in the source before it is visible in a run.

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

The ownership assignment in § 8 and the rehearsal interval in § 9 are named
decisions Michael has not made, recorded as open decision 25.
