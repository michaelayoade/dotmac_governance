"""How Governance names the Foundation contract it defers to, and nothing more.

This module is a POINTER. It holds coordinates — a repository, an immutable
revision, a path and a symbol — and it parses nothing, verifies nothing,
canonicalizes nothing and digests nothing. `ApplicationFoundationProfile.v1` is
owned and verified by `dotmac-deployment-foundation`, and importing its bytes
into Governance in any form would be the second verifier the ownership ruling
of 2026-09-05 exists to prevent.

## Why a revision and not a version

The intended end state is a RELEASED-VERSION binding: Governance requires a
published `dotmac-deployment-foundation` and invokes its verifier. That is not
available, and the reason is a fact rather than a preference. Measured
2026-09-05 in `michaelayoade/dotmac_starter_mt`:

- The only Foundation tags are `v0.1.0a1`, `v0.2.0a1` and `v0.2.0a2`. The
  newest peels to `55750e104df3dd94b6f9f70bf8c8db53986394c7`.
- `application_profile.py` is in NONE of them. It was added by
  `22a40d14d93ce5e49a3fd14e63092bb74810716d` on 2026-09-04, after that tag.
- `main` declares `version = "0.4.0a1"`, which
  `docs/inventories/declared-publication-baseline.json` records
  `declared-unpublished` — "unpublished, untagged and not an admissible
  rehearsal or publication coordinate".

So the contract exists only on `main`, in an unreleased package, and there is
no released version to require. ADR 0013 § 3 refuses a claim measured against a
reference that can move, so the binding is made to the immutable commit the
contract's bytes actually live at.

## The one place the swap happens

When a Foundation release carries `application_profile.py`, exactly one literal
below changes: `released_version` stops being `None` and `revision` becomes the
PEELED commit of that release's tag. Nothing else in this repository moves,
which is the property this module exists to provide — the coordinate KIND is
what changes later, not the shape of everything that reads it.

`released_version=None` is a stated absence, never an unstated one:
`requires_release` reports it, and open decision 50 owns the resolution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath

__all__ = [
    "ABANDONED_VERSIONS",
    "FOUNDATION_APPLICATION_PROFILE",
    "AdoptionClaim",
    "AdoptionState",
    "BootstrapOnlyError",
    "ContractBinding",
    "CoordinateError",
]


class CoordinateError(ValueError):
    """A binding was given a coordinate that cannot identify particular bytes."""


class BootstrapOnlyError(ValueError):
    """A revision-bound binding was asked to count as installed or adopted."""


#: Versions that must never be bound, with the reason each was abandoned.
#:
#: `0.4.0a1` is on `dotmac_starter_mt` `main` and is recorded
#: `declared-unpublished` in that repository's
#: `docs/inventories/declared-publication-baseline.json`: "BUILT ONCE;
#: UNRECORDED AND DRIFTED ... unpublished, untagged and not an admissible
#: rehearsal or publication coordinate; it must not be rebuilt or published."
#: A name that appears in a `pyproject.toml` and nowhere else is exactly the
#: shape ADR 0013 § 3 refuses, so it is refused BY NAME here rather than left
#: to be caught by whoever remembers.
#:
#: The replacement waits on a Foundation alpha that is built once, published
#: and verified. Until then this binding stays a bootstrap.
ABANDONED_VERSIONS: dict[str, str] = {
    "0.4.0a1": (
        "declared-unpublished in dotmac_starter_mt's "
        "docs/inventories/declared-publication-baseline.json — built once, "
        "unrecorded and drifted, and not an admissible publication coordinate"
    ),
    "0.3.0a6": "a never-built name",
    "0.3.0a5": "superseded, publishable=false",
}


class AdoptionState(str, Enum):
    """What a binding is being asked to count as.

    `BOOTSTRAP` is the only state a revision-bound binding may hold. The other
    three are claims about a released artifact — that it was installed, that a
    gate admitted it, that a product adopted it — and none of them is decidable
    from a source revision, which is why the refusal below is structural rather
    than a convention.
    """

    BOOTSTRAP = "bootstrap"
    INSTALLED = "installed"
    ADMITTED = "admitted"
    ADOPTED = "adopted"


#: The states a revision-bound binding may never hold. Michael's ruling of
#: 2026-09-05: the immutable source coordinate is permitted "only as a
#: temporary, report-only bootstrap"; it "must never count as installed,
#: admitted, or adopted".
RELEASE_ONLY_STATES: frozenset[AdoptionState] = frozenset(
    {AdoptionState.INSTALLED, AdoptionState.ADMITTED, AdoptionState.ADOPTED}
)


#: A peeled commit, and the only accepted revision shape.
_PEELED_COMMIT = re.compile(r"^[0-9a-f]{40}$")

#: The floating aliases named so a refusal can say WHICH mistake was made.
#: Deliberately the same set as `tools/check_receipts.py`'s `NON_COORDINATES`
#: first arm, and the same set as `dotmac-deployment-foundation`'s
#: `_MOVING_REFERENCE` — `latest|main|master|HEAD|stable|edge`, plus `current`,
#: which this repository's registry already refused. The agreement is asserted
#: by a test rather than trusted, because two lists that must match and are
#: never compared are two lists that will not match.
_MOVING_ALIAS = re.compile(
    r"^(?:latest|current|head|main|master|stable|edge)$", re.IGNORECASE
)


def _require_peeled(value: str, *, field: str) -> str:
    text = value.strip()
    if not text:
        raise CoordinateError(f"{field} may not be empty")
    if _MOVING_ALIAS.fullmatch(text):
        raise CoordinateError(
            f"{field} is {text!r}, which is a branch name or floating alias. "
            "ADR 0013 § 3 refuses it: a reference that can move does not "
            "identify any particular bytes, so a claim measured against it is "
            "not a claim. Use a peeled 40-character commit"
        )
    if not _PEELED_COMMIT.fullmatch(text):
        raise CoordinateError(
            f"{field} is {text!r}, which is not a peeled 40-character commit. "
            "ADR 0013 § 3 refuses a branch name, 'latest', an unpeeled tag and "
            "an image tag as coordinates"
        )
    return text


@dataclass(frozen=True)
class ContractBinding:
    """One externally-owned contract, named by coordinates Governance can cite.

    Validation happens at construction, so an unusable binding cannot sit in
    the tree waiting to be noticed. There is deliberately no `content`,
    `document` or `schema` field: this record says WHERE the contract is, and
    the owning repository says what it means.
    """

    repository: str
    revision: str
    path: PurePosixPath
    symbol: str
    released_version: str | None = None

    def __post_init__(self) -> None:
        if not self.repository.strip():
            raise CoordinateError("repository may not be empty")
        object.__setattr__(
            self, "revision", _require_peeled(self.revision, field="revision")
        )
        if not self.symbol.strip():
            raise CoordinateError("symbol may not be empty")
        if self.released_version is not None:
            text = self.released_version.strip()
            if not text:
                raise CoordinateError(
                    "released_version is blank; state None for 'no release "
                    "exists', because an empty string reads as a release "
                    "nobody named"
                )
            if _MOVING_ALIAS.fullmatch(text):
                raise CoordinateError(
                    f"released_version is {text!r}, which is a floating alias "
                    "rather than a published version"
                )
            abandoned = ABANDONED_VERSIONS.get(text)
            if abandoned is not None:
                raise CoordinateError(
                    f"released_version {text!r} is abandoned: {abandoned}. "
                    "Binding to it would make a published claim out of a name "
                    "that was never published"
                )

    @property
    def requires_release(self) -> bool:
        """True while this binding is still made by revision rather than release.

        A stated absence. The end state is a released-version binding, and a
        reader must be able to see that this one is not there yet without
        reading the docstring.
        """
        return self.released_version is None

    def cite(self) -> str:
        return f"{self.repository}@{self.revision}:{self.path.as_posix()}"


#: `ApplicationFoundationProfile.v1`, bound by immutable source coordinate.
#:
#: `revision` is the commit that last wrote the contract's bytes, read
#: 2026-09-05; the file is 1,072 lines and its blob is
#: `9ee491b352543f494621d2947751e227a962492c`. `released_version` is `None`
#: because no Foundation release carries this module — see this file's
#: docstring for the measurement and open decision 50 for the resolution.
FOUNDATION_APPLICATION_PROFILE = ContractBinding(
    repository="michaelayoade/dotmac_starter_mt",
    revision="ee07c42261e791fde3035e7682a8e2fb77ba4603",
    path=PurePosixPath(
        "packages/dotmac-deployment-foundation/src/dotmac_deployment_foundation"
        "/application_profile.py"
    ),
    symbol="APPLICATION_PROFILE_SCHEMA",
    released_version=None,
)


@dataclass(frozen=True)
class AdoptionClaim:
    """A claim that a binding holds some adoption state. Validated at construction.

    This is where Michael's ruling stops being documentation. A revision-bound
    binding is a REPORT-ONLY BOOTSTRAP, and the three release-only states are
    not merely discouraged for it — they cannot be constructed. There is no
    flag, no override and no keyword that relaxes this, because the failure
    being prevented is a later reader deciding the bootstrap was good enough.

    The guard is not "always raise": a binding that names a released version
    may hold any state, which is what makes the refusal above a property of the
    coordinate kind rather than of this class.
    """

    binding: ContractBinding
    state: AdoptionState

    def __post_init__(self) -> None:
        if self.state in RELEASE_ONLY_STATES and self.binding.requires_release:
            raise BootstrapOnlyError(
                f"{self.binding.cite()} is bound by source revision and cannot "
                f"count as {self.state.value!r}. Michael's ruling of "
                "2026-09-05 permits the immutable source coordinate only as a "
                "temporary, report-only bootstrap: it must never count as "
                "installed, admitted or adopted. A source revision says which "
                "bytes were written, and installation, admission and adoption "
                "are facts about a released artifact that no revision can "
                "establish. Bind a published version first — open decision 50"
            )
