"""Immutable contracts shared by agent-control adapters and the policy engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import NewType

ProfileId = NewType("ProfileId", str)
PolicyId = NewType("PolicyId", str)
EndpointId = NewType("EndpointId", str)
ModelVersion = NewType("ModelVersion", str)
CanonicalRepository = NewType("CanonicalRepository", str)
BranchName = NewType("BranchName", str)
ValidationCommand = NewType("ValidationCommand", str)
BlockerReference = NewType("BlockerReference", str)
GitRevision = NewType("GitRevision", str)
PrincipalReference = NewType("PrincipalReference", str)
CredentialPointer = NewType("CredentialPointer", str)
EnvironmentVariable = NewType("EnvironmentVariable", str)
HttpsUrl = NewType("HttpsUrl", str)
McpServerName = NewType("McpServerName", str)
Sha256Digest = NewType("Sha256Digest", str)
ClientVersion = NewType("ClientVersion", str)
LocalUsername = NewType("LocalUsername", str)
FileMode = NewType("FileMode", int)


class Severity(str, Enum):
    """Diagnostic severity emitted by the conformance engine."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class GovernanceStatus(str, Enum):
    """Lifecycle status of the governance model referenced by a profile."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class AgentSurface(str, Enum):
    """Agent clients a repository profile permits."""

    CODEX = "codex"
    CLAUDE_CODE = "claude-code"


class RenderMode(str, Enum):
    """Whether instruction files are checked structurally or generated exactly."""

    VALIDATE = "validate"
    MANAGED = "managed"


class RolloutMode(str, Enum):
    """Activation state for endpoint policy distribution."""

    PILOT = "pilot"
    MANAGED = "managed"


class EndpointClass(str, Enum):
    """Non-production endpoint classes admitted by schema version 1."""

    DEVELOPER_WORKSTATION = "developer-workstation"
    CI_RUNNER = "ci-runner"


class EndpointPlatform(str, Enum):
    """Platforms validated by the initial managed-deployment adapter."""

    MACOS = "macos"
    LINUX = "linux"


class InstructionRole(str, Enum):
    """Instruction surfaces that have distinct client loading behavior."""

    AGENTS = "agents"
    CLAUDE = "claude"


class ProjectionAction(str, Enum):
    """Stable outcomes from an idempotent file projection."""

    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    REFUSED = "refused"


class DeploymentMode(str, Enum):
    """Whether a deployment bundle is only staged or activated."""

    STAGE = "stage"
    APPLY = "apply"


class ArtifactKind(str, Enum):
    """Managed client artifact types emitted by the deployment owner."""

    CODEX_GLOBAL_INSTRUCTIONS = "codex-global-instructions"
    CODEX_MANAGED_CONFIG = "codex-managed-config"
    CODEX_REQUIREMENTS = "codex-requirements"
    CLAUDE_MANAGED_INSTRUCTIONS = "claude-managed-instructions"
    CLAUDE_USER_INSTRUCTIONS = "claude-user-instructions"
    CLAUDE_MANAGED_SETTINGS = "claude-managed-settings"
    CLAUDE_MANAGED_MCP = "claude-managed-mcp"
    ATTESTATION = "attestation"


class ArtifactOwnership(str, Enum):
    """Required owner class for an activated artifact."""

    ROOT = "root"
    ENDPOINT_USER = "endpoint-user"


class ArtifactState(str, Enum):
    """Observed state of one managed artifact on an endpoint."""

    MATCHED = "matched"
    MISSING = "missing"
    DRIFTED = "drifted"


class DependencyState(str, Enum):
    """Availability of an endpoint dependency not owned by this renderer."""

    AVAILABLE = "available"
    MISSING = "missing"
    NOT_APPLICABLE = "not-applicable"


class ActivationAction(str, Enum):
    """One local installer's intended effect on an endpoint target."""

    CREATED = "created"
    REPLACED = "replaced"
    UNCHANGED = "unchanged"


