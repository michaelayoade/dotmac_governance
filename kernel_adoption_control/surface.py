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

## `surface_identity_digest` — the same surface, with the Kernel's own names

`dmg-kernel-surface-v1` records the names an import BINDS LOCALLY. So
`from dotmac_kernel import A as Y` and `from dotmac_kernel import B as Y` render
identically and share a digest: the declaration goes on matching while the
symbol the product actually imports from the Kernel changed underneath it. That
is the binding half weakening, and only for aliased imports — the enforcement
arms re-derive from `_KernelImport.names`, the Kernel-side spelling, on every
run, so no verdict was ever taken against a local alias. It bit a fixture
before it bit a product: Platform aliases the Kernel's
`UndeclaredCapabilityError` to `KernelUndeclaredCapabilityError`, and the
measured fixture recorded the alias.

`dmg-kernel-surface-v2` records both halves as SEPARATE facts. Each binding is
a `SurfaceBinding(kernel, local)` pair — the name the Kernel publishes, and the
name this file bound it to — so `A as Y` and `B as Y` differ, while the local
name a product actually writes stays recoverable from the rendering rather than
being flattened away. An unaliased `from dotmac_kernel import A` renders
`A>A`: the same name on both sides is a fact about the import, not padding.

**v1 is not redefined.** It keeps its name, its input type (`SurfaceFact`), its
rendering and its digest, and a declaration carrying a v1 value keeps verifying
exactly as it did. The two algorithms coexist; migrating is a product's own act
and needs a change this module does not make — see the note at the end of this
section.

**Domain separation is structural, not a check.** The algorithm name is the
FIRST LINE of the bytes each digest is taken over. A v1 digest and a v2 digest
over the same facts therefore have different preimages and cannot collide by
construction; there is no comparison anyone could delete to make a v1 value
readable as a v2 one. This is the same property `dmg-kernel-catalogue-v2`
relies on, and it is why a later canonicalization is always a new name here.

**What v2 does NOT change**, stated so nothing is read into it:

- Every disclaimer above for `source_surface` still holds verbatim — not a
  revision, not a date, not inventory completeness, not non-Kernel change, not
  authorship.
- The merge and exclusion rules are unchanged: no line numbers, and multiple
  imports of one module in one file are merged into one fact. Reordering
  imports, reformatting, or adding a comment moves neither digest.
- **Not a new document schema.** `KernelAdoptionDeclaration.v2` is unchanged.
  `declaration_contract_v2` admits `source_surface.algorithm` from a CLOSED set
  of exactly two — `ACCEPTED_SOURCE_SURFACE_ALGORITHMS` — and the declared name
  SELECTS which canonicalization `engine._check_source_surface` re-derives.
  Compatible vocabulary widening: an existing v1 declaration parses and
  evaluates exactly as it did, and migrating is a product's own edit.
  `observed_surface_identity` derives the value a migrating product declares,
  from the runner rather than from a hand-rolled second implementation.
- **Not a defence against a relabelled digest at PARSE time, and it does not
  need to be.** A digest is 64 opaque hex characters; nothing in it records the
  rendering that produced it, and a document parser has no source to re-derive
  from. So a v1 digest labelled `dmg-kernel-surface-v2` parses, and the RUN
  refuses it: the re-derived v2 value is taken over different bytes and cannot
  equal a v1 one. The refusal comes from the structure of the two digests, not
  from a check that could be forgotten.
- **Not interchangeable inputs.** `SurfaceFact` and `SurfaceIdentityFact` do
  not share a render method name (`render` vs `render_identity`), so neither
  renderer can walk the other's facts. A mismatched set raises instead of
  producing a hybrid digest nobody defined. `render_surface_identity` says so
  in a message; `render_surface` raises `AttributeError`, a worse message and a
  deliberate one — improving it means editing v1.

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
    "SOURCE_SURFACE_IDENTITY_ALGORITHM",
    "SurfaceBinding",
    "SurfaceFact",
    "SurfaceIdentityFact",
    "catalogue_digest",
    "render_surface",
    "render_surface_identity",
    "surface_digest",
    "surface_identity_digest",
]

#: The canonicalization's own name and version, prefixed to the bytes digested.
#: A later canonicalization is a NEW name: two algorithms sharing one name
#: would make one declared digest describe two different renderings, and a
#: reader could not tell which one a stored value was taken under.
SOURCE_SURFACE_ALGORITHM: Final = "dmg-kernel-surface-v1"
#: The successor canonicalization, which records the Kernel's own name for a
#: symbol separately from the local name an import bound it to. A SEPARATE
#: name rather than a redefinition of the line above: v1 is frozen, and both
#: are prefixed to their own bytes, so no v1 value can be read as a v2 one.
SOURCE_SURFACE_IDENTITY_ALGORITHM: Final = "dmg-kernel-surface-v2"
CATALOGUE_DIGEST_ALGORITHM: Final = "dmg-kernel-catalogue-v2"

