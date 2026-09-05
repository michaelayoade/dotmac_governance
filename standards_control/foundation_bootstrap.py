"""Report-only validation of the Foundation candidate bootstrap evidence.

This module is deliberately not part of ``standards_control.engine``.  It
checks the bridge evidence for one immutable candidate artifact; it does not
load, interpret, canonicalize, or authorize an ApplicationFoundationProfile.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Final

REPOSITORY: Final = "https://github.com/michaelayoade/dotmac_starter_mt"
SOURCE_COMMIT: Final = "753a004e7f8dbab034d5d6ca565c680d931a5309"
PACKAGE_PATH: Final = "packages/dotmac-deployment-foundation"
GIT_TREE: Final = "1d3994b29e80e64fdaf9c0d69df6cd90c437cd7f"
CONTRACT_SOURCE_PATH: Final = (
    "packages/dotmac-deployment-foundation/src/"
    "dotmac_deployment_foundation/application_profile.py"
)
WHEEL_MEMBER: Final = "dotmac_deployment_foundation/application_profile.py"
CONTRACT_SHA256: Final = (
    "1cafd60da5d3ee0b2a99fe9a57138a5b4ccc64548d5c7510cf7fb1d80593bf8b"
)
CONTRACT_SIZE: Final = 47043
CANONICAL_SYMBOLS: Final = (
    "ApplicationFoundationProfile",
    "canonical_profile_bytes",
    "profile_digest",
    "verify_profile_against_candidate",
    "require_profile_readback",
)
RUN_ID: Final = 33920058598
RUN_ATTEMPT: Final = 1
CANDIDATE_ARTIFACT_ID: Final = 9954731961
CANDIDATE_ARTIFACT_NAME: Final = "dotmac-deployment-foundation-candidate"
CANDIDATE_ARCHIVE_DIGEST: Final = (
    "sha256:d037f819358e52444d5b086127d060ed5923dd90f2fc14201132b6706d1c8d54"
)
WHEEL_FILENAME: Final = "dotmac_deployment_foundation-0.4.0a1-py3-none-any.whl"
WHEEL_SHA256: Final = "c8522496afa682fabf0b209ee00e8676431f6e034743fbffc6a63aa65d493740"
WHEEL_SIZE: Final = 449612
CANDIDATE_VERSION: Final = "0.4.0a1"
CANDIDATE_ARCHIVE_SIZE: Final = 850732
SDIST_FILENAME: Final = "dotmac_deployment_foundation-0.4.0a1.tar.gz"
SDIST_SHA256: Final = "905dc0de722679633115098a086230835029762b5d44ac7428331e002f6476c8"
SDIST_SIZE: Final = 406201
RECEIPT_ARTIFACT_ID: Final = 9954732889
RECEIPT_ARTIFACT_NAME: Final = "dotmac-deployment-foundation-candidate-receipt"
RECEIPT_ARCHIVE_DIGEST: Final = (
    "sha256:5b8e316b4821150e0329c692d8e87d7154a04e872e28b4db6206e8c7438ac4b0"
)
RECEIPT_ARCHIVE_SIZE: Final = 597
RECEIPT_FILENAME: Final = "candidate-receipt.json"
RECEIPT_SHA256: Final = (
    "5c1a6d8c78eaf599492acd757e7bc32d61d47b09d8b256a572f2dc681082bb11"
)
RECEIPT_FILE_SIZE: Final = 789
RECEIPT_RETENTION_DAYS: Final = 90
EVIDENCE_EXPIRES_AT: Final = "2026-12-03T21:13:17Z"
ISSUE_URL: Final = "https://github.com/michaelayoade/dotmac_starter_mt/issues/642"


class FoundationBootstrapError(ValueError):
    """A malformed, altered, unsafe, or expired bootstrap evidence record."""


@dataclass(frozen=True)
class FoundationContractBootstrap:
    schema_version: str
    status: str
    intended_approver: str
    repository: str
    source_commit: str
    run_source_commit: str
    package_path: str
    git_tree: str
    contract_source_path: str
    wheel_member: str
    contract_sha256: str
    contract_size: int
    canonical_symbols: tuple[str, ...]
    run_id: int
    run_attempt: int
    candidate_artifact_id: int
    candidate_artifact_name: str
    candidate_archive_digest: str
    wheel_filename: str
    wheel_sha256: str
    wheel_size: int
    candidate_version: str
    candidate_archive_size: int
    sdist_filename: str
    sdist_sha256: str
    sdist_size: int
    receipt_artifact_id: int
    receipt_artifact_name: str
    receipt_archive_digest: str
    receipt_archive_size: int
    receipt_filename: str
    receipt_sha256: str
    receipt_file_size: int
    receipt_retention_days: int
    evidence_expires_at: str
    lifecycle_owner_action: str
    retirement_trigger: str
    claims: tuple[tuple[str, bool], ...]


_EXPECTED_KEYS = frozenset(FoundationContractBootstrap.__dataclass_fields__)
_EXPECTED_CLAIMS = (
    ("released", False),
    ("published", False),
    ("installed", False),
    ("runtime_adoption_authorized", False),
)


def _object(value: object, where: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise FoundationBootstrapError(f"{where} must be an object")
    return value


def _string(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise FoundationBootstrapError(f"{where} must be a non-empty string")
    return value


def _sha(value: object, where: str, prefixed: bool = False) -> str:
    result = _string(value, where)
    if prefixed and not result.startswith("sha256:"):
        raise FoundationBootstrapError(f"{where} must start with sha256:")
    raw = result.removeprefix("sha256:") if prefixed else result
    if len(raw) != 64 or any(char not in "0123456789abcdef" for char in raw):
        raise FoundationBootstrapError(f"{where} must be a lowercase SHA-256 digest")
    return result


def _parse_claims(value: object) -> tuple[tuple[str, bool], ...]:
    data = _object(value, "claims")
    if set(data) != {name for name, _ in _EXPECTED_CLAIMS}:
        raise FoundationBootstrapError("claims has unknown or missing keys")
    if any(type(data[name]) is not bool for name, _ in _EXPECTED_CLAIMS):
        raise FoundationBootstrapError("claims must state every required false claim")
    result = tuple((name, data[name]) for name, _ in _EXPECTED_CLAIMS)
    if result != _EXPECTED_CLAIMS:
        raise FoundationBootstrapError("claims must state every required false claim")
    return tuple((name, item) for name, item in result if isinstance(item, bool))


def _positive_int(value: object, where: str) -> int:
    if type(value) is not int or value <= 0:
        raise FoundationBootstrapError(f"{where} must be a positive integer")
    return value


def load_foundation_bootstrap(
    value: Mapping[str, object],
) -> FoundationContractBootstrap:
    """Strictly load the bridge evidence; no Foundation profile is read."""
    if set(value) != _EXPECTED_KEYS:
        raise FoundationBootstrapError("record has unknown or missing fields")
    symbols = value["canonical_symbols"]
    if not isinstance(symbols, list) or tuple(symbols) != CANONICAL_SYMBOLS:
        raise FoundationBootstrapError("canonical_symbols do not match the contract")
    ints = ("run_id", "run_attempt", "candidate_artifact_id", "receipt_artifact_id")
    numbers = {key: _positive_int(value[key], key) for key in ints}
    record = FoundationContractBootstrap(
        schema_version=_string(value["schema_version"], "schema_version"),
        status=_string(value["status"], "status"),
        intended_approver=_string(value["intended_approver"], "intended_approver"),
        repository=_string(value["repository"], "repository"),
        source_commit=_string(value["source_commit"], "source_commit"),
        run_source_commit=_string(value["run_source_commit"], "run_source_commit"),
        package_path=_string(value["package_path"], "package_path"),
        git_tree=_string(value["git_tree"], "git_tree"),
        contract_source_path=_string(
            value["contract_source_path"], "contract_source_path"
        ),
        wheel_member=_string(value["wheel_member"], "wheel_member"),
        contract_sha256=_sha(value["contract_sha256"], "contract_sha256"),
        contract_size=_positive_int(value["contract_size"], "contract_size"),
        canonical_symbols=CANONICAL_SYMBOLS,
        run_id=numbers["run_id"],
        run_attempt=numbers["run_attempt"],
        candidate_artifact_id=numbers["candidate_artifact_id"],
        candidate_artifact_name=_string(
            value["candidate_artifact_name"], "candidate_artifact_name"
        ),
        candidate_archive_digest=_sha(
            value["candidate_archive_digest"], "candidate_archive_digest", True
        ),
        wheel_filename=_string(value["wheel_filename"], "wheel_filename"),
        wheel_sha256=_sha(value["wheel_sha256"], "wheel_sha256"),
        wheel_size=_positive_int(value["wheel_size"], "wheel_size"),
        candidate_version=_string(value["candidate_version"], "candidate_version"),
        candidate_archive_size=_positive_int(
            value["candidate_archive_size"], "candidate_archive_size"
        ),
        sdist_filename=_string(value["sdist_filename"], "sdist_filename"),
        sdist_sha256=_sha(value["sdist_sha256"], "sdist_sha256"),
        sdist_size=_positive_int(value["sdist_size"], "sdist_size"),
        receipt_artifact_id=numbers["receipt_artifact_id"],
        receipt_artifact_name=_string(
            value["receipt_artifact_name"], "receipt_artifact_name"
        ),
        receipt_archive_digest=_sha(
            value["receipt_archive_digest"], "receipt_archive_digest", True
        ),
        receipt_archive_size=_positive_int(
            value["receipt_archive_size"], "receipt_archive_size"
        ),
        receipt_filename=_string(value["receipt_filename"], "receipt_filename"),
        receipt_sha256=_sha(value["receipt_sha256"], "receipt_sha256"),
        receipt_file_size=_positive_int(
            value["receipt_file_size"], "receipt_file_size"
        ),
        receipt_retention_days=_positive_int(
            value["receipt_retention_days"], "receipt_retention_days"
        ),
        evidence_expires_at=_string(
            value["evidence_expires_at"], "evidence_expires_at"
        ),
        lifecycle_owner_action=_string(
            value["lifecycle_owner_action"], "lifecycle_owner_action"
        ),
        retirement_trigger=_string(value["retirement_trigger"], "retirement_trigger"),
        claims=_parse_claims(value["claims"]),
    )
    expected = FoundationContractBootstrap(
        "FoundationContractBootstrap.v1",
        "proposed",
        "Michael Ayoade",
        REPOSITORY,
        SOURCE_COMMIT,
        SOURCE_COMMIT,
        PACKAGE_PATH,
        GIT_TREE,
        CONTRACT_SOURCE_PATH,
        WHEEL_MEMBER,
        CONTRACT_SHA256,
        CONTRACT_SIZE,
        CANONICAL_SYMBOLS,
        RUN_ID,
        RUN_ATTEMPT,
        CANDIDATE_ARTIFACT_ID,
        CANDIDATE_ARTIFACT_NAME,
        CANDIDATE_ARCHIVE_DIGEST,
        WHEEL_FILENAME,
        WHEEL_SHA256,
        WHEEL_SIZE,
        CANDIDATE_VERSION,
        CANDIDATE_ARCHIVE_SIZE,
        SDIST_FILENAME,
        SDIST_SHA256,
        SDIST_SIZE,
        RECEIPT_ARTIFACT_ID,
        RECEIPT_ARTIFACT_NAME,
        RECEIPT_ARCHIVE_DIGEST,
        RECEIPT_ARCHIVE_SIZE,
        RECEIPT_FILENAME,
        RECEIPT_SHA256,
        RECEIPT_FILE_SIZE,
        RECEIPT_RETENTION_DAYS,
        EVIDENCE_EXPIRES_AT,
        ISSUE_URL,
        "a valid successor Foundation release containing the canonical contract",
        _EXPECTED_CLAIMS,
    )
    if record != expected:
        raise FoundationBootstrapError(
            "record evidence is not the immutable bootstrap evidence"
        )
    return record


def load_foundation_bootstrap_json(path: Path) -> FoundationContractBootstrap:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FoundationBootstrapError("cannot read bootstrap record") from error
    return load_foundation_bootstrap(_object(value, "record"))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _verify_wheel_bytes(
    record: FoundationContractBootstrap, wheel_bytes: bytes, *, as_of: datetime
) -> None:
    """Check only the named contract member and its named definitions."""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise FoundationBootstrapError("as_of must be explicitly timezone-aware")
    expiry = datetime.fromisoformat(record.evidence_expires_at.replace("Z", "+00:00"))
    if as_of.astimezone(UTC) >= expiry:
        raise FoundationBootstrapError("bootstrap evidence has expired")
    try:
        if hashlib.sha256(wheel_bytes).hexdigest() != record.wheel_sha256:
            raise FoundationBootstrapError("wheel SHA-256 does not match evidence")
        with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as wheel:
            names = wheel.namelist()
            if any(
                not name
                or "\x00" in name
                or name.startswith(("/", "\\"))
                or "\\" in name
                or ".." in PurePosixPath(name).parts
                for name in names
            ):
                raise FoundationBootstrapError("wheel contains an unsafe ZIP member")
            if record.wheel_member not in names:
                raise FoundationBootstrapError("wheel is missing the contract member")
            contract_info = wheel.getinfo(record.wheel_member)
            if contract_info.file_size != record.contract_size:
                raise FoundationBootstrapError(
                    "contract member size does not match evidence"
                )
            source = wheel.read(contract_info)
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise FoundationBootstrapError("wheel is unreadable") from error
    if hashlib.sha256(source).hexdigest() != record.contract_sha256:
        raise FoundationBootstrapError(
            "contract member SHA-256 does not match evidence"
        )
    try:
        tree = ast.parse(source.decode("utf-8"), filename=record.wheel_member)
    except (UnicodeDecodeError, SyntaxError) as error:
        raise FoundationBootstrapError("contract member is not valid Python") from error
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = set(record.canonical_symbols) - defined
    if missing:
        raise FoundationBootstrapError(
            f"contract member is missing named symbols: {', '.join(sorted(missing))}"
        )


def _verify_materialized_wheel(
    record: FoundationContractBootstrap, wheel_path: Path, *, as_of: datetime
) -> None:
    if wheel_path.name != record.wheel_filename:
        raise FoundationBootstrapError("wheel filename does not match evidence")
    try:
        wheel_bytes = wheel_path.read_bytes()
    except OSError as error:
        raise FoundationBootstrapError("wheel is unreadable") from error
    _verify_wheel_bytes(record, wheel_bytes, as_of=as_of)


def verify_materialized_wheel(wheel_path: Path) -> None:
    """Verify the fixed checked-in candidate wheel using the real UTC clock."""
    record = load_foundation_bootstrap_json(
        Path(__file__).parents[1] / "policies/foundation-profile-bootstrap.json"
    )
    try:
        if wheel_path.stat().st_size != record.wheel_size:
            raise FoundationBootstrapError("wheel size does not match evidence")
    except OSError as error:
        raise FoundationBootstrapError("wheel is unreadable") from error
    _verify_materialized_wheel(record, wheel_path, as_of=_utc_now())


def _safe_members(archive: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, ...]:
    infos = tuple(archive.infolist())
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise FoundationBootstrapError("archive contains duplicate ZIP members")
    if any(
        not name
        or "\x00" in name
        or name.startswith(("/", "\\"))
        or "\\" in name
        or ".." in PurePosixPath(name).parts
        for name in names
    ):
        raise FoundationBootstrapError("archive contains an unsafe ZIP member")
    return infos


def _verify_receipt(record: FoundationContractBootstrap, receipt: bytes) -> None:
    if len(receipt) != record.receipt_file_size:
        raise FoundationBootstrapError("receipt file size does not match evidence")
    if hashlib.sha256(receipt).hexdigest() != record.receipt_sha256:
        raise FoundationBootstrapError("receipt file SHA-256 does not match evidence")
    try:
        value = json.loads(receipt)
    except json.JSONDecodeError as error:
        raise FoundationBootstrapError("receipt is not valid JSON") from error
    expected = {
        "artifact_id": str(record.candidate_artifact_id),
        "artifact_size_bytes": record.candidate_archive_size,
        "expires_at": record.evidence_expires_at,
        "facility": "dotmac-deployment-foundation",
        "filename": record.wheel_filename,
        "published": False,
        "repository": "michaelayoade/dotmac_starter_mt",
        "retention_requested_days": record.receipt_retention_days,
        "run_id": str(record.run_id),
        "schema": "CandidateArtifact.v1",
        "sdist": {
            "filename": record.sdist_filename,
            "sha256": record.sdist_sha256,
            "size_bytes": record.sdist_size,
        },
        "sha256": record.wheel_sha256,
        "size_bytes": record.wheel_size,
        "source_sha": record.source_commit,
        "tagged": False,
        "version": record.candidate_version,
    }
    if value != expected:
        raise FoundationBootstrapError(
            "receipt shape or artifact linkage does not match evidence"
        )


def _verify_materialized_evidence_bytes(
    record: FoundationContractBootstrap,
    candidate_bytes: bytes,
    receipt_bytes: bytes,
    *,
    as_of: datetime,
) -> None:
    """Check supplied archive bytes; the public wrapper supplies fixed evidence."""
    if len(candidate_bytes) != record.candidate_archive_size:
        raise FoundationBootstrapError("candidate archive size does not match evidence")
    if len(receipt_bytes) != record.receipt_archive_size:
        raise FoundationBootstrapError("receipt archive size does not match evidence")
    if hashlib.sha256(
        candidate_bytes
    ).hexdigest() != record.candidate_archive_digest.removeprefix("sha256:"):
        raise FoundationBootstrapError(
            "candidate archive digest does not match evidence"
        )
    if hashlib.sha256(
        receipt_bytes
    ).hexdigest() != record.receipt_archive_digest.removeprefix("sha256:"):
        raise FoundationBootstrapError("receipt archive digest does not match evidence")
    try:
        with zipfile.ZipFile(io.BytesIO(candidate_bytes)) as candidate:
            infos = _safe_members(candidate)
            expected_names = {record.wheel_filename, record.sdist_filename}
            if {info.filename for info in infos} != expected_names:
                raise FoundationBootstrapError(
                    "candidate archive members do not match evidence"
                )
            wheel_info = candidate.getinfo(record.wheel_filename)
            sdist_info = candidate.getinfo(record.sdist_filename)
            if wheel_info.file_size != record.wheel_size:
                raise FoundationBootstrapError("wheel size does not match evidence")
            if sdist_info.file_size != record.sdist_size:
                raise FoundationBootstrapError("sdist size does not match evidence")
            wheel = candidate.read(wheel_info)
            sdist = candidate.read(sdist_info)
            if len(wheel) != record.wheel_size:
                raise FoundationBootstrapError("wheel size does not match evidence")
            if hashlib.sha256(wheel).hexdigest() != record.wheel_sha256:
                raise FoundationBootstrapError("wheel SHA-256 does not match evidence")
            if len(sdist) != record.sdist_size:
                raise FoundationBootstrapError("sdist size does not match evidence")
            if hashlib.sha256(sdist).hexdigest() != record.sdist_sha256:
                raise FoundationBootstrapError("sdist SHA-256 does not match evidence")
        with zipfile.ZipFile(io.BytesIO(receipt_bytes)) as receipt_archive:
            infos = _safe_members(receipt_archive)
            if {info.filename for info in infos} != {record.receipt_filename}:
                raise FoundationBootstrapError(
                    "receipt archive members do not match evidence"
                )
            receipt_info = receipt_archive.getinfo(record.receipt_filename)
            if receipt_info.file_size != record.receipt_file_size:
                raise FoundationBootstrapError(
                    "receipt file size does not match evidence"
                )
            _verify_receipt(record, receipt_archive.read(receipt_info))
    except (OSError, zipfile.BadZipFile, KeyError) as error:
        raise FoundationBootstrapError("artifact archive is unreadable") from error
    _verify_wheel_bytes(record, wheel, as_of=as_of)


def verify_materialized_evidence(
    candidate_archive_path: Path, receipt_archive_path: Path
) -> None:
    """Verify fixed candidate and receipt GitHub artifact ZIP evidence."""
    record = load_foundation_bootstrap_json(
        Path(__file__).parents[1] / "policies/foundation-profile-bootstrap.json"
    )
    try:
        if candidate_archive_path.stat().st_size != record.candidate_archive_size:
            raise FoundationBootstrapError(
                "candidate archive size does not match evidence"
            )
        if receipt_archive_path.stat().st_size != record.receipt_archive_size:
            raise FoundationBootstrapError(
                "receipt archive size does not match evidence"
            )
        candidate_bytes = candidate_archive_path.read_bytes()
        receipt_bytes = receipt_archive_path.read_bytes()
    except OSError as error:
        raise FoundationBootstrapError("artifact archive is unreadable") from error
    _verify_materialized_evidence_bytes(
        record, candidate_bytes, receipt_bytes, as_of=_utc_now()
    )


parse_foundation_bootstrap = load_foundation_bootstrap

__all__ = (
    "FoundationBootstrapError",
    "FoundationContractBootstrap",
    "load_foundation_bootstrap",
    "load_foundation_bootstrap_json",
    "parse_foundation_bootstrap",
    "verify_materialized_evidence",
    "verify_materialized_wheel",
)