class ActivationManifestStatus(str, Enum):
    """Lifecycle state of one backup-backed activation manifest."""

    PREPARED = "prepared"
    APPLIED = "applied"
    ROLLED_BACK = "rolled-back"


class ApprovalPolicy(str, Enum):
    """Codex approval policies admitted by the candidate managed baseline."""

    ON_REQUEST = "on-request"
    UNTRUSTED = "untrusted"


class PermissionProfile(str, Enum):
    """Codex built-in permission profiles admitted by the baseline."""

    READ_ONLY = ":read-only"
    WORKSPACE = ":workspace"


class WebSearchMode(str, Enum):
    """Codex web-search modes admitted by managed requirements."""

    DISABLED = "disabled"
    CACHED = "cached"
    INDEXED = "indexed"
    LIVE = "live"


class UpdateChannel(str, Enum):
    """Claude Code update channels supported by managed settings."""

    STABLE = "stable"
    LATEST = "latest"


class DiagnosticCode(str, Enum):
    """Closed machine-readable finding codes emitted by the engine."""

    PROFILE_INVALID = "profile.invalid"
    REPOSITORY_IDENTITY_UNAVAILABLE = "repository.identity.unavailable"
    REPOSITORY_IDENTITY_MISMATCH = "repository.identity.mismatch"
    REPOSITORY_WORKING_TREE_DIRTY = "repository.working-tree.dirty"
    GOVERNANCE_SOURCE_MISSING = "governance.source.missing"
    GOVERNANCE_SOURCE_STATUS_MISSING = "governance.source.status-missing"
    GOVERNANCE_SOURCE_STATUS_MISMATCH = "governance.source.status-mismatch"
    INSTRUCTION_AGENTS_MISSING = "instruction.agents.missing"
    INSTRUCTION_AGENTS_ENCODING = "instruction.agents.encoding"
    INSTRUCTION_AGENTS_MARKER_MISSING = "instruction.agents.marker-missing"
    INSTRUCTION_AGENTS_MANAGED_DRIFT = "instruction.agents.managed-drift"
    INSTRUCTION_CLAUDE_MISSING = "instruction.claude.missing"
    INSTRUCTION_CLAUDE_ENCODING = "instruction.claude.encoding"
    INSTRUCTION_CLAUDE_MARKER_MISSING = "instruction.claude.marker-missing"
    INSTRUCTION_CLAUDE_MANAGED_DRIFT = "instruction.claude.managed-drift"
    INSTRUCTION_CLAUDE_DUPLICATES_SHARED_RULE = (
        "instruction.claude.duplicates-shared-rule"
    )
    INSTRUCTION_CLAUDE_IMPORT_ORDER = "instruction.claude.import-order"
    INSTRUCTION_CONTEXT_BUDGET_EXCEEDED = "instruction.context-budget.exceeded"
    INSTRUCTION_CONTEXT_BUDGET_WARNING = "instruction.context-budget.warning"
    INSTRUCTION_AUTHORITY_SOURCE_MISSING = "instruction.authority-source.missing"
    VALIDATION_COMMAND_INVALID = "validation.command.invalid"
    VALIDATION_COMMAND_EMPTY = "validation.command.empty"
    VALIDATION_COMMAND_PATH_MISSING = "validation.command.path-missing"
    ROLLOUT_ACCEPTED_GOVERNANCE_REQUIRED = "rollout.accepted-governance-required"
    ROLLOUT_BLOCKERS_OPEN = "rollout.blockers-open"
    ROLLOUT_MANAGED_CONFIGURATION_DISABLED = "rollout.managed-configuration-disabled"
    ROLLOUT_PILOT_CANNOT_MANAGE = "rollout.pilot-cannot-manage"
    SECRET_PRIVATE_KEY = "secret.private-key"
    SECRET_OPENAI = "secret.openai"
    SECRET_GITHUB = "secret.github"
    SECRET_KNOWLEDGE = "secret.knowledge"
    SECRET_BEARER = "secret.bearer"
    DEPLOYMENT_POLICY_MISMATCH = "deployment.policy-mismatch"
    DEPLOYMENT_ENDPOINT_CLASS_NOT_AUTHORIZED = (
        "deployment.endpoint-class-not-authorized"
    )
    DEPLOYMENT_ENDPOINT_NOT_AUTHORIZED = "deployment.endpoint-not-authorized"
    DEPLOYMENT_SURFACE_NOT_AUTHORIZED = "deployment.surface-not-authorized"
    DEPLOYMENT_GOVERNANCE_NOT_ACCEPTED = "deployment.governance-not-accepted"
    DEPLOYMENT_BLOCKERS_OPEN = "deployment.blockers-open"
    DEPLOYMENT_MANAGED_CONFIGURATION_DISABLED = (
        "deployment.managed-configuration-disabled"
    )
    DEPLOYMENT_SOURCE_IDENTITY_UNAVAILABLE = "deployment.source-identity-unavailable"
    DEPLOYMENT_SOURCE_IDENTITY_MISMATCH = "deployment.source-identity-mismatch"
    DEPLOYMENT_SOURCE_BRANCH_MISMATCH = "deployment.source-branch-mismatch"
    DEPLOYMENT_SOURCE_DIRTY = "deployment.source-dirty"
    DEPLOYMENT_GOVERNANCE_SOURCE_MISSING = "deployment.governance-source-missing"
    DEPLOYMENT_GOVERNANCE_STATUS_MISMATCH = "deployment.governance-status-mismatch"
    DEPLOYMENT_STAGE_CONFLICT = "deployment.stage-conflict"
    DEPLOYMENT_APPLY_NOT_IMPLEMENTED = "deployment.apply-not-implemented"
    ACTIVATION_PLAN_NOT_PERMITTED = "activation.plan-not-permitted"
    ACTIVATION_PRIVILEGE_REQUIRED = "activation.privilege-required"
    ACTIVATION_PLATFORM_MISMATCH = "activation.platform-mismatch"
    ACTIVATION_LOCAL_USER_MISMATCH = "activation.local-user-mismatch"
    ACTIVATION_TARGET_CONFLICT = "activation.target-conflict"
    ACTIVATION_BACKUP_CONFLICT = "activation.backup-conflict"
    ACTIVATION_APPLY_FAILED = "activation.apply-failed"
    ACTIVATION_MANIFEST_INVALID = "activation.manifest-invalid"
    ROLLBACK_TARGET_DRIFT = "rollback.target-drift"


