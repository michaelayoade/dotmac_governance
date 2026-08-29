"""Single policy engine for repository engineering conformance."""

from __future__ import annotations

import ast
import copy
import functools
import hashlib
import importlib
import ipaddress
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import NamedTuple
from urllib.parse import urlsplit

from .contracts import (
    CONSERVED_MODULE_SYMBOL,
    BranchName,
    CanonicalRepository,
    ConformanceReport,
    ConnectorCategory,
    ConnectorScope,
    ConservedFinding,
    DeploymentArtefactSurface,
    Diagnostic,
    DiagnosticCode,
    ExcludedSource,
    GitRevision,
    ModuleDeclaredVocabulary,
    PinnedGovernanceModelRef,
    Severity,
    StandardsProfile,
    TestingKitBoundary,
    TypedContractSurface,
    VocabularyMemberKind,
)
from .profile import ProfileError, load_profile

STATUS_LINE = re.compile(r"^- Status:\s*(Proposed|Accepted)\s*$", re.MULTILINE)
BARE_CONTAINERS = frozenset(
    {"dict", "list", "set", "tuple", "Mapping", "Sequence", "Iterable"}
)
CONTROL_PLANE_REPOSITORY = CanonicalRepository(
    "https://github.com/michaelayoade/dotmac_governance"
)
# Base names that make a class a CLOSED vocabulary: its members are fixed at the
# hosting layer's source, which is exactly what a module-declared vocabulary
# must not be. Matched on the terminal name, so `enum.Enum` and `Enum` both hit.
CLOSED_MEMBER_BASES = frozenset({"Enum", "IntEnum", "StrEnum", "Flag", "IntFlag"})
# Callables that pin a database column to a fixed member list.
CLOSED_STORAGE_CALLS = frozenset({"Enum", "ENUM"})
TESTING_KIT_MODULE = "dotmac_kernel.testing"
CONNECTOR_RUNTIME_AUTHORITY_PATH = PurePosixPath(
    "policies/external-connector-runtime-authority.json"
)
CONNECTOR_DISTRIBUTION_PREFIX = "dotmac-connector-"


class _ConnectorRuntimeAuthority(NamedTuple):
    runtime_host: CanonicalRepository
    source_repositories: frozenset[CanonicalRepository]


class _ConnectorLockEntry(NamedTuple):
    name: str
    version: str
    groups: tuple[str, ...]
    source_directory: PurePosixPath | None


def _finding(
    code: DiagnosticCode,
    message: str,
    *,
    path: PurePosixPath | None = None,
    line: int | None = None,
) -> Diagnostic:
    return Diagnostic(code, Severity.ERROR, message, path, line)


def _notice(
    code: DiagnosticCode,
    message: str,
    *,
    path: PurePosixPath | None = None,
) -> Diagnostic:
    """A published observation, not a failure: notices never fail a run."""
    return Diagnostic(code, Severity.NOTICE, message, path, None)


def _normalize_url(raw: str) -> CanonicalRepository | None:
    value = raw.strip()
    if value.startswith("git@") and ":" in value:
        authority, repository_path = value.split(":", 1)
        host = authority.split("@", 1)[1]
    else:
        parsed = urlsplit(value)
        if parsed.scheme not in {"https", "ssh"} or parsed.hostname is None:
            return None
        host = parsed.hostname
        repository_path = parsed.path.lstrip("/")
    repository_path = repository_path.removesuffix(".git").rstrip("/")
    if repository_path.count("/") != 1:
        return None
    return CanonicalRepository(f"https://{host.lower()}/{repository_path}")


def _connector_runtime_authority(
    governance_root: Path | None,
) -> tuple[_ConnectorRuntimeAuthority | None, str | None]:
    """Load the one Governance-owned answer to who may install connectors."""
    if governance_root is None:
        return None, "the pinned Governance root was not supplied"
    path = governance_root / CONNECTOR_RUNTIME_AUTHORITY_PATH
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return None, f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: {type(error).__name__}"
    if not isinstance(raw, dict):
        return None, f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: expected an object"
    if set(raw) != {"schema_version", "runtime_host", "source_repositories"}:
        return None, (
            f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: expected exactly schema_version, "
            "runtime_host and source_repositories"
        )
    schema_version = raw["schema_version"]
    if isinstance(schema_version, bool) or schema_version != 1:
        return None, f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: schema_version must be 1"
    runtime_host_raw = raw["runtime_host"]
    if not isinstance(runtime_host_raw, str):
        return None, f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: runtime_host must be a URL"
    runtime_host = _normalize_url(runtime_host_raw)
    if runtime_host is None:
        return None, f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: runtime_host is invalid"
    sources_raw = raw["source_repositories"]
    if not isinstance(sources_raw, list):
        return None, (
            f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: source_repositories must be a list"
        )
    sources: set[CanonicalRepository] = set()
    for index, source_raw in enumerate(sources_raw):
        if not isinstance(source_raw, str):
            return None, (
                f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: "
                f"source_repositories[{index}] must be a URL"
            )
        source = _normalize_url(source_raw)
        if source is None:
            return None, (
                f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: "
                f"source_repositories[{index}] is invalid"
            )
        if source == runtime_host:
            return None, (
                f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: the runtime host cannot also "
                "be a source-only repository"
            )
        if source in sources:
            return None, (
                f"{CONNECTOR_RUNTIME_AUTHORITY_PATH}: source repository {source!r} "
                "is duplicated"
            )
        sources.add(source)
    return _ConnectorRuntimeAuthority(runtime_host, frozenset(sources)), None


def _normalized_distribution_name(value: str) -> str:
    """PEP-503 spelling, so underscores cannot evade a prefix decision."""
    return re.sub(r"[-_.]+", "-", value).lower()


def _connector_lock_entries(
    root: Path,
) -> tuple[tuple[_ConnectorLockEntry, ...] | None, str | None]:
    """Read connector resolutions from Poetry's committed dependency authority."""
    path = root / "poetry.lock"
    tomllib = importlib.import_module("tomllib")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        return None, f"poetry.lock: {type(error).__name__}"
    packages = raw.get("package")
    if not isinstance(packages, list):
        return None, "poetry.lock: [[package]] entries are missing"
    entries: list[_ConnectorLockEntry] = []
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            return None, f"poetry.lock: package[{index}] is not an object"
        name = package.get("name")
        if not isinstance(name, str):
            return None, f"poetry.lock: package[{index}].name is not a string"
        if not _normalized_distribution_name(name).startswith(
            CONNECTOR_DISTRIBUTION_PREFIX
        ):
            continue
        version = package.get("version")
        groups = package.get("groups")
        if not isinstance(version, str):
            return None, (
                f"poetry.lock: connector package {name!r} has no string version"
            )
        if (
            not isinstance(groups, list)
            or not groups
            or any(not isinstance(group, str) for group in groups)
        ):
            return None, (
                f"poetry.lock: connector package {name!r} has no typed dependency "
                "groups, so runtime resolution cannot be decided"
            )
        entries.append(
            _ConnectorLockEntry(
                _normalized_distribution_name(name),
                version,
                tuple(sorted(set(groups))),
                _connector_directory_source(package.get("source")),
            )
        )
    return tuple(entries), None


def _connector_directory_source(value: object) -> PurePosixPath | None:
    """Return a Poetry directory source without treating it as trusted yet."""
    if not isinstance(value, dict) or value.get("type") != "directory":
        return None
    raw = value.get("url")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return PurePosixPath(raw)


def _connector_source_distribution_roots(
    root: Path,
    profile: StandardsProfile,
    *,
    governance_root: Path | None,
) -> tuple[PurePosixPath, ...]:
    """Prove authored connector roots that are not legacy product debt.

    This is intentionally derived from three independent authorities: the
    Governance-owned source-repository list, Poetry's committed resolution,
    and the distribution's connector entry point. A product profile cannot
    declare an exclusion, and an invalid candidate simply remains measured.
    """
    if not isinstance(profile.governance_model, PinnedGovernanceModelRef):
        return ()
    authority, _ = _connector_runtime_authority(governance_root)
    if (
        authority is None
        or profile.repository.canonical_url not in authority.source_repositories
    ):
        return ()
    entries, _ = _connector_lock_entries(root)
    if entries is None:
        return ()

    repository_root = root.resolve()
    tomllib = importlib.import_module("tomllib")
    proven: set[PurePosixPath] = set()
    for entry in entries:
        relative = entry.source_directory
        if relative is None or "main" in entry.groups:
            continue
        if relative.is_absolute() or relative in {PurePosixPath("."), PurePosixPath()}:
            continue
        if ".." in relative.parts:
            continue
        package_root = root.joinpath(*relative.parts)
        try:
            resolved_package_root = package_root.resolve(strict=True)
            resolved_package_root.relative_to(repository_root)
        except (OSError, ValueError):
            continue
        if resolved_package_root != repository_root.joinpath(*relative.parts):
            # A source path routed through a symlink can select an unrelated
            # region of the repository (or leave it) and is not provenance.
            continue
        metadata_path = package_root / "pyproject.toml"
        try:
            metadata = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError):
            continue
        tool = metadata.get("tool")
        poetry = tool.get("poetry") if isinstance(tool, dict) else None
        if not isinstance(poetry, dict):
            continue
        declared_name = poetry.get("name")
        if (
            not isinstance(declared_name, str)
            or _normalized_distribution_name(declared_name) != entry.name
        ):
            continue
        plugins = poetry.get("plugins")
        connector_plugins = (
            plugins.get("dotmac_integration.connectors")
            if isinstance(plugins, dict)
            else None
        )
        if not isinstance(connector_plugins, dict) or not connector_plugins:
            continue
        if any(
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(target, str)
            or not target.strip()
            for key, target in connector_plugins.items()
        ):
            continue
        proven.add(relative)
    return tuple(sorted(proven, key=PurePosixPath.as_posix))


def _outside_connector_source_distributions(
    inventory: tuple[PurePosixPath, ...] | None,
    roots: tuple[PurePosixPath, ...],
) -> tuple[PurePosixPath, ...] | None:
    if inventory is None or not roots:
        return inventory
    return tuple(
        relative
        for relative in inventory
        if not any(
            relative == package or package in relative.parents for package in roots
        )
    )


def _connector_runtime_dependencies(
    root: Path,
    profile: StandardsProfile,
    *,
    governance_root: Path | None,
) -> list[Diagnostic]:
    """Enforce ADR-0011 S2 from a Governance-owned authority and the lock."""
    if not isinstance(profile.governance_model, PinnedGovernanceModelRef):
        # Governance itself is policy source, not an enrolled product
        # distribution. Products and the Integrator consume a pinned source.
        return []
    authority, authority_error = _connector_runtime_authority(governance_root)
    if authority is None:
        return [
            _finding(
                DiagnosticCode.CONNECTOR_RUNTIME_AUTHORITY_UNAVAILABLE,
                "cannot decide which repository may resolve connector "
                f"distributions: {authority_error}",
                path=CONNECTOR_RUNTIME_AUTHORITY_PATH,
            )
        ]
    entries, lock_error = _connector_lock_entries(root)
    if entries is None:
        return [
            _finding(
                DiagnosticCode.CONNECTOR_DEPENDENCY_LOCK_UNAVAILABLE,
                f"cannot prove the connector runtime dependency boundary: {lock_error}",
                path=PurePosixPath("poetry.lock"),
            )
        ]

    repository = profile.repository.canonical_url
    findings: list[Diagnostic] = []
    for entry in entries:
        allowed = repository == authority.runtime_host or (
            repository in authority.source_repositories and "main" not in entry.groups
        )
        if allowed:
            continue
        findings.append(
            _finding(
                DiagnosticCode.CONNECTOR_RUNTIME_DEPENDENCY_FORBIDDEN,
                f"{entry.name} {entry.version} resolves in dependency groups "
                f"{', '.join(entry.groups)}. Only the Governance-declared "
                "Integrator runtime host may resolve a connector at runtime; "
                "source repositories may resolve one only outside the main "
                "runtime group, and products may resolve none",
                path=PurePosixPath("poetry.lock"),
            )
        )
    return findings


