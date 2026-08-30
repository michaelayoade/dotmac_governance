"""Known-good and known-bad controls for the validation-contract guard.

The guard exists because `AGENTS.md` and `.github/workflows/` drifted apart in
BOTH directions at once: the instructions listed an acceptance suite CI owns,
and they omitted lint paths CI had gained. A guard that checked only one
direction would have caught one of those and blessed the other, so every
divergence below is exercised in both directions with its own case.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.check_validation_contract import (
    REPO_ROOT,
    ContractError,
    _invocation_key,
    validate_validation_contract,
)

LOCAL_COMMANDS = (
    "python3 -m ruff check --select E4 pkg",
    "python3 tools/check_adrs.py",
    "python3 -m standards_control verify --root .",
)

CONTRACT: dict[str, Any] = {
    "schema_version": 1,
    "commands": [
        {"key": "ruff check", "aliases": [], "class": "local", "reason": "static"},
        {"key": "check_adrs.py", "aliases": [], "class": "local", "reason": "records"},
        {
            "key": "standards_control verify",
            "aliases": ["dotmac-standards verify"],
            "class": "local",
            "reason": "conformance",
        },
        {
            "key": "unittest discover",
            "aliases": [],
            "class": "ci-owned",
            "reason": "acceptance suite; CI is the acceptance owner",
        },
    ],
    "setup_commands": [
        {"key": "pip install", "reason": "provisioning, not validation"},
    ],
}

WORKFLOW = """\
name: checks
jobs:
  records:
    steps:
      - name: Install
        run: python3 -m pip install -r requirements-dev.txt
      - name: Lint
        run: python3 -m ruff check --select E4 pkg
      - name: Records
        run: python3 tools/check_adrs.py
      - name: Standards
        run: python3 -m standards_control verify --root .
      - name: Acceptance
        run: python3 -m unittest discover --start-directory tests --verbose
"""


def instructions(commands: tuple[str, ...]) -> str:
    """Build an AGENTS.md whose required-workflow block runs `commands`."""
    block = "\n".join(f"   {command}" for command in commands)
    return (
        "# Agent constraints\n\n"
        "## Required workflow\n\n"
        "1. Do the work.\n"
        "2. Run:\n\n"
        "   ```bash\n"
        f"{block}\n"
        "   ```\n\n"
        "## Reporting\n\n"
        "Say what you did. Do not run `python3 -m unittest discover` locally.\n"
    )


def build(
    root: Path,
    *,
    contract: dict[str, Any] | None = None,
    commands: tuple[str, ...] = LOCAL_COMMANDS,
    workflow: str = WORKFLOW,
) -> Path:
    """Write a complete, by-default-consistent repository into `root`."""
    (root / ".dotmac").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (root / ".dotmac" / "validation-contract.json").write_text(
        json.dumps(CONTRACT if contract is None else contract, indent=2),
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(instructions(commands), encoding="utf-8")
    (root / ".github" / "workflows" / "checks.yml").write_text(
        workflow, encoding="utf-8"
    )
    return root


class InvocationKeyTests(unittest.TestCase):
    """The key is the validator's identity, not its argv."""

    def test_module_and_subcommand(self) -> None:
        self.assertEqual(
            _invocation_key("python3 -m agent_control verify --root ."),
            "agent_control verify",
        )

    def test_an_option_is_not_a_subcommand(self) -> None:
        """`ruff format --check` must key as `ruff format`, not `ruff format --check`."""
        self.assertEqual(
            _invocation_key("python3 -m ruff format --check pkg"), "ruff format"
        )

    def test_a_module_with_no_subcommand(self) -> None:
        self.assertEqual(
            _invocation_key("python3 -m programme_control --root ."),
            "programme_control",
        )

    def test_a_script_keys_by_basename(self) -> None:
        self.assertEqual(
            _invocation_key("python3 tools/check_adrs.py"), "check_adrs.py"
        )

    def test_a_launcher_reached_through_a_variable_path(self) -> None:
        """The composite action spells the standards check this way."""
        self.assertEqual(
            _invocation_key(
                'python3 "${GITHUB_ACTION_PATH}/../../../tools/dotmac-standards" verify --root .'
            ),
            "dotmac-standards verify",
        )

    def test_a_stdin_script_keys_as_the_bare_interpreter(self) -> None:
        """Redirection after `-` is not a subcommand."""
        self.assertEqual(_invocation_key("PIN=\"$(python3 - <<'PY'"), "-")

    def test_a_line_that_runs_no_python3_has_no_key(self) -> None:
        self.assertIsNone(_invocation_key("git fetch --depth 1 origin main"))

    def test_python3_with_no_arguments_is_refused(self) -> None:
        """An unparseable invocation is unmonitored, not benign."""
        with self.assertRaises(ContractError):
            _invocation_key("python3")


