"""Backup-backed local activation and rollback for an accepted pilot endpoint."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import pwd
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path, PurePosixPath

from .contracts import (
    ActivationAction,
    ActivationEntry,
    ActivationManifest,
    ActivationManifestStatus,
    ArtifactKind,
    ArtifactOwnership,
    DeploymentPlan,
    Diagnostic,
    DiagnosticCode,
    EndpointId,
    EndpointPlatform,
    FileMode,
    GitRevision,
    LocalActivationResult,
    ManagedArtifact,
    ModelVersion,
    PolicyId,
    RollbackResult,
    Severity,
    Sha256Digest,
)
from .managed import (
    _mapped_endpoint_path,
    load_endpoint_enrollment,
    load_managed_policy,
    plan_deployment,
)
from .profile import ProfileError

SHA256_LENGTH = 64
DEFAULT_PARENT_MODE = FileMode(0o755)


def _sha256(content: bytes) -> Sha256Digest:
    return Sha256Digest(hashlib.sha256(content).hexdigest())


def _error(code: DiagnosticCode, message: str) -> Diagnostic:
    return Diagnostic(Severity.ERROR, code, message)


def _atomic_write(
    path: Path,
    content: bytes,
    *,
    mode: FileMode,
    uid: int,
    gid: int,
    parent_mode: FileMode = DEFAULT_PARENT_MODE,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=int(parent_mode))
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".dotmac-agent-",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, int(mode))
        os.chown(temporary, uid, gid)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _manifest_bytes(manifest: ActivationManifest) -> bytes:
    return (json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def _activation_result(
    *,
    plan: DeploymentPlan,
    backup_root: Path,
    diagnostics: tuple[Diagnostic, ...],
) -> LocalActivationResult:
    return LocalActivationResult(
        plan=plan,
        backup_root=backup_root,
        manifest=None,
        created=(),
        replaced=(),
        unchanged=(),
        refused=(),
        diagnostics=diagnostics,
    )


def _actual_endpoint_identity(
    endpoint_platform: EndpointPlatform,
    local_user: str,
    user_home: Path,
) -> tuple[int, int, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    observed_system = platform.system()
    observed_platform = {
        "Darwin": EndpointPlatform.MACOS,
        "Linux": EndpointPlatform.LINUX,
    }.get(observed_system)
    if observed_platform is not endpoint_platform:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_PLATFORM_MISMATCH,
                "local platform does not match endpoint enrollment",
            )
        )
    try:
        account = pwd.getpwnam(local_user)
    except KeyError:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_LOCAL_USER_MISMATCH,
                "enrolled local user does not exist",
            )
        )
        return os.getuid(), os.getgid(), tuple(diagnostics)
    if Path(account.pw_dir) != user_home:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_LOCAL_USER_MISMATCH,
                "enrolled local user home does not match the operating system",
            )
        )
    return account.pw_uid, account.pw_gid, tuple(diagnostics)


def _owner_ids(
    artifact: ManagedArtifact,
    *,
    actual_root: bool,
    endpoint_uid: int,
    endpoint_gid: int,
) -> tuple[int, int]:
    if not actual_root:
        return os.getuid(), os.getgid()
    if artifact.ownership is ArtifactOwnership.ENDPOINT_USER:
        return endpoint_uid, endpoint_gid
    return 0, 0


def activate_local(
    policy_path: Path,
    endpoint_path: Path,
    root: Path,
    backup_root: Path,
    *,
    migrate_existing: bool,
    target_root: Path = Path("/"),
) -> LocalActivationResult:
    """Install one accepted endpoint plan after complete preflight and backup."""

    policy = load_managed_policy(policy_path)
    endpoint = load_endpoint_enrollment(endpoint_path)
    plan = plan_deployment(policy, endpoint, root)
    resolved_target_root = target_root.resolve()
    backup_root_is_symlink = backup_root.is_symlink()
    resolved_backup_root = backup_root.resolve()
    diagnostics: list[Diagnostic] = list(plan.diagnostics)
    if not plan.activation_permitted or plan.source_revision is None:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_PLAN_NOT_PERMITTED,
                "local activation requires every managed deployment gate to pass",
            )
        )
        return _activation_result(
            plan=plan,
            backup_root=resolved_backup_root,
            diagnostics=tuple(diagnostics),
        )

    actual_root = resolved_target_root == Path("/")
    endpoint_uid = os.getuid()
    endpoint_gid = os.getgid()
    if actual_root:
        if os.geteuid() != 0:
            diagnostics.append(
                _error(
                    DiagnosticCode.ACTIVATION_PRIVILEGE_REQUIRED,
                    "local activation of system paths requires root privileges",
                )
            )
        endpoint_uid, endpoint_gid, identity_diagnostics = _actual_endpoint_identity(
            endpoint.platform,
            str(endpoint.local_user),
            endpoint.user_home,
        )
        diagnostics.extend(identity_diagnostics)
    if diagnostics:
        return _activation_result(
            plan=plan,
            backup_root=resolved_backup_root,
            diagnostics=tuple(diagnostics),
        )

    artifacts = tuple(
        artifact
        for artifact in plan.artifacts
        if artifact.kind is not ArtifactKind.ATTESTATION
    )
    entries: list[ActivationEntry] = []
    refused: list[PurePosixPath] = []
    for artifact in artifacts:
        target = _mapped_endpoint_path(resolved_target_root, artifact.target)
        resolved_parent = target.parent.resolve()
        if (
            not resolved_parent.is_relative_to(resolved_target_root)
            or target.is_symlink()
            or (target.exists() and not target.is_file())
        ):
            refused.append(artifact.target)
            continue
        if not target.exists():
            entries.append(
                ActivationEntry(
                    kind=artifact.kind,
                    target=artifact.target,
                    action=ActivationAction.CREATED,
                    desired_sha256=artifact.sha256,
                    backup_path=None,
                    prior_sha256=None,
                    prior_mode=None,
                    prior_uid=None,
                    prior_gid=None,
                )
            )
            continue
        current = target.read_bytes()
        current_hash = _sha256(current)
        stat = target.stat()
        if current_hash == artifact.sha256:
            action = ActivationAction.UNCHANGED
            backup_path = None
        elif migrate_existing:
            action = ActivationAction.REPLACED
            backup_path = PurePosixPath("files").joinpath(*artifact.target.parts[1:])
        else:
            refused.append(artifact.target)
            continue
        entries.append(
            ActivationEntry(
                kind=artifact.kind,
                target=artifact.target,
                action=action,
                desired_sha256=artifact.sha256,
                backup_path=backup_path,
                prior_sha256=current_hash,
                prior_mode=FileMode(stat.st_mode & 0o7777),
                prior_uid=stat.st_uid,
                prior_gid=stat.st_gid,
            )
        )

    if refused:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_TARGET_CONFLICT,
                "activation refused unsafe or unapproved existing targets",
            )
        )
        return LocalActivationResult(
            plan=plan,
            backup_root=resolved_backup_root,
            manifest=None,
            created=(),
            replaced=(),
            unchanged=tuple(
                entry.target
                for entry in entries
                if entry.action is ActivationAction.UNCHANGED
            ),
            refused=tuple(refused),
            diagnostics=tuple(diagnostics),
        )

    if (
        backup_root_is_symlink
        or (resolved_backup_root.exists() and not resolved_backup_root.is_dir())
        or (resolved_backup_root.is_dir() and any(resolved_backup_root.iterdir()))
    ):
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_BACKUP_CONFLICT,
                "backup root must be an absent or empty non-symlink directory",
            )
        )
        return _activation_result(
            plan=plan,
            backup_root=resolved_backup_root,
            diagnostics=tuple(diagnostics),
        )

    resolved_backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(resolved_backup_root, 0o700)
    for entry in entries:
        if entry.backup_path is None:
            continue
        target = _mapped_endpoint_path(resolved_target_root, entry.target)
        backup = resolved_backup_root.joinpath(*entry.backup_path.parts)
        _atomic_write(
            backup,
            target.read_bytes(),
            mode=FileMode(0o600),
            uid=os.getuid(),
            gid=os.getgid(),
            parent_mode=FileMode(0o700),
        )

    manifest = ActivationManifest(
        schema_version=1,
        status=ActivationManifestStatus.PREPARED,
        endpoint_id=endpoint.endpoint_id,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        source_revision=GitRevision(plan.source_revision),
        target_root=resolved_target_root,
        entries=tuple(entries),
    )
    manifest_path = resolved_backup_root / "manifest.json"
    _atomic_write(
        manifest_path,
        _manifest_bytes(manifest),
        mode=FileMode(0o600),
        uid=os.getuid(),
        gid=os.getgid(),
        parent_mode=FileMode(0o700),
    )

    artifact_by_target = {artifact.target: artifact for artifact in artifacts}
    applied_entries: list[ActivationEntry] = []
    try:
        for entry in entries:
            if entry.action is ActivationAction.UNCHANGED:
                continue
            artifact = artifact_by_target[entry.target]
            target = _mapped_endpoint_path(resolved_target_root, entry.target)
            uid, gid = _owner_ids(
                artifact,
                actual_root=actual_root,
                endpoint_uid=endpoint_uid,
                endpoint_gid=endpoint_gid,
            )
            _atomic_write(
                target,
                artifact.content.encode("utf-8"),
                mode=artifact.mode,
                uid=uid,
                gid=gid,
            )
            applied_entries.append(entry)
    except OSError as error:
        for applied in reversed(applied_entries):
            target = _mapped_endpoint_path(resolved_target_root, applied.target)
            if applied.action is ActivationAction.CREATED:
                if (
                    target.is_file()
                    and _sha256(target.read_bytes()) == applied.desired_sha256
                ):
                    target.unlink()
            elif (
                applied.action is ActivationAction.REPLACED
                and applied.backup_path is not None
                and applied.prior_mode is not None
                and applied.prior_uid is not None
                and applied.prior_gid is not None
            ):
                backup = resolved_backup_root.joinpath(*applied.backup_path.parts)
                _atomic_write(
                    target,
                    backup.read_bytes(),
                    mode=applied.prior_mode,
                    uid=applied.prior_uid,
                    gid=applied.prior_gid,
                )
        rolled_back_manifest = replace(
            manifest,
            status=ActivationManifestStatus.ROLLED_BACK,
        )
        _atomic_write(
            manifest_path,
            _manifest_bytes(rolled_back_manifest),
            mode=FileMode(0o600),
            uid=os.getuid(),
            gid=os.getgid(),
            parent_mode=FileMode(0o700),
        )
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_APPLY_FAILED,
                f"activation write failed and was rolled back: {type(error).__name__}",
            )
        )
        return LocalActivationResult(
            plan=plan,
            backup_root=resolved_backup_root,
            manifest=rolled_back_manifest,
            created=(),
            replaced=(),
            unchanged=tuple(
                entry.target
                for entry in entries
                if entry.action is ActivationAction.UNCHANGED
            ),
            refused=tuple(
                entry.target for entry in entries if entry not in applied_entries
            ),
            diagnostics=tuple(diagnostics),
        )

    applied_manifest = replace(manifest, status=ActivationManifestStatus.APPLIED)
    _atomic_write(
        manifest_path,
        _manifest_bytes(applied_manifest),
        mode=FileMode(0o600),
        uid=os.getuid(),
        gid=os.getgid(),
        parent_mode=FileMode(0o700),
    )
    return LocalActivationResult(
        plan=plan,
        backup_root=resolved_backup_root,
        manifest=applied_manifest,
        created=tuple(
            entry.target
            for entry in entries
            if entry.action is ActivationAction.CREATED
        ),
        replaced=tuple(
            entry.target
            for entry in entries
            if entry.action is ActivationAction.REPLACED
        ),
        unchanged=tuple(
            entry.target
            for entry in entries
            if entry.action is ActivationAction.UNCHANGED
        ),
        refused=(),
        diagnostics=(),
    )


def _object(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ProfileError(f"{location} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, object],
    required: frozenset[str],
    location: str,
) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required)
    if missing or unknown:
        raise ProfileError(
            f"{location} keys invalid; missing={missing!r} unknown={unknown!r}"
        )


def _required_string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProfileError(f"{location} must be a non-empty string")
    return value


def _optional_integer(value: object, location: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProfileError(f"{location} must be a non-negative integer or null")
    return value


def _optional_hash(value: object, location: str) -> Sha256Digest | None:
    if value is None:
        return None
    raw = _required_string(value, location)
    if len(raw) != SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in raw
    ):
        raise ProfileError(f"{location} must be a lowercase SHA-256 digest")
    return Sha256Digest(raw)


def _parse_entry(value: object, index: int) -> ActivationEntry:
    location = f"entries[{index}]"
    data = _object(value, location)
    _exact_keys(
        data,
        frozenset(
            {
                "kind",
                "target",
                "action",
                "desired_sha256",
                "backup_path",
                "prior_sha256",
                "prior_mode",
                "prior_uid",
                "prior_gid",
            }
        ),
        location,
    )
    try:
        kind = ArtifactKind(_required_string(data["kind"], f"{location}.kind"))
        action = ActivationAction(
            _required_string(data["action"], f"{location}.action")
        )
    except ValueError as error:
        raise ProfileError(f"{location} has an invalid enum value") from error
    target = PurePosixPath(_required_string(data["target"], f"{location}.target"))
    if not target.is_absolute() or ".." in target.parts:
        raise ProfileError(f"{location}.target must be absolute and normalized")
    raw_backup = data["backup_path"]
    backup_path = (
        PurePosixPath(_required_string(raw_backup, f"{location}.backup_path"))
        if raw_backup is not None
        else None
    )
    if backup_path is not None and (
        backup_path.is_absolute()
        or ".." in backup_path.parts
        or not backup_path.parts
        or backup_path.parts[0] != "files"
    ):
        raise ProfileError(f"{location}.backup_path must be a normalized files/ path")
    desired = _optional_hash(data["desired_sha256"], f"{location}.desired_sha256")
    if desired is None:
        raise ProfileError(f"{location}.desired_sha256 is required")
    prior_mode = _optional_integer(data["prior_mode"], f"{location}.prior_mode")
    entry = ActivationEntry(
        kind=kind,
        target=target,
        action=action,
        desired_sha256=desired,
        backup_path=backup_path,
        prior_sha256=_optional_hash(data["prior_sha256"], f"{location}.prior_sha256"),
        prior_mode=FileMode(prior_mode) if prior_mode is not None else None,
        prior_uid=_optional_integer(data["prior_uid"], f"{location}.prior_uid"),
        prior_gid=_optional_integer(data["prior_gid"], f"{location}.prior_gid"),
    )
    prior_values = (
        entry.prior_sha256,
        entry.prior_mode,
        entry.prior_uid,
        entry.prior_gid,
    )
    if entry.kind is ArtifactKind.ATTESTATION:
        raise ProfileError(f"{location}.kind cannot be attestation")
    if entry.action is ActivationAction.CREATED and (
        entry.backup_path is not None
        or any(value is not None for value in prior_values)
    ):
        raise ProfileError(f"{location} created action must not have prior state")
    if entry.action is ActivationAction.REPLACED and (
        entry.backup_path is None or any(value is None for value in prior_values)
    ):
        raise ProfileError(f"{location} replaced action requires complete prior state")
    if entry.action is ActivationAction.UNCHANGED and (
        entry.backup_path is not None or any(value is None for value in prior_values)
    ):
        raise ProfileError(
            f"{location} unchanged action requires prior metadata without backup"
        )
    return entry


def load_activation_manifest(path: Path) -> ActivationManifest:
    """Load one strict rollback manifest without reading backup file content."""

    raw: object = json.loads(path.read_text(encoding="utf-8"))
    data = _object(raw, "manifest")
    _exact_keys(
        data,
        frozenset(
            {
                "schema_version",
                "status",
                "endpoint_id",
                "policy_id",
                "policy_version",
                "source_revision",
                "target_root",
                "entries",
            }
        ),
        "manifest",
    )
    if data["schema_version"] != 1:
        raise ProfileError("manifest.schema_version must be 1")
    try:
        status = ActivationManifestStatus(
            _required_string(data["status"], "manifest.status")
        )
    except ValueError as error:
        raise ProfileError("manifest.status is invalid") from error
    raw_entries = data["entries"]
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        raise ProfileError("manifest.entries must be an array")
    entries = tuple(
        _parse_entry(value, index) for index, value in enumerate(raw_entries)
    )
    if not entries:
        raise ProfileError("manifest.entries must not be empty")
    if len({entry.target for entry in entries}) != len(entries):
        raise ProfileError("manifest.entries targets must be unique")
    revision = _required_string(data["source_revision"], "manifest.source_revision")
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise ProfileError("manifest.source_revision must be a full Git commit")
    target_root = Path(_required_string(data["target_root"], "manifest.target_root"))
    if not target_root.is_absolute() or ".." in target_root.parts:
        raise ProfileError("manifest.target_root must be absolute and normalized")
    return ActivationManifest(
        schema_version=1,
        status=status,
        endpoint_id=EndpointId(
            _required_string(data["endpoint_id"], "manifest.endpoint_id")
        ),
        policy_id=PolicyId(_required_string(data["policy_id"], "manifest.policy_id")),
        policy_version=ModelVersion(
            _required_string(data["policy_version"], "manifest.policy_version")
        ),
        source_revision=GitRevision(revision),
        target_root=target_root.resolve(),
        entries=entries,
    )


def rollback_local(manifest_path: Path) -> RollbackResult:
    """Restore only unchanged activated targets named by one strict manifest."""

    manifest_is_symlink = manifest_path.is_symlink()
    resolved_manifest = manifest_path.resolve()
    diagnostics: list[Diagnostic] = []
    try:
        if manifest_is_symlink:
            raise ProfileError("rollback manifest must not be a symlink")
        manifest = load_activation_manifest(resolved_manifest)
    except (OSError, json.JSONDecodeError, ProfileError) as error:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_MANIFEST_INVALID,
                f"rollback manifest is invalid: {type(error).__name__}",
            )
        )
        return RollbackResult(
            manifest_path=resolved_manifest,
            restored=(),
            removed=(),
            unchanged=(),
            refused=(),
            diagnostics=tuple(diagnostics),
        )
    if manifest.status is not ActivationManifestStatus.APPLIED:
        diagnostics.append(
            _error(
                DiagnosticCode.ACTIVATION_MANIFEST_INVALID,
                "rollback requires an applied manifest",
            )
        )
        return RollbackResult(
            manifest_path=resolved_manifest,
            restored=(),
            removed=(),
            unchanged=(),
            refused=(),
            diagnostics=tuple(diagnostics),
        )

    backup_root = resolved_manifest.parent
    refused: list[PurePosixPath] = []
    for entry in manifest.entries:
        target = _mapped_endpoint_path(manifest.target_root, entry.target)
        if (
            not target.is_file()
            or target.is_symlink()
            or _sha256(target.read_bytes()) != entry.desired_sha256
        ):
            refused.append(entry.target)
            continue
        if entry.action is ActivationAction.REPLACED:
            if entry.backup_path is None or entry.prior_sha256 is None:
                refused.append(entry.target)
                continue
            backup = backup_root.joinpath(*entry.backup_path.parts)
            if (
                not backup.is_file()
                or backup.is_symlink()
                or not backup.resolve().is_relative_to(backup_root)
                or _sha256(backup.read_bytes()) != entry.prior_sha256
            ):
                refused.append(entry.target)
    if refused:
        diagnostics.append(
            _error(
                DiagnosticCode.ROLLBACK_TARGET_DRIFT,
                "rollback refused because target or backup identity drifted",
            )
        )
        return RollbackResult(
            manifest_path=resolved_manifest,
            restored=(),
            removed=(),
            unchanged=(),
            refused=tuple(refused),
            diagnostics=tuple(diagnostics),
        )

    restored: list[PurePosixPath] = []
    removed: list[PurePosixPath] = []
    unchanged: list[PurePosixPath] = []
    for entry in reversed(manifest.entries):
        target = _mapped_endpoint_path(manifest.target_root, entry.target)
        if entry.action is ActivationAction.CREATED:
            target.unlink()
            removed.append(entry.target)
        elif entry.action is ActivationAction.REPLACED:
            if (
                entry.backup_path is None
                or entry.prior_mode is None
                or entry.prior_uid is None
                or entry.prior_gid is None
            ):
                raise RuntimeError("validated replacement lacks rollback metadata")
            backup = backup_root.joinpath(*entry.backup_path.parts)
            _atomic_write(
                target,
                backup.read_bytes(),
                mode=entry.prior_mode,
                uid=entry.prior_uid,
                gid=entry.prior_gid,
            )
            restored.append(entry.target)
        else:
            unchanged.append(entry.target)

    rolled_back = replace(manifest, status=ActivationManifestStatus.ROLLED_BACK)
    _atomic_write(
        resolved_manifest,
        _manifest_bytes(rolled_back),
        mode=FileMode(0o600),
        uid=os.getuid(),
        gid=os.getgid(),
        parent_mode=FileMode(0o700),
    )
    return RollbackResult(
        manifest_path=resolved_manifest,
        restored=tuple(restored),
        removed=tuple(removed),
        unchanged=tuple(unchanged),
        refused=(),
        diagnostics=(),
    )
