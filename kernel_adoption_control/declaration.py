"""Read a repository's Kernel-adoption declaration, and never raise.

Every failure mode becomes a typed outcome instead of an exception, because a
caller that has to remember a `try` around this is a caller that will one day
report a clean run over a file it could not open. The three outcomes are
`DeclarationPresent`, `DeclarationMissing` and `DeclarationUnreadable`, and
there is no fourth — in particular there is no empty one.

The declaration is its own document, `.dotmac/kernel-adoption.json`, under the
Governance-owned `KernelAdoptionDeclaration.v1` contract. The conformance
profile carries only a POINTER to it — `kernel_adoption_binding` — so a
classification never arrives as a line in a diff to that profile, and the two
documents version independently.

A repository that states no binding is read at the default path. That is not a
default CLASSIFICATION: if nothing is there, the outcome is
`DeclarationMissing`, which is an error.

The distinction this module exists to hold is between two sentences that a
single empty list would collapse: "this repository prohibits nothing" and
"nobody has said what this repository prohibits". The first is
`DeclarationPresent` carrying empty tuples. The second is
`DeclarationMissing`, and it is an error.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from .contracts import (
    DeclarationMissing,
    DeclarationOutcome,
    DeclarationPresent,
    DeclarationUnreadable,
)
from .declaration_contract import DeclarationError, parse_declaration

__all__ = ["DECLARATION_PATH", "read_declaration"]

#: Where the declaration lives when the profile states no binding.
DECLARATION_PATH = PurePosixPath(".dotmac/kernel-adoption.json")


def read_declaration(
    root: Path, relative: PurePosixPath | None = None
) -> DeclarationOutcome:
    """Return the repository's declaration, or the refusal that stands for it.

    A file that does not exist is MISSING; a file that exists and cannot be
    read, parsed or understood is UNREADABLE. The two are kept apart because
    the repairs differ — one writes a section, the other fixes one — and a
    guard that names the wrong repair sends the reader to the wrong file.
    """
    location = DECLARATION_PATH if relative is None else relative
    path = root / location
    if not path.is_file():
        return DeclarationMissing(
            f"{location.as_posix()} does not exist, so this repository has "
            "declared no Kernel surfaces. That is not the same as declaring "
            "that none are prohibited: write a KernelAdoptionDeclaration.v1 "
            'there, using applicability "not_applicable" with a reason if the '
            "repository consumes no Kernel"
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return DeclarationUnreadable(
            f"{location.as_posix()} could not be read: {error}. Refusing to "
            "report it as an empty classification"
        )
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as error:
        return DeclarationUnreadable(
            f"{location.as_posix()} is not valid JSON: {error}. Refusing to "
            "report it as an empty classification"
        )
    try:
        return DeclarationPresent(parse_declaration(document))
    except DeclarationError as error:
        return DeclarationUnreadable(
            f"{location.as_posix()}: {error}. Refusing to report a declaration "
            "that does not parse as an empty classification"
        )
