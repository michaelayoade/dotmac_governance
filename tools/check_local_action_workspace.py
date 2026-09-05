#!/usr/bin/env python3
"""Refuse a local action loaded from a workspace root a caller-supplied ref owns.

## The rule, and nothing wider

    A workflow job that checks out a CALLER-SUPPLIED ref into the workspace
    ROOT must not afterwards load a local action (`uses: ./...`).

`./...` resolves against `$GITHUB_WORKSPACE`. A local action is therefore this
repository's own code at this commit ONLY while the workspace root holds this
commit. Where a job has checked out a ref the dispatcher chose, the root holds
that ref, and `uses: ./...` runs the dispatched ref's code -- in a job that may
hold secrets, before anything has looked at it.

## What this does NOT cover, stated here because a narrow check read as a broad
## one is worse than no check

Three adjacent exposures are real, are NOT observed by anything in this file,
and are not made safer by it. They are named in `NOT_COVERED` so the boundary
is data rather than a comment, printed on success so a reader of CI output
sees it, and repeated in `dotmac_governance` ADR 0044:

- **Scripts invoked by `run:` steps.** `run: python work/scripts/x.py` and
  `run: ./script.sh` are shell text. This module does not read `run:` bodies,
  so a job that never loads a local action and executes an untrusted script
  every step is SILENT here.
- **Poetry and other plugins.** A `requires-plugins` table, a plugin installed
  into the resolver's own environment, or any plugin mechanism that executes
  code during a tool's own start-up is invisible to a `uses:` scan.
- **Package build backends run during dependency resolution.** A candidate with
  no wheel metadata has its build backend executed by the resolver. That is the
  exposure `poetry install` already carries in CI. Nothing here reduces it.

A job that passes this check has established ONE property. It has not been
shown to be safe to hand a credential.

## Provenance -- ported, not invented (`dotmac_starter_mt` AGENTS.md rule 22)

Owner: `dotmac_governance`. Contract: this module's `scan`/`scan_text` and the
`Finding` shape. Consumers: this repository's own CI only; propagation to the
enrolled estate is `docs/open-decisions.md` decision 51 and is undecided, so
every other enrolled repository is an UNMONITORED region rather than a covered
one.

Source: `michaelayoade/dotmac_platform_control_plane` at `origin/main`
`522e2b0f702b529ea9a155daf2731bd4c1a95d57` --
`tests/architecture/test_kernel_lock_workflow.py`
(`test_the_trusted_checkout_comes_first_and_owns_the_workspace_root`,
`test_no_local_action_runs_before_the_trusted_checkout`),
`tests/architecture/test_workflow_action_pinning.py` (the amended docstring
stating the premise behind the local-action exemption), and
`.github/workflows/kernel-lock.yml` (the subject: the pre-repair shape and the
two-checkout repair). `dotmac_governance` has no `EXTRACTION.toml`; this
docstring and ADR 0044 are where the provenance is recorded.

Two things were generalised in the port, and both are widenings of the SUBJECT
rather than of the CLAIM. Platform asserted a shape for one named file with one
job; this scans every workflow, per JOB, because a workspace is a job's. And
Platform's `inputs.ref` is one member of a declared set of caller-controlled
expressions (`CALLER_CONTROLLED`).

## Why textual, and not a YAML parse

`requirements-dev.txt` pins `mypy` and `ruff` and nothing else, so CI has no
YAML parser. Platform declined the same dependency for the same reason. The
cost is a hand-rolled parser, and a hand-rolled parser that silently returns
nothing makes every assertion built on it pass -- so `tests/
test_check_local_action_workspace.py` proves the parser finds this
repository's own jobs and steps before it proves anything about findings.

The validator is deliberately callable against a temporary directory so its
known-bad controls can prove that they fail, rather than merely asserting that
the production tree passes.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")

#: The families this check does not observe. Data, not prose, so a test can
#: require the boundary to be stated and the success message can carry it.
NOT_COVERED = (
    "scripts invoked by `run:` steps",
    "Poetry and other plugins",
    "package build backends executed during dependency resolution",
)

#: Expression prefixes whose value the DISPATCHER or the event's author
#: chooses. Closed and declared: an expression outside this set is not treated
#: as caller-supplied, so widening the rule is a visible edit rather than a
#: regex accident.
#:
#: `github.sha`, `github.ref` and a literal branch name are deliberately
#: ABSENT. Those are the event's own ref, which is the repaired shape's trusted
#: root -- treating them as caller-supplied would fire on every workflow in the
#: fleet and the check would be switched off within a day.
CALLER_CONTROLLED = (
    "inputs.",
    "github.event.inputs.",
    "github.event.client_payload.",
    "github.event.pull_request.head.",
    "github.head_ref",
    "github.event.workflow_run.head_",
)

#: `path:` values that still mean the workspace root.
ROOT_PATHS = frozenset({"", ".", "./"})

_USES = re.compile(r"^uses:\s*(?P<value>[^\s#]+)")
_KEY = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_-]*):\s*(?P<value>.*?)\s*$")
_CHECKOUT = re.compile(r"(?:^|/)checkout(?:@|$)")


class WorkspaceCheckError(Exception):
    """The check could not be performed. Nothing about the tree is claimed."""


@dataclass(frozen=True, order=True)
class Finding:
    """One job whose local action resolves against a caller-supplied root."""

    path: str
    job: str
    action_line: int
    action: str
    checkout_line: int
    ref_expression: str

    def key(self) -> str:
        return f"{self.path}:{self.job}:{self.action_line}"

    def message(self) -> str:
        return (
            f"{self.path}: job {self.job!r} checks out a caller-supplied ref "
            f"({self.ref_expression}) into the workspace ROOT at line "
            f"{self.checkout_line}, then loads the local action {self.action!r} "
            f"at line {self.action_line}. `./...` resolves against "
            "$GITHUB_WORKSPACE, so the dispatched ref supplies the code that "
            "runs. Put the trusted commit at the root and check the ref under "
            "resolution out beside it (`path:`)."
        )


@dataclass(frozen=True)
class _Line:
    """A significant line: its number, its indent, and its content."""

    number: int
    indent: int
    text: str


@dataclass(frozen=True)
class Step:
    """One step of one job, reduced to the three keys this check reads."""

    number: int
    uses: str | None
    ref: str | None
    path: str | None


def _significant(text: str) -> list[_Line]:
    """Every line that carries structure: blanks and whole-line comments out."""
    lines: list[_Line] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(_Line(number, len(raw) - len(raw.lstrip(" ")), stripped))
    return lines


def _dash(line: _Line) -> _Line | None:
    """Re-read a `- key: value` list item as a line at the item's key indent."""
    if not line.text.startswith("- "):
        return None
    return _Line(line.number, line.indent + 2, line.text[2:].strip())


