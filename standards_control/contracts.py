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
DeploymentArtefactSurfaceId = NewType("DeploymentArtefactSurfaceId", str)
CanonicalRepository = NewType("CanonicalRepository", str)
BranchName = NewType("BranchName", str)
PythonSymbol = NewType("PythonSymbol", str)
GitRevision = NewType("GitRevision", str)


class Severity(str, Enum):
    """How a diagnostic bears on conformance.

    `NOTICE` exists so the derived measurement scope can be PUBLISHED rather
    than merely applied: every file the engine removed from the connector
    universe is named in the report with the reason it was removed. A notice
    never fails a run, and `ConformanceReport.conforms` counts errors alone.
    """

    ERROR = "error"
    NOTICE = "notice"


class GovernanceStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class EnforcementMode(str, Enum):
    CANDIDATE = "candidate"
    REQUIRED = "required"


class GovernanceSourceKind(str, Enum):
    LOCAL = "local"
    PINNED = "pinned"


class VocabularyMemberKind(str, Enum):
    DECLARED = "declared"
    BUILTIN = "builtin"


class ConnectorCategory(str, Enum):
    """The six measured direct external-connector surfaces.

    Closed on purpose. A profile declares a baseline for every member, so a
    category cannot be dropped from a profile to make a count disappear.

    `OUTBOUND_TRANSPORT` was called `HTTP_CLIENT` until schema version 9, and
    the rename is the whole reason that version exists. A category named after
    ONE transport had no room for a genuine SMTP delivery task, which therefore
    held no category at all; the alternatives were to accept a documented blind
    spot or to file mail under HTTP, and both were refused. The member names
    the concept and carries one ARM per protocol — see ADR 0011, "The category
    is the concept, not one transport".

    Naming the concept is not covering it. Exactly TWO arms exist today, HTTP
    and SMTP, and every other protocol — brokers, gRPC, sockets, SSH/SFTP,
    SNMP/RADIUS, database links, SDKs whose transport is not a named client
    library — is UNMONITORED rather than exempt. A baseline of zero means zero
    in the protocols this engine measures. See ADR 0011's amendment of
    2026-08-16, statement 3.
    """

    OUTBOUND_TRANSPORT = "outbound_transport"
    WEBHOOK_SURFACE = "webhook_surface"
    PROVIDER_CREDENTIAL = "provider_credential"
    CONNECTOR_TASK = "connector_task"
    SYNC_CHECKPOINT = "sync_checkpoint"
    DELIVERY_RETRY = "delivery_retry"


