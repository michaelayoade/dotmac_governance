"""Kernel-adoption conformance over product source.

Seven properties are measured, and each is a fact about files in a product
checkout plus the date the run is asked about. None of them consults a profile
document, because the profile has one verifier and it is not this one — see
`contracts` for the boundary and ADR 0042 for the decision.

The seventh is expiry, added by ADR 0042's amendment of 2026-09-05: a
`TransitionalSurface` carried an orderable date that was compared to nothing,
which is a deadline that cannot pass. `as_of` is an INPUT, never a clock read
— see `_check_expiry` for why, and for which side of the boundary the expiry
day falls on.

Every finding names the offending file, line and symbol. That is a requirement
rather than a courtesy: the failures this package exists to catch are found by
grepping, and a message that omits the location makes the reader redo the
search that the checker already did.

Two vacuity hazards are handled as verdicts rather than assumed away:

- A run over no source emits `INVENTORY_EMPTY`. Every sweep below would
  otherwise report "no findings" over nothing.
- The pin-disagreement arm needs at least two INDEPENDENT observations to be
  capable of disagreeing. Given fewer it is an ERROR under an `applicable`
  declaration — it was a notice, and the report stayed conforming and citable,
  which is a check that structurally cannot fail being counted as one that
  passed. Under `not_applicable` the requirement inverts: any pin site at all
  contradicts the stated premise. Either way the sufficiency question has an
  answer rather than a shrug, and the arm's health is established by a planted
  defect, because no pin disagreement exists in any of the three products
  today.
"""

from __future__ import annotations

import ast
from collections import defaultdict
from datetime import date
from pathlib import PurePosixPath

from .contracts import (
    KERNEL_ROOT,
    AdoptionReport,
    AnyKernelAdoptionDeclaration,
    DeclarationEmpty,
    DeclarationIncomplete,
    DeclarationMissing,
    DeclarationPresent,
    DeclarationUnreadable,
    Finding,
    FindingCode,
    KernelAdoptionApplicability,
    KernelAdoptionDeclarationV2,
    KernelAdoptionInputs,
    KernelSurfaceCatalogue,
    RequiredSurface,
    Severity,
    TransitionalSurface,
)
from .surface import (
    SOURCE_SURFACE_ALGORITHM,
    SOURCE_SURFACE_IDENTITY_ALGORITHM,
    SurfaceBinding,
    SurfaceFact,
    SurfaceIdentityFact,
    catalogue_digest,
    render_surface,
    render_surface_identity,
    surface_digest,
    surface_identity_digest,
)
from .versions import VersionError, compare_versions

__all__ = ["KERNEL_ROOT", "REFUSAL_CODES", "evaluate", "observed_surface"]

#: Four refusals, four codes, one shared consequence. The consequence is shared
#: because it is the same in all four cases -- nothing downstream can be
#: measured -- but the codes stay APART because the repairs differ: create the
#: file, write a document into it, add the key that was never stated, fix the
#: value that is wrong. A reader handed one code for four repairs opens the
#: wrong file.
REFUSAL_CODES: dict[type, FindingCode] = {
    DeclarationMissing: FindingCode.DECLARATION_MISSING,
    DeclarationEmpty: FindingCode.DECLARATION_EMPTY,
    DeclarationIncomplete: FindingCode.DECLARATION_INCOMPLETE,
    DeclarationUnreadable: FindingCode.DECLARATION_UNREADABLE,
}

