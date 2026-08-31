#!/usr/bin/env python3
"""Refuse an ADR citation that cannot resolve in the repository making it.

`dotmac_governance` ADR 0031 states the rule this implements:

    A cross-repository ADR reference names its owning repository. A bare number
    refers only to a record in the citing repository.

The half that is decidable from repository content alone is the second one. A
bare ``ADR-NNNN`` asserts that the CITING repository holds a record at that
number. Where it does not, the citation is wrong -- not merely unhelpful --
even when exactly one candidate exists anywhere in the fleet.

## Why that half, and why now

`dotmac_platform_control_plane` cites `ADR-0018` bare seven times, in tests,
architecture documentation and its `AGENTS.md`. Every one means
`dotmac_starter_mt` ADR-0018. They resolve today only BY ELIMINATION, because
that repository's own numbering stops at 0016. The day it writes an ADR-0018,
all seven change meaning: no file edited, no diff, no review.

A reference that decays without an edit cannot be maintained by care, and a
guard that only fires after the collision arrives would never have fired at
all -- the collision arrives without an edit too. So the check is written to be
red BEFORE the collision, while the references still resolve.

## What is a citation, and what is a reproduction

This is the part that decides whether the guard is usable, and it is decided by
a PROPERTY of the text rather than by matching the string ``ADR-``. A guard
that matched the string would fail on prose explaining the rule, on ADR 0031's
own text, and on this docstring -- the family that has cost this fleet three CI
cycles in one day, where a ``"PYTHONPATH" not in dockerfile`` check failed on
the comment documenting its absence and a ledger test caught its own docstring.

Three exclusions, each structural:

- **Fenced code blocks** (```` ``` ````) are specimens. A record showing the
  correct form of a citation is not making one.
- **Markdown blockquote lines** (``>``) are reproductions. Quoting someone
  else's defective header -- which ADR 0030 and ADR 0031 both do, deliberately,
  as the exhibit -- is reporting a citation, not issuing one.
- **A qualified reference** is resolvable by construction, so it is not this
  check's business. A qualifier is recognised when a declared repository name
  appears EARLIER ON THE SAME LINE.

The baseline file is excluded for the same reason as a blockquote: it lists
findings rather than citing records, and a ledger that catches its own entries
measures itself.

The same-line window is a deliberate limit and it has a consequence worth
stating: a qualifier that wraps onto a different line than its number reads as
unqualified here and is reported. That is the exhibit's exact shape --
``ADR-0018 in`` ends a line and ```dotmac_governance``` begins the next -- and
the finding is correct there for an independent reason, since that repository
holds no ADR-0018 either. Where the number IS held locally, nothing fires at
all, so the window costs a finding only in the case where a reader would also
have had to hunt. Keeping a qualifier on the same line as its number is the
repair, and it is a readability improvement rather than a nuisance.

## Why a set, and why two-directional

Seven references repaired while an eighth appears leaves a count unchanged, so
the baseline is a SET of exact findings rather than a number. It fails when the
set grows -- new debt -- and when a baseline entry stops firing without being
removed in the same change, because an entry that no longer matches is an
exemption nobody is checking any more. That is `dotmac_starter_mt` ADR-0018
rule 3, applied here.

The baseline holds KNOWN DEBT and nothing else. It is deliberately NOT the
mechanism for "this reference is reviewed and correct" -- a reproduction is
excluded structurally above, so the two mechanisms cannot be confused, which is
that record's rule 4.

## Corpus

Files come from ``git ls-files --cached --others --exclude-standard``: tracked
files AND untracked files git would not ignore. Tracked-only was the wrong
corpus in a measured incident on this fleet -- a new contract was swallowed by
a `.gitignore` glob, so it was not in the corpus, so the scan was green over a
file that had never been committed. "Not in the corpus" looks exactly like
"clean".

The validator is deliberately callable against a temporary directory so its
known-bad controls can prove that they fail, rather than merely asserting that
the production tree passes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BASELINE_PATH = Path(".dotmac/adr-reference-baseline.json")
ADR_DIR = Path("docs/adr")

#: Extensions scanned. Declared rather than "every text file" so that adding a
#: new kind of file is a visible decision: a family this guard does not read is
#: unmonitored, and the list is where a reader sees which families those are.
SCANNED_SUFFIXES = frozenset(
    {".md", ".py", ".yml", ".yaml", ".toml", ".json", ".sh", ".txt", ".cfg", ".ini"}
)

#: The qualifier vocabulary of ADR 0031 section 3: canonical repository names,
#: plus the established short names that record admits. Closed and reviewed --
#: an unknown qualifier is not a qualifier, so a typo in a repository name
#: produces a finding rather than silently passing.
QUALIFIERS = (
    "dotmac_governance",
    "dotmac_starter_mt",
    "dotmac_platform_control_plane",
    "dotmac_vendor_control_plane",
    "dotmac_sub",
    "dotmac_erp",
    "dotmac_workspace",
    "dotmac_integrator",
    "dotmac_observability",
    "dotmac_crm",
    "dotmac_academy_app",
    "dotmac_identity_ops",
    "dotmac-deployment-foundation",
    "dotmac-deployment-control",
    "dotmac-integration-client",
    "governance",
    "kernel",
    "starter",
    "platform cp",
)

_REFERENCE = re.compile(r"\bADR[- ](\d{4})\b")
_FENCE = re.compile(r"^\s*(```|~~~)")
_QUOTE = re.compile(r"^\s*>")
_ADR_FILE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


class ReferenceCheckError(Exception):
    """The check could not be performed. Nothing about the tree is claimed."""


@dataclass(frozen=True, order=True)
class Finding:
    """One unresolvable citation, addressed exactly enough to be repaired."""

    path: str
    line: int
    number: str

    def key(self) -> str:
        return f"{self.path}:{self.line}:ADR-{self.number}"


def local_adr_numbers(root: Path) -> frozenset[str]:
    """The four-digit numbers this repository's own ADR directory holds."""
    directory = root / ADR_DIR
    if not directory.is_dir():
        return frozenset()
    found = set()
    for entry in directory.iterdir():
        match = _ADR_FILE.match(entry.name)
        if match:
            found.add(match.group(1))
    return frozenset(found)


