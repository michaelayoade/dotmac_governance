"""Strict JSON adapter for a repository engineering-standards profile."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from .contracts import (
    AuthorityContract,
    AuthorityId,
    BranchName,
    CanonicalRepository,
    EnforcementMode,
    GovernanceModelRef,
    GovernanceStatus,
    ProfileId,
    PythonSymbol,
    RepositoryContract,
    ResourceId,
    StandardsProfile,
    SurfaceId,
    TypedContractSurface,
)

SLUG = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
HTTPS_REPOSITORY = re.compile(r"^https://[^/\s]+/[^/\s]+/[^/\s]+$")
PYTHON_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")


class ProfileError(ValueError):
    """Raised when untrusted profile JSON violates the closed contract."""


def _object(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ProfileError(f"{location} must be an object")
    return value


def _keys(data: Mapping[str, object], required: frozenset[str], location: str) -> None:
    missing = sorted(required - data.keys())
    unknown = sorted(data.keys() - required)
    if missing:
        raise ProfileError(f"{location} missing keys: {', '.join(missing)}")
    if unknown:
        raise ProfileError(f"{location} has unknown keys: {', '.join(unknown)}")


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ProfileError(f"{location} must be a non-empty safe string")
    return value.strip()


def _bool(value: object, location: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileError(f"{location} must be a boolean")
    return value


def _sequence(value: object, location: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProfileError(f"{location} must be an array")
    return value


def _slug(value: object, location: str) -> str:
    raw = _string(value, location)
    if not SLUG.fullmatch(raw):
        raise ProfileError(f"{location} must be a lower-case stable identifier")
    return raw


def _path(value: object, location: str) -> PurePosixPath:
    raw = _string(value, location)
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or raw == ".":
        raise ProfileError(f"{location} must be a repository-relative path")
    return path


def _paths(value: object, location: str) -> tuple[PurePosixPath, ...]:
    result = tuple(
        _path(item, f"{location}[{index}]")
        for index, item in enumerate(_sequence(value, location))
    )
    if len(result) != len(set(result)):
        raise ProfileError(f"{location} must not contain duplicates")
    return result


def _repository(value: object) -> RepositoryContract:
    data = _object(value, "repository")
    _keys(data, frozenset({"canonical_url", "default_branch"}), "repository")
    url = _string(data["canonical_url"], "repository.canonical_url")
    branch = _string(data["default_branch"], "repository.default_branch")
    if not HTTPS_REPOSITORY.fullmatch(url):
        raise ProfileError("repository.canonical_url must be a canonical HTTPS URL")
    if not BRANCH.fullmatch(branch):
        raise ProfileError("repository.default_branch has invalid syntax")
    return RepositoryContract(
        canonical_url=CanonicalRepository(url.removesuffix(".git")),
        default_branch=BranchName(branch),
    )


def _governance(value: object) -> GovernanceModelRef:
    data = _object(value, "governance_model")
    _keys(data, frozenset({"source", "status"}), "governance_model")
    raw = _string(data["status"], "governance_model.status")
    try:
        status = GovernanceStatus(raw)
    except ValueError as error:
        raise ProfileError(
            "governance_model.status must be proposed or accepted"
        ) from error
    return GovernanceModelRef(
        source=_path(data["source"], "governance_model.source"), status=status
    )


def _authority(value: object, index: int) -> AuthorityContract:
    location = f"authorities[{index}]"
    data = _object(value, location)
    required = frozenset(
        {
            "authority_id",
            "subject",
            "protected_resources",
            "owner_component",
            "owner_implementation",
            "decision_interface",
            "canonical_writer_paths",
            "adapter_paths",
            "drift_test_paths",
        }
    )
    _keys(data, required, location)
    interface = _string(data["decision_interface"], f"{location}.decision_interface")
    if not PYTHON_SYMBOL.fullmatch(interface):
        raise ProfileError(f"{location}.decision_interface must be a dotted symbol")
    resources = tuple(
        ResourceId(_slug(item, f"{location}.protected_resources[{item_index}]"))
        for item_index, item in enumerate(
            _sequence(data["protected_resources"], f"{location}.protected_resources")
        )
    )
    writers = _paths(
        data["canonical_writer_paths"], f"{location}.canonical_writer_paths"
    )
    tests = _paths(data["drift_test_paths"], f"{location}.drift_test_paths")
    if not resources or len(resources) != len(set(resources)):
        raise ProfileError(
            f"{location}.protected_resources must be non-empty and unique"
        )
    if not writers or not tests:
        raise ProfileError(f"{location} needs canonical writers and drift tests")
    return AuthorityContract(
        authority_id=AuthorityId(
            _slug(data["authority_id"], f"{location}.authority_id")
        ),
        subject=_string(data["subject"], f"{location}.subject"),
        protected_resources=resources,
        owner_component=_slug(data["owner_component"], f"{location}.owner_component"),
        owner_implementation=_path(
            data["owner_implementation"], f"{location}.owner_implementation"
        ),
        decision_interface=PythonSymbol(interface),
        canonical_writer_paths=writers,
        adapter_paths=_paths(data["adapter_paths"], f"{location}.adapter_paths"),
        drift_test_paths=tests,
    )


def _surface(value: object, index: int) -> TypedContractSurface:
    location = f"typed_contract_surfaces[{index}]"
    data = _object(value, location)
    _keys(
        data,
        frozenset(
            {
                "surface_id",
                "paths",
                "require_public_annotations",
                "forbid_any",
                "require_immutable_records",
            }
        ),
        location,
    )
    paths = _paths(data["paths"], f"{location}.paths")
    if not paths:
        raise ProfileError(f"{location}.paths must not be empty")
    return TypedContractSurface(
        surface_id=SurfaceId(_slug(data["surface_id"], f"{location}.surface_id")),
        paths=paths,
        require_public_annotations=_bool(
            data["require_public_annotations"], f"{location}.require_public_annotations"
        ),
        forbid_any=_bool(data["forbid_any"], f"{location}.forbid_any"),
        require_immutable_records=_bool(
            data["require_immutable_records"], f"{location}.require_immutable_records"
        ),
    )


def parse_profile(value: object) -> StandardsProfile:
    """Parse untrusted JSON-compatible data into an immutable profile."""
    data = _object(value, "profile")
    _keys(
        data,
        frozenset(
            {
                "schema_version",
                "profile_id",
                "repository",
                "governance_model",
                "enforcement_mode",
                "authorities",
                "typed_contract_surfaces",
            }
        ),
        "profile",
    )
    version = data["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise ProfileError("schema_version must be integer 1")
    raw_mode = _string(data["enforcement_mode"], "enforcement_mode")
    try:
        mode = EnforcementMode(raw_mode)
    except ValueError as error:
        raise ProfileError("enforcement_mode must be candidate or required") from error
    governance = _governance(data["governance_model"])
    if (
        mode is EnforcementMode.REQUIRED
        and governance.status is not GovernanceStatus.ACCEPTED
    ):
        raise ProfileError("required enforcement needs an accepted governance source")
    authorities = tuple(
        _authority(item, index)
        for index, item in enumerate(_sequence(data["authorities"], "authorities"))
    )
    surfaces = tuple(
        _surface(item, index)
        for index, item in enumerate(
            _sequence(data["typed_contract_surfaces"], "typed_contract_surfaces")
        )
    )
    if not authorities or not surfaces:
        raise ProfileError("authorities and typed_contract_surfaces must not be empty")
    if len({item.authority_id for item in authorities}) != len(authorities):
        raise ProfileError("authority_id values must be unique")
    if len({item.surface_id for item in surfaces}) != len(surfaces):
        raise ProfileError("surface_id values must be unique")
    return StandardsProfile(
        schema_version=1,
        profile_id=ProfileId(_slug(data["profile_id"], "profile_id")),
        repository=_repository(data["repository"]),
        governance_model=governance,
        enforcement_mode=mode,
        authorities=authorities,
        typed_contract_surfaces=surfaces,
    )


def load_profile(path: Path) -> StandardsProfile:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError(f"cannot read profile {path}: {error}") from error
    return parse_profile(value)