#: The distribution's import name. Now DEFINED in `contracts`, because
#: `KernelSurfaceCatalogue.publishes` has to know which module is the root
#: façade; re-exported here unchanged so no importer moved.
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

    `names` is the third, and it is NOT `bound`. `bound` holds LOCAL names, so
    `from dotmac_kernel import Party as P` puts `P` in it — and `P` is not a
    name the Kernel publishes or could ever publish. The root-façade arm has to
    ask whether the KERNEL's name is in the Kernel's `__all__`, so it needs the
    name as written on the far side of `as`. Asking `bound` would refuse every
    aliased public import and admit an alias that happens to spell a public
    name, which is the arm getting both directions wrong at once.

    `names` is EMPTY for a plain `import dotmac_kernel`, and that emptiness is
    a fact rather than a gap: such a statement imports the package and names no
    export, so there is no symbol to admit or refuse.

    `bindings` is the fourth, and it is what `names` and `bound` cannot be
    recovered into once they are separate sets. `from dotmac_kernel import A as
    Y, B as Z` puts `{A, B}` in `names` and `{Y, Z}` in `bound`, and nothing in
    either says which went with which. The PAIRING is the fact the v2
    source-surface canonicalization records, so it is carried from the one
    place that still has it: the alias node itself.
    """

    __slots__ = ("bindings", "bound", "line", "module", "names", "star")

    def __init__(
        self,
        module: str,
        line: int,
        bound: frozenset[str],
        star: bool,
        names: frozenset[str] = frozenset(),
        bindings: frozenset[SurfaceBinding] = frozenset(),
    ):
        self.module = module
        self.line = line
        self.bound = bound
        self.star = star
        self.names = names
        self.bindings = bindings


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
                            alias.name,
                            node.lineno,
                            frozenset({local}),
                            False,
                            bindings=frozenset(
                                {SurfaceBinding(kernel=alias.name, local=local)}
                            ),
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
            # The names as the KERNEL spells them, before any `as`. See
            # `_KernelImport.names` for why this is not `bound`.
            names = frozenset(alias.name for alias in node.names if alias.name != "*")
            # The pairing, kept before the two sets above throw it away. See
            # `_KernelImport.bindings`.
            bindings = frozenset(
                SurfaceBinding(kernel=alias.name, local=alias.asname or alias.name)
                for alias in node.names
                if alias.name != "*"
            )
            found.append(
                _KernelImport(module, node.lineno, bound, star, names, bindings)
            )
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
    # The normal import census is AST-wide.  Keep this inventory AST-wide too:
    # a Kernel import inside a function or branch cannot disappear merely
    # because a separate export check looked only at ``tree.body``.
    for node in ast.walk(tree):
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


def _check_root_facade(
    path: PurePosixPath,
    entry: _KernelImport,
    catalogue: KernelSurfaceCatalogue | None,
) -> list[Finding]:
    """One import of the bare `dotmac_kernel`, admitted only by NAMED export.

    The root façade is a published surface and it is not a submodule.
    `SUPPORTED_MODULES` and `INTERNAL_MODULES` enumerate submodules and the
    bare root is in neither — at `dotmac-kernel-v0.1.0a102` (peeled
    `7a3c128b06eaba09784a9d8409d036169b3caa68`) they carry 89 and 4 names and
    neither is `dotmac_kernel`. A product importing the root therefore had no
    reachable clean verdict at all: declaring it required reported
    `kernel.required.unpublished`, and omitting it reported
    `kernel.surface.unclassified`.

    Normalising it must not become a blanket pass, and this function is the
    difference. The root is classifiable, and each name it is asked for is
    checked against the artifact's OWN publication authority,
    `dotmac_kernel.__all__`, carried on the catalogue as `root_exports`. A name
    absent from that list is refused exactly as an unpublished submodule is.

    Four import shapes reach here and each gets a different answer:

    - **public** — `from dotmac_kernel import Party`, and `Party` is in
      `__all__`: admitted, no finding. A name that is not in `__all__` but
      names a SUPPORTED SUBMODULE (`from dotmac_kernel import audit`) is
      admitted too: it binds `dotmac_kernel.audit`, which the Kernel publishes
      under its other authority. An INTERNAL submodule is not admitted here.
    - **private or nonexistent** — `_Internal`, or a name that was never
      there: `kernel.root.unexported`. Note that the leading-underscore case is
      not decided by the underscore. `_private_components` looks at MODULE path
      components and returns nothing for a SYMBOL, so `dotmac_kernel` never
      reaches the private-surface arm; the refusal here comes from the name's
      absence from `__all__`, which is also what refuses a plain typo.
    - **aliased** — `from dotmac_kernel import Party as P` is resolved on
      `Party`. Admission is a question about the Kernel's name, and the local
      one is the importer's business.
    - **module-only** — `import dotmac_kernel` names no export, so there is
      nothing to admit and nothing to refuse. The module is still MEASURED and
      still has to be classified by the declaration. What follows the statement
      — `dotmac_kernel.anything` by attribute access — is invisible to an
      import-shape arm, and that limit is stated rather than papered over: this
      arm reports on names an import statement binds, not on attribute reads.

    A star import is left to `kernel.facade.local`, which already refuses it
    and refuses it for the stronger reason: `from dotmac_kernel import *` binds
    every public name at once, so the import inventory stops being readable off
    the source at all. Reporting it twice would send one reader to two edits.
    """
    if catalogue is None:
        return [
            _error(
                FindingCode.CATALOGUE_ABSENT,
                f"imports the {KERNEL_ROOT} root façade, and this run was "
                "given no surface catalogue, so the façade's published names "
                "are unknown and no import of it can be classified",
                path=path,
                line=entry.line,
            )
        ]
    if not catalogue.root_exports:
        return [
            _error(
                FindingCode.ROOT_EXPORTS_UNOBSERVED,
                f"imports the {KERNEL_ROOT} root façade, and the supplied "
                f"catalogue carries no root exports. {KERNEL_ROOT} publishes "
                "the root through its own `__all__`, which is a SEPARATE "
                "authority from SUPPORTED_MODULES and INTERNAL_MODULES -- "
                f"those enumerate submodules and neither contains the bare "
                f"{KERNEL_ROOT}. The repair is in the OBSERVER: read "
                f"`{KERNEL_ROOT}.__all__` off the installed artifact and put "
                "it on the catalogue. Refused rather than admitted, because a "
                "root arm with no list to check against admits every name",
                path=path,
                line=entry.line,
            )
        ]
    findings: list[Finding] = []
    for name in sorted(entry.names - catalogue.root_exports):
        # A name may also be a SUBMODULE reached through the root:
        # `from dotmac_kernel import audit` binds the module
        # `dotmac_kernel.audit`, which is published -- by SUPPORTED_MODULES
        # rather than by `__all__`. Two publication authorities, one question,
        # and refusing this shape would refuse a supported surface for the
        # syntax used to reach it. Platform writes exactly this in
        # `alembic/env.py`.
        #
        # SUPPORTED only, never `known`. `dotmac_kernel._transactions` is an
        # INTERNAL module, and admitting it here would let a root import walk
        # straight past the private-surface arm -- that arm reads MODULE path
        # components, and the module recorded for this statement is the bare
        # root, so it never sees the symbol.
        if f"{KERNEL_ROOT}.{name}" in catalogue.supported:
            continue
        findings.append(
            _error(
                FindingCode.ROOT_SYMBOL_UNEXPORTED,
                f"imports {name} from the {KERNEL_ROOT} root façade, and "
                f"{KERNEL_ROOT} {catalogue.version} publishes it under neither "
                f"of the two authorities that could carry it: it is not in the "
                f"root's `__all__` ({len(catalogue.root_exports)} name(s), read "
                f"at {catalogue.revision}), and {KERNEL_ROOT}.{name} is not a "
                f"supported module ({len(catalogue.supported)} of those). The "
                "root is a published surface, and what it publishes is those "
                "enumerated lists -- not every attribute an importer can reach "
                "through the package object. A name in neither is a typo, an "
                "internal detail, a name that was removed, or a LOCAL alias "
                "recorded where the Kernel's own name was wanted",
                path=path,
                line=entry.line,
            )
        )
    return findings


def _check_module_exports(
    path: PurePosixPath,
    entry: _KernelImport,
    catalogue: KernelSurfaceCatalogue,
) -> list[Finding]:
    """Check direct submodule names against successor release evidence."""
    if not entry.names:
        return []
    exports = catalogue.module_exports.get(entry.module)
    if exports is None:
        return [
            _error(
                FindingCode.MODULE_EXPORTS_UNOBSERVED,
                f"imports named symbols from {entry.module}, but its trusted "
                "release catalogue carries no declared module exports. Python "
                "attribute reachability is not a published contract",
                path=path,
                line=entry.line,
            )
        ]
    return [
        _error(
            FindingCode.MODULE_SYMBOL_UNEXPORTED,
            f"imports {name} from {entry.module}, but {KERNEL_ROOT} "
            f"{catalogue.version} does not export that name in the trusted "
            "release catalogue",
            path=path,
            line=entry.line,
        )
        for name in sorted(entry.names - exports)
    ]


def _check_module_alias_attributes(
    path: PurePosixPath,
    tree: ast.Module,
    catalogue: KernelSurfaceCatalogue | None,
) -> list[Finding]:
    """Resolve attribute paths to Kernel module/name coordinates.

    Python's local aliases are not the publication subject.  This understands
    all three ordinary spellings of a submodule path: ``from root import db as
    d``, ``import root as k; k.db.Name`` and ``import root.db; root.db.Name``.
    Only the outermost attribute of a chain is evaluated, so the intermediate
    ``root.db`` in the last spelling is not falsely read as an exported name.
    """
    if catalogue is None:
        return []
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name == KERNEL_ROOT:
                    aliases[item.asname or KERNEL_ROOT] = KERNEL_ROOT
                elif item.name.startswith(_KERNEL_PREFIX):
                    # Without ``as``, Python binds the root. With it, it
                    # binds the full module path.
                    aliases[item.asname or KERNEL_ROOT] = (
                        item.name if item.asname else KERNEL_ROOT
                    )
        elif isinstance(node, ast.ImportFrom) and node.module == KERNEL_ROOT:
            for item in node.names:
                candidate = f"{KERNEL_ROOT}.{item.name}"
                if candidate in catalogue.known:
                    aliases[item.asname or item.name] = candidate

    children = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
    }
    parents = {
        id(child): parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    findings: list[Finding] = []
    for walk_node in ast.walk(tree):
        if not isinstance(walk_node, ast.Attribute) or id(walk_node) in children:
            continue
        names: list[str] = []
        cursor: ast.expr = walk_node
        while isinstance(cursor, ast.Attribute):
            names.append(cursor.attr)
            cursor = cursor.value
        if not isinstance(cursor, ast.Name):
            continue
        module = aliases.get(cursor.id)
        if module is None:
            continue
        # Binding resolution below function/class/branch scope needs a real
        # control-flow and lexical-scope analysis.  Do not silently treat a
        # same-spelled local as the module import: top-level paths are the
        # supported syntax; nested paths are deliberately unmeasured.
        ancestor: ast.AST | None = parents.get(id(walk_node))
        nested = False
        while ancestor is not None and not isinstance(ancestor, ast.Module):
            if isinstance(
                ancestor,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.Lambda,
                    ast.ClassDef,
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.With,
                    ast.AsyncWith,
                    ast.Match,
                ),
            ):
                nested = True
                break
            ancestor = parents.get(id(ancestor))
        if nested:
            findings.append(
                _error(
                    FindingCode.MODULE_ATTRIBUTE_UNMEASURED,
                    f"reads {cursor.id}.{'.'.join(reversed(names))} below a "
                    "nested lexical/control-flow scope. The export checker "
                    "does not yet resolve nested bindings, so it refuses "
                    "rather than admitting a same-spelled local name",
                    path=path,
                    line=walk_node.lineno,
                )
            )
            continue
        for index, name in enumerate(reversed(names)):
            candidate = f"{module}.{name}"
            if candidate in catalogue.known:
                module = candidate
                continue
            remaining = index != len(names) - 1
            if module == KERNEL_ROOT:
                if name in catalogue.root_exports and not remaining:
                    break
                findings.append(
                    _error(
                        FindingCode.MODULE_ATTRIBUTE_UNMEASURED,
                        f"reads {cursor.id}.{'.'.join(reversed(names))}, which "
                        "does not resolve to a trusted Kernel module/name "
                        "coordinate",
                        path=path,
                        line=walk_node.lineno,
                    )
                )
                break
            exports = catalogue.module_exports.get(module)
            if exports is None:
                findings.append(
                    _error(
                        FindingCode.MODULE_ATTRIBUTE_UNMEASURED,
                        f"reads {cursor.id}.{'.'.join(reversed(names))} through "
                        f"{module}, whose trusted release catalogue carries no "
                        "declared exports",
                        path=path,
                        line=walk_node.lineno,
                    )
                )
            elif name not in exports:
                findings.append(
                    _error(
                        FindingCode.MODULE_SYMBOL_UNEXPORTED,
                        f"reads {cursor.id}.{'.'.join(reversed(names))} through "
                        f"{module}, but {KERNEL_ROOT} {catalogue.version} does "
                        f"not export {name} in the trusted release catalogue",
                        path=path,
                        line=walk_node.lineno,
                    )
                )
            elif remaining:
                findings.append(
                    _error(
                        FindingCode.MODULE_ATTRIBUTE_UNMEASURED,
                        f"reads through exported {module}.{name}; the remaining "
                        "attribute path has no Kernel module/export coordinate",
                        path=path,
                        line=walk_node.lineno,
                    )
                )
            break
    return findings


def _prohibited_match(module: str, prohibited: frozenset[str]) -> str | None:
    """The prohibited entry `module` falls under, exactly or as a descendant."""
    for entry in sorted(prohibited):
        if module == entry or module.startswith(f"{entry}."):
            return entry
    return None


def _pin_sufficiency(inputs: KernelAdoptionInputs) -> list[Finding]:
    """Whether the pin arm was even CAPABLE of reporting what it is asked to.

    Applicability-aware, because "enough" is a different number for the two
    states and the old arm asked neither question. It emitted a NOTICE at fewer
    than two sites and the report stayed conforming and citable -- a check that
    structurally could not fail, counted as one that passed. That is the exact
    shape this repository exists to catch, arriving inside the package built to
    catch it.

    - **applicable** -- two or more INDEPENDENT observations, where independence
      is a distinct NORMALISED `(path, line)`. Two entries at one line are one
      observation written twice, and a disagreement between a value and itself
      is not detectable. Fewer is an ERROR. The normalization is decision
      52 (E)'s repair and is load-bearing here rather than tidy: the paths are
      caller-supplied, and before it `pyproject.toml` and
      `x/../pyproject.toml` were two independent observations of one line. See
      `contracts.normalise_observed_path`.
    - **not_applicable** -- zero pin sites AND zero Kernel imports. A repository
      declaring it consumes no Kernel while pinning the Kernel has stated a
      premise its own packaging contradicts, which is the same fault as
      importing one, so it is reported as the same code.

    A declaration that could not be read gets neither requirement, because the
    requirement is a function of a value nobody stated. The refusal in
    `_check_declaration` already names this arm as unmonitored.
    """
    outcome = inputs.declaration
    if not isinstance(outcome, DeclarationPresent):
        return []
    sites = inputs.pin_sites
    if outcome.declaration.applicability is KernelAdoptionApplicability.NOT_APPLICABLE:
        if not sites:
            return []
        rendered = ", ".join(
            f"{site.path.as_posix()}:{site.line} ({site.kind}) {site.version!r}"
            for site in sites
        )
        return [
            _error(
                FindingCode.DECLARATION_PREMISE_FALSE,
                f"the declaration states applicability 'not_applicable' and "
                f"this repository states {len(sites)} {KERNEL_ROOT} pin "
                f"site(s): {rendered}. A repository that consumes no Kernel "
                "does not pin one; the premise is contradicted by its own "
                "packaging, and an exemption states an ENFORCEABLE premise or "
                "the region is unmonitored rather than exempt",
                path=sites[0].path,
                line=sites[0].line,
            )
        ]
    independent = {site.independence_key for site in sites}
    if len(independent) >= 2:
        return []
    return [
        _error(
            FindingCode.PIN_UNDETECTABLE,
            f"the declaration states applicability 'applicable' and this run "
            f"was given {len(sites)} pin site(s) at {len(independent)} distinct "
            "location(s). The pin-disagreement arm cannot disagree with itself, "
            "so it established nothing -- and a check incapable of failing must "
            "not be counted as one that passed. Supply the product's real pin "
            "sites (a dependency declaration and its lock resolution are the "
            "usual two), or the arm is unmonitored rather than clean",
        )
    ]


def _check_pins(inputs: KernelAdoptionInputs) -> list[Finding]:
    sites = inputs.pin_sites
    if len({site.independence_key for site in sites}) < 2:
        # Sufficiency is `_pin_sufficiency`'s question now, and it answers with
        # an error or with nothing. Returning silently here would be silence
        # only in the arm that cannot run; it is never the whole verdict.
        return []

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


def _check_expiry(surface: TransitionalSurface, as_of: date) -> Finding | None:
    """Arm 7. Has the stated expiry passed on the date the run is asked about?

    Two choices are made here and neither is an accident of an operator.

    **What "now" is.** The run date, supplied by the caller and recorded in the
    report. Not a clock read: `date.today()` appears nowhere in this package,
    because a verdict that depends on when the process happened to start cannot
    be re-derived by a reader who was not present, and cannot be tested without
    freezing time. It is also NOT taken from the evidence, because there is
    nothing in the evidence to take it from -- `KernelAdoptionDeclaration.v1`
    carries `product_revision`, a commit id, and no date at all. Reading that
    commit's timestamp would mean asking the product's Git history, which is an
    oracle over another repository rather than a fact in the document.

    **Which side of the boundary the expiry day falls on.** `expiry` is the
    LAST DAY the transitional surface may exist, so a surface expiring on the
    run date is not yet expired and one expiring the day before is. The
    comparison is therefore strict: `expiry < as_of`. Stated because the
    difference between `<` and `<=` here is one day of a retirement deadline,
    and a boundary nobody wrote down is a boundary the next reader will change
    while believing it made no difference. Both neighbours are asserted.
    """
    try:
        expiry = date.fromisoformat(surface.expiry)
    except ValueError:
        # `parse_declaration` refuses this, so a declaration read from disk
        # cannot arrive here. A directly-constructed dataclass can, and an
        # unorderable expiry must fail closed rather than be treated as a
        # deadline that has not arrived.
        return _error(
            FindingCode.TRANSITIONAL_EXPIRED,
            f"{surface.module} states the expiry {surface.expiry!r}, which is "
            "not an orderable calendar date, so whether it has passed cannot "
            "be decided. Refusing to read an undecidable expiry as an unexpired "
            "one",
        )
    if expiry >= as_of:
        return None
    return _error(
        FindingCode.TRANSITIONAL_EXPIRED,
        f"{surface.module} is classified transitional with expiry "
        f"{surface.expiry}, and the run is asked about {as_of.isoformat()}: the "
        f"transition is {(as_of - expiry).days} day(s) overdue. It is owned by "
        f"{surface.owner} and tracked at {surface.retirement_issue}, replaced "
        f"by {surface.replacement}. Retire the surface, or move the date in a "
        "reviewed change that says who agreed to the new one -- an expiry that "
        "passes with no consequence is the field admitting it was never a "
        "commitment",
    )


def _check_transitional(
    surfaces: tuple[TransitionalSurface, ...],
    observed: dict[str, frozenset[tuple[PurePosixPath, str]]],
    as_of: date,
) -> list[Finding]:
    """Arms 6 and 7. Owner and expiry, the expiry comparison, then the ratchet.

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

        expired = _check_expiry(surface, as_of)
        if expired is not None:
            findings.append(expired)

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


