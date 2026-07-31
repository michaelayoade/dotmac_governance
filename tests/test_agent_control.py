from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tomllib

from agent_control import activation as activation_module
from agent_control.activation import (
    activate_local,
    load_activation_manifest,
    rollback_local,
)
from agent_control.contracts import (
    ActivationAction,
    ActivationManifestStatus,
    AgentSurface,
    ArtifactKind,
    ArtifactState,
    DependencyState,
    DeploymentMode,
    DiagnosticCode,
    EndpointClass,
    EndpointPlatform,
    PermissionProfile,
    RepositoryIdentity,
    Severity,
)
from agent_control.engine import (
    GENERATED_MARKER,
    bootstrap_repository,
    render_instructions,
    verify_repository,
)
from agent_control.managed import (
    deploy_endpoint,
    load_endpoint_enrollment,
    load_managed_policy,
    reconcile_endpoint,
)
from agent_control.profile import ProfileError, load_profile

CANONICAL_REPOSITORY = "https://github.com/michaelayoade/example"
IDENTITY = RepositoryIdentity(
    canonical_repository=CANONICAL_REPOSITORY,
    revision="a" * 40,
)
VALID_AGENTS = """\
# Agent constraints

## Authority and status

- Checked-in sources are authoritative for their scope.

## Required workflow

- Run the prescribed validation before publication.

## Reporting

- Report failures and unresolved decisions.
"""
VALID_CLAUDE = """\
@AGENTS.md

# Claude-specific additions

- Keep shared instructions in AGENTS.md.
"""
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def valid_profile() -> dict[str, object]:
    """Return fresh JSON-compatible input for the production profile adapter."""

    return {
        "schema_version": 1,
        "profile_id": "example",
        "repository_name": "example",
        "summary": "Example repository.",
        "canonical_repository": CANONICAL_REPOSITORY,
        "default_branch": "main",
        "governance_model": {
            "version": "0.1.0-draft",
            "source": "docs/adr/0005-agent-control.md",
            "status": "proposed",
        },
        "instructions": {
            "agents_path": "AGENTS.md",
            "claude_path": "CLAUDE.md",
            "claude_import": "@AGENTS.md",
            "render_mode": "validate",
            "max_combined_bytes": 32768,
            "warn_combined_bytes": 24576,
            "required_agents_markers": [
                "# Agent constraints",
                "## Authority and status",
                "## Required workflow",
                "## Reporting",
            ],
            "required_claude_markers": [
                "# Claude-specific additions",
            ],
            "authoritative_sources": [
                "README.md",
            ],
            "claude_additions": [
                "Keep shared instructions in AGENTS.md.",
            ],
        },
        "validation_commands": [
            "python3 tools/check.py",
        ],
        "allowed_surfaces": [
            "codex",
            "claude-code",
        ],
        "rollout": {
            "mode": "pilot",
            "managed_configuration": False,
            "authorized_endpoint_classes": [
                "developer-workstation",
            ],
            "blocked_by": [
                "identity separation",
            ],
        },
    }


def configure_managed(profile: dict[str, object]) -> None:
    """Move a profile through the same explicit gates required by the engine."""

    governance = profile["governance_model"]
    instructions = profile["instructions"]
    rollout = profile["rollout"]
    assert isinstance(governance, dict)
    assert isinstance(instructions, dict)
    assert isinstance(rollout, dict)
    governance["status"] = "accepted"
    instructions["render_mode"] = "managed"
    instructions["required_agents_markers"] = [
        "# example repository guidance",
        "## Authority and routing",
        "## Working agreement",
        "## Validation",
        "## Reporting",
    ]
    rollout["mode"] = "managed"
    rollout["managed_configuration"] = True
    rollout["blocked_by"] = []


def valid_endpoint() -> dict[str, object]:
    """Return a non-production endpoint enrollment without credential values."""

    return {
        "schema_version": 1,
        "endpoint_id": "michael-workstation",
        "endpoint_class": "developer-workstation",
        "platform": "macos",
        "principal": "agent:michael-workstation",
        "local_user": "developer",
        "credential_pointer": (
            "openbao:secret/claude-knowledge#client_michael_workstation_token"
        ),
        "credential_environment_variable": "DOTMAC_KNOWLEDGE_MCP_TOKEN",
        "user_home": "/Users/developer",
        "allowed_surfaces": [
            "codex",
            "claude-code",
        ],
        "policy_id": "dotmac-agent-baseline",
    }


