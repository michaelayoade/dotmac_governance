"""Ordering two version strings, or refusing to.

A `floor` that is never compared is a number somebody typed, and comparing it
needs an order. This module supplies one over a NARROW subset of PEP 440 and
REFUSES everything outside it, rather than guessing.

The subset: a release segment `N(.N)*`, optionally followed by one pre-release
marker `aN`, `bN` or `rcN`. That is exactly the shape the fleet's Kernel
versions take — `0.1.0a98`, `0.1.0a77` — and exactly the shape a floor in a
`RequiredSurface` has ever been written in.

Everything else refuses: an epoch (`1!2.0`), a post-release (`1.0.post1`), a
development release (`1.0.dev3`), a local version (`1.0+abc`), a wildcard, a
constraint operator, a `v` prefix, and free text. The refusal is the point.
`packaging` is not a dependency of this repository, and a hand-rolled parser
that SILENTLY mis-orders `1.0.post1` against `1.0` would turn a floor check
into a coin toss that reports as a comparison. A shape nobody wrote a rule for
is a shape nobody reviewed.

Two properties are asserted rather than assumed, because both are the ones a
naive comparator gets wrong:

- **A pre-release is BELOW its own release.** `0.1.0a98 < 0.1.0`, so declaring
  a floor of `0.1.0` is not satisfied by `0.1.0a98`. A tuple comparison over
  the release segment alone would call them equal.
- **Pre-release numbers order numerically, not lexically.** `0.1.0a98 <
  0.1.0a100`, which a string comparison reverses. That is the comparison this
  fleet actually makes: the Kernel is on its ninety-eighth alpha.
"""

from __future__ import annotations

import re
from typing import Final

__all__ = ["VersionError", "compare_versions", "version_key"]

_VERSION = re.compile(r"^(?P<release>\d+(?:\.\d+)*)(?:(?P<stage>a|b|rc)(?P<n>\d+))?$")

#: `a` < `b` < `rc` < a final release. The final release is `3`, above every
#: marker, which is what makes `0.1.0a98 < 0.1.0` come out right.
_STAGE_ORDER: Final[dict[str | None, int]] = {"a": 0, "b": 1, "rc": 2, None: 3}

#: How many release components are compared. Shorter versions are zero-padded
#: to this, so `0.1` and `0.1.0` are the SAME version rather than two.
_RELEASE_WIDTH: Final = 4


class VersionError(ValueError):
    """The string is not a version this module undertakes to order.

    Raised, never softened into an arbitrary ordering. A comparator that
    invents an answer for an input it does not understand reports a verdict
    over a question it never asked.
    """


def version_key(value: str, where: str) -> tuple[tuple[int, ...], int, int]:
    """A sortable key for one version string, or `VersionError`.

    The key is `(release, stage, pre_release_number)`. `stage` is `3` for a
    final release, so a final release sorts above every pre-release of the same
    release segment, and the pre-release number is compared as an INTEGER.
    """
    raw = value.strip()
    match = _VERSION.fullmatch(raw)
    if match is None:
        raise VersionError(
            f"{where} is {value!r}, which is not a version this can order. The "
            "understood shape is N(.N)* optionally followed by aN, bN or rcN. "
            "An epoch, a post-release, a dev release, a local version, a "
            "constraint operator and a 'v' prefix are all REFUSED rather than "
            "guessed at: a comparator that invents an order for a shape nobody "
            "reviewed turns a floor check into a coin toss that reads as a "
            "comparison"
        )
    parts = [int(part) for part in match.group("release").split(".")]
    if len(parts) > _RELEASE_WIDTH:
        raise VersionError(
            f"{where} is {value!r}, whose release segment has {len(parts)} "
            f"components; this orders at most {_RELEASE_WIDTH}. Refusing to "
            "truncate: a comparison over a prefix of a version is a comparison "
            "of a different version"
        )
    padded = tuple(parts + [0] * (_RELEASE_WIDTH - len(parts)))
    stage = match.group("stage")
    number = int(match.group("n")) if match.group("n") is not None else 0
    return padded, _STAGE_ORDER[stage], number


def compare_versions(left: str, right: str, *, where: str) -> int:
    """`-1`, `0` or `1` for `left` against `right`, or `VersionError`.

    `where` names the comparison so a refusal says which two fields could not
    be ordered rather than merely that something could not be.
    """
    first = version_key(left, f"{where} left operand")
    second = version_key(right, f"{where} right operand")
    if first < second:
        return -1
    if first > second:
        return 1
    return 0
