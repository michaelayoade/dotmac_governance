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
`DeclarationPresent` carrying empty tuples. The second is one of FOUR
refusals, and every one of them is an error:

- **missing** -- no file at the path.
- **empty** -- the file is there and holds no document at all. Not "missing",
  because the path exists; not "corrupt", because there are no bytes to fix.
- **incomplete** -- a JSON object that never states a required key.
- **corrupt** (`DeclarationUnreadable`) -- anything else that cannot be
  understood: unreadable bytes, invalid JSON, a non-object, an unknown key, a
  value stated wrongly.

The middle two are the pair most likely to collapse, so the line between them
is stated once and held by the parser rather than by a convention: absence of a
key is INCOMPLETE, wrongness of a stated value is CORRUPT, and absence is
checked first, so a document exhibiting both reports incomplete.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from .contracts import (
    DeclarationEmpty,
    DeclarationIncomplete,
    DeclarationMissing,
    DeclarationOutcome,
    DeclarationPresent,
    DeclarationUnreadable,
)
from .declaration_contract import (
    DeclarationError,
    IncompleteDeclarationError,
    parse_declaration,
)

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
    if not raw.strip():
        return DeclarationEmpty(
            f"{location.as_posix()} exists and holds no document "
            f"({len(raw)} byte(s), all whitespace). This is reported apart from "
            "a missing file and apart from a corrupt one because the repair "
            "differs from both: the path is already there, so there is nothing "
            "to create and nothing to fix -- write a "
            "KernelAdoptionDeclaration.v1 document into it"
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
    except IncompleteDeclarationError as error:
        return DeclarationIncomplete(
            f"{location.as_posix()}: {error}. The document is a declaration "
            "with an obligation it never states; refusing to read an unstated "
            "obligation as a discharged one"
        )
    except DeclarationError as error:
        return DeclarationUnreadable(
            f"{location.as_posix()}: {error}. Refusing to report a declaration "
            "that does not parse as an empty classification"
        )