# --- KernelAdoptionDeclaration.v2 arms ---------------------------------------
#
# Everything below reads a field v1 declared and nothing compared. Each arm is
# a function of `inputs` alone: the Git observation the predecessor arm needs
# arrives as `inputs.predecessor`, supplied by the runner, so the engine keeps
# reading nothing but what it was told.


def _check_declared_at(
    declaration: KernelAdoptionDeclarationV2, as_of: date
) -> list[Finding]:
    """Decision 52 (D). A declaration has an age, and two things follow from it.

    Only the two that are decidable WITHOUT inventing a policy number are
    checked here. Whether a declaration older than some number of days is
    stale enough to refuse is a decision with an owner, and this file is not
    where a threshold gets invented -- see `declaration_contract_v2`'s
    "What v2 deliberately does NOT add".
    """
    if declaration.declared_at > as_of:
        return [
            _error(
                FindingCode.DECLARED_AT_AHEAD,
                f"the declaration states declared_at "
                f"{declaration.declared_at.isoformat()} and the run is asked "
                f"about {as_of.isoformat()}. A declaration cannot have been "
                "written after the run that reads it; either the date is wrong "
                "or the run date is, and neither may be assumed",
            )
        ]
    return []


def _check_predecessor(inputs: KernelAdoptionInputs) -> list[Finding]:
    """Decision 52 (A), the half a digest cannot do: anchoring in real history.

    **What a satisfied predecessor proves.** The commit the declaration names
    exists in the measured repository's own history and is STRICTLY behind the
    revision that was measured. A fabricated hash fails, a hash from another
    repository fails, and a hash that is the measured revision itself fails --
    which it must, because a committed file cannot contain its own commit, so
    a declaration claiming to name it is claiming something impossible.

    **What it does not prove.** Not that the declaration was written at that
    commit, nor that anything about that commit is related to the declaration,
    nor that the surface it describes was the surface at that commit. A product
    may name its repository's first commit and satisfy this forever. The
    coordinate that binds the declaration to the SOURCE is the surface digest;
    this one binds it to the repository. Neither is the other, and both are
    required for exactly that reason.

    **A run that cannot decide is a refusal.** A shallow clone -- the default
    for `actions/checkout` -- makes ancestry undecidable, and the repair is
    `fetch-depth: 0`. Reading it as satisfied would be the coordinate reporting
    a colour.
    """
    observation = inputs.predecessor
    if observation is None:
        return [
            _error(
                FindingCode.PREDECESSOR_UNVERIFIABLE,
                "the declaration states a source_predecessor and this run was "
                "given no ancestry observation for it, so whether that commit "
                "precedes what was measured is unknown. The runner supplies "
                "this; an engine called directly without it must not report "
                "the coordinate clean",
            )
        ]
    if observation.is_strict_ancestor is None:
        return [
            _error(
                FindingCode.PREDECESSOR_UNVERIFIABLE,
                f"whether {observation.declared} precedes the measured "
                f"{observation.measured} could not be decided: "
                f"{observation.detail}. A shallow clone is the usual cause and "
                "`fetch-depth: 0` the usual repair. An undecidable coordinate "
                "is unmonitored, never satisfied",
            )
        ]
    if observation.is_strict_ancestor:
        return []
    return [
        _error(
            FindingCode.PREDECESSOR_NOT_ANCESTOR,
            f"the declaration names source_predecessor "
            f"{observation.declared}, which is not a strict ancestor of the "
            f"measured revision {observation.measured}: {observation.detail}. "
            "The coordinate names a commit this repository's history does not "
            "put behind what was measured, so the declaration is not anchored "
            "in the source it describes",
        )
    ]


