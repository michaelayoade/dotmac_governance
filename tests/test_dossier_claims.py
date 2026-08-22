"""SENSITIVITY for the cross-repository writer claim.

Every case here is built from the defect that motivated the control: two roster
rationales asserted that Sub had no writer while Sub's own dossiers named Sub
writers requiring retirement and Sub as cutover 1. Neither was caught, because
prose in one repository cannot be compared to prose in another.

The tests that matter most are the ones proving the control FAILS. A checker
that cannot be shown refuting anything is indistinguishable from one that always
passes — and this one has to fail in two different ways, because "the dossier
disagrees" and "nothing could be read" are different problems with the same
remedy only by coincidence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from programme_control.dossier_claims import (
    ClaimVerdict,
    check_claim,
    check_matrix,
    failures,
)

PIN = "c7fd24d63eeaf77c50aeb41e9260bfb872e5cc6a"


def _dossier(directory: Path, name: str, entries: list[dict] | None) -> Path:
    path = directory / f"{name}.toml"
    lines: list[str] = ['package = "x"']
    for entry in entries or []:
        lines.append("\n[[product_writers]]")
        for key, value in entry.items():
            if isinstance(value, bool):
                lines.append(f"{key} = {str(value).lower()}")
            elif isinstance(value, list):
                rendered = ", ".join(f'"{item}"' for item in value)
                lines.append(f"{key} = [{rendered}]")
            else:
                lines.append(f'{key} = "{value}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _entry(**overrides: object) -> dict:
    entry = {
        "product": "dotmac_sub",
        "writer_state": "no_writer",
        "retirement_required": False,
        "revision": PIN,
        "evidence_paths": [],
    }
    entry.update(overrides)
    return entry


class DossierClaimTests(unittest.TestCase):
    def _check(self, entries: list[dict] | None, *, write: bool = True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = (
                _dossier(root, "d", entries) if write else root / "does-not-exist.toml"
            )
            return check_claim(
                component_id="dotmac-x",
                subject_repository="dotmac_sub",
                evidence_record_id="rec-x",
                dossier_path=path,
            )

    # -- the claim holds ---------------------------------------------------

    def test_no_writer_upholds_the_claim(self) -> None:
        self.assertIs(self._check([_entry()]).verdict, ClaimVerdict.UPHELD)

    def test_inventory_only_upholds_the_claim(self) -> None:
        """The case that must PASS.

        A product read while inventorying that writes nothing is the legitimate
        shape of "no writer here". Refusing it would make the control unusable
        for exactly the capabilities it is meant to clear.
        """

        check = self._check([_entry(writer_state="inventory_only")])
        self.assertIs(check.verdict, ClaimVerdict.UPHELD)

    # -- the two original failures -----------------------------------------

    def test_the_expenses_failure_is_refuted(self) -> None:
        """Rostered "no ISP writer in scope" while Sub held writers to retire."""

        check = self._check(
            [
                _entry(
                    writer_state="legacy_writer",
                    retirement_required=True,
                    evidence_paths=["app/services/field/expense_requests.py"],
                )
            ]
        )
        self.assertIs(check.verdict, ClaimVerdict.REFUTED)
        self.assertIn("legacy_writer", check.detail)

    def test_the_surveys_failure_is_refuted(self) -> None:
        """Rostered "nothing scheduled" while its dossier opened "Sub is cutover 1"."""

        check = self._check(
            [
                _entry(
                    writer_state="qualifying_source",
                    retirement_required=True,
                    evidence_paths=["app/services/surveys.py"],
                )
            ]
        )
        self.assertIs(check.verdict, ClaimVerdict.REFUTED)
        self.assertIn("qualifying_source", check.detail)

    def test_retirement_work_refutes_a_clear_state(self) -> None:
        """The subtler half: state looks clear, retirement says otherwise."""

        check = self._check([_entry(retirement_required=True)])
        self.assertIs(check.verdict, ClaimVerdict.REFUTED)
        self.assertIn("retirement", check.detail)

    # -- every way of not knowing fails ------------------------------------

    def test_a_missing_dossier_is_unknown_not_absent(self) -> None:
        check = self._check(None, write=False)
        self.assertIs(check.verdict, ClaimVerdict.UNKNOWN)

    def test_a_dossier_with_no_product_writers_is_unknown(self) -> None:
        """Silence is not a claim that no product writes this."""

        self.assertIs(self._check([]).verdict, ClaimVerdict.UNKNOWN)

    def test_a_dossier_that_omits_the_subject_product_is_unknown(self) -> None:
        check = self._check([_entry(product="dotmac_erp")])
        self.assertIs(check.verdict, ClaimVerdict.UNKNOWN)

    def test_two_entries_for_one_product_is_unknown(self) -> None:
        check = self._check([_entry(), _entry(writer_state="legacy_writer")])
        self.assertIs(check.verdict, ClaimVerdict.UNKNOWN)

    def test_an_untyped_entry_is_unknown(self) -> None:
        check = self._check([_entry(retirement_required="no")])
        self.assertIs(check.verdict, ClaimVerdict.UNKNOWN)

    def test_unknown_is_a_failure(self) -> None:
        """The property the whole design rests on."""

        check = self._check(None, write=False)
        self.assertFalse(check.ok)
        self.assertTrue(failures([check]))

    # -- matrix wiring ------------------------------------------------------

    def test_only_no_product_writer_claims_are_checked(self) -> None:
        """The other codes record scope judgements no dossier can settle."""

        matrix = {
            "records": [],
            "capability_roster": [
                {"component_id": "a", "rationale_code": "external_authority"},
                {"component_id": "b", "rationale_code": "paused_by_decision"},
            ],
        }
        self.assertEqual(check_matrix(matrix, checkout_root=Path("/nonexistent")), [])

    def test_a_claim_citing_no_dossier_record_is_unknown(self) -> None:
        matrix = {
            "records": [],
            "capability_roster": [
                {
                    "component_id": "a",
                    "rationale_code": "no_product_writer",
                    "subject_repository": "dotmac_sub",
                    "evidence_record_id": "rec-missing",
                }
            ],
        }
        checks = check_matrix(matrix, checkout_root=Path("/nonexistent"))
        self.assertIs(checks[0].verdict, ClaimVerdict.UNKNOWN)

    def test_the_checked_in_matrix_claims_are_all_typed(self) -> None:
        """Pinned against the real programme."""

        matrix = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "programmes"
                / "dotmac-isp-replacement.json"
            ).read_text(encoding="utf-8")
        )
        for entry in matrix["capability_roster"]:
            self.assertIn("rationale_code", entry, entry["component_id"])
            if entry["rationale_code"] == "no_product_writer":
                self.assertIn("subject_repository", entry)
                self.assertIn("evidence_record_id", entry)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
