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
    GitRevision,
)
from standards_control.engine import verify_repository

REPOSITORY = CanonicalRepository("https://github.com/michaelayoade/dotmac_governance")
PRODUCT_REPOSITORY = CanonicalRepository("https://github.com/michaelayoade/example")
GOVERNANCE_REPOSITORY = CanonicalRepository(
    "https://github.com/michaelayoade/dotmac_governance"
)
GOVERNANCE_REVISION = GitRevision("a" * 40)
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
        "schema_version": 2,
        "profile_id": "example-standards",
        "repository": {"canonical_url": REPOSITORY, "default_branch": "main"},
        "governance_model": {
            "kind": "local",
            "source": "docs/adr/0006.md",
            "status": "proposed",
        },
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

    def evaluate_pinned(
        self,
        *,
        governance_root: bool = True,
        repository: CanonicalRepository | None = GOVERNANCE_REPOSITORY,
        revision: GitRevision | None = GOVERNANCE_REVISION,
        source_status: str = "Accepted",
        model_repository: str = ("https://github.com/michaelayoade/dotmac_governance"),
    ) -> ConformanceReport:
        value = profile()
        repository_contract = value["repository"]
        assert isinstance(repository_contract, dict)
        repository_contract["canonical_url"] = PRODUCT_REPOSITORY
        value["governance_model"] = {
            "kind": "pinned",
            "canonical_url": model_repository,
            "revision": "a" * 40,
            "source": "docs/adr/0006.md",
            "status": "accepted",
        }
        value["enforcement_mode"] = "required"
        with tempfile.TemporaryDirectory() as product_directory:
            with tempfile.TemporaryDirectory() as governance_directory:
                product = Path(product_directory)
                governance = Path(governance_directory)
                path = Fixture(product).write(value)
                source = governance / "docs/adr/0006.md"
                source.parent.mkdir(parents=True)
                source.write_text(f"- Status: {source_status}\n", encoding="utf-8")
                return verify_repository(
                    product,
                    path,
                    observed_repository=PRODUCT_REPOSITORY,
                    observed_default_branch=BranchName("main"),
                    governance_root=governance if governance_root else None,
                    observed_governance_repository=repository,
                    observed_governance_revision=revision,
                )

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
        for invalid in (True, 1.0, 1):
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

    def test_product_cannot_claim_a_local_governance_source(self) -> None:
        value = profile()
        repository = value["repository"]
        assert isinstance(repository, dict)
        repository["canonical_url"] = PRODUCT_REPOSITORY
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(value)
            report = verify_repository(
                root,
                path,
                observed_repository=PRODUCT_REPOSITORY,
                observed_default_branch=BranchName("main"),
            )
        self.assert_code(report, DiagnosticCode.GOVERNANCE_LOCAL_SOURCE_FORBIDDEN)

    def test_pinned_governance_source_passes_with_exact_identity(self) -> None:
        self.assertTrue(self.evaluate_pinned().conforms)

    def test_pinned_governance_root_is_required(self) -> None:
        self.assert_code(
            self.evaluate_pinned(governance_root=False),
            DiagnosticCode.GOVERNANCE_ROOT_UNAVAILABLE,
        )

    def test_pinned_governance_repository_is_required_and_exact(self) -> None:
        cases = (
            (None, DiagnosticCode.GOVERNANCE_REPOSITORY_UNAVAILABLE),
            (
                CanonicalRepository("https://github.com/michaelayoade/other"),
                DiagnosticCode.GOVERNANCE_REPOSITORY_MISMATCH,
            ),
        )
        for repository, code in cases:
            with self.subTest(code=code):
                self.assert_code(
                    self.evaluate_pinned(repository=repository),
                    code,
                )

    def test_pinned_governance_revision_is_required_and_exact(self) -> None:
        cases = (
            (None, DiagnosticCode.GOVERNANCE_REVISION_UNAVAILABLE),
            (GitRevision("b" * 40), DiagnosticCode.GOVERNANCE_REVISION_MISMATCH),
        )
        for revision, code in cases:
            with self.subTest(code=code):
                self.assert_code(self.evaluate_pinned(revision=revision), code)

    def test_pinned_profile_cannot_select_an_alternate_policy_owner(self) -> None:
        alternate = "https://github.com/michaelayoade/other"
        self.assert_code(
            self.evaluate_pinned(
                repository=CanonicalRepository(alternate),
                model_repository=alternate,
            ),
            DiagnosticCode.GOVERNANCE_REPOSITORY_MISMATCH,
        )

    def test_pinned_governance_status_comes_from_governance_root(self) -> None:
        self.assert_code(
            self.evaluate_pinned(source_status="Proposed"),
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
        self.assertIn("github.action_repository", action)
        self.assertIn("github.action_ref", action)
        self.assertIn("--governance-root", action)
        self.assertIn("uses: ./.github/actions/standards-check", workflow)
        self.assertIn("github.event.repository.default_branch", workflow)
        self.assertNotIn("token:", action.lower())
        self.assertNotIn("secret", action.lower())
