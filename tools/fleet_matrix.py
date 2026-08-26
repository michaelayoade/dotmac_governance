#!/usr/bin/env python3
"""Validate and render the fleet decomposition matrix.

The matrix holds six entity types with different invariants. `fleet-decomposition
.schema.json` is the STRUCTURAL contract; this module enforces the semantic
invariants a JSON Schema cannot express, and renders the human-readable view.

## The invariants that need code

1. **Extraction is computed, never assigned.** A cutover has four gates and no
   status field. `extraction_state` is derived from them, so nobody can mark a
   module "done" by editing a string. See `cutover_state`.
2. **Duplicate fact ownership is detectable.** Facts carry stable machine keys,
   so two capabilities claiming one fact is a hard error rather than something a
   reader might notice in prose.
3. **Multiple current claims require an unresolved adjudication.** More than one
   repository asserting authority is legitimate *while it is being adjudicated*
   and is a defect otherwise.
4. **Display codes are not foreign keys.** `M01`/`I1`/`A1` are ordering aids. A
   reference anywhere must be a semantic id, and nothing outside the matrix —
   `EXTRACTION.toml` least of all — may key on a display code.
5. **A stateful module owns a namespace; a host facility does not.** Being both
   is the contradiction that put licensing in `public` while calling it a module.

Stdlib only, matching `tools/check_adrs.py`.

    python3 tools/fleet_matrix.py check
    python3 tools/fleet_matrix.py render [--out docs/fleet-decomposition.md]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = REPO_ROOT / "fleet_control" / "fleet-decomposition.json"
SCHEMA_PATH = REPO_ROOT / "agent_control" / "schema" / "fleet-decomposition.schema.json"
RENDER_PATH = REPO_ROOT / "docs" / "fleet-decomposition.md"

#: The four conditions of extraction, in the order they must be satisfied.
GATES = ("authority_moved", "source_consuming", "parity_proven", "old_writer_retired")

ID_PREFIXES = {
    "modules": "mod.",
    "capabilities": "cap.",
    "assemblies": "asm.",
    "bindings": "bind.",
    "cutovers": "cut.",
    "decisions": "dec.",
}


@dataclass(frozen=True)
class Finding:
    """One validation failure, with the entity it belongs to."""

    entity: str
    message: str

    def __str__(self) -> str:
        return f"{self.entity}: {self.message}"


def load(path: Path = DATA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


# ── Computed extraction state ───────────────────────────────────────────────


def cutover_state(cutover: dict[str, Any]) -> str:
    """Derive a cutover's state from its gates. Never read from the data.

    `complete` requires all four gates passed — that IS the definition of
    extracted. A module whose package and tables exist but whose gates are
    untouched is `not-started`, and saying so is the point.
    """
    states = [cutover["gates"][gate]["state"] for gate in GATES]
    if all(state == "passed" for state in states):
        return "complete"
    if any(state == "blocked" for state in states):
        return "blocked"
    if any(state in ("passed", "in-progress") for state in states):
        return "in-progress"
    return "not-started"


def module_extraction_state(data: dict[str, Any], module_id: str) -> str:
    """Whether a module is EXTRACTED, computed from its cutovers.

    Extracted iff the module has at least one cutover and every cutover into it
    is complete. No cutovers at all means `no-cutover-defined` — which is not a
    milder form of progress, it is the absence of a plan.
    """
    cutovers = cutovers_for_module(data, module_id)
    if not cutovers:
        return "no-cutover-defined"
    states = {cutover_state(cutover) for cutover in cutovers}
    if states == {"complete"}:
        return "extracted"
    if "blocked" in states:
        return "blocked"
    if states & {"in-progress", "complete"}:
        return "in-progress"
    return "not-started"


def cutovers_for_module(data: dict[str, Any], module_id: str) -> list[dict[str, Any]]:
    """Every cutover whose target binding resolves to a capability this module owns."""
    module = next((m for m in data["modules"] if m["id"] == module_id), None)
    if module is None:
        return []
    owned = set(module["owns_capabilities"])
    bindings = {b["id"]: b for b in data["bindings"]}
    out = []
    for cutover in data["cutovers"]:
        binding = bindings.get(cutover["target_binding"])
        if binding is not None and binding["capability"] in owned:
            out.append(cutover)
    return out


# ── Validation ──────────────────────────────────────────────────────────────


def _index(data: dict[str, Any]) -> dict[str, set[str]]:
    return {key: {row["id"] for row in data[key]} for key in ID_PREFIXES}


def check(data: dict[str, Any]) -> list[Finding]:
    """Every semantic invariant. Returns findings; empty means the matrix holds."""
    findings: list[Finding] = []
    ids = _index(data)

    # 1. Ids are unique and correctly prefixed.
    for collection, prefix in ID_PREFIXES.items():
        counts = Counter(row["id"] for row in data[collection])
        for row_id, count in counts.items():
            if count > 1:
                findings.append(Finding(row_id, f"duplicate id in {collection}"))
            if not row_id.startswith(prefix):
                findings.append(
                    Finding(row_id, f"id in {collection} must start with {prefix!r}")
                )

    # 2. Every reference resolves to a semantic id.
    for capability in data["capabilities"]:
        for dependency in capability.get("depends_on", []):
            if dependency not in ids["capabilities"]:
                findings.append(
                    Finding(capability["id"], f"depends_on unknown {dependency}")
                )
        adjudication = capability.get("adjudication")
        if adjudication and adjudication not in ids["decisions"]:
            findings.append(
                Finding(capability["id"], f"adjudication unknown {adjudication}")
            )

    for module in data["modules"]:
        for capability in module["owns_capabilities"]:
            if capability not in ids["capabilities"]:
                findings.append(
                    Finding(module["id"], f"owns unknown capability {capability}")
                )

    for binding in data["bindings"]:
        if binding["assembly"] not in ids["assemblies"]:
            findings.append(Finding(binding["id"], "unknown assembly"))
        if binding["capability"] not in ids["capabilities"]:
            findings.append(Finding(binding["id"], "unknown capability"))
        if binding["installation"] == "remote" and not binding.get("remote_authority"):
            findings.append(
                Finding(
                    binding["id"],
                    "a remote binding must name the remote_authority that decides; "
                    "reaching a third-party provider over the network is transport, "
                    "not a remote binding",
                )
            )

    for cutover in data["cutovers"]:
        if cutover["target_binding"] not in ids["bindings"]:
            findings.append(Finding(cutover["id"], "unknown target_binding"))
        for decision in cutover.get("blocked_by", []):
            if decision not in ids["decisions"]:
                findings.append(Finding(cutover["id"], f"blocked_by unknown {decision}"))

    for decision in data["decisions"]:
        for blocked in decision.get("blocked_by", []):
            if blocked not in ids["decisions"]:
                findings.append(Finding(decision["id"], f"blocked_by unknown {blocked}"))
        for target in decision.get("blocks", []):
            known = any(target in group for group in ids.values())
            if not known:
                findings.append(Finding(decision["id"], f"blocks unknown {target}"))

    # 3. One fact, one owning capability.
    owners: dict[str, list[str]] = defaultdict(list)
    for capability in data["capabilities"]:
        for fact in capability.get("owned_facts", []):
            owners[fact["key"]].append(capability["id"])
    for fact_key, claimants in owners.items():
        if len(claimants) > 1:
            findings.append(
                Finding(
                    fact_key,
                    f"owned by {len(claimants)} capabilities ({', '.join(sorted(claimants))}) "
                    "— one module owns each fact",
                )
            )

    # 4. Multiple current claims need an UNRESOLVED adjudication.
    unresolved = {
        decision["id"]
        for decision in data["decisions"]
        if decision["state"] != "resolved"
    }
    for capability in data["capabilities"]:
        claims = capability["current_claims"]
        adjudication = capability.get("adjudication")
        if len(claims) > 1:
            if not adjudication:
                findings.append(
                    Finding(
                        capability["id"],
                        f"{len(claims)} current claims but no adjudication reference",
                    )
                )
            elif adjudication not in unresolved:
                findings.append(
                    Finding(
                        capability["id"],
                        f"{len(claims)} current claims but {adjudication} is resolved "
                        "— record the single surviving claim",
                    )
                )

    # 5. A stateful module owns a namespace; a host facility does not.
    for module in data["modules"]:
        namespace = module.get("namespace")
        if module["kind"] == "module" and namespace is None:
            findings.append(
                Finding(module["id"], "a stateful module must declare a namespace")
            )
        if module["kind"] == "host-facility" and namespace is not None:
            findings.append(
                Finding(
                    module["id"],
                    "a host facility lives in the host schema and must not claim a "
                    "mod_* namespace — it cannot be both",
                )
            )

    # 6. Namespaces, prefixes and branch labels are unique fleet-wide.
    for field in ("db_schema", "migration_prefix", "branch_label"):
        seen: dict[str, str] = {}
        for module in data["modules"]:
            namespace = module.get("namespace")
            if not namespace:
                continue
            value = namespace[field]
            if value in seen:
                findings.append(
                    Finding(module["id"], f"{field} {value!r} already used by {seen[value]}")
                )
            seen[value] = module["id"]

    # 7. Open decisions have a unique adjudication order.
    open_orders = Counter(
        decision["order"] for decision in data["decisions"] if decision["state"] == "open"
    )
    for order, count in open_orders.items():
        if count > 1:
            findings.append(
                Finding(f"order={order}", f"{count} open decisions share an order")
            )

    # 8. A resolved decision states its disposition; a blocked one says why.
    for decision in data["decisions"]:
        if decision["state"] == "resolved" and not decision.get("disposition"):
            findings.append(Finding(decision["id"], "resolved without a disposition"))
        if decision["state"] in ("blocked", "deferred") and not decision.get("remaining"):
            findings.append(
                Finding(decision["id"], f"{decision['state']} without a `remaining`")
            )

    # 9. No cutover may carry a hand-assigned status.
    for cutover in data["cutovers"]:
        if "status" in cutover or "state" in cutover:
            findings.append(
                Finding(
                    cutover["id"],
                    "extraction state is COMPUTED from the four gates and must never "
                    "be assigned by hand",
                )
            )

    return findings


# ── Rendering ───────────────────────────────────────────────────────────────

_STATE_MARK = {
    "extracted": "✅ extracted",
    "in-progress": "◐ in progress",
    "blocked": "⛔ blocked",
    "not-started": "○ not started",
    "no-cutover-defined": "— no cutover defined",
}


def render(data: dict[str, Any]) -> str:
    """The human-readable view. Generated — never hand-edited."""
    lines: list[str] = []
    add = lines.append

    add("# Fleet decomposition matrix")
    add("")
    add("<!-- GENERATED by tools/fleet_matrix.py — do not edit by hand. -->")
    add("")
    add(f"**As of:** {data['as_of']}")
    add("")
    add("Measured at: " + ", ".join(f"`{k}` {v}" for k, v in sorted(data["source_revisions"].items())))
    add("")
    add("> Extraction state is **computed** from four gates per cutover — authority")
    add("> moved, source consuming, parity proven, old writer retired. A package and")
    add("> tables are supply evidence; only a completed authority cutover is progress.")
    add("")

    add("## Modules")
    add("")
    add("| Module | Kind | Band | Namespace | Owns | Extraction |")
    add("|---|---|---|---|---|---|")
    for module in data["modules"]:
        namespace = module.get("namespace")
        if namespace:
            allocated = "" if namespace["allocated"] else " *(unallocated)*"
            ns = f"`{namespace['db_schema']}`/`{namespace['migration_prefix']}`{allocated}"
        else:
            ns = "— host schema"
        state = module_extraction_state(data, module["id"])
        add(
            f"| `{module['id']}` {module['name']} | {module['kind']} | {module['band']} "
            f"| {ns} | {len(module['owns_capabilities'])} | {_STATE_MARK[state]} |"
        )
    add("")

    add("## Capabilities")
    add("")
    add("| Capability | Target boundary | Facts | Current claims | Adjudication |")
    add("|---|---|---|---|---|")
    for capability in data["capabilities"]:
        claims = capability["current_claims"]
        claim_text = ", ".join(f"{c['repository']}" for c in claims) or "—"
        adjudication = capability.get("adjudication") or "—"
        add(
            f"| `{capability['id']}` {capability['name']} | {capability['target_boundary']} "
            f"| {len(capability.get('owned_facts', []))} | {len(claims)}: {claim_text} "
            f"| {adjudication} |"
        )
    add("")

    add("## Bindings — assembly × capability × local/remote")
    add("")
    add("| Binding | Assembly | Capability | Installation | State |")
    add("|---|---|---|---|---|")
    for binding in data["bindings"]:
        installation = binding["installation"]
        if installation == "remote":
            installation = f"**remote** → {binding['remote_authority']}"
        transport = binding.get("transport")
        if transport:
            installation += f" <br><sub>transport: {', '.join(transport)}</sub>"
        add(
            f"| `{binding['id']}` | `{binding['assembly']}` | `{binding['capability']}` "
            f"| {installation} | {binding['state']} |"
        )
    add("")

    add("## Cutovers — source authority → target binding")
    add("")
    add("| Cutover | Source | Target | Authority | Consuming | Parity | Retired | Computed |")
    add("|---|---|---|---|---|---|---|---|")
    for cutover in data["cutovers"]:
        gates = cutover["gates"]
        cells = " | ".join(gates[gate]["state"] for gate in GATES)
        add(
            f"| `{cutover['id']}` | {cutover['source']['repository']} "
            f"| `{cutover['target_binding']}` | {cells} | **{cutover_state(cutover)}** |"
        )
    add("")

    add("## Decisions — adjudication order")
    add("")
    add("| # | Decision | State | Blocks | Remaining |")
    add("|---|---|---|---|---|")
    for decision in sorted(data["decisions"], key=lambda d: d["order"]):
        remaining = decision.get("remaining") or decision.get("disposition") or ""
        if len(remaining) > 160:
            remaining = remaining[:157] + "…"
        add(
            f"| {decision['order']} | `{decision['id']}` {decision['title']} "
            f"| **{decision['state']}** | {len(decision.get('blocks', []))} | {remaining} |"
        )
    add("")

    extracted = sum(
        1
        for module in data["modules"]
        if module_extraction_state(data, module["id"]) == "extracted"
    )
    add("## Programme state")
    add("")
    add(f"- Modules defined: **{len(data['modules'])}**")
    add(f"- Modules **extracted**: **{extracted}**")
    add(f"- Cutovers defined: **{len(data['cutovers'])}**, "
        f"complete: **{sum(1 for c in data['cutovers'] if cutover_state(c) == 'complete')}**")
    add(f"- Open decisions: **{sum(1 for d in data['decisions'] if d['state'] == 'open')}**"
        f" (blocked: {sum(1 for d in data['decisions'] if d['state'] == 'blocked')})")
    add("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="validate the matrix")
    render_parser = sub.add_parser("render", help="write the human-readable matrix")
    render_parser.add_argument("--out", type=Path, default=RENDER_PATH)
    args = parser.parse_args(argv)

    data = load()
    if args.command == "check":
        findings = check(data)
        for finding in findings:
            print(f"FAIL {finding}", file=sys.stderr)
        if findings:
            print(f"\n{len(findings)} finding(s)", file=sys.stderr)
            return 1
        print(
            f"fleet matrix OK — {len(data['modules'])} modules, "
            f"{len(data['capabilities'])} capabilities, {len(data['cutovers'])} cutovers, "
            f"{sum(1 for d in data['decisions'] if d['state'] == 'open')} open decisions"
        )
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(data) + "\n", encoding="utf-8")
    print(f"rendered {args.out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