def _git(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _git_origin(root: Path) -> CanonicalRepository | None:
    observed = _git(root, "remote", "get-url", "origin")
    return _normalize_url(observed) if observed is not None else None


def _git_default_branch(root: Path) -> BranchName | None:
    observed = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if observed is None or not observed.startswith("origin/"):
        return None
    return BranchName(observed.removeprefix("origin/"))


def _governance(
    root: Path,
    profile: StandardsProfile,
    *,
    governance_root: Path | None,
    observed_governance_repository: CanonicalRepository | None,
    observed_governance_revision: GitRevision | None,
) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    model = profile.governance_model
    source_root = root
    if not isinstance(model, PinnedGovernanceModelRef):
        if profile.repository.canonical_url != CONTROL_PLANE_REPOSITORY:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_LOCAL_SOURCE_FORBIDDEN,
                    "only the Governance control-plane repository may use a "
                    "local governance source",
                )
            )
    else:
        if model.canonical_url != CONTROL_PLANE_REPOSITORY:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_REPOSITORY_MISMATCH,
                    f"profile must pin the Governance control plane "
                    f"{CONTROL_PLANE_REPOSITORY!r}, found {model.canonical_url!r}",
                )
            )
        if governance_root is None:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_ROOT_UNAVAILABLE,
                    "pinned governance source root is unavailable",
                )
            )
        else:
            source_root = governance_root
        if observed_governance_repository is None:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_REPOSITORY_UNAVAILABLE,
                    "pinned governance repository identity is unavailable",
                )
            )
        elif observed_governance_repository != model.canonical_url:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_REPOSITORY_MISMATCH,
                    f"expected governance repository {model.canonical_url!r}, "
                    f"found {observed_governance_repository!r}",
                )
            )
        if observed_governance_revision is None:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_REVISION_UNAVAILABLE,
                    "pinned governance revision is unavailable",
                )
            )
        elif observed_governance_revision != model.revision:
            findings.append(
                _finding(
                    DiagnosticCode.GOVERNANCE_REVISION_MISMATCH,
                    f"expected governance revision {model.revision!r}, "
                    f"found {observed_governance_revision!r}",
                )
            )
    relative = model.source
    source = source_root / relative
    if not source.is_file():
        findings.append(
            _finding(
                DiagnosticCode.GOVERNANCE_SOURCE_MISSING,
                "governance source is missing",
                path=relative,
            )
        )
        return findings
    try:
        statuses = STATUS_LINE.findall(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        statuses = []
    if len(statuses) != 1:
        findings.append(
            _finding(
                DiagnosticCode.GOVERNANCE_SOURCE_STATUS_MISSING,
                "governance source needs exactly one controlled status",
                path=relative,
            )
        )
        return findings
    observed = statuses[0].lower()
    expected = model.status.value
    if observed != expected:
        findings.append(
            _finding(
                DiagnosticCode.GOVERNANCE_SOURCE_STATUS_MISMATCH,
                f"profile expects status {expected!r}, found {observed!r}",
                path=relative,
            )
        )
    return findings


def _symbols(path: Path) -> frozenset[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeError, SyntaxError):
        return frozenset()
    return frozenset(
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )


def _implementation_modules(path: PurePosixPath) -> frozenset[str]:
    """Return importable module names represented by a repository path.

    Flat layouts map the whole repository-relative path. Standard ``src``
    layouts map from the segment after ``src``; this also covers a package in a
    monorepo such as ``packages/kernel/src/dotmac_kernel/db.py`` without
    pretending that ``packages.kernel.src`` is importable.
    """
    parts = PurePosixPath(path.as_posix().removesuffix(".py")).parts
    source_roots = [index for index, part in enumerate(parts[:-1]) if part == "src"]
    module_parts = parts[source_roots[-1] + 1 :] if source_roots else parts
    return frozenset({".".join(module_parts)})


def _authorities(root: Path, profile: StandardsProfile) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    owners: dict[str, str] = {}
    for authority in profile.authorities:
        authority_id = str(authority.authority_id)
        for resource in authority.protected_resources:
            resource_id = str(resource)
            prior = owners.get(resource_id)
            if prior is not None:
                findings.append(
                    _finding(
                        DiagnosticCode.AUTHORITY_RESOURCE_DUPLICATE,
                        f"resource {resource_id!r} has owners {prior!r} and {authority_id!r}",
                    )
                )
            else:
                owners[resource_id] = authority_id
        if authority.owner_implementation not in authority.canonical_writer_paths:
            findings.append(
                _finding(
                    DiagnosticCode.AUTHORITY_OWNER_NOT_WRITER,
                    f"owner for {authority_id!r} is not a canonical writer",
                    path=authority.owner_implementation,
                )
            )
        for relative in sorted(
            set(authority.canonical_writer_paths) & set(authority.adapter_paths),
            key=lambda item: item.as_posix(),
        ):
            findings.append(
                _finding(
                    DiagnosticCode.AUTHORITY_ADAPTER_WRITER_OVERLAP,
                    f"{authority_id!r} classifies one path as writer and adapter",
                    path=relative,
                )
            )
        paths = (
            authority.owner_implementation,
            *authority.canonical_writer_paths,
            *authority.adapter_paths,
            *authority.drift_test_paths,
        )
        for relative in paths:
            if not (root / relative).is_file():
                findings.append(
                    _finding(
                        DiagnosticCode.AUTHORITY_PATH_MISSING,
                        f"declared path for {authority_id!r} is missing",
                        path=relative,
                    )
                )
        module, _, symbol = str(authority.decision_interface).rpartition(".")
        expected_modules = _implementation_modules(authority.owner_implementation)
        if module not in expected_modules or symbol not in _symbols(
            root / authority.owner_implementation
        ):
            findings.append(
                _finding(
                    DiagnosticCode.AUTHORITY_INTERFACE_MISSING,
                    f"decision interface for {authority_id!r} is absent from its owner",
                    path=authority.owner_implementation,
                )
            )
    return findings


def _name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _annotation_findings(node: ast.expr) -> tuple[tuple[DiagnosticCode, int], ...]:
    result: list[tuple[DiagnosticCode, int]] = []

    def visit(annotation: ast.expr, *, base: bool = False) -> None:
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            try:
                visit(ast.parse(annotation.value, mode="eval").body)
            except SyntaxError:
                pass
            return
        terminal = _name(annotation)
        if terminal == "Any":
            result.append((DiagnosticCode.CONTRACT_ANY_FORBIDDEN, annotation.lineno))
            return
        if terminal in BARE_CONTAINERS and not base:
            result.append((DiagnosticCode.CONTRACT_BARE_CONTAINER, annotation.lineno))
            return
        if isinstance(annotation, ast.Subscript):
            visit(annotation.value, base=True)
            visit(annotation.slice)
            return
        for child in ast.iter_child_nodes(annotation):
            if isinstance(child, ast.expr):
                visit(child)

    visit(node)
    return tuple(result)


def _function_annotations(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterable[tuple[str, ast.expr | None, int]]:
    arguments = (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
    for argument in arguments:
        if argument.arg not in {"self", "cls"}:
            yield argument.arg, argument.annotation, argument.lineno
    if node.args.vararg is not None:
        yield node.args.vararg.arg, node.args.vararg.annotation, node.args.vararg.lineno
    if node.args.kwarg is not None:
        yield node.args.kwarg.arg, node.args.kwarg.annotation, node.args.kwarg.lineno
    yield "return", node.returns, node.lineno


def _dataclass(node: ast.ClassDef) -> ast.expr | None:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if _name(target) == "dataclass":
            return decorator
    return None


def _dataclass_frozen(decorator: ast.expr) -> bool:
    return isinstance(decorator, ast.Call) and any(
        keyword.arg == "frozen"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in decorator.keywords
    )


def _pydantic_frozen(node: ast.ClassDef) -> bool:
    for statement in node.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == "model_config"
            for target in targets
        ):
            continue
        value = statement.value
        if isinstance(value, ast.Call) and _name(value.func) == "ConfigDict":
            return any(
                keyword.arg == "frozen"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in value.keywords
            )
    return False


def _parse(root: Path, relative: PurePosixPath) -> ast.Module | Diagnostic:
    source = root / relative
    if not source.is_file():
        return _finding(
            DiagnosticCode.VOCABULARY_PATH_MISSING,
            "declared vocabulary path is missing",
            path=relative,
        )
    try:
        return ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    except (OSError, UnicodeError, SyntaxError) as error:
        return _finding(
            DiagnosticCode.VOCABULARY_SYNTAX_INVALID,
            "declared vocabulary path is not valid UTF-8 Python",
            path=relative,
            line=error.lineno if isinstance(error, SyntaxError) else None,
        )


def _annotated_field(tree: ast.Module, field: str) -> bool:
    """True when some class in `tree` annotates `field` — the declaration slot."""
    return any(
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == field
        for klass in ast.walk(tree)
        if isinstance(klass, ast.ClassDef)
        for node in klass.body
    )


def _closed_storage(tree: ast.Module, column: str) -> int | None:
    """Line of a column definition that pins `column` to a fixed member list.

    Two shapes close a column: a database enum type (`Enum(...)`/`ENUM(...)`
    anywhere in the column expression) and a CHECK constraint naming the column
    with a literal `IN (...)` list. Both re-impose the closed set the registry
    exists to open, and both cost the hosting layer a migration per consumer.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == column
            and node.value is not None
        ):
            for child in ast.walk(node.value):
                if isinstance(child, ast.Call) and _name(child.func) in (
                    CLOSED_STORAGE_CALLS
                ):
                    return child.lineno
        # Only inside a CheckConstraint call, never any string that happens to
        # contain the phrase: a docstring explaining the rule must not trip it.
        if isinstance(node, ast.Call) and _name(node.func) == "CheckConstraint":
            for child in ast.walk(node):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    text = " ".join(child.value.split()).lower()
                    if f"{column.lower()} in (" in text:
                        return child.lineno
    return None


def _vocabulary(root: Path, vocabulary: ModuleDeclaredVocabulary) -> list[Diagnostic]:
    """One module-declared vocabulary is open, registered, and unpinned.

    The failures correspond to the ways the rule is broken in practice: a
    declared member type is an enum again; nothing validates a member; or a
    real persisted column re-closes what the registry opened.
    """
    findings: list[Diagnostic] = []
    identifier = str(vocabulary.vocabulary_id)

    member = vocabulary.member_type
    if member.kind is VocabularyMemberKind.DECLARED:
        if member.path is None:  # impossible after strict profile parsing
            raise AssertionError("declared vocabulary member has no source path")
        member_tree = _parse(root, member.path)
        if isinstance(member_tree, Diagnostic):
            findings.append(member_tree)
        else:
            declared = [
                node
                for node in ast.walk(member_tree)
                if isinstance(node, ast.ClassDef) and node.name == member.name
            ]
            if not declared:
                findings.append(
                    _finding(
                        DiagnosticCode.VOCABULARY_MEMBER_TYPE_MISSING,
                        f"member type for {identifier!r} is absent from its declared path",
                        path=member.path,
                    )
                )
            for node in declared:
                if any(_name(base) in CLOSED_MEMBER_BASES for base in node.bases):
                    findings.append(
                        _finding(
                            DiagnosticCode.VOCABULARY_MEMBER_TYPE_CLOSED,
                            f"member type for {identifier!r} enumerates its members; a "
                            "module-declared vocabulary is an open registered value",
                            path=member.path,
                            line=node.lineno,
                        )
                    )

    registry_tree = _parse(root, vocabulary.registry_implementation)
    if isinstance(registry_tree, Diagnostic):
        findings.append(registry_tree)
    else:
        module, _, symbol = str(vocabulary.registry_interface).rpartition(".")
        expected = _implementation_modules(vocabulary.registry_implementation)
        if module not in expected or symbol not in _symbols(
            root / vocabulary.registry_implementation
        ):
            findings.append(
                _finding(
                    DiagnosticCode.VOCABULARY_REGISTRY_MISSING,
                    f"registry interface for {identifier!r} is absent from its "
                    "declared implementation",
                    path=vocabulary.registry_implementation,
                )
            )

    for relative in vocabulary.declaration_paths:
        tree = _parse(root, relative)
        if isinstance(tree, Diagnostic):
            findings.append(tree)
        elif not _annotated_field(tree, vocabulary.declaration_field):
            findings.append(
                _finding(
                    DiagnosticCode.VOCABULARY_DECLARATION_MISSING,
                    f"{vocabulary.declaration_field!r} is not a declared field here, "
                    f"so a module cannot declare a member of {identifier!r}",
                    path=relative,
                )
            )

    if vocabulary.storage is not None:
        for relative in vocabulary.storage.paths:
            tree = _parse(root, relative)
            if isinstance(tree, Diagnostic):
                findings.append(tree)
                continue
            line = _closed_storage(tree, vocabulary.storage.column)
            if line is not None:
                findings.append(
                    _finding(
                        DiagnosticCode.VOCABULARY_STORAGE_CLOSED,
                        f"storage for {identifier!r} pins "
                        f"{vocabulary.storage.column!r} to a fixed member list; "
                        "the write boundary is the enforcement point, not the column",
                        path=relative,
                        line=line,
                    )
                )

    return findings


def _typed(root: Path, surface: TypedContractSurface) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    for relative in surface.paths:
        source = root / relative
        if not source.is_file():
            findings.append(
                _finding(
                    DiagnosticCode.CONTRACT_PATH_MISSING,
                    "typed contract path is missing",
                    path=relative,
                )
            )
            continue
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (OSError, UnicodeError, SyntaxError) as error:
            line = error.lineno if isinstance(error, SyntaxError) else None
            findings.append(
                _finding(
                    DiagnosticCode.CONTRACT_SYNTAX_INVALID,
                    "typed contract is not valid UTF-8 Python",
                    path=relative,
                    line=line,
                )
            )
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and surface.require_public_annotations
                and not node.name.startswith("_")
            ):
                for role, annotation, line in _function_annotations(node):
                    if annotation is None:
                        findings.append(
                            _finding(
                                DiagnosticCode.CONTRACT_ANNOTATION_MISSING,
                                f"{node.name!r} {role!r} lacks an annotation",
                                path=relative,
                                line=line,
                            )
                        )
                    else:
                        for code, annotation_line in _annotation_findings(annotation):
                            if (
                                code is not DiagnosticCode.CONTRACT_ANY_FORBIDDEN
                                or surface.forbid_any
                            ):
                                findings.append(
                                    _finding(
                                        code,
                                        f"{node.name!r} uses a forbidden annotation",
                                        path=relative,
                                        line=annotation_line,
                                    )
                                )
            if not isinstance(node, ast.ClassDef):
                continue
            dataclass_decorator = _dataclass(node)
            is_pydantic = any(_name(base) == "BaseModel" for base in node.bases)
            if dataclass_decorator is None and not is_pydantic:
                continue
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if (
                            isinstance(target, ast.Name)
                            and not target.id.startswith("_")
                            and target.id != "model_config"
                        ):
                            findings.append(
                                _finding(
                                    DiagnosticCode.CONTRACT_ANNOTATION_MISSING,
                                    f"record field {node.name}.{target.id} lacks an annotation",
                                    path=relative,
                                    line=statement.lineno,
                                )
                            )
                if isinstance(statement, ast.AnnAssign):
                    for code, annotation_line in _annotation_findings(
                        statement.annotation
                    ):
                        if (
                            code is not DiagnosticCode.CONTRACT_ANY_FORBIDDEN
                            or surface.forbid_any
                        ):
                            findings.append(
                                _finding(
                                    code,
                                    f"record {node.name!r} uses a forbidden annotation",
                                    path=relative,
                                    line=annotation_line,
                                )
                            )
            if surface.require_immutable_records:
                immutable = (
                    _dataclass_frozen(dataclass_decorator)
                    if dataclass_decorator is not None
                    else _pydantic_frozen(node)
                )
                if not immutable:
                    findings.append(
                        _finding(
                            DiagnosticCode.CONTRACT_RECORD_MUTABLE,
                            f"boundary record {node.name!r} is mutable",
                            path=relative,
                            line=node.lineno,
                        )
                    )
    return findings


def _testing_kit_import_lines(tree: ast.Module) -> tuple[int, ...]:
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == TESTING_KIT_MODULE or alias.name.startswith(
                    f"{TESTING_KIT_MODULE}."
                ):
                    lines.append(node.lineno)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module == TESTING_KIT_MODULE or module.startswith(
                f"{TESTING_KIT_MODULE}."
            ):
                lines.append(node.lineno)
            elif module == "dotmac_kernel" and any(
                alias.name == "testing" for alias in node.names
            ):
                lines.append(node.lineno)
    return tuple(lines)


#: Cap on how far into a file the engine looks for an interpreter line. A
#: shebang is the first line or it is not a shebang.
SHEBANG_BYTES = 256


def _git_paths(root: Path, *arguments: str) -> tuple[PurePosixPath, ...] | None:
    """Run one NUL-separated `git ls-files` query, or None when Git cannot."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", *arguments],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return tuple(PurePosixPath(raw) for raw in result.stdout.split("\0") if raw)


#: Suffixes that make a path a Python source on the strength of the INDEX
#: ENTRY alone. Reading the working tree to answer this question let the
#: working tree decide what the index measured: a tracked source deleted from
#: the checkout, a tracked symlink dangling until the build materialises its
#: target, and a path excluded by a sparse checkout each turned a red tree
#: green with no diagnostic at all. What ships is what is tracked, so the
#: bytes being absent is a finding, never an exemption.
PYTHON_SUFFIXES = frozenset({".py", ".pyw"})


def _parses_as_python(source: Path) -> bool:
    """Does this file actually parse as Python?"""
    try:
        ast.parse(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, SyntaxError, ValueError):
        return False
    return True


def _is_python_source(root: Path, relative: PurePosixPath) -> bool:
    """Is this repository path a Python source?

    Suffix first, then the interpreter line, because a repository's real entry
    points are routinely extensionless — `tools/dotmac-standards` in this
    repository is one. A universe that only knew `*.py` would leave every such
    launcher unmeasured.

    An extensionless file that CLAIMS Python is Python, so a broken entry point
    is still reported rather than dropped. One that claims something else is
    admitted on the evidence of parsing, because `b"python" in head` is a guess
    at an open vocabulary: `uv run --script`, `pypy3`, `pipenv-shebang`,
    `poetry run`, `hatch`, `nix-shell` and an sh/Python polyglot all launch
    Python without the word ever appearing, and each one was a tracked file
    that was neither measured, nor excluded, nor untracked.
    """
    if relative.suffix in PYTHON_SUFFIXES:
        return True
    if relative.suffix:
        return False
    source = root / relative
    if not source.is_file():
        return False
    try:
        with source.open("rb") as handle:
            head = handle.readline(SHEBANG_BYTES)
    except OSError:
        return False
    if not head.startswith(b"#!"):
        return False
    if b"python" in head:
        return True
    return _parses_as_python(source)


def _index_entries(root: Path) -> tuple[tuple[str, PurePosixPath], ...]:
    """`(mode, path)` for every index entry, or empty when Git cannot answer."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--stage"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    if result.returncode != 0:
        return ()
    entries: list[tuple[str, PurePosixPath]] = []
    for entry in result.stdout.split("\0"):
        if not entry:
            continue
        metadata, _, name = entry.partition("\t")
        if name:
            entries.append((metadata.split(" ", 1)[0], PurePosixPath(name)))
    return tuple(entries)


def _grafted_trees(root: Path) -> tuple[PurePosixPath, ...]:
    """Index entries that graft a tree this index does not contain.

    Two shapes, one mechanism. A submodule is ONE entry at mode 160000, and a
    symlink to a directory outside the repository is ONE entry at mode 120000.
    In both cases `--cached` lists the entry and never its contents, and
    `--others` does not descend through it, so an entire importable package can
    sit in the working tree, be imported and run, and appear in no universe
    derived here.

    A gitlink is reported without looking inside it: whether the nested tree
    holds Python is a property of the WORKING TREE, and a region whose
    measurability can change without this repository's index changing is
    unmonitored — the same reason a product-authored `.gitignore` is not an
    input to measurement. A symlink whose target resolves back INSIDE this
    repository grafts nothing: those contents are tracked here on their own.
    """
    try:
        resolved_root = root.resolve()
    except OSError:
        return ()
    paths: list[PurePosixPath] = []
    for mode, relative in _index_entries(root):
        if mode == "160000":
            paths.append(relative)
            continue
        if mode != "120000":
            continue
        try:
            target = (root / relative).resolve()
            if not target.is_dir():
                continue
            if target == resolved_root or resolved_root in target.parents:
                continue
        except OSError:
            continue
        paths.append(relative)
    return tuple(sorted(set(paths), key=lambda path: path.as_posix()))


def _tracked_python_sources(root: Path) -> tuple[PurePosixPath, ...] | None:
    """The closed universe: every Python source in the repository's index.

    Derived, never declared. `--cached` alone is the whole point of this
    function: `--exclude-standard` would let a product-authored `.gitignore`
    decide what is measured, and `--others` would let a file that is not in the
    repository at all inflate a count. What ships is what is tracked.
    """
    tracked = _git_paths(root, "--cached")
    if tracked is None:
        return None
    return tuple(
        sorted(
            {relative for relative in tracked if _is_python_source(root, relative)},
            key=lambda path: path.as_posix(),
        )
    )


class UntrackedPopulations(NamedTuple):
    """Python on disk but outside the index, enumerated as distinct populations.

    * `visible` — untracked and NOT ignored: what a plain checkout shows.
    * `ignored` — untracked AND hidden by this repository's own ignore rules.

    Both `visible` and `ignored` are errors. The split exists so the two are
    REPORTED separately, not so one of them can be forgiven: an ignore file is
    product-authored and decides nothing about what is measured.
    """

    visible: tuple[PurePosixPath, ...]
    ignored: tuple[PurePosixPath, ...]


def _untracked_python_populations(root: Path) -> UntrackedPopulations:
    """Python sources present on disk but absent from the index.

    Reported, not measured, and not skipped either. Such a region is
    unmonitored rather than exempt: the engine cannot claim a zero over code
    whose provenance the repository does not record.

    `--exclude-standard` is deliberately NOT passed to the inventory query.
    Every untracked Python source remains an error, including installed package
    contents and generated console shims inside an in-repository environment.
    METADATA and RECORD are controlled by the same working tree and therefore
    cannot authorize source out of this population. The ignore query is run
    SEPARATELY and used only to split the report. When it cannot be answered,
    no source is classified as ignored — the split fails toward the louder
    half.
    """
    others = _git_paths(root, "--others")
    if others is None:
        return UntrackedPopulations((), ())
    sources = sorted(
        {relative for relative in others if _is_python_source(root, relative)},
        key=lambda path: path.as_posix(),
    )
    unignored = _git_paths(root, "--others", "--exclude-standard")
    not_ignored = frozenset(unignored) if unignored is not None else frozenset(sources)

    visible: list[PurePosixPath] = []
    ignored: list[PurePosixPath] = []
    for relative in sources:
        (visible if relative in not_ignored else ignored).append(relative)
    return UntrackedPopulations(tuple(visible), tuple(ignored))


def _inside(relative: PurePosixPath, roots: tuple[PurePosixPath, ...]) -> bool:
    return any(relative == root or root in relative.parents for root in roots)


def _testing_kit(
    root: Path,
    boundary: TestingKitBoundary,
    sources: tuple[PurePosixPath, ...],
) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    for relative in (*boundary.test_roots, *boundary.kit_source_roots):
        if not (root / relative).is_dir():
            findings.append(
                _finding(
                    DiagnosticCode.TESTING_KIT_PATH_MISSING,
                    "declared testing-kit boundary root is missing",
                    path=relative,
                )
            )
    probe_by_path = {probe.path: probe for probe in boundary.conformance_probes}
    existing_probes: set[PurePosixPath] = set()
    for probe in boundary.conformance_probes:
        if not (root / probe.path).is_file():
            findings.append(
                _finding(
                    DiagnosticCode.TESTING_KIT_PATH_MISSING,
                    "declared testing-kit conformance probe is missing",
                    path=probe.path,
                )
            )
        else:
            existing_probes.add(probe.path)

    observed_probe_counts: dict[PurePosixPath, int] = {}
    unparseable: set[PurePosixPath] = set()
    for relative in sources:
        source = root / relative
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (OSError, UnicodeError, SyntaxError) as error:
            unparseable.add(relative)
            line = error.lineno if isinstance(error, SyntaxError) else None
            findings.append(
                _finding(
                    DiagnosticCode.TESTING_KIT_SYNTAX_INVALID,
                    f"cannot inspect Python source for testing-kit imports: {error}",
                    path=relative,
                    line=line,
                )
            )
            continue
        lines = _testing_kit_import_lines(tree)
        if relative in probe_by_path:
            observed_probe_counts[relative] = len(lines)
            continue
        if (
            not lines
            or _inside(relative, boundary.test_roots)
            or _inside(relative, boundary.kit_source_roots)
        ):
            continue
        findings.extend(
            _finding(
                DiagnosticCode.TESTING_KIT_IMPORT_FORBIDDEN,
                "dotmac_kernel.testing is development-only; import it from a "
                "structural test root or an exact declared conformance probe",
                path=relative,
                line=line,
            )
            for line in lines
        )

    for probe in boundary.conformance_probes:
        if probe.path not in existing_probes or probe.path in unparseable:
            continue
        observed = observed_probe_counts.get(probe.path, 0)
        if observed != probe.expected_import_count:
            findings.append(
                _finding(
                    DiagnosticCode.TESTING_KIT_PROBE_COUNT_MISMATCH,
                    "testing-kit conformance probe import count drifted: "
                    f"expected {probe.expected_import_count}, found {observed}",
                    path=probe.path,
                )
            )
    return findings


# --- External connector surface (ADR 0011) --------------------------------
#
# Ported from the starter's proven sweep. Every rule is narrow and AST-grounded
# on purpose: a ratchet that fires on hundreds of lines gets switched off, and
# an honest undercount that shrinks beats an overcount nobody trusts. What each
# rule does NOT see is part of the contract, stated in ADR 0011.
#
# This family INVENTORIES AND FREEZES legacy debt during the Integrator
# migration. It is DEFENCE IN DEPTH, NOT RUNTIME ISOLATION: a green run says
# the measured spellings did not grow, never that the product cannot reach a
# provider. Two protocols are recognised — HTTP and SMTP — and everything else
# (brokers, gRPC, sockets, SSH/SFTP, SNMP, database links, SDKs whose transport
# is not a named client library) is UNMONITORED rather than exempt. Adding a
# protocol is an ARM with its own three ADR 0018 legs and a schema version. The
# rule family has a stated end; see ADR 0011's amendment of 2026-08-16, "What
# this record is, and what it is never going to be".

# There is deliberately no list of directory names that are "never runtime".
# Nothing checks that a directory called `migrations` contains migrations, so
# skipping it leaves that region UNMONITORED rather than exempt. A connector in
# a migration is a finding.
#: `outbound_transport` is ONE category with TWO arms, and the arms are listed
#: here so a reader can see at a glance which protocols are measured and which
#: are not. The category was called `http_client` until 2026-08-15, which named
#: a transport rather than the concept, and an SMTP delivery task therefore had
#: nowhere to land — see ADR 0011, "The category is the concept, not one
#: transport". Adding a protocol means adding an ARM with its own three legs,
#: never widening one of these sets past what it names.
#
#: ARM 1, HTTP. Client libraries: importing one means making outbound calls here
#: rather than asking a control plane to make them.
HTTP_TRANSPORTS = frozenset({"httpx", "requests", "aiohttp", "urllib3", "http.client"})
#: Method names that actually issue a request. Importing a client for a type
#: annotation is not a connector, and this is what separates the two.
REQUEST_METHODS = frozenset(
    {"get", "post", "put", "patch", "delete", "head", "request", "stream", "send"}
)
#: httpx transports that execute requests in this process. They exercise a
#: client API but create no provider egress, so treating them as outbound makes
#: an in-memory fake indistinguishable from the connector it tests.
IN_PROCESS_HTTP_TRANSPORTS = frozenset(
    {"MockTransport", "ASGITransport", "WSGITransport"}
)
#: ARM 2, SMTP. Mail transport libraries. Unlike an HTTP client — whose
#: `Session` and `get` collide with an ORM and a mapping — these two libraries
#: speak one protocol and nothing else, which is why the arm's shape differs
#: from the HTTP arm's and says so rather than copying it.
SMTP_TRANSPORTS = frozenset({"smtplib", "aiosmtplib"})
#: Their connection constructors, matched only against a bound transport module
#: or an alias imported directly from one — never on the bare name, which is a
#: three-letter word an application is free to reuse.
SMTP_CONSTRUCTORS = frozenset({"SMTP", "SMTP_SSL"})
#: `sendmail` is smtplib's own verb for handing bytes to a relay. Nothing else
#: in the seven measured repositories spells it, so like `webhook` among the
#: route hints it stands on its own and reaches a client handed in under a name
#: this analysis cannot resolve.
MAIL_SEND_METHODS = frozenset({"sendmail"})
#: `send_message` does NOT stand on its own — asyncio queues, websocket
#: connections and broker clients all spell it — so it counts only alongside a
#: bound SMTP transport, the same qualification `callback` gets among the
#: webhook path hints.
AMBIGUOUS_MAIL_SEND_METHODS = frozenset({"send_message"})
#: Route literals that make a handler a provider callback rather than a product
#: API. Matched against a ROUTE decorator's path constant — see
#: `_decorator_path_literals` for why the decorator has to be a route.
#:
#: Split by how much the word commits to, the same way a bare `*Cursor` and a
#: bare `@app.task` are split. `webhook`, `/hooks`, `notify-url` and `ipn` name
#: a provider callback and nothing else, and stand on their own.
WEBHOOK_PATH_HINTS = ("webhook", "/hooks", "notify-url", "ipn")
#: `callback` does not. It is equally the URL a BROWSER is redirected to after
#: an OAuth consent screen or a hosted checkout page, and all three real
#: matches across the adopters are exactly that: `erp-adopt`'s
#: `/auth/oidc/callback` and its Paystack payment-return page, and
#: `crm-guardrails`'s Meta OAuth return. Qualified by the route's METHOD.
AMBIGUOUS_WEBHOOK_PATH_HINTS = ("callback",)
#: A route beneath one of these management segments ordinarily configures the
#: product's callback registrations; it is not itself the provider callback.
#: Such a route must read callback material before the path can stand as
#: webhook evidence. Exact path segments prevent `configuration` prose or an
#: arbitrary function name from qualifying the exception.
MANAGEMENT_ROUTE_SEGMENTS = frozenset(
    {"admin", "config", "configuration", "settings", "management"}
)
#: Decorator attributes that MOUNT A ROUTE. Everything else that takes a string
#: constant — a celery task's `name=`, a cache key, a feature flag — is not a
#: path, and reading one as a path is what made a queue identifier a webhook.
#: Matched as the final dotted part, so `@router.post`, `@app.post` and
#: `@blueprint.route` all count while `@celery_app.task` does not.
ROUTE_DECORATOR_ATTRS = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
        "route",
        "api_route",
        "websocket",
        "add_api_route",
        "add_route",
        "add_url_rule",
    }
)
#: The mutating half of the decorators that name their own method. A provider
#: POSTs an event; a browser GETs a redirect target.
MUTATING_ROUTE_ATTRS = frozenset({"post", "put", "patch", "delete"})
#: Route decorators that name no method in the attribute and take a `methods=`
#: argument instead (Flask, and FastAPI's generic `api_route`). Absent that
#: argument both frameworks default to GET alone.
GENERIC_ROUTE_ATTRS = frozenset(
    {"route", "api_route", "add_api_route", "add_route", "add_url_rule"}
)
ROUTE_METHODS_KEYWORD = "methods"
#: Authenticity verification of an inbound provider payload. Split by how much
#: the NAME itself commits to — see `_is_webhook_surface`.
WEBHOOK_VERIFY_HINTS = ("verify_signature", "verify_webhook", "check_signature")
#: The word that makes a verification function name its own subject. A
#: `verify_webhook_signature` says what it verifies; a bare `verify_signature`
#: does not, and is equally the licence, JWT, artefact or config-bundle check.
WEBHOOK_SUBJECT_HINT = "webhook"
#: The premise a verification function must satisfy when its name does NOT name
#: a webhook: identifiers through which it reads the HTTP request it is
#: RECEIVING. Deliberately the request object and the parts a signature is
#: computed over, rather than a general vocabulary of web words — `payload`,
#: `data` and `event` are what a module calls the thing it is SENDING just as
#: often as the thing that arrived.
WEBHOOK_INBOUND_NAMES = frozenset(
    {"request", "headers", "header", "raw_body", "request_body"}
)
#: Provider credential material held in a product's own configuration. Narrow on
#: purpose: a generic `api_key` is a product's own key more often than a
#: provider's, so provider credential material must be NAMED with its provider.
PROVIDER_TOKENS = (
    "stripe",
    "twilio",
    "paystack",
    "flutterwave",
    "meta_",
    "facebook",
    "instagram",
    "whatsapp",
    "erpnext",
    "sendgrid",
    "mailgun",
    "smtp_",
    "s3_",
    "minio",
)
CREDENTIAL_SUFFIXES = (
    "_api_key",
    "_secret",
    "_secret_key",
    "_token",
    "_access_token",
    "_webhook_secret",
    "_client_secret",
    "_password",
)
#: Scheduling a connector run from inside the product runtime.
#:
#: This vocabulary is read in EXECUTABLE POSITIONS ONLY — an import root, a
#: decorator spelling, a call attribute. It used to be matched against
#: `source.lower()`, which made a comment saying "unlike the celery path we
#: retired" indistinguishable from an applied `@shared_task`. See
#: `_schedules_a_connector` for the arms.
#:
#: Scheduling frameworks. An import root in this set says this module is in the
#: scheduling business; it names no subject on its own, so it QUALIFIES the
#: ambiguous spellings below rather than standing as evidence by itself.
SCHEDULER_MODULES = frozenset(
    {
        "celery",
        "celery_once",
        "django_celery_beat",
        "apscheduler",
        "rq",
        "rq_scheduler",
        "huey",
        "dramatiq",
        "arq",
        "schedule",
        "croniter",
    }
)
#: Decorator spellings that SCHEDULE what they decorate, unambiguously enough to
#: count without a framework import: the words already name scheduling.
SCHEDULING_DECORATOR_HINTS = (
    "shared_task",
    "periodic_task",
    "scheduled_task",
    "scheduled_job",
    "celery",
    "crontab",
    "cron",
)
#: The ambiguous decorator tail. `@app.task` schedules under celery and means
#: nothing on its own, so it counts only beside a framework import. Matched as a
#: whole dotted PART, never a substring — `@dataclass` must not be a task.
AMBIGUOUS_SCHEDULING_DECORATOR = "task"
#: Registration calls that hand a callable to a scheduler. Unambiguous set: the
#: attribute name already says scheduling.
SCHEDULER_REGISTRATION_ATTRS = frozenset(
    {"add_periodic_task", "register_periodic_task", "register_task", "schedule_task"}
)
#: `add_job` is APScheduler's registration and also an ordinary domain verb, and
#: `enqueue*` is RQ's. Both count only beside a framework import.
AMBIGUOUS_REGISTRATION_ATTRS = frozenset(
    {"add_job", "enqueue", "enqueue_in", "enqueue_at"}
)
#: Dispatch: how a task is SENT for execution, rather than defined.
TASK_DISPATCH_ATTRS = frozenset({"delay", "apply_async", "send_task"})
#: Assignment targets that hold a periodic-task TABLE. `beat_schedule` is the
#: canonical celery spelling and defines tasks that carry no decorator anywhere
#: in this repository, so omitting it would be a real recall hole.
SCHEDULE_TABLE_NAMES = ("beat_schedule", "celerybeat_schedule", "cron_schedule")
#: The key under which such a table names the callable it runs.
SCHEDULE_TABLE_TASK_KEY = "task"
TASK_SUBJECT_HINTS = ("sync", "connector", "integration", "webhook", "poll", "fetch")
#: `sync` is a substring of `async`, and `async` says nothing whatsoever about
#: an external feed — it is the ordinary word for "not blocking". Plain
#: substring matching therefore made EVERY `async` identifier connector-shaped:
#: `execute_async_hook.delay(...)`, a generic asynchronous job runner in
#: `dotmac_erp`'s hooks framework, scored `connector_task`, and `AsyncCursor`
#: scored `sync_checkpoint` twice over — once through the bare `sync` feed hint
#: and once because `asynccursor` CONTAINS `synccursor`. Both are the error
#: class already recorded for `InboxTeamRoundRobinCursor` and for
#: `verify_signature`: a spelling taken for evidence.
#:
#: The guard is therefore on any hint that BEGINS with `sync`, not on the bare
#: word alone — a negative lookbehind that keeps every real spelling (`sync_x`,
#: `data_sync`, `resync`, `ProviderSyncCursor`) and drops only the false friend.
SYNC_PREFIX = "sync"


@functools.cache
def _hint_pattern(hint: str) -> re.Pattern[str]:
    return re.compile(r"(?<!a)" + re.escape(hint))


#: Durable cursor/watermark state for an external feed.
#:
#: Split in two because the words are not equally specific. `checkpoint`,
#: `syncstate` and `synccursor` already NAME durable progress over a stream, so
#: they stand alone. Bare `cursor` does not: it is equally the ordinary word for
#: a pagination cursor, a DBAPI cursor, and — the miscount that motivated this
#: split — a round-robin ROTATION pointer over an internal roster
#: (`InboxTeamRoundRobinCursor` in dotmac_sub), which has no feed, no watermark
#: and no external system anywhere near it. A bare `*Cursor` must therefore also
#: name the feed it is a position in.
#: `syncstate` and `synccursor` name durable progress over a STREAM outright,
#: so they stand alone. `checkpoint` does NOT, and treating it as standalone
#: evidence was the same error already fixed twice here: a workflow engine's
#: `WorkflowCheckpoint` is a durable position inside an INTERNAL execution —
#: keyed on `(execution_id, code)` and `(execution_id, position)`, in a module
#: importing nothing but the kernel, SQLAlchemy and stdlib — with no feed, no
#: watermark and no external system anywhere near it. That is
#: `InboxTeamRoundRobinCursor` again, and `AsyncCursor` before it: a spelling
#: taken for evidence.
#:
#: So `checkpoint` joins `cursor` in the ambiguous set and must also name the
#: feed it is a position in. Recall is unaffected in the cases that matter —
#: `PollingCheckpoint` still counts through `poll`, `SyncCheckpoint` through
#: `sync` — and the COLUMN net below is untouched, so anything that actually
#: stores a watermark counts whatever its class is called.
FEED_CHECKPOINT_CLASS_HINTS = ("syncstate", "synccursor")
AMBIGUOUS_CHECKPOINT_CLASS_HINTS = ("cursor", "checkpoint")
#: `meta_` is a provider prefix in a SETTINGS name but an ordinary programming
#: prefix in a CLASS name (`MetadataCursor`), so it does not qualify a cursor.
NOT_A_CLASS_NAME_PROVIDER = frozenset({"meta_"})
#: What turns an ambiguous `*Cursor` into a connector checkpoint: the name says
#: which external feed it is a position in. Provider names count too.
EXTERNAL_FEED_HINTS = (
    "sync",
    "external",
    "integration",
    "connector",
    "feed",
    "ingest",
    "import",
    "poll",
    "replicat",
    "upstream",
    "remote",
    "mirror",
    "provider",
    "webhook",
    "erp",
    *(
        provider.rstrip("_")
        for provider in PROVIDER_TOKENS
        if provider not in NOT_A_CLASS_NAME_PROVIDER
    ),
)
#: The COLUMN net, unchanged by the name rule above: anything that actually
#: stores a watermark counts whatever its class is called. This is why
#: narrowing bare `*Cursor` costs no recall.
CHECKPOINT_COLUMN_HINTS = frozenset(
    {"last_synced_at", "sync_cursor", "last_cursor", "watermark"}
)
#: Delivery-retry vocabulary. UNCHANGED from the raw-text rule it replaces —
#: the repair is about WHERE these words are read, not which words they are, so
#: that a corpus difference is attributable to context alone.
RETRY_HINTS = ("dead_letter", "deadletter", "retry_backoff", "max_retries", "requeue")
#: Decorator spellings that ARE a retry policy. This is the one addition to the
#: vocabulary, and it is confined to decorator position: `@retry(...)` over an
#: outbound call is a delivery-retry policy with no identifier, no keyword and
#: no mapping anywhere in the module, so a repair that read only the words above
#: in the positions above would silently lose it.
RETRY_DECORATOR_HINTS = ("retry", "backoff")

# --- Bounded tracing: one hop of project-local indirection ------------------
#
# A spelling-only sweep scored a genuine ERPNext connector as holding one
# surface out of three. The client came from a project-local transport factory
# and the credential came off a settings object, so the connector module BOUND
# nothing a name rule could see. That is one hop, not a hiding place.
#
# THE BOUND, and it is the whole contract of this section:
#
# 1. Tracing follows PROJECT-LOCAL code only — a module in this repository's
#    own tracked inventory. A name imported from a package the inventory does
#    not contain is third-party and is not resolved. The engine does not model
#    dependencies it cannot read.
# 2. Resolution runs `MAX_TRACE_ROUNDS` monotone rounds outward from a direct
#    HTTP client constructor. Two rounds reaches
#    `caller -> factory -> constructor`; a third link in the chain is NOT
#    resolved, and that undercount is stated rather than discovered.
# 3. Rounds are a fixed point over a finite name set, so a cycle of factories
#    that return each other terminates instead of recursing.
# 4. Every rule reads node SHAPES. Nothing added here inspects raw source text
#    or sweeps string constants: a docstring is one `ast.Constant`, a comment is
#    not in the tree at all, and both must stay inert. A prototype that swept
#    string constants produced five false positives and all five were prose.
# 5. No whole-program type inference. A receiver is resolved only when it is
#    literally a call to a name this analysis already proved yields a client, or
#    a local name assigned from exactly such a call.

#: How far a client may travel from its constructor and still be traced. Two.
MAX_TRACE_ROUNDS = 2
#: Constructor attributes of the known client libraries. The attribute name
#: alone is never enough — `sqlalchemy.orm.Session()` shares one of these — so a
#: construction is recognised only when its ROOT is a client module this module
#: actually imported.
CLIENT_CONSTRUCTORS = frozenset(
    {
        "Client",
        "AsyncClient",
        "Session",
        "ClientSession",
        "PoolManager",
        "HTTPSConnectionPool",
        "HTTPConnection",
        "HTTPSConnection",
    }
)
#: Receiver names that denote held CONFIGURATION rather than inbound data. The
#: credential rule reads attribute LOADS as well as stores, and this is what
#: keeps `payload.stripe_api_key` — a field of somebody else's request — from
#: being read as a credential this product holds. Matched EXACTLY against a
#: lowercased name part, never as a substring, so `envelope` is not `env`.
CONFIG_RECEIVER_NAMES = frozenset(
    {
        "settings",
        "setting",
        "config",
        "configuration",
        "conf",
        "cfg",
        "env",
        "environ",
        "environment",
        "secrets",
        "credentials",
        "options",
        "get_settings",
        "get_config",
    }
)
#: The same idea for a compound name: `tenant_config`, `app_settings`.
CONFIG_RECEIVER_SUFFIXES = ("_settings", "_config", "_conf", "_cfg", "_options")
#: Keywords under which a request-shaped call carries its target.
REQUEST_TARGET_KEYWORDS = frozenset({"url", "path", "endpoint"})


def _dotted(node: ast.expr) -> str | None:
    """The dotted spelling of a name expression, or None if it is not one."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


def _http_transport_bindings(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """Local names through which THIS module can reach a client library.

    Returns the module aliases (`import httpx as hx` -> `hx`) and the directly
    imported constructor names (`from httpx import Client as C` -> `C`).
    Aliases are read rather than assumed, because a renamed import is not an
    evasion and must not be treated as one.
    """
    modules: set[str] = set()
    constructors: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in HTTP_TRANSPORTS:
                    modules.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module.split(".")[0] not in HTTP_TRANSPORTS:
                continue
            for alias in node.names:
                if alias.name in CLIENT_CONSTRUCTORS:
                    constructors.add(alias.asname or alias.name)
    return frozenset(modules), frozenset(constructors)


def _constructs_a_client(
    node: ast.Call, modules: frozenset[str], constructors: frozenset[str]
) -> bool:
    """`httpx.Client(...)`, `requests.Session()`, `http.client.HTTPConnection()`.

    The root of the dotted callee must be a client module this file imported.
    Without that clause the shared `Session` name makes every ORM session a
    client, which is the false positive this rule exists to avoid.
    """
    if isinstance(node.func, ast.Name):
        return node.func.id in constructors
    dotted = _dotted(node.func)
    if dotted is None:
        return False
    head, _, attribute = dotted.rpartition(".")
    return (
        bool(head)
        and head.split(".")[0] in modules
        and attribute in (CLIENT_CONSTRUCTORS)
    )


def _in_process_transport_names(
    tree: ast.Module, modules: frozenset[str]
) -> frozenset[str]:
    """Names bound to an explicitly in-process httpx transport."""
    constructors: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "httpx"
            and not node.level
        ):
            constructors.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name in IN_PROCESS_HTTP_TRANSPORTS
            )

    def constructs(expression: ast.expr, known: set[str]) -> bool:
        inner = expression.value if isinstance(expression, ast.Await) else expression
        if isinstance(inner, ast.Name):
            return inner.id in known
        if not isinstance(inner, ast.Call):
            return False
        if isinstance(inner.func, ast.Name):
            return inner.func.id in constructors
        dotted = _dotted(inner.func)
        if dotted is None:
            return False
        head, _, attribute = dotted.rpartition(".")
        return (
            bool(head)
            and head.split(".")[0] in modules
            and attribute in IN_PROCESS_HTTP_TRANSPORTS
        )

    known: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            if constructs(node.value, known):
                before = len(known)
                known.update(_assigned_names(node))
                changed = changed or len(known) != before
    return frozenset(known | constructors)


