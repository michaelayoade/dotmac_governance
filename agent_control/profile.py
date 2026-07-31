"""Strict JSON adapter for the versioned agent profile contract."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from .contracts import (
    AgentProfile,
    AgentSurface,
    BlockerReference,
    BranchName,
    CanonicalRepository,
    EndpointClass,
    GovernanceModelRef,
    GovernanceStatus,
    InstructionContract,
    ModelVersion,
    ProfileId,
    RenderMode,
    RolloutContract,
    RolloutMode,
    ValidationCommand,
)

PROFILE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BRANCH_NAME = re.compile(r"^[A-Za-z0-9._/-]+$")
MODEL_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.-]+)?$")
HTTPS_REPOSITORY = re.compile(r"^https://[^/\s]+/[^/\s]+/[^/\s]+$")


class ProfileError(ValueError):
    """Raised when untrusted profile JSON does not satisfy the typed contract."""


def _expect_object(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ProfileError(f"{location} must be an object")
    return value


def _expect_exact_keys(
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


def _expect_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProfileError(f"{location} must be a non-empty string")
    if "\x00" in value:
        raise ProfileError(f"{location} must not contain a null byte")
    return value.strip()


def _expect_boolean(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileError(f"{location} must be a boolean")
    return value


def _expect_integer(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileError(f"{location} must be an integer")
    return value


def _expect_strings(value: object, location: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProfileError(f"{location} must be an array of strings")
    result = tuple(
        _expect_string(item, f"{location}[{index}]") for index, item in enumerate(value)
    )
    if len(result) != len(set(result)):
        raise ProfileError(f"{location} must not contain duplicates")
    return result


def _expect_relative_path(value: object, location: str) -> PurePosixPath:
    raw = _expect_string(value, location)
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw in {".", ""}:
        raise ProfileError(f"{location} must be a repository-relative path")
    return path


def _expect_relative_paths(
    value: object,
    location: str,
) -> tuple[PurePosixPath, ...]:
    strings = _expect_strings(value, location)
    return tuple(
        _expect_relative_path(item, f"{location}[{index}]")
        for index, item in enumerate(strings)
    )


def _parse_governance_model(value: object) -> GovernanceModelRef:
    location = "governance_model"
    data = _expect_object(value, location)
    required = frozenset({"version", "source", "status"})
    _expect_exact_keys(data, required, location)

    version = _expect_string(data["version"], f"{location}.version")
    if not MODEL_VERSION.fullmatch(version):
        raise ProfileError(
            f"{location}.version must be semantic version syntax, found {version!r}"
        )
    raw_status = _expect_string(data["status"], f"{location}.status")
    try:
        status = GovernanceStatus(raw_status)
    except ValueError as error:
        raise ProfileError(
            f"{location}.status must be proposed or accepted, found {raw_status!r}"
        ) from error

    return GovernanceModelRef(
        version=ModelVersion(version),
        source=_expect_relative_path(data["source"], f"{location}.source"),
        status=status,
    )


def _parse_instructions(value: object) -> InstructionContract:
    location = "instructions"
    data = _expect_object(value, location)
    required = frozenset(
        {
            "agents_path",
            "claude_path",
            "claude_import",
            "render_mode",
            "max_combined_bytes",
            "warn_combined_bytes",
            "required_agents_markers",
            "required_claude_markers",
            "authoritative_sources",
            "claude_additions",
        }
    )
    _expect_exact_keys(data, required, location)

    raw_render_mode = _expect_string(data["render_mode"], f"{location}.render_mode")
    try:
        render_mode = RenderMode(raw_render_mode)
    except ValueError as error:
        raise ProfileError(
            f"{location}.render_mode must be validate or managed, "
            f"found {raw_render_mode!r}"
        ) from error

    maximum = _expect_integer(
        data["max_combined_bytes"],
        f"{location}.max_combined_bytes",
    )
    warning = _expect_integer(
        data["warn_combined_bytes"],
        f"{location}.warn_combined_bytes",
    )
    if maximum <= 0:
        raise ProfileError(f"{location}.max_combined_bytes must be positive")
    if warning <= 0 or warning > maximum:
        raise ProfileError(
            f"{location}.warn_combined_bytes must be positive and no greater "
            "than max_combined_bytes"
        )

    agents_markers = _expect_strings(
        data["required_agents_markers"],
        f"{location}.required_agents_markers",
    )
    claude_markers = _expect_strings(
        data["required_claude_markers"],
        f"{location}.required_claude_markers",
    )
    authority_sources = _expect_relative_paths(
        data["authoritative_sources"],
        f"{location}.authoritative_sources",
    )
    if not agents_markers:
        raise ProfileError(f"{location}.required_agents_markers must not be empty")
    if not claude_markers:
        raise ProfileError(f"{location}.required_claude_markers must not be empty")
    if not authority_sources:
        raise ProfileError(f"{location}.authoritative_sources must not be empty")

    return InstructionContract(
        agents_path=_expect_relative_path(
            data["agents_path"],
            f"{location}.agents_path",
        ),
        claude_path=_expect_relative_path(
            data["claude_path"],
            f"{location}.claude_path",
        ),
        claude_import=_expect_string(
            data["claude_import"],
            f"{location}.claude_import",
        ),
        render_mode=render_mode,
        max_combined_bytes=maximum,
        warn_combined_bytes=warning,
        required_agents_markers=agents_markers,
        required_claude_markers=claude_markers,
        authoritative_sources=authority_sources,
        claude_additions=_expect_strings(
            data["claude_additions"],
            f"{location}.claude_additions",
        ),
    )


def _parse_rollout(value: object) -> RolloutContract:
    location = "rollout"
    data = _expect_object(value, location)
    required = frozenset(
        {
            "mode",
            "managed_configuration",
            "authorized_endpoint_classes",
            "blocked_by",
        }
    )
    _expect_exact_keys(data, required, location)

    raw_mode = _expect_string(data["mode"], f"{location}.mode")
    try:
        mode = RolloutMode(raw_mode)
    except ValueError as error:
        raise ProfileError(
            f"{location}.mode must be pilot or managed, found {raw_mode!r}"
        ) from error

    raw_endpoint_classes = _expect_strings(
        data["authorized_endpoint_classes"],
        f"{location}.authorized_endpoint_classes",
    )
    if not raw_endpoint_classes:
        raise ProfileError(f"{location}.authorized_endpoint_classes must not be empty")
    endpoint_classes: list[EndpointClass] = []
    for raw_endpoint_class in raw_endpoint_classes:
        try:
            endpoint_classes.append(EndpointClass(raw_endpoint_class))
        except ValueError as error:
            raise ProfileError(
                f"{location}.authorized_endpoint_classes entries must be "
                "developer-workstation or ci-runner, "
                f"found {raw_endpoint_class!r}"
            ) from error

    return RolloutContract(
        mode=mode,
        managed_configuration=_expect_boolean(
            data["managed_configuration"],
            f"{location}.managed_configuration",
        ),
        authorized_endpoint_classes=tuple(endpoint_classes),
        blocked_by=tuple(
            BlockerReference(blocker)
            for blocker in _expect_strings(
                data["blocked_by"],
                f"{location}.blocked_by",
            )
        ),
    )


def parse_profile(value: object) -> AgentProfile:
    """Convert untrusted JSON data into the immutable domain contract."""

    data = _expect_object(value, "profile")
    required = frozenset(
        {
            "schema_version",
            "profile_id",
            "repository_name",
            "summary",
            "canonical_repository",
            "default_branch",
            "governance_model",
            "instructions",
            "validation_commands",
            "allowed_surfaces",
            "rollout",
        }
    )
    _expect_exact_keys(data, required, "profile")

    schema_version = _expect_integer(data["schema_version"], "schema_version")
    if schema_version != 1:
        raise ProfileError(f"schema_version must be 1, found {schema_version!r}")

    profile_id = _expect_string(data["profile_id"], "profile_id")
    if not PROFILE_ID.fullmatch(profile_id):
        raise ProfileError(
            f"profile_id must be lowercase kebab-case, found {profile_id!r}"
        )

    canonical_repository = _expect_string(
        data["canonical_repository"],
        "canonical_repository",
    ).removesuffix(".git")
    if not HTTPS_REPOSITORY.fullmatch(canonical_repository):
        raise ProfileError(
            "canonical_repository must be an HTTPS repository URL with owner/name"
        )

    default_branch = _expect_string(data["default_branch"], "default_branch")
    if not BRANCH_NAME.fullmatch(default_branch):
        raise ProfileError(f"default_branch is invalid: {default_branch!r}")

    raw_surfaces = _expect_strings(data["allowed_surfaces"], "allowed_surfaces")
    surfaces: list[AgentSurface] = []
    for raw_surface in raw_surfaces:
        try:
            surfaces.append(AgentSurface(raw_surface))
        except ValueError as error:
            raise ProfileError(
                "allowed_surfaces entries must be codex or claude-code, "
                f"found {raw_surface!r}"
            ) from error
    if not surfaces:
        raise ProfileError("allowed_surfaces must not be empty")

    validation_commands = _expect_strings(
        data["validation_commands"],
        "validation_commands",
    )
    if not validation_commands:
        raise ProfileError("validation_commands must not be empty")
    if any("\n" in command or "\r" in command for command in validation_commands):
        raise ProfileError("validation_commands entries must be one line each")

    profile = AgentProfile(
        schema_version=schema_version,
        profile_id=ProfileId(profile_id),
        repository_name=_expect_string(data["repository_name"], "repository_name"),
        summary=_expect_string(data["summary"], "summary"),
        canonical_repository=CanonicalRepository(canonical_repository),
        default_branch=BranchName(default_branch),
        governance_model=_parse_governance_model(data["governance_model"]),
        instructions=_parse_instructions(data["instructions"]),
        validation_commands=tuple(
            ValidationCommand(command) for command in validation_commands
        ),
        allowed_surfaces=tuple(surfaces),
        rollout=_parse_rollout(data["rollout"]),
    )
    if (
        AgentSurface.CLAUDE_CODE in profile.allowed_surfaces
        and not profile.instructions.claude_additions
    ):
        raise ProfileError(
            "instructions.claude_additions must not be empty when Claude Code "
            "is an allowed surface"
        )
    return profile


def load_profile(path: Path) -> AgentProfile:
    """Read and validate one JSON profile without accepting partial data."""

    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ProfileError(f"profile does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ProfileError(
            f"profile is not valid JSON at line {error.lineno}, column {error.colno}"
        ) from error
    return parse_profile(raw)
