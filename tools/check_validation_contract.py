#!/usr/bin/env python3
"""Prove that the documented validation commands and CI's cannot diverge.

`AGENTS.md` tells a contributor what to run before pushing.
`.github/workflows/` decides what is actually enforced.
`.dotmac/agent-profile.json` is the list an agent client is handed. Nothing
connected them, so they drifted: the instructions listed an acceptance suite
that Michael owns in CI, and they omitted lint paths CI had gained. Each part
looked correct on its own, which is why no reader noticed.

This validator makes the two halves answer to one declaration,
`.dotmac/validation-contract.json`, and fails when either side moves without
it. Both directions matter and are checked separately: an undeclared command
appearing on a side is a different defect from a declared command vanishing
from it, and a guard that checks only one of them is the original defect in a
new place.

Commands are compared by INVOCATION KEY rather than by argv text, because the
same validator is spelled differently in different places -- CI reaches
`standards_control` through a composite action's launcher script. A key is the
module or script being run plus its subcommand, so arguments may differ between
the documentation and the workflow while the identity being compared stays
exact.

The validator is deliberately callable against a temporary directory so its
known-bad controls can prove that they fail, rather than merely asserting that
the production tree passes.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTRACT_PATH = Path(".dotmac/validation-contract.json")
INSTRUCTIONS_PATH = Path("AGENTS.md")
#: The SIXTH copy of the command list, and the one this guard originally
#: missed. `agent_control` checks that the paths a command names exist; nothing
#: checked that the list itself still matched the instructions, so a command
#: could be dropped from the profile — the list an agent is told to run —
#: while remaining in `AGENTS.md` and in CI. Reconciling five of six places
#: leaves the sixth free to disagree, which is the original defect standing in
#: a file nobody re-read.
PROFILE_PATH = Path(".dotmac/agent-profile.json")
WORKFLOW_GLOB = ".github/workflows/*.yml"
ACTION_GLOB = ".github/actions/*/action.yml"
DOC_GLOB = "**/*.md"

INSTRUCTIONS_SECTION = "## Required workflow"

LOCAL = "local"
CI_OWNED = "ci-owned"
CLASSES = frozenset({LOCAL, CI_OWNED})

_FENCE = re.compile(r"^\s*```")
_HEADING = re.compile(r"^## ")
_SUBCOMMAND = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")


class ContractError(Exception):
    """The contract itself could not be read. Nothing else can be checked."""


def _invocation_key(line: str) -> str | None:
    """Return the invocation key of a shell line, or None if it runs no python3.

    The key is the module (``-m pkg``) or the script's basename, plus the next
    token when that token is not an option. ``python3 -m ruff format --check``
    keys as ``ruff format``; ``python3 tools/check_adrs.py`` keys as
    ``check_adrs.py``.

    A line that plainly invokes python3 but cannot be tokenised raises rather
    than being skipped: an unparseable command is an unmonitored command, and
    silently ignoring one is how a guard stops measuring anything.
    """
    if "python3" not in line:
        return None

    try:
        tokens = shlex.split(line, comments=False, posix=True)
    except ValueError:
        try:
            tokens = shlex.split(line, comments=False, posix=False)
        except ValueError as error:
            raise ContractError(
                f"a line invoking python3 could not be tokenised: {line.strip()!r} ({error})"
            ) from error

    index: int | None = None
    for position, token in enumerate(tokens):
        # `$(python3` and `"…/python3"` both end with the interpreter name.
        if (
            token == "python3"
            or token.endswith("/python3")
            or token.endswith("(python3")
        ):
            index = position
            break
    if index is None:
        return None

    rest = tokens[index + 1 :]
    if not rest:
        raise ContractError(f"python3 invoked with no arguments: {line.strip()!r}")

    if rest[0] == "-m":
        if len(rest) < 2:
            raise ContractError(f"`python3 -m` with no module: {line.strip()!r}")
        head, tail = rest[1], rest[2:]
    elif rest[0] == "-":
        # A script on standard input. Whatever follows is redirection, not a
        # subcommand, so the key is the bare interpreter form.
        return "-"
    else:
        head, tail = Path(rest[0].strip("\"'")).name, rest[1:]

    # Only a bare word is a subcommand. An option, a redirection or a pipe is
    # not, and reading one as a subcommand would invent keys that no
    # declaration can ever match.
    if tail and _SUBCOMMAND.fullmatch(tail[0]):
        return f"{head} {tail[0]}"
    return head


def _join_continuations(lines: list[str]) -> list[str]:
    """Join shell continuation lines so one command is one line."""
    joined: list[str] = []
    buffer = ""
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.rstrip().endswith("\\"):
            buffer += stripped.rstrip()[:-1] + " "
            continue
        joined.append(buffer + stripped)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _keys_in_text(text: str) -> set[str]:
    """Every invocation key appearing in a block of shell-bearing text."""
    keys: set[str] = set()
    for line in _join_continuations(text.splitlines()):
        key = _invocation_key(line)
        if key is not None:
            keys.add(key)
    return keys


def _fenced_lines(text: str) -> list[str]:
    """Return the lines inside fenced code blocks only.

    Prose that mentions a command is describing it; a fenced block is telling a
    reader to run it. Scoping the sweep below to fences is what keeps this from
    becoming a prose scanner, which cannot tell an instruction from a
    description of one and decays into an exception list.
    """
    body: list[str] = []
    inside = False
    for line in text.splitlines():
        if _FENCE.match(line):
            inside = not inside
            continue
        if inside:
            body.append(line)
    return body


def _stray_acceptance_instructions(root: Path, classes: dict[str, str]) -> list[str]:
    """Fail when a CI-owned command is written as a runnable step anywhere in docs.

    The instructions were only one of FIVE places that listed these commands.
    Reconciling the one the guard reads would leave the other copies free to
    tell a contributor to run the acceptance suite locally, which is the same
    defect standing in a different file.
    """
    errors: list[str] = []
    ci_owned = {key for key, value in classes.items() if value == CI_OWNED}
    for path in sorted(root.glob(DOC_GLOB)):
        if any(part in {".git", "worktrees"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in _join_continuations(_fenced_lines(text)):
            try:
                key = _invocation_key(line)
            except ContractError as error:
                errors.append(f"{path.relative_to(root)}: {error}")
                continue
            if key is not None and key in ci_owned:
                errors.append(
                    f"{path.relative_to(root)}: gives {key!r} as a runnable step, "
                    f"but {CONTRACT_PATH} classes it {CI_OWNED!r}. Reference the "
                    "command in prose if it must be named; do not put it in a "
                    "block a contributor will copy."
                )
    return errors


def _instructions_block(root: Path) -> str:
    """Return the fenced command block under the instructions' required workflow.

    Scoping to that one block is deliberate: prose elsewhere in `AGENTS.md` may
    mention a command while describing it, and a scanner that cannot tell a
    documented requirement from a description of one decays into an exception
    list.
    """
    path = root / INSTRUCTIONS_PATH
    if not path.is_file():
        raise ContractError(f"{INSTRUCTIONS_PATH} does not exist")

    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(
            index
            for index, line in enumerate(lines)
            if line.strip() == INSTRUCTIONS_SECTION
        )
    except StopIteration:
        raise ContractError(
            f"{INSTRUCTIONS_PATH} has no {INSTRUCTIONS_SECTION!r} section"
        ) from None

    body: list[str] = []
    inside = False
    for line in lines[start + 1 :]:
        if _HEADING.match(line) and not inside:
            break
        if _FENCE.match(line):
            if inside:
                return "\n".join(body)
            inside = True
            continue
        if inside:
            body.append(line)

    raise ContractError(
        f"{INSTRUCTIONS_PATH}: no closed command block under {INSTRUCTIONS_SECTION!r}"
    )


def _profile_keys(root: Path) -> set[str]:
    """Every invocation key in the agent profile's `validation_commands`.

    The profile is what an agent client is handed as "the commands to run", so
    a profile that has fallen behind the instructions does not produce a
    disagreement anyone sees — it produces an agent quietly running a smaller
    set than the repository requires.
    """
    path = root / PROFILE_PATH
    if not path.is_file():
        raise ContractError(f"{PROFILE_PATH} does not exist")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContractError(f"{PROFILE_PATH} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ContractError(f"{PROFILE_PATH} must contain an object")
    commands = data.get("validation_commands")
    if not isinstance(commands, list) or not commands:
        raise ContractError(
            f"{PROFILE_PATH}: validation_commands must be a non-empty list; a profile "
            "listing no command would make this comparison pass over an empty set"
        )
    keys: set[str] = set()
    for command in commands:
        if not isinstance(command, str):
            raise ContractError(
                f"{PROFILE_PATH}: each validation command must be a string"
            )
        key = _invocation_key(command)
        if key is not None:
            keys.add(key)
    return keys


def _ci_text(root: Path) -> str:
    """Every workflow and composite action, concatenated.

    Composite actions are included because that is where the conformance check
    actually runs. A scanner reading only `workflows/` would report the
    standards check as unenforced, and the obvious repair -- excusing it --
    would be an exemption with no premise.
    """
    paths = sorted(root.glob(WORKFLOW_GLOB)) + sorted(root.glob(ACTION_GLOB))
    if not paths:
        raise ContractError(
            "no workflow or composite action found; refusing to report success"
        )
    return "\n".join(path.read_text(encoding="utf-8") for path in paths)


def _load_contract(root: Path) -> tuple[dict[str, str], dict[str, str], set[str]]:
    """Return (key-or-alias -> canonical key), (canonical key -> class), setup keys."""
    path = root / CONTRACT_PATH
    if not path.is_file():
        raise ContractError(f"{CONTRACT_PATH} does not exist")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContractError(f"{CONTRACT_PATH} is not valid JSON: {error}") from error
    if not isinstance(data, dict):
        raise ContractError(f"{CONTRACT_PATH} must contain an object")
    if data.get("schema_version") != 1:
        raise ContractError(
            f"{CONTRACT_PATH}: schema_version must be 1, "
            f"found {data.get('schema_version')!r}"
        )

    resolve: dict[str, str] = {}
    classes: dict[str, str] = {}
    entries = data.get("commands")
    if not isinstance(entries, list) or not entries:
        raise ContractError(f"{CONTRACT_PATH}: commands must be a non-empty list")

    for entry in entries:
        if not isinstance(entry, dict):
            raise ContractError(f"{CONTRACT_PATH}: each command must be an object")
        key = entry.get("key")
        klass = entry.get("class")
        reason = entry.get("reason")
        if not isinstance(key, str) or not key.strip():
            raise ContractError(f"{CONTRACT_PATH}: a command has no key")
        if klass not in CLASSES:
            raise ContractError(
                f"{CONTRACT_PATH}: command {key!r} has class {klass!r}; "
                f"expected one of {', '.join(sorted(CLASSES))}"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError(
                f"{CONTRACT_PATH}: command {key!r} has no reason; a classification "
                "without a stated premise is not enforceable"
            )
        if key in classes:
            raise ContractError(f"{CONTRACT_PATH}: duplicate command key {key!r}")
        classes[key] = klass

        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list):
            raise ContractError(
                f"{CONTRACT_PATH}: command {key!r} aliases must be a list"
            )
        for name in [key, *aliases]:
            if not isinstance(name, str) or not name.strip():
                raise ContractError(
                    f"{CONTRACT_PATH}: command {key!r} has an empty alias"
                )
            if name in resolve and resolve[name] != key:
                raise ContractError(
                    f"{CONTRACT_PATH}: {name!r} resolves to both "
                    f"{resolve[name]!r} and {key!r}"
                )
            resolve[name] = key

    setup: set[str] = set()
    for entry in data.get("setup_commands", []):
        if not isinstance(entry, dict):
            raise ContractError(
                f"{CONTRACT_PATH}: each setup command must be an object"
            )
        key = entry.get("key")
        reason = entry.get("reason")
        if not isinstance(key, str) or not key.strip():
            raise ContractError(f"{CONTRACT_PATH}: a setup command has no key")
        if not isinstance(reason, str) or not reason.strip():
            raise ContractError(
                f"{CONTRACT_PATH}: setup command {key!r} has no reason; an exclusion "
                "without a stated premise is an unmonitored region, not an exemption"
            )
        if key in classes:
            raise ContractError(
                f"{CONTRACT_PATH}: {key!r} is declared both as a validator and as setup"
            )
        setup.add(key)

    if not any(value == LOCAL for value in classes.values()):
        raise ContractError(
            f"{CONTRACT_PATH}: no command is classed {LOCAL!r}; the local half of "
            "the comparison would pass over an empty set"
        )
    if not any(value == CI_OWNED for value in classes.values()):
        raise ContractError(
            f"{CONTRACT_PATH}: no command is classed {CI_OWNED!r}; the rule this "
            "guard exists to enforce would have nothing to bite on"
        )

    return resolve, classes, setup


def validate_validation_contract(root: Path) -> list[str]:
    """Return every divergence between the contract, the instructions and CI."""
    try:
        resolve, classes, setup = _load_contract(root)
        documented_raw = _keys_in_text(_instructions_block(root))
        enforced_raw = _keys_in_text(_ci_text(root))
        profile_raw = _profile_keys(root)
    except ContractError as error:
        return [str(error)]

    errors: list[str] = []
    documented = {resolve.get(key, key) for key in documented_raw}
    enforced = {resolve.get(key, key) for key in enforced_raw}
    profiled = {resolve.get(key, key) for key in profile_raw}
    local_keys = {key for key, value in classes.items() if value == LOCAL}

    # Instructions -> contract. An undeclared command in the instructions is a
    # command nobody classified, which is how an acceptance test gets
    # documented as a local step.
    for key in sorted(documented - set(classes)):
        errors.append(
            f"{INSTRUCTIONS_PATH}: documents {key!r}, which {CONTRACT_PATH} does "
            "not declare"
        )
    for key in sorted(documented & set(classes)):
        if classes[key] != LOCAL:
            errors.append(
                f"{INSTRUCTIONS_PATH}: documents {key!r} as a local step, but "
                f"{CONTRACT_PATH} classes it {classes[key]!r}; acceptance tests are "
                "owned by CI and a local run of one is not evidence"
            )

    # Contract -> instructions. A local command that stops being documented is
    # a check contributors quietly stop running.
    for key in sorted(local_keys - documented):
        errors.append(
            f"{INSTRUCTIONS_PATH}: does not document {key!r}, which "
            f"{CONTRACT_PATH} classes {LOCAL!r}"
        )

    # CI -> contract. A workflow step nobody declared is an unreviewed change
    # to what the repository enforces.
    for key in sorted(enforced - set(classes) - setup):
        errors.append(
            f"CI runs {key!r}, which {CONTRACT_PATH} declares neither as a "
            "validator nor as setup"
        )

    # Contract -> CI. This is the half that catches a documented command CI
    # never actually runs, which is a check that exists only in prose.
    for key in sorted(set(classes) - enforced):
        errors.append(
            f"CI does not run {key!r}, which {CONTRACT_PATH} declares as a "
            f"{classes[key]!r} command"
        )

    # Profile <-> instructions, both directions. The profile is the list an
    # agent client is handed, so a divergence here is an agent running a
    # different set from the one the repository documents -- silently, because
    # both files look correct on their own. That is the original defect, and
    # reconciling five of six copies would have left it in the sixth.
    for key in sorted(profiled - documented):
        errors.append(
            f"{PROFILE_PATH}: lists {key!r}, which {INSTRUCTIONS_PATH} does not "
            "document as a local step"
        )
    for key in sorted(documented - profiled):
        errors.append(
            f"{PROFILE_PATH}: does not list {key!r}, which {INSTRUCTIONS_PATH} "
            "documents as a local step"
        )
    for key in sorted(profiled & set(classes)):
        if classes[key] != LOCAL:
            errors.append(
                f"{PROFILE_PATH}: lists {key!r}, but {CONTRACT_PATH} classes it "
                f"{classes[key]!r}; the profile must never hand an agent a CI-owned "
                "command to run"
            )

    # Every other document. See the function's docstring for why one
    # reconciled file is not enough.
    errors.extend(_stray_acceptance_instructions(root, classes))

    return errors


def main() -> int:
    errors = validate_validation_contract(REPO_ROOT)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        "ok: the documented validation commands, the declared contract, the agent "
        "profile and the commands CI enforces agree in both directions"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