def corpus(root: Path) -> tuple[Path, ...]:
    """Tracked plus untracked-but-not-ignored files, filtered to text families."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ReferenceCheckError(
            f"cannot enumerate the corpus in {root}: {exc}"
        ) from exc
    paths = []
    for name in result.stdout.splitlines():
        if not name:
            continue
        if name == str(BASELINE_PATH):
            # The baseline ENUMERATES findings; it does not make citations. A
            # ledger that catches its own entries is the self-reference defect
            # this fleet has already paid for -- a ledger test caught its own
            # docstring in another lane on the same day this guard was written.
            continue
        candidate = root / name
        if candidate.suffix.lower() in SCANNED_SUFFIXES and candidate.is_file():
            paths.append(candidate)
    return tuple(sorted(paths))


def _qualified(prefix: str) -> bool:
    """Is a declared repository qualifier present earlier on this line?"""
    lowered = prefix.lower()
    return any(name in lowered for name in QUALIFIERS)


def scan_text(text: str, *, held: frozenset[str], path: str) -> list[Finding]:
    """Every citation in one file that names a number the repository lacks."""
    findings: list[Finding] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or _QUOTE.match(line):
            continue
        for match in _REFERENCE.finditer(line):
            if match.group(1) in held:
                continue
            if _qualified(line[: match.start()]):
                continue
            findings.append(Finding(path=path, line=number, number=match.group(1)))
    return findings


def scan(root: Path) -> list[Finding]:
    """Every unresolvable citation in the repository at ``root``."""
    held = local_adr_numbers(root)
    findings: list[Finding] = []
    for path in corpus(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            # A file that cannot be read cannot be cleared. Fail closed.
            raise ReferenceCheckError(f"cannot read {path}") from None
        findings.extend(scan_text(text, held=held, path=str(path.relative_to(root))))
    return sorted(findings)


def load_baseline(root: Path) -> tuple[str, ...]:
    """The declared known-debt set, or an empty set when none is declared."""
    path = root / BASELINE_PATH
    if not path.is_file():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReferenceCheckError(f"cannot read {BASELINE_PATH}: {exc}") from exc
    entries = data.get("known_unresolvable_references")
    if not isinstance(entries, list) or not all(isinstance(e, str) for e in entries):
        raise ReferenceCheckError(
            f"{BASELINE_PATH} needs a list of strings at "
            "'known_unresolvable_references'"
        )
    return tuple(sorted(entries))


def evaluate(root: Path) -> tuple[list[str], list[str]]:
    """Return (new findings, stale baseline entries), both as exact keys."""
    observed = {finding.key() for finding in scan(root)}
    declared = set(load_baseline(root))
    return sorted(observed - declared), sorted(declared - observed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        default=".",
        help="repository to check (default: the current directory)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="list every unresolvable citation and exit 0; makes no claim",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.report:
            findings = scan(root)
            for finding in findings:
                print(finding.key())
            print(f"{len(findings)} unresolvable citation(s) in {root}")
            return 0
        new, stale = evaluate(root)
    except ReferenceCheckError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not new and not stale:
        print(
            "ok: every ADR citation resolves in the repository making it, "
            "or names the repository that owns it"
        )
        return 0
    for key in new:
        print(
            f"{key}: cites a number this repository does not hold; name the "
            "owning repository (dotmac_governance ADR 0031)"
        )
    for key in stale:
        print(
            f"{key}: baseline entry no longer fires; remove it in the change "
            "that repaired it, so retirement is recorded rather than assumed"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
