from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from standards_control.contracts import (
    BranchName,
    CanonicalRepository,
    ConformanceReport,
    DiagnosticCode,
)
from standards_control.engine import verify_repository

REPOSITORY = CanonicalRepository("https://github.com/michaelayoade/example")
ROOT = Path(__file__).resolve().parent.parent
GOOD_CONTRACT = """\
from dataclasses import dataclass
@dataclass(frozen=True)
class Envelope:
    payload: str
def serialize(value: Envelope) -> str:
    return value.payload
"""


def profile() -> dict[str, object]:
    return {
        "schema_version": 1,
        "profile_id": "example-standards",
        "repository": {"canonical_url": REPOSITORY, "default_branch": "main"},
        "governance_model": {"source": "docs/adr/0006.md", "status": "proposed"},
        "enforcement_mode": "candidate",
        "authorities": [
            {
                "authority_id": "example-owner",
                "subject": "Example state.",
                "protected_resources": ["example-state"],
                "owner_component": "example-service",
                "owner_implementation": "example/service.py",
                "decision_interface": "example.service.decide",
                "canonical_writer_paths": ["example/service.py"],
                "adapter_paths": ["example/router.py"],
                "drift_test_paths": ["tests/test_example.py"],
            }
        ],
        "typed_contract_surfaces": [
            {
                "surface_id": "wire-contracts",
                "paths": ["example/contracts.py"],
                "require_public_annotations": True,
                "forbid_any": True,
                "require_immutable_records": True,
            }
        ],
    }


class Fixture:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write(
        self,
        value: dict[str, object],
        *,
        contract: str = GOOD_CONTRACT,
        owner: str = "def decide() -> bool:\n    return True\n",
        status: str = "Proposed",
    ) -> Path:
        profile_path = self.root / ".dotmac/standards-profile.json"
        files = {
            profile_path: json.dumps(value),
            self.root / "docs/adr/0006.md": f"- Status: {status}\n",
            self.root / "example/service.py": owner,
            self.root / "example/router.py": "def route() -> None:\n    return None\n",
            self.root / "example/contracts.py": contract,
            self.root
            / "tests/test_example.py": "def test_drift() -> None:\n    assert True\n",
        }
        for path, body in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        return profile_path


