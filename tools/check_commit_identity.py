#!/usr/bin/env python3
"""Refuse an AI identity or attribution trailer on a pull request's own commits.

A commit's author and committer are the repository's record of who did the
work. A model is not a who: it holds no account, cannot be asked what it
intended, and cannot be the person an approver is attesting against under
`AGENTS.md`. An AI identity in either field silently converts an attributable
change into an unattributable one, and Git preserves that forever — a commit's
identity is part of its hash, so the only repair after the fact is a history
rewrite.

The failure is a configuration accident, not a decision. A local
`user.email` override in one clone puts that identity on every commit made from
it, across every repository that clone touches, until somebody reads a `git log`
carefully. Nothing in the ordinary review path shows it: the diff is right, the
message is right, CI is green, and the author line is the one field a reviewer
never checks.

## Scope, and why it is the pull request's own commits

The guard reads `head --not base` — the commits this branch adds — and nothing
else. That is a deliberate limit rather than a convenience:

- History cannot be repaired by a gate. Rewriting a shared branch to fix an
  author line is a far larger hazard than the wrong author line, so a guard
  over history would either be permanently red or immediately disabled, and a
  disabled guard measures nothing.
- The property this control can actually hold is "nothing NEW arrives wrong",
  and that is the property it claims. It does not claim the history is clean.

## Fail closed

If the range cannot be established the guard **errors**. Not warns, not skips.
A guard that goes green when it cannot determine what to inspect reports a
colour it did not earn, and it does so exactly when something is unusual — a
shallow clone, a missing base, a detached checkout — which is when it is most
needed.

An *established* range that happens to be **empty** is a different thing and is
reported differently: `not_applicable`, with the reason. Conflating "there were
no commits to check" with "the commits checked were clean" is the same defect in
the other direction.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gate_control.contracts import (  # noqa: E402
    NO_TESTS_EXECUTED,
    GateVerdict,
)

#: Email domains that identify a model vendor rather than a person. Matched on
#: the domain and its subdomains, so a new `*.anthropic.com` address does not
#: need a new entry.
PROHIBITED_EMAIL_DOMAINS = (
    "anthropic.com",
    "openai.com",
)

#: Exact addresses that are not covered by a vendor domain. `noreply@anthropic.com`
#: is already caught above and is repeated nowhere; these are the shapes that
#: reach a repository through a forge account instead.
PROHIBITED_EMAIL_PATTERNS = (
    re.compile(r"(?i)^claude(?:-code|-bot)?@"),
    re.compile(r"(?i)^codex(?:-bot)?@"),
    re.compile(r"(?i)^devin(?:-ai)?(?:-bot)?@"),
    re.compile(r"(?i)^(?:aider|cursor)(?:-bot)?@"),
    re.compile(r"(?i)^copilot(?:-swe-agent)?(?:\[bot\])?@"),
    re.compile(r"(?i)\bclaude\b.*@users\.noreply\.github\.com$"),
)

#: Display names that name a model or an assistant product. Word-bounded, so a
#: person called Claudia or Codexis is not caught by a substring.
PROHIBITED_NAME_PATTERNS = (
    re.compile(r"(?i)\bclaude\b"),
    re.compile(r"(?i)\banthropic\b"),
    re.compile(r"(?i)\bopen ?ai\b"),
    re.compile(r"(?i)\bcodex\b"),
    re.compile(r"(?i)\bgithub copilot\b"),
    re.compile(r"(?i)\bdevin\b"),
    re.compile(r"(?i)\b(?:opus|sonnet|haiku)\b"),
    re.compile(r"(?i)\bgpt-?\d"),
)

#: Trailer keys that are refused outright.
#:
#: `Co-Authored-By` is refused in full rather than only when its value names a
#: model. That is Michael's standing rule, and it is also the only version of
#: the rule that can be enforced: a co-author line is free text, so a check that
#: inspected the value would be a check on how the value was spelled. A genuine
#: second human author is recorded in the pull request, where it is attributable
#: to an account.
PROHIBITED_TRAILER_KEYS = frozenset(
    {
        "co-authored-by",
        "co-committed-by",
        "assisted-by",
        "generated-by",
        "ai-assisted",
        "claude-session",
        "codex-session",
    }
)

#: Attribution that arrives as prose rather than as a trailer. The generated
#: footer is the common one, and it carries no colon, so the trailer scan above
#: cannot see it.
PROHIBITED_BODY_PATTERNS = (
    re.compile(r"(?i)generated with \[?claude code\]?"),
    re.compile(r"(?i)\bco-?authored\s+by\s+claude\b"),
    re.compile(r"(?i)\bwritten by (?:claude|chatgpt|codex|an? ai)\b"),
)

_TRAILER = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9-]*)\s*:\s*(?P<value>.*\S)\s*$")
#: The record separator. A commit message may contain any line, so the
#: separator has to be something Git will never emit inside one.
_RECORD = "\x1e"
_FIELD = "\x1f"


class RangeError(Exception):
    """The commit range could not be established. Nothing may be concluded."""


@dataclass(frozen=True)
class Commit:
    """One commit's identity fields and message."""

    sha: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    message: str


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def _resolve(root: Path, ref: str, label: str) -> str:
    if not ref.strip():
        raise RangeError(
            f"no {label} ref was supplied, so the pull request's commit range cannot "
            "be established; refusing to report success"
        )
    if set(ref.strip()) == {"0"}:
        raise RangeError(
            f"the {label} ref is the all-zero SHA, which names no commit (a newly "
            "created branch or a deleted ref); the range cannot be established, so "
            "this is an error rather than an empty range"
        )
    found = _git(root, "rev-parse", "--verify", "--quiet", f"{ref.strip()}^{{commit}}")
    if found.returncode != 0 or not found.stdout.strip():
        raise RangeError(
            f"the {label} ref {ref.strip()!r} does not resolve to a commit in this "
            "checkout (a shallow clone is the usual cause); refusing to report success"
        )
    return found.stdout.strip()


