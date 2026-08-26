"""The fleet decomposition matrix gate, with sensitivity proofs.

Every invariant here is paired with a mutation test that breaks the data and
asserts the check FIRES. A guard with no sensitivity proof is a guard that can
rot into a permanently-green assertion about nothing (ADR-0018), and this file
exists precisely to stop the matrix becoming decorative.

The load-bearing one is `test_extraction_is_computed_not_assigned`: extraction
state must be derived from the four gates, never written down. If that check
weakens, "extracted" becomes a string somebody edits and the programme loses its
only honest progress measure.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.fleet_matrix import (
    DATA_PATH,
    GATES,
    SCHEMA_PATH,
    check,
    cutover_state,
    load,
    module_extraction_state,
    render,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class FleetMatrixDataTests(unittest.TestCase):
    """The shipped matrix must hold every invariant."""

    def setUp(self) -> None:
        self.data = load()

    def test_the_shipped_matrix_passes_every_check(self) -> None:
        findings = check(self.data)
        self.assertEqual([], [str(f) for f in findings])

    def test_the_data_is_not_empty(self) -> None:
        """Sensitivity: a gate over an empty matrix would pass silently."""
        for collection in (
            "modules",
            "capabilities",
            "assemblies",
            "bindings",
            "cutovers",
            "decisions",
        ):
            self.assertTrue(self.data[collection], f"{collection} is empty")

    def test_the_schema_file_is_valid_json_and_describes_every_collection(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for collection in (
            "modules",
            "capabilities",
            "assemblies",
            "bindings",
            "cutovers",
            "decisions",
        ):
            self.assertIn(collection, schema["properties"])
            self.assertIn(collection, schema["required"])

    def test_display_codes_are_never_used_as_foreign_keys(self) -> None:
        """`M01`/`I1`/`A1` order and label. They must not be referenced.

        A display code as a foreign key is a rename waiting to break every
        consumer, and `EXTRACTION.toml` least of all may key on one.
        """
        display_codes = {
            row["display_code"]
            for collection in ("modules", "capabilities", "decisions")
            for row in self.data[collection]
            if row.get("display_code")
        }
        reference_fields = json.dumps(
            {
                "modules": [m["owns_capabilities"] for m in self.data["modules"]],
                "capability_deps": [
                    c.get("depends_on", []) for c in self.data["capabilities"]
                ],
                "adjudications": [
                    c.get("adjudication") for c in self.data["capabilities"]
                ],
                "bindings": [
                    [b["assembly"], b["capability"]] for b in self.data["bindings"]
                ],
                "cutovers": [
                    [c["target_binding"], c.get("blocked_by", [])]
                    for c in self.data["cutovers"]
                ],
                "decision_blocks": [
                    d.get("blocks", []) for d in self.data["decisions"]
                ],
            }
        )
        for code in display_codes:
            self.assertNotIn(
                f'"{code}"',
                reference_fields,
                f"display code {code} is used as a foreign key; use the semantic id",
            )


class ComputedExtractionTests(unittest.TestCase):
    """Extraction is derived from gates. This is the rule that must not weaken."""

    def setUp(self) -> None:
        self.data = load()

    def test_extraction_is_computed_not_assigned(self) -> None:
        """No cutover carries a hand-written status field."""
        for cutover in self.data["cutovers"]:
            self.assertNotIn("status", cutover, cutover["id"])
            self.assertNotIn("state", cutover, cutover["id"])

    def test_a_cutover_is_complete_only_when_all_four_gates_pass(self) -> None:
        cutover = copy.deepcopy(self.data["cutovers"][0])
        for gate in GATES:
            cutover["gates"][gate] = {"state": "passed"}
        self.assertEqual("complete", cutover_state(cutover))

        # Sensitivity: any single gate short of passed defeats completion.
        for gate in GATES:
            partial = copy.deepcopy(cutover)
            partial["gates"][gate] = {"state": "in-progress"}
            self.assertNotEqual(
                "complete",
                cutover_state(partial),
                f"completion survived {gate} being unfinished",
            )

    def test_a_package_with_untouched_gates_is_not_extracted(self) -> None:
        """The programme's headline correction, as an executable assertion.

        `mod.ticketing` has a distribution, a namespace and tables. It is not
        extracted, and the matrix must say so.
        """
        ticketing = next(
            m for m in self.data["modules"] if m["id"] == "mod.ticketing"
        )
        self.assertIsNotNone(ticketing["distribution"])
        self.assertIsNotNone(ticketing["namespace"])
        self.assertNotEqual(
            "extracted", module_extraction_state(self.data, "mod.ticketing")
        )

    def test_no_module_is_currently_extracted(self) -> None:
        """Pins the programme's actual state so progress is a visible diff.

        When this fails, something genuinely completed a cutover — update the
        assertion deliberately, and celebrate.
        """
        extracted = [
            module["id"]
            for module in self.data["modules"]
            if module_extraction_state(self.data, module["id"]) == "extracted"
        ]
        self.assertEqual([], extracted)

    def test_a_module_with_no_cutover_is_not_reported_as_progress(self) -> None:
        """"No cutover defined" is the absence of a plan, not a mild state."""
        self.assertEqual(
            "no-cutover-defined", module_extraction_state(self.data, "mod.ui")
        )


class SensitivityTests(unittest.TestCase):
    """Each check is broken on purpose and must be caught."""

    def setUp(self) -> None:
        self.data = load()

    def _messages(self, data: dict) -> str:
        return " | ".join(str(f) for f in check(data))

    def test_duplicate_fact_ownership_is_caught(self) -> None:
        """Prose cannot be checked for duplicate ownership; machine keys can."""
        data = copy.deepcopy(self.data)
        donor = next(c for c in data["capabilities"] if c.get("owned_facts"))
        thief = next(
            c
            for c in data["capabilities"]
            if c["id"] != donor["id"] and c.get("owned_facts") is not None
        )
        thief.setdefault("owned_facts", []).append(copy.deepcopy(donor["owned_facts"][0]))
        self.assertIn("one module owns each fact", self._messages(data))

    def test_multiple_claims_without_an_adjudication_are_caught(self) -> None:
        data = copy.deepcopy(self.data)
        capability = next(
            c for c in data["capabilities"] if len(c["current_claims"]) > 1
        )
        capability["adjudication"] = None
        self.assertIn("no adjudication reference", self._messages(data))

    def test_multiple_claims_pointing_at_a_RESOLVED_decision_are_caught(self) -> None:
        """Permitted only while unresolved. Once adjudicated, one claim survives."""
        data = copy.deepcopy(self.data)
        capability = next(
            c for c in data["capabilities"] if len(c["current_claims"]) > 1
        )
        decision = next(
            d for d in data["decisions"] if d["id"] == capability["adjudication"]
        )
        decision["state"] = "resolved"
        decision["disposition"] = "settled"
        self.assertIn("is resolved", self._messages(data))

    def test_a_dangling_reference_is_caught(self) -> None:
        data = copy.deepcopy(self.data)
        data["modules"][0]["owns_capabilities"].append("cap.does.not-exist")
        self.assertIn("owns unknown capability", self._messages(data))

    def test_a_host_facility_claiming_a_namespace_is_caught(self) -> None:
        """The M51 contradiction: licensing cannot be both."""
        data = copy.deepcopy(self.data)
        facility = next(m for m in data["modules"] if m["kind"] == "host-facility")
        facility["namespace"] = {
            "db_schema": "mod_bogus",
            "migration_prefix": "bg",
            "branch_label": "bogus",
            "allocated": False,
        }
        self.assertIn("cannot be both", self._messages(data))

    def test_a_stateful_module_without_a_namespace_is_caught(self) -> None:
        data = copy.deepcopy(self.data)
        module = next(m for m in data["modules"] if m["kind"] == "module")
        module["namespace"] = None
        self.assertIn("must declare a namespace", self._messages(data))

    def test_a_duplicated_namespace_is_caught(self) -> None:
        data = copy.deepcopy(self.data)
        modules = [m for m in data["modules"] if m.get("namespace")]
        modules[1]["namespace"]["db_schema"] = modules[0]["namespace"]["db_schema"]
        self.assertIn("already used by", self._messages(data))

    def test_a_remote_binding_without_a_remote_authority_is_caught(self) -> None:
        """Remote means another system DECIDES. A provider over the network is
        transport, and transport is never authority."""
        data = copy.deepcopy(self.data)
        binding = next(b for b in data["bindings"] if b["installation"] == "remote")
        binding["remote_authority"] = None
        self.assertIn("must name the remote_authority", self._messages(data))

    def test_a_hand_assigned_cutover_status_is_caught(self) -> None:
        data = copy.deepcopy(self.data)
        data["cutovers"][0]["status"] = "complete"
        self.assertIn("must never", self._messages(data))

    def test_two_open_decisions_sharing_an_order_are_caught(self) -> None:
        data = copy.deepcopy(self.data)
        open_decisions = [d for d in data["decisions"] if d["state"] == "open"]
        open_decisions[1]["order"] = open_decisions[0]["order"]
        self.assertIn("share an order", self._messages(data))

    def test_a_resolved_decision_without_a_disposition_is_caught(self) -> None:
        data = copy.deepcopy(self.data)
        decision = next(d for d in data["decisions"] if d["state"] == "resolved")
        decision["disposition"] = None
        self.assertIn("resolved without a disposition", self._messages(data))

    def test_a_duplicate_id_is_caught(self) -> None:
        data = copy.deepcopy(self.data)
        data["modules"].append(copy.deepcopy(data["modules"][0]))
        self.assertIn("duplicate id", self._messages(data))


class AdjudicationOrderTests(unittest.TestCase):
    """The sequence Michael set on 2026-08-12."""

    def setUp(self) -> None:
        self.data = load()
        self.by_id = {d["id"]: d for d in self.data["decisions"]}

    def test_principal_mapping_is_adjudicated_first(self) -> None:
        """It blocks Sub's atomic revision 0001 lineage adoption and the Party
        principal cutover, so nothing downstream can be sequenced before it."""
        principal = self.by_id["dec.identity.principal-mapping"]
        self.assertEqual("open", principal["state"])
        others = [
            d["order"]
            for d in self.data["decisions"]
            if d["state"] == "open" and d["id"] != principal["id"]
        ]
        self.assertTrue(all(principal["order"] < other for other in others))

    def test_the_finance_boundary_is_second_and_only_its_contract_remains(self) -> None:
        finance = self.by_id["dec.finance.posting-contract"]
        self.assertEqual("open", finance["state"])
        self.assertEqual(2, finance["order"])
        self.assertIn("separate authorities", finance["disposition"])
        self.assertIn("contract", finance["remaining"])

    def test_service_teams_are_blocked_not_open(self) -> None:
        """A blocked decision must not be worked: finish and retire the current
        Sub service-team cutover before selecting another destination."""
        teams = self.by_id["dec.workforce.service-team-destination"]
        self.assertEqual("blocked", teams["state"])

    def test_lead_scope_is_already_adjudicated_into_two_capabilities(self) -> None:
        leads = self.by_id["dec.acquisition.lead-scope"]
        self.assertEqual("resolved", leads["state"])
        capability_ids = {c["id"] for c in self.data["capabilities"]}
        self.assertIn("cap.engagement.lead-pipeline", capability_ids)
        self.assertIn("cap.isp.service-qualification", capability_ids)

    def test_inbound_is_split_into_resolved_and_open_rows(self) -> None:
        """I3, I5 and I8 are resolved dispositions with no open decision; I2 and
        I4 are separate open decisions."""
        capabilities = {c["id"]: c for c in self.data["capabilities"]}

        for resolved, boundary in (
            ("cap.inbound.idempotent-admission", "kernel-primitive"),
            ("cap.isp.inbound-routing", "owning-domain-module"),
            ("cap.inbound.reply-delivery", "kernel-primitive"),
        ):
            self.assertEqual(boundary, capabilities[resolved]["target_boundary"])
            self.assertIsNone(capabilities[resolved]["adjudication"], resolved)

        for still_open, decision_id in (
            ("cap.inbound.connected-account", "dec.inbound.connected-account-boundary"),
            ("cap.inbound.observation", "dec.inbound.shared-ingress"),
        ):
            self.assertEqual("undecided", capabilities[still_open]["target_boundary"])
            self.assertEqual("open", self.by_id[decision_id]["state"])

    def test_the_two_resolved_kernel_rows_own_no_facts_of_their_own(self) -> None:
        """I3 and I8 resolve to EXISTING kernel owners. A capability that
        resolved to "no new owner" must not quietly acquire facts."""
        capabilities = {c["id"]: c for c in self.data["capabilities"]}
        for capability_id in (
            "cap.inbound.idempotent-admission",
            "cap.inbound.reply-delivery",
        ):
            self.assertEqual([], capabilities[capability_id].get("owned_facts", []))


class RenderTests(unittest.TestCase):
    def test_render_is_deterministic_and_marked_generated(self) -> None:
        data = load()
        first = render(data)
        self.assertEqual(first, render(data))
        self.assertIn("GENERATED", first)
        self.assertIn("do not edit by hand", first)

    def test_the_checked_in_rendering_matches_the_data(self) -> None:
        """Drift between the data and its rendering means the readable view is
        lying. Regenerate with `python3 tools/fleet_matrix.py render`."""
        rendered = REPO_ROOT / "docs" / "fleet-decomposition.md"
        self.assertTrue(rendered.is_file(), "rendering has not been generated")
        self.assertEqual(
            render(load()) + "\n",
            rendered.read_text(encoding="utf-8"),
            "docs/fleet-decomposition.md is stale — re-run the renderer",
        )

    def test_the_data_path_is_where_the_schema_says(self) -> None:
        self.assertTrue(DATA_PATH.is_file())
        self.assertTrue(SCHEMA_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