class AgreementTests(unittest.TestCase):
    """The known-good case, and one known-bad case per direction."""

    def check(self, **kwargs: Any) -> list[str]:
        with tempfile.TemporaryDirectory() as name:
            return validate_validation_contract(build(Path(name), **kwargs))

    def test_a_consistent_repository_passes(self) -> None:
        self.assertEqual(self.check(), [])

    def test_the_production_tree_agrees_with_itself(self) -> None:
        self.assertEqual(validate_validation_contract(REPO_ROOT), [])

    # --- direction 1: instructions -> contract ---

    def test_an_undeclared_command_in_the_instructions_fails(self) -> None:
        errors = self.check(commands=(*LOCAL_COMMANDS, "python3 -m mypy --strict pkg"))
        self.assertTrue(any("does not declare" in error for error in errors), errors)

    def test_documenting_a_ci_owned_command_locally_fails(self) -> None:
        """The exact regression: `unittest` back in the local instructions."""
        errors = self.check(
            commands=(
                *LOCAL_COMMANDS,
                "python3 -m unittest discover --start-directory tests",
            )
        )
        self.assertTrue(any("owned by CI" in error for error in errors), errors)

    # --- direction 2: contract -> instructions ---

    def test_dropping_a_local_command_from_the_instructions_fails(self) -> None:
        errors = self.check(commands=LOCAL_COMMANDS[:-1])
        self.assertTrue(any("does not document" in error for error in errors), errors)

    # --- direction 3: CI -> contract ---

    def test_an_undeclared_command_in_ci_fails(self) -> None:
        errors = self.check(
            workflow=WORKFLOW
            + "      - name: Extra\n        run: python3 -m mypy --strict pkg\n"
        )
        self.assertTrue(
            any("neither as a validator nor as setup" in error for error in errors),
            errors,
        )

    # --- direction 4: contract -> CI ---

    def test_a_declared_command_ci_never_runs_fails(self) -> None:
        trimmed = WORKFLOW.replace(
            "      - name: Acceptance\n"
            "        run: python3 -m unittest discover --start-directory tests --verbose\n",
            "",
        )
        errors = self.check(workflow=trimmed)
        self.assertTrue(any("CI does not run" in error for error in errors), errors)

    def test_dropping_a_local_command_from_ci_also_fails(self) -> None:
        """The same direction, for a `local` command rather than a CI-owned one."""
        trimmed = WORKFLOW.replace(
            "      - name: Records\n        run: python3 tools/check_adrs.py\n", ""
        )
        errors = self.check(workflow=trimmed)
        self.assertTrue(any("CI does not run" in error for error in errors), errors)

    # --- the alias arm must not be vacuous ---

    def test_ci_may_spell_a_command_through_a_declared_alias(self) -> None:
        aliased = WORKFLOW.replace(
            "python3 -m standards_control verify --root .",
            'python3 "${GITHUB_ACTION_PATH}/../tools/dotmac-standards" verify --root .',
        )
        self.assertEqual(self.check(workflow=aliased), [])

    def test_an_alias_ci_uses_but_the_contract_lacks_still_fails(self) -> None:
        """Sensitivity for the case above: the alias is what makes it pass."""
        contract = json.loads(json.dumps(CONTRACT))
        contract["commands"][2]["aliases"] = []
        aliased = WORKFLOW.replace(
            "python3 -m standards_control verify --root .",
            'python3 "${GITHUB_ACTION_PATH}/../tools/dotmac-standards" verify --root .',
        )
        errors = self.check(contract=contract, workflow=aliased)
        self.assertTrue(any("CI does not run" in error for error in errors), errors)


class StrayCopyTests(unittest.TestCase):
    """Reconciling one document is not enough: there were five copies."""

    def sweep(self, name: str, body: str) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = build(Path(directory))
            (root / name).write_text(body, encoding="utf-8")
            return validate_validation_contract(root)

    def test_another_document_offering_a_ci_owned_command_fails(self) -> None:
        errors = self.sweep(
            "README.md",
            "# Repo\n\n```bash\npython3 -m unittest discover --start-directory tests\n```\n",
        )
        self.assertTrue(any("runnable step" in error for error in errors), errors)

    def test_naming_the_command_in_prose_is_allowed(self) -> None:
        """Sensitivity for the case above: the fence is what makes it fail.

        A scanner that flagged prose could not tell an instruction from a
        description of one, including this repository's own account of the
        drift it fixed.
        """
        errors = self.sweep(
            "README.md",
            "# Repo\n\nCI runs `python3 -m unittest discover`; do not run it here.\n",
        )
        self.assertEqual(errors, [])

    def test_another_document_may_still_offer_a_local_command(self) -> None:
        errors = self.sweep(
            "README.md", "# Repo\n\n```bash\npython3 tools/check_adrs.py\n```\n"
        )
        self.assertEqual(errors, [])


