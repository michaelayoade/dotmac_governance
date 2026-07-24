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


class AdrValidationTests(unittest.TestCase):
    def validate(self, files: dict[str, str]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")
            return validate_adrs(root)

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
        self.assertTrue(any("ADR number 0001 used by" in error for error in errors))

    def test_missing_owner_fails(self):
        errors = self.validate(
            {
                "0001-example-decision.md": VALID_ADR.replace(
                    "- Owner: Michael Ayoade\n",
                    "",
                )
            }
        )
        self.assertTrue(any("expected exactly one '- Owner:' line" in error for error in errors))

    def test_invalid_status_fails(self):
        errors = self.validate(
            {
                "0001-example-decision.md": VALID_ADR.replace(
                    "- Status: Proposed",
                    "- Status: Effective",
                )
            }
        )
        self.assertTrue(any("invalid status 'Effective'" in error for error in errors))

    def test_missing_drift_prevention_fails(self):
        errors = self.validate(
            {
                "0001-example-decision.md": VALID_ADR.replace(
                    "## Drift prevention\n\nDrift prevention.\n",
                    "",
                )
            }
        )
        self.assertTrue(any("missing required section 'Drift prevention'" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
