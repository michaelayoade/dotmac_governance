from __future__ import annotations

import copy
import json
import subprocess
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
OPEN_MEMBER_TYPE = """\
class Topic(str):
    __slots__ = ()
"""
CLOSED_MEMBER_TYPE = """\
import enum
class Topic(str, enum.Enum):
    alpha = "alpha"
"""
REGISTRY = """\
class TopicRegistry:
    def require(self, topic: str) -> str:
        return topic
"""
MANIFEST = """\
from dataclasses import dataclass, field
@dataclass(frozen=True)
class Manifest:
    topics: tuple[str, ...] = field(default_factory=tuple)
"""
OPEN_STORAGE = """\
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
class Row:
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
"""
CLOSED_STORAGE_ENUM = """\
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
class Row:
    topic: Mapped[str] = mapped_column(sa.Enum("alpha", name="ck_topic"))
"""
CLOSED_STORAGE_CHECK = """\
from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column
class Row:
    __table_args__ = (CheckConstraint("topic IN ('alpha')", name="ck_topic"),)
    topic: Mapped[str] = mapped_column(String(120), nullable=False)
"""


def vocabulary() -> dict[str, object]:
    return {
        "vocabulary_id": "topic",
        "subject": "Topics a module owns.",
        "member_type": "Topic",
        "member_type_path": "example/member.py",
        "registry_interface": "example.registry.TopicRegistry",
        "registry_implementation": "example/registry.py",
        "declaration_field": "topics",
        "declaration_paths": ["example/manifest.py"],
        "storage_column": "topic",
        "storage_paths": ["example/models.py"],
    }


