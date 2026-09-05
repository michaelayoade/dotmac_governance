#!/usr/bin/env python3
"""Enforce the authority-cutover receipt registry decided by ADR 0018 § 3.

A receipt exists to be trustworthy after both parties to a cutover are gone, at
which point it cannot be re-derived and nothing can contradict it. Everything
below follows from that one property:

- **Envelopes only.** The registry is published (ADR 0003), so a receipt that
  carried private evidence would make the whole registry unpublishable. A
  receipt therefore *commits* to the product's evidence by digest and, where a
  reader could not otherwise find it, by an approved pointer. A field that is
  neither is refused.
- **Append-only.** An edited receipt is byte-for-byte indistinguishable from an
  accurate one, so a registry that permits editing has the *appearance* of
  durable evidence and none of the property. Corrections add a receipt carrying
  `supersedes_receipt`; they never rewrite one.
- **Bytes, not diff shape.** The append-only arm reads every pre-existing
  receipt's blob out of the merge base and compares it with the working tree.
  Trusting the diff's shape is not that check: a rename plus a rewrite reads as
  an addition, and a delete plus an add reads as two unrelated edits.
- **Fail closed.** If the merge base cannot be established the arm reports an
  error rather than success. A guard that silently passes when it cannot
  determine what to compare against is worse than no guard, because it reports
  a colour.

Non-vacuity is handled explicitly rather than assumed. A validator over an
empty directory passes for the wrong reason, so occupancy is reported as its
own verdict: an empty registry is `not_applicable`, never `executed_passed`.
The verdict vocabulary is `gate_control.contracts`, reused as code so the
repository does not acquire a second set of words for the same distinction;
reuse asserts nothing about ADR 0015's status.

The validator is deliberately callable against a temporary directory so its
known-bad controls can prove that they fail, rather than merely asserting that
the production tree passes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent_control.engine import SENSITIVE_PATTERNS  # noqa: E402
from gate_control.contracts import (  # noqa: E402
    NO_TESTS_EXECUTED,
    GateVerdict,
)

#: Where receipts live. One file per receipt, reviewed in by pull request.
RECEIPT_DIR = Path("receipts")
RECEIPT_SUFFIX = ".json"

#: The envelope's shape is versioned so a change to it is a visible change
#: rather than a silent reinterpretation of every stored receipt.
SCHEMA_VERSION = 1

#: `receipts/README.md` documents the registry and is not a receipt.
NON_RECEIPT_NAMES = frozenset({"README.md"})

REQUIRED_FIELDS = (
    "schema_version",
    "receipt_id",
    "old_authority",
    "new_authority",
    "coordinates",
    "effective_time",
    "runtime_evidence_digest",
    "old_writer_retirement_status",
)
OPTIONAL_FIELDS = (
    "private_evidence_pointer",
    "supersedes_receipt",
)
KNOWN_FIELDS = frozenset(REQUIRED_FIELDS + OPTIONAL_FIELDS)

AUTHORITY_FIELDS = ("system", "resource")
COORDINATE_SIDES = ("old", "new")
COORDINATE_REQUIRED = ("repository", "commit")
COORDINATE_OPTIONAL = ("path", "released_version", "artifact_digest")
COORDINATE_KNOWN = frozenset(COORDINATE_REQUIRED + COORDINATE_OPTIONAL)

RECEIPT_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: A peeled commit. ADR 0013 § 3: a branch name, "latest", an unpeeled tag and
#: an image tag are not coordinates, and none of them matches this.
COMMIT = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
#: RFC 3339 in UTC. A local offset would leave two receipts unorderable
#: without knowing which zone each was written in.
EFFECTIVE_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
#: An approved pointer names a controlled system and an address inside it. The
#: scheme list is closed: an unknown scheme is how a value enters wearing a
#: pointer's punctuation.
POINTER = re.compile(r"^(?:bao|knowledge|github|s3)://[A-Za-z0-9][A-Za-z0-9._/#@:-]*$")

#: The shapes ADR 0013 § 3 names as *not* coordinates, matched so the error can
#: say which one was used rather than only that the value was not 40 hex.
#:
#: `stable` and `edge` were added on 2026-09-05 to match
#: `dotmac-deployment-foundation`'s `_MOVING_REFERENCE`, which names
#: `latest|main|master|HEAD|stable|edge`. Both were ALREADY refused here by the
#: 40-hex rule, so this changes how precisely the refusal names the mistake and
#: not what the registry admits — a message that says only "not 40 hex" leaves
#: the author guessing whether the value was a branch, a tag or a typo.
NON_COORDINATES = (
    (
        re.compile(r"^(?:latest|current|head|main|master|stable|edge)$", re.IGNORECASE),
        "a branch name or floating alias",
    ),
    (
        re.compile(r"^v?\d+(?:\.\d+)*(?:[.-][A-Za-z0-9]+)*$"),
        "an unpeeled tag or version string",
    ),
    (re.compile(r"^[A-Za-z0-9._/-]+:[A-Za-z0-9._-]+$"), "an image tag"),
)

RETIRED = "retired"
TRANSFERRED = "transferred"
STILL_LIVE = "still_live"
#: Rule 2's vocabulary. A status, never a boolean: a receipt is written when
#: authority moves, and at that moment the old writer is usually still live, so
#: a boolean pressures the author into recording a false `retired` to produce a
#: complete-looking receipt — the failure the record exists to prevent.
RETIREMENT_STATUSES = (RETIRED, TRANSFERRED, STILL_LIVE)
#: Each status carries the detail that makes it checkable. Without these a
#: status is an adjective.
RETIREMENT_DETAIL: dict[str, tuple[str, ...]] = {
    RETIRED: ("revision",),
    TRANSFERRED: ("new_owner", "receipt"),
    STILL_LIVE: ("owner", "retirement_condition"),
}
RETIREMENT_KNOWN = frozenset(
    ("status",) + tuple(name for names in RETIREMENT_DETAIL.values() for name in names)
)


class RegistryError(Exception):
    """The registry itself could not be read. Nothing else can be checked."""


def _is_non_empty_str(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _describe_non_coordinate(value: str) -> str | None:
    for pattern, description in NON_COORDINATES:
        if pattern.fullmatch(value):
            return description
    return None


def _check_authority(where: str, name: str, value: object, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(
            f"{where}: {name} must be an object naming a system and a resource"
        )
        return
    unknown = sorted(set(value) - set(AUTHORITY_FIELDS))
    if unknown:
        errors.append(f"{where}: {name} carries unknown field(s) {', '.join(unknown)}")
    for field in AUTHORITY_FIELDS:
        if not _is_non_empty_str(value.get(field)):
            errors.append(
                f"{where}: {name}.{field} is missing; an authority is a system AND the "
                "exact resource whose authority moved, not a repository or host alone"
            )


def _check_coordinate(where: str, side: str, value: object, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{where}: coordinates.{side} must be an object")
        return
    unknown = sorted(set(value) - COORDINATE_KNOWN)
    if unknown:
        errors.append(
            f"{where}: coordinates.{side} carries unknown field(s) {', '.join(unknown)}"
        )
    for field in COORDINATE_REQUIRED:
        if not _is_non_empty_str(value.get(field)):
            errors.append(f"{where}: coordinates.{side}.{field} is missing")

    commit = value.get("commit")
    if isinstance(commit, str) and commit.strip() and not COMMIT.fullmatch(commit):
        described = _describe_non_coordinate(commit.strip())
        detail = f" — that is {described}" if described else ""
        errors.append(
            f"{where}: coordinates.{side}.commit is {commit!r}, which is not a peeled "
            f"40-character commit{detail}. ADR 0013 § 3 refuses a branch name, "
            '"latest", an unpeeled tag and an image tag as coordinates.'
        )

    digest = value.get("artifact_digest")
    if digest is not None and not (
        isinstance(digest, str) and DIGEST.fullmatch(digest)
    ):
        errors.append(
            f"{where}: coordinates.{side}.artifact_digest must be 'sha256:' followed "
            "by 64 hex characters"
        )


def _check_retirement(where: str, value: object, errors: list[str]) -> None:
    if isinstance(value, bool):
        errors.append(
            f"{where}: old_writer_retirement_status is a boolean. It is a status — "
            f"one of {', '.join(RETIREMENT_STATUSES)} — because a boolean pressures the "
            "author into recording a false 'retired' to produce a complete-looking "
            "receipt, which is the failure this record exists to prevent."
        )
        return
    if not isinstance(value, dict):
        errors.append(
            f"{where}: old_writer_retirement_status must be an object carrying a "
            "status and that status's detail"
        )
        return

    unknown = sorted(set(value) - RETIREMENT_KNOWN)
    if unknown:
        errors.append(
            f"{where}: old_writer_retirement_status carries unknown field(s) "
            f"{', '.join(unknown)}"
        )

    status = value.get("status")
    if status is None:
        errors.append(
            f"{where}: old_writer_retirement_status has no status. Absence is not a "
            "status; an item nobody found is unexamined, not retired."
        )
        return
    if not isinstance(status, str) or status not in RETIREMENT_STATUSES:
        errors.append(
            f"{where}: old_writer_retirement_status.status is {status!r}; expected one "
            f"of {', '.join(RETIREMENT_STATUSES)}"
        )
        return

    for field in RETIREMENT_DETAIL[status]:
        if not _is_non_empty_str(value.get(field)):
            errors.append(
                f"{where}: old_writer_retirement_status is {status!r} but names no "
                f"{field}; a status with no detail cannot be checked by anyone"
            )
    revision = value.get("revision")
    if (
        status == RETIRED
        and isinstance(revision, str)
        and revision.strip()
        and not COMMIT.fullmatch(revision)
    ):
        errors.append(
            f"{where}: old_writer_retirement_status.revision is {revision!r}, which is "
            "not a peeled 40-character commit"
        )


def _check_secret_literals(where: str, raw: str, errors: list[str]) -> None:
    """Refuse a receipt carrying anything shaped like a secret.

    The instrument is `agent_control`'s own pattern set, imported rather than
    copied: ADR 0018's drift-prevention names it as the existing detector and
    requires it to cover this directory, and a second copy would be a second
    thing to keep current.
    """
    for code, pattern in SENSITIVE_PATTERNS:
        if pattern.search(raw):
            errors.append(
                f"{where}: possible literal secret found ({code.value}). A receipt "
                "commits to evidence by digest and, where necessary, an approved "
                "pointer. It never inlines a value."
            )


def _check_pointer(where: str, value: object, errors: list[str]) -> None:
    if not _is_non_empty_str(value):
        errors.append(f"{where}: private_evidence_pointer must be a non-empty string")
        return
    assert isinstance(value, str)
    if not POINTER.fullmatch(value.strip()):
        errors.append(
            f"{where}: private_evidence_pointer is {value!r}, which is not an approved "
            "pointer. Give a controlled system's address "
            "(bao://, knowledge://, github://, s3://) — never a value, never a "
            "credential."
        )


def _check_receipt(path: Path, raw: str, errors: list[str]) -> dict[str, Any] | None:
    """Validate one envelope. Returns the parsed receipt, or None if unusable."""
    where = str(RECEIPT_DIR / path.name)
    _check_secret_literals(where, raw, errors)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        errors.append(f"{where}: is not valid JSON: {error}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{where}: must contain a receipt object")
        return None

    unknown = sorted(set(data) - KNOWN_FIELDS)
    if unknown:
        errors.append(
            f"{where}: carries field(s) outside the declared envelope: "
            f"{', '.join(unknown)}. The envelope is closed — a field that is neither "
            "a digest nor an approved pointer does not go in."
        )
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"{where}: required field {field!r} is missing")

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"{where}: schema_version must be {SCHEMA_VERSION}, found "
            f"{data.get('schema_version')!r}"
        )

    receipt_id = data.get("receipt_id")
    expected_id = path.name.removesuffix(RECEIPT_SUFFIX)
    if not _is_non_empty_str(receipt_id):
        errors.append(f"{where}: receipt_id is missing")
    elif not RECEIPT_ID.fullmatch(str(receipt_id)):
        errors.append(
            f"{where}: receipt_id {receipt_id!r} must be lowercase kebab-case"
        )
    elif receipt_id != expected_id:
        errors.append(
            f"{where}: receipt_id is {receipt_id!r} but the filename says "
            f"{expected_id!r}; a receipt addressed by two names cannot be superseded "
            "unambiguously"
        )

    if "old_authority" in data:
        _check_authority(where, "old_authority", data["old_authority"], errors)
    if "new_authority" in data:
        _check_authority(where, "new_authority", data["new_authority"], errors)

    coordinates = data.get("coordinates")
    if coordinates is not None:
        if not isinstance(coordinates, dict):
            errors.append(f"{where}: coordinates must be an object")
        else:
            unknown_sides = sorted(set(coordinates) - set(COORDINATE_SIDES))
            if unknown_sides:
                errors.append(
                    f"{where}: coordinates carries unknown side(s) "
                    f"{', '.join(unknown_sides)}"
                )
            for side in COORDINATE_SIDES:
                if side not in coordinates:
                    errors.append(f"{where}: coordinates.{side} is missing")
                    continue
                _check_coordinate(where, side, coordinates[side], errors)

    effective = data.get("effective_time")
    if effective is not None and not (
        isinstance(effective, str) and EFFECTIVE_TIME.fullmatch(effective)
    ):
        errors.append(
            f"{where}: effective_time is {effective!r}; expected an RFC 3339 UTC "
            "instant such as 2026-08-30T09:15:00Z, recorded by the transaction that "
            "moved authority"
        )

    digest = data.get("runtime_evidence_digest")
    if digest is not None and not (
        isinstance(digest, str) and DIGEST.fullmatch(digest)
    ):
        errors.append(
            f"{where}: runtime_evidence_digest must be 'sha256:' followed by 64 hex "
            "characters. It is a digest over the product-side runtime_observation "
            "artefact, never the artefact."
        )

    if "old_writer_retirement_status" in data:
        _check_retirement(where, data["old_writer_retirement_status"], errors)

    if "private_evidence_pointer" in data:
        _check_pointer(where, data["private_evidence_pointer"], errors)

    supersedes = data.get("supersedes_receipt")
    if supersedes is not None and not _is_non_empty_str(supersedes):
        errors.append(f"{where}: supersedes_receipt must be a non-empty receipt id")

    return data


def _check_supersession(receipts: dict[str, dict[str, Any]], errors: list[str]) -> None:
    """Refuse a dangling, self-referential, cyclic or forked supersession chain."""
    superseded_by: dict[str, list[str]] = {}
    for receipt_id, data in sorted(receipts.items()):
        target = data.get("supersedes_receipt")
        if not _is_non_empty_str(target):
            continue
        assert isinstance(target, str)
        if target == receipt_id:
            errors.append(
                f"{RECEIPT_DIR / (receipt_id + RECEIPT_SUFFIX)}: supersedes itself"
            )
            continue
        if target not in receipts:
            errors.append(
                f"{RECEIPT_DIR / (receipt_id + RECEIPT_SUFFIX)}: supersedes "
                f"{target!r}, which is not a receipt in this registry"
            )
            continue
        superseded_by.setdefault(target, []).append(receipt_id)

    for target, correctors in sorted(superseded_by.items()):
        if len(correctors) > 1:
            errors.append(
                f"{RECEIPT_DIR / (target + RECEIPT_SUFFIX)}: superseded by "
                f"{len(correctors)} receipts ({', '.join(sorted(correctors))}); a "
                "supersession chain with two live heads leaves no single current "
                "receipt, which is the ambiguity supersession exists to remove"
            )

    # A cycle has no head at all. Walk each chain; a repeated node is a cycle.
    for receipt_id in sorted(receipts):
        seen = {receipt_id}
        cursor = receipts[receipt_id].get("supersedes_receipt")
        while (
            _is_non_empty_str(cursor) and isinstance(cursor, str) and cursor in receipts
        ):
            if cursor in seen:
                errors.append(
                    f"{RECEIPT_DIR / (receipt_id + RECEIPT_SUFFIX)}: supersession chain "
                    f"is cyclic through {cursor!r}; a cycle has no current receipt"
                )
                break
            seen.add(cursor)
            cursor = receipts[cursor].get("supersedes_receipt")


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def merge_base(root: Path, base_ref: str) -> str:
    """Resolve the merge base, or raise. There is deliberately no fallback.

    The append-only arm's whole content is "compare against what was already
    there". If it cannot find what was already there it has established
    nothing, and reporting success would be reporting a colour it did not earn.
    """
    if not base_ref.strip():
        raise RegistryError(
            "no base ref was supplied, so the append-only comparison has nothing to "
            "compare against; refusing to report success"
        )
    resolved = _git(root, "rev-parse", "--verify", "--quiet", f"{base_ref}^{{commit}}")
    if resolved.returncode != 0 or not resolved.stdout.strip():
        raise RegistryError(
            f"base ref {base_ref!r} does not resolve to a commit in this checkout "
            "(a shallow clone is the usual cause); refusing to report success"
        )
    found = _git(root, "merge-base", base_ref, "HEAD")
    if found.returncode != 0 or not found.stdout.strip():
        raise RegistryError(
            f"no merge base between {base_ref!r} and HEAD; refusing to report success"
        )
    return found.stdout.strip()


def _receipt_filename(entry: str) -> str | None:
    """Return the receipt filename in a tree entry, or None when it is not one."""
    stripped = entry.strip()
    if not stripped:
        return None
    tail = stripped.rsplit("/", 1)[-1]
    if tail in NON_RECEIPT_NAMES or not tail.endswith(RECEIPT_SUFFIX):
        return None
    return tail


def _receipts_at(root: Path, revision: str) -> dict[str, str]:
    """Every receipt blob at `revision`, keyed by filename."""
    listing = _git(
        root, "ls-tree", "-r", "--name-only", "-z", revision, "--", str(RECEIPT_DIR)
    )
    if listing.returncode != 0:
        raise RegistryError(
            f"could not list {RECEIPT_DIR}/ at {revision}: {listing.stderr.strip()}"
        )
    blobs: dict[str, str] = {}
    for entry in listing.stdout.split("\0"):
        name = _receipt_filename(entry)
        if name is None:
            continue
        show = _git(root, "show", f"{revision}:{entry.strip()}")
        if show.returncode != 0:
            raise RegistryError(f"could not read {entry.strip()} at {revision}")
        blobs[name] = show.stdout
    return blobs


def check_append_only(root: Path, base_ref: str) -> list[str]:
    """Compare every pre-existing receipt's BYTES against the merge base.

    Reading the merge base rather than the diff is the entire point. A rename
    plus a rewrite presents to a diff reader as one deletion and one addition,
    and an addition looks like exactly what this registry is for.
    """
    base = merge_base(root, base_ref)
    errors: list[str] = []
    for name, before in sorted(_receipts_at(root, base).items()):
        current = root / RECEIPT_DIR / name
        if not current.is_file():
            errors.append(
                f"{RECEIPT_DIR / name}: existed at the merge base ({base[:12]}) and is "
                "gone. A receipt is never deleted or renamed; a wrong receipt is "
                "corrected by adding one carrying supersedes_receipt."
            )
            continue
        after = current.read_text(encoding="utf-8")
        if after != before:
            errors.append(
                f"{RECEIPT_DIR / name}: differs from its bytes at the merge base "
                f"({base[:12]}). A receipt is never edited — an edited receipt is "
                "byte-for-byte indistinguishable from an accurate one, so a registry "
                "that permits editing has the appearance of durable evidence and none "
                "of the property. Add a superseding receipt instead."
            )
    return errors


def load_registry(root: Path) -> dict[str, str]:
    """Every receipt file in the registry, keyed by filename."""
    directory = root / RECEIPT_DIR
    if not directory.is_dir():
        raise RegistryError(
            f"{RECEIPT_DIR}/ does not exist; refusing to report success over a "
            "registry that is not there"
        )
    found: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.name in NON_RECEIPT_NAMES:
            continue
        if not path.name.endswith(RECEIPT_SUFFIX):
            raise RegistryError(
                f"{RECEIPT_DIR / path.name}: the registry holds one JSON receipt per "
                "file; an undeclared file here is unvalidated content in a reviewed "
                "store"
            )
        found[path.name] = path.read_text(encoding="utf-8")
    return found


def validate_registry(
    root: Path, base_ref: str | None
) -> tuple[GateVerdict, list[str]]:
    """Return the registry's verdict and every divergence found.

    `base_ref` of None runs the schema arm only, and says so. It is for a
    checkout with no comparable base; it is NOT a way to skip the append-only
    arm in CI, where the base is always supplied and a missing one is an error.
    """
    try:
        files = load_registry(root)
    except RegistryError as error:
        return GateVerdict.EXECUTED_FAILED, [str(error)]

    errors: list[str] = []
    receipts: dict[str, dict[str, Any]] = {}
    for name, raw in sorted(files.items()):
        parsed = _check_receipt(Path(name), raw, errors)
        if parsed is not None:
            receipts[name.removesuffix(RECEIPT_SUFFIX)] = parsed
    _check_supersession(receipts, errors)

    if base_ref is not None:
        try:
            errors.extend(check_append_only(root, base_ref))
        except RegistryError as error:
            errors.append(str(error))

    if errors:
        return GateVerdict.EXECUTED_FAILED, errors

    # Non-vacuity. Everything above is structural, and every structural check
    # over zero receipts holds trivially. Saying `executed_passed` here would
    # claim the registry discipline is evidenced when nothing has been
    # measured, which is the shape this repository refuses everywhere else.
    if not files:
        return GateVerdict.NOT_APPLICABLE, []
    return GateVerdict.EXECUTED_PASSED, []


def _default_base_ref() -> str | None:
    """The base to compare against, from the environment CI actually provides."""
    for name in ("RECEIPT_REGISTRY_BASE", "GITHUB_BASE_REF"):
        value = os.environ.get(name, "").strip()
        if value:
            return value if name == "RECEIPT_REGISTRY_BASE" else f"origin/{value}"
    return None


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    base_ref: str | None
    if "--base" in args:
        position = args.index("--base") + 1
        if position >= len(args):
            print("error: --base needs a ref", file=sys.stderr)
            return 1
        base_ref = args[position]
    elif "--no-base" in args:
        base_ref = None
    else:
        base_ref = _default_base_ref()

    verdict, errors = validate_registry(REPO_ROOT, base_ref)
    if verdict is GateVerdict.EXECUTED_FAILED:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if verdict is GateVerdict.NOT_APPLICABLE:
        print(
            f"{verdict.value}: {NO_TESTS_EXECUTED} — the receipt registry holds no "
            "receipts, so nothing about the append-only or envelope discipline is "
            "claimed. The directory, schema, parser and validator exist; authorizing "
            "the first receipt is open decision 21."
        )
        return 0
    scope = (
        "envelope and supersession"
        if base_ref is None
        else "envelope, supersession and append-only"
    )
    count = len(load_registry(REPO_ROOT))
    print(f"{verdict.value}: {count} receipt(s), {scope} valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
