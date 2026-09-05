#!/usr/bin/env python3
"""This repository's Kernel-adoption observation. The whole product-side surface.

`dotmac_governance` is a subject of the Kernel-adoption standard and not only
its author: it carries `.dotmac/kernel-adoption.json`, declaring
`not_applicable` on the premise that it imports `dotmac_kernel` nowhere. That
premise is machine-checkable, and this file is what makes it checked here
rather than asserted — `kernel_adoption_control` reports
`kernel.declaration.premise-false` if this repository ever grows such an
import.

**This file is the entire product-side contract.** One callable, taking the
checkout root and returning a `ProductObservation`. It classifies nothing,
decides nothing and cannot state a declaration: the runner reads
`.dotmac/kernel-adoption.json` itself, so a product cannot hand Governance a
convenient one. An enrolling repository writes a file this shape and a workflow
step, and nothing else.

Three choices below are the ones a copy of this file has to make, so each says
why:

- **The inventory is enumerated from a declared rule, not from a search's own
  results.** Every `*.py` in the tree, plus the extensionless `tools/dotmac-*`
  launchers, which are Python and which a `.py` sweep walks straight past. The
  same blind spot is real elsewhere: `KernelAdoptionInputs` records
  `dotmac_platform_control_plane`'s `rotation_runtime_oracle.pyprogram`, which
  imports `dotmac_kernel.db` and is not a `.py` file.
- **An unreadable file is not skipped.** Its bytes go through as a source the
  engine will fail to parse and report `kernel.source.unreadable`. Dropping it
  here would be the observation quietly deciding what is measured.
- **The catalogue is `None`, and that is a stated absence.** This repository
  consumes no Kernel, so it holds no evidence of the Kernel's published module
  lists. Inventing a version and a revision to fill the field would put a
  coordinate nobody read into a bound report. Every Kernel import measured
  without a catalogue is refused `kernel.catalogue.absent`, so the `None`
  cannot buy silence — it can only be honest.
"""

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kernel_adoption_control.runner import ProductObservation  # noqa: E402

__all__ = ["EXCLUDED_DIRECTORIES", "observe"]

#: Directories that hold no source of this repository's own. `.git` is Git's
#: object store; a nested checkout under any `*_worktree` directory is another
#: revision's source and would be measured as though it were this one.
EXCLUDED_DIRECTORIES = frozenset({".git", ".mypy_cache", ".ruff_cache", "__pycache__"})

#: The extensionless Python launchers. Named individually rather than globbed
#: on `tools/*`, so a shell script dropped in that directory is not read as
#: Python and reported unparseable.
EXTENSIONLESS_ENTRY_POINTS = (
    "tools/dotmac-agent",
    "tools/dotmac-gates",
    "tools/dotmac-programme",
    "tools/dotmac-standards",
)


def _excluded(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(
        part in EXCLUDED_DIRECTORIES or part.endswith("_worktree") for part in parts
    )


def observe(root: Path) -> ProductObservation:
    """Read this repository's Python entry points as text."""
    sources: dict[PurePosixPath, str] = {}
    for path in sorted(root.rglob("*.py")):
        if _excluded(path, root):
            continue
        sources[PurePosixPath(path.relative_to(root).as_posix())] = path.read_text(
            encoding="utf-8", errors="replace"
        )
    for relative in EXTENSIONLESS_ENTRY_POINTS:
        path = root / relative
        if path.is_file():
            sources[PurePosixPath(relative)] = path.read_text(
                encoding="utf-8", errors="replace"
            )
    return ProductObservation(sources=sources, catalogue=None, pin_sites=())