def _check_source_surface(
    declaration: KernelAdoptionDeclarationV2,
    facts: frozenset[SurfaceFact],
    identity_facts: frozenset[SurfaceIdentityFact],
) -> list[Finding]:
    """Decision 52 (A), the half that is re-derived rather than named.

    See `surface.surface_digest` for exactly what the digest is taken over,
    what it proves and the five things it does not.

    The declared `algorithm` SELECTS which canonicalization is re-derived.
    Both fact sets come from the same sweep over the same measured source
    (`_SurfaceAccumulator`), so the two are always consistent with each other
    and the label chooses between two derivations rather than being trusted
    about one. A label this engine has no derivation for REFUSES: the parser
    admits exactly `ACCEPTED_SOURCE_SURFACE_ALGORITHMS`, so the branch is
    unreachable through a parsed document, and a caller building the dataclass
    directly must not get a silently skipped arm.

    A digest RELABELLED from one algorithm to the other parses -- a parser
    cannot tell two 64-hex strings apart -- and is refused HERE, because the
    two algorithms digest different bytes and the re-derived value will not
    match. That is the refusal domain separation buys, and it needs no oracle.
    """
    coordinate = declaration.source_surface
    if coordinate is None:
        # Unreachable through the parser, which requires the field of every
        # `applicable` v2 document. Kept because a caller may build the
        # dataclass directly, and a missing coordinate must fail closed rather
        # than skip the arm.
        return [
            _error(
                FindingCode.SOURCE_SURFACE_DRIFT,
                "this applicable declaration states no source_surface, so the "
                "source it describes cannot be identified. Refusing to read an "
                "absent coordinate as a matching one",
            )
        ]
    if not facts:
        return [
            _error(
                FindingCode.SURFACE_NONE_OBSERVED,
                "this declaration is 'applicable' and the measured source "
                "contains no dotmac_kernel import at all. The surface digest "
                "of an empty set is a CONSTANT that every Kernel-free product "
                "shares, so a declaration matching it would have matched "
                "nothing in particular. Either the product does not adopt the "
                "Kernel -- in which case it declares not_applicable, whose "
                "premise is checked -- or the observation is not reaching its "
                "source",
            )
        ]
    if coordinate.algorithm == SOURCE_SURFACE_ALGORITHM:
        derived = surface_digest(facts)
    elif coordinate.algorithm == SOURCE_SURFACE_IDENTITY_ALGORITHM:
        derived = surface_identity_digest(identity_facts)
    else:
        return [
            _error(
                FindingCode.SOURCE_SURFACE_DRIFT,
                f"the declaration states source_surface algorithm "
                f"{coordinate.algorithm!r}, which this engine has no "
                "derivation for, so the coordinate cannot be re-derived and "
                "cannot be compared. Refusing rather than falling back to "
                "another canonicalization: a digest compared under a rendering "
                "rule nobody declared is a comparison whose result means "
                "nothing. Unreachable through the document contract, which "
                "admits only the algorithms this arm implements",
            )
        ]
    if derived == coordinate.digest:
        return []
    return [
        _error(
            FindingCode.SOURCE_SURFACE_DRIFT,
            f"the declaration states source_surface {coordinate.digest} under "
            f"{coordinate.algorithm}, and the measured source renders to "
            f"{derived} over {len(facts)} Kernel-surface fact(s). The "
            "declaration was written against a different Kernel surface than "
            "the one it is being applied to, so its classifications describe "
            "source that is not this source. Re-derive the coordinate in the "
            "change that moved the imports -- that edit is the review the "
            "coordinate exists to force",
        )
    ]