class DiagnosticCode(str, Enum):
    PROFILE_INVALID = "profile.invalid"
    REPOSITORY_IDENTITY_UNAVAILABLE = "repository.identity.unavailable"
    REPOSITORY_IDENTITY_MISMATCH = "repository.identity.mismatch"
    REPOSITORY_DEFAULT_BRANCH_UNAVAILABLE = "repository.default-branch.unavailable"
    REPOSITORY_DEFAULT_BRANCH_MISMATCH = "repository.default-branch.mismatch"
    REPOSITORY_INVENTORY_UNAVAILABLE = "repository.inventory.unavailable"
    REPOSITORY_SOURCE_UNTRACKED = "repository.source.untracked"
    REPOSITORY_TREE_UNMEASURED = "repository.tree.unmeasured"
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
    TESTING_KIT_PATH_MISSING = "testing-kit.path.missing"
    TESTING_KIT_SYNTAX_INVALID = "testing-kit.syntax.invalid"
    TESTING_KIT_IMPORT_FORBIDDEN = "testing-kit.import.forbidden"
    TESTING_KIT_PROBE_COUNT_MISMATCH = "testing-kit.probe.count-mismatch"
    CONNECTOR_SYNTAX_INVALID = "connector.syntax.invalid"
    CONNECTOR_BASELINE_EXCEEDED = "connector.baseline.exceeded"
    CONNECTOR_BASELINE_STALE = "connector.baseline.stale"
    CONNECTOR_SCOPE_EXCLUDED = "connector.scope.excluded"
    CONNECTOR_CONSERVED_RECORDED = "connector.conserved.recorded"
    CONNECTOR_CONSERVED_UNDECLARED = "connector.conserved.undeclared"
    CONNECTOR_CONSERVED_STALE = "connector.conserved.stale"
    CONNECTOR_CONSERVED_CHANGED = "connector.conserved.changed"
    CONNECTOR_RUNTIME_AUTHORITY_UNAVAILABLE = "connector.runtime-authority.unavailable"
    CONNECTOR_DEPENDENCY_LOCK_UNAVAILABLE = "connector.dependency-lock.unavailable"
    CONNECTOR_RUNTIME_DEPENDENCY_FORBIDDEN = "connector.runtime-dependency.forbidden"
    CONNECTOR_SOURCE_DISTRIBUTION_EXCLUDED = "connector.source-distribution.excluded"
    DEPLOYMENT_SURFACE_MISSING = "deployment.surface.missing"
    DEPLOYMENT_SURFACE_UNREADABLE = "deployment.surface.unreadable"
    DEPLOYMENT_IMAGE_NOT_PINNED = "deployment.image.not-pinned"
    DEPLOYMENT_ENVIRONMENT_LITERAL = "deployment.environment.literal"
    DEPLOYMENT_CREDENTIAL_FILENAME = "deployment.credential.filename"
    DEPLOYMENT_DECLARATION_UNPARSEABLE = "deployment.declaration.unparseable"
    DEPLOYMENT_RENDER_CHECK_ABSENT = "deployment.render-check.absent"
    DEPLOYMENT_SURFACE_UNDECLARED = "deployment.surface.undeclared"
    DEPLOYMENT_ACKNOWLEDGEMENT_STALE = "deployment.acknowledgement.stale"
    RETIREMENT_SURFACE_DUPLICATE = "retirement.surface.duplicate"
    RETIREMENT_SOURCE_UNMEASURED = "retirement.source.unmeasured"
    RETIREMENT_STATIC_ADDED = "retirement.static.added"
    RETIREMENT_STATIC_STALE = "retirement.static.stale"
    RETIREMENT_STATIC_CHANGED = "retirement.static.changed"
    RETIREMENT_CATALOGUE_ADDED = "retirement.catalogue.added"
    RETIREMENT_CATALOGUE_STALE = "retirement.catalogue.stale"
    RETIREMENT_CATALOGUE_CHANGED = "retirement.catalogue.changed"
    RETIREMENT_AUTHORITY_CONFLICT = "retirement.authority.conflict"
    RETIREMENT_HISTORY_CHANGED = "retirement.history.changed"
    RETIREMENT_WRITER_FORBIDDEN = "retirement.writer.forbidden"
    RETIREMENT_PROJECTION_INVALID = "retirement.projection.invalid"
    RETIREMENT_DELETION_LINEAGE_MISMATCH = "retirement.deletion.lineage-mismatch"
    RETIREMENT_GATE_NONZERO = "retirement.gate.nonzero"
    RETIREMENT_EVIDENCE_MISSING = "retirement.evidence.missing"
    RETIREMENT_EVIDENCE_BINDING_MISMATCH = "retirement.evidence.binding-mismatch"
    RETIREMENT_EVIDENCE_UNKNOWN = "retirement.evidence.unknown"
    RETIREMENT_TEARDOWN_INVENTORY_MISMATCH = "retirement.teardown.inventory-mismatch"
    RETIREMENT_COMPLETION_UNSUPPORTED = "retirement.completion.unsupported"


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
class VocabularyMemberType:
    kind: VocabularyMemberKind
    name: str
    path: PurePosixPath | None


@dataclass(frozen=True)
class VocabularyStorage:
    column: str
    paths: tuple[PurePosixPath, ...]


@dataclass(frozen=True)
class ModuleDeclaredVocabulary:
    vocabulary_id: VocabularyId
    subject: str
    member_type: VocabularyMemberType
    registry_interface: PythonSymbol
    registry_implementation: PurePosixPath
    declaration_field: str
    declaration_paths: tuple[PurePosixPath, ...]
    storage: VocabularyStorage | None


@dataclass(frozen=True)
class ConformanceProbe:
    path: PurePosixPath
    expected_import_count: int


@dataclass(frozen=True)
class TestingKitBoundary:
    test_roots: tuple[PurePosixPath, ...]
    kit_source_roots: tuple[PurePosixPath, ...]
    conformance_probes: tuple[ConformanceProbe, ...]


@dataclass(frozen=True)
class AcknowledgedNonDeployment:
    """A file that LOOKS like a deployment declaration and is not one.

    An acknowledgement, never a waiver — the same shape the connector family
    uses for a conserved exclusion, and for the same reason. It removes nothing
    from what is checked; it records that a reader has already decided this
    path is a development convenience or a test fixture, so the next reader
    inherits the decision instead of rediscovering it. A stale entry is a
    finding, because a list that only grows stops describing anything.
    """

    path: PurePosixPath
    reason: str


