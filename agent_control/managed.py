"""Typed managed-policy, endpoint-enrollment, and staging adapters."""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import TypeVar

from .contracts import (
    AgentSurface,
    ApprovalPolicy,
    ArtifactKind,
    ArtifactObservation,
    ArtifactOwnership,
    ArtifactState,
    BlockerReference,
    BranchName,
    CanonicalRepository,
    ClaudeManagedPolicy,
    CodexManagedPolicy,
    CredentialPointer,
    DependencyState,
    DeploymentAttestation,
    DeploymentMode,
    DeploymentPlan,
    DeploymentResult,
    Diagnostic,
    DiagnosticCode,
    EndpointClass,
    EndpointEnrollment,
    EndpointId,
    EndpointPlatform,
    EnvironmentVariable,
    FileMode,
    GovernanceModelRef,
    GovernanceStatus,
    HttpsUrl,
    LocalUsername,
    ManagedArtifact,
    ManagedMcpServer,
    ManagedPolicy,
    McpServerName,
    ModelVersion,
    PermissionProfile,
    PolicyId,
    PrincipalReference,
    ReconciliationReport,
    RepositoryIdentity,
    Severity,
    Sha256Digest,
    UpdateChannel,
    WebSearchMode,
)
from .engine import detect_repository_identity
from .profile import ProfileError

KEBAB_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MODEL_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?$")
HTTPS_URL = re.compile(r"^https://[^/\s]+(?:/[^\s]*)?$")
PRINCIPAL = re.compile(r"^agent:[a-z0-9]+(?:-[a-z0-9]+)*$")
LOCAL_USERNAME = re.compile(r"^[a-z_][a-z0-9_-]*$")
ENVIRONMENT_VARIABLE = re.compile(r"^[A-Z][A-Z0-9_]*$")
POINTER = re.compile(r"^(?:openbao:secret/[A-Za-z0-9._/-]+#[A-Za-z0-9._-]+|file:/\S+)$")
CANONICAL_REPOSITORY = re.compile(r"^https://[^/\s]+/[^/\s]+/[^/\s]+$")
BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
ADR_STATUS = re.compile(r"^- Status:\s*(Proposed|Accepted)\s*$", re.MULTILINE)
EnumValue = TypeVar("EnumValue", bound=Enum)
DEFAULT_ARTIFACT_MODE = FileMode(0o644)


