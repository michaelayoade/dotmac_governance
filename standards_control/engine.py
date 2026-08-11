"""Single policy engine for repository engineering conformance."""

from __future__ import annotations

import ast
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from .contracts import (
    BranchName,
    CanonicalRepository,
    ConformanceReport,
    Diagnostic,
    DiagnosticCode,
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


def _finding(
    code: DiagnosticCode,
    message: str,
    *,
    path: PurePosixPath | None = None,
    line: int | None = None,
) -> Diagnostic:
    return Diagnostic(code, Severity.ERROR, message, path, line)


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


def _repository_python_files(root: Path) -> tuple[PurePosixPath, ...]:
    """Return repository Python sources, including untracked non-ignored files."""
    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
                "--",
                "*.py",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        result = None
    if result is not None and result.returncode == 0:
        candidates = (PurePosixPath(raw) for raw in result.stdout.split("\0") if raw)
    else:
        candidates = (
            PurePosixPath(path.relative_to(root).as_posix())
            for path in root.rglob("*.py")
        )
    return tuple(
        sorted(
            {relative for relative in candidates if (root / relative).is_file()},
            key=lambda path: path.as_posix(),
        )
    )


def _inside(relative: PurePosixPath, roots: tuple[PurePosixPath, ...]) -> bool:
    return any(relative == root or root in relative.parents for root in roots)


def _testing_kit(root: Path, boundary: TestingKitBoundary) -> list[Diagnostic]:
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
    for relative in _repository_python_files(root):
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
    findings.extend(_authorities(root, profile))
    for surface in profile.typed_contract_surfaces:
        findings.extend(_typed(root, surface))
    for vocabulary in profile.module_declared_vocabularies:
        findings.extend(_vocabulary(root, vocabulary))
    findings.extend(_testing_kit(root, profile.testing_kit_boundary))
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