def _step_keys(block: list[_Line]) -> Step:
    """Read `uses:`, and `with:`'s `ref:`/`path:`, out of one step's lines.

    `with:` is scoped properly rather than by searching the whole block for a
    `ref:`. A step-level key that happens to be spelled `ref` is not a checkout
    input, and a check that read one would report a job for a key that changes
    nothing about the workspace.
    """
    uses: str | None = None
    ref: str | None = None
    path: str | None = None
    with_indent: int | None = None

    for line in block:
        if with_indent is not None and line.indent <= with_indent:
            with_indent = None

        match = _USES.match(line.text)
        if match is not None and uses is None:
            uses = match.group("value").strip("'\"")
            continue

        key_match = _KEY.match(line.text)
        if key_match is None:
            continue
        key, value = key_match.group("key"), key_match.group("value")

        if key == "with" and not value:
            with_indent = line.indent
            continue
        if with_indent is None:
            continue
        if key == "ref" and ref is None:
            ref = value.strip("'\"")
        elif key == "path" and path is None:
            path = value.strip("'\"")

    return Step(block[0].number, uses, ref, path)


def _steps(lines: list[_Line], start: int, end: int) -> list[Step]:
    """The ordered steps declared by a `steps:` list inside [start, end)."""
    steps: list[Step] = []
    index = start
    while index < end:
        line = lines[index]
        if _KEY.match(line.text) is None or not line.text.startswith("steps:"):
            index += 1
            continue
        item_indent: int | None = None
        cursor = index + 1
        block: list[_Line] = []
        while cursor < end:
            current = lines[cursor]
            if current.indent <= line.indent:
                break
            item = _dash(current)
            if item is not None and (
                item_indent is None or current.indent == item_indent
            ):
                if block:
                    steps.append(_step_keys(block))
                item_indent = current.indent
                block = [item]
            elif block and current.indent > (item_indent or 0):
                block.append(current)
            cursor += 1
        if block:
            steps.append(_step_keys(block))
        index = cursor
    return steps


