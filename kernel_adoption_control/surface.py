"""Two derived digests, and the exact bytes each is taken over.

Both exist for the same reason: **a declaration and the thing it describes must
be bound to each other, so that drift between them is a reviewable edit rather
than silence.** Neither is a signature and neither is an oracle. A product
authors both halves of each pair; what a digest buys is that the two halves
cannot move apart without someone editing the declaration in the same change.
That is a modest claim, and it is stated here so nothing downstream reads a
larger one into it.

## `source_surface` — the non-self-referential source coordinate

`KernelAdoptionDeclaration.v1` requires `product_revision`, a peeled commit,
and nothing compares it. It cannot be compared, and Michael said why on
2026-09-06: *"a committed file cannot contain its own commit."* A file that
named the commit containing it would have to know a hash over its own bytes
before those bytes existed.

The repair is to name something the declaration CAN contain and a run CAN
re-derive: a digest over the product's Kernel-surface usage. `surface_digest`
takes it over the canonical, sorted, line-free rendering of every
`(path, module, symbols, star)` fact the run measured.

**What it proves.** The declaration was written against a source whose Kernel
surface is exactly this one. Any Kernel import added, removed, renamed, moved
between files, or changed in the names it binds produces a different digest and
a refusal. It is derived from the measured source rather than asserted, so it
cannot be satisfied by editing the declaration alone.

**What it does not prove**, each stated because each is a claim someone will
otherwise read into it:

- **Not a revision.** It names no commit and cannot be resolved to one. Two
  different commits with identical Kernel usage share a digest. Ancestry is a
  separate coordinate — `source_predecessor` — verified by the runner.
- **Not a date.** A digest has no age. `declared_at` is a separate field.
- **Not inventory completeness.** It digests what was MEASURED. An observer
  that never offers a file hides that file from the digest exactly as it hides
  it from every other arm; the digest binds the declaration to the observation,
  not the observation to the repository. A product narrowing its own inventory
  to conceal an import gets a digest change only if the concealed file imported
  the Kernel — which it did, so it does. What stays invisible is an observer
  that never grew to cover a directory at all.
- **Not non-Kernel change.** Deliberately. A digest over every byte of the tree
  would change on every commit, and a coordinate that refuses on every commit
  is a coordinate that gets deleted. The declaration classifies Kernel
  surfaces; it is bound to Kernel surfaces.
- **Not authorship.** It says the two documents agree, not that a human read
  either.

Line numbers are excluded ON PURPOSE. Inserting an unrelated function above an
import moves its line and changes nothing the declaration classifies; a
coordinate that refuses on that is noise, and noise is how a check stops being
read. Multiple imports of one module in one file are MERGED — union of symbols,
`star` if any is a star — so splitting one `from x import a, b` into two
statements does not move the digest either.

## `catalogue_digest` — which Kernel the surfaces were classified against

`kernel_catalogue` carries a version, a peeled revision and an artifact digest,
and v1 compares none of them with the catalogue the observer supplies. So a
product could declare one Kernel and be measured against a self-authored
catalogue for another: every unknown-surface verdict would be taken against
module lists nobody bound to the declared version.

`catalogue_digest` closes it by digesting the catalogue's CONTENT — the version,
the revision, and the sorted supported and internal module lists. Declaring the
version is then not enough; the lists behind it are bound too.

### The root façade is the third list, and why the name moved to v2

`SUPPORTED_MODULES` and `INTERNAL_MODULES` enumerate SUBMODULES. The bare
`dotmac_kernel` is in neither — checked at `dotmac-kernel-v0.1.0a102`, peeled
`7a3c128b06eaba09784a9d8409d036169b3caa68`, where they carry 89 and 4 names.
The root façade has its own publication authority, `dotmac_kernel.__all__`, and
that list is bound here as `root_export` records so a verdict about a root
import is taken against a set the declaration named.

`CATALOGUE_DIGEST_ALGORITHM` moved from `dmg-kernel-catalogue-v1` to
`dmg-kernel-catalogue-v2` because of the rule stated at the top of this module:
a later canonicalization is a NEW name. Every stored `catalogue_digest` taken
under v1 must be re-derived. That is a visible refusal — `catalogue.disagrees`
— rather than a silent re-interpretation, which is the outcome the naming rule
exists to buy.

What is NOT repaired, and is stated rather than left to be discovered:
`kernel_catalogue` carries no `algorithm` field, unlike `source_surface`. So a
stored catalogue digest does not say which canonicalization produced it, and a
reader holding only the document cannot tell. The Governance pin is exact and
the runner refuses a product measured by an unpinned revision, so in practice
one implementation produces and compares every value — but that is a property
of the pin, not of this coordinate, and it is a gap.

**What it does not prove:** that any such Kernel was published. It is a digest
over lists the observer supplied from its own checkout, not a registry
attestation. The distribution artifact digest is carried separately and
compared to what the observer read out of the product's own lock file — a
repository-local fact — and verifying THAT against a registry needs the oracle
of open decision 17, which this repository does not have.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final

__all__ = [
    "CATALOGUE_DIGEST_ALGORITHM",
    "SOURCE_SURFACE_ALGORITHM",
    "SurfaceFact",
    "catalogue_digest",
    "render_surface",
    "surface_digest",
]

#: The canonicalization's own name and version, prefixed to the bytes digested.
#: A later canonicalization is a NEW name: two algorithms sharing one name
#: would make one declared digest describe two different renderings, and a
#: reader could not tell which one a stored value was taken under.
SOURCE_SURFACE_ALGORITHM: Final = "dmg-kernel-surface-v1"
CATALOGUE_DIGEST_ALGORITHM: Final = "dmg-kernel-catalogue-v2"

#: Field and record separators chosen because neither can occur in any field.
#: A module path, a symbol and a POSIX path cannot contain a tab or a newline,
#: so no field can impersonate a separator and no two distinct fact sets can
#: render to the same bytes.
_FIELD = "\t"
_RECORD = "\n"


@dataclass(frozen=True, order=True)
class SurfaceFact:
    """One file's use of one Kernel module, with the names it binds.

    Deliberately carries NO line number — see this module's docstring for why.
    """

    path: PurePosixPath
    module: str
    symbols: tuple[str, ...]
    star: bool

    def render(self) -> str:
        star = "*" if self.star else "-"
        return _FIELD.join(
            (self.path.as_posix(), self.module, ",".join(self.symbols), star)
        )


def render_surface(facts: frozenset[SurfaceFact]) -> str:
    """The canonical rendering the digest is taken over. Exposed for diagnosis.

    A digest mismatch is unreadable on its own, so the rendering is a public
    function: a reader can print both sides and see which line moved.
    """
    lines = sorted(fact.render() for fact in facts)
    return SOURCE_SURFACE_ALGORITHM + _RECORD + _RECORD.join(lines) + _RECORD


def surface_digest(facts: frozenset[SurfaceFact]) -> str:
    """`sha256:<hex>` over `render_surface`.

    An EMPTY fact set has a digest, and it is a constant. That is a vacuity
    hazard rather than a feature — every product importing no Kernel would
    share it — and it is not handled here, because a digest function is the
    wrong place to hold a policy. The engine refuses an `applicable`
    declaration over zero observed Kernel imports outright
    (`kernel.surface.none-observed`), which is what stops the constant from
    ever being the value that passed.
    """
    rendered = render_surface(facts)
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def catalogue_digest(
    *,
    version: str,
    revision: str,
    supported: frozenset[str],
    internal: frozenset[str],
    root_exports: frozenset[str],
) -> str:
    """`sha256:<hex>` over the catalogue's version, revision and published names.

    The lists are rendered separately and labelled, so moving a module from
    `internal` to `supported` changes the digest. That move changes what the
    unknown-surface arm would say about nothing — both are `known` — but it
    changes what the PRIVATE arm's near-miss rests on, and more importantly it
    is a change to the Kernel's published classification. A digest that let it
    pass would be binding a summary rather than the catalogue.

    `root_exports` is the third list and is bound for the same reason as the
    first two. It is the ROOT FAÇADE's publication authority — the installed
    artifact's `dotmac_kernel.__all__` — and it is the set the root arm admits
    against. Left out of the digest, an observer could widen it silently and
    the declaration would go on matching while the arm admitted names the
    Kernel never published; a declaration that binds the catalogue must bind
    every list a verdict is taken against.

    `root_exports` is a REQUIRED keyword with no default, deliberately. A
    default of `frozenset()` would let a caller that has root exports omit them
    and produce a digest that silently disagrees with the catalogue it was
    supposed to describe — which is a mismatch reported as "the catalogue
    moved" for a call that forgot an argument.
    """
    body = _RECORD.join(
        (
            CATALOGUE_DIGEST_ALGORITHM,
            f"version{_FIELD}{version}",
            f"revision{_FIELD}{revision}",
            *(f"supported{_FIELD}{name}" for name in sorted(supported)),
            *(f"internal{_FIELD}{name}" for name in sorted(internal)),
            *(f"root_export{_FIELD}{name}" for name in sorted(root_exports)),
        )
    )
    return "sha256:" + hashlib.sha256((body + _RECORD).encode("utf-8")).hexdigest()
