from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.check_processes import validate_processes


VALID_PROCESS = """\
# Example process

- Status: Proposed
- Date: 2026-07-26
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Classification: Internal
- Model version: 0.1.0

## Purpose

Purpose.

## Standards mapping

Unmapped.

## Inputs

Inputs.

## Activities

Activities.

## Outcomes

Outcomes.

## `required_information_items`

Items.

## `work_products`

Products.

## Approval gate

Gate.

## Effectiveness verification

None required.

## Agent participation

Limits.

## Enforcement

A check.

## Declaration

```yaml
process: example-process
model_version: 0.1.0
status: proposed
enforcement:
  ci: [check_adrs]
```
"""


class ProcessValidationTests(unittest.TestCase):
    def validate(self, files: dict[str, str]) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in files.items():
                (root / name).write_text(content, encoding="utf-8")
            return validate_processes(root)

    def assertFails(self, errors: list[str], fragment: str) -> None:
        self.assertTrue(
            any(fragment in error for error in errors),
            f"expected an error containing {fragment!r}, got {errors!r}",
        )

    def test_valid_definition_passes(self):
        self.assertEqual(
            self.validate({"example-process.md": VALID_PROCESS}), []
        )

    def test_empty_directory_is_valid(self):
        """Unlike ADRs, no processes means none adopted yet — not a failure."""
        self.assertEqual(self.validate({}), [])

    def test_missing_model_version_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "- Model version: 0.1.0\n", ""
                )
            }
        )
        self.assertFails(errors, "expected exactly one '- Model version:' line")

    def test_missing_section_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "## Effectiveness verification\n\nNone required.\n", ""
                )
            }
        )
        self.assertFails(
            errors, "missing required section 'Effectiveness verification'"
        )

    def test_work_products_section_is_required(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "## `work_products`\n\nProducts.\n", ""
                )
            }
        )
        self.assertFails(errors, "missing required section '`work_products`'")

    def test_invalid_status_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "- Status: Proposed", "- Status: Draft"
                )
            }
        )
        self.assertFails(errors, "invalid status 'Draft'")

    def test_superseded_by_slug_is_valid(self):
        self.assertEqual(
            self.validate(
                {
                    "example-process.md": VALID_PROCESS.replace(
                        "- Status: Proposed", "- Status: Superseded by other-process"
                    ).replace("status: proposed", "status: superseded")
                }
            ),
            [],
        )

    def test_unknown_metadata_field_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "- Classification: Internal",
                    "- Classification: Internal\n- Modelversion: 0.1.0",
                )
            }
        )
        self.assertFails(errors, "unknown controlled metadata field '- Modelversion:'")

    def test_bad_filename_fails(self):
        errors = self.validate({"Example_Process.md": VALID_PROCESS})
        self.assertFails(errors, "filename must be kebab-case-slug.md")

    # Declaration block

    def test_missing_declaration_block_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace("```yaml", "```text")
            }
        )
        self.assertFails(errors, "missing the fenced ```yaml Declaration block")

    def test_declaration_slug_mismatch_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "process: example-process", "process: other-process"
                )
            }
        )
        self.assertFails(errors, "Declaration says process 'other-process'")

    def test_declaration_status_mismatch_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "status: proposed", "status: accepted"
                )
            }
        )
        self.assertFails(errors, "Declaration status 'accepted' does not match")

    def test_enforcement_none_fails(self):
        """The enforce-or-delete rule, as a control rather than a sentence."""
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "enforcement:\n  ci: [check_adrs]", "enforcement: none"
                )
            }
        )
        self.assertFails(errors, "'enforcement: none' is not a valid declaration")

    def test_enforcement_without_ci_or_manual_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "enforcement:\n  ci: [check_adrs]",
                    "enforcement:\n  aspiration: someday",
                )
            }
        )
        self.assertFails(errors, "must declare 'ci:' or 'manual:'")

    def test_manual_enforcement_is_valid(self):
        self.assertEqual(
            self.validate(
                {
                    "example-process.md": VALID_PROCESS.replace(
                        "enforcement:\n  ci: [check_adrs]",
                        "enforcement:\n  manual:\n    - owner: michael_ayoade",
                    )
                }
            ),
            [],
        )

    def test_missing_declaration_key_fails(self):
        errors = self.validate(
            {
                "example-process.md": VALID_PROCESS.replace(
                    "model_version: 0.1.0\n", "", 1
                )
            }
        )
        self.assertFails(errors, "Declaration is missing 'model_version:'")


if __name__ == "__main__":
    unittest.main()
