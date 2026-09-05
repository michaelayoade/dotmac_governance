"""Kernel-adoption conformance over product source. Report-only.

Six properties are measured, and each is a fact about files in a product
checkout. None of them consults a profile document, because the profile has one
verifier and it is not this one — see `contracts` for the boundary and ADR 0042
for the decision.

Every finding names the offending file, line and symbol. That is a requirement
rather than a courtesy: the failures this package exists to catch are found by
grepping, and a message that omits the location makes the reader redo the
search that the checker already did.

Two vacuity hazards are handled as verdicts rather than assumed away:

- A run over no source emits `INVENTORY_EMPTY`. Every sweep below would
  otherwise report "no findings" over nothing.
- The pin-disagreement arm needs at least two sites to be capable of
  disagreeing. Given fewer it emits a NOTICE saying so, because a check that
  structurally cannot fail must not read as one that passed. This matters here
  specifically: no pin disagreement exists in any of the three products today,
  so the arm's health cannot be inferred from a green run and is established by
  a planted defect instead.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import PurePosixPath

from .contracts import (
    AdoptionReport,
    DeclarationMissing,
    DeclarationUnreadable,
    Finding,
    FindingCode,
    KernelAdoptionApplicability,
    KernelAdoptionInputs,
    Severity,
    TransitionalSurface,
)

__all__ = ["KERNEL_ROOT", "evaluate"]

#: The distribution's import name. One constant, so a rename is one edit.
KERNEL_ROOT = "dotmac_kernel"

_KERNEL_PREFIX = f"{KERNEL_ROOT}."


def _error(
    code: FindingCode,
    message: str,
    *,
    path: PurePosixPath | None = None,
    line: int | None = None,
) -> Finding:
    return Finding(
        code=code, severity=Severity.ERROR, message=message, path=path, line=line
    )


def _notice(
    code: FindingCode,
    message: str,
    *,
    path: PurePosixPath | None = None,
    line: int | None = None,
) -> Finding:
    return Finding(
        code=code, severity=Severity.NOTICE, message=message, path=path, line=line
    )


class _KernelImport:
    """One import of a Kernel module, with the names it bound locally.

    `bound` is what the importing module can now re-export, which is the input
    the facade arm needs. `module` is the dotted Kernel path, which is what the
    surface arms need. Both come from the same statement, so they are carried
    together rather than recovered twice from the tree.
    """

    __slots__ = ("bound", "line", "module", "star")

    def __init__(self, module: str, line: int, bound: frozenset[str], star: bool):
        self.module = module
        self.line = line
        self.bound = bound
        self.star = star


def _kernel_imports(tree: ast.Module) -> list[_KernelImport]:
    """Every Kernel import in one parsed module.

    Read from the parse tree, never from the text. A comment, a docstring or a
    string fixture that merely SPEAKS of `dotmac_kernel.db` binds nothing and
    must stay invisible here — `dotmac_erp`'s import-boundary guard keeps such a
    string as a fixture, and a text scanner would report the guard itself as the
    violation it exists to prevent.
    """
    found: list[_KernelImport] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == KERNEL_ROOT or alias.name.startswith(_KERNEL_PREFIX):
                    local = alias.asname or alias.name.split(".")[0]
                    found.append(
                        _KernelImport(
                            alias.name, node.lineno, frozenset({local}), False
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            if node.level != 0 or module is None:
                continue
            if module != KERNEL_ROOT and not module.startswith(_KERNEL_PREFIX):
                continue
            star = any(alias.name == "*" for alias in node.names)
            bound = frozenset(
                alias.asname or alias.name for alias in node.names if alias.name != "*"
            )
            found.append(_KernelImport(module, node.lineno, bound, star))
    return found


def _module_all(tree: ast.Module) -> frozenset[str] | None:
    """The module-level `__all__`, or None when there is not one.

    The presence of `__all__` is what separates a FACADE from an ADAPTER, and
    the distinction is load-bearing rather than stylistic.
    `dotmac_sub`'s `app/services/settings_kernel_bridge.py` imports four Kernel
    names and re-exports none of them: it declares no `__all__` and its public
    functions translate Sub's own `SettingSpec` into the Kernel registry. That
    is a translation layer, which is the correct shape, and a detector that
    fired on "imports Kernel names and is not a test" would condemn it.
    """
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in targets
        ):
            continue
        if node.value is None:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            return frozenset()
        if isinstance(value, (list, tuple, set)):
            return frozenset(str(item) for item in value)
        return frozenset()
    return None


def _private_components(module: str) -> tuple[str, ...]:
    """Kernel path components that are private, excluding dunders.

    `dotmac_kernel._transactions` is private AND published as internal, so the
    two arms are genuinely different questions and both are asked.
    `dotmac_kernel.display` is internal and NOT private; this returns nothing
    for it, which is the near-miss that keeps the two apart.
    """
    parts = module.split(".")[1:]
    return tuple(
        part for part in parts if part.startswith("_") and not part.startswith("__")
    )


def _prohibited_match(module: str, prohibited: frozenset[str]) -> str | None:
    """The prohibited entry `module` falls under, exactly or as a descendant."""
    for entry in sorted(prohibited):
        if module == entry or module.startswith(f"{entry}."):
            return entry
    return None


def _check_pins(inputs: KernelAdoptionInputs) -> list[Finding]:
    sites = inputs.pin_sites
    if len(sites) < 2:
        return [
            _notice(
                FindingCode.PIN_DISAGREES,
                f"the pin-disagreement arm was given {len(sites)} pin site(s); it "
                "cannot disagree with itself, so this run establishes nothing "
                "about pin agreement. Two or more sites are required for the "
                "check to be capable of failing",
            )
        ]

    by_version: dict[str, list[tuple[PurePosixPath, int, str]]] = defaultdict(list)
    for site in sites:
        by_version[site.version.strip()].append((site.path, site.line, site.kind))
    if len(by_version) < 2:
        return []

    rendered = "; ".join(
        f"{version!r} at "
        + ", ".join(
            f"{path.as_posix()}:{line} ({kind})" for path, line, kind in sorted(places)
        )
        for version, places in sorted(by_version.items())
    )
    findings: list[Finding] = []
    for version, places in sorted(by_version.items()):
        for path, line, kind in sorted(places):
            findings.append(
                _error(
                    FindingCode.PIN_DISAGREES,
                    f"this {kind} states {KERNEL_ROOT} {version!r}, but the "
                    f"product's pin sites do not agree: {rendered}. A product "
                    "adopts ONE Kernel; two sites naming two versions means the "
                    "version that was reviewed and the version that is installed "
                    "are decided by which file the reader opened",
                    path=path,
                    line=line,
                )
            )
    return findings


def _check_transitional(
    surfaces: tuple[TransitionalSurface, ...],
    observed: dict[str, frozenset[tuple[PurePosixPath, str]]],
) -> list[Finding]:
    """Arm 6. Owner and expiry, then the baseline ratchet.

    The blankness check below is defence in depth: `parse_declaration` already
    refuses a blank owner or expiry, so a declaration read from disk cannot
    reach it. It stays because a caller may construct the dataclass directly,
    and a guard removed on the grounds that another guard covers it is how a
    seam becomes unmonitored.

    The ratchet is the arm that bites on real input, and it is TWO-DIRECTIONAL
    for the reason this fleet already learned once: a baseline that may only
    grow stops describing anything, and one that may shrink silently hides that
    the last use was removed and the surface could have been retired. Both
    directions are the same edit — update the baseline in the change that moves
    the code.
    """
    findings: list[Finding] = []
    for surface in surfaces:
        blank = [
            name
            for name, value in (("owner", surface.owner), ("expiry", surface.expiry))
            if not value.strip()
        ]
        if blank:
            findings.append(
                _error(
                    FindingCode.TRANSITIONAL_UNOWNED,
                    f"{surface.module} is classified transitional but states no "
                    f"{' and no '.join(blank)}. A transitional surface with no "
                    "owner and no expiry is a permanent surface wearing a "
                    "temporary word: nobody is answerable for removing it and "
                    "no date makes its absence noticeable",
                )
            )
            continue

        declared = {(site.path, site.symbol) for site in surface.baseline}
        actual = set(observed.get(surface.module, frozenset()))
        for path, symbol in sorted(actual - declared, key=lambda item: str(item)):
            findings.append(
                _error(
                    FindingCode.TRANSITIONAL_BASELINE_DRIFT,
                    f"uses {symbol} from the transitional {surface.module}, "
                    f"which its declared baseline does not list. "
                    f"{surface.module} is being retired by {surface.owner} on "
                    f"{surface.expiry} ({surface.retirement_issue}, replaced by "
                    f"{surface.replacement}); a new use grows the work that "
                    "retirement has to undo",
                    path=path,
                    line=None,
                )
            )
        for path, symbol in sorted(declared - actual, key=lambda item: str(item)):
            findings.append(
                _error(
                    FindingCode.TRANSITIONAL_BASELINE_DRIFT,
                    f"the declared baseline for the transitional "
                    f"{surface.module} lists {symbol} at {path.as_posix()}, and "
                    "no such use was measured. Lower the baseline in the change "
                    "that removed the use: a baseline that only grows stops "
                    "describing anything, and one that silently shrinks hides "
                    "that the surface may now be retirable",
                    path=path,
                )
            )
    return findings


def _check_declaration(
    inputs: KernelAdoptionInputs,
    kernel_import_sites: list[tuple[PurePosixPath, int, str]],
    observed_symbols: dict[str, frozenset[tuple[PurePosixPath, str]]],
) -> list[Finding]:
    """Arms 4 and 6, and the three states the declaration can be in.

    This is the half that used to be inert. Arms 4 and 6 have a production
    input now — the `kernel_adoption` section of `.dotmac/standards-profile.json`
    — and, more importantly, they REFUSE when it is absent or unreadable rather
    than reporting nothing.

    `not_applicable` is checked, not accepted. An exemption states an
    enforceable premise or the region is unmonitored rather than exempt, and
    the premise here is decidable from the same source inventory the arms above
    already read: a repository that declares it consumes no Kernel and then
    imports one is named, with the file and line of the import that contradicts
    it.
    """
    outcome = inputs.declaration
    if isinstance(outcome, DeclarationMissing):
        return [
            _error(
                FindingCode.DECLARATION_MISSING,
                f"{outcome.detail}. Arms 4 and 6 are therefore UNMONITORED "
                "rather than clean: no prohibited surface and no transitional "
                "surface can be reported, and that is a refusal rather than a "
                "pass",
            )
        ]
    if isinstance(outcome, DeclarationUnreadable):
        return [
            _error(
                FindingCode.DECLARATION_UNREADABLE,
                f"{outcome.detail}. Arms 4 and 6 are UNMONITORED rather than clean",
            )
        ]

    declaration = outcome.declaration
    if declaration.applicability is KernelAdoptionApplicability.NOT_APPLICABLE:
        if not kernel_import_sites:
            return []
        path, line, module = kernel_import_sites[0]
        return [
            _error(
                FindingCode.DECLARATION_PREMISE_FALSE,
                f"the declaration states applicability 'not_applicable' — "
                f"{declaration.not_applicable_reason!r} — but this repository "
                f"imports {module}, at {path.as_posix()}:{line}, and "
                f"{len(kernel_import_sites)} Kernel import(s) in total. An "
                "exemption states an ENFORCEABLE premise; this one is "
                "contradicted by the repository's own source, so the "
                "classification cannot stand and arms 4 and 6 do not run",
                path=path,
                line=line,
            )
        ]

    findings: list[Finding] = []
    citations = {item.module: item.citation for item in declaration.prohibited_surfaces}
    prohibited = declaration.prohibited_modules
    for path, line, module in kernel_import_sites:
        entry = _prohibited_match(module, prohibited)
        if entry is None:
            continue
        detail = (
            f"{module} (under the prohibited {entry})" if module != entry else module
        )
        findings.append(
            _error(
                FindingCode.SURFACE_PROHIBITED,
                f"imports {detail}, which this product's own declaration "
                f"forbids under {citations[entry]}. The classification is the "
                "product's; this arm reports the import that contradicts it, "
                "and the citation is carried so the reader knows whether "
                "removing the prohibition needs a decision or a commit",
                path=path,
                line=line,
            )
        )
    findings.extend(
        _check_transitional(declaration.transitional_surfaces, observed_symbols)
    )
    return findings


def evaluate(inputs: KernelAdoptionInputs) -> AdoptionReport:
    """Measure Kernel adoption over the supplied product source.

    Reads only `inputs`. No filesystem, no network, no profile document.
    """
    findings: list[Finding] = []
    kernel_import_sites: list[tuple[PurePosixPath, int, str]] = []
    observed_symbols: dict[str, set[tuple[PurePosixPath, str]]] = {}

    if not inputs.sources:
        findings.append(
            _error(
                FindingCode.INVENTORY_EMPTY,
                "no product source was supplied, so every surface arm below "
                "would report no findings over an empty set. An empty inventory "
                "is a measurement failure, not a clean result",
            )
        )

    for path in sorted(inputs.sources, key=lambda item: item.as_posix()):
        text = inputs.sources[path]
        try:
            tree = ast.parse(text, filename=path.as_posix())
        except (SyntaxError, ValueError) as error:
            line = error.lineno if isinstance(error, SyntaxError) else None
            findings.append(
                _error(
                    FindingCode.SOURCE_UNREADABLE,
                    f"cannot parse this source for {KERNEL_ROOT} imports: {error}. "
                    "Refusing to report it as clean: an unparsed file is an "
                    "unmeasured file",
                    path=path,
                    line=line,
                )
            )
            continue

        imports = _kernel_imports(tree)
        if not imports:
            continue
        exported = _module_all(tree)

        for entry in imports:
            module = entry.module
            kernel_import_sites.append((path, entry.line, module))
            observed_symbols.setdefault(module, set()).update(
                (path, name) for name in entry.bound
            )

            private = _private_components(module)
            if private:
                findings.append(
                    _error(
                        FindingCode.SURFACE_PRIVATE,
                        f"imports {module}, whose component "
                        f"{private[0]!r} is private. A leading underscore is the "
                        "Kernel saying this name carries no compatibility "
                        "promise, so an importer is pinned to an implementation "
                        "detail that may change in a patch release",
                        path=path,
                        line=entry.line,
                    )
                )
            elif module != KERNEL_ROOT and module not in inputs.catalogue.known:
                findings.append(
                    _error(
                        FindingCode.SURFACE_UNKNOWN,
                        f"imports {module}, which {KERNEL_ROOT} "
                        f"{inputs.catalogue.version} does not publish. Its module "
                        f"lists were read at {inputs.catalogue.revision} and "
                        f"carry {len(inputs.catalogue.supported)} supported and "
                        f"{len(inputs.catalogue.internal)} internal names. An "
                        "unpublished surface is either a typo or a module the "
                        "Kernel does not undertake to keep",
                        path=path,
                        line=entry.line,
                    )
                )

            if entry.star:
                findings.append(
                    _error(
                        FindingCode.FACADE_LOCAL,
                        f"re-exports {module} wholesale via `from {module} import "
                        "*`, which makes this file a product-local Kernel facade. "
                        "Every consumer then imports the Kernel through a name "
                        "the Kernel does not own, so the real import inventory "
                        "cannot be read off the source",
                        path=path,
                        line=entry.line,
                    )
                )
                continue

            if exported is None:
                continue
            reexported = sorted(entry.bound & exported)
            if not reexported:
                continue
            findings.append(
                _error(
                    FindingCode.FACADE_LOCAL,
                    f"imports {', '.join(reexported)} from {module} and re-exports "
                    f"{'them' if len(reexported) > 1 else 'it'} in this module's "
                    "`__all__`, which makes this file a product-local Kernel "
                    "facade. A facade is not an adapter: it forwards the Kernel's "
                    "own name unchanged, so consumers depend on the Kernel while "
                    "the import inventory records a dependency on this file",
                    path=path,
                    line=entry.line,
                )
            )

    findings.extend(_check_pins(inputs))
    findings.extend(
        _check_declaration(
            inputs,
            kernel_import_sites,
            {key: frozenset(value) for key, value in observed_symbols.items()},
        )
    )

    return AdoptionReport(findings=tuple(findings))
