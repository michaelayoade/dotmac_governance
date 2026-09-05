"""Read a repository's Kernel-adoption declaration, and never raise.

Every failure mode becomes a typed outcome instead of an exception, because a
caller that has to remember a `try` around this is a caller that will one day
report a clean run over a file it could not open. The three outcomes are
`DeclarationPresent`, `DeclarationMissing` and `DeclarationUnreadable`, and
there is no fourth — in particular there is no empty one.

The section lives in `.dotmac/standards-profile.json`, whose schema Governance
owns (schema version 12, section version 1) and whose instance each repository
owns. Parsing is delegated to `standards_control.profile`, which is the one
parser for that file; this module adds no second one. It reads the section by
key and hands it to `parse_kernel_adoption` rather than re-deriving what a valid
section looks like.

The distinction this module exists to hold is between two sentences that a
single empty list would collapse: "this repository prohibits nothing" and
"nobody has said what this repository prohibits". The first is
`DeclarationPresent` carrying empty tuples. The second is
`DeclarationMissing`, and it is an error.
"""

from __future__ import annotations

import json
from pathlib import Path

from standards_control.profile import ProfileError, parse_kernel_adoption

from .contracts import (
    DeclarationMissing,
    DeclarationOutcome,
    DeclarationPresent,
    DeclarationUnreadable,
)

__all__ = ["PROFILE_PATH", "SECTION_KEY", "read_declaration"]

#: Where the section lives, relative to a repository root.
PROFILE_PATH = Path(".dotmac/standards-profile.json")

#: The section's key inside that document.
SECTION_KEY = "kernel_adoption"


def read_declaration(root: Path) -> DeclarationOutcome:
    """Return the repository's declaration, or the refusal that stands for it.

    A file that does not exist is MISSING; a file that exists and cannot be
    read, parsed or understood is UNREADABLE. The two are kept apart because
    the repairs differ — one writes a section, the other fixes one — and a
    guard that names the wrong repair sends the reader to the wrong file.
    """
    path = root / PROFILE_PATH
    if not path.is_file():
        return DeclarationMissing(
            f"{PROFILE_PATH.as_posix()} does not exist, so this repository has "
            f"declared no Kernel surfaces. That is not the same as declaring "
            f"that none are prohibited: add a {SECTION_KEY!r} section, using "
            'applicability "not_applicable" with a reason if the repository '
            "consumes no Kernel"
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return DeclarationUnreadable(
            f"{PROFILE_PATH.as_posix()} could not be read: {error}. Refusing to "
            "report it as an empty classification"
        )
    try:
        document: object = json.loads(raw)
    except json.JSONDecodeError as error:
        return DeclarationUnreadable(
            f"{PROFILE_PATH.as_posix()} is not valid JSON: {error}. Refusing to "
            "report it as an empty classification"
        )
    if not isinstance(document, dict):
        return DeclarationUnreadable(
            f"{PROFILE_PATH.as_posix()} does not contain an object, so it holds "
            f"no {SECTION_KEY!r} section to read"
        )
    if SECTION_KEY not in document:
        return DeclarationMissing(
            f"{PROFILE_PATH.as_posix()} declares no {SECTION_KEY!r} section. An "
            "absent section is not a statement that nothing is prohibited — "
            "nobody has said either way, and this check will not answer for "
            "them"
        )
    try:
        return DeclarationPresent(parse_kernel_adoption(document[SECTION_KEY]))
    except ProfileError as error:
        return DeclarationUnreadable(
            f"{PROFILE_PATH.as_posix()}: {error}. Refusing to report a section "
            "that does not parse as an empty classification"
        )
