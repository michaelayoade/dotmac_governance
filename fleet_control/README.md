# Fleet control — the decomposition matrix

The canonical fleet artifact. Repositories reference **its rows**; they do not
maintain competing plans.

| Piece | Path |
|---|---|
| data | `fleet_control/fleet-decomposition.json` |
| schema | `agent_control/schema/fleet-decomposition.schema.json` |
| validator + renderer | `tools/fleet_matrix.py` |
| gate | `tests/test_fleet_decomposition.py` |
| rendering | `docs/fleet-decomposition.md` *(generated — never hand-edited)* |

```bash
python3 tools/fleet_matrix.py check     # semantic invariants
python3 tools/fleet_matrix.py render    # regenerate the readable view
python3 -m unittest tests.test_fleet_decomposition
```

## Six entity types, because they have different invariants

| Entity | Id form | Holds |
|---|---|---|
| `modules[]` | `mod.conversations` | a distribution, its namespace, the capability **contracts** it owns externally |
| `capabilities[]` | `cap.inbound.observation` | owned facts (with machine keys), current claims, target boundary |
| `assemblies[]` | `asm.isp` | a product/SKU |
| `bindings[]` | `bind.isp.conversation-thread` | assembly × capability × `local`\|`remote` |
| `cutovers[]` | `cut.sub.conversations-v1` | one source authority → one target binding, with four gates |
| `decisions[]` | `dec.identity.principal-mapping` | an adjudication, its order and what it blocks |

## The rules the gate enforces

1. **Extraction is computed, never assigned.** A cutover has four gates and no
   status field. A module is `extracted` only when every cutover into it has
   authority moved, source consuming, parity proven and old writer retired.
   Packages are supply evidence; completed authority cutovers are progress.
2. **Installation is per binding, not per module.** The same capability may be
   installed locally in one assembly and bound remotely in another. `remote`
   means another system **decides**; a third-party provider reached over the
   network is `transport`, and transport is never authority.
3. **Gates belong to a transition.** One module may have several source
   cutovers in different states — `cut.crm.ticketing-v1` and
   `cut.sub.ticketing-v1` target the same capability and are not the same job.
4. **Facts carry stable machine keys.** `fact.support.ticket-status`, not prose.
   Two capabilities claiming one fact is a hard failure, which is only possible
   because the key is machine-readable.
5. **Multiple current claims need an unresolved adjudication.** Contested
   authority is legitimate *while being adjudicated* and a defect otherwise.
6. **A stateful module owns a `mod_*` namespace; a host facility does not.**
   Being both is the contradiction that had licensing living in `public` while
   calling itself a module.
7. **Display codes are never foreign keys.** `M01`, `I1`, `A1` order and label.
   Every reference is a semantic id.

## Referencing a row from a repository

A repository's `EXTRACTION.toml` names the rows it implements. Use **semantic
ids only**:

```toml
# packages/dotmac-ticketing/EXTRACTION.toml
fleet_module = "mod.ticketing"
fleet_capabilities = ["cap.support.ticket-lifecycle"]
fleet_cutovers = ["cut.vendor-cp.ticketing-v1", "cut.sub.ticketing-v1"]
```

`M02` must never appear. Display codes are reordered for readability; semantic
ids are immutable, which is what makes them safe to key on.

Governance is pinned by exact commit through `.dotmac/standards-profile.json`,
so a matrix revision is a reviewable, versioned fleet event rather than a wiki
edit.

## Externally a module owns a contract; internally services own decisions

`owns_capabilities` is the module's **external** contract — what other assemblies
may depend on. Inside a module, named services own the individual decisions and
transitions, exactly as Sub's 426 named SOT owners do today. A module is not a
single owner, and it is not a bag of unowned code either.

## Keeping it honest

Every row carries `evidence` pointing at a dated inventory or design document,
and `source_revisions` records where the claims were measured. **Facts go stale.**
A matrix that disagrees with the code is wrong, not authoritative — re-measure
rather than trusting it.