class ContractShapeTests(unittest.TestCase):
    """A malformed contract must refuse, never pass over an empty comparison."""

    def check(self, contract: dict[str, Any]) -> list[str]:
        with tempfile.TemporaryDirectory() as name:
            return validate_validation_contract(build(Path(name), contract=contract))

    def mutate(self, **changes: Any) -> dict[str, Any]:
        contract: dict[str, Any] = json.loads(json.dumps(CONTRACT))
        contract.update(changes)
        return contract

    def test_a_contract_with_no_ci_owned_command_is_refused(self) -> None:
        """Non-vacuity: the rule would have nothing to bite on."""
        contract = self.mutate()
        contract["commands"] = [
            c for c in contract["commands"] if c["class"] != "ci-owned"
        ]
        errors = self.check(contract)
        self.assertTrue(any("ci-owned" in error for error in errors), errors)

    def test_a_contract_with_no_local_command_is_refused(self) -> None:
        contract = self.mutate()
        contract["commands"] = [
            c for c in contract["commands"] if c["class"] != "local"
        ]
        errors = self.check(contract)
        self.assertTrue(any("empty set" in error for error in errors), errors)

    def test_a_command_without_a_reason_is_refused(self) -> None:
        contract = self.mutate()
        contract["commands"][0]["reason"] = ""
        errors = self.check(contract)
        self.assertTrue(any("no reason" in error for error in errors), errors)

    def test_a_setup_exclusion_without_a_reason_is_refused(self) -> None:
        contract = self.mutate()
        contract["setup_commands"][0]["reason"] = "  "
        errors = self.check(contract)
        self.assertTrue(any("unmonitored region" in error for error in errors), errors)

    def test_an_ambiguous_alias_is_refused(self) -> None:
        contract = self.mutate()
        contract["commands"][0]["aliases"] = ["check_adrs.py"]
        errors = self.check(contract)
        self.assertTrue(any("resolves to both" in error for error in errors), errors)

    def test_a_duplicate_key_is_refused(self) -> None:
        contract = self.mutate()
        contract["commands"].append(dict(contract["commands"][0]))
        errors = self.check(contract)
        self.assertTrue(
            any("duplicate command key" in error for error in errors), errors
        )

    def test_a_setup_key_that_shadows_a_validator_is_refused(self) -> None:
        """Otherwise an exclusion could quietly switch a real check off."""
        contract = self.mutate()
        contract["setup_commands"].append(
            {"key": "unittest discover", "reason": "not really setup"}
        )
        errors = self.check(contract)
        self.assertTrue(
            any("both as a validator and as setup" in error for error in errors), errors
        )

    def test_an_unknown_class_is_refused(self) -> None:
        contract = self.mutate()
        contract["commands"][0]["class"] = "optional"
        errors = self.check(contract)
        self.assertTrue(any("expected one of" in error for error in errors), errors)

    def test_a_wrong_schema_version_is_refused(self) -> None:
        errors = self.check(self.mutate(schema_version=2))
        self.assertTrue(any("schema_version" in error for error in errors), errors)


class MissingInputTests(unittest.TestCase):
    """Absent inputs refuse rather than reporting agreement over nothing."""

    def test_a_missing_contract_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = build(Path(name))
            (root / ".dotmac" / "validation-contract.json").unlink()
            errors = validate_validation_contract(root)
        self.assertTrue(any("does not exist" in error for error in errors), errors)

    def test_a_missing_instructions_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = build(Path(name))
            (root / "AGENTS.md").unlink()
            errors = validate_validation_contract(root)
        self.assertTrue(
            any("AGENTS.md does not exist" in error for error in errors), errors
        )

    def test_instructions_without_the_required_workflow_section_are_refused(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = build(Path(name))
            (root / "AGENTS.md").write_text("# Agent constraints\n", encoding="utf-8")
            errors = validate_validation_contract(root)
        self.assertTrue(any("Required workflow" in error for error in errors), errors)

    def test_an_unclosed_command_block_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = build(Path(name))
            (root / "AGENTS.md").write_text(
                "## Required workflow\n\n   ```bash\n   python3 -m ruff check pkg\n",
                encoding="utf-8",
            )
            errors = validate_validation_contract(root)
        self.assertTrue(
            any("no closed command block" in error for error in errors), errors
        )

    def test_a_repository_with_no_workflow_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = build(Path(name))
            (root / ".github" / "workflows" / "checks.yml").unlink()
            errors = validate_validation_contract(root)
        self.assertTrue(
            any("refusing to report success" in error for error in errors), errors
        )


if __name__ == "__main__":
    unittest.main()
