from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_adrs import validate_adrs


VALID_ADR = """\
# 0001. Example decision

- Status: Proposed
- Date: 2026-07-24
- Owner: Michael Ayoade
- Approver: Michael Ayoade (interim)
- Scope: Dotmac engineering
- Classification: Internal

## Context

Context.

## Decision

Decision.

## Consequences

Consequences.

## Drift prevention

Drift prevention.
"""


def record(number: str, title: str, **fields: str) -> str:
    """Build a valid record, overriding or adding controlled metadata."""
    body = VALID_ADR.replace("# 0001. Example decision", f"# {number}. {title}")
    for field, value in fields.items():
        name = field.replace("_", " ").capitalize()
        existing = f"- {name}: "
        if existing in body:
            start = body.index(existing)
            end = body.index("\n", start)
            body = body[:start] + f"{existing}{value}" + body[end:]
        else:
            body = body.replace(
                "- Classification: Internal",
                f"- Classification: Internal\n- {name}: {value}",
            )
    return body


class AdrValidationTests(unittest.TestCase):
    def validate(self, files: dict[str, str]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")
            return validate_adrs(root)

    def assertFails(self, errors: list[str], fragment: str) -> None:
        self.assertTrue(
            any(fragment in error for error in errors),
            f"expected an error containing {fragment!r}, got {errors!r}",
        )

    def test_valid_record_passes(self):
        self.assertEqual(
            self.validate({"0001-example-decision.md": VALID_ADR}),
            [],
        )

    def test_empty_record_set_fails(self):
        self.assertIn(
            "no ADRs found; refusing to report success",
            self.validate({}),
        )

    def test_duplicate_number_fails(self):
        errors = self.validate(
            {
                "0001-first.md": VALID_ADR,
                "0001-second.md": VALID_ADR.replace(
                    "# 0001. Example decision",
                    "# 0001. Second decision",
                ),
            }
        )
        self.assertFails(errors, "ADR number 0001 used by")

    def test_missing_owner_fails(self):
        errors = self.validate(
            {
                "0001-example-decision.md": VALID_ADR.replace(
                    "- Owner: Michael Ayoade\n",
                    "",
                )
            }
        )
        self.assertFails(errors, "expected exactly one '- Owner:' line")

    def test_invalid_status_fails(self):
        errors = self.validate(
            {
                "0001-example-decision.md": VALID_ADR.replace(
                    "- Status: Proposed",
                    "- Status: Effective",
                )
            }
        )
        self.assertFails(errors, "invalid status 'Effective'")

    def test_missing_drift_prevention_fails(self):
        errors = self.validate(
            {
                "0001-example-decision.md": VALID_ADR.replace(
                    "## Drift prevention\n\nDrift prevention.\n",
                    "",
                )
            }
        )
        self.assertFails(errors, "missing required section 'Drift prevention'")

    # Controlled metadata boundary

    def test_optional_effective_field_passes(self):
        self.assertEqual(
            self.validate(
                {"0001-example.md": record("0001", "Example", effective="2026-07-25")}
            ),
            [],
        )

    def test_unknown_metadata_field_fails(self):
        """A typo must fail loudly rather than silently disabling a control."""
        errors = self.validate(
            {
                "0001-example.md": VALID_ADR.replace(
                    "- Classification: Internal",
                    "- Classification: Internal\n- Ammends: 0002 — typo",
                )
            }
        )
        self.assertFails(errors, "unknown controlled metadata field '- Ammends:'")

    def test_unknown_metadata_field_with_a_hyphen_fails(self):
        """The regression this test exists for.

        The key class used to be `[A-Za-z][A-Za-z ]*?`, which admitted no
        hyphen, so this line never matched `METADATA_LINE`, never entered
        `_fields()`, and was silently accepted with exit 0 — while the
        alphabetic `Ammends` above was correctly rejected. The control was not
        narrow, it was blind, and the only known-bad case guarding it happened
        to use a spelling the regex could see.
        """
        errors = self.validate(
            {
                "0001-example.md": VALID_ADR.replace(
                    "- Classification: Internal",
                    "- Classification: Internal"
                    "\n- Supersedes-Knowledge: some-memory-slug",
                )
            }
        )
        self.assertFails(
            errors,
            "unknown controlled metadata field '- Supersedes-Knowledge:'",
        )

    def test_unknown_metadata_field_with_a_digit_fails(self):
        """A near-miss on a REQUIRED field is the dangerous shape.

        `Status2` reads like `Status` to a human skimming the block. Under the
        old key class it was invisible, so a record could carry a second
        status-shaped line that no control ever looked at.
        """
        errors = self.validate(
            {
                "0001-example.md": VALID_ADR.replace(
                    "- Classification: Internal",
                    "- Classification: Internal\n- Status2: Accepted",
                )
            }
        )
        self.assertFails(
            errors, "unknown controlled metadata field '- Status2:'"
        )

    def test_unknown_metadata_field_with_an_underscore_fails(self):
        errors = self.validate(
            {
                "0001-example.md": VALID_ADR.replace(
                    "- Classification: Internal",
                    "- Classification: Internal\n- Amends_note: 0002",
                )
            }
        )
        self.assertFails(
            errors, "unknown controlled metadata field '- Amends_note:'"
        )

    def test_the_widened_key_class_still_accepts_every_legal_field(self):
        """The other half: widening what the scanner SEES must not change what
        it ALLOWS. A fix that made the detector fire on a legal record would be
        a worse defect than the one it repaired."""
        self.assertEqual(
            self.validate(
                {
                    "0001-example.md": record(
                        "0001",
                        "Example",
                        effective="2026-07-25",
                        amends="0002 — the part it narrows",
                    ),
                    "0002-other.md": record("0002", "Other"),
                }
            ),
            [],
        )

    def test_duplicate_optional_field_fails(self):
        errors = self.validate(
            {
                "0001-example.md": VALID_ADR.replace(
                    "- Classification: Internal",
                    "- Classification: Internal\n- Effective: 2026-07-25"
                    "\n- Effective: 2026-07-26",
                )
            }
        )
        self.assertFails(errors, "expected at most one '- Effective:' line")

    def test_bulleted_prose_is_not_read_as_metadata(self):
        """Field scanning stops at the first section; prose is not metadata."""
        self.assertEqual(
            self.validate(
                {
                    "0001-example.md": VALID_ADR.replace(
                        "## Context\n\nContext.",
                        "## Context\n\n- Owner: a prose bullet, not a field.",
                    )
                }
            ),
            [],
        )

    # Amendment

    def test_valid_amendment_passes(self):
        self.assertEqual(
            self.validate(
                {
                    "0001-first.md": record("0001", "First"),
                    "0002-second.md": record(
                        "0002", "Second", amends="0001 — the standards baseline"
                    ),
                }
            ),
            [],
        )

    def test_amending_a_missing_record_fails(self):
        errors = self.validate(
            {
                "0002-second.md": record(
                    "0002", "Second", amends="0001 — the standards baseline"
                )
            }
        )
        self.assertFails(errors, "amends ADR 0001, which does not exist")

    def test_amendment_without_a_named_part_fails(self):
        errors = self.validate(
            {
                "0001-first.md": record("0001", "First"),
                "0002-second.md": record("0002", "Second", amends="0001"),
            }
        )
        self.assertFails(errors, "'- Amends:' must be 'NNNN — what it changes'")

    def test_self_amendment_fails(self):
        errors = self.validate(
            {"0001-first.md": record("0001", "First", amends="0001 — itself")}
        )
        self.assertFails(errors, "amends itself")

    def test_amending_and_superseding_the_same_record_fails(self):
        errors = self.validate(
            {
                "0001-first.md": record("0001", "First", status="Superseded by 0002"),
                "0002-second.md": record(
                    "0002",
                    "Second",
                    amends="0001 — the standards baseline",
                    supersedes="0001",
                ),
            }
        )
        self.assertFails(errors, "both amends and supersedes ADR 0001")

    # Supersession

    def test_valid_supersession_passes(self):
        self.assertEqual(
            self.validate(
                {
                    "0001-first.md": record(
                        "0001", "First", status="Superseded by 0002"
                    ),
                    "0002-second.md": record("0002", "Second", supersedes="0001"),
                }
            ),
            [],
        )

    def test_superseding_a_missing_record_fails(self):
        errors = self.validate(
            {"0002-second.md": record("0002", "Second", supersedes="0001")}
        )
        self.assertFails(errors, "supersedes ADR 0001, which does not exist")

    def test_supersession_without_back_reference_fails(self):
        """The superseded record must record that it was replaced."""
        errors = self.validate(
            {
                "0001-first.md": record("0001", "First"),
                "0002-second.md": record("0002", "Second", supersedes="0001"),
            }
        )
        self.assertFails(errors, "expected 'Superseded by 0002'")

    def test_superseded_status_without_declared_supersession_fails(self):
        """A record cannot be retired by a successor that never claims it."""
        errors = self.validate(
            {
                "0001-first.md": record("0001", "First", status="Superseded by 0002"),
                "0002-second.md": record("0002", "Second"),
            }
        )
        self.assertFails(errors, "must declare '- Supersedes: 0001'")

    def test_superseded_by_a_missing_record_fails(self):
        errors = self.validate(
            {"0001-first.md": record("0001", "First", status="Superseded by 0009")}
        )
        self.assertFails(errors, "superseded by ADR 0009, which does not exist")

    def test_mismatched_supersession_pair_fails(self):
        errors = self.validate(
            {
                "0001-first.md": record("0001", "First", status="Superseded by 0003"),
                "0002-second.md": record("0002", "Second", supersedes="0001"),
                "0003-third.md": record("0003", "Third"),
            }
        )
        self.assertFails(errors, "status claims supersession by ADR 0003")

    def test_self_supersession_fails(self):
        errors = self.validate(
            {
                "0001-first.md": record(
                    "0001",
                    "First",
                    status="Superseded by 0001",
                    supersedes="0001",
                )
            }
        )
        self.assertFails(errors, "supersedes itself")

    def test_malformed_supersedes_value_fails(self):
        errors = self.validate(
            {
                "0001-first.md": record("0001", "First"),
                "0002-second.md": record("0002", "Second", supersedes="ADR 0001"),
            }
        )
        self.assertFails(errors, "'- Supersedes:' must be a four-digit ADR number")


if __name__ == "__main__":
    unittest.main()
