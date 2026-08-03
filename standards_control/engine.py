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
    Severity,
    StandardsProfile,
    TypedContractSurface,
)
from .profile import ProfileError, load_profile

STATUS_LINE = re.compile(r"^- Status:\s*(Proposed|Accepted)\s*$", re.MULTILINE)
BARE_CONTAINERS = frozenset(
    {"dict", "list", "set", "tuple", "Mapping", "Sequence", "Iterable"}
)


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


def _governance(root: Path, profile: StandardsProfile) -> list[Diagnostic]:
    relative = profile.governance_model.source
    source = root / relative
    if not source.is_file():
        return [
            _finding(
                DiagnosticCode.GOVERNANCE_SOURCE_MISSING,
                "governance source is missing",
                path=relative,
            )
        ]
    try:
        statuses = STATUS_LINE.findall(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        statuses = []
    if len(statuses) != 1:
        return [
            _finding(
                DiagnosticCode.GOVERNANCE_SOURCE_STATUS_MISSING,
                "governance source needs exactly one controlled status",
                path=relative,
            )
        ]
    observed = statuses[0].lower()
    expected = profile.governance_model.status.value
    if observed != expected:
        return [
            _finding(
                DiagnosticCode.GOVERNANCE_SOURCE_STATUS_MISMATCH,
                f"profile expects status {expected!r}, found {observed!r}",
                path=relative,
            )
        ]
    return []


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
        expected_module = (
            authority.owner_implementation.as_posix()
            .removesuffix(".py")
            .replace("/", ".")
        )
        if module != expected_module or symbol not in _symbols(
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


def verify_repository(
    root: Path,
    profile_path: Path,
    *,
    observed_repository: CanonicalRepository | None = None,
    observed_default_branch: BranchName | None = None,
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
    findings.extend(_governance(root, profile))
    findings.extend(_authorities(root, profile))
    for surface in profile.typed_contract_surfaces:
        findings.extend(_typed(root, surface))
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