def _check_catalogue_binding(
    declaration: KernelAdoptionDeclarationV2, catalogue: KernelSurfaceCatalogue | None
) -> list[Finding]:
    """Decision 52 (B). Which Kernel was declared, and which one was measured.

    Before this arm, `kernel_catalogue` was required, syntax-checked and
    compared with NOTHING, while the catalogue every surface verdict was taken
    against arrived separately from the observer. A product could declare
    Kernel `0.1.0a98` and hand the run `0.1.0a50`'s module lists, and the
    unknown-surface arm would answer against lists nobody had bound to the
    declared version.

    Four comparisons, and the fourth is the one that makes the first three mean
    something: version, peeled revision, distribution artifact digest, and a
    digest over the module LISTS themselves.
    """
    binding = declaration.kernel_catalogue
    if binding is None:
        return [
            _error(
                FindingCode.CATALOGUE_UNBOUND,
                "this applicable declaration binds no kernel_catalogue, so "
                "which Kernel its surface classifications are about is "
                "unstated",
            )
        ]
    if catalogue is None:
        return [
            _error(
                FindingCode.CATALOGUE_UNBOUND,
                f"the declaration binds {KERNEL_ROOT} {binding.version} at "
                f"{binding.revision} and this run was given no surface "
                "catalogue, so the binding could not be checked and no import "
                "could be classified. An applicable declaration is measured "
                "against a catalogue or it is not measured",
            )
        ]
    if not catalogue.known:
        return [
            _error(
                FindingCode.CATALOGUE_EMPTY,
                f"the supplied {KERNEL_ROOT} catalogue publishes no modules at "
                "all. Every import would be classified against an empty set, "
                "which is not a measurement of anything. A catalogue with no "
                "names is a catalogue that was not read",
            )
        ]
    findings: list[Finding] = []
    if catalogue.version != binding.version:
        findings.append(
            _error(
                FindingCode.CATALOGUE_DISAGREES,
                f"the declaration binds {KERNEL_ROOT} {binding.version} and "
                f"the catalogue supplied is {catalogue.version}. The surfaces "
                "were classified against one Kernel and are being measured "
                "against another",
            )
        )
    if catalogue.revision != binding.revision:
        findings.append(
            _error(
                FindingCode.CATALOGUE_DISAGREES,
                f"the declaration binds catalogue revision {binding.revision} "
                f"and the catalogue supplied was read at {catalogue.revision}. "
                "A version string is a name; the peeled commit is the bytes, "
                "and these are not the same bytes",
            )
        )
    if catalogue.artifact_digest is None:
        findings.append(
            _error(
                FindingCode.CATALOGUE_UNBOUND,
                f"the declaration binds artifact digest {binding.artifact_digest} "
                "and the observer supplied a catalogue carrying none, so the "
                "distribution the product actually resolved is unobserved. "
                "This is a repository-local read -- a lock file entry -- and "
                "not a registry attestation, but an unread one buys silence "
                "for the field that names the bytes",
            )
        )
    elif catalogue.artifact_digest != binding.artifact_digest:
        findings.append(
            _error(
                FindingCode.CATALOGUE_DISAGREES,
                f"the declaration binds artifact digest "
                f"{binding.artifact_digest} and the observer read "
                f"{catalogue.artifact_digest} out of this product's own "
                "resolution. The declaration describes a distribution the "
                "product is not installing",
            )
        )
    derived = catalogue_digest(
        version=catalogue.version,
        revision=catalogue.revision,
        supported=catalogue.supported,
        internal=catalogue.internal,
        root_exports=catalogue.root_exports,
    )
    if derived != binding.catalogue_digest:
        findings.append(
            _error(
                FindingCode.CATALOGUE_DISAGREES,
                f"the declaration binds catalogue_digest "
                f"{binding.catalogue_digest} and the supplied catalogue -- "
                f"{len(catalogue.supported)} supported, "
                f"{len(catalogue.internal)} internal and "
                f"{len(catalogue.root_exports)} root export name(s) -- digests "
                f"to {derived}. This is the comparison the other three cannot "
                "make: without it a product may state the right version and "
                "hand the run another Kernel's module lists, and every surface "
                "verdict is taken against a catalogue nobody bound. A digest "
                "taken under the superseded dmg-kernel-catalogue-v1 also lands "
                "here, and correctly: root exports changed the canonical "
                "subject, so a v1 value answers a different question and is "
                "RE-DERIVED rather than relabelled",
            )
        )
    return findings


def _floor_findings(
    surface: RequiredSurface, catalogue_version: str | None
) -> list[Finding]:
    """Is the declared floor satisfied by the Kernel the declaration binds?"""
    if catalogue_version is None:
        return []
    try:
        order = compare_versions(
            surface.floor,
            catalogue_version,
            where=f"required floor for {surface.module}",
        )
    except VersionError as error:
        return [
            _error(
                FindingCode.REQUIRED_FLOOR_UNORDERABLE,
                f"{surface.module} declares a floor that cannot be ordered "
                f"against the bound Kernel version: {error}. A floor nobody "
                "can compare is a number somebody typed, which is the state "
                "this arm exists to end",
            )
        ]
    if order <= 0:
        return []
    return [
        _error(
            FindingCode.REQUIRED_FLOOR_UNSATISFIED,
            f"{surface.module} declares floor {surface.floor} and this "
            f"declaration binds {KERNEL_ROOT} {catalogue_version}, which is "
            "lower. The product states it needs a Kernel it is not composing: "
            "either the floor is aspirational or the pin is behind it, and "
            "which one is a fact somebody has to state",
        )
    ]


