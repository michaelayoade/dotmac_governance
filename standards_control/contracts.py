"""Immutable contracts for cross-repository engineering conformance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import NewType

ProfileId = NewType("ProfileId", str)
AuthorityId = NewType("AuthorityId", str)
ResourceId = NewType("ResourceId", str)
SurfaceId = NewType("SurfaceId", str)
VocabularyId = NewType("VocabularyId", str)
CanonicalRepository = NewType("CanonicalRepository", str)
BranchName = NewType("BranchName", str)
PythonSymbol = NewType("PythonSymbol", str)
GitRevision = NewType("GitRevision", str)


class Severity(str, Enum):
    ERROR = "error"


class GovernanceStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class EnforcementMode(str, Enum):
    CANDIDATE = "candidate"
    REQUIRED = "required"


class GovernanceSourceKind(str, Enum):
    LOCAL = "local"
    PINNED = "pinned"


class DiagnosticCode(str, Enum):
    PROFILE_INVALID = "profile.invalid"
    REPOSITORY_IDENTITY_UNAVAILABLE = "repository.identity.unavailable"
    REPOSITORY_IDENTITY_MISMATCH = "repository.identity.mismatch"
    REPOSITORY_DEFAULT_BRANCH_UNAVAILABLE = "repository.default-branch.unavailable"
    REPOSITORY_DEFAULT_BRANCH_MISMATCH = "repository.default-branch.mismatch"
    GOVERNANCE_SOURCE_MISSING = "governance.source.missing"
    GOVERNANCE_SOURCE_STATUS_MISSING = "governance.source.status-missing"
    GOVERNANCE_SOURCE_STATUS_MISMATCH = "governance.source.status-mismatch"
    GOVERNANCE_ROOT_UNAVAILABLE = "governance.root.unavailable"
    GOVERNANCE_LOCAL_SOURCE_FORBIDDEN = "governance.local-source.forbidden"
    GOVERNANCE_REPOSITORY_UNAVAILABLE = "governance.repository.unavailable"
    GOVERNANCE_REPOSITORY_MISMATCH = "governance.repository.mismatch"
    GOVERNANCE_REVISION_UNAVAILABLE = "governance.revision.unavailable"
    GOVERNANCE_REVISION_MISMATCH = "governance.revision.mismatch"
    AUTHORITY_RESOURCE_DUPLICATE = "authority.resource.duplicate"
    AUTHORITY_PATH_MISSING = "authority.path.missing"
    AUTHORITY_INTERFACE_MISSING = "authority.interface.missing"
    AUTHORITY_OWNER_NOT_WRITER = "authority.owner.not-canonical-writer"
    AUTHORITY_ADAPTER_WRITER_OVERLAP = "authority.adapter.writer-overlap"
    CONTRACT_PATH_MISSING = "contract.path.missing"
    CONTRACT_SYNTAX_INVALID = "contract.syntax.invalid"
    CONTRACT_ANY_FORBIDDEN = "contract.any.forbidden"
    CONTRACT_ANNOTATION_MISSING = "contract.annotation.missing"
    CONTRACT_BARE_CONTAINER = "contract.bare-container"
    CONTRACT_RECORD_MUTABLE = "contract.record.mutable"
    VOCABULARY_PATH_MISSING = "vocabulary.path.missing"
    VOCABULARY_SYNTAX_INVALID = "vocabulary.syntax.invalid"
    VOCABULARY_MEMBER_TYPE_MISSING = "vocabulary.member-type.missing"
    VOCABULARY_MEMBER_TYPE_CLOSED = "vocabulary.member-type.closed"
    VOCABULARY_REGISTRY_MISSING = "vocabulary.registry.missing"
    VOCABULARY_DECLARATION_MISSING = "vocabulary.declaration.missing"
    VOCABULARY_STORAGE_CLOSED = "vocabulary.storage.closed"


@dataclass(frozen=True)
class RepositoryContract:
    canonical_url: CanonicalRepository
    default_branch: BranchName


@dataclass(frozen=True)
class LocalGovernanceModelRef:
    kind: GovernanceSourceKind
    source: PurePosixPath
    status: GovernanceStatus


@dataclass(frozen=True)
class PinnedGovernanceModelRef:
    kind: GovernanceSourceKind
    canonical_url: CanonicalRepository
    revision: GitRevision
    source: PurePosixPath
    status: GovernanceStatus


GovernanceModelRef = LocalGovernanceModelRef | PinnedGovernanceModelRef


@dataclass(frozen=True)
class AuthorityContract:
    authority_id: AuthorityId
    subject: str
    protected_resources: tuple[ResourceId, ...]
    owner_component: str
    owner_implementation: PurePosixPath
    decision_interface: PythonSymbol
    canonical_writer_paths: tuple[PurePosixPath, ...]
    adapter_paths: tuple[PurePosixPath, ...]
    drift_test_paths: tuple[PurePosixPath, ...]


@dataclass(frozen=True)
class TypedContractSurface:
    surface_id: SurfaceId
    paths: tuple[PurePosixPath, ...]
    require_public_annotations: bool
    forbid_any: bool
    require_immutable_records: bool


@dataclass(frozen=True)
class ModuleDeclaredVocabulary:
    vocabulary_id: VocabularyId
    subject: str
    member_type: str
    member_type_path: PurePosixPath
    registry_interface: PythonSymbol
    registry_implementation: PurePosixPath
    declaration_field: str
    declaration_paths: tuple[PurePosixPath, ...]
    storage_column: str
    storage_paths: tuple[PurePosixPath, ...]


@dataclass(frozen=True)
class StandardsProfile:
    schema_version: int
    profile_id: ProfileId
    repository: RepositoryContract
    governance_model: GovernanceModelRef
    enforcement_mode: EnforcementMode
    authorities: tuple[AuthorityContract, ...]
    typed_contract_surfaces: tuple[TypedContractSurface, ...]
    module_declared_vocabularies: tuple[ModuleDeclaredVocabulary, ...]


@dataclass(frozen=True)
class Diagnostic:
    code: DiagnosticCode
    severity: Severity
    message: str
    path: PurePosixPath | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "code": self.code.value,
            "severity": self.severity.value,
            "message": self.message,
        }
        if self.path is not None:
            result["path"] = self.path.as_posix()
        if self.line is not None:
            result["line"] = self.line
        return result


@dataclass(frozen=True)
class ConformanceReport:
    profile_id: ProfileId | None
    enforcement_mode: EnforcementMode | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def conforms(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "enforcement_mode": (
                self.enforcement_mode.value
                if self.enforcement_mode is not None
                else None
            ),
            "conforms": self.conforms,
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