def profile() -> dict[str, object]:
    return {
        "schema_version": 4,
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
        "module_declared_vocabularies": [vocabulary()],
        "testing_kit_boundary": {
            "test_roots": ["tests"],
            "kit_source_roots": [],
            "conformance_probes": [],
        },
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
        member: str = OPEN_MEMBER_TYPE,
        manifest: str = MANIFEST,
        storage: str = OPEN_STORAGE,
        runtime: str = "def runtime() -> None:\n    return None\n",
        test_source: str = "def test_drift() -> None:\n    assert True\n",
        probe_source: str | None = None,
        kit_source: str | None = None,
    ) -> Path:
        profile_path = self.root / ".dotmac/standards-profile.json"
        files = {
            profile_path: json.dumps(value),
            self.root / "docs/adr/0006.md": f"- Status: {status}\n",
            self.root / "example/service.py": owner,
            self.root / "example/router.py": "def route() -> None:\n    return None\n",
            self.root / "example/contracts.py": contract,
            self.root / "tests/test_example.py": test_source,
            self.root / "example/member.py": member,
            self.root / "example/registry.py": REGISTRY,
            self.root / "example/manifest.py": manifest,
            self.root / "example/models.py": storage,
            self.root / "example/runtime.py": runtime,
        }
        if probe_source is not None:
            files[self.root / "scripts/floor/probe.py"] = probe_source
        if kit_source is not None:
            files[
                self.root
                / "packages/dotmac-kernel/src/dotmac_kernel/testing/__init__.py"
            ] = kit_source
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
        member: str = OPEN_MEMBER_TYPE,
        manifest: str = MANIFEST,
        storage: str = OPEN_STORAGE,
        runtime: str = "def runtime() -> None:\n    return None\n",
        test_source: str = "def test_drift() -> None:\n    assert True\n",
        probe_source: str | None = None,
        kit_source: str | None = None,
    ) -> ConformanceReport:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(
                copy.deepcopy(value or profile()),
                contract=contract,
                owner=owner,
                status=status,
                member=member,
                manifest=manifest,
                storage=storage,
                runtime=runtime,
                test_source=test_source,
                probe_source=probe_source,
                kit_source=kit_source,
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

    def test_src_layout_uses_the_importable_decision_interface(self) -> None:
        value = profile()
        authority = self.authority(value)
        authority["owner_implementation"] = "src/example/service.py"
        authority["decision_interface"] = "example.service.decide"
        authority["canonical_writer_paths"] = ["src/example/service.py"]
        authority["adapter_paths"] = ["src/example/router.py"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(value)
            source = root / "src/example"
            source.mkdir(parents=True)
            (source / "service.py").write_text(
                "def decide() -> bool:\n    return True\n", encoding="utf-8"
            )
            (source / "router.py").write_text(
                "def route() -> None:\n    return None\n", encoding="utf-8"
            )
            report = verify_repository(
                root,
                path,
                observed_repository=REPOSITORY,
                observed_default_branch=BranchName("main"),
            )
        self.assertTrue(report.conforms, report.to_dict())

    def test_src_layout_rejects_the_repository_path_as_an_import_symbol(self) -> None:
        value = profile()
        authority = self.authority(value)
        authority["owner_implementation"] = "src/example/service.py"
        authority["decision_interface"] = "src.example.service.decide"
        authority["canonical_writer_paths"] = ["src/example/service.py"]
        authority["adapter_paths"] = ["src/example/router.py"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(value)
            source = root / "src/example"
            source.mkdir(parents=True)
            (source / "service.py").write_text(
                "def decide() -> bool:\n    return True\n", encoding="utf-8"
            )
            (source / "router.py").write_text(
                "def route() -> None:\n    return None\n", encoding="utf-8"
            )
            report = verify_repository(
                root,
                path,
                observed_repository=REPOSITORY,
                observed_default_branch=BranchName("main"),
            )
        self.assert_code(report, DiagnosticCode.AUTHORITY_INTERFACE_MISSING)

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
        self.assertEqual(schema["properties"]["schema_version"]["const"], 4)
        self.assertIn("testing_kit_boundary", schema["required"])

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

    # ── Module-declared vocabularies (ADR 0007) ─────────────────────────────
    #
    # One sabotage proof per diagnostic code. Each plants exactly one violation
    # against an otherwise-conformant fixture, so a check that stops firing is a
    # failing test rather than a silently vacuous one.

    def test_open_vocabulary_passes(self) -> None:
        """Positive control: the fixture is conformant, so every negative case
        below is attributable to the one thing it changes."""
        report = self.evaluate()
        self.assertTrue(report.conforms, report.to_dict())

    def test_enumerated_member_type_fails(self) -> None:
        report = self.evaluate(member=CLOSED_MEMBER_TYPE)
        self.assert_code(report, DiagnosticCode.VOCABULARY_MEMBER_TYPE_CLOSED)

    def test_absent_member_type_fails(self) -> None:
        report = self.evaluate(member="class Other(str):\n    __slots__ = ()\n")
        self.assert_code(report, DiagnosticCode.VOCABULARY_MEMBER_TYPE_MISSING)

    def test_absent_registry_interface_fails(self) -> None:
        value = profile()
        vocabularies = value["module_declared_vocabularies"]
        assert isinstance(vocabularies, list)
        entry = vocabularies[0]
        assert isinstance(entry, dict)
        entry["registry_interface"] = "example.registry.AbsentRegistry"
        self.assert_code(
            self.evaluate(value), DiagnosticCode.VOCABULARY_REGISTRY_MISSING
        )

    def test_missing_declaration_field_fails(self) -> None:
        """A vocabulary nothing can be declared on is not a vocabulary."""
        report = self.evaluate(
            manifest=(
                "from dataclasses import dataclass\n"
                "@dataclass(frozen=True)\n"
                "class Manifest:\n"
                "    name: str\n"
            )
        )
        self.assert_code(report, DiagnosticCode.VOCABULARY_DECLARATION_MISSING)

    def test_database_enum_storage_fails(self) -> None:
        report = self.evaluate(storage=CLOSED_STORAGE_ENUM)
        self.assert_code(report, DiagnosticCode.VOCABULARY_STORAGE_CLOSED)

    def test_check_constraint_storage_fails(self) -> None:
        """A CHECK naming the column with a literal IN list re-closes exactly
        what the open member type opened."""
        report = self.evaluate(storage=CLOSED_STORAGE_CHECK)
        self.assert_code(report, DiagnosticCode.VOCABULARY_STORAGE_CLOSED)

    def test_missing_vocabulary_path_fails(self) -> None:
        value = profile()
        vocabularies = value["module_declared_vocabularies"]
        assert isinstance(vocabularies, list)
        entry = vocabularies[0]
        assert isinstance(entry, dict)
        entry["member_type_path"] = "example/absent.py"
        self.assert_code(self.evaluate(value), DiagnosticCode.VOCABULARY_PATH_MISSING)

    def test_unparseable_vocabulary_path_fails(self) -> None:
        report = self.evaluate(member="class Topic(str)\n")
        self.assert_code(report, DiagnosticCode.VOCABULARY_SYNTAX_INVALID)

    def test_no_declared_vocabulary_is_legal_and_checks_nothing(self) -> None:
        """An empty list is a claim, not an error — see ADR 0007's drift note on
        what the engine does and does not detect."""
        value = profile()
        value["module_declared_vocabularies"] = []
        report = self.evaluate(value, member=CLOSED_MEMBER_TYPE)
        self.assertTrue(report.conforms, report.to_dict())

    def test_duplicate_vocabulary_id_is_rejected(self) -> None:
        value = profile()
        value["module_declared_vocabularies"] = [vocabulary(), vocabulary()]
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_schema_version_three_profiles_are_rejected(self) -> None:
        """Version 4 is a closed contract, not an additive one: a profile that
        predates the testing-kit boundary must be migrated, not silently
        accepted with the new rule family switched off."""
        value = profile()
        value["schema_version"] = 3
        del value["testing_kit_boundary"]
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    # -- Kernel testing-kit import locality (ADR 0008) -----------------------

    def test_runtime_imports_of_the_testing_kit_fail_in_every_spelling(self) -> None:
        imports = (
            "import dotmac_kernel.testing\n",
            "import dotmac_kernel.testing.harness\n",
            "from dotmac_kernel.testing import FakeClock\n",
            "from dotmac_kernel.testing.fakes import FakeClock\n",
            "from dotmac_kernel import testing\n",
        )
        for source in imports:
            with self.subTest(source=source.strip()):
                report = self.evaluate(runtime=source)
                self.assert_code(report, DiagnosticCode.TESTING_KIT_IMPORT_FORBIDDEN)
                finding = next(
                    item
                    for item in report.diagnostics
                    if item.code is DiagnosticCode.TESTING_KIT_IMPORT_FORBIDDEN
                )
                self.assertEqual(finding.path, Path("example/runtime.py"))
                self.assertEqual(finding.line, 1)

    def test_git_inventory_scans_a_real_untracked_runtime_file(self) -> None:
        """Production uses Git inventory; the fallback canary is not enough."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = Fixture(root).write(
                profile(), runtime="import dotmac_kernel.testing\n"
            )
            subprocess.run(
                ["git", "init", "--quiet"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            report = verify_repository(
                root,
                path,
                observed_repository=REPOSITORY,
                observed_default_branch=BranchName("main"),
            )
        self.assert_code(report, DiagnosticCode.TESTING_KIT_IMPORT_FORBIDDEN)

    def test_testing_kit_detector_ignores_near_misses(self) -> None:
        source = (
            "from dotmac_kernel import db\n"
            "import dotmac_kernel\n"
            "# from dotmac_kernel.testing import FakeClock\n"
            'NAME = "dotmac_kernel.testing"\n'
        )
        self.assertTrue(self.evaluate(runtime=source).conforms)

    def test_structural_test_root_may_import_the_testing_kit(self) -> None:
        report = self.evaluate(
            test_source="from dotmac_kernel.testing import FakeClock\n"
        )
        self.assertTrue(report.conforms, report.to_dict())

    def test_kit_source_root_may_assemble_itself(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["kit_source_roots"] = [
            "packages/dotmac-kernel/src/dotmac_kernel/testing"
        ]
        report = self.evaluate(
            value,
            kit_source="from dotmac_kernel.testing.fakes import FakeClock\n",
        )
        self.assertTrue(report.conforms, report.to_dict())

    def test_exact_conformance_probe_may_import_the_testing_kit(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["conformance_probes"] = [
            {"path": "scripts/floor/probe.py", "expected_import_count": 1}
        ]
        report = self.evaluate(
            value,
            probe_source="from dotmac_kernel.testing import FakeClock\n",
        )
        self.assertTrue(report.conforms, report.to_dict())

    def test_missing_declared_testing_kit_path_fails(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["conformance_probes"] = [
            {"path": "scripts/floor/probe.py", "expected_import_count": 1}
        ]
        self.assert_code(self.evaluate(value), DiagnosticCode.TESTING_KIT_PATH_MISSING)

    def test_testing_kit_probe_import_count_is_a_two_way_ratchet(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["conformance_probes"] = [
            {"path": "scripts/floor/probe.py", "expected_import_count": 1}
        ]
        for source in (
            "def probe() -> None:\n    return None\n",
            (
                "import dotmac_kernel.testing\n"
                "from dotmac_kernel.testing import FakeClock\n"
            ),
        ):
            with self.subTest(source=source):
                self.assert_code(
                    self.evaluate(value, probe_source=source),
                    DiagnosticCode.TESTING_KIT_PROBE_COUNT_MISMATCH,
                )

    def test_missing_declared_testing_kit_root_fails(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["test_roots"] = ["quality/tests"]
        self.assert_code(self.evaluate(value), DiagnosticCode.TESTING_KIT_PATH_MISSING)

    def test_missing_declared_kit_source_root_fails(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["kit_source_roots"] = [
            "packages/dotmac-kernel/src/dotmac_kernel/testing"
        ]
        self.assert_code(self.evaluate(value), DiagnosticCode.TESTING_KIT_PATH_MISSING)

    def test_non_test_directory_cannot_be_declared_as_a_test_root(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["test_roots"] = ["example"]
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_unrelated_source_cannot_be_declared_as_the_kit_root(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["kit_source_roots"] = ["example"]
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_probe_cannot_hide_inside_an_already_allowed_root(self) -> None:
        value = profile()
        boundary = value["testing_kit_boundary"]
        assert isinstance(boundary, dict)
        boundary["conformance_probes"] = [
            {"path": "tests/test_example.py", "expected_import_count": 1}
        ]
        self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_probe_import_count_must_be_positive(self) -> None:
        for count in (True, 0, -1):
            with self.subTest(count=count):
                value = profile()
                boundary = value["testing_kit_boundary"]
                assert isinstance(boundary, dict)
                boundary["conformance_probes"] = [
                    {
                        "path": "scripts/floor/probe.py",
                        "expected_import_count": count,
                    }
                ]
                self.assert_code(self.evaluate(value), DiagnosticCode.PROFILE_INVALID)

    def test_unparseable_runtime_source_fails_closed(self) -> None:
        self.assert_code(
            self.evaluate(runtime="if True print('broken')\n"),
            DiagnosticCode.TESTING_KIT_SYNTAX_INVALID,
        )
