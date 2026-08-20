from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from programme_control.engine import validate_matrix, verify_repository

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "programmes" / "dotmac-isp-replacement.json"


def valid_matrix() -> dict[str, object]:
    return {
        "schema_version": 1,
        "programme_id": "pgm-dotmac-isp-replacement",
        "title": "Dotmac ISP replacement",
        "status": "proposed",
        "owner": "Michael Ayoade",
        "approver": "Michael Ayoade",
        "authority": {
            "source": {
                "assembly_id": "asm-dotmac-sub-legacy",
                "repository": "https://github.com/michaelayoade/dotmac_sub",
                "authority_state": "source-authoritative",
            },
            "target": {
                "assembly_id": "asm-dotmac-isp",
                "repository_status": "unassigned",
                "repository": "unassigned",
                "database_boundary": "independent",
                "authority_state": "candidate",
            },
        },
        "records": [
            {
                "record_id": "rec-isp-governance-decision",
                "repository": "https://github.com/michaelayoade/dotmac_governance",
                "revision": "SELF",
                "path": "docs/adr/0012-dotmac-isp-replacement-programme.md",
                "role": "governing-decision",
            },
            {
                "record_id": "rec-isp-cutover-standard",
                "repository": "https://github.com/michaelayoade/dotmac_starter_mt",
                "revision": "fcdecad3a06ef0b2567ccb7892364d6f60cd4215",
                "path": (
                    "docs/adr/"
                    "0031-an-authority-cutover-is-sealed-by-its-own-evidence.md"
                ),
                "role": "technical-source",
            },
        ],
        "cutover_control_ids": ["ctl-isp-001", "ctl-isp-002"],
        "controls": [
            {
                "control_id": "ctl-isp-001",
                "name": "Human approval",
                "owner": "Michael Ayoade",
                "state": "pending-approval",
                "depends_on": [],
                "evidence_refs": [],
            },
            {
                "control_id": "ctl-isp-002",
                "name": "Exact target identity",
                "owner": "Michael Ayoade",
                "state": "blocked",
                "depends_on": ["ctl-isp-001"],
                "evidence_refs": [],
            },
        ],
        "cohorts": [
            {
                "cohort_id": "cohort-isp-01",
                "sequence": 1,
                "name": "Foundation and customer",
                "state": "blocked",
                "depends_on": [],
                "current_authority": "asm-dotmac-sub-legacy",
                "target_authority": "asm-dotmac-isp",
                "components": [
                    {
                        "component_id": "dotmac-customers",
                        "owner_id": "dotmac-customers",
                        "disposition": "build",
                    }
                ],
            },
            {
                "cohort_id": "cohort-isp-02",
                "sequence": 2,
                "name": "Network",
                "state": "blocked",
                "depends_on": ["cohort-isp-01"],
                "current_authority": "asm-dotmac-sub-legacy",
                "target_authority": "asm-dotmac-isp",
                "components": [
                    {
                        "component_id": "dotmac-network-access",
                        "owner_id": "dotmac-network-access",
                        "disposition": "adopt",
                    }
                ],
            },
        ],
        "open_decisions": [
            {
                "decision_id": "dec-isp-001",
                "question": "Approve replacement?",
                "owner": "Michael Ayoade",
                "state": "open",
                "blocks": ["ctl-isp-001"],
            }
        ],
    }


class ProgrammeControlTests(unittest.TestCase):
    def validate(self, payload: dict[str, object]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "programme.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return validate_matrix(path)

    def assertFails(self, errors: list[str], fragment: str) -> None:
        self.assertTrue(
            any(fragment in error for error in errors),
            f"expected an error containing {fragment!r}, got {errors!r}",
        )

    def test_minimal_valid_matrix_passes(self) -> None:
        self.assertEqual(self.validate(valid_matrix()), [])

    def test_checked_in_programme_passes(self) -> None:
        self.assertEqual(validate_matrix(MATRIX), [])
        self.assertEqual(verify_repository(ROOT), [])

    def test_unknown_top_level_field_fails(self) -> None:
        payload = valid_matrix()
        payload["escape_hatch"] = True
        self.assertFails(self.validate(payload), "unknown field 'escape_hatch'")

    def test_duplicate_control_id_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        controls = copy.deepcopy(payload["controls"])
        assert isinstance(controls, list)
        controls.append(copy.deepcopy(controls[0]))
        payload["controls"] = controls
        self.assertFails(self.validate(payload), "duplicate control_id 'ctl-isp-001'")

    def test_control_dependency_cycle_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        controls = payload["controls"]
        assert isinstance(controls, list)
        first = controls[0]
        assert isinstance(first, dict)
        first["depends_on"] = ["ctl-isp-002"]
        self.assertFails(self.validate(payload), "control dependency cycle")

    def test_verified_control_without_evidence_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        controls = payload["controls"]
        assert isinstance(controls, list)
        second = controls[1]
        assert isinstance(second, dict)
        second["state"] = "verified"
        self.assertFails(
            self.validate(payload), "verified control has no evidence_refs"
        )

    def test_non_immutable_external_revision_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        records = payload["records"]
        assert isinstance(records, list)
        external = records[1]
        assert isinstance(external, dict)
        external["revision"] = "main"
        self.assertFails(self.validate(payload), "must be SELF or a 40-character")

    def test_duplicate_component_across_cohorts_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        second = cohorts[1]
        assert isinstance(second, dict)
        components = second["components"]
        assert isinstance(components, list)
        component = components[0]
        assert isinstance(component, dict)
        component["component_id"] = "dotmac-customers"
        self.assertFails(self.validate(payload), "component 'dotmac-customers' appears")

    def test_cohort_dependency_must_point_backward_sensitivity(self) -> None:
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        first = cohorts[0]
        assert isinstance(first, dict)
        first["depends_on"] = ["cohort-isp-02"]
        self.assertFails(self.validate(payload), "must point to an earlier cohort")

    def test_open_decision_unknown_block_target_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        decisions = payload["open_decisions"]
        assert isinstance(decisions, list)
        first = decisions[0]
        assert isinstance(first, dict)
        first["blocks"] = ["cohort-isp-99"]
        self.assertFails(self.validate(payload), "unknown block target 'cohort-isp-99'")

    def test_assigned_target_requires_canonical_repository_sensitivity(self) -> None:
        payload = valid_matrix()
        authority = payload["authority"]
        assert isinstance(authority, dict)
        target = authority["target"]
        assert isinstance(target, dict)
        target["repository_status"] = "assigned"
        self.assertFails(
            self.validate(payload),
            "assigned target repository must be a canonical HTTPS URL",
        )


if __name__ == "__main__":
    unittest.main()