def _check_required_surfaces(
    declaration: KernelAdoptionDeclarationV2,
    catalogue: KernelSurfaceCatalogue | None,
    observed_modules: frozenset[str],
    sources: dict[PurePosixPath, str],
) -> list[Finding]:
    """Decision 52 (C). `module`, `floor` and `proven_by` each compared to something.

    Five questions, and the fifth runs in the opposite direction from the rest
    because a one-directional inventory is a sample:

    1. Is the module one the bound Kernel PUBLISHES? A required dependency on a
       name the Kernel does not carry is a dependency on nothing.
    2. Is it IMPORTED? A declared dependency with no use is a field somebody
       wrote and nothing reads -- this package's own subject.
    3. Is the floor SATISFIED by the bound Kernel version?
    4. Is `proven_by` a path the run actually READ? A proof that cannot be
       opened is not a proof.
    5. Is every imported Kernel module CLASSIFIED as something? This is what
       turns `required_surfaces` from a list of whatever the author remembered
       into an inventory, and it is the arm that will bite on real products.

    The `proven_by` arm's second half is the weakest thing here and is labelled
    as such rather than dressed up: it checks that the named file MENTIONS the
    module it is offered as proof of. That establishes the proof is about the
    right subject. It does not establish that the file proves anything, and no
    check at this layer can -- a test's meaning is not readable from its text.
    """
    findings: list[Finding] = []
    version = None if catalogue is None else catalogue.version
    for surface in declaration.required_surfaces:
        # `publishes`, not `known`: `known` enumerates SUBMODULES and cannot
        # answer for the bare root, which is in neither Kernel list. Asking it
        # made a required root façade report `kernel.required.unpublished`
        # while omitting it reported `kernel.surface.unclassified`, so exit 0
        # was unreachable for any product importing the root.
        if catalogue is not None and not catalogue.publishes(surface.module):
            findings.append(
                _error(
                    FindingCode.REQUIRED_UNPUBLISHED,
                    f"{surface.module} is declared required and "
                    f"{KERNEL_ROOT} {catalogue.version} does not publish it. "
                    f"Its lists were read at {catalogue.revision} and carry "
                    f"{len(catalogue.supported)} supported and "
                    f"{len(catalogue.internal)} internal name(s), and its root "
                    f"façade publishes {len(catalogue.root_exports)} name(s). "
                    "A required surface that is not in the Kernel is either a "
                    "typo or a dependency on something that was removed -- or, "
                    f"for the bare {KERNEL_ROOT}, an observer that never read "
                    "the root's `__all__`",
                )
            )
        if surface.module not in observed_modules:
            findings.append(
                _error(
                    FindingCode.REQUIRED_UNUSED,
                    f"{surface.module} is declared required with floor "
                    f"{surface.floor}, and no measured source imports it. A "
                    "declared dependency nothing uses is the defect this "
                    "package exists to catch, arriving inside a declaration: "
                    "the floor it carries constrains the pin for a reason that "
                    "no longer exists. Remove the entry, or the import it "
                    "described is not being measured",
                )
            )
        findings.extend(_floor_findings(surface, version))
        proof = sources.get(surface.proven_by)
        if proof is None:
            findings.append(
                _error(
                    FindingCode.REQUIRED_PROOF_UNREAD,
                    f"{surface.module} names {surface.proven_by.as_posix()} as "
                    "the proof of its floor, and this run did not read that "
                    "path. A floor with an unreadable proof is a number "
                    "somebody typed. Either the path is wrong or the "
                    "observation does not cover it -- and a proof outside the "
                    "measured inventory is a proof nobody can check",
                    path=surface.proven_by,
                )
            )
        elif surface.module not in proof:
            findings.append(
                _error(
                    FindingCode.REQUIRED_PROOF_SILENT,
                    f"{surface.module} names {surface.proven_by.as_posix()} as "
                    "the proof of its floor, and that file never mentions the "
                    "module. This is the weakest of the proof arms and claims "
                    "only what it checks: a proof must at least be about its "
                    "subject. Whether it proves the floor is not readable from "
                    "the text and is not asserted here",
                    path=surface.proven_by,
                )
            )

    classified = (
        {item.module for item in declaration.required_surfaces}
        | {item.module for item in declaration.transitional_surfaces}
        | set(declaration.prohibited_modules)
    )
    for module in sorted(observed_modules - classified):
        findings.append(
            _error(
                FindingCode.SURFACE_UNCLASSIFIED,
                f"the measured source imports {module} and this declaration "
                "classifies it as nothing -- not required, not transitional, "
                "not prohibited. required_surfaces is an INVENTORY of what the "
                "product depends on, not a sample of what its author "
                "remembered: an unclassified import carries no floor, no "
                "retirement date and no prohibition, so nothing about it is "
                "measured and a clean run would say otherwise",
            )
        )
    return findings


def _check_expiry_against_declaration(
    declaration: KernelAdoptionDeclarationV2,
) -> list[Finding]:
    """A retirement deadline that had already passed when it was written.

    Decidable from the document alone, with no staleness policy and no clock:
    if `expiry < declared_at`, the undertaking was overdue on the day somebody
    undertook it. That is the shape a COPIED declaration takes -- the dates
    came with the file -- and it is exactly the case the run-date comparison
    cannot distinguish from an honest deadline that later lapsed.
    """
    findings: list[Finding] = []
    for surface in declaration.transitional_surfaces:
        try:
            expiry = date.fromisoformat(surface.expiry)
        except ValueError:
            # `_check_expiry` already refuses an unorderable expiry, with the
            # code whose repair is fixing the date. Reporting it twice under
            # two codes would send one reader to two edits.
            continue
        if expiry >= declaration.declared_at:
            continue
        findings.append(
            _error(
                FindingCode.TRANSITIONAL_EXPIRY_PREDATES_DECLARATION,
                f"{surface.module} is classified transitional with expiry "
                f"{surface.expiry}, and this declaration was written on "
                f"{declaration.declared_at.isoformat()} -- the deadline had "
                f"already passed by {(declaration.declared_at - expiry).days} "
                "day(s) when it was undertaken. A date that was never in the "
                "future is not a commitment; it is a date that came with a "
                "copied file",
            )
        )
    return findings


class _SurfaceAccumulator:
    """The merge rule, in ONE place, for both source-surface algorithms.

    One entry per (file, Kernel module), MERGED across statements: two imports
    of one module in one file are one fact carrying the union of what they
    bound, so splitting a `from x import a, b` in two moves neither digest.
    Line numbers are not accumulated at all.

    Both algorithms merge the SAME way over the SAME statements and differ only
    in what each fact records, so the rule lives here rather than once per
    algorithm. Two implementations of one merge is the drift the source-surface
    coordinate exists to prevent, and a second copy of it inside the coordinate
    would be that drift.
    """

    __slots__ = ("bindings", "stars", "symbols")

    def __init__(self) -> None:
        self.symbols: dict[tuple[PurePosixPath, str], set[str]] = defaultdict(set)
        self.bindings: dict[tuple[PurePosixPath, str], set[SurfaceBinding]] = (
            defaultdict(set)
        )
        self.stars: set[tuple[PurePosixPath, str]] = set()

    def add(self, path: PurePosixPath, entry: _KernelImport) -> None:
        key = (path, entry.module)
        # Both are `defaultdict` accesses, so a star-only import -- which binds
        # and names nothing -- still CREATES its key. A star that produced no
        # fact would be a wholesale re-export invisible to the digest.
        self.symbols[key].update(entry.bound)
        self.bindings[key].update(entry.bindings)
        if entry.star:
            self.stars.add(key)

    def facts(self) -> frozenset[SurfaceFact]:
        """v1's facts: LOCAL bound names. Frozen, and unchanged by v2's arrival."""
        return frozenset(
            SurfaceFact(
                path=path,
                module=module,
                symbols=tuple(sorted(symbols)),
                star=(path, module) in self.stars,
            )
            for (path, module), symbols in self.symbols.items()
        )

    def identity_facts(self) -> frozenset[SurfaceIdentityFact]:
        """v2's facts: the Kernel's name and the local one, kept apart."""
        return frozenset(
            SurfaceIdentityFact(
                path=path,
                module=module,
                bindings=tuple(sorted(bindings)),
                star=(path, module) in self.stars,
            )
            for (path, module), bindings in self.bindings.items()
        )