def _client_uses_in_process_transport(
    node: ast.Call,
    modules: frozenset[str],
    transports: frozenset[str],
) -> bool:
    for keyword in node.keywords:
        if keyword.arg != "transport":
            continue
        value = (
            keyword.value.value
            if isinstance(keyword.value, ast.Await)
            else keyword.value
        )
        if isinstance(value, ast.Name):
            return value.id in transports
        if not isinstance(value, ast.Call):
            return False
        if isinstance(value.func, ast.Name):
            return value.func.id in transports
        dotted = _dotted(value.func)
        if dotted is None:
            return False
        head, _, attribute = dotted.rpartition(".")
        return (
            bool(head)
            and head.split(".")[0] in modules
            and attribute in IN_PROCESS_HTTP_TRANSPORTS
        )
    return False


def _only_constructs_in_process_http_clients(tree: ast.Module) -> bool:
    """Every constructed client is explicitly wired to an in-process transport.

    A direct module request such as ``httpx.post(...)`` always defeats the
    result: a module that holds both a fake client and real egress is still an
    outbound surface.
    """
    modules, constructors = _http_transport_bindings(tree)
    transports = _in_process_transport_names(tree, modules)
    clients = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _constructs_a_client(node, modules, constructors)
    ]
    if not clients or not all(
        _client_uses_in_process_transport(node, modules, transports) for node in clients
    ):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        dotted = _dotted(node.func)
        if dotted is None:
            continue
        if (
            node.func.attr in REQUEST_METHODS
            and dotted.split(".")[0] in modules
            and len(dotted.split(".")) == 2
        ):
            return False
    return True


def _returned_expressions(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.expr]:
    """What this function itself returns, NOT what a nested one returns.

    `ast.walk` would attribute a closure's return to its enclosing function, so
    a helper that builds a client inside a decorator would make the decorator a
    factory. Nested definitions are their own scope and are skipped.
    """
    found: list[ast.expr] = []
    remaining: list[ast.stmt] = list(node.body)
    while remaining:
        current = remaining.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(current, ast.Return) and current.value is not None:
            found.append(current.value)
        remaining.extend(
            child
            for child in ast.iter_child_nodes(current)
            if isinstance(child, ast.stmt)
        )
    return found


