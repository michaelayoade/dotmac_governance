"""Strict JSON adapter for a repository engineering-standards profile."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from .contracts import (
    CONSERVED_MODULE_SYMBOL,
    AuthorityContract,
    AuthorityId,
    BranchName,
    CanonicalRepository,
    CategoryBaseline,
    ConformanceProbe,
    ConnectorCategory,
    ConservedFinding,
    EnforcementMode,
    ExternalConnectorSurface,
    GitRevision,
    GovernanceModelRef,
    GovernanceSourceKind,
    GovernanceStatus,
    LocalGovernanceModelRef,
    ModuleDeclaredVocabulary,
    PinnedGovernanceModelRef,
    ProfileId,
    PythonSymbol,
    RepositoryContract,
    ResourceId,
    StandardsProfile,
    SurfaceId,
    TestingKitBoundary,
    TypedContractSurface,
    VocabularyId,
    VocabularyMemberKind,
    VocabularyMemberType,
    VocabularyStorage,
)

SLUG = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
BRANCH = re.compile(r"^[A-Za-z0-9._/-]+$")
HTTPS_REPOSITORY = re.compile(r"^https://[^/\s]+/[^/\s]+/[^/\s]+$")
PYTHON_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
#: A conserved fingerprint is a full lower-case SHA-256 digest and nothing else.
#: Truncating it would be a shorter hash, not a friendlier one.
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


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


def _positive_int(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ProfileError(f"{location} must be a positive integer")
    return value


def _count(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ProfileError(f"{location} must be a non-negative integer")
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
    raw_kind = _string(data.get("kind"), "governance_model.kind")
    try:
        kind = GovernanceSourceKind(raw_kind)
    except ValueError as error:
        raise ProfileError("governance_model.kind must be local or pinned") from error
    if kind is GovernanceSourceKind.LOCAL:
        _keys(data, frozenset({"kind", "source", "status"}), "governance_model")
    else:
        _keys(
            data,
            frozenset({"kind", "canonical_url", "revision", "source", "status"}),
            "governance_model",
        )
    raw = _string(data["status"], "governance_model.status")
    try:
        status = GovernanceStatus(raw)
    except ValueError as error:
        raise ProfileError(
            "governance_model.status must be proposed or accepted"
        ) from error
    source = _path(data["source"], "governance_model.source")
    if kind is GovernanceSourceKind.LOCAL:
        return LocalGovernanceModelRef(kind=kind, source=source, status=status)
    canonical_url = _string(data["canonical_url"], "governance_model.canonical_url")
    if not HTTPS_REPOSITORY.fullmatch(canonical_url):
        raise ProfileError(
            "governance_model.canonical_url must be a canonical HTTPS URL"
        )
    revision = _string(data["revision"], "governance_model.revision")
    if not GIT_REVISION.fullmatch(revision):
        raise ProfileError(
            "governance_model.revision must be a lower-case 40-character Git SHA"
        )
    return PinnedGovernanceModelRef(
        kind=kind,
        canonical_url=CanonicalRepository(canonical_url.removesuffix(".git")),
        revision=GitRevision(revision),
        source=source,
        status=status,
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


def _identifier(value: object, location: str) -> str:
    raw = _string(value, location)
    if not IDENTIFIER.fullmatch(raw):
        raise ProfileError(f"{location} must be a Python identifier")
    return raw


def _vocabulary_member(value: object, location: str) -> VocabularyMemberType:
    data = _object(value, location)
    raw_kind = _string(data.get("kind"), f"{location}.kind")
    try:
        kind = VocabularyMemberKind(raw_kind)
    except ValueError as error:
        raise ProfileError(f"{location}.kind must be declared or builtin") from error
    if kind is VocabularyMemberKind.DECLARED:
        _keys(data, frozenset({"kind", "name", "path"}), location)
        path: PurePosixPath | None = _path(data["path"], f"{location}.path")
    else:
        _keys(data, frozenset({"kind", "name"}), location)
        path = None
    name = _identifier(data["name"], f"{location}.name")
    if kind is VocabularyMemberKind.BUILTIN and name != "str":
        raise ProfileError(f"{location}.name must be str for a builtin member")
    return VocabularyMemberType(kind=kind, name=name, path=path)


def _vocabulary_storage(value: object, location: str) -> VocabularyStorage | None:
    if value is None:
        return None
    data = _object(value, location)
    _keys(data, frozenset({"column", "paths"}), location)
    paths = _paths(data["paths"], f"{location}.paths")
    if not paths:
        raise ProfileError(f"{location}.paths must not be empty")
    return VocabularyStorage(
        column=_identifier(data["column"], f"{location}.column"),
        paths=paths,
    )


def _vocabulary(value: object, index: int) -> ModuleDeclaredVocabulary:
    location = f"module_declared_vocabularies[{index}]"
    data = _object(value, location)
    required = frozenset(
        {
            "vocabulary_id",
            "subject",
            "member_type",
            "registry_interface",
            "registry_implementation",
            "declaration_field",
            "declaration_paths",
            "storage",
        }
    )
    _keys(data, required, location)
    interface = _string(data["registry_interface"], f"{location}.registry_interface")
    if not PYTHON_SYMBOL.fullmatch(interface):
        raise ProfileError(f"{location}.registry_interface must be a dotted symbol")
    declarations = _paths(data["declaration_paths"], f"{location}.declaration_paths")
    if not declarations:
        raise ProfileError(f"{location} needs declaration paths")
    return ModuleDeclaredVocabulary(
        vocabulary_id=VocabularyId(
            _slug(data["vocabulary_id"], f"{location}.vocabulary_id")
        ),
        subject=_string(data["subject"], f"{location}.subject"),
        member_type=_vocabulary_member(data["member_type"], f"{location}.member_type"),
        registry_interface=PythonSymbol(interface),
        registry_implementation=_path(
            data["registry_implementation"], f"{location}.registry_implementation"
        ),
        declaration_field=_identifier(
            data["declaration_field"], f"{location}.declaration_field"
        ),
        declaration_paths=declarations,
        storage=_vocabulary_storage(data["storage"], f"{location}.storage"),
    )


def _testing_kit_boundary(value: object) -> TestingKitBoundary:
    location = "testing_kit_boundary"
    data = _object(value, location)
    _keys(
        data,
        frozenset({"test_roots", "kit_source_roots", "conformance_probes"}),
        location,
    )
    test_roots = _paths(data["test_roots"], f"{location}.test_roots")
    if not test_roots:
        raise ProfileError(f"{location}.test_roots must not be empty")
    for index, path in enumerate(test_roots):
        if path.name != "tests":
            raise ProfileError(
                f"{location}.test_roots[{index}] must name a structural tests directory"
            )
    kit_source_roots = _paths(data["kit_source_roots"], f"{location}.kit_source_roots")
    for index, path in enumerate(kit_source_roots):
        if path.parts[-2:] != ("dotmac_kernel", "testing"):
            raise ProfileError(
                f"{location}.kit_source_roots[{index}] must end in "
                "dotmac_kernel/testing"
            )
    probes: list[ConformanceProbe] = []
    for index, raw_probe in enumerate(
        _sequence(data["conformance_probes"], f"{location}.conformance_probes")
    ):
        probe_location = f"{location}.conformance_probes[{index}]"
        probe = _object(raw_probe, probe_location)
        _keys(probe, frozenset({"path", "expected_import_count"}), probe_location)
        path = _path(probe["path"], f"{probe_location}.path")
        if path.suffix != ".py":
            raise ProfileError(f"{probe_location}.path must name a Python file")
        if any(path == root or root in path.parents for root in test_roots):
            raise ProfileError(
                f"{probe_location}.path is already inside a declared test root"
            )
        if any(path == root or root in path.parents for root in kit_source_roots):
            raise ProfileError(
                f"{probe_location}.path is already inside a kit source root"
            )
        probes.append(
            ConformanceProbe(
                path=path,
                expected_import_count=_positive_int(
                    probe["expected_import_count"],
                    f"{probe_location}.expected_import_count",
                ),
            )
        )
    if len({probe.path for probe in probes}) != len(probes):
        raise ProfileError(f"{location}.conformance_probes paths must be unique")
    return TestingKitBoundary(
        test_roots=test_roots,
        kit_source_roots=kit_source_roots,
        conformance_probes=tuple(probes),
    )


def _conserved_finding(value: object, location: str) -> ConservedFinding:
    """Parse one exact, governance-authored conservation record.

    Every coordinate is a literal the ENGINE published: the path it removed,
    the symbol that held the surface, the category it was classified as, and
    the fingerprint of the normalized unit. There is no reason field and no
    predicate — a premise a product can satisfy by editing its own file is the
    mechanism this record family exists without. There is no wildcard either:
    an entry matches one finding or none.
    """
    data = _object(value, location)
    _keys(data, frozenset({"path", "symbol", "category", "fingerprint"}), location)
    raw_category = _string(data["category"], f"{location}.category")
    try:
        category = ConnectorCategory(raw_category)
    except ValueError as error:
        raise ProfileError(
            f"{location}.category must be one of "
            f"{', '.join(item.value for item in ConnectorCategory)}"
        ) from error
    symbol = _string(data["symbol"], f"{location}.symbol")
    if symbol != CONSERVED_MODULE_SYMBOL and not IDENTIFIER.fullmatch(symbol):
        raise ProfileError(
            f"{location}.symbol must be a Python identifier or "
            f"{CONSERVED_MODULE_SYMBOL!r}"
        )
    fingerprint = _string(data["fingerprint"], f"{location}.fingerprint")
    if not FINGERPRINT.fullmatch(fingerprint):
        raise ProfileError(
            f"{location}.fingerprint must be a lower-case 64-character SHA-256 digest"
        )
    path = _path(data["path"], f"{location}.path")
    if any(character in path.as_posix() for character in "*?[]"):
        raise ProfileError(
            f"{location}.path must be a literal file, never a pattern: an entry "
            "matches one conserved finding or none"
        )
    if path.suffix not in {".py", ".pyw"} and "." in path.name:
        raise ProfileError(f"{location}.path must name a Python source")
    return ConservedFinding(
        path=path, symbol=symbol, category=category, fingerprint=fingerprint
    )


def _external_connector_surface(value: object) -> ExternalConnectorSurface:
    """Parse what a repository may declare here: six counts and its ledger.

    `runtime_roots` and `exclusions` were product-authored scope, and both are
    refused as unknown keys now. A repository that could name what is measured,
    or name a file out of the measurement, was declaring its own result.
    `conserved_exclusions` is the opposite shape: it names nothing INTO or OUT
    of the measurement, it acknowledges a subtraction the engine already made.
    """
    location = "external_connector_surface"
    data = _object(value, location)
    _keys(data, frozenset({"baselines", "conserved_exclusions"}), location)
    baselines_data = _object(data["baselines"], f"{location}.baselines")
    _keys(
        baselines_data,
        frozenset(item.value for item in ConnectorCategory),
        f"{location}.baselines",
    )
    baselines = tuple(
        CategoryBaseline(
            category=category,
            count=_count(
                baselines_data[category.value],
                f"{location}.baselines.{category.value}",
            ),
        )
        for category in ConnectorCategory
    )
    conserved = tuple(
        _conserved_finding(item, f"{location}.conserved_exclusions[{index}]")
        for index, item in enumerate(
            _sequence(data["conserved_exclusions"], f"{location}.conserved_exclusions")
        )
    )
    # Keyed on path, symbol and category, NOT on the whole record. Two entries
    # differing only in fingerprint would let one match while the other went
    # stale, which is a second answer to a question that has one.
    keys = [(item.path, item.symbol, item.category) for item in conserved]
    if len(set(keys)) != len(keys):
        raise ProfileError(
            f"{location}.conserved_exclusions must not name the same path, "
            "symbol and category twice"
        )
    return ExternalConnectorSurface(baselines=baselines, conserved_exclusions=conserved)


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
                "module_declared_vocabularies",
                "testing_kit_boundary",
                "external_connector_surface",
            }
        ),
        "profile",
    )
    version = data["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ProfileError("schema_version must be integer 9")
    if version == 7:
        # Version 7 shipped an exclusion that was a SILENT subtraction: nothing
        # recorded what left the measured universe. It is withdrawn rather than
        # upgraded, and it refuses to load rather than gaining conservation it
        # was never reviewed against. Every adopter was pending approval when
        # version 8 landed, so there is no migration path to preserve.
        raise ProfileError(
            "schema_version 7 was withdrawn and never accepted: it recorded no "
            "conserved exclusions, so a subtraction from the measured universe "
            "left no trace. There is no upgrade path from it — move the profile "
            "to schema_version 9 and declare external_connector_surface."
            "conserved_exclusions from a run of the engine"
        )
    if version == 8:
        # Version 8 named a category `http_client`, after ONE transport rather
        # than the concept, and an SMTP delivery task consequently held no
        # category at all. Carrying the vocabulary forward would have meant
        # accepting a documented blind spot or filing mail under HTTP; both
        # were refused, so the abstraction was fixed instead. A version-8
        # profile declares a baseline for a category that no longer exists and
        # none for the one that replaced it, which is not a rename a loader may
        # perform on a product's behalf: the number behind `http_client` was
        # measured under a rule that could not see SMTP, so inheriting it would
        # silently ratchet a surface nobody counted. It is withdrawn, exactly
        # as version 7 is, and every adopter was pending approval when version
        # 9 landed, so there is no accepted consumer to migrate.
        raise ProfileError(
            "schema_version 8 was withdrawn and never accepted: its "
            "external_connector_surface.baselines declared http_client, a "
            "category named after one transport, so a genuine SMTP delivery "
            "surface could hold no category at all. There is no upgrade path "
            "from it — the recorded http_client count was measured by a rule "
            "that could not see SMTP and must not be inherited. Move the "
            "profile to schema_version 9, rename the baseline key to "
            "outbound_transport, and RE-MEASURE it with the engine"
        )
    if version != 9:
        raise ProfileError("schema_version must be integer 9")
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
    vocabularies = tuple(
        _vocabulary(item, index)
        for index, item in enumerate(
            _sequence(
                data["module_declared_vocabularies"], "module_declared_vocabularies"
            )
        )
    )
    if not authorities or not surfaces:
        raise ProfileError("authorities and typed_contract_surfaces must not be empty")
    if len({item.authority_id for item in authorities}) != len(authorities):
        raise ProfileError("authority_id values must be unique")
    if len({item.surface_id for item in surfaces}) != len(surfaces):
        raise ProfileError("surface_id values must be unique")
    if len({item.vocabulary_id for item in vocabularies}) != len(vocabularies):
        raise ProfileError("vocabulary_id values must be unique")
    connector_surface = _external_connector_surface(data["external_connector_surface"])
    return StandardsProfile(
        schema_version=9,
        profile_id=ProfileId(_slug(data["profile_id"], "profile_id")),
        repository=_repository(data["repository"]),
        governance_model=governance,
        enforcement_mode=mode,
        authorities=authorities,
        typed_contract_surfaces=surfaces,
        module_declared_vocabularies=vocabularies,
        testing_kit_boundary=_testing_kit_boundary(data["testing_kit_boundary"]),
        external_connector_surface=connector_surface,
    )


def load_profile(path: Path) -> StandardsProfile:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ProfileError(f"cannot read profile {path}: {error}") from error
    return parse_profile(value)