def surface_identity_facts(
    sources: dict[PurePosixPath, str],
) -> frozenset[SurfaceIdentityFact]:
    """Every v2 surface fact over the supplied source. Reads only `sources`.

    Uses the same parser (`_kernel_imports`) and the same merge rule
    (`_SurfaceAccumulator`) `evaluate` uses, so there is no second sweep to
    drift from the first.

    A source that will not parse is SKIPPED here rather than reported. This is
    a derivation helper, not an arm: `evaluate` already refuses an unparsed
    file as an unmeasured one (`kernel.source.unreadable`), and a product that
    reached this function without running that has a measurement problem this
    function cannot repair and must not paper over by raising a different one.
    """
    accumulated = _SurfaceAccumulator()
    for path in sorted(sources, key=lambda item: item.as_posix()):
        try:
            tree = ast.parse(sources[path], filename=path.as_posix())
        except (SyntaxError, ValueError):
            continue
        for entry in _kernel_imports(tree):
            accumulated.add(path, entry)
    return accumulated.identity_facts()


def observed_surface_identity(
    facts: frozenset[SurfaceIdentityFact],
) -> tuple[str, str]:
    """`observed_surface`'s v2 counterpart: the digest and its rendering.

    Same purpose and same reason for existing. A product migrating from
    `dmg-kernel-surface-v1` to `dmg-kernel-surface-v2` needs the value the
    runner would derive, and it must come from the runner rather than from a
    second implementation.

    A v2 digest IS compared. `declaration_contract_v2` admits
    `ACCEPTED_SOURCE_SURFACE_ALGORITHMS` -- exactly `{dmg-kernel-surface-v1,
    dmg-kernel-surface-v2}` -- and `_check_source_surface` dispatches on the
    declared name, so a product that declares the value this function returns
    is measured against it and refused when its source moves.

    (This paragraph previously said the opposite. It was true when written and
    the same change that made it false is the change that admitted v2, which is
    exactly the shape a stale docstring takes: nothing fails when a comment
    stops being true.)
    """
    return surface_identity_digest(facts), render_surface_identity(facts)


def observed_surface(
    facts: frozenset[SurfaceFact],
) -> tuple[str, str]:
    """The derived digest and its canonical rendering. For diagnosis and tooling.

    A product writing its declaration for the first time needs the value the
    runner will compare against, and it must come from the runner rather than
    from a hand-rolled second implementation -- two renderings of one surface
    is the drift this whole coordinate exists to prevent.
    """
    return surface_digest(facts), render_surface(facts)


def _check_declaration(
    inputs: KernelAdoptionInputs,
    kernel_import_sites: list[tuple[PurePosixPath, int, str]],
    observed_symbols: dict[str, frozenset[tuple[PurePosixPath, str]]],
    facts: frozenset[SurfaceFact],
    identity_facts: frozenset[SurfaceIdentityFact],
) -> list[Finding]:
    """Arms 4, 6 and 7, and the five states the declaration can be in.

    The input is the product's own `.dotmac/kernel-adoption.json` — its own
    document, pointed at by the profile's optional `kernel_adoption_binding`
    and never carried inside the profile. These arms REFUSE when it is missing,
    empty, incomplete or corrupt rather than reporting nothing.

    `not_applicable` is checked, not accepted. An exemption states an
    enforceable premise or the region is unmonitored rather than exempt, and
    the premise here is decidable from the same source inventory the arms above
    already read: a repository that declares it consumes no Kernel and then
    imports one is named, with the file and line of the import that contradicts
    it.
    """
    outcome = inputs.declaration
    if not isinstance(outcome, DeclarationPresent):
        code = REFUSAL_CODES.get(type(outcome))
        if code is None:
            # A sixth outcome added without a code would otherwise fall through
            # this function and be reported as nothing, which is the exact
            # shape -- a refusal read as a pass -- that the four below exist to
            # prevent.
            raise AssertionError(
                f"{type(outcome).__name__} is a declaration outcome with no "
                "finding code. A new refusal is given one or it silently reads "
                "as a clean run"
            )
        return [
            _error(
                code,
                f"{outcome.detail}. Arms 1, 4, 6 and 7 are therefore "
                "UNMONITORED rather than clean: no prohibited surface, no "
                "transitional surface and no expired transition can be "
                "reported, and the pin arm cannot even be told how many "
                "observations it needs, because that is a function of an "
                "applicability nobody stated. This is a refusal, not a pass",
            )
        ]

    declaration: AnyKernelAdoptionDeclaration = outcome.declaration
    if isinstance(declaration, KernelAdoptionDeclarationV2):
        return _check_v2(
            inputs,
            declaration,
            kernel_import_sites,
            observed_symbols,
            facts,
            identity_facts,
        )

    #: `product_revision` is REQUIRED of every declaration, `not_applicable`
    #: included, and nothing in this package compares it with the revision the
    #: run measured. Disclosed on both paths rather than only the applicable
    #: one: the `not_applicable` shape is the shape that is CITABLE today, so
    #: an unread field left silent there is an unread field inside the only
    #: claim anyone can make -- which is the defect this package exists to
    #: catch, in the one place it would have gone unseen. Open decision 52 (A)
    #: owns the repair, and it is a non-self-referential coordinate rather than
    #: a comparison: a committed file cannot contain its own commit.
    unevaluated = _notice(
        FindingCode.DECLARATION_FIELDS_UNEVALUATED,
        f"this declaration states product_revision "
        f"{declaration.product_revision}, and this runner does not compare it "
        "with the revision it measured. Published rather than left silent "
        "because a declared field nothing reads is the defect this package "
        "exists to catch. The repair is a non-self-referential source "
        "coordinate in a versioned successor contract -- open decision 52 -- "
        "and NOT an edit to KernelAdoptionDeclaration.v1, which is frozen",
    )
    if declaration.applicability is KernelAdoptionApplicability.NOT_APPLICABLE:
        if not kernel_import_sites:
            return [unevaluated]
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

    findings: list[Finding] = [
        _notice(
            FindingCode.DECLARATION_FIELDS_UNEVALUATED,
            "this declaration is 'applicable' and states product_revision "
            f"{declaration.product_revision}, a kernel_catalogue and "
            f"{len(declaration.required_surfaces)} entries in required_surfaces. NONE of "
            "those three is evaluated by this runner. They are published here "
            "rather than left silent because a declared field nothing compares "
            "is the defect this package exists to catch, and a reader must not "
            "infer from a clean run that they were checked. The repair is a "
            "versioned successor contract carrying a non-self-referential "
            "source coordinate, a catalogue digest comparison and "
            "required-surface floor semantics -- open decision 52 -- and NOT an "
            "edit to KernelAdoptionDeclaration.v1, which is frozen. Until it "
            "exists an 'applicable' run is not citable as enforcement",
        )
    ]
    findings.extend(
        _check_applicable_common(
            declaration, kernel_import_sites, observed_symbols, inputs.as_of
        )
    )
    return findings