@dataclass(frozen=True)
class DeploymentArtefactSurface:
    """One deployable a repository ships, and the assets rendered from it.

    ADR 0014. The DECLARATION is the artefact that must carry no environment
    fact; the RENDER is that declaration plus one environment, compared
    byte-for-byte by a named workflow. Both are named here because the two
    halves fail differently: a declaration that grew an address is a standard
    violation, and a render nobody compares is a deployment nobody approved.
    """

    surface_id: DeploymentArtefactSurfaceId
    subject: str
    declaration_paths: tuple[PurePosixPath, ...]
    rendered_paths: tuple[PurePosixPath, ...]
    render_check_workflow: PurePosixPath
    render_check_command: str
    acknowledged_non_deployments: tuple[AcknowledgedNonDeployment, ...]


@dataclass(frozen=True)
class CategoryBaseline:
    category: ConnectorCategory
    count: int


#: The symbol a conserved finding carries when no module-level definition owns
#: it — a surface held by the module's own import-time statements.
CONSERVED_MODULE_SYMBOL = "<module>"


@dataclass(frozen=True)
class ConservedFinding:
    """One connector-shaped surface that left the measured universe.

    The same record serves both directions: the engine PUBLISHES one per
    conserved surface it observes, and a profile DECLARES the set already
    reviewed. Conformance is set equality between the two, so a subtraction
    nobody has seen before is an error rather than another quiet notice.

    A declared entry is an acknowledgement, never a waiver. Nothing here can
    remove a source from the universe — the derivation already did that, and no
    profile key is an input to it. An entry naming a MEASURED source suppresses
    nothing and reports stale, because no conserved finding backs it.

    `fingerprint` hashes the NORMALIZED parse tree of the unit the symbol names,
    so reformatting, a comment, a docstring or a renamed local leave the record
    standing while a change in what the code DOES invalidates it.
    """

    path: PurePosixPath
    symbol: str
    category: ConnectorCategory
    fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path.as_posix(),
            "symbol": self.symbol,
            "category": self.category.value,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True)
class ExternalConnectorSurface:
    """What a repository may say about its own connector surface.

    Six counts, and the conserved exclusions it has already reviewed. There is
    deliberately no `runtime_roots` and no `exclusions` key: a product that can
    name what is measured, or name a file out of the measurement, is not
    measured. The universe is derived by the engine from the repository's
    tracked inventory, and `conserved_exclusions` records what that derivation
    removed rather than influencing it.
    """

    baselines: tuple[CategoryBaseline, ...]
    conserved_exclusions: tuple[ConservedFinding, ...]


@dataclass(frozen=True)
class ExcludedSource:
    """One tracked source the engine removed from the connector universe."""

    path: PurePosixPath
    reason: str


@dataclass(frozen=True)
class ConnectorScope:
    """The derived, closed measurement universe for one repository.

    `measured` and `excluded` partition the tracked Python inventory, so the
    scope is reviewable rather than invisible. `conserved` is the
    connector-shaped subset of what `excluded` removed — the part of the
    subtraction that is ratcheted rather than merely published.

    Python on disk but outside the index is enumerated as TWO DISTINCT
    POPULATIONS, never one. `untracked_visible` is what a plain checkout shows;
    `untracked_ignored` is what this repository's own ignore rules hide.
    Collapsing them is precisely what hid the problem: reporting only the union
    made an unusable count, and answering that by applying `--exclude-standard`
    would have deleted a gitignored connector and a dependency tree together.
    Both populations are errors — an ignore rule is product-authored and
    decides nothing about what is measured — and `untracked` remains their
    union so a caller cannot read one half and believe it read the whole.

    No dependency-environment outcome exists. Files below an in-repository
    virtualenv remain untracked source because its METADATA and RECORD are
    controlled by the same working tree and cannot authorize themselves out of
    measurement.
    """

    inventory_available: bool
    measured: tuple[PurePosixPath, ...]
    excluded: tuple[ExcludedSource, ...]
    untracked_visible: tuple[PurePosixPath, ...] = ()
    untracked_ignored: tuple[PurePosixPath, ...] = ()
    conserved: tuple[ConservedFinding, ...] = ()

    @property
    def untracked(self) -> tuple[PurePosixPath, ...]:
        """Both untracked populations, in one deterministic sequence."""
        return tuple(
            sorted(
                (*self.untracked_visible, *self.untracked_ignored),
                key=lambda path: path.as_posix(),
            )
        )