def write_json(path: Path, value: object) -> None:
    """Write JSON fixture data through the same file boundary as production."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


class RepositoryFixture:
    """Create profiles and work products through the same JSON/file adapters."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.profile_path = root / ".dotmac" / "agent-profile.json"

    def write(
        self,
        profile: dict[str, object] | None = None,
        *,
        agents: str | None = VALID_AGENTS,
        claude: str | None = VALID_CLAUDE,
        source_status: str = "Proposed",
    ) -> Path:
        payload = copy.deepcopy(profile if profile is not None else valid_profile())
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        self.profile_path.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        (self.root / "docs" / "adr").mkdir(parents=True, exist_ok=True)
        (self.root / "docs" / "adr" / "0005-agent-control.md").write_text(
            f"- Status: {source_status}\n",
            encoding="utf-8",
        )
        (self.root / "README.md").write_text("# Example\n", encoding="utf-8")
        (self.root / "tools").mkdir(parents=True, exist_ok=True)
        (self.root / "tools" / "check.py").write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        if agents is not None:
            (self.root / "AGENTS.md").write_text(agents, encoding="utf-8")
        if claude is not None:
            (self.root / "CLAUDE.md").write_text(claude, encoding="utf-8")
        return self.profile_path


class AgentControlTests(unittest.TestCase):
    def evaluate(
        self,
        profile: dict[str, object] | None = None,
        *,
        agents: str | None = VALID_AGENTS,
        claude: str | None = VALID_CLAUDE,
        source_status: str = "Proposed",
        identity: RepositoryIdentity = IDENTITY,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = RepositoryFixture(root)
            profile_path = fixture.write(
                profile,
                agents=agents,
                claude=claude,
                source_status=source_status,
            )
            return verify_repository(profile_path, root, identity=identity)

    def assertFails(self, report, code: str) -> None:
        self.assertTrue(
            any(
                item.code == code and item.severity is Severity.ERROR
                for item in report.diagnostics
            ),
            f"expected error {code!r}, got {report.diagnostics!r}",
        )

    def test_valid_profile_and_repository_pass(self):
        report = self.evaluate()
        self.assertTrue(report.conforms, report.diagnostics)
        self.assertEqual(report.source_revision, IDENTITY.revision)

    def test_unknown_profile_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = RepositoryFixture(Path(directory))
            profile = valid_profile()
            profile["unexpected"] = True
            profile_path = fixture.write(profile)
            with self.assertRaisesRegex(ProfileError, "unknown keys: unexpected"):
                load_profile(profile_path)

    def test_empty_required_markers_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = RepositoryFixture(Path(directory))
            profile = valid_profile()
            instructions = profile["instructions"]
            assert isinstance(instructions, dict)
            instructions["required_agents_markers"] = []
            profile_path = fixture.write(profile)
            with self.assertRaisesRegex(
                ProfileError,
                "required_agents_markers must not be empty",
            ):
                load_profile(profile_path)

    def test_empty_endpoint_classes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = RepositoryFixture(Path(directory))
            profile = valid_profile()
            rollout = profile["rollout"]
            assert isinstance(rollout, dict)
            rollout["authorized_endpoint_classes"] = []
            profile_path = fixture.write(profile)
            with self.assertRaisesRegex(
                ProfileError,
                "authorized_endpoint_classes must not be empty",
            ):
                load_profile(profile_path)

    def test_missing_instruction_file_fails(self):
        report = self.evaluate(agents=None)
        self.assertFails(report, "instruction.agents.missing")

    def test_missing_required_marker_fails(self):
        report = self.evaluate(
            agents=VALID_AGENTS.replace("## Required workflow\n", "")
        )
        self.assertFails(report, "instruction.agents.marker-missing")

    def test_claude_import_must_be_first_effective_instruction(self):
        report = self.evaluate(claude="# Before import\n\n" + VALID_CLAUDE)
        self.assertFails(report, "instruction.claude.import-order")

    def test_shared_rule_duplication_in_claude_fails(self):
        shared = (
            "- This deliberately long shared rule belongs only in the "
            "vendor-neutral instruction file."
        )
        report = self.evaluate(
            agents=VALID_AGENTS + shared + "\n",
            claude=VALID_CLAUDE + shared + "\n",
        )
        self.assertFails(report, "instruction.claude.duplicates-shared-rule")

    def test_instruction_budget_overflow_fails(self):
        profile = valid_profile()
        instructions = profile["instructions"]
        assert isinstance(instructions, dict)
        instructions["max_combined_bytes"] = 200
        instructions["warn_combined_bytes"] = 100
        report = self.evaluate(profile)
        self.assertFails(report, "instruction.context-budget.exceeded")

    def test_missing_authority_source_fails(self):
        profile = valid_profile()
        instructions = profile["instructions"]
        assert isinstance(instructions, dict)
        instructions["authoritative_sources"] = ["docs/missing.md"]
        report = self.evaluate(profile)
        self.assertFails(report, "instruction.authority-source.missing")

    def test_missing_validation_path_fails(self):
        profile = valid_profile()
        profile["validation_commands"] = ["python3 tools/missing.py"]
        report = self.evaluate(profile)
        self.assertFails(report, "validation.command.path-missing")

    def test_governance_source_status_mismatch_fails(self):
        report = self.evaluate(source_status="Accepted")
        self.assertFails(report, "governance.source.status-mismatch")

    def test_repository_identity_mismatch_fails(self):
        report = self.evaluate(
            identity=RepositoryIdentity(
                canonical_repository="https://github.com/michaelayoade/other",
                revision="b" * 40,
            )
        )
        self.assertFails(report, "repository.identity.mismatch")

    def test_dirty_working_tree_is_attributable_warning(self):
        report = self.evaluate(
            identity=RepositoryIdentity(
                canonical_repository=CANONICAL_REPOSITORY,
                revision="c" * 40,
                dirty=True,
            )
        )
        self.assertTrue(report.conforms)
        self.assertTrue(report.source_dirty)
        self.assertTrue(
            any(
                item.code == "repository.working-tree.dirty"
                and item.severity is Severity.WARNING
                for item in report.diagnostics
            )
        )

    def test_managed_rollout_requires_accepted_unblocked_governance(self):
        profile = valid_profile()
        rollout = profile["rollout"]
        assert isinstance(rollout, dict)
        rollout["mode"] = "managed"
        rollout["managed_configuration"] = False
        report = self.evaluate(profile)
        self.assertFails(report, "rollout.accepted-governance-required")
        self.assertFails(report, "rollout.blockers-open")
        self.assertFails(report, "rollout.managed-configuration-disabled")

    def test_pilot_cannot_enable_managed_configuration(self):
        profile = valid_profile()
        rollout = profile["rollout"]
        assert isinstance(rollout, dict)
        rollout["managed_configuration"] = True
        report = self.evaluate(profile)
        self.assertFails(report, "rollout.pilot-cannot-manage")

    def test_production_endpoint_class_fails_closed(self):
        profile = valid_profile()
        rollout = profile["rollout"]
        assert isinstance(rollout, dict)
        rollout["authorized_endpoint_classes"] = ["production-application-host"]
        report = self.evaluate(profile)
        self.assertFails(report, "profile.invalid")

    def test_literal_secret_pattern_fails(self):
        report = self.evaluate(agents=VALID_AGENTS + "\n- key: sk-" + ("X" * 24) + "\n")
        self.assertFails(report, "secret.openai")

    def test_managed_projection_drift_fails(self):
        profile = valid_profile()
        configure_managed(profile)
        report = self.evaluate(profile, source_status="Accepted")
        self.assertFails(report, "instruction.agents.managed-drift")
        self.assertFails(report, "instruction.claude.managed-drift")

    def test_managed_bootstrap_creates_then_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = RepositoryFixture(root)
            profile = valid_profile()
            configure_managed(profile)
            profile_path = fixture.write(
                profile,
                agents=None,
                claude=None,
                source_status="Accepted",
            )

            first = bootstrap_repository(
                profile_path,
                root,
                apply=True,
                identity=IDENTITY,
            )
            self.assertTrue(first.succeeded, first.report.diagnostics)
            self.assertEqual(
                first.created,
                (Path("AGENTS.md"), Path("CLAUDE.md")),
            )
            self.assertTrue(
                (root / "AGENTS.md")
                .read_text(encoding="utf-8")
                .startswith(GENERATED_MARKER)
            )

            second = bootstrap_repository(
                profile_path,
                root,
                apply=True,
                identity=IDENTITY,
            )
            self.assertTrue(second.succeeded, second.report.diagnostics)
            self.assertEqual(
                second.unchanged,
                (Path("AGENTS.md"), Path("CLAUDE.md")),
            )

    def test_managed_bootstrap_refuses_unmarked_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = RepositoryFixture(root)
            profile = valid_profile()
            configure_managed(profile)
            profile_path = fixture.write(
                profile,
                agents=VALID_AGENTS,
                claude=None,
                source_status="Accepted",
            )

            result = bootstrap_repository(
                profile_path,
                root,
                apply=True,
                identity=IDENTITY,
            )
            self.assertIn(Path("AGENTS.md"), result.refused)
            self.assertFalse(result.succeeded)
            self.assertEqual(
                (root / "AGENTS.md").read_text(encoding="utf-8"),
                VALID_AGENTS,
            )

    def test_renderer_uses_generated_marker_and_profile_values(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = RepositoryFixture(Path(directory))
            profile_path = fixture.write()
            rendered = render_instructions(load_profile(profile_path))
            self.assertTrue(rendered.agents.startswith(GENERATED_MARKER))
            self.assertIn("# example repository guidance", rendered.agents)
            self.assertTrue(rendered.claude.startswith(GENERATED_MARKER))
            self.assertIn("@AGENTS.md", rendered.claude)

    def test_checked_in_schema_is_valid_json(self):
        schema_path = (
            Path(__file__).resolve().parent.parent
            / "agent_control"
            / "schema"
            / "agent-profile.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
        )


class ManagedDeploymentTests(unittest.TestCase):
    """Exercise typed policy/enrollment boundaries and fail-closed activation."""

    policy_path = REPOSITORY_ROOT / ".dotmac" / "managed-agent-policy.json"
    pilot_endpoint_path = (
        REPOSITORY_ROOT / ".dotmac" / "endpoints" / "michael-workstation.json"
    )

    def test_checked_in_policy_parses_to_closed_types(self):
        policy = load_managed_policy(self.policy_path)
        self.assertEqual(policy.policy_id, "dotmac-agent-baseline")
        self.assertEqual(
            policy.allowed_endpoint_classes,
            (EndpointClass.DEVELOPER_WORKSTATION,),
        )
        self.assertEqual(policy.allowed_endpoint_ids, ("michael-workstation",))
        self.assertEqual(
            policy.codex.allowed_permission_profiles,
            (PermissionProfile.READ_ONLY, PermissionProfile.WORKSPACE),
        )
        self.assertTrue(policy.managed_configuration)

    def test_endpoint_enrollment_parses_to_closed_types(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint_path = Path(directory) / "endpoint.json"
            write_json(endpoint_path, valid_endpoint())
            endpoint = load_endpoint_enrollment(endpoint_path)
            self.assertEqual(
                endpoint.endpoint_class,
                EndpointClass.DEVELOPER_WORKSTATION,
            )
            self.assertEqual(endpoint.platform, EndpointPlatform.MACOS)
            self.assertEqual(
                endpoint.allowed_surfaces,
                (AgentSurface.CODEX, AgentSurface.CLAUDE_CODE),
            )

    def test_checked_in_pilot_endpoint_is_attributable_and_non_production(self):
        endpoint = load_endpoint_enrollment(self.pilot_endpoint_path)
        self.assertEqual(endpoint.endpoint_id, "michael-workstation")
        self.assertEqual(endpoint.principal, "agent:michael-workstation")
        self.assertEqual(
            endpoint.endpoint_class,
            EndpointClass.DEVELOPER_WORKSTATION,
        )
        self.assertEqual(endpoint.user_home, Path("/Users/michaelayoade"))
        self.assertTrue(str(endpoint.credential_pointer).startswith("openbao:"))

    def test_production_endpoint_enrollment_is_unrepresentable(self):
        with tempfile.TemporaryDirectory() as directory:
            endpoint_path = Path(directory) / "endpoint.json"
            endpoint = valid_endpoint()
            endpoint["endpoint_class"] = "production-application-host"
            write_json(endpoint_path, endpoint)
            with self.assertRaisesRegex(
                ProfileError,
                "endpoint_class is not admitted",
            ):
                load_endpoint_enrollment(endpoint_path)

    def test_policy_default_permission_must_be_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            policy_path = Path(directory) / "policy.json"
            policy = json.loads(self.policy_path.read_text(encoding="utf-8"))
            policy["codex"]["allowed_permission_profiles"] = [":read-only"]
            write_json(policy_path, policy)
            with self.assertRaisesRegex(
                ProfileError,
                "default_permission_profile must be allowed",
            ):
                load_managed_policy(policy_path)

    def test_stage_writes_content_addressed_non_secret_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            output = root / "bundle"
            write_json(endpoint_path, valid_endpoint())
            result = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                output,
                mode=DeploymentMode.STAGE,
            )
            self.assertTrue(result.succeeded)
            self.assertEqual(len(result.created), len(result.plan.artifacts))
            self.assertIn(
                "/Users/developer/.codex/AGENTS.md",
                {artifact.target.as_posix() for artifact in result.plan.artifacts},
            )
            self.assertFalse(result.plan.activation_permitted)
            self.assertTrue(
                any(
                    item.code is DiagnosticCode.DEPLOYMENT_SOURCE_DIRTY
                    for item in result.plan.diagnostics
                )
            )
            self.assertTrue((output / "attestation.json").is_file())
            tomllib.loads(
                (output / "payload" / "codex" / "requirements.toml").read_text(
                    encoding="utf-8"
                )
            )
            tomllib.loads(
                (output / "payload" / "codex" / "managed_config.toml").read_text(
                    encoding="utf-8"
                )
            )
            json.loads(
                (output / "payload" / "claude" / "managed-settings.json").read_text(
                    encoding="utf-8"
                )
            )
            json.loads(
                (output / "payload" / "claude" / "managed-mcp.json").read_text(
                    encoding="utf-8"
                )
            )
            for artifact in result.plan.artifacts:
                staged = output.joinpath(*artifact.stage_path.parts)
                self.assertEqual(
                    hashlib.sha256(staged.read_bytes()).hexdigest(),
                    artifact.sha256,
                )
            bundle_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in output.rglob("*")
                if path.is_file()
            )
            self.assertNotIn("knw_", bundle_text)
            self.assertIn("Bearer ${DOTMAC_KNOWLEDGE_MCP_TOKEN}", bundle_text)
            self.assertIn("DOTMAC_KNOWLEDGE_MCP_TOKEN", bundle_text)

            repeated = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                output,
                mode=DeploymentMode.STAGE,
            )
            self.assertTrue(repeated.succeeded)
            self.assertFalse(repeated.created)
            self.assertEqual(
                len(repeated.unchanged),
                len(repeated.plan.artifacts),
            )

    def test_policy_rejects_an_unlisted_endpoint_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            endpoint = valid_endpoint()
            endpoint["endpoint_id"] = "another-workstation"
            endpoint["principal"] = "agent:another-workstation"
            write_json(endpoint_path, endpoint)
            result = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                root / "bundle",
                mode=DeploymentMode.STAGE,
            )
            self.assertTrue(
                any(
                    item.code is DiagnosticCode.DEPLOYMENT_ENDPOINT_NOT_AUTHORIZED
                    for item in result.plan.diagnostics
                )
            )

    def test_stage_refuses_conflicting_existing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            output = root / "bundle"
            write_json(endpoint_path, valid_endpoint())
            first = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                output,
                mode=DeploymentMode.STAGE,
            )
            self.assertTrue(first.succeeded)
            target = output / "payload" / "codex" / "requirements.toml"
            target.write_text("operator-owned\n", encoding="utf-8")

            second = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                output,
                mode=DeploymentMode.STAGE,
            )
            self.assertFalse(second.succeeded)
            self.assertIn(
                Path("payload/codex/requirements.toml"),
                second.refused,
            )
            self.assertEqual(target.read_text(encoding="utf-8"), "operator-owned\n")

    def test_stage_refuses_symlink_escape_without_partial_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            output = root / "bundle"
            outside = root / "outside"
            output.mkdir()
            outside.mkdir()
            (output / "payload").symlink_to(outside, target_is_directory=True)
            write_json(endpoint_path, valid_endpoint())

            result = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                output,
                mode=DeploymentMode.STAGE,
            )
            self.assertFalse(result.succeeded)
            self.assertTrue(result.refused)
            self.assertFalse(any(outside.iterdir()))
            self.assertFalse((output / "attestation.json").exists())

    def test_apply_fails_closed_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            output = root / "activation"
            write_json(endpoint_path, valid_endpoint())
            result = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                output,
                mode=DeploymentMode.APPLY,
            )
            self.assertFalse(result.succeeded)
            self.assertFalse(output.exists())
            self.assertTrue(
                any(
                    item.code is DiagnosticCode.DEPLOYMENT_APPLY_NOT_IMPLEMENTED
                    for item in result.plan.diagnostics
                )
            )

    def test_local_activation_backs_up_migrates_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            backup_root = root / "backup"
            write_json(endpoint_path, valid_endpoint())
            existing_targets = (
                target_root / "Users/developer/.codex/AGENTS.md",
                target_root / "Users/developer/.claude/CLAUDE.md",
            )
            for target in existing_targets:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("operator-owned\n", encoding="utf-8")

            identity = RepositoryIdentity(
                canonical_repository=(
                    "https://github.com/michaelayoade/dotmac_governance"
                ),
                revision="d" * 40,
                dirty=False,
                branch="main",
            )
            with patch(
                "agent_control.managed.detect_repository_identity",
                return_value=identity,
            ):
                result = activate_local(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    backup_root,
                    migrate_existing=True,
                    target_root=target_root,
                )
            self.assertTrue(result.succeeded, result.diagnostics)
            self.assertEqual(len(result.replaced), 2)
            self.assertEqual(len(result.created), 5)
            self.assertIsNotNone(result.manifest)
            manifest = load_activation_manifest(backup_root / "manifest.json")
            self.assertEqual(manifest.status, ActivationManifestStatus.APPLIED)
            self.assertEqual(manifest.source_revision, "d" * 40)
            self.assertEqual(
                (backup_root / "files/Users/developer/.codex/AGENTS.md").read_text(
                    encoding="utf-8"
                ),
                "operator-owned\n",
            )
            for target in existing_targets:
                self.assertNotEqual(
                    target.read_text(encoding="utf-8"),
                    "operator-owned\n",
                )

            rolled_back = rollback_local(backup_root / "manifest.json")
            self.assertTrue(rolled_back.succeeded, rolled_back.diagnostics)
            self.assertEqual(len(rolled_back.restored), 2)
            self.assertEqual(len(rolled_back.removed), 5)
            for target in existing_targets:
                self.assertEqual(
                    target.read_text(encoding="utf-8"),
                    "operator-owned\n",
                )
            self.assertEqual(
                load_activation_manifest(backup_root / "manifest.json").status,
                ActivationManifestStatus.ROLLED_BACK,
            )

    def test_local_activation_refuses_unapproved_migration_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            backup_root = root / "backup"
            existing = target_root / "Users/developer/.codex/AGENTS.md"
            existing.parent.mkdir(parents=True, exist_ok=True)
            existing.write_text("operator-owned\n", encoding="utf-8")
            write_json(endpoint_path, valid_endpoint())
            identity = RepositoryIdentity(
                canonical_repository=(
                    "https://github.com/michaelayoade/dotmac_governance"
                ),
                revision="e" * 40,
                dirty=False,
                branch="main",
            )
            with patch(
                "agent_control.managed.detect_repository_identity",
                return_value=identity,
            ):
                result = activate_local(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    backup_root,
                    migrate_existing=False,
                    target_root=target_root,
                )
            self.assertFalse(result.succeeded)
            self.assertIn(
                Path("/Users/developer/.codex/AGENTS.md"),
                result.refused,
            )
            self.assertEqual(existing.read_text(encoding="utf-8"), "operator-owned\n")
            self.assertFalse(backup_root.exists())

    def test_local_activation_refuses_non_directory_backup_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            backup_root = root / "backup"
            backup_root.write_text("not-a-directory\n", encoding="utf-8")
            write_json(endpoint_path, valid_endpoint())
            identity = RepositoryIdentity(
                canonical_repository=(
                    "https://github.com/michaelayoade/dotmac_governance"
                ),
                revision="2" * 40,
                dirty=False,
                branch="main",
            )
            with patch(
                "agent_control.managed.detect_repository_identity",
                return_value=identity,
            ):
                result = activate_local(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    backup_root,
                    migrate_existing=True,
                    target_root=target_root,
                )
            self.assertFalse(result.succeeded)
            self.assertTrue(
                any(
                    item.code is DiagnosticCode.ACTIVATION_BACKUP_CONFLICT
                    for item in result.diagnostics
                )
            )
            self.assertFalse(target_root.exists())
            self.assertEqual(
                backup_root.read_text(encoding="utf-8"),
                "not-a-directory\n",
            )

    def test_local_rollback_refuses_post_activation_drift_without_partial_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            backup_root = root / "backup"
            write_json(endpoint_path, valid_endpoint())
            identity = RepositoryIdentity(
                canonical_repository=(
                    "https://github.com/michaelayoade/dotmac_governance"
                ),
                revision="f" * 40,
                dirty=False,
                branch="main",
            )
            with patch(
                "agent_control.managed.detect_repository_identity",
                return_value=identity,
            ):
                activated = activate_local(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    backup_root,
                    migrate_existing=True,
                    target_root=target_root,
                )
            self.assertTrue(activated.succeeded, activated.diagnostics)
            drifted = target_root / "etc/codex/requirements.toml"
            preserved = target_root / "etc/codex/managed_config.toml"
            preserved_content = preserved.read_bytes()
            drifted.write_text("post-activation change\n", encoding="utf-8")

            result = rollback_local(backup_root / "manifest.json")
            self.assertFalse(result.succeeded)
            self.assertIn(Path("/etc/codex/requirements.toml"), result.refused)
            self.assertEqual(
                drifted.read_text(encoding="utf-8"), "post-activation change\n"
            )
            self.assertEqual(preserved.read_bytes(), preserved_content)

    def test_local_activation_rolls_back_a_partial_write_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            backup_root = root / "backup"
            write_json(endpoint_path, valid_endpoint())
            identity = RepositoryIdentity(
                canonical_repository=(
                    "https://github.com/michaelayoade/dotmac_governance"
                ),
                revision="1" * 40,
                dirty=False,
                branch="main",
            )
            original_write = activation_module._atomic_write

            def failing_write(path, content, **kwargs):
                if path.name == "managed_config.toml":
                    raise OSError("test-only write failure")
                return original_write(path, content, **kwargs)

            with (
                patch(
                    "agent_control.managed.detect_repository_identity",
                    return_value=identity,
                ),
                patch(
                    "agent_control.activation._atomic_write",
                    side_effect=failing_write,
                ),
            ):
                result = activate_local(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    backup_root,
                    migrate_existing=True,
                    target_root=target_root,
                )
            self.assertFalse(result.succeeded)
            self.assertTrue(
                any(
                    item.code is DiagnosticCode.ACTIVATION_APPLY_FAILED
                    for item in result.diagnostics
                )
            )
            self.assertFalse(
                (target_root / "Users/developer/.codex/AGENTS.md").exists()
            )
            self.assertFalse((target_root / "etc/codex/requirements.toml").exists())
            self.assertEqual(
                load_activation_manifest(backup_root / "manifest.json").status,
                ActivationManifestStatus.ROLLED_BACK,
            )

    def test_reconcile_reports_matching_artifacts_and_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            write_json(endpoint_path, valid_endpoint())
            staged = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                root / "bundle",
                mode=DeploymentMode.STAGE,
            )
            for artifact in staged.plan.artifacts:
                if artifact.kind is ArtifactKind.ATTESTATION:
                    continue
                target = target_root.joinpath(*artifact.target.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(artifact.content, encoding="utf-8")
            with patch.dict(
                os.environ,
                {"DOTMAC_KNOWLEDGE_MCP_TOKEN": "test-only-present"},
            ):
                report = reconcile_endpoint(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    target_root,
                )
            self.assertTrue(report.artifacts_match)
            self.assertTrue(report.dependencies_available)
            self.assertEqual(
                report.credential_environment,
                DependencyState.AVAILABLE,
            )
            self.assertTrue(
                all(
                    observation.state is ArtifactState.MATCHED
                    for observation in report.observations
                )
            )
            self.assertFalse(report.plan.activation_permitted)
            self.assertFalse(report.ready_for_activation)

    def test_reconcile_reports_missing_and_drifted_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            endpoint_path = root / "endpoint.json"
            target_root = root / "endpoint-root"
            write_json(endpoint_path, valid_endpoint())
            staged = deploy_endpoint(
                self.policy_path,
                endpoint_path,
                REPOSITORY_ROOT,
                root / "bundle",
                mode=DeploymentMode.STAGE,
            )
            desired = tuple(
                artifact
                for artifact in staged.plan.artifacts
                if artifact.kind is not ArtifactKind.ATTESTATION
            )
            drifted = desired[0]
            drifted_target = target_root.joinpath(*drifted.target.parts[1:])
            drifted_target.parent.mkdir(parents=True, exist_ok=True)
            drifted_target.write_text("operator-owned\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {"DOTMAC_KNOWLEDGE_MCP_TOKEN": ""},
            ):
                report = reconcile_endpoint(
                    self.policy_path,
                    endpoint_path,
                    REPOSITORY_ROOT,
                    target_root,
                )
            states = {
                observation.kind: observation.state
                for observation in report.observations
            }
            self.assertEqual(states[drifted.kind], ArtifactState.DRIFTED)
            self.assertIn(ArtifactState.MISSING, states.values())
            self.assertEqual(
                report.credential_environment,
                DependencyState.MISSING,
            )
            self.assertFalse(report.artifacts_match)
            self.assertFalse(report.dependencies_available)
            self.assertFalse(report.ready_for_activation)

    def test_schema_enums_match_closed_contracts(self):
        endpoint_schema = json.loads(
            (
                REPOSITORY_ROOT
                / "agent_control"
                / "schema"
                / "endpoint-enrollment.schema.json"
            ).read_text(encoding="utf-8")
        )
        profile_schema = json.loads(
            (
                REPOSITORY_ROOT
                / "agent_control"
                / "schema"
                / "agent-profile.schema.json"
            ).read_text(encoding="utf-8")
        )
        policy_schema = json.loads(
            (
                REPOSITORY_ROOT
                / "agent_control"
                / "schema"
                / "managed-agent-policy.schema.json"
            ).read_text(encoding="utf-8")
        )
        manifest_schema = json.loads(
            (
                REPOSITORY_ROOT
                / "agent_control"
                / "schema"
                / "activation-manifest.schema.json"
            ).read_text(encoding="utf-8")
        )
        checked_policy = json.loads(self.policy_path.read_text(encoding="utf-8"))
        self.assertEqual(set(checked_policy), set(policy_schema["required"]))
        self.assertEqual(set(valid_endpoint()), set(endpoint_schema["required"]))
        self.assertEqual(
            set(endpoint_schema["properties"]["endpoint_class"]["enum"]),
            {item.value for item in EndpointClass},
        )
        self.assertEqual(
            set(endpoint_schema["properties"]["platform"]["enum"]),
            {item.value for item in EndpointPlatform},
        )
        self.assertEqual(
            set(
                profile_schema["$defs"]["rollout"]["properties"][
                    "authorized_endpoint_classes"
                ]["items"]["enum"]
            ),
            {item.value for item in EndpointClass},
        )
        self.assertEqual(
            set(manifest_schema["properties"]["status"]["enum"]),
            {item.value for item in ActivationManifestStatus},
        )
        self.assertEqual(
            set(manifest_schema["$defs"]["entry"]["properties"]["action"]["enum"]),
            {item.value for item in ActivationAction},
        )
        self.assertEqual(
            set(manifest_schema["$defs"]["entry"]["properties"]["kind"]["enum"]),
            {
                item.value
                for item in ArtifactKind
                if item is not ArtifactKind.ATTESTATION
            },
        )


if __name__ == "__main__":
    unittest.main()