@dataclass(frozen=True)
class GovernanceModelRef:
    """Versioned Git source that owns the profile's governance model."""

    version: ModelVersion
    source: PurePosixPath
    status: GovernanceStatus


@dataclass(frozen=True)
class InstructionContract:
    """Structure, routing, and context-budget rules for instruction files."""

    agents_path: PurePosixPath
    claude_path: PurePosixPath
    claude_import: str
    render_mode: RenderMode
    max_combined_bytes: int
    warn_combined_bytes: int
    required_agents_markers: tuple[str, ...]
    required_claude_markers: tuple[str, ...]
    authoritative_sources: tuple[PurePosixPath, ...]
    claude_additions: tuple[str, ...]


@dataclass(frozen=True)
class RolloutContract:
    """Explicit rollout gate and authorized endpoint classes."""

    mode: RolloutMode
    managed_configuration: bool
    authorized_endpoint_classes: tuple[EndpointClass, ...]
    blocked_by: tuple[BlockerReference, ...]


@dataclass(frozen=True)
class AgentProfile:
    """Complete typed repository profile consumed by every adapter."""

    schema_version: int
    profile_id: ProfileId
    repository_name: str
    summary: str
    canonical_repository: CanonicalRepository
    default_branch: BranchName
    governance_model: GovernanceModelRef
    instructions: InstructionContract
    validation_commands: tuple[ValidationCommand, ...]
    allowed_surfaces: tuple[AgentSurface, ...]
    rollout: RolloutContract