def _check_applicable_common(
    declaration: AnyKernelAdoptionDeclaration,
    kernel_import_sites: list[tuple[PurePosixPath, int, str]],
    observed_symbols: dict[str, frozenset[tuple[PurePosixPath, str]]],
    as_of: date,
) -> list[Finding]:
    """The arms an `applicable` declaration gets under EITHER contract.

    Prohibition and the transitional ratchet were already honest in v1 -- they
    read fields and compare them to source -- so v2 does not reimplement them.
    Extracted rather than duplicated: two copies of the prohibition arm would
    be two places for a product to be measured differently depending on which
    contract it wrote, which is the per-product adapter this package refuses,
    wearing a version number.
    """
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
        _check_transitional(declaration.transitional_surfaces, observed_symbols, as_of)
    )
    return findings


def _check_v2(
    inputs: KernelAdoptionInputs,
    declaration: KernelAdoptionDeclarationV2,
    kernel_import_sites: list[tuple[PurePosixPath, int, str]],
    observed_symbols: dict[str, frozenset[tuple[PurePosixPath, str]]],
    facts: frozenset[SurfaceFact],
    identity_facts: frozenset[SurfaceIdentityFact],
) -> list[Finding]:
    """Everything a `KernelAdoptionDeclaration.v2` document is measured against.

    There is NO `kernel.declaration.fields-unevaluated` notice on this path,
    and its absence is the whole claim of the successor contract: every field
    v2 requires is read by an arm below. The notice remains on the v1 path,
    because a v1 `applicable` declaration still carries three fields nothing
    compares and is still non-citable.

    The prelude runs for BOTH applicability values. A `not_applicable` v2
    declaration still states `declared_at` and `source_predecessor`, and a
    field required of a document is read wherever the document is read -- the
    one thing this package cannot do is require a field on a path where nothing
    looks at it.
    """
    findings: list[Finding] = []
    findings.extend(_check_declared_at(declaration, inputs.as_of))
    findings.extend(_check_predecessor(inputs))

    if declaration.applicability is KernelAdoptionApplicability.NOT_APPLICABLE:
        if not kernel_import_sites:
            return findings
        path, line, module = kernel_import_sites[0]
        findings.append(
            _error(
                FindingCode.DECLARATION_PREMISE_FALSE,
                f"the declaration states applicability 'not_applicable' — "
                f"{declaration.not_applicable_reason!r} — but this repository "
                f"imports {module}, at {path.as_posix()}:{line}, and "
                f"{len(kernel_import_sites)} Kernel import(s) in total. An "
                "exemption states an ENFORCEABLE premise; this one is "
                "contradicted by the repository's own source, so the "
                "classification cannot stand and the surface arms do not run",
                path=path,
                line=line,
            )
        )
        return findings

    observed_modules = frozenset(fact.module for fact in facts)
    findings.extend(_check_source_surface(declaration, facts, identity_facts))
    findings.extend(_check_catalogue_binding(declaration, inputs.catalogue))
    findings.extend(
        _check_required_surfaces(
            declaration, inputs.catalogue, observed_modules, inputs.sources
        )
    )
    findings.extend(_check_expiry_against_declaration(declaration))
    # Transitional baselines describe the Kernel surface, not the importing
    # module's local spelling.  Reuse the v2 identity facts already derived by
    # the one source sweep; rebuilding an alias-aware parser here would create
    # a second canonicalizer.  v1 deliberately keeps its historical local-name
    # behaviour below.
    kernel_symbols: defaultdict[str, set[tuple[PurePosixPath, str]]] = defaultdict(set)
    for fact in identity_facts:
        kernel_symbols[fact.module].update(
            (fact.path, binding.kernel) for binding in fact.bindings
        )
    observed_kernel_symbols = {
        module: frozenset(sites) for module, sites in kernel_symbols.items()
    }
    findings.extend(
        _check_applicable_common(
            declaration,
            kernel_import_sites,
            observed_kernel_symbols,
            inputs.as_of,
        )
    )
    return findings


def evaluate(inputs: KernelAdoptionInputs) -> AdoptionReport:
    """Measure Kernel adoption over the supplied product source.

    Reads only `inputs`. No filesystem, no network, no profile document.
    """
    findings: list[Finding] = []
    kernel_import_sites: list[tuple[PurePosixPath, int, str]] = []
    observed_symbols: dict[str, set[tuple[PurePosixPath, str]]] = {}
    #: The merge rule and both algorithms' fact builders. See
    #: `_SurfaceAccumulator`, and `surface` for the rest of the
    #: canonicalization and for what a digest does not prove.
    accumulated = _SurfaceAccumulator()
    catalogue = inputs.catalogue
    module_exports_required = isinstance(
        inputs.declaration, DeclarationPresent
    ) and isinstance(inputs.declaration.declaration, KernelAdoptionDeclarationV2)

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
        if module_exports_required:
            findings.extend(_check_module_alias_attributes(path, tree, catalogue))

        for entry in imports:
            module = entry.module
            kernel_import_sites.append((path, entry.line, module))
            observed_symbols.setdefault(module, set()).update(
                (path, name) for name in entry.bound
            )
            accumulated.add(path, entry)

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
            elif module == KERNEL_ROOT:
                # The root façade is its own published surface, classified
                # against `__all__` rather than against the submodule lists.
                # See `_check_root_facade` for the four import shapes.
                findings.extend(_check_root_facade(path, entry, catalogue))
            else:
                # Nested rather than a second `elif`, so the absent-catalogue
                # case cannot fall through to the arm that would have to read
                # it. An unclassifiable surface is REFUSED; it never lands in
                # the branch that reports a name as published.
                if catalogue is None:
                    findings.append(
                        _error(
                            FindingCode.CATALOGUE_ABSENT,
                            f"imports {module}, and this run was given no "
                            f"{KERNEL_ROOT} surface catalogue, so whether that "
                            "name is published cannot be decided. An "
                            "unclassifiable surface is refused rather than "
                            "reported as a known one: a caller with no "
                            "catalogue must not get a clean unknown-surface "
                            "arm over every import it made",
                            path=path,
                            line=entry.line,
                        )
                    )
                elif module not in catalogue.known:
                    findings.append(
                        _error(
                            FindingCode.SURFACE_UNKNOWN,
                            f"imports {module}, which {KERNEL_ROOT} "
                            f"{catalogue.version} does not publish. Its module "
                            f"lists were read at {catalogue.revision} and "
                            f"carry {len(catalogue.supported)} supported and "
                            f"{len(catalogue.internal)} internal names. An "
                            "unpublished surface is either a typo or a module "
                            "the Kernel does not undertake to keep",
                            path=path,
                            line=entry.line,
                        )
                    )
                elif module_exports_required:
                    findings.extend(_check_module_exports(path, entry, catalogue))

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

    facts = accumulated.facts()
    # Both fact sets, from the ONE sweep above. The declaration's own
    # `source_surface.algorithm` selects which is compared; deriving both
    # unconditionally is what keeps the label a CHOICE between two
    # measurements rather than an assertion about one.
    identity_facts = accumulated.identity_facts()

    findings.extend(_check_pins(inputs))
    findings.extend(_pin_sufficiency(inputs))
    findings.extend(
        _check_declaration(
            inputs,
            kernel_import_sites,
            {key: frozenset(value) for key, value in observed_symbols.items()},
            facts,
            identity_facts,
        )
    )

    return AdoptionReport(findings=tuple(findings))