def commit_range(root: Path, base: str, head: str) -> list[Commit]:
    """Return the commits `head` adds over `base`, or raise.

    `head --not base` rather than `base..head` spelled differently: they are the
    same set, and the point of stating it this way is that a commit already
    reachable from the base branch is out of scope. This repository requires
    linear history, so a branch is rebased rather than merged and the set is
    exactly the branch's own work.
    """
    if not (root / ".git").exists() and _git(root, "rev-parse", "--git-dir").returncode:
        raise RangeError(
            f"{root} is not a Git repository, so no commit range exists; refusing to "
            "report success"
        )
    base_sha = _resolve(root, base, "base")
    head_sha = _resolve(root, head, "head")

    template = _FIELD.join(["%H", "%an", "%ae", "%cn", "%ce", "%B"]) + _RECORD
    listed = _git(root, "log", f"--format={template}", head_sha, "--not", base_sha)
    if listed.returncode != 0:
        raise RangeError(
            f"could not list commits in {base_sha[:12]}..{head_sha[:12]}: "
            f"{listed.stderr.strip()}; refusing to report success"
        )

    commits: list[Commit] = []
    for record in listed.stdout.split(_RECORD):
        if not record.strip():
            continue
        fields = record.lstrip("\n").split(_FIELD)
        if len(fields) != 6:
            raise RangeError(
                "a commit record could not be parsed, so the range is incomplete; "
                "refusing to report success"
            )
        commits.append(
            Commit(
                sha=fields[0],
                author_name=fields[1],
                author_email=fields[2],
                committer_name=fields[3],
                committer_email=fields[4],
                message=fields[5],
            )
        )
    return commits


def _email_is_prohibited(email: str) -> str | None:
    address = email.strip().lower()
    if not address:
        return None
    domain = address.rpartition("@")[2]
    for prohibited in PROHIBITED_EMAIL_DOMAINS:
        if domain == prohibited or domain.endswith(f".{prohibited}"):
            return f"the vendor domain {prohibited!r}"
    for pattern in PROHIBITED_EMAIL_PATTERNS:
        if pattern.search(address):
            return "an assistant account address"
    return None