def _object(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ProfileError(f"{location} must be an object")
    return value


def _keys(
    value: Mapping[str, object],
    required: frozenset[str],
    location: str,
) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing:
        raise ProfileError(f"{location} missing keys: {', '.join(missing)}")
    if unknown:
        raise ProfileError(f"{location} has unknown keys: {', '.join(unknown)}")


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ProfileError(f"{location} must be a non-empty string")
    return value.strip()


def _boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileError(f"{location} must be a boolean")
    return value


def _integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileError(f"{location} must be an integer")
    return value


def _strings(value: object, location: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProfileError(f"{location} must be an array of strings")
    result = tuple(
        _string(item, f"{location}[{index}]") for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise ProfileError(f"{location} must not contain duplicates")
    return result


def _enum_values(
    value: object,
    location: str,
    enum_type: type[EnumValue],
) -> tuple[EnumValue, ...]:
    result: list[EnumValue] = []
    for raw in _strings(value, location):
        try:
            result.append(enum_type(raw))
        except ValueError as error:
            raise ProfileError(f"{location} entry {raw!r} is invalid") from error
    if not result:
        raise ProfileError(f"{location} must not be empty")
    return tuple(result)


def _governance(value: object, location: str) -> GovernanceModelRef:
    data = _object(value, location)
    _keys(data, frozenset({"version", "source", "status"}), location)
    raw_version = _string(data["version"], f"{location}.version")
    if not MODEL_VERSION.fullmatch(raw_version):
        raise ProfileError(f"{location}.version must use semantic version syntax")
    raw_source = _string(data["source"], f"{location}.source")
    source = PurePosixPath(raw_source)
    if source.is_absolute() or ".." in source.parts:
        raise ProfileError(f"{location}.source must be repository-relative")
    raw_status = _string(data["status"], f"{location}.status")
    try:
        status = GovernanceStatus(raw_status)
    except ValueError as error:
        raise ProfileError(f"{location}.status must be proposed or accepted") from error
    return GovernanceModelRef(ModelVersion(raw_version), source, status)


def _parse_codex(value: object) -> CodexManagedPolicy:
    location = "codex"
    data = _object(value, location)
    _keys(
        data,
        frozenset(
            {
                "allowed_approval_policies",
                "allowed_permission_profiles",
                "default_permission_profile",
                "allowed_web_search_modes",
                "allow_managed_hooks_only",
                "disable_remote_control",
                "disable_computer_use",
            }
        ),
        location,
    )
    permission_profiles = _enum_values(
        data["allowed_permission_profiles"],
        f"{location}.allowed_permission_profiles",
        PermissionProfile,
    )
    raw_default = _string(
        data["default_permission_profile"],
        f"{location}.default_permission_profile",
    )
    try:
        default = PermissionProfile(raw_default)
    except ValueError as error:
        raise ProfileError(
            f"{location}.default_permission_profile is invalid"
        ) from error
    if default not in permission_profiles:
        raise ProfileError(f"{location}.default_permission_profile must be allowed")
    return CodexManagedPolicy(
        allowed_approval_policies=_enum_values(
            data["allowed_approval_policies"],
            f"{location}.allowed_approval_policies",
            ApprovalPolicy,
        ),
        allowed_permission_profiles=permission_profiles,
        default_permission_profile=default,
        allowed_web_search_modes=_enum_values(
            data["allowed_web_search_modes"],
            f"{location}.allowed_web_search_modes",
            WebSearchMode,
        ),
        allow_managed_hooks_only=_boolean(
            data["allow_managed_hooks_only"],
            f"{location}.allow_managed_hooks_only",
        ),
        disable_remote_control=_boolean(
            data["disable_remote_control"],
            f"{location}.disable_remote_control",
        ),
        disable_computer_use=_boolean(
            data["disable_computer_use"],
            f"{location}.disable_computer_use",
        ),
    )


def _parse_claude(value: object) -> ClaudeManagedPolicy:
    location = "claude"
    data = _object(value, location)
    _keys(
        data,
        frozenset(
            {
                "update_channel",
                "allow_managed_hooks_only",
                "allow_managed_mcp_servers_only",
                "allow_managed_permission_rules_only",
                "sandbox_enabled",
                "sandbox_fail_if_unavailable",
                "sandbox_allow_unsandboxed_commands",
            }
        ),
        location,
    )
    raw_update_channel = _string(
        data["update_channel"],
        f"{location}.update_channel",
    )
    try:
        update_channel = UpdateChannel(raw_update_channel)
    except ValueError as error:
        raise ProfileError(f"{location}.update_channel is invalid") from error
    return ClaudeManagedPolicy(
        update_channel=update_channel,
        allow_managed_hooks_only=_boolean(
            data["allow_managed_hooks_only"],
            f"{location}.allow_managed_hooks_only",
        ),
        allow_managed_mcp_servers_only=_boolean(
            data["allow_managed_mcp_servers_only"],
            f"{location}.allow_managed_mcp_servers_only",
        ),
        allow_managed_permission_rules_only=_boolean(
            data["allow_managed_permission_rules_only"],
            f"{location}.allow_managed_permission_rules_only",
        ),
        sandbox_enabled=_boolean(
            data["sandbox_enabled"],
            f"{location}.sandbox_enabled",
        ),
        sandbox_fail_if_unavailable=_boolean(
            data["sandbox_fail_if_unavailable"],
            f"{location}.sandbox_fail_if_unavailable",
        ),
        sandbox_allow_unsandboxed_commands=_boolean(
            data["sandbox_allow_unsandboxed_commands"],
            f"{location}.sandbox_allow_unsandboxed_commands",
        ),
    )


def parse_managed_policy(value: object) -> ManagedPolicy:
    """Convert untrusted JSON into the managed-policy domain contract."""

    data = _object(value, "policy")
    _keys(
        data,
        frozenset(
            {
                "schema_version",
                "policy_id",
                "version",
                "canonical_repository",
                "default_branch",
                "governance_model",
                "allowed_surfaces",
                "allowed_endpoint_classes",
                "allowed_endpoint_ids",
                "blocked_by",
                "managed_configuration",
                "global_instruction_source",
                "claude_user_instruction_source",
                "codex",
                "claude",
                "mcp_servers",
            }
        ),
        "policy",
    )
    schema_version = _integer(data["schema_version"], "schema_version")
    if schema_version != 1:
        raise ProfileError(f"schema_version must be 1, found {schema_version!r}")
    raw_policy_id = _string(data["policy_id"], "policy_id")
    if not KEBAB_ID.fullmatch(raw_policy_id):
        raise ProfileError("policy_id must be lowercase kebab-case")
    raw_version = _string(data["version"], "version")
    if not MODEL_VERSION.fullmatch(raw_version):
        raise ProfileError("version must use semantic version syntax")
    raw_repository = _string(
        data["canonical_repository"],
        "canonical_repository",
    ).removesuffix(".git")
    raw_branch = _string(data["default_branch"], "default_branch")
    if not CANONICAL_REPOSITORY.fullmatch(raw_repository):
        raise ProfileError("canonical_repository must be an HTTPS owner/repository URL")
    if not BRANCH.fullmatch(raw_branch):
        raise ProfileError("default_branch is invalid")
    governance = _governance(
        data["governance_model"],
        "governance_model",
    )
    if governance.version != ModelVersion(raw_version):
        raise ProfileError("version must match governance_model.version")

    servers: list[ManagedMcpServer] = []
    raw_servers = data["mcp_servers"]
    if not isinstance(raw_servers, Sequence) or isinstance(raw_servers, (str, bytes)):
        raise ProfileError("mcp_servers must be an array")
    names: set[str] = set()
    for index, raw_server in enumerate(raw_servers):
        location = f"mcp_servers[{index}]"
        server = _object(raw_server, location)
        _keys(server, frozenset({"name", "url"}), location)
        name = _string(server["name"], f"{location}.name")
        url = _string(server["url"], f"{location}.url")
        if not KEBAB_ID.fullmatch(name):
            raise ProfileError(f"{location}.name must be lowercase kebab-case")
        if not HTTPS_URL.fullmatch(url):
            raise ProfileError(f"{location}.url must be HTTPS")
        if name in names:
            raise ProfileError("mcp_servers names must be unique")
        names.add(name)
        servers.append(ManagedMcpServer(name=McpServerName(name), url=HttpsUrl(url)))
    if not servers:
        raise ProfileError("mcp_servers must not be empty")

    raw_endpoint_ids = _strings(data["allowed_endpoint_ids"], "allowed_endpoint_ids")
    if not raw_endpoint_ids:
        raise ProfileError("allowed_endpoint_ids must not be empty")
    if any(not KEBAB_ID.fullmatch(item) for item in raw_endpoint_ids):
        raise ProfileError("allowed_endpoint_ids entries must be lowercase kebab-case")

    raw_global_source = _string(
        data["global_instruction_source"],
        "global_instruction_source",
    )
    global_source = PurePosixPath(raw_global_source)
    raw_claude_user_source = _string(
        data["claude_user_instruction_source"],
        "claude_user_instruction_source",
    )
    claude_user_source = PurePosixPath(raw_claude_user_source)
    for source, location in (
        (global_source, "global_instruction_source"),
        (claude_user_source, "claude_user_instruction_source"),
    ):
        if source.is_absolute() or ".." in source.parts:
            raise ProfileError(f"{location} must be repository-relative")

    return ManagedPolicy(
        schema_version=schema_version,
        policy_id=PolicyId(raw_policy_id),
        version=ModelVersion(raw_version),
        canonical_repository=CanonicalRepository(raw_repository),
        default_branch=BranchName(raw_branch),
        governance_model=governance,
        allowed_surfaces=_enum_values(
            data["allowed_surfaces"],
            "allowed_surfaces",
            AgentSurface,
        ),
        allowed_endpoint_classes=_enum_values(
            data["allowed_endpoint_classes"],
            "allowed_endpoint_classes",
            EndpointClass,
        ),
        allowed_endpoint_ids=tuple(EndpointId(item) for item in raw_endpoint_ids),
        blocked_by=tuple(
            BlockerReference(item)
            for item in _strings(data["blocked_by"], "blocked_by")
        ),
        managed_configuration=_boolean(
            data["managed_configuration"],
            "managed_configuration",
        ),
        global_instruction_source=global_source,
        claude_user_instruction_source=claude_user_source,
        codex=_parse_codex(data["codex"]),
        claude=_parse_claude(data["claude"]),
        mcp_servers=tuple(servers),
    )


def parse_endpoint_enrollment(value: object) -> EndpointEnrollment:
    """Convert untrusted JSON into one attributable endpoint enrollment."""

    data = _object(value, "endpoint")
    _keys(
        data,
        frozenset(
            {
                "schema_version",
                "endpoint_id",
                "endpoint_class",
                "platform",
                "principal",
                "local_user",
                "credential_pointer",
                "credential_environment_variable",
                "user_home",
                "allowed_surfaces",
                "policy_id",
            }
        ),
        "endpoint",
    )
    schema_version = _integer(data["schema_version"], "schema_version")
    if schema_version != 1:
        raise ProfileError(f"schema_version must be 1, found {schema_version!r}")
    raw_endpoint_id = _string(data["endpoint_id"], "endpoint_id")
    raw_principal = _string(data["principal"], "principal")
    raw_local_user = _string(data["local_user"], "local_user")
    raw_pointer = _string(data["credential_pointer"], "credential_pointer")
    raw_environment_variable = _string(
        data["credential_environment_variable"],
        "credential_environment_variable",
    )
    raw_user_home = _string(data["user_home"], "user_home")
    raw_policy_id = _string(data["policy_id"], "policy_id")
    if not KEBAB_ID.fullmatch(raw_endpoint_id):
        raise ProfileError("endpoint_id must be lowercase kebab-case")
    if not PRINCIPAL.fullmatch(raw_principal):
        raise ProfileError("principal must be an attributable agent:<slug>")
    if not LOCAL_USERNAME.fullmatch(raw_local_user):
        raise ProfileError("local_user is invalid")
    if not POINTER.fullmatch(raw_pointer):
        raise ProfileError(
            "credential_pointer must be an OpenBao field or absolute file pointer"
        )
    if not ENVIRONMENT_VARIABLE.fullmatch(raw_environment_variable):
        raise ProfileError("credential_environment_variable is invalid")
    user_home = Path(raw_user_home)
    if not user_home.is_absolute() or ".." in user_home.parts:
        raise ProfileError("user_home must be an absolute normalized path")
    if not KEBAB_ID.fullmatch(raw_policy_id):
        raise ProfileError("policy_id must be lowercase kebab-case")

    raw_class = _string(data["endpoint_class"], "endpoint_class")
    raw_platform = _string(data["platform"], "platform")
    try:
        endpoint_class = EndpointClass(raw_class)
    except ValueError as error:
        raise ProfileError(
            "endpoint_class is not admitted by schema version 1"
        ) from error
    try:
        platform = EndpointPlatform(raw_platform)
    except ValueError as error:
        raise ProfileError("platform must be macos or linux") from error
    return EndpointEnrollment(
        schema_version=schema_version,
        endpoint_id=EndpointId(raw_endpoint_id),
        endpoint_class=endpoint_class,
        platform=platform,
        principal=PrincipalReference(raw_principal),
        local_user=LocalUsername(raw_local_user),
        credential_pointer=CredentialPointer(raw_pointer),
        credential_environment_variable=EnvironmentVariable(raw_environment_variable),
        user_home=user_home,
        allowed_surfaces=_enum_values(
            data["allowed_surfaces"],
            "allowed_surfaces",
            AgentSurface,
        ),
        policy_id=PolicyId(raw_policy_id),
    )


def _load_json(path: Path, label: str) -> object:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProfileError(f"{label} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"{label} is not valid JSON at line {error.lineno}, column {error.colno}"
        ) from error
    return raw


def load_managed_policy(path: Path) -> ManagedPolicy:
    """Load one strict managed policy."""

    return parse_managed_policy(_load_json(path, "managed policy"))


def load_endpoint_enrollment(path: Path) -> EndpointEnrollment:
    """Load one strict endpoint enrollment."""

    return parse_endpoint_enrollment(_load_json(path, "endpoint enrollment"))


def _toml_strings(values: Sequence[str]) -> str:
    return "[" + ", ".join(json.dumps(value) for value in values) + "]"


def _instruction_source(root: Path, source: PurePosixPath) -> str:
    resolved_root = root.resolve()
    path = resolved_root.joinpath(*source.parts)
    if (
        not path.is_file()
        or path.is_symlink()
        or not path.resolve().is_relative_to(resolved_root)
    ):
        raise ProfileError(f"managed instruction source is unavailable: {source}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def _managed_instructions(
    policy: ManagedPolicy,
    root: Path,
    source: PurePosixPath,
) -> str:
    return (
        "<!-- Generated by dotmac-agent from an accepted managed policy; "
        "do not edit. -->\n"
        f"<!-- Policy: {policy.policy_id}@{policy.version}; source: {source} -->\n\n"
        f"{_instruction_source(root, source)}"
    )


def _codex_requirements(policy: ManagedPolicy) -> str:
    codex = policy.codex
    lines = [
        f"allowed_approval_policies = {_toml_strings(codex.allowed_approval_policies)}",
        f"allowed_web_search_modes = {_toml_strings(codex.allowed_web_search_modes)}",
        f"default_permissions = {json.dumps(codex.default_permission_profile.value)}",
        f"allow_managed_hooks_only = {str(codex.allow_managed_hooks_only).lower()}",
        f"allow_remote_control = {str(not codex.disable_remote_control).lower()}",
        "",
        "[allowed_permission_profiles]",
    ]
    lines.extend(
        f"{json.dumps(profile.value)} = true"
        for profile in codex.allowed_permission_profiles
    )
    lines.extend(
        [
            "",
            "[features]",
            f"computer_use = {str(not codex.disable_computer_use).lower()}",
        ]
    )
    for server in policy.mcp_servers:
        lines.extend(
            [
                "",
                f"[mcp_servers.{server.name}]",
                f"identity = {{ url = {json.dumps(server.url)} }}",
            ]
        )
    return "\n".join(lines) + "\n"


def _codex_managed_config(
    policy: ManagedPolicy,
    endpoint: EndpointEnrollment,
) -> str:
    lines: list[str] = []
    for server in policy.mcp_servers:
        lines.extend(
            [
                f"[mcp_servers.{server.name}]",
                f"url = {json.dumps(server.url)}",
                "bearer_token_env_var = "
                f"{json.dumps(endpoint.credential_environment_variable)}",
                "",
            ]
        )
    return "\n".join(lines)


def _claude_settings(policy: ManagedPolicy) -> str:
    claude = policy.claude
    allowed_mcp = [{"serverUrl": str(server.url)} for server in policy.mcp_servers]
    payload: dict[str, object] = {
        "autoUpdatesChannel": claude.update_channel.value,
        "allowManagedHooksOnly": claude.allow_managed_hooks_only,
        "allowManagedMcpServersOnly": claude.allow_managed_mcp_servers_only,
        "allowManagedPermissionRulesOnly": (claude.allow_managed_permission_rules_only),
        "allowedMcpServers": allowed_mcp,
        "sandbox": {
            "enabled": claude.sandbox_enabled,
            "failIfUnavailable": claude.sandbox_fail_if_unavailable,
            "allowUnsandboxedCommands": (claude.sandbox_allow_unsandboxed_commands),
        },
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _claude_managed_mcp(
    policy: ManagedPolicy,
    endpoint: EndpointEnrollment,
) -> str:
    payload: dict[str, object] = {
        "mcpServers": {
            server.name: {
                "type": "http",
                "url": str(server.url),
                "headers": {
                    "Authorization": "Bearer "
                    f"${{{endpoint.credential_environment_variable}}}"
                },
            }
            for server in policy.mcp_servers
        }
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _artifact(
    kind: ArtifactKind,
    target: PurePosixPath,
    stage_path: PurePosixPath,
    content: str,
    *,
    ownership: ArtifactOwnership = ArtifactOwnership.ROOT,
    mode: FileMode = DEFAULT_ARTIFACT_MODE,
) -> ManagedArtifact:
    return ManagedArtifact(
        kind=kind,
        target=target,
        stage_path=stage_path,
        sha256=Sha256Digest(hashlib.sha256(content.encode("utf-8")).hexdigest()),
        content=content,
        ownership=ownership,
        mode=mode,
    )


def _targets(
    platform: EndpointPlatform,
    user_home: Path,
) -> tuple[PurePosixPath, PurePosixPath, PurePosixPath]:
    if platform is EndpointPlatform.MACOS:
        claude_root = PurePosixPath("/Library/Application Support/ClaudeCode")
    else:
        claude_root = PurePosixPath("/etc/claude-code")
    return (
        PurePosixPath("/etc/codex"),
        PurePosixPath(user_home.as_posix()) / ".codex",
        claude_root,
    )


def _deployment_diagnostics(
    policy: ManagedPolicy,
    endpoint: EndpointEnrollment,
    root: Path,
    identity: RepositoryIdentity | None,
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if endpoint.policy_id != policy.policy_id:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_POLICY_MISMATCH,
                "endpoint enrollment references a different managed policy",
            )
        )
    if endpoint.endpoint_class not in policy.allowed_endpoint_classes:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_ENDPOINT_CLASS_NOT_AUTHORIZED,
                "endpoint class is not authorized by the managed policy",
            )
        )
    if endpoint.endpoint_id not in policy.allowed_endpoint_ids:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_ENDPOINT_NOT_AUTHORIZED,
                "endpoint ID is not authorized by the managed policy",
            )
        )
    unauthorized = tuple(
        surface
        for surface in endpoint.allowed_surfaces
        if surface not in policy.allowed_surfaces
    )
    if unauthorized:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_SURFACE_NOT_AUTHORIZED,
                "endpoint requests surfaces not authorized by the managed policy: "
                + ", ".join(surface.value for surface in unauthorized),
            )
        )
    if policy.governance_model.status is not GovernanceStatus.ACCEPTED:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_GOVERNANCE_NOT_ACCEPTED,
                "activation requires an Accepted governance source",
            )
        )
    if policy.blocked_by:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_BLOCKERS_OPEN,
                "activation is blocked by checked-in open decisions",
            )
        )
    if not policy.managed_configuration:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_MANAGED_CONFIGURATION_DISABLED,
                "activation requires managed_configuration=true",
            )
        )
    source_path = root.joinpath(*policy.governance_model.source.parts)
    if not source_path.is_file():
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_GOVERNANCE_SOURCE_MISSING,
                "managed policy governance source does not exist",
                policy.governance_model.source,
            )
        )
    else:
        status_match = ADR_STATUS.search(source_path.read_text(encoding="utf-8"))
        observed_status = (
            GovernanceStatus(status_match.group(1).lower())
            if status_match is not None
            else None
        )
        if observed_status is not policy.governance_model.status:
            diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    DiagnosticCode.DEPLOYMENT_GOVERNANCE_STATUS_MISMATCH,
                    "managed policy governance status does not match its Git source",
                    policy.governance_model.source,
                )
            )
    if identity is None:
        diagnostics.append(
            Diagnostic(
                Severity.ERROR,
                DiagnosticCode.DEPLOYMENT_SOURCE_IDENTITY_UNAVAILABLE,
                "managed deployment source must be an attributable Git repository",
            )
        )
    else:
        if identity.canonical_repository != policy.canonical_repository:
            diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    DiagnosticCode.DEPLOYMENT_SOURCE_IDENTITY_MISMATCH,
                    "managed deployment source repository does not match policy",
                )
            )
        if identity.branch != policy.default_branch:
            diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    DiagnosticCode.DEPLOYMENT_SOURCE_BRANCH_MISMATCH,
                    "managed deployment source must be on the canonical default branch",
                )
            )
        if identity.dirty:
            diagnostics.append(
                Diagnostic(
                    Severity.ERROR,
                    DiagnosticCode.DEPLOYMENT_SOURCE_DIRTY,
                    "managed deployment source must have a clean working tree",
                )
            )
    return tuple(diagnostics)


