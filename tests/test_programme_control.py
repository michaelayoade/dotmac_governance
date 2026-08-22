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

    # ------------------------------------------------------------------
    # superseded: a control whose PREMISE was removed, not one that stalled
    # ------------------------------------------------------------------

    def _superseded_first_control(self, payload: dict[str, object]) -> dict:
        controls = payload["controls"]
        assert isinstance(controls, list)
        first = controls[0]
        assert isinstance(first, dict)
        first["state"] = "superseded"
        first["evidence_refs"] = [
            {
                "producer": "Michael Ayoade",
                "repository": "https://github.com/michaelayoade/dotmac_governance",
                "revision": "b36dbb913a2ff24414f77fd6807183c10593cae0",
                "subject": "amendment removing the premise",
            }
        ]
        return first

    def test_superseded_control_without_evidence_fails_sensitivity(self) -> None:
        """Ending a control's life must cite the revision that ended it."""

        payload = valid_matrix()
        controls = payload["controls"]
        assert isinstance(controls, list)
        first = controls[0]
        assert isinstance(first, dict)
        first["state"] = "superseded"
        self.assertFails(
            self.validate(payload), "superseded control has no evidence_refs"
        )

    def test_live_control_may_not_depend_on_a_superseded_one_sensitivity(self) -> None:
        """Such a control could never open — nothing advances its dependency."""

        payload = valid_matrix()
        self._superseded_first_control(payload)
        # ctl-isp-002 still depends on ctl-isp-001 and is still blocked.
        payload["cutover_control_ids"] = ["ctl-isp-002"]
        self.assertFails(
            self.validate(payload), "depends on superseded control 'ctl-isp-001'"
        )

    def test_a_superseded_control_may_be_depended_on_by_another_superseded_one(
        self,
    ) -> None:
        """The rule targets a dangling gate, not the act of superseding a pair."""

        payload = valid_matrix()
        self._superseded_first_control(payload)
        controls = payload["controls"]
        assert isinstance(controls, list)
        second = controls[1]
        assert isinstance(second, dict)
        second["state"] = "superseded"
        second["evidence_refs"] = [
            {
                "producer": "Michael Ayoade",
                "repository": "https://github.com/michaelayoade/dotmac_governance",
                "revision": "b36dbb913a2ff24414f77fd6807183c10593cae0",
                "subject": "amendment removing the premise",
            }
        ]
        payload["cutover_control_ids"] = ["ctl-isp-001", "ctl-isp-002"]
        errors = self.validate(payload)
        self.assertFalse(
            [e for e in errors if "depends on superseded control" in e],
            f"a superseded dependent must not trip the rule: {errors!r}",
        )

    def test_superseded_control_in_the_cutover_gate_fails_sensitivity(self) -> None:
        """It can never be verified, so it blocks every cohort forever."""

        payload = valid_matrix()
        self._superseded_first_control(payload)
        controls = payload["controls"]
        assert isinstance(controls, list)
        second = controls[1]
        assert isinstance(second, dict)
        second["depends_on"] = []
        second["state"] = "not-started"
        # ctl-isp-001 is superseded and still listed in the gate.
        self.assertFails(
            self.validate(payload),
            "'ctl-isp-001' is superseded and can never be verified",
        )

    def test_shared_in_process_database_boundary_is_accepted(self) -> None:
        """An in-place conversion shares one database; that is not two writers."""

        payload = valid_matrix()
        authority = payload["authority"]
        assert isinstance(authority, dict)
        target = authority["target"]
        assert isinstance(target, dict)
        target["database_boundary"] = "shared-in-process"
        self.assertEqual(self.validate(payload), [])

    def test_an_invented_database_boundary_is_still_rejected(self) -> None:
        """Widening the enum by two must not widen it to anything."""

        payload = valid_matrix()
        authority = payload["authority"]
        assert isinstance(authority, dict)
        target = authority["target"]
        assert isinstance(target, dict)
        target["database_boundary"] = "mostly-independent"
        self.assertFails(self.validate(payload), "database_boundary")

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

        # The eleven capabilities the 2026-08-21 ordering amendment rescued
        # from silence. Five were SCHEDULED on 2026-08-22 and six still hold a
        # roster disposition; both halves are pinned, because the property that
        # matters is that each is disposed of deliberately in exactly one
        # place, not which place it happens to be in today.
        for scheduled in (
            "dotmac-records",
            "dotmac-documents",
            "dotmac-surveys",
            "dotmac-campaigns",
            "dotmac-expenses",
        ):
            assert scheduled in in_cohorts, scheduled
        for still_rostered in (
            "dotmac-content",
            "dotmac-publishing",
            "dotmac-sites",
            "dotmac-media-observations",
            "dotmac-web-analytics",
            "dotmac-procurement",
        ):
            assert still_rostered in rostered, still_rostered

        # The four owners added on 2026-08-22 are scoped and scheduled, never
        # scoped and forgotten — the failure mode that made `capability_scope`
        # necessary in the first place.
        for added in (
            "dotmac-service-orders",
            "dotmac-payments",
            "dotmac-service-changes",
            "dotmac-operational-escalations",
        ):
            assert added in scope, added
            assert added in in_cohorts, added

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

    # -- ADR / matrix agreement ---------------------------------------------
    #
    # A 2026-08-21 amendment declared `ctl-isp-003` verified in prose while the
    # matrix left it blocked. Nothing caught it, and a reader had no way to
    # know which controlled record to believe.

    def _repo_with(self, adr_body: str, control_state: str) -> Path:
        """Build a throwaway Governance checkout with one ADR and one matrix."""
        root = Path(tempfile.mkdtemp())
        (root / "programmes").mkdir()
        (root / "docs" / "adr").mkdir(parents=True)
        (root / "docs" / "adr" / "0001-governing.md").write_text(
            adr_body, encoding="utf-8"
        )
        payload = valid_matrix()
        controls = payload["controls"]
        assert isinstance(controls, list)
        first = controls[0]
        assert isinstance(first, dict)
        first["state"] = control_state
        if control_state == "verified":
            # A verified control needs immutable evidence, and a proposed
            # programme may not claim one at all.
            payload["status"] = "accepted"
            first["depends_on"] = []
            first["evidence_refs"] = [
                {
                    "producer": "Michael Ayoade",
                    "repository": (
                        "https://github.com/michaelayoade/dotmac_governance"
                    ),
                    "revision": "b" * 40,
                    "subject": "Approval",
                }
            ]
        else:
            first["evidence_refs"] = []
            first["depends_on"] = ["ctl-isp-000"]
            controls.insert(
                0,
                {
                    "control_id": "ctl-isp-000",
                    "name": "Prerequisite",
                    "owner": "Michael Ayoade",
                    "state": "not-started",
                    "depends_on": [],
                    "evidence_refs": [],
                },
            )
        payload["records"] = [
            {
                "record_id": "rec-governing",
                "repository": "https://github.com/michaelayoade/dotmac_governance",
                "revision": "SELF",
                "path": "docs/adr/0001-governing.md",
                "role": "governing-decision",
            }
        ]
        (root / "programmes" / "p.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        return root

    def test_adr_may_not_contradict_the_matrix_sensitivity(self) -> None:
        root = self._repo_with("`ctl-isp-001` is verified on that basis.\n", "blocked")
        errors = verify_repository(root)
        self.assertTrue(
            any("may not disagree about a control" in error for error in errors),
            f"expected an ADR/matrix disagreement, got {errors!r}",
        )

    def test_adr_agreeing_with_the_matrix_passes(self) -> None:
        """The acceptance half: the same sentence is fine when it is true."""
        root = self._repo_with("`ctl-isp-001` is verified on that basis.\n", "verified")
        self.assertEqual(verify_repository(root), [])

    def test_adr_discussing_a_control_without_claiming_a_state_passes(self) -> None:
        """The guard reads one sentence shape, not prose generally.

        Without this it would be tempting to widen the pattern until any
        mention of a control near any state word failed, and an ADR that
        cannot discuss its own controls is worse than the drift.
        """
        root = self._repo_with(
            "`ctl-isp-001` stays where it is until cohort scoping exists, and "
            "nothing here is verified yet.\n",
            "blocked",
        )
        self.assertEqual(verify_repository(root), [])

    def test_adr_claiming_a_state_for_an_unknown_control_fails_sensitivity(
        self,
    ) -> None:
        root = self._repo_with("`ctl-isp-404` is verified.\n", "blocked")
        errors = verify_repository(root)
        self.assertTrue(
            any("unknown control" in error for error in errors),
            f"expected an unknown-control error, got {errors!r}",
        )

    def test_missing_governing_decision_document_fails_sensitivity(self) -> None:
        root = self._repo_with("nothing to see\n", "blocked")
        (root / "docs" / "adr" / "0001-governing.md").unlink()
        errors = verify_repository(root)
        self.assertTrue(
            any("is missing" in error for error in errors),
            f"expected a missing-document error, got {errors!r}",
        )

    def test_resolved_decision_rejects_an_unknown_field_sensitivity(self) -> None:
        payload = valid_matrix()
        resolved = self._resolved()
        resolved["state"] = "resolved"
        payload["resolved_decisions"] = [resolved]
        self.assertFails(self.validate(payload), "resolved_decisions[0]")


if __name__ == "__main__":
    unittest.main()