def _module_level_functions(
    tree: ast.Module,
) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in _module_level(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _called_name(expression: ast.expr) -> str | None:
    """The dotted callee of `f(...)` / `await f(...)`, else None."""
    inner = expression.value if isinstance(expression, ast.Await) else expression
    if not isinstance(inner, ast.Call):
        return None
    return _dotted(inner.func)


def _function_local_clients(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    modules: frozenset[str],
    constructors: frozenset[str],
    visible: frozenset[str],
    in_process_transports: frozenset[str],
) -> frozenset[str]:
    """Locals of THIS function bound from something proved to be a client.

    Bounded exactly like `_returned_expressions`: the same function body, its
    own statements, nested definitions skipped. It is a binding rule, not a
    type inference — the right-hand side must literally be a client
    construction or a call to an already-resolved factory.
    """
    found: set[str] = set()
    remaining: list[ast.stmt] = list(node.body)
    while remaining:
        current = remaining.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (
            isinstance(current, (ast.Assign, ast.AnnAssign))
            and current.value is not None
        ):
            value = current.value
            inner = value.value if isinstance(value, ast.Await) else value
            called = _called_name(value)
            if (
                isinstance(inner, ast.Call)
                and _constructs_a_client(inner, modules, constructors)
                and not _client_uses_in_process_transport(
                    inner, modules, in_process_transports
                )
            ) or (called is not None and called in visible):
                found.update(_assigned_names(current))
        remaining.extend(
            child
            for child in ast.iter_child_nodes(current)
            if isinstance(child, ast.stmt)
        )
    return frozenset(found)


def _client_factories(tree: ast.Module, visible: frozenset[str]) -> frozenset[str]:
    """Module-level function names in THIS file that yield an HTTP client.

    A function qualifies when one of its own returns either constructs a client
    directly, calls a name `visible` already proves is a factory, or returns a
    LOCAL this same function bound from one of those two. `visible` is what
    carries a factory across the import graph, one round at a time.

    The local-binding clause is not a convenience. `return httpx.Client(...)`
    is the textbook factory; the shape the measured repositories actually write
    is a memoising one that binds the client to a local and returns the local
    (`crm_client._pooled_client`, `core_router_metrics._get_client` in
    `dotmac_sub`). Without it the whole trace resolved ZERO spellings across
    5,626 measured real sources — correct on its fixture, inert on its subject.

    It costs no bound: the binding must sit in the SAME function body, so this
    is still one function and still `MAX_TRACE_ROUNDS` hops, not a third link.
    """
    modules, constructors = _http_transport_bindings(tree)
    in_process_transports = _in_process_transport_names(tree, modules)
    found: set[str] = set()
    for name, node in _module_level_functions(tree).items():
        local_clients = _function_local_clients(
            node, modules, constructors, visible, in_process_transports
        )
        for expression in _returned_expressions(node):
            inner = (
                expression.value if isinstance(expression, ast.Await) else expression
            )
            if (
                isinstance(inner, ast.Call)
                and _constructs_a_client(inner, modules, constructors)
                and not _client_uses_in_process_transport(
                    inner, modules, in_process_transports
                )
            ):
                found.add(name)
                break
            called = _called_name(expression)
            if called is not None and called in visible:
                found.add(name)
                break
            if isinstance(inner, ast.Name) and inner.id in local_clients:
                found.add(name)
                break
    return frozenset(found)


def _resolved_import_module(
    node: ast.ImportFrom, relative: PurePosixPath
) -> str | None:
    """The absolute module an `ImportFrom` names, relative levels resolved."""
    package = _package_parts(relative)
    if not node.level:
        return node.module or None
    if node.level - 1 > len(package):
        return None
    base = package[: len(package) - (node.level - 1)]
    parts = (*base, node.module) if node.module else base
    return ".".join(parts) or None


class _ModuleImports(NamedTuple):
    """One module's import statements, walked ONCE and resolved ONCE.

    Both `_imported_factory_spellings` and `_re_exported_factories` need the
    same `ImportFrom` nodes, and the trace consults them on every round. Walking
    the tree inside the round loop made the cost of the whole resolution scale
    with the number of rules that read imports rather than with the repository:
    on the largest measured repository (`sub-adopt`, 4,727 modules) adding one
    more import-reading rule took the trace from 29s to 64s. Nothing here
    changes what is resolved — the same nodes, the same targets, the same
    order — so it is a hoist and not a widening.
    """

    #: `(resolved absolute module, ((imported name, bound name), ...))`.
    from_imports: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    #: `(imported module, prefix this module spells it with)`.
    plain_imports: tuple[tuple[str, str], ...]


def _module_imports(tree: ast.Module, relative: PurePosixPath) -> _ModuleImports:
    from_imports: list[tuple[str, tuple[tuple[str, str], ...]]] = []
    plain_imports: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = _resolved_import_module(node, relative)
            if target is None:
                continue
            from_imports.append(
                (
                    target,
                    tuple(
                        (alias.name, alias.asname or alias.name) for alias in node.names
                    ),
                )
            )
        elif isinstance(node, ast.Import):
            plain_imports.extend(
                (alias.name, alias.asname or alias.name) for alias in node.names
            )
    return _ModuleImports(tuple(from_imports), tuple(plain_imports))


def _imported_factory_spellings(
    imports: _ModuleImports,
    by_module: Mapping[str, frozenset[PurePosixPath]],
    factories: Mapping[PurePosixPath, frozenset[str]],
) -> frozenset[str]:
    """Factory names reachable from THIS module, as this module spells them.

    THREE import forms carry a factory, and they are three spellings of one
    import edge rather than three links:

    * `from p.transport import make_client` spells it `make_client`.
    * `import p.transport` spells it `p.transport.make_client`.
    * `from p import transport` binds the MODULE `p.transport` under the name
      `transport`, so the same function is spelled `transport.make_client`.

    The third was missing, and it is the spelling this fleet actually writes:
    19,155 such calls across 1,542 modules in `sub-adopt`, 1,056 in the
    starter, 660 in `academy-adopt`, 495 in `erp-adopt`, 387 in `vcp-adopt`.
    Leaving it out made the verdict depend on how a caller spells an import —
    the same packaging-style conditionality the re-export clause was added to
    end, and the reason that one was treated as a blocker rather than a bound:
    a product could hold a real connector, spell its import the ordinary way,
    and be green.

    It adds a rename, not a link. The submodule must be a module in
    `by_module` — the repository's own tracked inventory — and it must already
    OWN or REPUBLISH a name this analysis has proved yields a client, which is
    the same condition the other two forms carry. Everything outside the
    inventory is third-party and the trace stops at the repository edge.
    """
    spellings: set[str] = set()
    for target, names in imports.from_imports:
        for path in by_module.get(target, frozenset()):
            owned = factories.get(path, frozenset())
            for name, bound in names:
                if name in owned:
                    spellings.add(bound)
        for name, bound in names:
            for path in by_module.get(f"{target}.{name}", frozenset()):
                for owned_name in factories.get(path, frozenset()):
                    spellings.add(f"{bound}.{owned_name}")
    for module, prefix in imports.plain_imports:
        for path in by_module.get(module, frozenset()):
            for owned_name in factories.get(path, frozenset()):
                spellings.add(f"{prefix}.{owned_name}")
    return frozenset(spellings)


def _declared_all(tree: ast.Module) -> frozenset[str] | None:
    """The names a module's `__all__` publishes, or None if it declares none.

    Only a literal list or tuple of string constants is read: `__all__` built
    by concatenation or comprehension is not a declaration this analysis can
    evaluate, and guessing at one would be the whole-program inference clause 5
    refuses. An unreadable `__all__` therefore falls back to the underscore
    rule, which is the conservative direction.
    """
    for node in _module_level(tree):
        if "__all__" not in _assigned_names(node):
            continue
        value = getattr(node, "value", None)
        if not isinstance(value, (ast.List, ast.Tuple)):
            continue
        if any(
            not isinstance(item, ast.Constant) or not isinstance(item.value, str)
            for item in value.elts
        ):
            continue
        return frozenset(item.value for item in value.elts)  # type: ignore[attr-defined]
    return None


def _re_exported_factories(
    imports: _ModuleImports,
    by_module: Mapping[str, frozenset[PurePosixPath]],
    owned: Mapping[PurePosixPath, frozenset[str]],
    declared: Mapping[PurePosixPath, frozenset[str] | None] | None = None,
) -> frozenset[str]:
    """Factory names THIS module republishes under its own module name.

    `chain/__init__.py` holding `from chain.zero import build` makes
    `from chain import build` name the very same function. Resolution reads the
    factories a module DEFINES, and a pure re-export module defines none — so
    the factory died at the package root, and a caller spelling it the ordinary
    way measured clean while the identical connector spelled one module deeper
    measured red.

    That was never the depth bound. A module with no `def` cannot become a
    factory owner in ANY number of rounds, so raising `MAX_TRACE_ROUNDS` did
    not reach it. The detector was conditional on whether a product publishes
    its transport through a package root — a packaging style, not a structure.

    The clause is a RENAME, not a link, and it is bounded like one: the source
    module must already OWN the name. A re-export of a re-export would need the
    republished set OF the republished set, which is not computed, so it stays
    unresolved exactly as a third function link does.

    `from p.transport import *` republishes the same names as listing them one
    by one and is read the same way, because reading only explicit aliases
    would leave a one-word evasion of the whole clause. Its bound is Python's
    own rule rather than a chosen one — and Python's rule is `__all__` FIRST
    and the underscore convention only in its absence. A module declaring
    `__all__ = ["_pooled_client"]` republishes that private factory through the
    star, and `from p import _pooled_client` then runs; verified against the
    interpreter. Reading the underscore alone made the bound unenforceable and
    left the clause evadable by one line, in a corpus whose real factories
    (`_pooled_client`, `_get_client`) are exactly the private names `__all__`
    would carry. An `__all__` this analysis cannot evaluate falls back to the
    underscore rule.
    """
    republished: set[str] = set()
    for target, names in imports.from_imports:
        for path in by_module.get(target, frozenset()):
            exported = owned.get(path, frozenset())
            published = (declared or {}).get(path)
            for name, bound in names:
                if name == "*":
                    if published is None:
                        republished.update(
                            item for item in exported if not item.startswith("_")
                        )
                    else:
                        republished.update(exported & published)
                elif name in exported:
                    republished.add(bound)
    return frozenset(republished)


def _trace_client_factories(
    trees: Mapping[PurePosixPath, ast.Module],
) -> dict[PurePosixPath, frozenset[str]]:
    """Every spelling that yields an HTTP client, per module, within the bound.

    Round 0 seeds on direct constructors. Each further round carries factories
    one import hop outward and one local return inward, and there are exactly
    `MAX_TRACE_ROUNDS` of them. The result is the set of spellings VISIBLE in
    each module, which is what the request rule consumes.

    What travels between modules is a module's EXPORTED set — the factories it
    DEFINES plus the ones it REPUBLISHES under its own name — because those are
    the two ways a caller can legitimately name a factory. Republication is
    resolved from `owned` alone, so it adds a rename and not a link.

    Imports are walked and resolved ONCE, before the rounds, because both
    import-reading rules consult the same nodes on every round.
    """
    by_module: dict[str, set[PurePosixPath]] = {}
    for relative in trees:
        for name in _module_names(relative):
            by_module.setdefault(name, set()).add(relative)
    index: Mapping[str, frozenset[PurePosixPath]] = {
        name: frozenset(paths) for name, paths in by_module.items()
    }
    imports = {
        relative: _module_imports(tree, relative) for relative, tree in trees.items()
    }
    # `__all__` decides what a star import republishes, and like the imports it
    # is read ONCE per module rather than inside the rounds.
    declared = {relative: _declared_all(tree) for relative, tree in trees.items()}

    owned: dict[PurePosixPath, frozenset[str]] = {
        relative: _client_factories(tree, frozenset())
        for relative, tree in trees.items()
    }
    visible: dict[PurePosixPath, frozenset[str]] = dict(owned)
    for _ in range(MAX_TRACE_ROUNDS):
        exported = {
            relative: owned[relative]
            | _re_exported_factories(imports[relative], index, owned, declared)
            for relative in trees
        }
        visible = {
            relative: owned[relative]
            | _imported_factory_spellings(imports[relative], index, exported)
            for relative in trees
        }
        grown = {
            relative: _client_factories(tree, visible[relative])
            for relative, tree in trees.items()
        }
        if grown == owned:
            break
        owned = grown
    return {
        relative: owned[relative] | visible.get(relative, frozenset())
        for relative in trees
    }


#: What a string constant must carry to prove, ON ITS OWN, that a call
#: addresses a REMOTE resource. A scheme names a network; a leading slash does
#: not.
REMOTE_URL_SCHEMES = ("http://", "https://")


def _url_shaped(node: ast.expr) -> bool:
    """A string constant that addresses a REMOTE resource, not a local path.

    This is the whole evidence of the one request arm that does not resolve to
    a constructor, so it has to be a discriminator and not a resemblance. A
    leading slash is not one. `"/admin"` in a permission map, `"/health"` in a
    route table and `"/api/v1/..."` handed to an in-process ASGI test client
    are the same string as a request path, and the receiver — a module-level
    function this analysis could not resolve — says nothing either way.

    Read on real code, the slash rule found five call sites across the six
    measured repositories and every one of them was
    `starlette.testclient.TestClient`: an in-process call to the application
    under test, which is the definitional opposite of an external connector.
    One of them is the only conserved record the starter publishes, and the
    counter-example the rule shipped with — `_rows().get("key", "")` — passed
    for the wrong reason, because `"key"` is not path-shaped and so never
    reached the discriminator.

    The bound this buys, stated in the conservative direction: a project-local
    transport wrapper that the factory trace could not resolve, called with a
    RELATIVE path against a client whose library is not in `HTTP_TRANSPORTS`, is
    now UNDERCOUNTED. It costs nothing measured today — the arm contributed
    zero hits to the measured universe of all six repositories — and the two
    errors are not symmetric: this ratchet can be raised for a miss, while a
    false positive is unfixable by the repository holding it.
    """
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False
    return node.value.startswith(REMOTE_URL_SCHEMES)


def _addresses_a_url(node: ast.Call) -> bool:
    if node.args and _url_shaped(node.args[0]):
        return True
    return any(
        keyword.arg in REQUEST_TARGET_KEYWORDS and _url_shaped(keyword.value)
        for keyword in node.keywords
    )


def _decorator_calls(tree: ast.Module) -> frozenset[int]:
    """Identity of every `Call` node used as a decorator.

    `@get_router().get("/health")` is a route MOUNT, not an outbound request,
    and it is the one shape that reads like both.
    """
    found: set[int] = set()
    for node in ast.walk(tree):
        for decorator in getattr(node, "decorator_list", []):
            for child in ast.walk(decorator):
                if isinstance(child, ast.Call):
                    found.add(id(child))
    return frozenset(found)


def _client_named_locals(tree: ast.Module, visible: frozenset[str]) -> frozenset[str]:
    """Names bound from a resolved factory call: `client = _client()`.

    Deliberately name-level and scope-blind. That is the documented cost of
    refusing type inference: two functions binding the same name to different
    things are conflated. Both must still trace back to a real constructor, so
    the shape cannot be produced by anything but a client.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None:
            continue
        called = _called_name(value)
        if called is not None and called in visible:
            found.update(_assigned_names(node))
    return frozenset(found)


def _issues_a_traced_request(tree: ast.Module, visible: frozenset[str]) -> bool:
    """An outbound request through resolved project-local indirection.

    Three receiver shapes, each bounded:

    * `_client().get(...)` where `_client` is a RESOLVED factory — a client
      reached through project-local code, whatever library sits underneath.
    * `client.get(...)` where `client` was bound from such a factory call.
    * `_client().get("/api/resource/Supplier")` where `_client` is merely a
      module-level function of this file, and the call ADDRESSES A URL. This is
      the one rule that does not resolve to a constructor, so the URL literal
      carries the whole claim: `_rows().get("key", "")` is the ordinary mapping
      accessor and must stay silent. Decorator calls are excluded — mounting a
      route is not issuing a request.
    """
    local_functions = frozenset(_module_level_functions(tree))
    bound = _client_named_locals(tree, visible)
    decorators = _decorator_calls(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in REQUEST_METHODS or id(node) in decorators:
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Name) and receiver.id in bound:
            return True
        if not isinstance(receiver, ast.Call):
            continue
        callee = _dotted(receiver.func)
        if callee is None:
            continue
        if callee in visible:
            return True
        if callee in local_functions and _addresses_a_url(node):
            return True
    return False


def _is_configuration_receiver(node: ast.expr) -> bool:
    """Is this expression held CONFIGURATION rather than inbound data?

    `settings.x`, `self.config.x`, `get_settings().x`, `tenant_config.x` are;
    `payload.x` and `response.x` are not. Exact part matching, plus a small set
    of compound suffixes: substring matching would make `envelope` an `env`.
    """
    target = node.func if isinstance(node, ast.Call) else node
    dotted = _dotted(target)
    if dotted is None:
        return False
    for part in (item.lower() for item in dotted.split(".")):
        if part in CONFIG_RECEIVER_NAMES:
            return True
        if part.endswith(CONFIG_RECEIVER_SUFFIXES):
            return True
    return False


def _names_provider_credential(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in PROVIDER_TOKENS) and any(
        lowered.endswith(suffix) for suffix in CREDENTIAL_SUFFIXES
    )


def _http_transport_names(tree: ast.Module) -> frozenset[str]:
    """Local names this module binds to a client library.

    `import httpx` binds `httpx`; `import httpx as h` binds `h`;
    `from httpx import AsyncClient` binds `AsyncClient`.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in HTTP_TRANSPORTS:
                    bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in HTTP_TRANSPORTS:
                bound.update(alias.asname or alias.name for alias in node.names)
    return frozenset(bound)


def _caught_client_positions(tree: ast.Module) -> frozenset[int]:
    """Node ids inside an `except` clause's EXCEPTION TYPE.

    The one position where naming a client commits to nothing:
    `except httpx.HTTPStatusError` says somebody ELSE made the call and this
    module handles the failure.

    Deliberately NOT annotations, and that boundary was found by proof rather
    than argued. Excluding annotations too looks like the same idea — the arm
    has always said "importing a client for a type annotation is not a
    connector" — but it is a different one, because an annotated PARAMETER is
    how an already-constructed client is handed in:

        def deliver(client: httpx.Client) -> None:
            client.post("https://provider.example/v1/events", ...)

    is an outbound request in every sense, and three of this record's own
    fixtures are exactly that shape. The annotation-only module is already
    separated by `_issues_a_request`, which is where the arm always said the
    separation lived; widening this set silently retired real surfaces.
    """
    inert: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.type is not None:
            inert.update(id(child) for child in ast.walk(node.type))
    return frozenset(inert)


def _uses_an_http_transport(tree: ast.Module) -> bool:
    """Does this module USE a client library, rather than merely name one?

    A confirmed FALSE POSITIVE on real code, twice over. The arm used to ask
    only whether a client was IMPORTED, and pairing that with
    `_issues_a_request` — which reads an attribute name and no receiver — meant
    a module that delegates every outbound call elsewhere and imports the
    library solely to name its exception classes scored `http_client` off its
    own `payload.get(...)` accessors.

    `crm-guardrails/app/services/crm/conversations/comments.py` is the case:
    one `httpx` reference in the file, `except httpx.HTTPStatusError`, and 33
    request-named calls of which every single one is a mapping accessor. The
    real requests are `meta_pages`', and `meta_pages` is measured on its own
    account. `sub-adopt/app/tasks/notifications.py` is the same module in
    another repository. Both are unfixable in the product: the only repair
    available to either is to stop catching the exception by its real name.

    So the import has to be USED somewhere outside the one position where
    naming a client commits to nothing — see `_caught_client_positions`.

    THE BOUND, stated in the conservative direction: a module that reaches an
    outbound call through a client it neither names nor catches — handed in
    under a name this analysis cannot resolve, and not reachable by the
    bounded factory trace — is UNDERCOUNTED, exactly as before. What this
    changes is only that CATCHING a client's exception stopped being a use.
    Measured across the seven repositories swept, that retires two modules and
    no other of the 96.
    """
    bound = _http_transport_names(tree)
    if not bound:
        return False
    inert = _caught_client_positions(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in bound and id(node) not in inert:
            return True
    return False


def _issues_a_request(tree: ast.Module) -> bool:
    """An `httpx.post(...)`/`client.get(...)`-shaped call.

    Attribute-name matching, not receiver tracking: the receiver could be any
    local name and resolving it needs type inference this engine has no
    business doing. Paired with `_uses_an_http_transport`, the false-positive
    surface is a module that both USES a client AND calls something named
    `get` — rare enough to be worth the recall.
    """
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in REQUEST_METHODS
        for node in ast.walk(tree)
    )


# --- `outbound_transport`, ARM 2: SMTP --------------------------------------
#
# The category used to be called `http_client`, and the name was doing damage
# rather than merely reading oddly. `erp-adopt/app/tasks/email.py` is a
# `@shared_task` that owns outbound mail delivery — SMTP response-code tables,
# a permanent/transient classification, a retry policy over the send — and it
# held NO category at all. It was briefly visible only through a false friend
# (`async` matching the `sync` subject hint), and when that friend was retired
# the module went dark. There was nowhere for it to land: it is not HTTP, and
# calling it HTTP to make a number move would have been worse than the gap.
#
# So the category is the CONCEPT and each protocol is an arm with its own three
# legs. This arm's shape is deliberately NOT a copy of the HTTP arm's, and the
# difference is the reason both are written out rather than parameterised:
#
#   The HTTP arm is a CONJUNCTION — a client used AND a request-shaped call —
#   because `httpx.Client`, `requests.Session` and a bare `.get(...)` all
#   collide with things that are not transports, so the import alone
#   overcounts and the call alone overcounts far worse.
#
#   The SMTP arm is not. `smtplib` and `aiosmtplib` do one thing. A module that
#   names either, anywhere the naming commits to something, is handling mail
#   transport, and requiring a `sendmail` call as a second conjunct would have
#   made the witness above invisible for a second time — it classifies SMTP
#   failures and owns the retry policy without spelling the send itself, which
#   is exactly what a delivery task looks like when the socket work sits one
#   module away.
#
# The one position that commits to nothing is shared with the HTTP arm and is
# shared in CODE, not by restatement: `_caught_client_positions`. `except
# smtplib.SMTPException` says somebody else sent the mail and this module
# handles the failure.
#
# WHAT THIS ARM DOES NOT SEE, stated in the conservative direction: a mail API
# reached over HTTP (SendGrid, Mailgun, SES via boto) is measured by the HTTP
# arm and not by this one, which is correct — the transport really is HTTP.
# A module that hands a message to a queue for something else to relay is not
# measured here at all, and should not be. `email.message` and `email.mime`
# BUILD a message and send nothing, so they are deliberately absent from
# `SMTP_TRANSPORTS`: constructing a MIME part is not a transport surface.


def _smtp_transport_names(tree: ast.Module) -> frozenset[str]:
    """Local names this module binds to an SMTP transport library.

    `import smtplib` binds `smtplib`; `import aiosmtplib as mail` binds `mail`;
    `from smtplib import SMTPException as Failed` binds `Failed`.

    A CONSTRUCTOR name imported directly — `from smtplib import SMTP_SSL` — is
    deliberately NOT bound here, and the omission is what keeps the three legs
    of this arm separable. Opening a connection is the constructor leg's own
    evidence (`_opens_an_smtp_connection`); binding the name here as well would
    make that leg unreachable on its own and its liveness unprovable, which is
    the failure ADR 0018 names. Nothing is lost: any module that constructs a
    connection is measured by the leg that owns constructions.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in SMTP_TRANSPORTS:
                    bound.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in SMTP_TRANSPORTS:
                bound.update(
                    alias.asname or alias.name
                    for alias in node.names
                    if alias.name not in SMTP_CONSTRUCTORS
                )
    return frozenset(bound)


def _smtp_transport_bindings(tree: ast.Module) -> tuple[frozenset[str], frozenset[str]]:
    """The module aliases and the CONSTRUCTOR aliases, told apart.

    `import smtplib as s` -> module `s`; `from aiosmtplib import SMTP as Relay`
    -> constructor `Relay`. Read rather than assumed, because a renamed import
    is not an evasion; the same rule `_http_transport_bindings` follows.
    """
    modules: set[str] = set()
    constructors: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in SMTP_TRANSPORTS:
                    modules.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            if node.module.split(".")[0] not in SMTP_TRANSPORTS:
                continue
            for alias in node.names:
                if alias.name in SMTP_CONSTRUCTORS:
                    constructors.add(alias.asname or alias.name)
    return frozenset(modules), frozenset(constructors)


def _opens_an_smtp_connection(tree: ast.Module) -> bool:
    """`smtplib.SMTP(...)`, `smtplib.SMTP_SSL(...)`, `Relay(...)` from an alias.

    The ROOT of a dotted callee must be a transport module THIS module
    imported, exactly as `_constructs_a_client` requires — `SMTP` is a
    three-letter word and an application is free to name its own class that.
    """
    modules, constructors = _smtp_transport_bindings(tree)
    if not modules and not constructors:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in constructors:
                return True
            continue
        dotted = _dotted(node.func)
        if dotted is None:
            continue
        head, _, attribute = dotted.rpartition(".")
        if head and head.split(".")[0] in modules and attribute in SMTP_CONSTRUCTORS:
            return True
    return False


def _sends_mail(tree: ast.Module) -> bool:
    """A `sendmail(...)` or, qualified, a `send_message(...)` call.

    Two tiers, and the split is the same one the webhook path hints make.
    `sendmail` names mail delivery and nothing else, so it stands alone and
    reaches the shape the HTTP arm records as undercounted — a transport handed
    in under a name this analysis cannot resolve:

        def deliver(relay) -> None:
            relay.sendmail(sender, [to], message.as_string())

    `send_message` is not distinctive. An asyncio queue, a websocket connection
    and a broker client all spell it, so it counts only in a module that has
    already bound an SMTP transport — under EITHER spelling, module alias or
    imported constructor, since the qualification asks whether the library is
    present and not which leg found it.
    """
    modules, constructors = _smtp_transport_bindings(tree)
    methods = set(MAIL_SEND_METHODS)
    if _smtp_transport_names(tree) or modules or constructors:
        methods |= AMBIGUOUS_MAIL_SEND_METHODS
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in methods
        for node in ast.walk(tree)
    )


def _uses_an_smtp_transport(tree: ast.Module) -> bool:
    """Does this module USE an SMTP library, rather than merely name one?

    The same question `_uses_an_http_transport` asks, answered against the same
    inert position: a name that appears ONLY inside an `except` clause's
    exception type commits to nothing, because catching
    `smtplib.SMTPServerDisconnected` says somebody else opened the socket.

    Everywhere else counts, and that boundary is what makes the witness fire.
    `erp-adopt/app/tasks/email.py` reads `isinstance(exc,
    smtplib.SMTPResponseException)` and `exc.smtp_code` against its own tables
    of permanent and transient SMTP codes — executable positions, holding
    delivery policy over the protocol, not handling one failure at one call
    site. A module that only catches is silent; a module that decides is not.
    """
    bound = _smtp_transport_names(tree)
    if not bound:
        return False
    inert = _caught_client_positions(tree)
    return any(
        isinstance(node, ast.Name) and node.id in bound and id(node) not in inert
        for node in ast.walk(tree)
    )


def _speaks_smtp(tree: ast.Module) -> bool:
    """ARM 2 of `outbound_transport`, as one predicate.

    Three legs, any of which is sufficient, and each is separately proved: the
    library is USED, a connection is OPENED, or mail is SENT. The third is the
    only one that can fire with no import in this module at all.
    """
    return (
        _uses_an_smtp_transport(tree)
        or _opens_an_smtp_connection(tree)
        or _sends_mail(tree)
    )


def _route_mounts_a_mutation(decorator: ast.Call, attribute: str) -> bool:
    """Whether this route decorator mounts a MUTATING method.

    Two spellings. `@router.post(...)` names the method in the attribute.
    `@app.route(..., methods=["POST"])` names it in an argument, and with no
    such argument Flask and FastAPI both mount GET alone.
    """
    if attribute in MUTATING_ROUTE_ATTRS:
        return True
    if attribute not in GENERIC_ROUTE_ATTRS:
        return False
    for keyword in decorator.keywords:
        if keyword.arg != ROUTE_METHODS_KEYWORD:
            continue
        for element in ast.walk(keyword.value):
            if (
                isinstance(element, ast.Constant)
                and isinstance(element.value, str)
                and element.value.lower() in MUTATING_ROUTE_ATTRS
            ):
                return True
    return False


def _decorator_path_literals(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, bool]]:
    """Route path constants on a ROUTE decorator, positional AND keyword.

    Each result is the lowered literal paired with whether the route it mounts
    is mutating.

    `@router.post("/webhooks/x")` and `@router.post(path="/webhooks/x")` mount
    the same route; reading only positional arguments made the second form a
    one-keyword bypass of the whole webhook rule.

    THE DECORATOR HAS TO BE A ROUTE, and that is the repair rather than a
    tidy-up. This used to harvest string constants from ANY decorator call, so
    `@celery_app.task(name="app.tasks.webhooks.retry_failed_deliveries")` — a
    queue identifier, on a module with no route, no inbound request and no
    HTTP client — arrived at the webhook rule looking exactly like a mounted
    path. That is the `verify_signature` error again: a NAME read as evidence.
    It compounded, too, because a phantom webhook surface satisfies the second
    conjunct of `_owns_delivery_retry`, so one string constant manufactured
    two findings.

    Measured across seven repositories: exactly two modules rested their
    `webhook_surface` on a non-route decorator, both celery task names
    (`crm-guardrails/app/tasks/webhooks.py`, `app/tasks/webhook_health.py`),
    and restricting the arm loses no other module.
    """
    literals: list[tuple[str, bool]] = []
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        dotted = _dotted(decorator.func)
        if dotted is None:
            continue
        attribute = dotted.split(".")[-1].lower()
        if attribute not in ROUTE_DECORATOR_ATTRS:
            continue
        mutating = _route_mounts_a_mutation(decorator, attribute)
        arguments: list[ast.expr] = [*decorator.args]
        arguments.extend(keyword.value for keyword in decorator.keywords)
        literals.extend(
            (argument.value.lower(), mutating)
            for argument in arguments
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
        )
    return literals


def _reads_an_inbound_request(node: ast.AST) -> bool:
    """Whether this function reads an HTTP request it is RECEIVING.

    Read off the identifiers the function actually mentions — a parameter, a
    local, or an attribute it dereferences — because that is where a receiver
    differs from a sender: `request.headers` and `request.body` are the two
    things a signature is computed over, and a module that verifies a
    signature without touching either is verifying something that did not
    arrive over HTTP.
    """
    for child in ast.walk(node):
        if isinstance(child, ast.arg) and child.arg.lower() in WEBHOOK_INBOUND_NAMES:
            return True
        if isinstance(child, ast.Name) and child.id.lower() in WEBHOOK_INBOUND_NAMES:
            return True
        if (
            isinstance(child, ast.Attribute)
            and child.attr.lower() in WEBHOOK_INBOUND_NAMES
        ):
            return True
    return False


def _reads_callback_material(node: ast.AST) -> bool:
    """Evidence a management route consumes provider callback material.

    A generic ``request`` parameter is deliberately insufficient: admin form
    handlers receive one too. Headers/raw bytes/body and the subscription
    challenge are callback-specific enough to distinguish the two real
    surfaces without teaching the engine a provider's signature scheme.
    """
    material = frozenset({"headers", "header", "raw_body", "request_body", "body"})
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id.lower() in material:
            return True
        if isinstance(child, ast.Attribute) and child.attr.lower() in material:
            return True
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and child.value.lower() in {"hub.challenge", "hub_challenge"}
        ):
            return True
    return False


def _is_management_route(path: str) -> bool:
    segments = frozenset(filter(None, re.split(r"[/_.:-]+", path.lower())))
    return bool(segments & MANAGEMENT_ROUTE_SEGMENTS)


def _is_webhook_surface(tree: ast.Module) -> bool:
    """Whether this module RECEIVES a provider callback.

    Two arms, and they carry different weight. A route literal naming a
    webhook path is a mounted receiver and is evidence by itself. A
    signature-verification FUNCTION NAME is not: a provider callback is
    routinely split, with the route in one module and the verification beside
    the secret in another, so reading the name recovers a real half — but
    `verify_signature` is equally what you call the function that checks a
    licence file, a JWT, a release artefact or a config bundle.

    Reading the name alone measured `erp-adopt`'s offline Ed25519 licence
    verifier as a webhook surface. That module loads a file from a `Path` and
    checks a detached signature against an embedded public key; nothing about
    it arrives over HTTP. With no product suppression, the only repair
    available to that repository was to rename a correctly named function to
    satisfy a governance rule.

    So the second arm is split by how much the name commits to.
    `verify_webhook`, `verify_webhook_signature` — a name carrying the word
    `webhook` names its own subject, and stays evidence on its own. A bare
    `verify_signature` or `check_signature` names nothing, and has to earn the
    finding by ALSO reading the request it is verifying: the same function
    must touch a request object, its headers, or its raw body.

    That split is what the adopters actually look like. `mono_client` and
    `paystack_client` verify with the word in the name and take the header or
    the raw payload as a bare parameter; `crm_webhooks` uses a bare
    `_verify_signature` and reads `request.headers` and the raw body. All
    three stay measured. The licence verifier names nothing and reads nothing
    that arrived over HTTP, and stops being a webhook.

    The stated bound is the conservative one: a bare-named verifier that
    reaches its request through a spelling this does not recognise is
    UNDERCOUNTED. That is a miss the ratchet can be raised for later, rather
    than an unfixable finding in somebody else's repository — and given there
    is no product suppression, those two errors are not symmetric.

    THE PATH ARM IS SPLIT THE SAME WAY, for the same reason. `webhook`,
    `/hooks`, `notify-url` and `ipn` name a provider callback on their own.
    `callback` does not — it is equally an OAuth consent return or a hosted
    checkout's redirect target, and all three real matches across the adopters
    are exactly that. An ambiguous word is qualified by the route's METHOD: a
    browser is redirected with a GET, a provider delivers an event with a POST.

    The qualification is confined to the ambiguous word deliberately. Meta
    verifies a webhook subscription with a GET carrying `hub.challenge`
    (`crm_webhooks.whatsapp_webhook_verify`, `inbox_webhooks.
    verify_meta_webhook`), so a blanket "a webhook route must be mutating"
    rule would retire a real receiver — the wrongly-lost-true-positive error,
    which is the worse of the two.
    """
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for literal, mutating in _decorator_path_literals(node):
            names_webhook = any(hint in literal for hint in WEBHOOK_PATH_HINTS)
            names_ambiguous_callback = mutating and any(
                hint in literal for hint in AMBIGUOUS_WEBHOOK_PATH_HINTS
            )
            if not (names_webhook or names_ambiguous_callback):
                continue
            if _is_management_route(literal) and not _reads_callback_material(node):
                continue
            return True
        name = node.name.lower()
        if not any(hint in name for hint in WEBHOOK_VERIFY_HINTS):
            continue
        if WEBHOOK_SUBJECT_HINT in name or _reads_an_inbound_request(node):
            return True
    return False


def _target_names(node: ast.expr) -> list[str]:
    """Names one assignment target binds, through tuple and attribute forms."""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        return [node.attr]
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for element in node.elts for name in _target_names(element)]
    return []


def _assigned_names(node: ast.AST) -> list[str]:
    """Names bound by one assignment, in BOTH declaration styles.

    Annotated (`x: Mapped[str] = mapped_column(...)`) and classic
    (`x = Column(...)`) declare the same column; a detector that reads only the
    annotated form is blind to every pre-2.0 SQLAlchemy model, and blind to
    `self.stripe_api_key = ...` in either style.
    """
    if isinstance(node, ast.AnnAssign):
        return _target_names(node.target)
    if isinstance(node, ast.Assign):
        return [name for target in node.targets for name in _target_names(target)]
    if isinstance(node, ast.AugAssign):
        return _target_names(node.target)
    return []


def _holds_provider_credential(tree: ast.Module) -> bool:
    """A configuration attribute naming BOTH a provider and secret material.

    Read on BOTH sides of the assignment. Binding the name
    (`stripe_api_key = ...`) was the only visible spelling, so a module that
    merely READ `settings.erpnext_token` off a configuration object held the
    credential in its own runtime and measured clean. A read is a hold.

    The receiver must be configuration-shaped, which is the bound: a field of
    an inbound payload is somebody else's credential passing through, not one
    this repository holds, and the rule does not follow it.
    """
    for node in ast.walk(tree):
        for name in _assigned_names(node):
            if _names_provider_credential(name):
                return True
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.ctx, ast.Load)
            and _names_provider_credential(node.attr)
            and _is_configuration_receiver(node.value)
        ):
            return True
    return False


def _mentions(name: str, hints: tuple[str, ...]) -> bool:
    """Substring hint matching, with the one documented false friend excluded.

    Every hint is an ordinary substring test except the `sync*` family, which
    must not match inside `async` — see `SYNC_PREFIX`. Shared by every rule
    that reads one of these vocabularies, so the exclusion cannot be fixed in
    one and forgotten in another.
    """
    lowered = name.lower()
    return any(
        bool(_hint_pattern(hint).search(lowered))
        if hint.startswith(SYNC_PREFIX)
        else hint in lowered
        for hint in hints
    )


def _is_connector_shaped(name: str) -> bool:
    """Is this name the SUBJECT half — something a connector would run?

    The ratchet reads `sync`, `connector`, `integration`, `webhook`, `poll` and
    `fetch`.  It excludes `sync` inside `async`, but it deliberately does not
    infer whether a bare sync is local: the real corpus uses the same scheduled
    shape for both local reconciliation and live provider/device work.
    """
    return _mentions(name, TASK_SUBJECT_HINTS)


def _imports_a_scheduler(tree: ast.Module) -> bool:
    """Does this module IMPORT a scheduling framework?

    Read off the import ROOT, matched exactly, so `schedule` the library counts
    and `myapp.schedules` does not. This is a qualifier, never an arm: an import
    names no subject, and `_schedules_a_connector` requires a subject.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name.split(".")[0] in SCHEDULER_MODULES for alias in node.names
            ):
                return True
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in SCHEDULER_MODULES:
                return True
    return False