def plan_deployment(
    policy: ManagedPolicy,
    endpoint: EndpointEnrollment,
    root: Path,
) -> DeploymentPlan:
    """Render a content-addressed candidate plan without touching system paths."""

    codex_system, codex_user, claude_system = _targets(
        endpoint.platform,
        endpoint.user_home,
    )
    try:
        identity = detect_repository_identity(root)
    except ValueError:
        identity = None
    source_revision = identity.revision if identity is not None else None
    source_dirty = identity.dirty if identity is not None else None
    source_branch = identity.branch if identity is not None else None
    instructions = _managed_instructions(
        policy,
        root,
        policy.global_instruction_source,
    )
    claude_user_instructions = _managed_instructions(
        policy,
        root,
        policy.claude_user_instruction_source,
    )
    artifacts: list[ManagedArtifact] = []
    if AgentSurface.CODEX in endpoint.allowed_surfaces:
        artifacts.extend(
            (
                _artifact(
                    ArtifactKind.CODEX_GLOBAL_INSTRUCTIONS,
                    codex_user / "AGENTS.md",
                    PurePosixPath("payload/codex/AGENTS.md"),
                    instructions,
                    ownership=ArtifactOwnership.ENDPOINT_USER,
                    mode=FileMode(0o600),
                ),
                _artifact(
                    ArtifactKind.CODEX_REQUIREMENTS,
                    codex_system / "requirements.toml",
                    PurePosixPath("payload/codex/requirements.toml"),
                    _codex_requirements(policy),
                ),
                _artifact(
                    ArtifactKind.CODEX_MANAGED_CONFIG,
                    codex_system / "managed_config.toml",
                    PurePosixPath("payload/codex/managed_config.toml"),
                    _codex_managed_config(policy, endpoint),
                ),
            )
        )
    if AgentSurface.CLAUDE_CODE in endpoint.allowed_surfaces:
        artifacts.extend(
            (
                _artifact(
                    ArtifactKind.CLAUDE_MANAGED_INSTRUCTIONS,
                    claude_system / "CLAUDE.md",
                    PurePosixPath("payload/claude/CLAUDE.md"),
                    instructions,
                ),
                _artifact(
                    ArtifactKind.CLAUDE_MANAGED_SETTINGS,
                    claude_system / "managed-settings.json",
                    PurePosixPath("payload/claude/managed-settings.json"),
                    _claude_settings(policy),
                ),
                _artifact(
                    ArtifactKind.CLAUDE_MANAGED_MCP,
                    claude_system / "managed-mcp.json",
                    PurePosixPath("payload/claude/managed-mcp.json"),
                    _claude_managed_mcp(policy, endpoint),
                ),
                _artifact(
                    ArtifactKind.CLAUDE_USER_INSTRUCTIONS,
                    PurePosixPath(endpoint.user_home.as_posix())
                    / ".claude"
                    / "CLAUDE.md",
                    PurePosixPath("payload/claude/user-CLAUDE.md"),
                    claude_user_instructions,
                    ownership=ArtifactOwnership.ENDPOINT_USER,
                    mode=FileMode(0o600),
                ),
            )
        )

    attestation = DeploymentAttestation(
        endpoint_id=endpoint.endpoint_id,
        endpoint_class=endpoint.endpoint_class,
        platform=endpoint.platform,
        principal=endpoint.principal,
        local_user=endpoint.local_user,
        user_home=endpoint.user_home,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        source_revision=source_revision,
        source_dirty=source_dirty,
        source_branch=source_branch,
        artifacts=tuple(artifacts),
    )
    attestation_content = (
        json.dumps(attestation.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    artifacts.append(
        _artifact(
            ArtifactKind.ATTESTATION,
            PurePosixPath("attestation.json"),
            PurePosixPath("attestation.json"),
            attestation_content,
            mode=FileMode(0o600),
        )
    )
    return DeploymentPlan(
        endpoint=endpoint,
        policy=policy,
        source_revision=source_revision,
        source_dirty=source_dirty,
        source_branch=source_branch,
        artifacts=tuple(artifacts),
        diagnostics=_deployment_diagnostics(policy, endpoint, root, identity),
    )


def deploy_endpoint(
    policy_path: Path,
    endpoint_path: Path,
    root: Path,
    output_root: Path,
    *,
    mode: DeploymentMode,
) -> DeploymentResult:
    """Stage a bundle, or fail closed when direct activation is requested."""

    policy = load_managed_policy(policy_path)
    endpoint = load_endpoint_enrollment(endpoint_path)
    plan = plan_deployment(policy, endpoint, root)
    if mode is DeploymentMode.APPLY:
        refusal = Diagnostic(
            Severity.ERROR,
            DiagnosticCode.DEPLOYMENT_APPLY_NOT_IMPLEMENTED,
            "direct system activation is not implemented; stage, review, and "
            "deliver through an explicitly authorized endpoint-management owner",
        )
        return DeploymentResult(
            mode=mode,
            output_root=output_root,
            plan=replace(plan, diagnostics=plan.diagnostics + (refusal,)),
            created=(),
            unchanged=(),
            refused=(),
        )

    resolved_output = output_root.resolve()
    created: list[PurePosixPath] = []
    unchanged: list[PurePosixPath] = []
    refused: list[PurePosixPath] = []
    for artifact in plan.artifacts:
        target = resolved_output.joinpath(*artifact.stage_path.parts)
        resolved_parent = target.parent.resolve()
        if not resolved_parent.is_relative_to(resolved_output) or target.is_symlink():
            refused.append(artifact.stage_path)
        elif not target.exists():
            created.append(artifact.stage_path)
        elif target.is_file() and target.read_bytes() == artifact.content.encode(
            "utf-8"
        ):
            unchanged.append(artifact.stage_path)
        else:
            refused.append(artifact.stage_path)

    if refused:
        conflict = Diagnostic(
            Severity.ERROR,
            DiagnosticCode.DEPLOYMENT_STAGE_CONFLICT,
            "staging refuses to overwrite an existing artifact with different content",
        )
        return DeploymentResult(
            mode=mode,
            output_root=resolved_output,
            plan=replace(plan, diagnostics=plan.diagnostics + (conflict,)),
            created=(),
            unchanged=tuple(unchanged),
            refused=tuple(refused),
        )

    for artifact in plan.artifacts:
        target = resolved_output.joinpath(*artifact.stage_path.parts)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(artifact.content, encoding="utf-8")

    return DeploymentResult(
        mode=mode,
        output_root=resolved_output,
        plan=plan,
        created=tuple(created),
        unchanged=tuple(unchanged),
        refused=(),
    )


def _mapped_endpoint_path(target_root: Path, target: PurePosixPath) -> Path:
    if not target.is_absolute():
        raise ValueError(f"endpoint artifact target must be absolute: {target}")
    return target_root.joinpath(*target.parts[1:])


def reconcile_endpoint(
    policy_path: Path,
    endpoint_path: Path,
    root: Path,
    target_root: Path,
) -> ReconciliationReport:
    """Compare endpoint files with desired bytes without changing endpoint state."""

    policy = load_managed_policy(policy_path)
    endpoint = load_endpoint_enrollment(endpoint_path)
    plan = plan_deployment(policy, endpoint, root)
    resolved_root = target_root.resolve()
    observations: list[ArtifactObservation] = []
    for artifact in plan.artifacts:
        if artifact.kind is ArtifactKind.ATTESTATION:
            continue
        target = _mapped_endpoint_path(resolved_root, artifact.target)
        observed_hash: Sha256Digest | None = None
        state = ArtifactState.MISSING
        if target.is_file() and not target.is_symlink():
            if target.resolve().is_relative_to(resolved_root):
                observed_hash = Sha256Digest(
                    hashlib.sha256(target.read_bytes()).hexdigest()
                )
                state = (
                    ArtifactState.MATCHED
                    if observed_hash == artifact.sha256
                    else ArtifactState.DRIFTED
                )
            else:
                state = ArtifactState.DRIFTED
        elif target.exists() or target.is_symlink():
            state = ArtifactState.DRIFTED
        observations.append(
            ArtifactObservation(
                kind=artifact.kind,
                target=artifact.target,
                expected_sha256=artifact.sha256,
                observed_sha256=observed_hash,
                state=state,
            )
        )

    environment_state = (
        DependencyState.AVAILABLE
        if os.environ.get(str(endpoint.credential_environment_variable))
        else DependencyState.MISSING
    )

    return ReconciliationReport(
        plan=plan,
        target_root=resolved_root,
        observations=tuple(observations),
        credential_environment=environment_state,
    )