class StandardsTests(unittest.TestCase):
    def evaluate(
        self,
        value: dict[str, object] | None = None,
        *,
        contract: str = GOOD_CONTRACT,
        owner: str = "def decide() -> bool:\n    return True\n",
        status: str = "Proposed",
        branch: str = "main",
    ) -> ConformanceReport:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(
                copy.deepcopy(value or profile()),
                contract=contract,
                owner=owner,
                status=status,
            )
            return verify_repository(
                root,
                path,
                observed_repository=REPOSITORY,
                observed_default_branch=BranchName(branch),
            )

    def assert_code(self, report: ConformanceReport, code: DiagnosticCode) -> None:
        self.assertIn(code, {item.code for item in report.diagnostics})

    def authority(self, value: dict[str, object]) -> dict[str, object]:
        authorities = value["authorities"]
        assert isinstance(authorities, list)
        authority = authorities[0]
        assert isinstance(authority, dict)
        return authority

    def test_known_good_profile_passes(self) -> None:
        self.assertTrue(self.evaluate().conforms)

    def test_unknown_profile_field_fails(self) -> None:
        value = profile()
        value["unknown"] = True
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_schema_version_rejects_boolean_and_float_aliases(self) -> None:
        for invalid in (True, 1.0):
            with self.subTest(invalid=invalid):
                value = profile()
                value["schema_version"] = invalid
                self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_proposed_source_cannot_activate_required_mode(self) -> None:
        value = profile()
        value["enforcement_mode"] = "required"
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_repository_default_branch_is_enforced(self) -> None:
        self.assert_code(
            self.evaluate(branch="dev"),
            DiagnosticCode.REPOSITORY_DEFAULT_BRANCH_MISMATCH,
        )

    def test_repository_identity_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(profile())
            report = verify_repository(
                root,
                path,
                observed_repository=CanonicalRepository(
                    "https://github.com/michaelayoade/other"
                ),
                observed_default_branch=BranchName("main"),
            )
        self.assert_code(report, DiagnosticCode.REPOSITORY_IDENTITY_MISMATCH)

    def test_unavailable_default_branch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(profile())
            report = verify_repository(
                root,
                path,
                observed_repository=REPOSITORY,
            )
        self.assert_code(report, DiagnosticCode.REPOSITORY_DEFAULT_BRANCH_UNAVAILABLE)

    def test_governance_status_is_enforced(self) -> None:
        self.assert_code(
            self.evaluate(status="Accepted"),
            DiagnosticCode.GOVERNANCE_SOURCE_STATUS_MISMATCH,
        )

    def test_duplicate_resource_owner_fails(self) -> None:
        value = profile()
        authorities = value["authorities"]
        assert isinstance(authorities, list)
        duplicate = copy.deepcopy(self.authority(value))
        duplicate["authority_id"] = "other-owner"
        authorities.append(duplicate)
        self.assert_code(
            self.evaluate(value), DiagnosticCode.AUTHORITY_RESOURCE_DUPLICATE
        )

    def test_owner_must_be_a_canonical_writer(self) -> None:
        value = profile()
        self.authority(value)["canonical_writer_paths"] = ["example/other.py"]
        self.assert_code(
            self.evaluate(value), DiagnosticCode.AUTHORITY_OWNER_NOT_WRITER
        )

    def test_adapter_cannot_be_a_writer(self) -> None:
        value = profile()
        self.authority(value)["adapter_paths"] = ["example/service.py"]
        self.assert_code(
            self.evaluate(value), DiagnosticCode.AUTHORITY_ADAPTER_WRITER_OVERLAP
        )

    def test_missing_authority_path_fails(self) -> None:
        value = profile()
        self.authority(value)["drift_test_paths"] = ["tests/missing.py"]
        self.assert_code(self.evaluate(value), DiagnosticCode.AUTHORITY_PATH_MISSING)

    def test_missing_decision_interface_fails(self) -> None:
        self.assert_code(
            self.evaluate(owner="def other() -> bool:\n    return True\n"),
            DiagnosticCode.AUTHORITY_INTERFACE_MISSING,
        )

    def test_any_fails(self) -> None:
        source = "from typing import Any\ndef send(value: Any) -> str:\n    return str(value)\n"
        self.assert_code(
            self.evaluate(contract=source), DiagnosticCode.CONTRACT_ANY_FORBIDDEN
        )

    def test_missing_annotation_fails(self) -> None:
        self.assert_code(
            self.evaluate(contract="def send(value: str):\n    return value\n"),
            DiagnosticCode.CONTRACT_ANNOTATION_MISSING,
        )

    def test_bare_container_fails(self) -> None:
        self.assert_code(
            self.evaluate(
                contract="def send(value: dict) -> str:\n    return str(value)\n"
            ),
            DiagnosticCode.CONTRACT_BARE_CONTAINER,
        )

    def test_mutable_dataclass_fails(self) -> None:
        source = (
            "from dataclasses import dataclass\n@dataclass\nclass E:\n    value: str\n"
        )
        self.assert_code(
            self.evaluate(contract=source), DiagnosticCode.CONTRACT_RECORD_MUTABLE
        )

    def test_mutable_pydantic_record_fails_without_importing_pydantic(self) -> None:
        source = "from pydantic import BaseModel\nclass E(BaseModel):\n    value: str\n"
        self.assert_code(
            self.evaluate(contract=source), DiagnosticCode.CONTRACT_RECORD_MUTABLE
        )

    def test_immutable_pydantic_record_passes_without_importing_pydantic(self) -> None:
        source = (
            "from pydantic import BaseModel, ConfigDict\n"
            "class E(BaseModel):\n"
            "    model_config = ConfigDict(frozen=True)\n"
            "    value: str\n"
        )
        self.assertTrue(self.evaluate(contract=source).conforms)

    def test_unannotated_record_field_fails(self) -> None:
        source = (
            "from dataclasses import dataclass\n"
            "@dataclass(frozen=True)\n"
            "class E:\n"
            "    value = 'missing annotation'\n"
        )
        self.assert_code(
            self.evaluate(contract=source),
            DiagnosticCode.CONTRACT_ANNOTATION_MISSING,
        )

    def test_checked_in_profile_passes_production_engine(self) -> None:
        report = verify_repository(
            ROOT,
            ROOT / ".dotmac/standards-profile.json",
            observed_repository=CanonicalRepository(
                "https://github.com/michaelayoade/dotmac_governance"
            ),
            observed_default_branch=BranchName("main"),
        )
        self.assertTrue(report.conforms, report.to_dict())

    def test_schema_enum_matches_runtime_contract(self) -> None:
        schema = json.loads(
            (
                ROOT / "standards_control/schema/standards-profile.schema.json"
            ).read_text()
        )
        self.assertEqual(
            schema["properties"]["enforcement_mode"]["enum"],
            ["candidate", "required"],
        )

    def test_composite_action_uses_the_one_engine_without_secret_inputs(self) -> None:
        action = (ROOT / ".github/actions/standards-check/action.yml").read_text()
        workflow = (ROOT / ".github/workflows/governance-checks.yml").read_text()

        self.assertIn("tools/dotmac-standards", action)
        self.assertIn("uses: ./.github/actions/standards-check", workflow)
        self.assertIn("github.event.repository.default_branch", workflow)
        self.assertNotIn("token:", action.lower())
        self.assertNotIn("secret", action.lower())