def _is_scheduling_decorator(node: ast.expr, *, framework: bool) -> bool:
    """Is this decorator expression one that SCHEDULES what it decorates?

    `@shared_task`, `@app.task`, `@celery.task(bind=True)`,
    `@scheduler.scheduled_job(...)`, `@periodic_task`. Both bare and called
    forms, since `@shared_task` and `@shared_task(queue="x")` schedule alike.

    The unambiguous hints are substring-matched against the whole dotted
    spelling, because the word carries the meaning wherever it sits. The
    ambiguous tail `task` is matched as a whole dotted PART and only beside a
    framework import: as a substring it would make `@dataclass` a scheduler.
    """
    target = node.func if isinstance(node, ast.Call) else node
    dotted = _dotted(target)
    if dotted is None:
        return False
    lowered = dotted.lower()
    if any(hint in lowered for hint in SCHEDULING_DECORATOR_HINTS):
        return True
    return framework and AMBIGUOUS_SCHEDULING_DECORATOR in lowered.split(".")


def _named_within(node: ast.expr) -> list[str]:
    """Every identifier-ish name an expression mentions.

    A dotted spelling is not enough once a call appears in the chain:
    `_webhook_tasks().process_whatsapp_webhook` has no dotted spelling at all,
    and the subject is the middle attribute. Reading the names inside the
    expression finds it.
    """
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.append(child.id)
        elif isinstance(child, ast.Attribute):
            names.append(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            names.append(child.value)
    return names


def _dispatch_subjects(node: ast.AST) -> list[str]:
    """Names a task DISPATCH identifies as the task being sent.

    Three shapes, and the third is not optional. `sync_invoices.delay()`
    carries its subject in the receiver. `app.send_task("myapp.sync_invoices")`
    carries it in a string ARGUMENT — a call argument is an executable
    position, which is exactly what a comment and a docstring are not.

    The third is dispatch by REFERENCE: `.delay` handed to a helper rather than
    called here. `dotmac_crm`'s `crm_webhooks` does exactly this —

        _enqueue_webhook_task(
            _webhook_tasks().process_whatsapp_webhook.delay, channel="whatsapp", ...
        )

    — and a first draft of this rule, which only inspected `ast.Call` nodes
    whose own func was a dispatch attribute, dropped a live Celery dispatch of
    a webhook-processing task. The bound handle is the dispatch; whether the
    parentheses are here or in the helper is not the question the rule is
    asking. An `ast.Attribute` is still strictly executable, so nothing about
    prose inertness changes.
    """
    if isinstance(node, ast.Attribute):
        if node.attr not in TASK_DISPATCH_ATTRS:
            return []
        return _named_within(node.value)
    if not isinstance(node, ast.Call):
        return []
    if not isinstance(node.func, ast.Attribute):
        callee = _dotted(node.func)
        if callee is None or callee.split(".")[-1] not in TASK_DISPATCH_ATTRS:
            return []
        receiver_names: list[str] = []
    elif node.func.attr not in TASK_DISPATCH_ATTRS:
        return []
    else:
        receiver_names = _named_within(node.func.value)
    arguments: list[ast.expr] = [*node.args]
    arguments.extend(keyword.value for keyword in node.keywords)
    receiver_names.extend(
        argument.value
        for argument in arguments
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
    )
    return receiver_names


def _registration_subjects(node: ast.Call, *, framework: bool) -> list[str]:
    """Names a scheduler-registration call hands to the scheduler.

    `app.add_periodic_task(3600.0, sync_invoices.s())`,
    `scheduler.add_job(poll_provider, "interval", minutes=5)`,
    `queue.enqueue("myapp.tasks.sync_invoices")`. Positional and keyword
    arguments alike, in name, attribute and string-literal form.
    """
    attribute = node.func.attr if isinstance(node.func, ast.Attribute) else None
    if attribute is None:
        dotted = _dotted(node.func)
        attribute = dotted.split(".")[-1] if dotted else None
    if attribute is None:
        return []
    if attribute not in SCHEDULER_REGISTRATION_ATTRS and not (
        framework and attribute in AMBIGUOUS_REGISTRATION_ATTRS
    ):
        return []
    subjects: list[str] = []
    arguments: list[ast.expr] = [*node.args]
    arguments.extend(keyword.value for keyword in node.keywords)
    for argument in arguments:
        for child in ast.walk(argument):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                subjects.append(child.value)
            elif isinstance(child, ast.Name):
                subjects.append(child.id)
            elif isinstance(child, ast.Attribute):
                subjects.append(child.attr)
    return subjects


def _schedule_table_subjects(tree: ast.Module) -> list[str]:
    """Task names declared in a periodic-task TABLE.

    `beat_schedule = {"nightly": {"task": "myapp.sync_invoices", ...}}` is how
    celery declares a periodic task that carries no decorator at all, so the
    mapping has to be read or that task is invisible. Read narrowly: the
    assignment target must name a schedule table, and the value must sit under
    the literal `task` KEY. A dict key and a mapping value are executable
    positions; prose cannot occupy either.
    """
    subjects: list[str] = []
    for node in ast.walk(tree):
        names = [name.lower() for name in _assigned_names(node)]
        if not any(hint in name for name in names for hint in SCHEDULE_TABLE_NAMES):
            continue
        for child in ast.walk(node):
            if not isinstance(child, ast.Dict):
                continue
            for key, value in zip(child.keys, child.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == SCHEDULE_TABLE_TASK_KEY
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    subjects.append(value.value)
    return subjects


def _schedules_a_connector(tree: ast.Module) -> bool:
    """Does this module SCHEDULE a connector run, in executable code?

    This rule used to open with `any(hint in source.lower() ...)` — a scan of
    the raw file text. That made prose evidence: a comment reading "unlike the
    celery periodic_task we retired" satisfied the whole first conjunct, and any
    ordinary decorator on a connector-shaped name (`@functools.cache` over
    `sync_local_cache`) satisfied the second. Both directions of the acceptance
    check — the word in a comment, and the word in a docstring — scored a
    finding against a module that schedules nothing.

    The words did not change. WHERE THEY ARE READ did. Four arms, each pairing
    executable evidence with the connector-shaped subject the rule has always
    required:

    * DECORATOR — a scheduling-shaped decorator applied to a connector-shaped
      function. The textbook `@shared_task def sync_provider_invoices`.
    * DISPATCH — `.delay(...)`, `.apply_async(...)`, `send_task(...)`, where the
      task sent is connector-shaped. This is the CALLER's half, and it is
      routinely in a different module from the definition.
    * REGISTRATION — a scheduler registration call handed a connector-shaped
      callable: `add_periodic_task`, `add_job`, `register_task`, `enqueue`.
    * SCHEDULE TABLE — a `beat_schedule`-shaped mapping whose `task` entry names
      a connector-shaped callable. Periodic tasks declared this way carry no
      decorator anywhere.

    Importing a scheduling framework is deliberately NOT a fifth arm. An import
    names no subject, and the subject requirement is the whole precision of this
    rule; it serves instead as the QUALIFIER that promotes the two ambiguous
    spellings (`@app.task`, `add_job`/`enqueue`) which mean nothing alone.

    The stated bound, in the conservative direction: a scheduled connector whose
    function name is not connector-shaped and which is registered through a
    spelling not listed here is UNDERCOUNTED. That is the same bound the rule
    always had, and it is a ratchet that can be raised later rather than a
    finding somebody else cannot repair.
    """
    framework = _imports_a_scheduler(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_connector_shaped(node.name) and any(
                _is_scheduling_decorator(decorator, framework=framework)
                for decorator in node.decorator_list
            ):
                return True
        elif isinstance(node, ast.Call):
            subjects = _dispatch_subjects(node)
            subjects.extend(_registration_subjects(node, framework=framework))
            if any(_is_connector_shaped(subject) for subject in subjects):
                return True
        elif isinstance(node, ast.Attribute):
            if any(
                _is_connector_shaped(subject) for subject in _dispatch_subjects(node)
            ):
                return True
    return any(
        _is_connector_shaped(subject) for subject in _schedule_table_subjects(tree)
    )


def _is_checkpoint_class_name(class_name: str) -> bool:
    """Does this class name denote a position in an EXTERNAL feed?

    The class-name rule is the SECONDARY net; a class that declares a watermark
    column is caught below whatever it is called. This rule exists only for feed
    state whose column is named something else.
    """
    lowered = class_name.lower()
    # `synccursor` through `_mentions` as well: `asynccursor` contains it.
    if _mentions(lowered, FEED_CHECKPOINT_CLASS_HINTS):
        return True
    if any(hint in lowered for hint in AMBIGUOUS_CHECKPOINT_CLASS_HINTS):
        # Same false friend: `AsyncCursor` names no feed. See `SYNC_NOT_ASYNC`.
        return _mentions(lowered, EXTERNAL_FEED_HINTS)
    return False


def _holds_a_checkpoint(tree: ast.Module) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and _is_checkpoint_class_name(node.name):
            return True
        if any(
            name.lower() in CHECKPOINT_COLUMN_HINTS for name in _assigned_names(node)
        ):
            return True
    return False


def _is_retry_word(name: str) -> bool:
    return any(hint in name.lower() for hint in RETRY_HINTS)


def _is_retry_literal(node: ast.AST | None) -> bool:
    """A string constant that IS a retry word, rather than one that mentions it.

    EXACTNESS is the whole discriminator for the literal arm. A configuration
    key or a state value is the bare token — `"max_retries"`, `"dead_letter"` —
    while prose that happens to sit inside a call is a sentence:
    `logger.info("no max_retries configured")` must stay silent. Substring
    matching is right for identifiers, where the token is the whole name, and
    wrong for free text.
    """
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False
    return node.value.strip().lower() in RETRY_HINTS


#: Expression forms that BUILD a string out of pieces. A constant inside one is
#: a FRAGMENT of a sentence, never a whole token — see `_literal_arguments`.
_STRING_FRAGMENT_NODES = (ast.JoinedStr, ast.BinOp)


def _literal_arguments(node: ast.expr) -> list[ast.expr]:
    """Every node of an argument expression EXCEPT the pieces of a built string.

    `ast.walk` over a call argument is what lets the literal arm reach a token
    inside a container a call was handed — `state.in_(("dead_letter", ...))` —
    which is a nesting level. It also descends into the two forms that BUILD a
    string out of pieces, and those are a prose channel rather than a nesting
    level, because both CHOP a sentence into fragments the parser stores as
    separate `ast.Constant` nodes:

        log.info(f"gave up after {n} max_retries")   -> Constant ' max_retries'
        log.info("gave up after " + str(n) + " max_retries")   -> the same

    Either fragment strips to exactly the hint, so it arrives at the literal arm
    looking like a configuration token. That defeats EXACTNESS, which is the
    entire discriminator making the literal arm safe — and it is the same defect
    the rewrite exists to close, prose supplying evidence, arriving through the
    parse tree instead of through the raw source text. The unsplit sentence was
    already inert in both spellings; an interpolation or a `+` must not be the
    difference. `"%s max_retries" % n` and `"{} max_retries".format(n)` never
    were, because those keep the sentence in one constant — which is the shape
    of the rule: one constant, one token.

    Skipping these subtrees loses no structure. Every `Call`, `Dict` and
    `Subscript` nested inside one is reached independently by
    `_declares_retry_policy`'s own walk over the whole module, so a real
    configuration mapping written inside a concatenation is still read.

    The bound, stated: `cfg[f"max_retries"]` and `cfg["max" + "_retries"]` — a
    built string with nothing to build — are refused too. Both are spellings
    with no reason to exist, and the plain key still counts.
    """
    kept: list[ast.expr] = []
    stack: list[ast.AST] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, _STRING_FRAGMENT_NODES):
            continue
        if isinstance(current, ast.expr):
            kept.append(current)
        stack.extend(ast.iter_child_nodes(current))
    return kept


def _declares_retry_policy(tree: ast.Module) -> bool:
    """Does this module DECLARE a delivery-retry policy, in executable code?

    Five arms, and the split matters because a retry policy has five ordinary
    spellings and no one of them dominates:

    * IDENTIFIER — a retry-shaped name in ANY executable identifier position: a
      binding (`MAX_RETRIES = 3`, `self.max_retries = n`, and both SQLAlchemy
      declaration styles through `_assigned_names`), a PARAMETER (`ast.arg`),
      or a LOAD (`ast.Name`, as in `if retries >= max_retries`).
    * KEYWORD — a retry-shaped keyword in a call. `transport(max_retries=3)`.
    * ATTRIBUTE — a retry-shaped attribute read. `settings.max_retries`.
    * DECORATOR — `@retry(...)`, `@backoff.on_exception(...)`. The whole policy
      is the decorator; there is no identifier to find.
    * CONFIGURATION LITERAL — a string that IS a retry word, in a mapping key, a
      subscript index, or a call argument.

    The identifier arm reaches parameters and loads because a first draft did
    not, and the corpus said so. `dotmac_sub`'s `meta_pages._request_with_retry`
    is the whole delivery-retry policy of that module — `max_retries: int = 1`
    in the signature, `while True`, `if retries >= max_retries: return
    response`, `Retry-After` honoured, `retries += 1` — and it binds nothing, so
    a rule reading only bindings dropped a live retry loop around an httpx
    client. "It accepts a policy rather than declaring one" is a distinction the
    code does not make: the loop is here.

    The last arm is the one that makes this repair delicate, and it is why the
    fix is not "stop looking at strings". A retry policy carried as data is the
    ordinary spelling — `{"max_retries": 3}` handed to a client, or
    `IntegrationDelivery.state.in_(("dead_letter", ...))` selecting the
    dead-lettered rows. What separates those from prose is POSITION and
    EXACTNESS, and both are required. Position: a mapping key, a subscript index
    and a call argument are places a comment can never be, and a docstring —
    one `ast.Constant` in statement position — reaches none of them. Exactness:
    a configuration or state token IS the word, so the string must EQUAL a retry
    hint rather than contain one. That is what separates `"dead_letter"` used as
    a state value from `logger.info("no max_retries configured")`, which is
    prose that happens to sit inside a call. Refusing string constants outright
    would have made prose inert by trading one false negative for another.

    Exactness has one adversary the parse tree supplies rather than the source
    text, and the walk excludes it: a BUILT string — an f-string, or a `+`
    concatenation — is prose CHOPPED into fragments, and a fragment can be
    exactly the token even when the sentence is not. See `_literal_arguments`.
    """
    for node in ast.walk(tree):
        if any(_is_retry_word(name) for name in _assigned_names(node)):
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for decorator in node.decorator_list:
                target = (
                    decorator.func if isinstance(decorator, ast.Call) else decorator
                )
                dotted = _dotted(target)
                if dotted is not None and (
                    _is_retry_word(dotted)
                    or any(
                        hint in part
                        for part in dotted.lower().split(".")
                        for hint in RETRY_DECORATOR_HINTS
                    )
                ):
                    return True
        elif isinstance(node, ast.arg) and _is_retry_word(node.arg):
            return True
        elif isinstance(node, ast.Name) and _is_retry_word(node.id):
            return True
        elif isinstance(node, ast.Call):
            if any(
                keyword.arg is not None and _is_retry_word(keyword.arg)
                for keyword in node.keywords
            ):
                return True
            arguments: list[ast.expr] = [*node.args]
            arguments.extend(keyword.value for keyword in node.keywords)
            if any(
                _is_retry_literal(child)
                for argument in arguments
                for child in _literal_arguments(argument)
            ):
                return True
        elif isinstance(node, ast.Attribute) and _is_retry_word(node.attr):
            return True
        elif isinstance(node, ast.Dict):
            if any(_is_retry_literal(key) for key in node.keys if key is not None):
                return True
        elif isinstance(node, ast.Subscript) and _is_retry_literal(node.slice):
            return True
    return False


def _owns_delivery_retry(tree: ast.Module, *, outbound: bool = False) -> bool:
    """Delivery-retry machinery, over a real connector surface.

    This rule used to open with `any(hint in source.lower() ...)`, so a comment
    reading "no max_retries here: the caller owns the retry policy" scored
    `delivery_retry` against a module that owns none — and the second conjunct
    could not catch it, because that conjunct is satisfied by the perfectly
    genuine outbound client the comment is about. The word moved into executable
    positions; see `_declares_retry_policy`.

    The second conjunct is where two other false positives COMPOUNDED, and
    both are fixed at their source rather than here. A celery task NAME read
    as a route path made this module a webhook surface, and a client library
    imported only to be CAUGHT made it an outbound one — either way the guard
    whose whole job is to stop a retry loop around a local queue counting as
    delivery machinery was satisfied by something that delivers nothing. See
    `_decorator_path_literals` and `_uses_an_http_transport`.

    SMTP joined the second conjunct when `outbound_transport` grew its second
    arm, and it had to: the conjunct asks whether a real outbound surface is
    present, and reading only HTTP would have left a retry policy over a mail
    relay looking like a retry loop around a local queue. That is the same
    blind spot the rename exists to close, one category over.
    """
    if not _declares_retry_policy(tree):
        return False
    # Only counts alongside an actual outbound or inbound connector surface: a
    # retry loop around a local database write is not delivery machinery. A
    # TRACED outbound call is such a surface, so retry machinery around it is
    # delivery machinery whether or not the client library is used here.
    return (
        outbound
        or _uses_an_http_transport(tree)
        or _speaks_smtp(tree)
        or _is_webhook_surface(tree)
    )


def _classify_connector(
    tree: ast.Module, *, traced_factories: frozenset[str] = frozenset()
) -> frozenset[ConnectorCategory]:
    """Which of the six surfaces this module holds.

    THE CLASSIFIER NO LONGER RECEIVES THE SOURCE TEXT, and that is a contract
    rather than a tidy-up. Two of the six rules opened with a scan of
    `source.lower()`, which made a comment and a docstring evidence; four did
    not. A rule cannot read what it is not given, so removing the parameter
    makes the whole class of regression unrepresentable instead of merely
    absent. The per-unit attribution path was already passing
    `ast.unparse(unit)` here — a text channel that dropped comments and kept
    docstrings, so the two paths did not even agree on what prose was.

    `traced_factories` is the set of spellings that yield an HTTP client in
    THIS module, computed once per repository by `_trace_client_factories`
    within the stated bound. It defaults to empty, so a caller with no
    repository context measures the direct spellings alone rather than
    silently measuring something else.
    """
    found: set[ConnectorCategory] = set()
    outbound = _issues_a_traced_request(tree, traced_factories)
    # `outbound_transport` is one category over TWO arms. The HTTP arm is
    # unchanged from the category's whole history under its old name; the SMTP
    # arm is new, and each carries its own sensitivity, specificity and
    # liveness legs, because a live arm at 94 real sources would otherwise
    # conceal an inert one — see ADR 0018 and `_speaks_smtp`.
    http = outbound or (
        _uses_an_http_transport(tree)
        and _issues_a_request(tree)
        and not _only_constructs_in_process_http_clients(tree)
    )
    smtp = _speaks_smtp(tree)
    webhook = _is_webhook_surface(tree)
    credential = _holds_provider_credential(tree)
    checkpoint = _holds_a_checkpoint(tree)
    if http or smtp:
        found.add(ConnectorCategory.OUTBOUND_TRANSPORT)
    if webhook:
        found.add(ConnectorCategory.WEBHOOK_SURFACE)
    if credential:
        found.add(ConnectorCategory.PROVIDER_CREDENTIAL)
    if _schedules_a_connector(tree):
        found.add(ConnectorCategory.CONNECTOR_TASK)
    if checkpoint:
        found.add(ConnectorCategory.SYNC_CHECKPOINT)
    if _owns_delivery_retry(tree, outbound=outbound):
        found.add(ConnectorCategory.DELIVERY_RETRY)
    return frozenset(found)


# --- Exclusion conservation (ADR 0011) -------------------------------------
#
# An exclusion used to be a SILENT SUBTRACTION. A source proven test-only left
# the universe with nothing but a notice, indistinguishable from every other
# notice, so an unsound classifier could remove a live connector and leave no
# signal. Conservation records what left — but only the part that matters.
#
# WHAT IS CONSERVED, and the narrowness is the point: a connector-shaped
# finding in a test-only source. A test file holding no connector surface
# records nothing. Conserving every test file would put an entire suite in
# every profile and bury the one entry a reviewer has to look at, which is the
# same as recording nothing.
#
# Each record carries four coordinates — path, symbol, category and a
# NORMALIZED AST FINGERPRINT OF THE WHOLE EXCLUDED MODULE — and all four are
# part of the match. That buys three properties, each proved in
# `tests/test_standards_control.py`:
#
# 1. The legitimate transitive test double stays excluded and is CONSERVED.
# 2. Newly hidden connector code — the same trick, a different file — is
#    DETECTED, because it appears as a conserved finding nobody declared.
# 3. Editing a conserved file so it DOES something different invalidates the
#    fingerprint and re-surfaces it — ANYWHERE in the file, not only inside the
#    symbol the record names. The fingerprint was per-unit, and property 3 was
#    FALSE wherever the units failed to cover the file. `_fingerprint` records
#    the three ways they failed and why hashing the module closes all of them.
#
# A declared entry is an acknowledgement, never a waiver. It cannot remove a
# source from the universe: the derivation below does that, and no profile key
# is an input to it. An entry naming a MEASURED source suppresses nothing and
# reports stale.


def _module_level_ordered(tree: ast.Module) -> list[ast.stmt]:
    """`_module_level`'s statements, in SOURCE order.

    `_module_level` reads through import-time wrappers with a stack, so it
    yields them reversed. Detection does not care; a conserved record does,
    because the unit a symbol names has to be assembled the way it was written.
    """
    statements: list[ast.stmt] = []

    def visit(body: Sequence[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith)):
                visit(node.body)
                visit(getattr(node, "orelse", []))
                visit(getattr(node, "finalbody", []))
                for handler in getattr(node, "handlers", []):
                    visit(handler.body)
            else:
                statements.append(node)

    visit(tree.body)
    return statements


def _unit_module(body: Sequence[ast.stmt]) -> ast.Module:
    return ast.Module(body=list(body), type_ignores=[])


def _connector_units(tree: ast.Module) -> list[tuple[str, ast.Module]]:
    """The attributable units of one module: `<module>`, then each definition.

    A unit is the module's own imports plus ONE module-level definition, which
    is what makes a per-symbol classification meaningful — a request call means
    nothing without the import that types it. The `<module>` unit carries the
    imports plus every module-level statement that is not a definition, and it
    is always present, because it is also the fallback for a surface no single
    definition holds.

    A redefined name keeps its LAST definition, which is the one that survives
    at run time.
    """
    statements = _module_level_ordered(tree)
    imports = [
        node for node in statements if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    definitions: dict[str, ast.stmt] = {}
    residue: list[ast.stmt] = []
    for node in statements:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            definitions[node.name] = node
            continue
        residue.append(node)
    units: list[tuple[str, ast.Module]] = [
        (CONSERVED_MODULE_SYMBOL, _unit_module([*imports, *residue]))
    ]
    units.extend(
        (name, _unit_module([*imports, node])) for name, node in definitions.items()
    )
    return units


def _strip_docstrings(tree: ast.AST) -> None:
    """Remove every docstring, in place. Prose is not behaviour."""
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = node.body
        first = body[0] if body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            del body[0]
            if not body:
                body.append(ast.Pass())


def _scope_bindings(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Names this function binds, in document order.

    Parameters, assignments in either declaration style, `for` and `with`
    targets, comprehension targets, walrus targets, `except ... as`, imports
    made inside the body, and the names of nested definitions. A nested
    definition's INTERIOR is a scope of its own and is not read here.
    """
    names: list[str] = []

    def add(name: str | None) -> None:
        if name and name not in names:
            names.append(name)

    arguments = node.args
    for argument in (
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
    ):
        add(argument.arg)
    add(arguments.vararg.arg if arguments.vararg else None)
    add(arguments.kwarg.arg if arguments.kwarg else None)

    def visit(current: ast.AST) -> None:
        if isinstance(current, ast.Name) and isinstance(
            current.ctx, (ast.Store, ast.Del)
        ):
            add(current.id)
        elif isinstance(current, (ast.Import, ast.ImportFrom)):
            for alias in current.names:
                add((alias.asname or alias.name).split(".")[0])
        elif isinstance(current, ast.ExceptHandler):
            add(current.name)
        for child in ast.iter_child_nodes(current):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                add(child.name)
                continue
            visit(child)

    for statement in node.body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            add(statement.name)
            continue
        visit(statement)
    return names


#: The placeholder spelling, before it is reserved against the module it is
#: about to rewrite. `_placeholder_prefix` decides the prefix actually used.
_PLACEHOLDER_STEM = "_l"


def _written_names(tree: ast.AST) -> set[str]:
    """Every identifier the normalization writes into, or leaves standing.

    A superset on purpose. It is read once, to pick a placeholder spelling that
    cannot be confused with anything already in the module, so including a name
    that could not have collided costs a prefix character and nothing else.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.keyword) and node.arg is not None:
            names.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name is not None:
            names.add(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[0])
            if node.asname:
                names.add(node.asname)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def _placeholder_prefix(tree: ast.AST) -> str:
    """A placeholder spelling this module cannot already be using.

    THE PLACEHOLDER NAMESPACE IS NOT THE REPOSITORY'S TO USE, and until it was
    reserved it was shared. Locals are rewritten to `_l{depth}_{index}` while
    module-level names are left standing, because a global is API — so a global
    SPELLED like a placeholder normalized to the same token a local did, and two
    modules that did different things collided on one digest:

        _l0_0 = "https://api.production.example/v1/charge"
        def provider(sandbox_url):  return httpx.get(sandbox_url)
        def provider(sandbox_url):  return httpx.get(_l0_0)

    Same path, same symbol, same category, so the fingerprint was the only
    coordinate that could carry the difference. A reviewed sandbox double could
    be re-pointed at production underneath its own unchanged ledger entry, which
    is conservation with the ratchet taken out.

    The fix is an ESCAPE, not a refusal, because the two obvious alternatives
    buy the collision back as churn: refusing to fingerprint a module that
    mentions such a name would invalidate a record on a rename, and folding the
    original local names into the digest would move it on every rename. The
    prefix grows an underscore until no identifier in the module can be read as
    a placeholder in it, so the mapping stays positional and a rename stays
    free. It is per-module and deterministic, and on every repository measured
    so far no identifier is placeholder-shaped at all, so no existing digest
    moves.

    One stated cost, in the conservative direction: renaming a local TO a
    placeholder-shaped name does move the prefix, and therefore the digest, for
    the whole module. That re-surfaces the record for review rather than hiding
    an edit, and nothing else in the file has to change for it to be correct.
    """
    used = _written_names(tree)
    prefix = _PLACEHOLDER_STEM
    while any(re.fullmatch(rf"{re.escape(prefix)}\d+_\d+", name) for name in used):
        prefix = "_" + prefix
    return prefix


def _normalize_names(
    node: ast.AST, mapping: Mapping[str, str], depth: int, prefix: str
) -> None:
    """Rewrite local bindings to POSITIONAL placeholders, in place.

    Renaming a local is not a change in behaviour, so it must not move a
    fingerprint. Placeholders are positional rather than name-derived: a
    mapping built by sorting the names would move every other local whenever
    one of them was renamed, which is the churn this exists to prevent.

    A function introduces a scope. Its own bindings extend the mapping it
    inherits, so a closure that reads an enclosing local still agrees with it
    and an inner binding that shadows an outer one wins. Placeholders carry
    their scope DEPTH, so an inner `_l1_0` can never be read as an outer
    `_l0_0`. A class body is not treated as a scope: a class attribute is API.

    `prefix` comes from `_placeholder_prefix` and is what keeps the placeholder
    namespace the normalization's own; see that function for the collision it
    closes. It is a parameter rather than a constant because it is a property
    of the module being hashed, not of the engine.

    One stated corner: a nested function's decorator list is rewritten with the
    inner mapping, so an outer name that collides with an inner local name is
    rewritten there as if it were the inner one. It is deterministic and it
    cannot change what is conserved — only which placeholder a hash sees.
    """
    if isinstance(node, ast.Name):
        node.id = mapping.get(node.id, node.id)
    elif isinstance(node, ast.arg):
        node.arg = mapping.get(node.arg, node.arg)
    elif isinstance(node, ast.ExceptHandler) and node.name is not None:
        node.name = mapping.get(node.name, node.name)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        node.name = mapping.get(node.name, node.name)
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            inner = dict(mapping)
            for index, name in enumerate(_scope_bindings(child)):
                inner[name] = f"{prefix}{depth}_{index}"
            _normalize_names(child, inner, depth + 1, prefix)
        else:
            _normalize_names(child, mapping, depth, prefix)


#: Sentinel for a field the running interpreter's node type does not have.
_ABSENT = object()


def _encode(node: object) -> str:
    """Serialize a parse tree the same way on every interpreter.

    `ast.dump` cannot do this and must not be used here. It prints the fields
    the RUNNING interpreter's AST happens to carry, and those move: 3.12 added
    `type_params` to every definition, and 3.13 stopped printing fields that
    hold their default. Three interpreters produced three digests for the same
    source, so a product regenerating its ledger anywhere but on the pinned CI
    Python got `connector.conserved.changed` for every record it had declared,
    with no local way to produce a value CI would accept. That trains a
    reviewer to re-transcribe a ledger without reading it, which is exactly
    what conservation exists to prevent.

    The encoding is therefore explicit and total: fields in `_fields` order, a
    field the interpreter does not define omitted, and a field holding `None`
    or an empty list omitted — the two shapes the versions disagreed about.
    `Constant` is written whole, because omitting a `None` VALUE would erase
    the `None` literal itself. Positions are never read: no `_attributes`.

    The consequence is stated: this digest is a governance artefact with its
    own compatibility, pinned by golden tests. Changing it re-surfaces every
    conserved record in every adopter, so it is a deliberate edit, never a
    side effect of an interpreter upgrade.
    """
    if isinstance(node, ast.Constant):
        kind = f", kind={node.kind!r}" if node.kind is not None else ""
        return f"Constant(value={node.value!r}{kind})"
    if isinstance(node, ast.AST):
        parts: list[str] = []
        for field in node._fields:
            value = getattr(node, field, _ABSENT)
            if value is _ABSENT or value is None:
                continue
            if isinstance(value, list) and not value:
                continue
            parts.append(f"{field}={_encode(value)}")
        return f"{type(node).__name__}({', '.join(parts)})"
    if isinstance(node, list):
        return "[" + ", ".join(_encode(item) for item in node) + "]"
    return repr(node)


def _fingerprint(unit: ast.Module) -> str:
    """A SHA-256 over the normalized parse tree of a WHOLE excluded module.

    Normalized means: source positions dropped, docstrings stripped, locals
    rewritten to positional placeholders. Comments were never in the tree.
    What survives is what the code DOES — the calls it makes, the constants it
    carries, the imports that type them, the attributes it reads — so a
    reformat, a comment, a docstring and a renamed local all leave the record
    standing while a changed URL, a changed call or a changed import does not.

    The whole module, not the attributed unit, and that is a correction rather
    than a preference. A unit is the imports plus ONE definition, and the units
    of a file DO NOT COVER THE FILE: a module-level constant sits only in the
    `<module>` unit, which becomes a record only when some category falls back
    to it; a definition shadowed by a later one with the same name sits in no
    unit at all; and `_module_level_ordered` flattens `with`/`if`/`try`, so the
    wrapper is not in the hashed tree either. Everything a record's symbol did
    not enclose could therefore be rewritten underneath a declared, reviewed
    entry without moving a single coordinate — a double re-pointed from a
    sandbox host to production, an optional-dependency stub swapped for a live
    exfiltration call, a mock deleted from around an import-time request.
    Hashing the module closes all three at once, because it stops depending on
    a decomposition being exhaustive.

    The cost is stated and it is the conservative direction: ANY behavioural
    edit anywhere in a conserved file re-surfaces EVERY conserved record in it,
    including adding an import. Re-declaring is mechanical — the notice carries
    the measured record — and it puts the exclusion back in front of a reviewer,
    which is what the ledger is for. Over-invalidating costs a re-read;
    under-invalidating is the silent subtraction this exists to end.
    """
    normalized = copy.deepcopy(unit)
    _strip_docstrings(normalized)
    _normalize_names(normalized, {}, 0, _placeholder_prefix(normalized))
    return hashlib.sha256(_encode(normalized).encode("utf-8")).hexdigest()


def _conserved_findings(
    relative: PurePosixPath,
    tree: ast.Module,
    traced: frozenset[str],
) -> tuple[ConservedFinding, ...]:
    """The connector-shaped surfaces this EXCLUDED source takes out of scope.

    The module's own classification is authoritative: attribution may name
    which symbol holds a category, never invent one the module does not hold.
    A category no single unit accounts for — a surface the module holds only as
    a whole — is recorded against `<module>` rather than dropped, so the
    conserved set always covers exactly what the module was classified as.

    A unit decides the SYMBOL only. The fingerprint is the whole module's, so
    every record this file publishes carries the same one: attribution tells a
    reviewer where to look, and the fingerprint pins what they read. See
    `_fingerprint` for why a per-unit hash could not.
    """
    categories = _classify_connector(tree, traced_factories=traced)
    if not categories:
        return ()
    units = _connector_units(tree)
    fingerprint = _fingerprint(tree)
    found: set[ConservedFinding] = set()
    attributed: set[ConnectorCategory] = set()
    for symbol, unit in units:
        held = _classify_connector(unit, traced_factories=traced) & categories
        for category in held:
            attributed.add(category)
            found.add(
                ConservedFinding(
                    path=relative,
                    symbol=symbol,
                    category=category,
                    fingerprint=fingerprint,
                )
            )
    for category in sorted(categories - attributed, key=lambda item: item.value):
        found.add(
            ConservedFinding(
                path=relative,
                symbol=CONSERVED_MODULE_SYMBOL,
                category=category,
                fingerprint=fingerprint,
            )
        )
    return tuple(sorted(found, key=_conserved_key))


def _conserved_key(item: ConservedFinding) -> tuple[str, str, str]:
    return (item.path.as_posix(), item.symbol, item.category.value)


# --- The derived measurement universe -------------------------------------
#
# There is no scope declaration to read. The universe is every tracked Python
# source, minus the files an ANALYSIS — not a name, not a directory, not a
# profile key — proves are test-only and unreachable from anything else.


def _package_parts(relative: PurePosixPath) -> tuple[str, ...]:
    """The dotted package a module lives in, honouring a `src` layout.

    `a/b/c.py` and `a/b/__init__.py` both live in package `a.b`, which is what
    a relative import in either of them resolves against.
    """
    parts = PurePosixPath(relative.as_posix().removesuffix(".py")).parts
    source_roots = [index for index, part in enumerate(parts[:-1]) if part == "src"]
    module_parts = parts[source_roots[-1] + 1 :] if source_roots else parts
    return module_parts[:-1]


def _module_names(relative: PurePosixPath) -> frozenset[str]:
    """Every importable name that resolves to this repository path."""
    parts = PurePosixPath(relative.as_posix().removesuffix(".py")).parts
    source_roots = [index for index, part in enumerate(parts[:-1]) if part == "src"]
    module_parts = parts[source_roots[-1] + 1 :] if source_roots else parts
    names = {".".join(module_parts)}
    if module_parts and module_parts[-1] == "__init__":
        names.add(".".join(module_parts[:-1]))
    return frozenset(name for name in names if name)


def _prefixes(module: str) -> frozenset[str]:
    """`a.b.c` also executes `a` and `a.b`, so both are reached."""
    parts = module.split(".")
    return frozenset(
        ".".join(parts[: index + 1]) for index in range(len(parts)) if parts[index]
    )


def _imported_names(tree: ast.Module, relative: PurePosixPath) -> frozenset[str]:
    """Absolute module names this source imports, relative imports resolved."""
    package = _package_parts(relative)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names |= _prefixes(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # `from . import x` resolves against the importer's own
                # package; each extra dot climbs one level out of it.
                if node.level - 1 > len(package):
                    continue
                base = package[: len(package) - (node.level - 1)]
                prefix = (
                    ".".join((*base, node.module)) if node.module else ".".join(base)
                )
            else:
                prefix = node.module or ""
            if not prefix:
                continue
            names |= _prefixes(prefix)
            for alias in node.names:
                if alias.name != "*":
                    names.add(f"{prefix}.{alias.name}")
    return frozenset(names)


#: A string constant that is ENTIRELY a dotted identifier path. Anchored and
#: identifier-shaped on purpose: prose that merely mentions a module is not a
#: reference to it, and a docstring can never match.
DOTTED_MODULE_NAME = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\Z"
)
#: The literal head of an ASSEMBLED dotted name — `f"product.integrations.{n}"`.
#: A registry that resolves providers per deployment builds the path rather than
#: writing it out, so no complete constant exists anywhere in the tree.
DOTTED_PACKAGE_PREFIX = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\.\Z"
)


def _named_modules(tree: ast.Module) -> frozenset[str]:
    """Module names this source NAMES as a string.

    Dynamic wiring is how integrations are ordinarily reached: a plugin
    registry, `importlib.import_module`, a console-script entry point, a Celery
    autodiscover list, a Django settings string. None of those is an import
    edge, so an import-graph-only notion of reachability concluded that a
    public, undisguised provider client whose only static importer was its own
    honest unit test could be removed from the universe. Writing the test was
    what bought the exemption and deleting it was what turned the build red,
    which is the incentive precisely inverted.

    The `module:attribute` entry-point form is split, so both halves of
    `"product.integrations.mailgun:build"` are read as naming the module.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        candidate = node.value.split(":", 1)[0].strip()
        if DOTTED_MODULE_NAME.match(candidate):
            names |= _prefixes(candidate)
    return frozenset(names)


def _named_packages(tree: ast.Module) -> frozenset[str]:
    """Package prefixes this source assembles a module name under.

    `importlib.import_module(f"product.integrations.{name}")` reaches a module
    the engine cannot individually identify, so it may not conclude that ANY
    module under that package is unreachable. The literal head must be a dotted
    package path: an interpolated URL is not a module reference.
    """
    prefixes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            head = value.value.split(":", 1)[0]
            if DOTTED_PACKAGE_PREFIX.match(head):
                prefixes.add(head)
    return frozenset(prefixes)


def _importers(
    trees: dict[PurePosixPath, ast.Module],
) -> dict[PurePosixPath, frozenset[PurePosixPath]]:
    """Reverse reachability graph over the tracked universe.

    An edge is an import OR a dotted name held as a string, because both reach
    the module. Naming a module is deliberately treated as reaching it even
    when the string is incidental: the error lands on the side of measuring
    more, and only ever costs an exclusion nobody was owed.
    """
    by_module: dict[str, set[PurePosixPath]] = {}
    for relative in trees:
        for name in _module_names(relative):
            by_module.setdefault(name, set()).add(relative)
    result: dict[PurePosixPath, set[PurePosixPath]] = {
        relative: set() for relative in trees
    }
    for relative, tree in trees.items():
        for name in _imported_names(tree, relative) | _named_modules(tree):
            for target in by_module.get(name, ()):
                if target != relative:
                    result[target].add(relative)
        for prefix in _named_packages(tree):
            for name, targets in by_module.items():
                if not name.startswith(prefix):
                    continue
                for target in targets:
                    if target != relative:
                        result[target].add(relative)
    return {relative: frozenset(value) for relative, value in result.items()}


def _is_test_name(name: str) -> bool:
    return name == "test" or name.startswith("test_")


def _module_level(tree: ast.Module) -> list[ast.stmt]:
    """Statements a module runs at import time, THROUGH its wrappers.

    An optional-dependency guard (`try: import httpx / except ImportError:`
    then `if httpx is not None:`) is the idiomatic way to write a gateway, and
    it takes the class out of `tree.body` — so a module offering a public
    connector class read as offering no public surface at all.
    """
    remaining = list(tree.body)
    statements: list[ast.stmt] = []
    while remaining:
        node = remaining.pop()
        if isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith)):
            remaining.extend(node.body)
            remaining.extend(getattr(node, "orelse", []))
            remaining.extend(getattr(node, "finalbody", []))
            for handler in getattr(node, "handlers", []):
                remaining.extend(handler.body)
            continue
        statements.append(node)
    return statements


def _is_test_class(node: ast.ClassDef) -> bool:
    """A class a runner would COLLECT, not a class merely NAMED like one.

    A bare `Test` prefix is a name, and the inherited exemption discipline is
    that an exemption states an enforceable premise rather than a name. It did
    not: a public runtime class called `TestFlightPaymentGateway` — a sandbox
    payment gateway — was read as a declared test AND as no public surface,
    which is the entire exemption bought with a product noun.
    """
    if any((_name(base) or "").endswith("TestCase") for base in node.bases):
        return True
    if not node.name.startswith("Test"):
        return False
    return any(
        isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_test_name(child.name)
        for child in node.body
    )


def _declares_a_test(tree: ast.Module) -> bool:
    """Does this module declare a test AT MODULE LEVEL?

    Walking the whole tree counted any nested definition, so an ordinary
    `def test_connection(self)` health probe on a live gateway, and a
    `test_delivery` method on a private alerter, each declared their module a
    test. A method is not a module's test declaration.
    """
    for node in _module_level(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_test_name(
            node.name
        ):
            return True
        if isinstance(node, ast.ClassDef) and _is_test_class(node):
            return True
    return False


def _is_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if _name(target) == "fixture":
            return True
    return False


def _public_runtime_definitions(tree: ast.Module) -> tuple[str, ...]:
    """Module-level names this source offers to anything that imports it.

    A test module offers tests, fixtures and private helpers. A module that
    also offers a public non-test callable is offering runtime surface, and a
    single fake `def test_ping()` must not buy it an exemption.

    Read through import-time wrappers, not off `tree.body`: a public class
    defined under an optional-dependency guard is still public surface.
    """
    offered: list[str] = []
    for node in _module_level(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                not node.name.startswith("_")
                and not _is_test_name(node.name)
                and not _is_fixture(node)
            ):
                offered.append(node.name)
        elif isinstance(node, ast.ClassDef):
            if not node.name.startswith("_") and not _is_test_class(node):
                offered.append(node.name)
    return tuple(offered)


def _has_entry_point(tree: ast.Module) -> bool:
    """A `__main__` guard makes a file runnable without anyone importing it."""
    for node in tree.body:
        if not isinstance(node, ast.If):
            continue
        for child in ast.walk(node.test):
            if isinstance(child, ast.Name) and child.id == "__name__":
                return True
    return False


def _declared_runtime_paths(profile: StandardsProfile) -> frozenset[PurePosixPath]:
    """Paths the PROFILE itself declares are application runtime.

    An authority's owner implementation, its canonical writers and its adapters,
    and a typed contract surface, are runtime code BY DECLARATION. The scope
    analysis may not then conclude they are test-only — that is one profile
    contradicting itself into a green build, and it did: a declared canonical
    writer holding a live provider client was removed from the universe because
    the only source importing it was the drift test the same profile declares.

    `drift_test_paths` are deliberately absent. The profile declares those to be
    tests, so pinning them would contradict the declaration in the other
    direction.
    """
    paths: set[PurePosixPath] = set()
    for authority in profile.authorities:
        paths.add(authority.owner_implementation)
        paths.update(authority.canonical_writer_paths)
        paths.update(authority.adapter_paths)
    for surface in profile.typed_contract_surfaces:
        paths.update(surface.paths)
    return frozenset(paths)


def _derive_scope(
    root: Path,
    inventory: tuple[PurePosixPath, ...] | None,
    untracked: UntrackedPopulations,
    pinned: frozenset[PurePosixPath] = frozenset(),
) -> ConnectorScope:
    """Partition the tracked universe into measured and proven-test-only.

    Two monotone passes, each to a fixed point, so the result does not depend
    on iteration order:

    1. SHRINK the seeds. A seed is a source that declares a test and offers no
       public runtime definition. A seed imported by anything outside the seed
       set is dropped, and dropping it can drop the seed that imported it.
    2. GROW the helpers. A source imported by at least one candidate, and by
       nothing outside the candidate set, joins it — which is how `A imports B
       imports C` excludes C only once A and B are themselves excluded.

    Anything reachable from a non-candidate is measured, whatever it is named
    and wherever it sits. A source that nothing imports is measured too: being
    unreferenced is not evidence of being a test. A source the PROFILE declares
    is runtime is never a candidate at all.

    What is removed is then CONSERVED: every connector-shaped surface inside an
    excluded source is recorded, so the subtraction is ratcheted rather than
    silent.
    """
    if inventory is None:
        return ConnectorScope(
            inventory_available=False,
            measured=(),
            excluded=(),
            untracked_visible=untracked.visible,
            untracked_ignored=untracked.ignored,
        )
    # Only trees are retained. The raw text is read to parse it and then
    # dropped, so no downstream rule can fall back to scanning it.
    trees: dict[PurePosixPath, ast.Module] = {}
    for relative in inventory:
        source = root / relative
        try:
            trees[relative] = ast.parse(
                source.read_text(encoding="utf-8"), filename=str(source)
            )
        except (OSError, UnicodeError, SyntaxError):
            # Fail closed. A source the engine cannot read has no evidence of
            # being test-only, so it stays measured and the connector sweep
            # reports why it could not be measured.
            continue
    importers = _importers(trees)

    reason: dict[PurePosixPath, str] = {}
    candidates: set[PurePosixPath] = set()
    for relative, tree in trees.items():
        if _has_entry_point(tree) or relative in pinned:
            continue
        if relative.suffix not in PYTHON_SUFFIXES:
            continue
        if not _declares_a_test(tree):
            continue
        offered = _public_runtime_definitions(tree)
        if offered:
            continue
        candidates.add(relative)
        reason[relative] = (
            "declares tests and offers no public runtime definition, and no "
            "source outside the excluded set imports it"
        )

    changed = True
    while changed:
        changed = False
        for relative in sorted(candidates, key=lambda item: item.as_posix()):
            if importers[relative] - candidates:
                candidates.discard(relative)
                reason.pop(relative, None)
                changed = True

    eligible = {
        relative
        for relative, tree in trees.items()
        if relative not in candidates
        and relative not in pinned
        and relative.suffix in PYTHON_SUFFIXES
        and not _has_entry_point(tree)
    }
    changed = True
    while changed:
        changed = False
        for relative in sorted(eligible, key=lambda item: item.as_posix()):
            reached = importers[relative]
            if not reached or reached - candidates:
                continue
            candidates.add(relative)
            eligible.discard(relative)
            named = sorted(item.as_posix() for item in reached)
            shown = ", ".join(named[:3])
            if len(named) > 3:
                shown += f", and {len(named) - 3} more"
            reason[relative] = f"imported only by excluded test-only sources ({shown})"
            changed = True

    measured = tuple(
        sorted(
            (relative for relative in inventory if relative not in candidates),
            key=lambda item: item.as_posix(),
        )
    )
    excluded = tuple(
        ExcludedSource(path=relative, reason=reason[relative])
        for relative in sorted(candidates, key=lambda item: item.as_posix())
    )

    # Conservation runs over the WHOLE inventory's trace, not the measured
    # half: a test double reaching a project-local transport is exactly the
    # shape being conserved, and resolving it needs the modules it reaches. It
    # is a separate resolution from the one the measured counts use, and it
    # cannot move them.
    conserved: list[ConservedFinding] = []
    if candidates:
        traced = _trace_client_factories(trees)
        for relative in sorted(candidates, key=lambda item: item.as_posix()):
            # Every candidate came from `trees`, so this is a total lookup; the
            # guard is here so a future caller cannot make it a KeyError.
            parsed = trees.get(relative)
            if parsed is None:
                continue
            conserved.extend(
                _conserved_findings(relative, parsed, traced.get(relative, frozenset()))
            )
    return ConnectorScope(
        inventory_available=True,
        measured=measured,
        excluded=excluded,
        untracked_visible=untracked.visible,
        untracked_ignored=untracked.ignored,
        conserved=tuple(conserved),
    )


def connector_scope(
    root: Path, profile: StandardsProfile | None = None
) -> ConnectorScope:
    """Publish the derived connector universe for one repository."""
    inventory = _tracked_python_sources(root)
    untracked = (
        _untracked_python_populations(root)
        if inventory is not None
        else UntrackedPopulations((), ())
    )
    pinned = _declared_runtime_paths(profile) if profile is not None else frozenset()
    return _derive_scope(root, inventory, untracked, pinned)


def _conserved(
    declared: tuple[ConservedFinding, ...], observed: tuple[ConservedFinding, ...]
) -> list[Diagnostic]:
    """Reconcile the declared conservation ledger against what was observed.

    Set equality on (path, symbol, category), with the fingerprint checked on
    every match. Three ways to fail, and they are the three properties this
    mechanism buys:

    * OBSERVED BUT NOT DECLARED — a connector-shaped surface left the universe
      and nobody has seen it. This is the arm that catches the same trick in a
      different file.
    * DECLARED BUT NOT OBSERVED — a conservation that stopped happening, which
      is indistinguishable from a classifier that stopped seeing something. It
      is the downward arm the baselines already have.
    * MATCHED WITH A DIFFERENT FINGERPRINT — the conserved code now does
      something else. Every other coordinate is identical, so only the
      fingerprint can carry that, and it must.
    """
    findings: list[Diagnostic] = []
    by_declared = {_conserved_key(item): item for item in declared}
    by_observed = {_conserved_key(item): item for item in observed}
    for item in sorted(observed, key=_conserved_key):
        findings.append(
            _notice(
                DiagnosticCode.CONNECTOR_CONSERVED_RECORDED,
                "conserved connector surface removed from the measured "
                "universe; declare it in "
                "external_connector_surface.conserved_exclusions: "
                + json.dumps(item.to_dict(), sort_keys=True),
                path=item.path,
            )
        )
    for key in sorted(by_observed.keys() - by_declared.keys()):
        item = by_observed[key]
        findings.append(
            _finding(
                DiagnosticCode.CONNECTOR_CONSERVED_UNDECLARED,
                f"{item.symbol!r} holds {item.category.value} and left the "
                "measured universe, but no conserved exclusion declares it; "
                "an exclusion nobody has reviewed is the hiding place this "
                "ledger exists to close. Read WHY it left before you declare "
                f"it — the {DiagnosticCode.CONNECTOR_SCOPE_EXCLUDED.value} "
                "notice on this path carries the derivation's own reason, and "
                "most conserved files are not tests: a file is usually removed "
                "for being unreachable from measured code, which is a claim "
                "about reachability and not about what the file IS. Declare "
                "it: " + json.dumps(item.to_dict(), sort_keys=True),
                path=item.path,
            )
        )
    for key in sorted(by_declared.keys() - by_observed.keys()):
        item = by_declared[key]
        findings.append(
            _finding(
                DiagnosticCode.CONNECTOR_CONSERVED_STALE,
                f"the conserved exclusion for {item.symbol!r} "
                f"({item.category.value}) matches nothing measured here; "
                "retire it in the SAME change that deletes the code it "
                "recorded, so the retirement is reviewed rather than inferred. "
                "A conserved entry never removes a source from the universe, "
                "so this is also what an entry naming measured code reports",
                path=item.path,
            )
        )
    for key in sorted(by_declared.keys() & by_observed.keys()):
        expected = by_declared[key]
        actual = by_observed[key]
        if expected.fingerprint == actual.fingerprint:
            continue
        findings.append(
            _finding(
                DiagnosticCode.CONNECTOR_CONSERVED_CHANGED,
                f"the conserved {actual.category.value} surface held by "
                f"{actual.symbol!r} no longer matches its recorded "
                f"fingerprint (declared {expected.fingerprint}, measured "
                f"{actual.fingerprint}); the code does something different "
                "now, so the exclusion has to be reviewed again rather than "
                "inherited. Re-declare it: "
                + json.dumps(actual.to_dict(), sort_keys=True),
                path=actual.path,
            )
        )
    return findings


def _external_connector(
    root: Path, profile: StandardsProfile, scope: ConnectorScope
) -> list[Diagnostic]:
    surface = profile.external_connector_surface
    findings: list[Diagnostic] = [
        _notice(
            DiagnosticCode.CONNECTOR_SCOPE_EXCLUDED,
            f"removed from the measured universe: {item.reason}",
            path=item.path,
        )
        for item in scope.excluded
    ]
    findings.extend(_conserved(surface.conserved_exclusions, scope.conserved))
    # Trees only; see `_classify_connector` on why the text channel is gone.
    trees: dict[PurePosixPath, ast.Module] = {}
    for relative in scope.measured:
        source = root / relative
        try:
            trees[relative] = ast.parse(
                source.read_text(encoding="utf-8"), filename=str(source)
            )
        except (OSError, UnicodeError, SyntaxError) as error:
            # Fail closed: an unreadable source is not a measured zero.
            findings.append(
                _finding(
                    DiagnosticCode.CONNECTOR_SYNTAX_INVALID,
                    f"cannot measure external-connector surfaces here: {error}",
                    path=relative,
                    line=error.lineno if isinstance(error, SyntaxError) else None,
                )
            )

    # Tracing is a property of the REPOSITORY, not of one file, so it is
    # resolved once over the measured universe and then consulted per file.
    traced = _trace_client_factories(trees)

    observed = dict.fromkeys(ConnectorCategory, 0)
    for relative, tree in trees.items():
        classified = _classify_connector(
            tree, traced_factories=traced.get(relative, frozenset())
        )
        for category in classified:
            observed[category] += 1

    for baseline in surface.baselines:
        count = observed[baseline.category]
        if count > baseline.count:
            findings.append(
                _finding(
                    DiagnosticCode.CONNECTOR_BASELINE_EXCEEDED,
                    f"{baseline.category.value}: {count} measured sources exceed "
                    f"the declared baseline {baseline.count}; a new direct "
                    "external-connector surface landed",
                )
            )
        elif count < baseline.count:
            findings.append(
                _finding(
                    DiagnosticCode.CONNECTOR_BASELINE_STALE,
                    f"{baseline.category.value}: {count} measured sources are "
                    f"below the declared baseline {baseline.count}; lower the "
                    "baseline in the SAME change that deletes the code, so the "
                    "retirement is reviewed rather than inferred",
                )
            )
    return findings


# --- ADR 0014: build once, bind the environment late -------------------------
#
# The standard's four properties, minus the two a repository may not assert
# about itself. Whether a pipeline produced all four digests, and whether an
# authorization named them, are facts about workflow runs and about another
# repository's records; ADR 0013 § 1 puts those outside repository-local
# derivation and § 5 permits automation only where a contract carries a
# declared oracle kind. This family checks what IS decidable from repository
# content, and ADR 0014's drift-prevention section states the rest as
# review discipline rather than implying coverage.
#
# The DECLARATION and the RENDER are checked differently on purpose. A
# declaration must carry no environment fact at all. A render is that
# declaration plus one environment, so a derived loopback literal is expected
# there and an address check over rendered output would refuse the correct
# result. What both must hold is an immutable image digest.

#: Filenames that name credential material. A basename is a BINDING, and
#: ADR 0014 § 4 excludes it alongside the value precisely because a redaction
#: sweep shaped for values passes straight over it.
_CREDENTIAL_FILENAMES = frozenset(
    {".env", ".netrc", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
)
_CREDENTIAL_SUFFIXES = (
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keytab",
    ".kdbx",
    ".ppk",
)

#: A token is read as an image reference only in these positions. Scanning
#: every string for something image-shaped would flag a module path; reading
#: the KEY keeps the check narrow enough to be believed.
_IMAGE_ASSIGNMENT = re.compile(
    r"""(?:^|[\s,{[])(?:image|reference)\s*[:=]\s*["']?([^"'\s,}\]]+)""",
    re.IGNORECASE,
)
_IMAGE_DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
#: Anything that could be an image reference at all: a registry path, or a
#: name carrying a tag. A bare word is not one, so `image = true` is ignored
#: rather than reported as an unpinned image.
_IMAGE_SHAPED = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._/-]*(?::[A-Za-z0-9._-]+)?(?:@[A-Za-z0-9:._-]+)?$"
)
_ADDRESS_TOKEN = re.compile(r"[0-9A-Fa-f:.]+(?:/[0-9]{1,3})?")


def _reads(root: Path, relative: PurePosixPath) -> tuple[str | None, Diagnostic | None]:
    """Read one declared file, turning every failure into a diagnostic.

    Fails closed. A surface the engine cannot read is reported, never skipped:
    a skip is indistinguishable from a pass in a report a human scans.
    """
    target = root / Path(relative)
    if not target.exists():
        return None, _finding(
            DiagnosticCode.DEPLOYMENT_SURFACE_MISSING,
            "the profile declares this deployment surface and the repository "
            "does not contain it; a surface that names nothing passes every "
            "content check for the wrong reason",
            path=relative,
        )
    try:
        return target.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as error:
        return None, _finding(
            DiagnosticCode.DEPLOYMENT_SURFACE_UNREADABLE,
            f"cannot read the declared deployment surface: {type(error).__name__}",
            path=relative,
        )


def _unpinned_images(body: str, relative: PurePosixPath) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    for number, line in enumerate(body.splitlines(), start=1):
        for value in _IMAGE_ASSIGNMENT.findall(line):
            if not _IMAGE_SHAPED.match(value) and "${" not in value:
                continue
            if _IMAGE_DIGEST.search(value):
                continue
            if "${" in value:
                # A deploy-time substitution is not an artefact-carried digest.
                # ADR 0014 § 3 says the artefact holds exact digests, and a
                # variable is exactly the escape that would let a repository
                # replace every digest and stay green.
                findings.append(
                    _finding(
                        DiagnosticCode.DEPLOYMENT_IMAGE_NOT_PINNED,
                        f"{value} defers the image to a deploy-time "
                        "substitution; ADR 0014 requires the artefact to carry "
                        "the exact digest, because a value resolved later "
                        "cannot be the value that was approved",
                        path=relative,
                        line=number,
                    )
                )
                continue
            if "/" not in value and ":" not in value:
                continue
            findings.append(
                _finding(
                    DiagnosticCode.DEPLOYMENT_IMAGE_NOT_PINNED,
                    f"{value} is a mutable reference; ADR 0014 requires an "
                    "immutable @sha256: digest, because a tag makes what ran "
                    "yesterday and what runs after the next restart two "
                    "deployments with one description",
                    path=relative,
                    line=number,
                )
            )
    return findings


def _environment_literals(body: str, relative: PurePosixPath) -> list[Diagnostic]:
    """Addresses and CIDRs, PARSED rather than pattern-matched.

    A regex for something address-shaped reports a version string and a port
    range. `ipaddress` decides, so `1.2.3` and `8000-8080` are not findings and
    `10.0.0.0/8` is.
    """
    findings: list[Diagnostic] = []
    for number, line in enumerate(body.splitlines(), start=1):
        for token in _ADDRESS_TOKEN.findall(line):
            candidate = token.strip(".:")
            if (
                not candidate
                or "sha256" in line
                and candidate in line.split("sha256")[-1]
            ):
                continue
            if len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate):
                continue
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                try:
                    ipaddress.ip_network(candidate, strict=False)
                except ValueError:
                    continue
            findings.append(
                _finding(
                    DiagnosticCode.DEPLOYMENT_ENVIRONMENT_LITERAL,
                    f"{candidate} is an environment address; ADR 0014 § 4 "
                    "excludes it from the artefact and § 5 binds it late, "
                    "because an address committed here differs per environment "
                    "and goes stale with nothing failing",
                    path=relative,
                    line=number,
                )
            )
    return findings


def _credential_filenames(body: str, relative: PurePosixPath) -> list[Diagnostic]:
    findings: list[Diagnostic] = []
    for number, line in enumerate(body.splitlines(), start=1):
        for raw in re.findall(r"[A-Za-z0-9_.\-/]+", line):
            name = raw.rsplit("/", 1)[-1]
            if name in _CREDENTIAL_FILENAMES or name.endswith(_CREDENTIAL_SUFFIXES):
                findings.append(
                    _finding(
                        DiagnosticCode.DEPLOYMENT_CREDENTIAL_FILENAME,
                        f"{name} names credential material; ADR 0014 § 4 "
                        "excludes a credential FILENAME alongside the value, "
                        "because a basename is a binding and a sweep shaped "
                        "for values passes straight over it",
                        path=relative,
                        line=number,
                    )
                )
    return findings


#: Filenames that ARE a deployment declaration in this fleet. Used only to
#: decide whether declaring NO surface is credible — never to guess what a
#: surface contains.
_DEPLOYMENT_ARTEFACT_NAMES = frozenset(
    {
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
        "product.toml",
    }
)


def _undeclared_deployment_artefacts(root: Path) -> list[PurePosixPath]:
    """Deployment declarations the repository ships and the profile does not name.

    Without this, an empty `deployment_artefact_surfaces` is a way to ship a
    deployment and stay green by declining to mention it — the exact vacuous
    pass ADR 0018 refuses. The detector is narrow on purpose: it recognises the
    file NAMES this fleet actually deploys from, and never inspects content, so
    it cannot drift into guessing.
    """
    found: list[PurePosixPath] = []
    for candidate in sorted(root.rglob("*")):
        if not candidate.is_file() or candidate.name not in _DEPLOYMENT_ARTEFACT_NAMES:
            continue
        relative = PurePosixPath(candidate.relative_to(root).as_posix())
        if any(part in {".git", "node_modules", ".venv"} for part in relative.parts):
            continue
        found.append(relative)
    return found


def _deployment_artefact(
    root: Path, surfaces: tuple[DeploymentArtefactSurface, ...]
) -> list[Diagnostic]:
    """ADR 0014, over every declared deployment surface."""
    findings: list[Diagnostic] = []
    declared = {path for surface in surfaces for path in surface.declaration_paths} | {
        path for surface in surfaces for path in surface.rendered_paths
    }
    for shipped in _undeclared_deployment_artefacts(root):
        if shipped in declared:
            continue
        if any(
            shipped.is_relative_to(rendered)
            for surface in surfaces
            for rendered in surface.rendered_paths
        ):
            continue
        findings.append(
            _finding(
                DiagnosticCode.DEPLOYMENT_SURFACE_UNDECLARED,
                "the repository ships this deployment declaration and the "
                "profile does not name it; a pin that does not say what is "
                "enforced cannot fail when the enforcement stops covering "
                "something",
                path=shipped,
            )
        )
    for surface in surfaces:
        for relative in surface.declaration_paths:
            body, problem = _reads(root, relative)
            if problem is not None:
                findings.append(problem)
                continue
            assert body is not None
            findings.extend(_unpinned_images(body, relative))
            findings.extend(_environment_literals(body, relative))
            findings.extend(_credential_filenames(body, relative))
        for relative in surface.rendered_paths:
            target = root / Path(relative)
            if target.is_dir():
                members = sorted(item for item in target.rglob("*") if item.is_file())
                if not members:
                    findings.append(
                        _finding(
                            DiagnosticCode.DEPLOYMENT_SURFACE_MISSING,
                            "the profile declares rendered output here and the "
                            "directory holds none",
                            path=relative,
                        )
                    )
                for member in members:
                    child = PurePosixPath(member.relative_to(root).as_posix())
                    body, problem = _reads(root, child)
                    if problem is not None:
                        findings.append(problem)
                        continue
                    assert body is not None
                    findings.extend(_unpinned_images(body, child))
                continue
            body, problem = _reads(root, relative)
            if problem is not None:
                findings.append(problem)
                continue
            assert body is not None
            findings.extend(_unpinned_images(body, relative))
        workflow, problem = _reads(root, surface.render_check_workflow)
        if problem is not None:
            findings.append(problem)
            continue
        assert workflow is not None
        if surface.render_check_command not in workflow:
            findings.append(
                _finding(
                    DiagnosticCode.DEPLOYMENT_RENDER_CHECK_ABSENT,
                    f"this workflow does not run {surface.render_check_command!r}; "
                    "ADR 0014 requires rendered assets to be compared "
                    "byte-for-byte rather than produced on the target host, and "
                    "a render nobody compares is a deployment nobody approved",
                    path=surface.render_check_workflow,
                )
            )
    return findings


def verify_repository(
    root: Path,
    profile_path: Path,
    *,
    observed_repository: CanonicalRepository | None = None,
    observed_default_branch: BranchName | None = None,
    governance_root: Path | None = None,
    observed_governance_repository: CanonicalRepository | None = None,
    observed_governance_revision: GitRevision | None = None,
) -> ConformanceReport:
    """Evaluate one repository through the single typed policy owner."""
    try:
        profile = load_profile(profile_path)
    except ProfileError as error:
        return ConformanceReport(
            None, None, (_finding(DiagnosticCode.PROFILE_INVALID, str(error)),)
        )
    findings: list[Diagnostic] = []
    repository = observed_repository or _git_origin(root)
    if repository is None:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_IDENTITY_UNAVAILABLE,
                "Git origin identity is unavailable",
            )
        )
    elif repository != profile.repository.canonical_url:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_IDENTITY_MISMATCH,
                f"expected {profile.repository.canonical_url!r}, found {repository!r}",
            )
        )
    default_branch = observed_default_branch or _git_default_branch(root)
    if default_branch is None:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_DEFAULT_BRANCH_UNAVAILABLE,
                "Git default branch is unavailable; CI must pass trusted repository metadata",
            )
        )
    elif default_branch != profile.repository.default_branch:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_DEFAULT_BRANCH_MISMATCH,
                f"expected branch {profile.repository.default_branch!r}, found {default_branch!r}",
            )
        )
    findings.extend(
        _governance(
            root,
            profile,
            governance_root=governance_root,
            observed_governance_repository=observed_governance_repository,
            observed_governance_revision=observed_governance_revision,
        )
    )
    findings.extend(
        _connector_runtime_dependencies(
            root,
            profile,
            governance_root=governance_root,
        )
    )
    findings.extend(_authorities(root, profile))
    for surface in profile.typed_contract_surfaces:
        findings.extend(_typed(root, surface))
    for vocabulary in profile.module_declared_vocabularies:
        findings.extend(_vocabulary(root, vocabulary))
    inventory = _tracked_python_sources(root)
    untracked = (
        _untracked_python_populations(root)
        if inventory is not None
        else UntrackedPopulations((), ())
    )
    connector_source_roots = _connector_source_distribution_roots(
        root,
        profile,
        governance_root=governance_root,
    )
    measured_inventory = _outside_connector_source_distributions(
        inventory, connector_source_roots
    )
    for source_root in connector_source_roots:
        findings.append(
            _notice(
                DiagnosticCode.CONNECTOR_SOURCE_DISTRIBUTION_EXCLUDED,
                "Governance authorizes this repository to author connector "
                "distributions, and the committed non-runtime Poetry resolution "
                "plus connector entry point prove this package is distribution "
                "source rather than legacy product-runtime connector debt",
                path=source_root / "pyproject.toml",
            )
        )
    scope = _derive_scope(
        root,
        measured_inventory,
        untracked,
        _declared_runtime_paths(profile),
    )
    for relative in _grafted_trees(root):
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_TREE_UNMEASURED,
                "this index entry grafts a tree whose contents are absent from "
                "this repository's index, so no universe derived here can "
                "measure them; that region is unmonitored rather than exempt",
                path=relative,
            )
        )
    if not scope.inventory_available:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_INVENTORY_UNAVAILABLE,
                "the repository's tracked Python inventory is unavailable, so no "
                "measured universe can be derived; an unmeasurable repository is "
                "not a conformant one",
            )
        )
    for relative in scope.untracked_visible:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_SOURCE_UNTRACKED,
                "this Python source is on disk but outside the tracked "
                "inventory, so it is unmonitored rather than exempt; track it, "
                "or remove it from the working tree",
                path=relative,
            )
        )
    for relative in scope.untracked_ignored:
        findings.append(
            _finding(
                DiagnosticCode.REPOSITORY_SOURCE_UNTRACKED,
                "this Python source is on disk, is hidden by this repository's "
                "own ignore rules, and is outside the tracked inventory, so it "
                "is unmonitored rather than exempt. An ignore rule is "
                "product-authored and decides nothing about what is measured — "
                "it is reported as its own population so that it can be seen, "
                "never so that it can be forgiven. No worktree-controlled "
                "dependency metadata may authorize it away. Track it, remove "
                "it from the working tree, or keep the environment outside "
                "the repository",
                path=relative,
            )
        )
    findings.extend(_testing_kit(root, profile.testing_kit_boundary, inventory or ()))
    findings.extend(_external_connector(root, profile, scope))
    findings.extend(_deployment_artefact(root, profile.deployment_artefact_surfaces))
    return ConformanceReport(
        profile.profile_id,
        profile.enforcement_mode,
        tuple(
            sorted(
                findings,
                key=lambda item: (
                    item.code.value,
                    item.path.as_posix() if item.path else "",
                    item.line or 0,
                ),
            )
        ),
    )
