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
        "tracks": [
            {
                "track_id": "track-isp-sub-cutover",
                "role": "source-cutover",
                "assembly_id": "asm-dotmac-sub-legacy",
                "responsibility": "Prepare source evidence and retire displaced writers",
            },
            {
                "track_id": "track-isp-target-build",
                "role": "target-construction",
                "assembly_id": "asm-dotmac-isp",
                "responsibility": "Build and verify the independent target assembly",
            },
        ],
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
        "capability_scope": [
            "dotmac-customers",
            "dotmac-network-access",
            "dotmac-campaigns",
        ],
        "capability_roster": [
            {
                "component_id": "dotmac-campaigns",
                "disposition": "replace",
                "rationale": "Sub owns campaign execution; not yet scheduled.",
            }
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
        "resolved_decisions": [],
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

    def test_both_programme_track_roles_are_required_sensitivity(self) -> None:
        payload = valid_matrix()
        tracks = payload["tracks"]
        assert isinstance(tracks, list)
        tracks.pop()
        self.assertFails(
            self.validate(payload),
            "tracks: missing required roles: target-construction",
        )

    def test_track_role_must_use_its_authority_assembly_sensitivity(self) -> None:
        payload = valid_matrix()
        tracks = payload["tracks"]
        assert isinstance(tracks, list)
        source_track = tracks[0]
        assert isinstance(source_track, dict)
        source_track["assembly_id"] = "asm-dotmac-isp"
        self.assertFails(
            self.validate(payload),
            "track role 'source-cutover' must use 'asm-dotmac-sub-legacy'",
        )

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

    def test_component_requires_a_later_cohort_fails_sensitivity(self) -> None:
        """The defect this check exists for.

        Cohort `depends_on` orders the SWITCHES and was the only ordering ever
        validated. It cannot see a component scheduled ahead of a capability it
        declares it needs, which is exactly how `dotmac-fulfillment` sat in
        cohort 4 while the `dotmac-durable-timers` its manifest names in
        `dependencies=("durable_timers",)` sat in cohort 5 — with every cohort
        edge intact and the matrix green.
        """
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        first, second = cohorts[0], cohorts[1]
        assert isinstance(first, dict) and isinstance(second, dict)
        components = first["components"]
        assert isinstance(components, list)
        component = components[0]
        assert isinstance(component, dict)
        component["requires"] = ["dotmac-network-access"]  # lives in cohort 2

        self.assertFails(self.validate(payload), "is scheduled in a later cohort")

    def test_component_may_require_a_sibling_in_the_same_cohort(self) -> None:
        """A cohort is one sealed switch, so its members cut over together.

        The negative half of the check above: without this, the fix for the
        ordering defect would be to forbid a dependency the programme model
        actually permits, and cohort 3's twelve-module sealed switch could not
        express any internal ordering at all.
        """
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        first = cohorts[0]
        assert isinstance(first, dict)
        components = first["components"]
        assert isinstance(components, list)
        components.append(
            {
                "component_id": "dotmac-work-orders",
                "owner_id": "dotmac-work-orders",
                "disposition": "release",
                "requires": ["dotmac-customers"],
            }
        )
        # A cohort component must also be in scope — the roster check enforces
        # that, and leaving it out here would fail for the unrelated reason
        # rather than proving same-cohort `requires` is accepted.
        scope = payload["capability_scope"]
        assert isinstance(scope, list)
        scope.append("dotmac-work-orders")

        self.assertEqual(self.validate(payload), [])

    def test_component_requiring_an_unknown_component_fails_sensitivity(self) -> None:
        """A requirement naming nothing is how a capability disappears.

        `dotmac-work-orders` was a built, ledger-allocated module that no
        cohort claimed at all; omission is silent in a way a dangling
        reference is not.
        """
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        first = cohorts[0]
        assert isinstance(first, dict)
        components = first["components"]
        assert isinstance(components, list)
        component = components[0]
        assert isinstance(component, dict)
        component["requires"] = ["dotmac-not-a-component"]

        self.assertFails(self.validate(payload), "requires unknown component")

    def test_component_requiring_itself_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        first = cohorts[0]
        assert isinstance(first, dict)
        components = first["components"]
        assert isinstance(components, list)
        component = components[0]
        assert isinstance(component, dict)
        component["requires"] = ["dotmac-customers"]

        self.assertFails(self.validate(payload), "requires itself")

    def test_an_unknown_component_field_is_still_rejected(self) -> None:
        """`requires` became optional; that must not have opened the record.

        `_strict_fields` gained an `optional` set for it, and an optional set
        is exactly the kind of change that silently turns a closed record into
        an open one.
        """
        payload = valid_matrix()
        cohorts = payload["cohorts"]
        assert isinstance(cohorts, list)
        first = cohorts[0]
        assert isinstance(first, dict)
        components = first["components"]
        assert isinstance(components, list)
        component = components[0]
        assert isinstance(component, dict)
        component["cohort_note"] = "not a declared field"

        self.assertFails(self.validate(payload), "unknown field 'cohort_note'")

    def test_fulfillment_is_ordered_with_its_declared_prerequisites(self) -> None:
        """Pinned against the checked-in matrix, not a synthetic one.

        The generic ordering check above proves the RULE bites; this proves the
        real programme now satisfies it, so a later slice cannot move Durable
        Timers back out of cohort 4 and stay green.
        """
        payload = json.loads(MATRIX.read_text())
        cohorts = payload["cohorts"]
        by_component = {
            component["component_id"]: cohort["sequence"]
            for cohort in cohorts
            for component in cohort["components"]
        }

        assert (
            by_component["dotmac-durable-timers"] <= by_component["dotmac-fulfillment"]
        )
        assert by_component["dotmac-work-orders"] == by_component["dotmac-fulfillment"]

    def test_a_scoped_capability_with_no_cohort_and_no_disposition_fails(self) -> None:
        """The `dotmac-work-orders` failure mode, generalised.

        Ordering checks read the matrix's own contents, so they cannot see a
        capability that was never mentioned. Work Orders was a built,
        ledger-allocated module with a package on Starter main that appeared in
        no cohort at all, and everything passed. Only a separately declared
        scope can turn silence into an error.
        """
        payload = valid_matrix()
        scope = payload["capability_scope"]
        assert isinstance(scope, list)
        scope.append("dotmac-work-orders")

        self.assertFails(
            self.validate(payload),
            "has no cohort and no retain/replace/retire disposition",
        )

    def test_a_capability_may_not_be_both_rostered_and_in_a_cohort(self) -> None:
        payload = valid_matrix()
        roster = payload["capability_roster"]
        assert isinstance(roster, list)
        roster.append(
            {
                "component_id": "dotmac-customers",
                "disposition": "retain",
                "rationale": "Also carried by cohort 1.",
            }
        )

        self.assertFails(self.validate(payload), "already carried by a cohort")

    def test_a_cohort_component_outside_capability_scope_fails(self) -> None:
        """The ratchet runs both ways: scope may not silently shrink either."""
        payload = valid_matrix()
        scope = payload["capability_scope"]
        assert isinstance(scope, list)
        scope.remove("dotmac-network-access")

        self.assertFails(self.validate(payload), "is not in capability_scope")

    def test_a_roster_disposition_must_be_retain_replace_or_retire(self) -> None:
        payload = valid_matrix()
        roster = payload["capability_roster"]
        assert isinstance(roster, list)
        entry = roster[0]
        assert isinstance(entry, dict)
        entry["disposition"] = "defer"

        self.assertFails(self.validate(payload), "expected one of")

    def test_a_roster_entry_requires_a_rationale(self) -> None:
        """A disposition with no reason is how "retain" becomes a shrug."""
        payload = valid_matrix()
        roster = payload["capability_roster"]
        assert isinstance(roster, list)
        entry = roster[0]
        assert isinstance(entry, dict)
        del entry["rationale"]

        self.assertFails(self.validate(payload), "missing field 'rationale'")

    def test_the_checked_in_matrix_disposes_of_every_scoped_capability(self) -> None:
        """Pinned against the real programme, not a synthetic fixture.

        The checks above prove the RULE bites. This proves the actual matrix
        satisfies it, including the eleven packages that previously had no
        programme disposition at all.
        """
        payload = json.loads(MATRIX.read_text())
        scope = set(payload["capability_scope"])
        in_cohorts = {
            component["component_id"]
            for cohort in payload["cohorts"]
            for component in cohort["components"]
        }
        rostered = {entry["component_id"] for entry in payload["capability_roster"]}

        assert scope == in_cohorts | rostered
        assert not in_cohorts & rostered
        assert "dotmac-work-orders" in in_cohorts
        for previously_unclaimed in (
            "dotmac-campaigns",
            "dotmac-documents",
            "dotmac-records",
            "dotmac-content",
            "dotmac-publishing",
            "dotmac-sites",
            "dotmac-surveys",
            "dotmac-media-observations",
            "dotmac-web-analytics",
            "dotmac-procurement",
            "dotmac-expenses",
        ):
            assert previously_unclaimed in rostered

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

    # -- resolved decisions -------------------------------------------------
    #
    # `open_decisions` accepts only `state: "open"`, so before this field a
    # decision was resolved by DELETING it — which discarded the answer, the
    # person who gave it and the revision proving when. Each rule below is
    # paired with the acceptance case for the same code path.

    def _resolved(self) -> dict[str, object]:
        return {
            "decision_id": "dec-isp-002",
            "question": "Assign the production deployment owner?",
            "owner": "Michael Ayoade",
            "resolution": "Named owner and host recorded in the governing ADR.",
            "evidence_refs": [
                {
                    "producer": "Michael Ayoade",
                    "repository": "https://github.com/michaelayoade/dotmac_governance",
                    "revision": "a" * 40,
                    "subject": "Resolution of dec-isp-002",
                }
            ],
        }

    def test_resolved_decision_with_immutable_evidence_passes(self) -> None:
        payload = valid_matrix()
        payload["resolved_decisions"] = [self._resolved()]
        self.assertEqual(self.validate(payload), [])

    def test_resolved_decision_without_evidence_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        resolved = self._resolved()
        resolved["evidence_refs"] = []
        payload["resolved_decisions"] = [resolved]
        self.assertFails(
            self.validate(payload),
            "an agent-authored assertion is not a decision record",
        )

    def test_resolved_decision_with_mutable_revision_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        resolved = self._resolved()
        evidence = resolved["evidence_refs"]
        assert isinstance(evidence, list)
        first = evidence[0]
        assert isinstance(first, dict)
        first["revision"] = "main"
        payload["resolved_decisions"] = [resolved]
        self.assertFails(
            self.validate(payload),
            "expected an immutable 40-character lower-case Git revision",
        )

    def test_a_decision_cannot_be_open_and_resolved_sensitivity(self) -> None:
        payload = valid_matrix()
        resolved = self._resolved()
        resolved["decision_id"] = "dec-isp-001"
        payload["resolved_decisions"] = [resolved]
        self.assertFails(
            self.validate(payload),
            "is also listed as open; a decision is open or answered, never both",
        )

    def test_duplicate_resolved_decision_id_fails_sensitivity(self) -> None:
        payload = valid_matrix()
        payload["resolved_decisions"] = [self._resolved(), self._resolved()]
        self.assertFails(self.validate(payload), "duplicate decision_id")

    def test_resolved_decision_keeps_its_question_sensitivity(self) -> None:
        """A resolution without its question is unreadable a month later."""

        payload = valid_matrix()
        resolved = self._resolved()
        del resolved["question"]
        payload["resolved_decisions"] = [resolved]
        self.assertFails(self.validate(payload), "question")

    def test_resolved_decision_rejects_an_unknown_field_sensitivity(self) -> None:
        payload = valid_matrix()
        resolved = self._resolved()
        resolved["state"] = "resolved"
        payload["resolved_decisions"] = [resolved]
        self.assertFails(self.validate(payload), "resolved_decisions[0]")


if __name__ == "__main__":
    unittest.main()