def _name_is_prohibited(name: str) -> str | None:
    for pattern in PROHIBITED_NAME_PATTERNS:
        if pattern.search(name):
            return "a model or assistant product name"
    return None


def _check_identity(commit: Commit, errors: list[str]) -> None:
    """Both roles, separately.

    Author and committer are distinct fields and drift apart routinely — a
    rebase, a cherry-pick or a squash rewrites the committer and preserves the
    author. Checking one of them catches roughly half of the ways the wrong
    identity arrives.
    """
    for role, name, email in (
        ("author", commit.author_name, commit.author_email),
        ("committer", commit.committer_name, commit.committer_email),
    ):
        reason = _email_is_prohibited(email)
        if reason is not None:
            errors.append(
                f"{commit.sha[:12]}: {role} email {email!r} is {reason}. A commit's "
                "identity records who did the work, and a model is not a who. Set "
                "`git config user.email` to your own address and amend or rebase "
                "before pushing."
            )
        reason = _name_is_prohibited(name)
        if reason is not None:
            errors.append(
                f"{commit.sha[:12]}: {role} name {name!r} is {reason}. Use the human "
                "who is accountable for the change."
            )


def _check_message(commit: Commit, errors: list[str]) -> None:
    for line in commit.message.splitlines():
        match = _TRAILER.match(line.strip())
        if match is not None:
            key = match.group("key").lower()
            if key in PROHIBITED_TRAILER_KEYS:
                errors.append(
                    f"{commit.sha[:12]}: message carries a {match.group('key')!r} "
                    "trailer. No AI attribution trailer goes on a commit — a genuine "
                    "second human author belongs in the pull request, where it is "
                    "attributable to an account."
                )
    for pattern in PROHIBITED_BODY_PATTERNS:
        found = pattern.search(commit.message)
        if found is not None:
            errors.append(
                f"{commit.sha[:12]}: message carries AI attribution as prose "
                f"({found.group(0)!r}). It is refused wherever it appears, not only "
                "as a trailer."
            )


def validate_commits(root: Path, base: str, head: str) -> tuple[GateVerdict, list[str]]:
    """Return the guard's verdict over the commits `head` adds to `base`."""
    try:
        commits = commit_range(root, base, head)
    except RangeError as error:
        return GateVerdict.EXECUTED_FAILED, [str(error)]

    if not commits:
        # An ESTABLISHED but empty range. Distinct from the failure above: the
        # range was determined and contains nothing, so there is nothing to
        # claim about it either way.
        return GateVerdict.NOT_APPLICABLE, []

    errors: list[str] = []
    for commit in commits:
        _check_identity(commit, errors)
        _check_message(commit, errors)
    if errors:
        return GateVerdict.EXECUTED_FAILED, errors
    return GateVerdict.EXECUTED_PASSED, []


def _argument(args: list[str], flag: str, fallback: str) -> str:
    if flag in args:
        position = args.index(flag) + 1
        if position < len(args):
            return args[position]
        return ""
    return fallback


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    base = _argument(args, "--base", os.environ.get("COMMIT_IDENTITY_BASE", ""))
    head = _argument(args, "--head", os.environ.get("COMMIT_IDENTITY_HEAD", "HEAD"))

    verdict, errors = validate_commits(REPO_ROOT, base, head)
    if verdict is GateVerdict.EXECUTED_FAILED:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if verdict is GateVerdict.NOT_APPLICABLE:
        print(
            f"{verdict.value}: {NO_TESTS_EXECUTED} — the commit range was established "
            "and is empty, so no commit identity was inspected."
        )
        return 0
    checked = len(commit_range(REPO_ROOT, base, head))
    print(
        f"{verdict.value}: {checked} new commit(s) carry an accountable author and "
        "committer and no AI attribution trailer"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