def _jobs(text: str) -> list[tuple[str, list[Step]]]:
    """Every `jobs:` entry, as (job name, its ordered steps).

    Per JOB, because a workspace belongs to a job. Two jobs in one file have
    two workspaces, and reporting a file because one job checks out a ref while
    a different one loads a local action would be a false positive.
    """
    lines = _significant(text)
    jobs: list[tuple[str, list[Step]]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.indent != 0 or line.text != "jobs:":
            index += 1
            continue
        cursor = index + 1
        job_indent: int | None = None
        while cursor < len(lines) and lines[cursor].indent > 0:
            current = lines[cursor]
            match = _KEY.match(current.text)
            if (
                match is not None
                and not match.group("value")
                and (job_indent is None or current.indent == job_indent)
            ):
                job_indent = current.indent
                end = cursor + 1
                while end < len(lines) and lines[end].indent > current.indent:
                    end += 1
                jobs.append((match.group("key"), _steps(lines, cursor + 1, end)))
                cursor = end
                continue
            cursor += 1
        index = cursor
    return jobs


def _caller_controlled(expression: str | None) -> str | None:
    """The declared prefix a `ref:` value is caller-controlled through, if any."""
    if not expression:
        return None
    for prefix in CALLER_CONTROLLED:
        if prefix in expression:
            return prefix
    return None


def _is_root_checkout(step: Step) -> bool:
    return (
        step.uses is not None
        and not step.uses.startswith("./")
        and _CHECKOUT.search(step.uses.split("@")[0]) is not None
        and (step.path is None or step.path in ROOT_PATHS)
    )


def scan_text(path: str, text: str) -> list[Finding]:
    """Every finding in one workflow file's text."""
    findings: list[Finding] = []
    for job, steps in _jobs(text):
        untrusted: Step | None = None
        prefix = ""
        for step in steps:
            if _is_root_checkout(step):
                found = _caller_controlled(step.ref)
                if found is not None:
                    untrusted, prefix = step, found
                else:
                    # An ordinary checkout takes the root back. The trusted
                    # commit is the workspace again, and a local action after
                    # it is the repaired shape.
                    untrusted = None
                continue
            if untrusted is None or step.uses is None:
                continue
            if step.uses.startswith("./"):
                findings.append(
                    Finding(
                        path=path,
                        job=job,
                        action_line=step.number,
                        action=step.uses,
                        checkout_line=untrusted.number,
                        ref_expression=prefix,
                    )
                )
    return sorted(findings)


def workflow_files(root: Path) -> tuple[Path, ...]:
    """Every file GitHub would run as a workflow.

    BOTH extensions, RECURSIVELY -- GitHub accepts `.yml` and `.yaml`, so a
    scanner reading only `*.yml` one directory deep is bypassed by a perfectly
    valid `.yaml` file. That is a silent hole in a supply-chain guard, and it
    is `dotmac_platform_control_plane`'s own measured lesson, ported.
    """
    directory = root / WORKFLOW_DIR
    if not directory.is_dir():
        raise WorkspaceCheckError(
            f"{WORKFLOW_DIR} does not exist under {root}; refusing to report success"
        )
    files: list[Path] = []
    for suffix in ("yml", "yaml"):
        files += directory.rglob(f"*.{suffix}")
    if not files:
        raise WorkspaceCheckError(
            f"{WORKFLOW_DIR} holds no workflow; refusing to report success"
        )
    return tuple(sorted(set(files)))


def scan(root: Path) -> list[Finding]:
    """Every finding across every workflow under `root`."""
    findings: list[Finding] = []
    for path in workflow_files(root):
        findings += scan_text(
            str(path.relative_to(root)), path.read_text(encoding="utf-8")
        )
    return sorted(findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args(argv)

    try:
        findings = scan(arguments.root)
    except WorkspaceCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if findings:
        for finding in findings:
            print(f"error: {finding.message()}", file=sys.stderr)
        return 1

    print(
        "ok: no workflow job loads a local action from a workspace root that a "
        "caller-supplied ref controls. This says NOTHING about "
        + "; ".join(NOT_COVERED)
        + " -- none of which is observed here."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