@dataclass(frozen=True)
class RepositoryIdentity:
    """Observed Git identity used to prevent a clone from changing scope."""

    canonical_repository: CanonicalRepository
    revision: GitRevision
    dirty: bool = False
    branch: BranchName | None = None


@dataclass(frozen=True)
class Diagnostic:
    """One stable, machine-readable conformance finding."""

    severity: Severity
    code: DiagnosticCode
    message: str
    path: PurePosixPath | None = None

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI/reporting adapter boundary."""

        payload: dict[str, object] = {
            "severity": self.severity.value,
            "code": self.code.value,
            "message": self.message,
        }
        if self.path is not None:
            payload["path"] = self.path.as_posix()
        return payload


@dataclass(frozen=True)
class ConformanceReport:
    """Deterministic result of evaluating one repository profile."""

    profile_id: ProfileId
    model_version: ModelVersion
    repository_root: Path
    source_revision: GitRevision | None
    source_dirty: bool | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        """Return blocking diagnostics."""

        return tuple(
            item for item in self.diagnostics if item.severity is Severity.ERROR
        )

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        """Return advisory diagnostics."""

        return tuple(
            item for item in self.diagnostics if item.severity is Severity.WARNING
        )

    @property
    def conforms(self) -> bool:
        """Whether the repository satisfies every blocking control."""

        return not self.errors

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI/reporting adapter boundary."""

        return {
            "profile_id": self.profile_id,
            "model_version": self.model_version,
            "repository_root": str(self.repository_root),
            "source_revision": self.source_revision,
            "source_dirty": self.source_dirty,
            "conforms": self.conforms,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class RenderedInstructions:
    """Rendered projections for the two vendor instruction boundaries."""

    agents: str
    claude: str


@dataclass(frozen=True)
class BootstrapResult:
    """Plan or applied result of an idempotent repository bootstrap."""

    applied: bool
    created: tuple[PurePosixPath, ...]
    updated: tuple[PurePosixPath, ...]
    unchanged: tuple[PurePosixPath, ...]
    refused: tuple[PurePosixPath, ...]
    report: ConformanceReport

    @property
    def succeeded(self) -> bool:
        """Whether bootstrap completed without refusal or conformance errors."""

        return not self.refused and self.report.conforms

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI/reporting adapter boundary."""

        return {
            "applied": self.applied,
            "created": [path.as_posix() for path in self.created],
            "updated": [path.as_posix() for path in self.updated],
            "unchanged": [path.as_posix() for path in self.unchanged],
            "refused": [path.as_posix() for path in self.refused],
            "succeeded": self.succeeded,
            "report": self.report.to_dict(),
        }


@dataclass(frozen=True)
class ClientRuntime:
    """Non-secret runtime fact collected by the doctor adapter."""

    surface: AgentSurface
    executable: Path | None
    version: ClientVersion | None

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI/reporting adapter boundary."""

        return {
            "surface": self.surface.value,
            "executable": str(self.executable) if self.executable is not None else None,
            "version": self.version,
        }


@dataclass(frozen=True)
class DoctorReport:
    """Conformance plus local client availability, without secret material."""

    conformance: ConformanceReport
    clients: tuple[ClientRuntime, ...]
    rollout_mode: RolloutMode
    managed_configuration: bool
    blockers: tuple[BlockerReference, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI/reporting adapter boundary."""

        return {
            "conformance": self.conformance.to_dict(),
            "clients": [client.to_dict() for client in self.clients],
            "rollout": {
                "mode": self.rollout_mode.value,
                "managed_configuration": self.managed_configuration,
                "blocked_by": list(self.blockers),
            },
        }


@dataclass(frozen=True)
class ProjectionResult:
    """One typed result from projecting an owned file."""

    action: ProjectionAction
    path: PurePosixPath


@dataclass(frozen=True)
class ManagedMcpServer:
    """Identity and non-secret credential adapter for one managed MCP server."""

    name: McpServerName
    url: HttpsUrl


@dataclass(frozen=True)
class CodexManagedPolicy:
    """Typed Codex requirements and managed-default values."""

    allowed_approval_policies: tuple[ApprovalPolicy, ...]
    allowed_permission_profiles: tuple[PermissionProfile, ...]
    default_permission_profile: PermissionProfile
    allowed_web_search_modes: tuple[WebSearchMode, ...]
    allow_managed_hooks_only: bool
    disable_remote_control: bool
    disable_computer_use: bool


@dataclass(frozen=True)
class ClaudeManagedPolicy:
    """Typed Claude Code managed settings values."""

    update_channel: UpdateChannel
    allow_managed_hooks_only: bool
    allow_managed_mcp_servers_only: bool
    allow_managed_permission_rules_only: bool
    sandbox_enabled: bool
    sandbox_fail_if_unavailable: bool
    sandbox_allow_unsandboxed_commands: bool


@dataclass(frozen=True)
class ManagedPolicy:
    """Git-owned candidate policy rendered into vendor-managed artifacts."""

    schema_version: int
    policy_id: PolicyId
    version: ModelVersion
    canonical_repository: CanonicalRepository
    default_branch: BranchName
    governance_model: GovernanceModelRef
    allowed_surfaces: tuple[AgentSurface, ...]
    allowed_endpoint_classes: tuple[EndpointClass, ...]
    allowed_endpoint_ids: tuple[EndpointId, ...]
    blocked_by: tuple[BlockerReference, ...]
    managed_configuration: bool
    global_instruction_source: PurePosixPath
    claude_user_instruction_source: PurePosixPath
    codex: CodexManagedPolicy
    claude: ClaudeManagedPolicy
    mcp_servers: tuple[ManagedMcpServer, ...]


@dataclass(frozen=True)
class EndpointEnrollment:
    """Attributable endpoint input consumed by staging and reconciliation."""

    schema_version: int
    endpoint_id: EndpointId
    endpoint_class: EndpointClass
    platform: EndpointPlatform
    principal: PrincipalReference
    local_user: LocalUsername
    credential_pointer: CredentialPointer
    credential_environment_variable: EnvironmentVariable
    user_home: Path
    allowed_surfaces: tuple[AgentSurface, ...]
    policy_id: PolicyId


@dataclass(frozen=True)
class ManagedArtifact:
    """One content-addressed deployment artifact and its intended target."""

    kind: ArtifactKind
    target: PurePosixPath
    stage_path: PurePosixPath
    sha256: Sha256Digest
    content: str
    ownership: ArtifactOwnership
    mode: FileMode

    def to_dict(self) -> dict[str, object]:
        """Serialize artifact metadata without duplicating its content."""

        return {
            "kind": self.kind.value,
            "target": self.target.as_posix(),
            "stage_path": self.stage_path.as_posix(),
            "sha256": self.sha256,
            "ownership": self.ownership.value,
            "mode": int(self.mode),
        }


@dataclass(frozen=True)
class DeploymentAttestation:
    """Non-secret source and artifact identity for one staged bundle."""

    endpoint_id: EndpointId
    endpoint_class: EndpointClass
    platform: EndpointPlatform
    principal: PrincipalReference
    local_user: LocalUsername
    user_home: Path
    policy_id: PolicyId
    policy_version: ModelVersion
    source_revision: GitRevision | None
    source_dirty: bool | None
    source_branch: BranchName | None
    artifacts: tuple[ManagedArtifact, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the immutable attestation payload."""

        return {
            "endpoint_id": self.endpoint_id,
            "endpoint_class": self.endpoint_class.value,
            "platform": self.platform.value,
            "principal": self.principal,
            "local_user": self.local_user,
            "user_home": str(self.user_home),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "source_revision": self.source_revision,
            "source_dirty": self.source_dirty,
            "source_branch": self.source_branch,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclass(frozen=True)
class DeploymentPlan:
    """Typed decision for one endpoint and one managed policy version."""

    endpoint: EndpointEnrollment
    policy: ManagedPolicy
    source_revision: GitRevision | None
    source_dirty: bool | None
    source_branch: BranchName | None
    artifacts: tuple[ManagedArtifact, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def activation_permitted(self) -> bool:
        """Whether governance permits endpoint activation."""

        return not any(
            diagnostic.severity is Severity.ERROR for diagnostic in self.diagnostics
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize at the deployment-reporting boundary."""

        return {
            "endpoint_id": self.endpoint.endpoint_id,
            "endpoint_class": self.endpoint.endpoint_class.value,
            "platform": self.endpoint.platform.value,
            "principal": self.endpoint.principal,
            "local_user": self.endpoint.local_user,
            "credential_pointer": self.endpoint.credential_pointer,
            "credential_environment_variable": (
                self.endpoint.credential_environment_variable
            ),
            "user_home": str(self.endpoint.user_home),
            "allowed_surfaces": [
                surface.value for surface in self.endpoint.allowed_surfaces
            ],
            "policy_id": self.policy.policy_id,
            "policy_version": self.policy.version,
            "source_revision": self.source_revision,
            "source_dirty": self.source_dirty,
            "source_branch": self.source_branch,
            "activation_permitted": self.activation_permitted,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


@dataclass(frozen=True)
class DeploymentResult:
    """Typed stage/apply outcome for one deployment plan."""

    mode: DeploymentMode
    output_root: Path
    plan: DeploymentPlan
    created: tuple[PurePosixPath, ...]
    unchanged: tuple[PurePosixPath, ...]
    refused: tuple[PurePosixPath, ...]

    @property
    def succeeded(self) -> bool:
        """Staging succeeds when all artifacts were written."""

        return (
            self.mode is DeploymentMode.STAGE
            and not self.refused
            and len(self.created) + len(self.unchanged) == len(self.plan.artifacts)
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI boundary."""

        return {
            "mode": self.mode.value,
            "output_root": str(self.output_root),
            "succeeded": self.succeeded,
            "created": [path.as_posix() for path in self.created],
            "unchanged": [path.as_posix() for path in self.unchanged],
            "refused": [path.as_posix() for path in self.refused],
            "plan": self.plan.to_dict(),
        }


@dataclass(frozen=True)
class ArtifactObservation:
    """Read-only comparison between desired and endpoint artifact identity."""

    kind: ArtifactKind
    target: PurePosixPath
    expected_sha256: Sha256Digest
    observed_sha256: Sha256Digest | None
    state: ArtifactState

    def to_dict(self) -> dict[str, object]:
        """Serialize at the status-reporting boundary."""

        return {
            "kind": self.kind.value,
            "target": self.target.as_posix(),
            "expected_sha256": self.expected_sha256,
            "observed_sha256": self.observed_sha256,
            "state": self.state.value,
        }


@dataclass(frozen=True)
class ReconciliationReport:
    """Typed desired-versus-observed endpoint report."""

    plan: DeploymentPlan
    target_root: Path
    observations: tuple[ArtifactObservation, ...]
    credential_environment: DependencyState

    @property
    def artifacts_match(self) -> bool:
        """Whether every endpoint-managed artifact matches desired bytes."""

        return bool(self.observations) and all(
            observation.state is ArtifactState.MATCHED
            for observation in self.observations
        )

    @property
    def dependencies_available(self) -> bool:
        """Whether every applicable dependency is available."""

        return self.credential_environment is not DependencyState.MISSING

    @property
    def ready_for_activation(self) -> bool:
        """Whether source gates, installed artifacts, and dependencies conform."""

        return (
            self.plan.activation_permitted
            and self.artifacts_match
            and self.dependencies_available
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize at the CLI or future read-only MCP boundary."""

        return {
            "target_root": str(self.target_root),
            "artifacts_match": self.artifacts_match,
            "dependencies_available": self.dependencies_available,
            "ready_for_activation": self.ready_for_activation,
            "credential_environment": self.credential_environment.value,
            "observations": [
                observation.to_dict() for observation in self.observations
            ],
            "plan": self.plan.to_dict(),
        }


@dataclass(frozen=True)
class ActivationEntry:
    """Backup and desired-state identity for one activated endpoint file."""

    kind: ArtifactKind
    target: PurePosixPath
    action: ActivationAction
    desired_sha256: Sha256Digest
    backup_path: PurePosixPath | None
    prior_sha256: Sha256Digest | None
    prior_mode: FileMode | None
    prior_uid: int | None
    prior_gid: int | None

    def to_dict(self) -> dict[str, object]:
        """Serialize without file content or credential values."""

        return {
            "kind": self.kind.value,
            "target": self.target.as_posix(),
            "action": self.action.value,
            "desired_sha256": self.desired_sha256,
            "backup_path": (
                self.backup_path.as_posix() if self.backup_path is not None else None
            ),
            "prior_sha256": self.prior_sha256,
            "prior_mode": (
                int(self.prior_mode) if self.prior_mode is not None else None
            ),
            "prior_uid": self.prior_uid,
            "prior_gid": self.prior_gid,
        }


@dataclass(frozen=True)
class ActivationManifest:
    """Typed rollback manifest for one exact endpoint and source revision."""

    schema_version: int
    status: ActivationManifestStatus
    endpoint_id: EndpointId
    policy_id: PolicyId
    policy_version: ModelVersion
    source_revision: GitRevision
    target_root: Path
    entries: tuple[ActivationEntry, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the non-secret rollback manifest."""

        return {
            "schema_version": self.schema_version,
            "status": self.status.value,
            "endpoint_id": self.endpoint_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "source_revision": self.source_revision,
            "target_root": str(self.target_root),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class LocalActivationResult:
    """Outcome of the accepted endpoint-specific local installer."""

    plan: DeploymentPlan
    backup_root: Path
    manifest: ActivationManifest | None
    created: tuple[PurePosixPath, ...]
    replaced: tuple[PurePosixPath, ...]
    unchanged: tuple[PurePosixPath, ...]
    refused: tuple[PurePosixPath, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def succeeded(self) -> bool:
        """Whether every target reached the desired state."""

        return (
            not self.refused
            and not any(item.severity is Severity.ERROR for item in self.diagnostics)
            and self.manifest is not None
            and self.manifest.status is ActivationManifestStatus.APPLIED
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize at the privileged CLI boundary."""

        return {
            "succeeded": self.succeeded,
            "backup_root": str(self.backup_root),
            "created": [path.as_posix() for path in self.created],
            "replaced": [path.as_posix() for path in self.replaced],
            "unchanged": [path.as_posix() for path in self.unchanged],
            "refused": [path.as_posix() for path in self.refused],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "manifest": self.manifest.to_dict() if self.manifest is not None else None,
            "plan": self.plan.to_dict(),
        }


@dataclass(frozen=True)
class RollbackResult:
    """Outcome of a manifest-constrained local rollback."""

    manifest_path: Path
    restored: tuple[PurePosixPath, ...]
    removed: tuple[PurePosixPath, ...]
    unchanged: tuple[PurePosixPath, ...]
    refused: tuple[PurePosixPath, ...]
    diagnostics: tuple[Diagnostic, ...]

    @property
    def succeeded(self) -> bool:
        """Whether rollback completed without drift or contract errors."""

        return not self.refused and not any(
            item.severity is Severity.ERROR for item in self.diagnostics
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize at the privileged CLI boundary."""

        return {
            "succeeded": self.succeeded,
            "manifest_path": str(self.manifest_path),
            "restored": [path.as_posix() for path in self.restored],
            "removed": [path.as_posix() for path in self.removed],
            "unchanged": [path.as_posix() for path in self.unchanged],
            "refused": [path.as_posix() for path in self.refused],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