@dataclass(frozen=True)
class KernelAdoptionBinding:
    """Where a repository's Kernel-adoption declaration lives, and which
    contract it claims. A POINTER, never the declaration itself.

    The declaration is a dedicated product-owned document
    (`.dotmac/kernel-adoption.json`) under the Governance-owned
    `KernelAdoptionDeclaration.v1` contract. This profile carries only the
    binding, so a classification cannot arrive as a plausible line in a diff to
    the conformance profile, and so the two documents version independently.

    The key is DECLARED-OPTIONAL rather than required, and the reason is
    stated rather than convenient. A required key would force every enrolled
    repository through a `schema_version` bump before it could declare
    anything, and the three products are still at v9 — four migration stops
    away. Optionality costs nothing here because the refusal that matters lives
    on the DECLARATION: an absent or unreadable `.dotmac/kernel-adoption.json`
    is refused by `kernel_adoption_control`, never read as an empty list. What
    the binding adds is a non-default path and the contract version the
    repository claims.
    """

    declaration_path: PurePosixPath
    contract_version: str


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
    testing_kit_boundary: TestingKitBoundary
    external_connector_surface: ExternalConnectorSurface
    deployment_artefact_surfaces: tuple[DeploymentArtefactSurface, ...]
    compatibility_retirements: tuple[CompatibilityRetirement, ...]
    retirement_history: tuple[RetirementHistory, ...]
    #: `None` means "this profile states no binding", which is NOT the same as
    #: "this repository has no declaration": the declaration is then read from
    #: its default path, and its absence is refused there rather than here.
    kernel_adoption_binding: KernelAdoptionBinding | None = None


@dataclass(frozen=True)
class SourceReference:
    kind: str
    path: PurePosixPath
    member: str


@dataclass(frozen=True)
class StaticRetirementEdge:
    kind: str
    path: PurePosixPath
    symbol: PythonSymbol
    target: str
    fingerprint: str
    consumer_id: str | None

    @property
    def identity(self) -> tuple[str, PurePosixPath, PythonSymbol, str, str | None]:
        return (self.kind, self.path, self.symbol, self.target, self.consumer_id)


@dataclass(frozen=True)
class CatalogueRetirementEdge:
    kind: str
    identity: str
    definition_sha256: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.kind, self.identity)


@dataclass(frozen=True)
class CompatibilityRetirement:
    retirement_id: str
    relation_kind: str
    relation_identity: str
    owner_lineage: str
    authority_state: str
    current_authority_id: AuthorityId
    current_writer: SourceReference
    target_module_authority_id: AuthorityId | None
    displaced_authority_id: AuthorityId | None
    accountable_owner: str
    disposition_kind: str
    disposition_authority_id: AuthorityId | None
    projection_kind: str | None
    projection_writer: SourceReference | None
    source_state: str
    requested_gate: str
    consumers: tuple[str, ...]
    consumer_blocked_by: tuple[SourceReference, ...]
    static_baseline: tuple[StaticRetirementEdge, ...]
    catalogue_baseline: tuple[CatalogueRetirementEdge, ...]
    collector: SourceReference
    collector_workflow_path: PurePosixPath
    collector_producer_id: str
    normalization_version: str
    deletion_migration: SourceReference | None
    deletion_owner_lineage: str | None
    teardown_set: tuple[CatalogueRetirementEdge, ...]
    fence_relations: tuple[str, ...]
    exit_conditions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RetirementHistory:
    retirement_id: str
    relation_identity: str
    displaced_authority: AuthorityId
    current_authority_id: AuthorityId
    closure_kind: str


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
    enrolled_retirement_ids: tuple[str, ...] = ()
    product_revision_evidence: str = "not_supplied"
    target_evidence: str = "not_supplied"
    repository_contracts: str | None = None

    @property
    def conforms(self) -> bool:
        return not any(item.severity is Severity.ERROR for item in self.diagnostics)

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
            "repository_contracts": self.repository_contracts
            if self.repository_contracts is not None
            else "pass"
            if self.conforms
            else "fail",
            "product_revision_evidence": self.product_revision_evidence,
            "target_evidence": self.target_evidence,
            "enrolled_retirement_ids": list(self.enrolled_retirement_ids),
        }