#: Field and record separators chosen because neither can occur in any field.
#: A module path, a symbol and a POSIX path cannot contain a tab or a newline,
#: so no field can impersonate a separator and no two distinct fact sets can
#: render to the same bytes.
_FIELD = "\t"
_RECORD = "\n"
#: Separates the two halves of one binding, INSIDE the tab-delimited bindings
#: field. Chosen because that field holds only Python identifiers and dotted
#: module paths, neither of which can contain `>`; the repository path, which
#: could, is a different field. So no half can impersonate the separator and
#: `A>Y` and `B>Y` cannot render to the same bytes.
_BINDING = ">"


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


@dataclass(frozen=True, order=True)
class SurfaceBinding:
    """One imported symbol, as the Kernel spells it and as this file bound it.

    `kernel` is the name on the FAR side of `as` -- the one the Kernel
    publishes, and the only one a verdict about the Kernel may be taken
    against. `local` is the name the importing module can now use and
    re-export. For an unaliased import they are equal, and that equality is
    recorded rather than collapsed: a rendering that dropped one half when they
    matched would have to be told apart from one that had only ever seen the
    other half.

    For a plain `import dotmac_kernel.db as k` there is no imported SYMBOL, so
    `kernel` is the dotted module path -- the Kernel identity that statement
    names -- and `local` is `k`. Such a statement cannot collide with a `from`
    import of the same names, because the two render under different `module`
    fields.
    """

    kernel: str
    local: str

    def render(self) -> str:
        return self.kernel + _BINDING + self.local


@dataclass(frozen=True, order=True)
class SurfaceIdentityFact:
    """One file's use of one Kernel module, with canonical identity preserved.

    `SurfaceFact`'s successor, and a SEPARATE type rather than a widened one.
    Giving `SurfaceFact` an optional bindings field would let a caller that has
    bindings omit them and still get a v2 digest -- a value that silently
    describes less than the algorithm claims, reported later as "the source
    moved" for a call that forgot an argument. That hazard is named for
    `catalogue_digest`'s `root_exports` in this same module; the repair here is
    that v1's input cannot be handed to v2 at all.

    Carries NO line number, for the reason v1 does not -- see this module's
    docstring.
    """

    path: PurePosixPath
    module: str
    bindings: tuple[SurfaceBinding, ...]
    star: bool

    def render_identity(self) -> str:
        """NOT called `render`, and the difference is the refusal.

        `SurfaceFact.render` and this method would otherwise be one duck-typed
        name over two canonicalizations, and `render_surface_identity` would
        happily walk a set of v1 facts: v1 lines under a v2 header, a hybrid
        digest nobody defined, produced silently. Distinct method names make
        each renderer reach for something the other shape does not have, so a
        mismatched set raises instead of coercing. There is no check here to
        delete -- the absence of the method IS the refusal.
        """
        star = "*" if self.star else "-"
        return _FIELD.join(
            (
                self.path.as_posix(),
                self.module,
                ",".join(sorted(binding.render() for binding in self.bindings)),
                star,
            )
        )


def render_surface_identity(facts: frozenset[SurfaceIdentityFact]) -> str:
    """The canonical rendering `surface_identity_digest` is taken over.

    Public for the reason `render_surface` is: a digest mismatch is unreadable
    on its own, and a reader needs to see which line moved.

    The first line is `SOURCE_SURFACE_IDENTITY_ALGORITHM`, exactly as
    `render_surface`'s first line is `SOURCE_SURFACE_ALGORITHM`. That placement
    is what makes the two domains separate by construction rather than by a
    check: no fact set renders to the same bytes under both.
    """
    wrong = sorted(
        type(fact).__name__
        for fact in facts
        if not isinstance(fact, SurfaceIdentityFact)
    )
    if wrong:
        raise TypeError(
            f"{SOURCE_SURFACE_IDENTITY_ALGORITHM} renders SurfaceIdentityFact "
            f"and was handed {', '.join(wrong)}. A v1 fact carries no "
            "canonical Kernel name, so rendering one here would produce a "
            "digest labelled v2 over a surface that never recorded the "
            "identity v2 exists to bind. Refusing rather than coercing"
        )
    lines = sorted(fact.render_identity() for fact in facts)
    return SOURCE_SURFACE_IDENTITY_ALGORITHM + _RECORD + _RECORD.join(lines) + _RECORD


def surface_identity_digest(facts: frozenset[SurfaceIdentityFact]) -> str:
    """`sha256:<hex>` over `render_surface_identity`.

    The empty fact set has a constant digest here too, and it is the same
    vacuity hazard `surface_digest` documents, held by the same engine arm
    (`kernel.surface.none-observed`) rather than by this function.
    """
    rendered = render_surface_identity(facts)
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
