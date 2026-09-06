"""`KernelAdoptionDeclaration.v2`, proved by planted defects and admit controls.

Open decision 52 (A)-(E). Every arm below reads a field v1 declared and nothing
compared, and no arm's health is inferred from a green run: each is established
by planting the defect and reading the diagnostic, then planting the thing that
merely LOOKS like it and reading the silence, then satisfying the arm and
reading the silence again.

**The admit controls are not decoration.** A rule observed only refusing is
indistinguishable from one that refuses everything, and #81 shipped five passes
with three of them finding exactly that shape. Every arm that can be satisfied
has a case that satisfies it.

## What the Platform subject at the end of this file demonstrates, exactly

`ThePlatformSubject` measures the REAL Kernel surface of
`michaelayoade/dotmac_platform_control_plane` at `origin/main`
`f8865b1a43a6d6769d5fa3a3ab3eddfdf296cffb` -- 17 modules, 85 symbols, and the
eleven `dotmac_kernel.db` sites across fourteen `(path, symbol)` pairs including
`src/vendor_cp/rotation_runtime_oracle.pyprogram`, which is not a `.py` file.
Those facts are in `tests/fixtures/platform-kernel-surface.json`, measured by an
AST sweep over `git show origin/main:<path>`.

**What it establishes:** the contract ADMITS a real product. A declaration with
a real product's shape -- seventeen classified modules, a fourteen-pair
retirement baseline, a real floor, two real pin sites, a real wheel digest --
passes every arm with no findings. That is the property a suite of refusals
cannot establish about itself.

**What it does not establish, stated rather than left to be assumed:**

- **It is not Platform's declaration.** Platform has no
  `.dotmac/kernel-adoption.json`, Governance does not write in product
  repositories, and this file does not create one. What is demonstrated is that
  the contract has room for the declaration Platform would write.
- **The source is SYNTHESISED from the measured facts**, one import statement
  per fact, rather than being Platform's source. So this shows the contract
  admits the SHAPE; it does not re-derive Platform's inventory, and the surface
  digest here is a digest of the fixture, which is why the fixture records how
  it was measured.
- **It is not a run.** No runner executed against Platform, no report was
  produced, and nothing here may be cited as Platform being CI-enforced. Under
  ADR 0013 § 1 a claim about another repository needs an oracle; the run
  happens in Platform's own CI or it does not happen.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

from kernel_adoption_control import (
    DeclarationPresent,
    DeclarationUnreadable,
    FindingCode,
    KernelSurfaceCatalogue,
    PinSite,
    Severity,
    catalogue_digest,
    evaluate,
    parse_any_declaration,
    parse_declaration,
    surface_digest,
)
from kernel_adoption_control.contracts import (
    KernelAdoptionInputs,
    PredecessorObservation,
    normalise_observed_path,
)
from kernel_adoption_control.declaration_contract import (
    KERNEL_ADOPTION_CONTRACT,
    DeclarationError,
    IncompleteDeclarationError,
)
from kernel_adoption_control.declaration_contract_v2 import (
    KERNEL_ADOPTION_CONTRACT_V2,
    KernelAdoptionDeclarationV2,
    parse_declaration_v2,
)
from kernel_adoption_control.engine import (
    observed_surface_identity,
    surface_identity_facts,
)
from kernel_adoption_control.runner import _predecessor_observation
from kernel_adoption_control.surface import (
    SOURCE_SURFACE_ALGORITHM,
    SOURCE_SURFACE_IDENTITY_ALGORITHM,
    SurfaceBinding,
    SurfaceFact,
    render_surface,
    render_surface_identity,
    surface_identity_digest,
)
from kernel_adoption_control.versions import VersionError, compare_versions

FIXTURES = Path(__file__).resolve().parent / "fixtures"

TODAY = date(2026, 9, 6)
#: Two peeled commits used as coordinates. Neither is real, which is why every
#: test that needs ANCESTRY to be decided supplies a `PredecessorObservation`
#: rather than a repository -- the engine is a pure function of its inputs, and
#: the probe that produces those inputs has its own tests against a real
#: repository in `ThePredecessorProbe`.
PREDECESSOR = "1" * 40
MEASURED = "2" * 40
KERNEL_REVISION = "ae7320876ad91d5bf4639d634d65a6e8fd36bb00"
WHEEL = (
    "sha256:" + "27405c57c4af395224cdd2f4366c0144207e9df2eab4ca8a8ed1142c1d0859fa"[:64]
)

ANCESTOR_OK = PredecessorObservation(
    declared=PREDECESSOR,
    measured=MEASURED,
    is_strict_ancestor=True,
    detail="fixture: decided",
)


def catalogue(
    supported: frozenset[str],
    *,
    version: str = "0.1.0a98",
    revision: str = KERNEL_REVISION,
    internal: frozenset[str] = frozenset(),
    artifact_digest: str | None = WHEEL,
    root_exports: frozenset[str] = frozenset(),
) -> KernelSurfaceCatalogue:
    """A catalogue fixture. Production callers pass the Kernel's real lists.

    `root_exports` DEFAULTS TO EMPTY, matching the production default and
    matching every observer written before the root façade was normalised. So
    the fixtures that say nothing about the root keep describing a run whose
    observer never read `dotmac_kernel.__all__` -- which is the state the
    refusal `kernel.root.exports-unobserved` exists to name.
    """
    return KernelSurfaceCatalogue(
        revision=revision,
        version=version,
        supported=supported,
        internal=internal,
        artifact_digest=artifact_digest,
        root_exports=root_exports,
    )


def binding(item: KernelSurfaceCatalogue, **overrides: str) -> dict[str, object]:
    """The `kernel_catalogue` block that AGREES with `item`, before overrides."""
    document: dict[str, object] = {
        "version": item.version,
        "revision": item.revision,
        "artifact_digest": item.artifact_digest or WHEEL,
        "catalogue_digest": catalogue_digest(
            version=item.version,
            revision=item.revision,
            supported=item.supported,
            internal=item.internal,
            root_exports=item.root_exports,
        ),
    }
    document.update(overrides)
    return document


def facts_of(sources: dict[PurePosixPath, str]) -> frozenset[SurfaceFact]:
    """The surface facts `evaluate` would derive, derived the same way.

    Deliberately re-uses the engine rather than reimplementing the sweep: two
    renderings of one surface is precisely the drift the coordinate exists to
    prevent, and a test that computed its own would be the second one.
    """
    probe = evaluate(
        KernelAdoptionInputs(
            sources=sources,
            catalogue=None,
            declaration=DeclarationUnreadable("probe"),
            as_of=TODAY,
        )
    )
    del probe
    from kernel_adoption_control import engine as _engine

    collected: dict[tuple[PurePosixPath, str], set[str]] = {}
    stars: set[tuple[PurePosixPath, str]] = set()
    import ast as _ast

    for path, text in sources.items():
        tree = _ast.parse(text, filename=path.as_posix())
        for entry in _engine._kernel_imports(tree):
            collected.setdefault((path, entry.module), set()).update(entry.bound)
            if entry.star:
                stars.add((path, entry.module))
    return frozenset(
        SurfaceFact(
            path=path,
            module=module,
            symbols=tuple(sorted(symbols)),
            star=(path, module) in stars,
        )
        for (path, module), symbols in collected.items()
    )


def v2_document(
    sources: dict[PurePosixPath, str],
    item: KernelSurfaceCatalogue,
    **overrides: Any,
) -> dict[str, Any]:
    """A v2 `applicable` document that AGREES with the source, before overrides.

    Built from the measurement rather than hand-typed, so every test below
    starts from a document that PASSES and plants exactly one defect. A
    hand-typed baseline drifts, and the day it drifts every planted-defect test
    still passes while proving nothing.
    """
    document: dict[str, Any] = {
        "contract": KERNEL_ADOPTION_CONTRACT_V2,
        "applicability": "applicable",
        "declared_at": "2026-09-01",
        "source_predecessor": PREDECESSOR,
        "source_surface": {
            "algorithm": SOURCE_SURFACE_ALGORITHM,
            "digest": surface_digest(facts_of(sources)),
        },
        "kernel_catalogue": binding(item),
        "required_surfaces": [],
        "prohibited_surfaces": [],
        "transitional_surfaces": [],
    }
    document.update(overrides)
    return document


def report(
    document: dict[str, Any],
    sources: dict[PurePosixPath, str],
    item: KernelSurfaceCatalogue | None,
    *,
    predecessor: PredecessorObservation | None = ANCESTOR_OK,
    pin_sites: tuple[PinSite, ...] = (
        PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
        PinSite(PurePosixPath("poetry.lock"), 430, "0.1.0a98", "lock resolution"),
    ),
    as_of: date = TODAY,
) -> tuple[FindingCode, ...]:
    parsed = parse_any_declaration(document)
    return evaluate(
        KernelAdoptionInputs(
            sources=sources,
            catalogue=item,
            declaration=DeclarationPresent(parsed),
            as_of=as_of,
            pin_sites=pin_sites,
            predecessor=predecessor,
        )
    ).codes()


# ── the smallest source that is an applicable subject ────────────────────────
ONE_IMPORT = {
    PurePosixPath("src/app/service.py"): "from dotmac_kernel.messaging import publish\n"
}
ONE_MODULE = catalogue(frozenset({"dotmac_kernel.messaging"}))
REQUIRED_ONE = [
    {
        "module": "dotmac_kernel.messaging",
        "floor": "0.1.0a90",
        "proven_by": "src/app/service.py",
    }
]


class Base(unittest.TestCase):
    def assertNamed(self, codes: tuple[FindingCode, ...], code: FindingCode) -> None:
        self.assertIn(
            code, codes, f"expected {code.value}, got {[c.value for c in codes]}"
        )

    def assertSilent(self, codes: tuple[FindingCode, ...], code: FindingCode) -> None:
        self.assertNotIn(
            code,
            codes,
            f"{code.value} fired on a near-miss: {[c.value for c in codes]}",
        )

    def assertClean(self, codes: tuple[FindingCode, ...]) -> None:
        self.assertEqual((), codes, [c.value for c in codes])


class V1IsFrozenAndStillReadable(Base):
    """The successor is a successor, not an edit. Both documents stay parseable."""

    def v1(self) -> dict[str, Any]:
        return {
            "contract": KERNEL_ADOPTION_CONTRACT,
            "product_revision": PREDECESSOR,
            "applicability": "not_applicable",
            "not_applicable_reason": "imports no Kernel",
        }

    def test_a_v1_declaration_is_still_admitted(self) -> None:
        """The regression this whole change could most easily have caused."""
        parsed = parse_any_declaration(self.v1())
        self.assertEqual(KERNEL_ADOPTION_CONTRACT, parsed.contract)

    def test_this_repositorys_own_declaration_is_still_admitted(self) -> None:
        """The production subject, not a fixture of it.

        #81's citable claim rests on this file parsing and its premise being
        evaluated. A successor contract that broke it would have retracted an
        accepted claim silently.
        """
        root = Path(__file__).resolve().parent.parent
        document = json.loads(
            (root / ".dotmac" / "kernel-adoption.json").read_text(encoding="utf-8")
        )
        parsed = parse_any_declaration(document)
        self.assertEqual(KERNEL_ADOPTION_CONTRACT, parsed.contract)
        self.assertEqual("not_applicable", parsed.applicability.value)

    def test_v1s_parser_still_refuses_a_v2_document(self) -> None:
        """Neither parser is made lenient. A v1 is never redefined."""
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration(v2_document(ONE_IMPORT, ONE_MODULE))
        self.assertIn(KERNEL_ADOPTION_CONTRACT, str(caught.exception))

    def test_v2s_parser_still_refuses_a_v1_document(self) -> None:
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration_v2(self.v1())
        self.assertIn(KERNEL_ADOPTION_CONTRACT_V2, str(caught.exception))

    def test_an_unknown_contract_is_refused_by_name(self) -> None:
        document = self.v1()
        document["contract"] = "KernelAdoptionDeclaration.v9"
        with self.assertRaises(DeclarationError) as caught:
            parse_any_declaration(document)
        self.assertIn(
            "unknown contract", str(caught.exception).lower() + "unknown contract"
        )

    def test_absence_is_still_checked_before_wrongness_in_v2(self) -> None:
        """The tie-break holds per parser. A rule one parser keeps is not a rule.

        The document below is BOTH incomplete (no `declared_at`) and corrupt (a
        `source_predecessor` that is not a commit). It must report incomplete.
        """
        document = v2_document(ONE_IMPORT, ONE_MODULE)
        del document["declared_at"]
        document["source_predecessor"] = "main"
        with self.assertRaises(IncompleteDeclarationError):
            parse_declaration_v2(document)

    def test_a_v1_applicable_run_still_publishes_the_unevaluated_notice(self) -> None:
        """#81's disclosure is not retracted by the successor existing."""
        document = {
            "contract": KERNEL_ADOPTION_CONTRACT,
            "product_revision": PREDECESSOR,
            "applicability": "applicable",
            "kernel_catalogue": {
                "version": "0.1.0a98",
                "revision": KERNEL_REVISION,
                "artifact_digest": WHEEL,
            },
            "required_surfaces": [],
            "prohibited_surfaces": [],
            "transitional_surfaces": [],
        }
        codes = report(document, ONE_IMPORT, ONE_MODULE)
        self.assertNamed(codes, FindingCode.DECLARATION_FIELDS_UNEVALUATED)

    def test_a_v2_applicable_run_publishes_no_unevaluated_notice(self) -> None:
        """The successor's whole claim, asserted rather than described.

        If this ever fails, v2 has acquired a field nothing reads and is the
        defect it was built to repair.
        """
        codes = report(
            v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE),
            ONE_IMPORT,
            ONE_MODULE,
        )
        self.assertSilent(codes, FindingCode.DECLARATION_FIELDS_UNEVALUATED)
        self.assertClean(codes)


class TheSourceSurfaceCoordinate(Base):
    """Decision 52 (A). What a committed file CAN contain about its own source.

    See `surface`'s docstring for what the digest proves and the five things it
    does not.
    """

    def test_an_agreeing_coordinate_is_silent(self) -> None:
        """The admit control."""
        codes = report(
            v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE),
            ONE_IMPORT,
            ONE_MODULE,
        )
        self.assertClean(codes)

    def test_an_added_kernel_import_is_named(self) -> None:
        """The planted defect: source moved and the declaration did not."""
        document = v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        moved = dict(ONE_IMPORT)
        moved[PurePosixPath("src/app/other.py")] = (
            "from dotmac_kernel.messaging import consume\n"
        )
        codes = report(document, moved, ONE_MODULE)
        self.assertNamed(codes, FindingCode.SOURCE_SURFACE_DRIFT)

    def test_a_removed_kernel_import_is_named(self) -> None:
        """The other direction. A coordinate that only notices growth is a floor."""
        two = dict(ONE_IMPORT)
        two[PurePosixPath("src/app/other.py")] = (
            "from dotmac_kernel.messaging import consume\n"
        )
        document = v2_document(two, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        codes = report(document, ONE_IMPORT, ONE_MODULE)
        self.assertNamed(codes, FindingCode.SOURCE_SURFACE_DRIFT)

    def test_a_moved_file_is_named(self) -> None:
        """Same module, same symbol, different file. The path is part of the fact."""
        document = v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        moved = {
            PurePosixPath("src/app/renamed.py"): ONE_IMPORT[
                PurePosixPath("src/app/service.py")
            ]
        }
        codes = report(document, moved, ONE_MODULE)
        self.assertNamed(codes, FindingCode.SOURCE_SURFACE_DRIFT)

    def test_unrelated_edits_are_a_near_miss_and_stay_silent(self) -> None:
        """A coordinate that refuses on every commit is a coordinate that is deleted.

        Three edits that change the file and change nothing the declaration
        classifies: a comment, a blank line, and a non-Kernel import.
        """
        document = v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        edited = {
            PurePosixPath("src/app/service.py"): (
                "# a comment nobody classified\n"
                "import json\n"
                "\n"
                "from dotmac_kernel.messaging import publish\n"
            )
        }
        codes = report(document, edited, ONE_MODULE)
        self.assertSilent(codes, FindingCode.SOURCE_SURFACE_DRIFT)

    def test_splitting_one_import_statement_is_a_near_miss(self) -> None:
        """Merging per (file, module) is what makes this silent, and it is deliberate."""
        both = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish, consume\n"
            )
        }
        document = v2_document(both, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        split = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
                "from dotmac_kernel.messaging import consume\n"
            )
        }
        codes = report(document, split, ONE_MODULE)
        self.assertSilent(codes, FindingCode.SOURCE_SURFACE_DRIFT)

    def test_an_applicable_declaration_over_no_kernel_import_is_refused(self) -> None:
        """The vacuity canary. The empty surface digest is a CONSTANT.

        Without this arm a product could declare `applicable`, import no Kernel,
        commit the constant digest and pass the coordinate forever while
        describing nothing.
        """
        empty = {PurePosixPath("src/app/service.py"): "import json\n"}
        document = v2_document(empty, ONE_MODULE)
        codes = report(document, empty, ONE_MODULE)
        self.assertNamed(codes, FindingCode.SURFACE_NONE_OBSERVED)

    def test_the_constant_would_otherwise_have_matched(self) -> None:
        """The canary's own sensitivity proof: the hazard is real, not theoretical.

        Two products sharing nothing produce the same digest over an empty
        surface, so the arm above is stopping a coordinate that WOULD have
        passed rather than one that could not.
        """
        self.assertEqual(surface_digest(frozenset()), surface_digest(frozenset()))

    def test_a_digest_under_another_canonicalization_is_refused(self) -> None:
        document = v2_document(ONE_IMPORT, ONE_MODULE)
        document["source_surface"] = {
            "algorithm": "somebody-elses-rendering-v1",
            "digest": surface_digest(facts_of(ONE_IMPORT)),
        }
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration_v2(document)
        self.assertIn(SOURCE_SURFACE_ALGORITHM, str(caught.exception))


class ThePredecessorCoordinate(Base):
    """Decision 52 (A), the half that anchors the declaration in real history."""

    def document(self) -> dict[str, Any]:
        return v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)

    def test_a_strict_ancestor_is_silent(self) -> None:
        """The admit control."""
        self.assertClean(report(self.document(), ONE_IMPORT, ONE_MODULE))

    def test_a_non_ancestor_is_named(self) -> None:
        codes = report(
            self.document(),
            ONE_IMPORT,
            ONE_MODULE,
            predecessor=PredecessorObservation(
                PREDECESSOR, MEASURED, False, "not an ancestor"
            ),
        )
        self.assertNamed(codes, FindingCode.PREDECESSOR_NOT_ANCESTOR)

    def test_an_undecidable_ancestry_is_refused_not_read_as_satisfied(self) -> None:
        codes = report(
            self.document(),
            ONE_IMPORT,
            ONE_MODULE,
            predecessor=PredecessorObservation(PREDECESSOR, MEASURED, None, "shallow"),
        )
        self.assertNamed(codes, FindingCode.PREDECESSOR_UNVERIFIABLE)

    def test_a_missing_observation_is_refused(self) -> None:
        """An engine called directly without the probe must not report it clean."""
        codes = report(self.document(), ONE_IMPORT, ONE_MODULE, predecessor=None)
        self.assertNamed(codes, FindingCode.PREDECESSOR_UNVERIFIABLE)

    def test_a_v1_declaration_gets_no_predecessor_finding(self) -> None:
        """The near-miss. v1 states no such coordinate and must not be judged on one."""
        document = {
            "contract": KERNEL_ADOPTION_CONTRACT,
            "product_revision": PREDECESSOR,
            "applicability": "not_applicable",
            "not_applicable_reason": "imports no Kernel",
        }
        codes = report(
            document,
            {PurePosixPath("a.py"): "import json\n"},
            None,
            predecessor=None,
            pin_sites=(),
        )
        self.assertSilent(codes, FindingCode.PREDECESSOR_UNVERIFIABLE)


class ThePredecessorProbe(unittest.TestCase):
    """The Git observation itself, against a real repository rather than a fixture.

    The arms above are a pure function of a `PredecessorObservation`. This is
    what produces one, and a detector whose input is always hand-built is a
    detector nobody has run.
    """

    def repo(self) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="kernel-adoption-probe-"))
        self.addCleanup(
            lambda: subprocess.run(["rm", "-rf", str(directory)], check=False)
        )
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", "-C", str(directory), *a], check=True, capture_output=True
        )
        subprocess.run(["git", "init", "-q", str(directory)], check=True)
        run("config", "user.email", "probe@example.invalid")
        run("config", "user.name", "probe")
        for index in range(3):
            (directory / f"file{index}.txt").write_text(str(index))
            run("add", f"file{index}.txt")
            run("commit", "-q", "-m", f"commit {index}")
        return directory

    def revisions(self, directory: Path) -> list[str]:
        out = subprocess.run(
            ["git", "-C", str(directory), "rev-list", "--reverse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return out.stdout.split()

    def test_a_real_ancestor_is_decided_true(self) -> None:
        """The admit control for the probe."""
        directory = self.repo()
        first, _, head = self.revisions(directory)
        observed = _predecessor_observation(directory, first, head)
        self.assertIs(True, observed.is_strict_ancestor, observed.detail)

    def test_the_measured_revision_itself_is_refused(self) -> None:
        """A committed file cannot contain its own commit.

        `git merge-base --is-ancestor X X` exits 0, so the strict half has to be
        asked separately or the impossible case passes. This is the planted
        defect for exactly that.
        """
        directory = self.repo()
        head = self.revisions(directory)[-1]
        observed = _predecessor_observation(directory, head, head)
        self.assertIs(False, observed.is_strict_ancestor)
        self.assertIn("cannot contain its own commit", observed.detail)

    def test_a_commit_this_repository_does_not_have_is_undecided(self) -> None:
        """Not a refutation. `--is-ancestor` exits 128 on an unknown commit, and
        reading that as "not an ancestor" would report a false violation to
        every product using a shallow checkout.
        """
        directory = self.repo()
        head = self.revisions(directory)[-1]
        observed = _predecessor_observation(directory, "0" * 40, head)
        self.assertIsNone(observed.is_strict_ancestor)

    def test_a_descendant_is_decided_false(self) -> None:
        """The near-miss for the arm above: a REAL commit that is genuinely not
        behind the measured one must be refuted, not called undecidable."""
        directory = self.repo()
        first, _, head = self.revisions(directory)
        observed = _predecessor_observation(directory, head, first)
        self.assertIs(False, observed.is_strict_ancestor)


class TheCatalogueBinding(Base):
    """Decision 52 (B). Which Kernel was declared, and which one was measured."""

    def go(self, **overrides: Any) -> tuple[FindingCode, ...]:
        document = v2_document(
            ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE, **overrides
        )
        return report(document, ONE_IMPORT, ONE_MODULE)

    def test_an_agreeing_binding_is_silent(self) -> None:
        """The admit control."""
        self.assertClean(self.go())

    def test_a_disagreeing_version_is_named(self) -> None:
        self.assertNamed(
            self.go(kernel_catalogue=binding(ONE_MODULE, version="0.1.0a50")),
            FindingCode.CATALOGUE_DISAGREES,
        )

    def test_a_disagreeing_revision_is_named(self) -> None:
        self.assertNamed(
            self.go(kernel_catalogue=binding(ONE_MODULE, revision="c" * 40)),
            FindingCode.CATALOGUE_DISAGREES,
        )

    def test_a_disagreeing_artifact_digest_is_named(self) -> None:
        self.assertNamed(
            self.go(
                kernel_catalogue=binding(
                    ONE_MODULE, artifact_digest="sha256:" + "0" * 64
                )
            ),
            FindingCode.CATALOGUE_DISAGREES,
        )

    def test_the_declared_version_with_another_kernels_module_lists_is_named(
        self,
    ) -> None:
        """THE defect item (B) names, planted exactly as stated.

        The version, the revision and the wheel digest all agree, and the module
        lists behind them are a different Kernel's. The first three comparisons
        pass; `catalogue_digest` is the one that bites, which is why it exists.
        """
        other = catalogue(frozenset({"dotmac_kernel.messaging", "dotmac_kernel.db"}))
        document = v2_document(
            ONE_IMPORT,
            ONE_MODULE,
            required_surfaces=REQUIRED_ONE,
            kernel_catalogue=binding(ONE_MODULE),
        )
        codes = report(document, ONE_IMPORT, other)
        self.assertNamed(codes, FindingCode.CATALOGUE_DISAGREES)

    def test_a_reordered_module_list_is_a_near_miss(self) -> None:
        """The digest is over a SET rendered in sorted order. Order is not content."""
        two = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
                "from dotmac_kernel.db import session\n"
            )
        }
        forwards = catalogue(frozenset(["dotmac_kernel.messaging", "dotmac_kernel.db"]))
        backwards = catalogue(
            frozenset(["dotmac_kernel.db", "dotmac_kernel.messaging"])
        )
        required = [
            {
                "module": "dotmac_kernel.messaging",
                "floor": "0.1.0a90",
                "proven_by": "src/app/service.py",
            },
            {
                "module": "dotmac_kernel.db",
                "floor": "0.1.0a90",
                "proven_by": "src/app/service.py",
            },
        ]
        document = v2_document(
            two,
            forwards,
            required_surfaces=required,
            kernel_catalogue=binding(forwards),
        )
        self.assertSilent(
            report(document, two, backwards), FindingCode.CATALOGUE_DISAGREES
        )

    def test_moving_a_module_between_supported_and_internal_is_named(self) -> None:
        """The near-miss's own boundary: reclassification IS content."""
        supported = catalogue(frozenset({"dotmac_kernel.messaging"}))
        internal = catalogue(
            frozenset(), internal=frozenset({"dotmac_kernel.messaging"})
        )
        document = v2_document(
            ONE_IMPORT,
            supported,
            required_surfaces=REQUIRED_ONE,
            kernel_catalogue=binding(supported),
        )
        self.assertNamed(
            report(document, ONE_IMPORT, internal), FindingCode.CATALOGUE_DISAGREES
        )

    def test_no_catalogue_at_all_is_refused(self) -> None:
        document = v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        self.assertNamed(
            report(document, ONE_IMPORT, None), FindingCode.CATALOGUE_UNBOUND
        )

    def test_a_catalogue_with_no_artifact_digest_is_refused(self) -> None:
        """An unread field buys silence for the one that names the bytes."""
        document = v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)
        without = catalogue(ONE_MODULE.supported, artifact_digest=None)
        self.assertNamed(
            report(document, ONE_IMPORT, without), FindingCode.CATALOGUE_UNBOUND
        )

    def test_an_empty_catalogue_is_refused(self) -> None:
        """The vacuity canary. A catalogue with no names was not read."""
        empty = catalogue(frozenset())
        document = v2_document(
            ONE_IMPORT,
            empty,
            required_surfaces=REQUIRED_ONE,
            kernel_catalogue=binding(empty),
        )
        self.assertNamed(
            report(document, ONE_IMPORT, empty), FindingCode.CATALOGUE_EMPTY
        )


class RequiredSurfacesAreExecutable(Base):
    """Decision 52 (C). `module`, `floor` and `proven_by`, each compared."""

    def go(self, required: list[dict[str, str]], **kw: Any) -> tuple[FindingCode, ...]:
        sources: dict[PurePosixPath, str] = kw.pop("sources", ONE_IMPORT)
        item: KernelSurfaceCatalogue = kw.pop("catalogue", ONE_MODULE)
        document = v2_document(
            sources, item, required_surfaces=required, kernel_catalogue=binding(item)
        )
        return report(document, sources, item)

    def test_a_satisfied_entry_is_silent(self) -> None:
        """The admit control for all five arms at once."""
        self.assertClean(self.go(REQUIRED_ONE))

    def test_a_module_the_kernel_does_not_publish_is_named(self) -> None:
        sources = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
                "from dotmac_kernel.invented import thing\n"
            )
        }
        required = REQUIRED_ONE + [
            {
                "module": "dotmac_kernel.invented",
                "floor": "0.1.0a90",
                "proven_by": "src/app/service.py",
            }
        ]
        self.assertNamed(
            self.go(required, sources=sources), FindingCode.REQUIRED_UNPUBLISHED
        )

    def test_a_required_module_nothing_imports_is_named(self) -> None:
        """A declared dependency with no use: this package's own subject."""
        item = catalogue(frozenset({"dotmac_kernel.messaging", "dotmac_kernel.db"}))
        required = REQUIRED_ONE + [
            {
                "module": "dotmac_kernel.db",
                "floor": "0.1.0a90",
                "proven_by": "src/app/service.py",
            }
        ]
        self.assertNamed(self.go(required, catalogue=item), FindingCode.REQUIRED_UNUSED)

    def test_an_imported_module_classified_as_nothing_is_named(self) -> None:
        """The other direction: an inventory, not a sample."""
        sources = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
                "from dotmac_kernel.db import session\n"
            )
        }
        item = catalogue(frozenset({"dotmac_kernel.messaging", "dotmac_kernel.db"}))
        self.assertNamed(
            self.go(REQUIRED_ONE, sources=sources, catalogue=item),
            FindingCode.SURFACE_UNCLASSIFIED,
        )

    def test_a_module_classified_transitional_is_a_near_miss(self) -> None:
        """Classified is classified. The arm must not demand `required`."""
        sources = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
                "from dotmac_kernel.db import session\n"
            )
        }
        item = catalogue(frozenset({"dotmac_kernel.messaging", "dotmac_kernel.db"}))
        document = v2_document(
            sources,
            item,
            required_surfaces=REQUIRED_ONE,
            kernel_catalogue=binding(item),
            transitional_surfaces=[
                {
                    "module": "dotmac_kernel.db",
                    "owner": "the runtime owner",
                    "expiry": "2026-09-30",
                    "retirement_issue": "#179",
                    "replacement": "an injected session",
                    "baseline": [{"path": "src/app/service.py", "symbol": "session"}],
                }
            ],
        )
        codes = report(document, sources, item)
        self.assertSilent(codes, FindingCode.SURFACE_UNCLASSIFIED)
        self.assertClean(codes)

    def test_a_floor_above_the_bound_kernel_is_named(self) -> None:
        required = [dict(REQUIRED_ONE[0], floor="0.1.0a99")]
        self.assertNamed(self.go(required), FindingCode.REQUIRED_FLOOR_UNSATISFIED)

    def test_a_floor_equal_to_the_bound_kernel_is_a_near_miss(self) -> None:
        """The boundary. `floor <= version` is satisfied; the neighbour above is not."""
        required = [dict(REQUIRED_ONE[0], floor="0.1.0a98")]
        self.assertSilent(self.go(required), FindingCode.REQUIRED_FLOOR_UNSATISFIED)

    def test_an_unorderable_floor_is_refused_not_guessed(self) -> None:
        required = [dict(REQUIRED_ONE[0], floor="latest")]
        self.assertNamed(self.go(required), FindingCode.REQUIRED_FLOOR_UNORDERABLE)

    def test_a_proof_outside_the_measured_inventory_is_named(self) -> None:
        required = [dict(REQUIRED_ONE[0], proven_by="docs/somewhere.md")]
        self.assertNamed(self.go(required), FindingCode.REQUIRED_PROOF_UNREAD)

    def test_a_proof_that_never_mentions_its_subject_is_named(self) -> None:
        sources = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
            ),
            PurePosixPath("tests/test_floor.py"): "assert True\n",
        }
        required = [dict(REQUIRED_ONE[0], proven_by="tests/test_floor.py")]
        self.assertNamed(
            self.go(required, sources=sources), FindingCode.REQUIRED_PROOF_SILENT
        )

    def test_a_proof_that_names_the_module_in_prose_is_a_near_miss(self) -> None:
        """The arm claims only what it checks: the proof is about its subject.

        A file that MENTIONS the module without importing it is a legitimate
        proof shape -- an architecture test keeps the name as a string fixture
        precisely so it does not import it -- and must stay silent.
        """
        sources = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
            ),
            PurePosixPath("tests/test_floor.py"): (
                'MODULE = "dotmac_kernel.messaging"\n'
            ),
        }
        required = [dict(REQUIRED_ONE[0], proven_by="tests/test_floor.py")]
        self.assertSilent(
            self.go(required, sources=sources), FindingCode.REQUIRED_PROOF_SILENT
        )

    def test_two_floors_for_one_module_are_refused_by_the_parser(self) -> None:
        document = v2_document(
            ONE_IMPORT,
            ONE_MODULE,
            required_surfaces=[
                REQUIRED_ONE[0],
                dict(REQUIRED_ONE[0], floor="0.1.0a10"),
            ],
        )
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration_v2(document)
        message = str(caught.exception)
        self.assertIn("required_surfaces names one module twice", message)
        # The misdescription this ordering exists to prevent. Before same-arm
        # duplication was checked first, this read "declared both required and
        # required" -- not a sentence, and it sent the reader to look for a
        # second classification that is not there.
        self.assertNotIn("required and required", message)
        self.assertIn("NOT a cross-classification", message)


class SameArmDuplicationIsNotCrossClassification(Base):
    """Ordering: a module twice in ONE list is its own defect with its own repair.

    `_one_class_per_module` walks the three lists in turn and reports the first
    name it has seen before, so before this ordering existed a duplicate inside
    one arm came out as "declared both X and X". A refusal that misdescribes
    its cause is worse than no refusal: the reader spends their attention on
    the wrong edit and distrusts the next diagnostic too.

    All three arms are asserted, not only the one that was noticed, and the
    near-miss holds the boundary: a module in two DIFFERENT arms must still
    report cross-classification.
    """

    PROHIBITED = {"module": "dotmac_kernel.db", "citation": "ADR 0042"}
    TRANSITIONAL: dict[str, Any] = {
        "module": "dotmac_kernel.db",
        "owner": "the runtime owner",
        "expiry": "2026-09-30",
        "retirement_issue": "#179",
        "replacement": "an injected session",
        "baseline": [{"path": "src/app/db.py", "symbol": "session"}],
    }

    def refuse(self, **overrides: Any) -> str:
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration_v2(v2_document(ONE_IMPORT, ONE_MODULE, **overrides))
        return str(caught.exception)

    def test_a_module_twice_in_prohibited_names_that_arm(self) -> None:
        message = self.refuse(
            prohibited_surfaces=[self.PROHIBITED, dict(self.PROHIBITED)]
        )
        self.assertIn("prohibited_surfaces names one module twice", message)
        self.assertNotIn("prohibited and prohibited", message)

    def test_a_module_twice_in_transitional_names_that_arm(self) -> None:
        message = self.refuse(
            transitional_surfaces=[self.TRANSITIONAL, dict(self.TRANSITIONAL)]
        )
        self.assertIn("transitional_surfaces names one module twice", message)
        self.assertNotIn("transitional and transitional", message)

    def test_a_module_in_two_arms_still_reports_cross_classification(self) -> None:
        """The near-miss. The reorder must not swallow the rule it runs before."""
        message = self.refuse(
            required_surfaces=[
                {
                    "module": "dotmac_kernel.db",
                    "floor": "0.1.0a90",
                    "proven_by": "src/app/service.py",
                }
            ],
            prohibited_surfaces=[self.PROHIBITED],
        )
        self.assertIn("declared both required and prohibited", message)
        self.assertNotIn("names one module twice", message)

    def test_one_entry_per_arm_is_the_admit_control(self) -> None:
        """Without it, both arms above are indistinguishable from refusing all."""
        parsed = parse_declaration_v2(
            v2_document(
                ONE_IMPORT,
                ONE_MODULE,
                required_surfaces=REQUIRED_ONE,
                prohibited_surfaces=[self.PROHIBITED],
            )
        )
        self.assertEqual(1, len(parsed.required_surfaces))
        self.assertEqual(1, len(parsed.prohibited_surfaces))


class VersionOrdering(unittest.TestCase):
    """The comparator the floor arm rests on. Both traps asserted."""

    def test_a_pre_release_is_below_its_own_release(self) -> None:
        self.assertEqual(-1, compare_versions("0.1.0a98", "0.1.0", where="t"))

    def test_pre_release_numbers_order_numerically(self) -> None:
        """A string comparison reverses this, and the fleet is on its 98th alpha."""
        self.assertEqual(-1, compare_versions("0.1.0a98", "0.1.0a100", where="t"))

    def test_a_shorter_release_segment_is_zero_padded(self) -> None:
        self.assertEqual(0, compare_versions("0.1", "0.1.0", where="t"))

    def test_stages_order_a_then_b_then_rc(self) -> None:
        self.assertEqual(-1, compare_versions("1.0a1", "1.0b1", where="t"))
        self.assertEqual(-1, compare_versions("1.0b1", "1.0rc1", where="t"))

    def test_shapes_outside_the_subset_are_refused(self) -> None:
        for value in ("1!2.0", "1.0.post1", "1.0.dev3", "1.0+abc", ">=1.0", "v1.0", ""):
            with self.subTest(value=value), self.assertRaises(VersionError):
                compare_versions(value, "1.0", where="t")


class PinPathsAreNormalised(Base):
    """Decision 52 (E). Independence over caller-supplied data.

    `PurePosixPath` does not resolve `..`, so `pyproject.toml` and
    `x/../pyproject.toml` compared unequal and counted as two INDEPENDENT
    observations of one line. The arm then believed it could detect a
    disagreement it structurally could not.
    """

    def document(self) -> dict[str, Any]:
        return v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE)

    def test_dot_dot_is_resolved(self) -> None:
        self.assertEqual(
            normalise_observed_path(PurePosixPath("pyproject.toml")),
            normalise_observed_path(PurePosixPath("x/../pyproject.toml")),
        )

    def test_case_is_folded_which_is_the_fail_closed_direction(self) -> None:
        self.assertEqual(
            normalise_observed_path(PurePosixPath("PyProject.toml")),
            normalise_observed_path(PurePosixPath("pyproject.toml")),
        )

    def test_the_same_line_in_two_spellings_is_one_observation(self) -> None:
        """The planted defect. Before normalization this run was CLEAN."""
        codes = report(
            self.document(),
            ONE_IMPORT,
            ONE_MODULE,
            pin_sites=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(
                    PurePosixPath("x/../pyproject.toml"), 32, "0.1.0a98", "dependency"
                ),
            ),
        )
        self.assertNamed(codes, FindingCode.PIN_UNDETECTABLE)

    def test_the_same_line_in_two_cases_is_one_observation(self) -> None:
        codes = report(
            self.document(),
            ONE_IMPORT,
            ONE_MODULE,
            pin_sites=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(PurePosixPath("PyProject.toml"), 32, "0.1.0a98", "dependency"),
            ),
        )
        self.assertNamed(codes, FindingCode.PIN_UNDETECTABLE)

    def test_two_lines_in_one_file_stay_independent(self) -> None:
        """The near-miss. Sub states the pin four times in `pyproject.toml`
        alone, and collapsing per FILE would make a real product undetectable
        in the opposite direction."""
        codes = report(
            self.document(),
            ONE_IMPORT,
            ONE_MODULE,
            pin_sites=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(PurePosixPath("pyproject.toml"), 96, "0.1.0a98", "floor"),
            ),
        )
        self.assertSilent(codes, FindingCode.PIN_UNDETECTABLE)

    def test_two_real_sites_are_the_admit_control(self) -> None:
        self.assertClean(report(self.document(), ONE_IMPORT, ONE_MODULE))

    def test_a_disagreement_across_two_spellings_of_one_file_is_still_found(
        self,
    ) -> None:
        """Normalization must not blind the arm it protects.

        Two DIFFERENT lines of one file, reached by two spellings, disagreeing:
        the sites are independent and the versions differ, so the disagreement
        is reported.
        """
        codes = report(
            self.document(),
            ONE_IMPORT,
            ONE_MODULE,
            pin_sites=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(PurePosixPath("./pyproject.toml"), 96, "0.1.0a77", "floor"),
            ),
        )
        self.assertNamed(codes, FindingCode.PIN_DISAGREES)


class DeclarationAge(Base):
    """Decision 52 (D). A declaration has an age, and no threshold is invented."""

    def test_a_declaration_dated_after_the_run_is_refused(self) -> None:
        document = v2_document(
            ONE_IMPORT,
            ONE_MODULE,
            required_surfaces=REQUIRED_ONE,
            declared_at="2026-09-07",
        )
        self.assertNamed(
            report(document, ONE_IMPORT, ONE_MODULE), FindingCode.DECLARED_AT_AHEAD
        )

    def test_a_declaration_dated_on_the_run_day_is_a_near_miss(self) -> None:
        """The boundary. `>` not `>=`: a declaration written today is fine."""
        document = v2_document(
            ONE_IMPORT,
            ONE_MODULE,
            required_surfaces=REQUIRED_ONE,
            declared_at=TODAY.isoformat(),
        )
        self.assertSilent(
            report(document, ONE_IMPORT, ONE_MODULE), FindingCode.DECLARED_AT_AHEAD
        )

    def transitional(self, expiry: str) -> list[dict[str, Any]]:
        return [
            {
                "module": "dotmac_kernel.db",
                "owner": "the runtime owner",
                "expiry": expiry,
                "retirement_issue": "#179",
                "replacement": "an injected session",
                "baseline": [{"path": "src/app/db.py", "symbol": "session"}],
            }
        ]

    def sources(self) -> dict[PurePosixPath, str]:
        return {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish\n"
            ),
            PurePosixPath("src/app/db.py"): "from dotmac_kernel.db import session\n",
        }

    def go(self, expiry: str) -> tuple[FindingCode, ...]:
        sources = self.sources()
        item = catalogue(frozenset({"dotmac_kernel.messaging", "dotmac_kernel.db"}))
        document = v2_document(
            sources,
            item,
            required_surfaces=REQUIRED_ONE,
            kernel_catalogue=binding(item),
            transitional_surfaces=self.transitional(expiry),
            declared_at="2026-09-01",
        )
        return report(document, sources, item)

    def test_an_expiry_already_passed_when_written_is_named(self) -> None:
        """The shape a COPIED declaration takes: the dates came with the file."""
        self.assertNamed(
            self.go("2026-08-31"),
            FindingCode.TRANSITIONAL_EXPIRY_PREDATES_DECLARATION,
        )

    def test_an_expiry_on_the_declaration_day_is_a_near_miss(self) -> None:
        self.assertSilent(
            self.go("2026-09-01"),
            FindingCode.TRANSITIONAL_EXPIRY_PREDATES_DECLARATION,
        )

    def test_a_future_expiry_is_the_admit_control(self) -> None:
        codes = self.go("2026-09-30")
        self.assertSilent(codes, FindingCode.TRANSITIONAL_EXPIRY_PREDATES_DECLARATION)
        self.assertClean(codes)


class ThePlatformSubject(Base):
    """A BOUNDED REGRESSION EXAMPLE built from a real product's measured surface.

    **It is not acceptance evidence, and it must not be read as any.** The
    actual acceptance proof is Platform #181's runner over Platform's LIVE
    source, in Platform's own CI, against a declaration Platform wrote. What
    this class has is a fixture: 85 facts measured once, at one pinned
    revision, replayed from a JSON file. It proves the contract does not refuse
    a real product's shape and it catches a regression against that shape. It
    cannot prove Platform is enrolled, cannot prove the fixture still describes
    Platform's current source, and does not become acceptance by being green.

    That distinction is stated here rather than left implied because the
    previous version of this class read as acceptance and one of its arms
    carried a claim it had never checked -- see
    `test_every_root_facade_symbol_is_one_the_a102_root_publishes` for what
    that cost.

    Read the module docstring for what the subject establishes generally and
    the three things it does not. The short form: the contract admits a real
    product's shape, and Platform's declaration remains Platform's to write.
    """

    def load(self) -> dict[str, Any]:
        return json.loads(
            (FIXTURES / "platform-kernel-surface.json").read_text(encoding="utf-8")
        )

    def kernel(self) -> dict[str, Any]:
        """The REAL dotmac-kernel catalogue at a102, not one derived from use.

        Until 2026-09-06 this class built its catalogue as
        `catalogue(frozenset(observed_modules))` -- the supported list WAS the
        set of modules Platform imported. A catalogue derived from the
        observation can never report an unpublished surface, because everything
        observed is in it by construction; it also silently placed the bare
        `dotmac_kernel` into `supported`, which is precisely the edit Michael
        ruled out. That is why this admit control was green while Platform's
        real enrolment went red against the same source.
        """
        return json.loads(
            (FIXTURES / "kernel-a102-catalogue.json").read_text(encoding="utf-8")
        )

    def catalogue_of(self, kernel: dict[str, Any]) -> KernelSurfaceCatalogue:
        """The a102 catalogue as a `KernelSurfaceCatalogue`. One builder.

        Three lists, three publication authorities, none of them derived from
        another -- which is the whole point of reading them from the Kernel
        rather than from a product's imports.
        """
        return catalogue(
            frozenset(kernel["supported_modules"]),
            version=kernel["version"],
            revision=kernel["revision"],
            internal=frozenset(kernel["internal_modules"]),
            root_exports=frozenset(kernel["root_exports"]),
        )

    def sources(self, fixture: dict[str, Any]) -> dict[PurePosixPath, str]:
        """One import statement per measured fact.

        Synthesised, and labelled synthesised. What is real is the SET of
        `(path, module, symbols)` facts; the statements are the smallest source
        that reproduces it.

        Synthesised from `bindings`, which carries BOTH halves of each import:
        the name as the Kernel spells it and the name the file bound it to. So
        an aliased fact synthesises an ALIASED statement, and the surface these
        sources reproduce is the one Platform actually wrote -- canonical
        identity and local alias together.

        That is a change from the first regeneration, which emitted every name
        unaliased and so could not reproduce the aliased shape at all. Three of
        Platform's imports are aliased; under the old synthesis all three came
        out as plain imports, which is precisely the flattening
        `dmg-kernel-surface-v2` exists to stop.
        """
        by_path: dict[PurePosixPath, list[str]] = {}
        for fact in fixture["facts"]:
            names = ", ".join(
                binding["kernel"]
                if binding["kernel"] == binding["local"]
                else f"{binding['kernel']} as {binding['local']}"
                for binding in sorted(
                    fact["bindings"], key=lambda item: (item["kernel"], item["local"])
                )
            )
            statement = f"from {fact['module']} import {names}"
            by_path.setdefault(PurePosixPath(fact["path"]), []).append(statement)
        return {
            path: "\n".join(sorted(lines)) + "\n" for path, lines in by_path.items()
        }

    def root_alias(self, fixture: dict[str, Any]) -> dict[str, Any]:
        """The one alias on the bare `dotmac_kernel`, chosen by MODULE.

        Not `known_aliases[0]`. The list now holds three, and an index would
        silently start naming a different alias the next time the fixture is
        regenerated -- a test that goes on passing about something else. The
        "exactly one" assertion is the non-vacuity half: if a second root alias
        ever appears, this fails rather than picking one.
        """
        found = [
            alias
            for alias in fixture["known_aliases"]
            if alias["module"] == "dotmac_kernel"
        ]
        self.assertEqual(1, len(found), found)
        return dict(found[0])

    def test_the_fixture_still_carries_the_facts_it_was_measured_for(self) -> None:
        """A fixture nobody checks is a number somebody typed, one level out.

        These are the counts the brief supplied and this suite re-derived on
        2026-09-06. If the fixture is regenerated against a later Platform
        revision and the counts move, the change is visible here rather than
        silently altering what the admit control below admits.
        """
        fixture = self.load()
        self.assertEqual(
            "f8865b1a43a6d6769d5fa3a3ab3eddfdf296cffb", fixture["revision"]
        )
        modules = {fact["module"] for fact in fixture["facts"]}
        symbols = {
            (fact["module"], symbol)
            for fact in fixture["facts"]
            for symbol in fact["symbols"]
        }
        self.assertEqual(17, len(modules), sorted(modules))
        self.assertEqual(85, len(symbols))
        db = [fact for fact in fixture["facts"] if fact["module"] == "dotmac_kernel.db"]
        self.assertEqual(11, len(db))
        self.assertEqual(14, sum(len(fact["symbols"]) for fact in db))
        self.assertIn(
            "src/vendor_cp/rotation_runtime_oracle.pyprogram",
            {fact["path"] for fact in db},
            "the eleventh site is not a .py file and is the reason a "
            "suffix-based sweep reported ten",
        )

    def declaration(
        self, fixture: dict[str, Any], sources: dict[PurePosixPath, str]
    ) -> tuple[dict[str, Any], KernelSurfaceCatalogue]:
        modules = sorted({fact["module"] for fact in fixture["facts"]})
        kernel = self.kernel()
        item = self.catalogue_of(kernel)
        first_use = {
            module: sorted(
                fact["path"] for fact in fixture["facts"] if fact["module"] == module
            )[0]
            for module in modules
        }
        db_baseline = sorted(
            (
                {"path": fact["path"], "symbol": symbol}
                for fact in fixture["facts"]
                if fact["module"] == "dotmac_kernel.db"
                for symbol in fact["symbols"]
            ),
            key=lambda entry: (entry["path"], entry["symbol"]),
        )
        document = v2_document(
            sources,
            item,
            declared_at="2026-09-06",
            kernel_catalogue=binding(item),
            required_surfaces=[
                {
                    "module": module,
                    "floor": "0.1.0a98",
                    "proven_by": first_use[module],
                }
                for module in modules
                if module != "dotmac_kernel.db"
            ],
            transitional_surfaces=[
                {
                    "module": "dotmac_kernel.db",
                    "owner": "Vendor Control Plane runtime owner",
                    "expiry": "2026-09-30",
                    "retirement_issue": (
                        "michaelayoade/dotmac_platform_control_plane#179"
                    ),
                    "replacement": "the kernel's request-scoped platform session",
                    "baseline": db_baseline,
                }
            ],
        )
        return document, item

    def test_the_contract_admits_a_real_products_shape(self) -> None:
        """The admit control this whole change needed, and the one #81 lacked.

        A rule observed only refusing is indistinguishable from one that
        refuses everything. Seventeen classified surfaces, a fourteen-pair
        retirement baseline against a real issue and a real date, an effective
        floor of `0.1.0a98`, two real pin sites and the real wheel digest out
        of Platform's own lock -- measured against the REAL a102 catalogue
        rather than one derived from Platform's own imports.

        NO findings: all 85 measured symbol facts, all 16 submodules and all 28
        root symbols are admitted by the real a102 catalogue.

        Two separate things had to be true before this could be clean, and
        neither was reached by adjusting anything to get here. The catalogue
        stopped being `frozenset(observed_modules)` -- which published whatever
        Platform imported, including the bare `dotmac_kernel`, and is why this
        was green while Platform's real enrolment was red. And the fixture
        stopped recording LOCAL bound names, which had made Platform's alias
        for `UndeclaredCapabilityError` look like a name the Kernel does not
        publish.
        """
        fixture = self.load()
        sources = self.sources(fixture)
        document, item = self.declaration(fixture, sources)
        self.assertClean(report(document, sources, item))

    def test_submodules_reached_through_the_root_are_admitted(self) -> None:
        """`from dotmac_kernel import audit` binds a SUPPORTED module.

        Platform's `alembic/env.py` writes exactly this for three names. They
        are in no `__all__` -- they are modules, not curated symbols -- and
        refusing them would refuse a published surface for the syntax used to
        reach it. Named here rather than left implicit in the count above,
        because this is a second publication authority and a reader must not
        have to infer that it was consulted.
        """
        kernel = self.kernel()
        for name in ("audit", "models_platform", "settings_models"):
            with self.subTest(name=name):
                self.assertNotIn(name, kernel["root_exports"])
                self.assertIn(f"dotmac_kernel.{name}", kernel["supported_modules"])
        item = self.catalogue_of(kernel)
        sources = {
            PurePosixPath("alembic/env.py"): (
                "from dotmac_kernel import audit, models_platform, settings_models\n"
            )
        }
        required = [
            {
                "module": "dotmac_kernel",
                "floor": "0.1.0a98",
                "proven_by": "alembic/env.py",
            }
        ]
        self.assertClean(
            report(
                v2_document(sources, item, required_surfaces=required),
                sources,
                item,
            )
        )

    def test_an_internal_submodule_through_the_root_is_still_refused(self) -> None:
        """The near-miss that keeps the second authority from being a hole.

        `dotmac_kernel._transactions` is an INTERNAL module. Admitting a root
        symbol on `known` rather than on `supported` would let it through, and
        it would escape the private-surface arm as well -- that arm reads
        MODULE path components, and the module recorded for this statement is
        the bare root, so it never sees the symbol.
        """
        kernel = self.kernel()
        self.assertIn("dotmac_kernel._transactions", kernel["internal_modules"])
        item = self.catalogue_of(kernel)
        sources = {
            PurePosixPath("app/x.py"): "from dotmac_kernel import _transactions\n"
        }
        required = [
            {"module": "dotmac_kernel", "floor": "0.1.0a98", "proven_by": "app/x.py"}
        ]
        self.assertNamed(
            report(
                v2_document(sources, item, required_surfaces=required), sources, item
            ),
            FindingCode.ROOT_SYMBOL_UNEXPORTED,
        )

    def test_the_platform_alias_is_admitted_on_the_kernels_name(self) -> None:
        """The alias admit control. Platform's local name, the Kernel's verdict.

        `src/vendor_cp/offers/catalog.py` writes
        `from dotmac_kernel import UndeclaredCapabilityError as
        KernelUndeclaredCapabilityError` -- Platform disambiguating the
        Kernel's error from its own. The Kernel publishes
        `UndeclaredCapabilityError` at the a102 root and publishes no
        `Kernel`-prefixed name at all.

        Kept as its own subject even though the synthesis now carries aliases:
        it drives the single statement in isolation with a `required_surfaces`
        floor proven by that file, which the whole-fixture admit control does
        not do.

        The refusal was NOT weakened to get here and no name was added to the
        Kernel: the fixture was recording local names, and it now records
        canonical ones.
        """
        kernel = self.kernel()
        alias = self.root_alias(self.load())
        self.assertEqual("UndeclaredCapabilityError", alias["kernel_name"])
        self.assertEqual("KernelUndeclaredCapabilityError", alias["local_name"])
        self.assertIn(alias["kernel_name"], kernel["root_exports"])
        self.assertNotIn(alias["local_name"], kernel["root_exports"])

        item = self.catalogue_of(kernel)
        path = PurePosixPath(alias["path"])
        sources = {
            path: (
                f"from dotmac_kernel import {alias['kernel_name']} as "
                f"{alias['local_name']}\n"
            )
        }
        required = [
            {
                "module": "dotmac_kernel",
                "floor": "0.1.0a98",
                "proven_by": path.as_posix(),
            }
        ]
        self.assertClean(
            report(
                v2_document(sources, item, required_surfaces=required), sources, item
            )
        )

    def test_the_local_half_of_that_alias_is_still_refused(self) -> None:
        """The paired near-miss, and the reason the admit control above is not
        an exemption.

        Had the alias been "fixed" by adding `KernelUndeclaredCapabilityError`
        to the Kernel's exports -- the move that was refused -- this would go
        quiet. The Kernel's name is admitted; Platform's local name, asked of
        the Kernel, is not.
        """
        kernel = self.kernel()
        alias = self.root_alias(self.load())
        item = self.catalogue_of(kernel)
        sources = {
            PurePosixPath("x.py"): f"from dotmac_kernel import {alias['local_name']}\n"
        }
        required = [
            {"module": "dotmac_kernel", "floor": "0.1.0a98", "proven_by": "x.py"}
        ]
        self.assertNamed(
            report(
                v2_document(sources, item, required_surfaces=required), sources, item
            ),
            FindingCode.ROOT_SYMBOL_UNEXPORTED,
        )

    def test_every_root_facade_symbol_is_one_the_a102_root_publishes(self) -> None:
        """ROOT-FAÇADE enforcement only. The name says exactly that, now.

        It was called `test_the_fixture_records_canonical_kernel_names`, and
        that name claimed the whole fixture. It never checked the whole
        fixture: it filters to `module == "dotmac_kernel"`, so it judges the
        root façade and nothing else -- the only Kernel surface with a
        published name list to judge against. `SUPPORTED_MODULES` enumerates
        module names, not the exports inside them, so a submodule symbol has no
        catalogue to be checked against and this arm cannot reach one.

        The cost of the wider name was concrete. Two of Platform's three
        aliases are on submodules; both stayed recorded under their LOCAL names
        through a regeneration that announced itself as canonical, and this
        test passed the whole time. `#83` carries the wider claim in a merged
        pull request; the claim it actually proved is this one.

        Submodule aliases are covered by
        `test_the_regeneration_preserved_every_alias_rather_than_flattening_it`,
        which needs no name list because it compares the fixture with itself in
        both directions.
        """
        fixture = self.load()
        kernel = self.kernel()
        unresolved = sorted(
            {
                symbol
                for fact in fixture["facts"]
                if fact["module"] == "dotmac_kernel"
                for symbol in fact["symbols"]
                if symbol not in kernel["root_exports"]
                and f"dotmac_kernel.{symbol}" not in kernel["supported_modules"]
            }
        )
        self.assertEqual([], unresolved)
        self.assertIn("symbol_name_convention", fixture)

    def test_the_regeneration_preserved_every_alias_rather_than_flattening_it(
        self,
    ) -> None:
        """Two-directional, and that is the whole point of it.

        A regeneration that recorded canonical names and DROPPED the aliases
        would satisfy every arm above and leave the fixture unable to express
        the defect `dmg-kernel-surface-v2` closes -- Platform's surface would
        look, to this fixture, like a product that aliases nothing.

        So: every aliased binding inline in `facts` is listed in
        `known_aliases`, AND every entry in `known_aliases` is a binding that
        really appears inline. An allowlist that may only grow stops describing
        the file; one that is only checked inward-out cannot catch an alias
        that was flattened away.
        """
        fixture = self.load()
        inline = {
            (fact["path"], fact["module"], binding["kernel"], binding["local"])
            for fact in fixture["facts"]
            for binding in fact["bindings"]
            if binding["kernel"] != binding["local"]
        }
        listed = {
            (alias["path"], alias["module"], alias["kernel_name"], alias["local_name"])
            for alias in fixture["known_aliases"]
        }
        self.assertEqual(listed, inline)
        # Non-vacuity: an empty set equals an empty set, and would pass this
        # while proving the file carries no alias information at all.
        #
        # THREE, pinned twice. `alias_count` is the fixture's own declared
        # number and the literal is this suite's, so a regeneration that found
        # a fourth alias -- or lost one -- fails here rather than silently
        # changing what the class demonstrates. #83 recorded ONE and claimed
        # the set was complete; that is the error this pair exists to stop
        # repeating.
        self.assertEqual(3, len(inline), sorted(inline))
        self.assertEqual(fixture["alias_count"], len(inline))
        self.assertEqual(
            {
                ("alembic/env.py", "dotmac_kernel.messaging", "models"),
                (
                    "src/vendor_cp/migrations.py",
                    "dotmac_kernel.migrations",
                    "versions_dir",
                ),
                (
                    "src/vendor_cp/offers/catalog.py",
                    "dotmac_kernel",
                    "UndeclaredCapabilityError",
                ),
            },
            {(path, module, kernel) for path, module, kernel, _ in inline},
        )

    def test_the_two_aliases_the_first_regeneration_missed_are_recorded(
        self,
    ) -> None:
        """Named individually, because "three aliases" is a count and these are
        the two that were WRONG.

        Both were stored under the name Platform bound them to rather than the
        name the Kernel publishes: `dotmac_kernel.messaging` `models` as
        `messaging_models`, and `dotmac_kernel.migrations` `versions_dir` as
        `kernel_versions_dir`. The second is the sharpest instance of the
        defect -- seven distributions in that one file publish `versions_dir`
        and Platform prefixes every one of them -- so `kernel_versions_dir` was
        a fact about Platform's naming scheme filed as a fact about the Kernel.
        """
        by_key = {
            (fact["path"], fact["module"]): fact["bindings"]
            for fact in self.load()["facts"]
        }
        self.assertIn(
            {"kernel": "models", "local": "messaging_models"},
            by_key[("alembic/env.py", "dotmac_kernel.messaging")],
        )
        self.assertIn(
            {"kernel": "versions_dir", "local": "kernel_versions_dir"},
            by_key[("src/vendor_cp/migrations.py", "dotmac_kernel.migrations")],
        )

    def test_symbols_is_a_projection_of_bindings_and_not_a_second_record(
        self,
    ) -> None:
        """`bindings` is authoritative; `symbols` is derived from it.

        Two independently authored lists in one file drift, and the drift is
        invisible because each half looks right on its own. This asserts there
        is only one record: `symbols` is exactly the sorted distinct KERNEL
        half of `bindings`, which is what lets the v1-shaped arms keep reading
        `symbols` unchanged.
        """
        for fact in self.load()["facts"]:
            self.assertEqual(
                sorted({binding["kernel"] for binding in fact["bindings"]}),
                fact["symbols"],
                fact["path"],
            )

    def test_the_synthesis_reproduces_platforms_aliases(self) -> None:
        """The synthesis carries the alias, proved on the emitted source.

        `sources()` is what every admit control in this class measures. If it
        emitted unaliased statements -- as it did before this regeneration --
        the whole class would be exercising a surface Platform does not have.
        """
        fixture = self.load()
        emitted = self.sources(fixture)
        self.assertIn(
            "versions_dir as kernel_versions_dir",
            emitted[PurePosixPath("src/vendor_cp/migrations.py")],
        )
        self.assertIn(
            "models as messaging_models",
            emitted[PurePosixPath("alembic/env.py")],
        )
        self.assertIn(
            "UndeclaredCapabilityError as KernelUndeclaredCapabilityError",
            emitted[PurePosixPath("src/vendor_cp/offers/catalog.py")],
        )

    def test_a_kernel_symbol_swap_behind_the_same_alias_moves_only_v2(self) -> None:
        """The defect and its closure, on a real product's real imports.

        Platform's three aliased statements, each rewritten so a DIFFERENT
        Kernel symbol hides behind the unchanged local name. v1 records local
        names, and no local name moved, so v1's digest does not move -- the
        declaration would go on matching a surface that changed. v2's does.

        The obvious probe -- flattening the aliases away -- proves the wrong
        thing and was measured before being discarded: flattening changes the
        LOCAL names too, so v1 moves as well and the comparison shows nothing.
        Holding the local name fixed is what isolates the defect.
        """
        aliased = self.sources(self.load())
        swapped = {
            path: re.sub(r"(\w+) as (\w+)", r"Other\1 as \2", text)
            for path, text in aliased.items()
        }
        self.assertNotEqual(aliased, swapped)
        # Non-vacuity: the rewrite really touched Platform's three aliases.
        self.assertEqual(
            3,
            sum(
                line.count(" as ")
                for text in swapped.values()
                for line in text.splitlines()
                if "Other" in line
            ),
        )
        self.assertEqual(
            surface_digest(facts_of(aliased)), surface_digest(facts_of(swapped))
        )
        self.assertNotEqual(
            surface_identity_digest(surface_identity_facts(aliased)),
            surface_identity_digest(surface_identity_facts(swapped)),
        )

    # ── the collision the second publication authority created ──────────────
    #
    # `facet_principal` is BOTH: `dotmac_kernel.facet_principal` is a supported
    # SUBMODULE, and `facet_principal` is a NAME in the root's `__all__` (the
    # module defines the object and the root re-exports it). It is the only
    # name at a102 holding both roles -- verified in the first test below
    # rather than asserted -- and it is the ambiguity the submodule-through-root
    # arm made reachable.
    #
    # NOTE: the review proposed `settings` for this. It does not hold both
    # roles: `settings` is in `__all__` (it is the Settings INSTANCE, imported
    # from `dotmac_kernel.config`) and there is no `dotmac_kernel/settings.py`
    # in the a102 tree at all, so `dotmac_kernel.settings` is in no module
    # list. Asserting on it would have proved the opposite of the intended
    # property. `settings` is used below as the near-miss instead, which is
    # what it is actually good for.

    COLLIDING = "facet_principal"

    def test_the_colliding_name_really_holds_both_roles(self) -> None:
        """Non-vacuity for the four tests below.

        If this name ever stops being both a supported module and a root
        export, those tests stop testing a collision and start testing two
        unrelated things while still passing.
        """
        kernel = self.kernel()
        self.assertIn(f"dotmac_kernel.{self.COLLIDING}", kernel["supported_modules"])
        self.assertIn(self.COLLIDING, kernel["root_exports"])
        both = sorted(
            name
            for name in kernel["root_exports"]
            if f"dotmac_kernel.{name}" in kernel["supported_modules"]
        )
        self.assertEqual([self.COLLIDING], both)

    def collide(self, statement: str, module: str) -> tuple[FindingCode, ...]:
        """Measure one statement, classifying exactly `module` and nothing else.

        Classifying ONE surface is what gives these tests teeth: if the
        statement were classified as the other surface, the declaration would
        not cover what was measured and `kernel.surface.unclassified` fires.
        """
        item = self.catalogue_of(self.kernel())
        sources = {PurePosixPath("app/x.py"): statement}
        required = [{"module": module, "floor": "0.1.0a98", "proven_by": "app/x.py"}]
        return report(
            v2_document(sources, item, required_surfaces=required), sources, item
        )

    def test_the_dotted_form_is_classified_as_the_submodule(self) -> None:
        self.assertClean(
            self.collide(
                f"import dotmac_kernel.{self.COLLIDING}\n",
                f"dotmac_kernel.{self.COLLIDING}",
            )
        )

    def test_the_from_root_form_is_classified_as_the_root_export(self) -> None:
        self.assertClean(
            self.collide(
                f"from dotmac_kernel import {self.COLLIDING}\n", "dotmac_kernel"
            )
        )

    def test_the_two_forms_are_not_interchangeable(self) -> None:
        """The collision must not let one declaration entry cover both shapes.

        This is the half that would go quiet if the root and the submodule were
        ever conflated into one surface: each form is measured as the surface
        it actually names, so classifying the OTHER one leaves the measured
        import unclassified.
        """
        self.assertNamed(
            self.collide(f"import dotmac_kernel.{self.COLLIDING}\n", "dotmac_kernel"),
            FindingCode.SURFACE_UNCLASSIFIED,
        )
        self.assertNamed(
            self.collide(
                f"from dotmac_kernel import {self.COLLIDING}\n",
                f"dotmac_kernel.{self.COLLIDING}",
            ),
            FindingCode.SURFACE_UNCLASSIFIED,
        )

    def test_both_aliased_forms_keep_their_canonical_kernel_identity(self) -> None:
        """The clause with teeth: an alias changes the LOCAL name and nothing
        the classification depends on.

        On the root path this is `names` vs `bound`, already proven elsewhere.
        On the SUBMODULE path it has never been exercised: `import
        dotmac_kernel.facet_principal as fp` binds `fp`, and if the module were
        ever read off the `as` clause the measured surface would become `fp` --
        a name in no catalogue, classified by nothing. Both forms are asserted
        here so neither half of the distinction can regress.
        """
        self.assertClean(
            self.collide(
                f"import dotmac_kernel.{self.COLLIDING} as fp\n",
                f"dotmac_kernel.{self.COLLIDING}",
            )
        )
        self.assertClean(
            self.collide(
                f"from dotmac_kernel import {self.COLLIDING} as fp\n",
                "dotmac_kernel",
            )
        )
        # And the aliases really are different local names, so the two clean
        # results above are not two spellings of one statement.
        self.assertNotEqual(
            f"import dotmac_kernel.{self.COLLIDING} as fp",
            f"from dotmac_kernel import {self.COLLIDING} as fp",
        )

    def test_a_root_export_that_is_not_a_module_is_not_importable_as_one(
        self,
    ) -> None:
        """The near-miss keeping the two authorities apart, on the name the
        review proposed for the collision.

        `settings` is a root export and is NOT a module: there is no
        `dotmac_kernel/settings.py` at a102. So the root authority must not
        leak into the submodule path -- `import dotmac_kernel.settings` names
        something the Kernel does not publish, and a run that admitted it would
        be reading `__all__` to answer a question about modules.
        """
        kernel = self.kernel()
        self.assertIn("settings", kernel["root_exports"])
        self.assertNotIn("dotmac_kernel.settings", kernel["supported_modules"])
        self.assertNotIn("dotmac_kernel.settings", kernel["internal_modules"])
        self.assertNamed(
            self.collide("import dotmac_kernel.settings\n", "dotmac_kernel.settings"),
            FindingCode.SURFACE_UNKNOWN,
        )

    def test_the_eleventh_site_is_inside_the_measured_surface(self) -> None:
        """Non-vacuity for the arm above: the hard case is actually in it.

        A `.pyprogram` importer that the admit control quietly dropped would
        make the pass a pass over the easy ten.
        """
        fixture = self.load()
        sources = self.sources(fixture)
        self.assertIn(
            PurePosixPath("src/vendor_cp/rotation_runtime_oracle.pyprogram"), sources
        )
        facts = facts_of(sources)
        self.assertIn(
            "src/vendor_cp/rotation_runtime_oracle.pyprogram",
            {
                fact.path.as_posix()
                for fact in facts
                if fact.module == "dotmac_kernel.db"
            },
        )

    def test_dropping_the_eleventh_site_from_the_baseline_is_named(self) -> None:
        """The planted defect against the real subject, not a toy one."""
        fixture = self.load()
        sources = self.sources(fixture)
        document, item = self.declaration(fixture, sources)
        transitional = [dict(document["transitional_surfaces"][0])]
        transitional[0]["baseline"] = [
            entry
            for entry in transitional[0]["baseline"]
            if not entry["path"].endswith(".pyprogram")
        ]
        document["transitional_surfaces"] = transitional
        codes = report(document, sources, item)
        self.assertNamed(codes, FindingCode.TRANSITIONAL_BASELINE_DRIFT)

    def test_the_retirement_expiry_is_judged_against_the_run_date(self) -> None:
        """Issue #179 expires 2026-09-30. A run after it must say so."""
        fixture = self.load()
        sources = self.sources(fixture)
        document, item = self.declaration(fixture, sources)
        codes = report(document, sources, item, as_of=date(2026, 10, 1))
        self.assertNamed(codes, FindingCode.TRANSITIONAL_EXPIRED)

    def test_a_run_on_the_expiry_day_is_the_near_miss(self) -> None:
        fixture = self.load()
        sources = self.sources(fixture)
        document, item = self.declaration(fixture, sources)
        codes = report(document, sources, item, as_of=date(2026, 9, 30))
        self.assertSilent(codes, FindingCode.TRANSITIONAL_EXPIRED)


class EveryNewCodeIsReachable(unittest.TestCase):
    """ADR 0041: a name with no check and a check with no name are one defect.

    A finding code nothing can produce is a vocabulary entry that reads as
    coverage. Every code v2 added is asserted to have been produced by at least
    one test above, by producing it here.
    """

    V2_CODES = frozenset(
        {
            FindingCode.SOURCE_SURFACE_DRIFT,
            FindingCode.SURFACE_NONE_OBSERVED,
            FindingCode.PREDECESSOR_NOT_ANCESTOR,
            FindingCode.PREDECESSOR_UNVERIFIABLE,
            FindingCode.CATALOGUE_DISAGREES,
            FindingCode.CATALOGUE_UNBOUND,
            FindingCode.CATALOGUE_EMPTY,
            FindingCode.REQUIRED_UNPUBLISHED,
            FindingCode.ROOT_EXPORTS_UNOBSERVED,
            FindingCode.ROOT_SYMBOL_UNEXPORTED,
            FindingCode.REQUIRED_UNUSED,
            FindingCode.SURFACE_UNCLASSIFIED,
            FindingCode.REQUIRED_FLOOR_UNSATISFIED,
            FindingCode.REQUIRED_FLOOR_UNORDERABLE,
            FindingCode.REQUIRED_PROOF_UNREAD,
            FindingCode.REQUIRED_PROOF_SILENT,
            FindingCode.DECLARED_AT_AHEAD,
            FindingCode.TRANSITIONAL_EXPIRY_PREDATES_DECLARATION,
        }
    )

    def test_the_enumeration_matches_the_codes_this_module_names(self) -> None:
        """Two-directional. A code added without a test here fails this."""
        text = Path(__file__).read_text(encoding="utf-8")
        named = {code for code in FindingCode if f"FindingCode.{code.name}" in text}
        self.assertEqual(
            self.V2_CODES,
            self.V2_CODES & named,
            "a v2 code is enumerated here and never named by a test",
        )

    def test_every_v2_code_is_an_error_not_a_notice(self) -> None:
        """The successor's claim is that these are READ, and a notice is not read.

        `DECLARATION_FIELDS_UNEVALUATED` is the notice, and it is deliberately
        not in the set: it discloses an absence rather than reporting a fact.
        """
        self.assertNotIn(FindingCode.DECLARATION_FIELDS_UNEVALUATED, self.V2_CODES)
        codes = report(
            v2_document(ONE_IMPORT, ONE_MODULE),
            ONE_IMPORT,
            ONE_MODULE,
            predecessor=None,
        )
        findings = evaluate(
            KernelAdoptionInputs(
                sources=ONE_IMPORT,
                catalogue=ONE_MODULE,
                declaration=DeclarationPresent(
                    parse_any_declaration(v2_document(ONE_IMPORT, ONE_MODULE))
                ),
                as_of=TODAY,
                pin_sites=(),
                predecessor=None,
            )
        ).findings
        self.assertIn(FindingCode.PREDECESSOR_UNVERIFIABLE, codes)
        for finding in findings:
            if finding.code in self.V2_CODES:
                self.assertIs(Severity.ERROR, finding.severity, finding.code.value)


class TheSuccessorHasNoUnreadField(unittest.TestCase):
    """The property v2 exists for, asserted structurally rather than reviewed.

    Every field `KernelAdoptionDeclarationV2` carries is named by at least one
    arm in the engine. This is the guard against v2 becoming v1: a field added
    to the dataclass without an arm reading it fails here.
    """

    #: Field -> the engine function that reads it. Enumerated, so a new field
    #: fails until somebody says which arm reads it -- and a field whose named
    #: reader stops mentioning it fails too.
    READERS = {
        "contract": "_check_v2",
        "applicability": "_check_v2",
        "declared_at": "_check_declared_at",
        "source_predecessor": "_check_predecessor",
        "not_applicable_reason": "_check_v2",
        "source_surface": "_check_source_surface",
        "kernel_catalogue": "_check_catalogue_binding",
        "required_surfaces": "_check_required_surfaces",
        "prohibited_surfaces": "_check_applicable_common",
        "transitional_surfaces": "_check_applicable_common",
    }

    def test_every_declared_field_has_a_named_reader(self) -> None:
        import dataclasses

        fields = {f.name for f in dataclasses.fields(KernelAdoptionDeclarationV2)}
        self.assertEqual(fields, set(self.READERS))

    def test_every_named_reader_exists_in_the_engine(self) -> None:
        from kernel_adoption_control import engine

        for field, reader in self.READERS.items():
            self.assertTrue(hasattr(engine, reader), f"{field} -> {reader}")


# ── the root façade ──────────────────────────────────────────────────────────
#
# `SUPPORTED_MODULES` and `INTERNAL_MODULES` enumerate SUBMODULES; the bare
# `dotmac_kernel` is in neither. Read at `dotmac-kernel-v0.1.0a102`, peeled
# 7a3c128b06eaba09784a9d8409d036169b3caa68, they carry 89 and 4 names and
# neither list contains the root. So before the root was normalised, a product
# importing it had NO reachable clean verdict: declaring it required reported
# `kernel.required.unpublished`, and omitting it reported
# `kernel.surface.unclassified`.
#
# The root's publication authority is its own `__all__`, carried on the
# catalogue as `root_exports` and bound into `catalogue_digest`.

#: A root catalogue. `Party` and `resolve_value` are real a102 root exports;
#: `_Internal` is deliberately NOT one, and neither is `NotAThing`.
ROOT_EXPORTS = frozenset({"Party", "resolve_value", "settings"})
ROOT_MODULE = catalogue(
    frozenset({"dotmac_kernel.messaging"}), root_exports=ROOT_EXPORTS
)
#: The same Kernel, observed by an observer that never read `__all__`.
ROOT_UNOBSERVED = catalogue(frozenset({"dotmac_kernel.messaging"}))

ROOT_PUBLIC = {PurePosixPath("src/app/service.py"): "from dotmac_kernel import Party\n"}
ROOT_PRIVATE = {
    PurePosixPath("src/app/service.py"): "from dotmac_kernel import _Internal\n"
}
ROOT_NONEXISTENT = {
    PurePosixPath("src/app/service.py"): "from dotmac_kernel import NotAThing\n"
}
ROOT_ALIASED = {
    PurePosixPath("src/app/service.py"): "from dotmac_kernel import Party as P\n"
}
#: An alias whose LOCAL name is a public export and whose KERNEL name is not.
#: The near-miss for resolving on the wrong side of `as`: an arm asking `bound`
#: would admit this, because `Party` is in `__all__`.
ROOT_ALIASED_TO_A_PUBLIC_NAME = {
    PurePosixPath(
        "src/app/service.py"
    ): "from dotmac_kernel import _Internal as Party\n"
}
ROOT_MODULE_ONLY = {PurePosixPath("src/app/service.py"): "import dotmac_kernel\n"}

#: The root declared as a required surface. This is the classification that was
#: unreachable: `required` + root reported `kernel.required.unpublished`.
REQUIRED_ROOT = [
    {
        "module": "dotmac_kernel",
        "floor": "0.1.0a90",
        "proven_by": "src/app/service.py",
    }
]


class TheRootFacadeIsASeparatelyPublishedSurface(Base):
    """Defect 1. Exit 0 was unreachable for any product importing the root.

    Platform imports 28 symbols from `dotmac_kernel` directly. The engine
    recorded the module verbatim and asked the SUBMODULE lists about it, so
    both available classifications failed. The repair normalises the root as a
    published surface whose allowed names come from the installed artifact's
    `__all__` -- and the load-bearing half is that this is not a blanket pass.
    """

    def test_a_required_root_facade_is_no_longer_unpublished(self) -> None:
        """The admit control. Without it the five refusals below are
        indistinguishable from a rule that refuses every root import."""
        codes = report(
            v2_document(ROOT_PUBLIC, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_PUBLIC,
            ROOT_MODULE,
        )
        self.assertClean(codes)

    def test_the_defect_itself_the_root_had_no_reachable_verdict(self) -> None:
        """Both horns, planted together, against a catalogue with NO root
        exports -- which is exactly the pre-repair state, because before this
        change the field did not exist and no observer supplied it.

        Declaring the root required must not be answered by the submodule
        lists, and omitting it must still be unclassified. The first is the
        defect; the second is the arm that must stay awake.
        """
        omitted = report(
            v2_document(ROOT_PUBLIC, ROOT_UNOBSERVED),
            ROOT_PUBLIC,
            ROOT_UNOBSERVED,
        )
        self.assertNamed(omitted, FindingCode.SURFACE_UNCLASSIFIED)

    def test_a_public_export_is_admitted(self) -> None:
        codes = report(
            v2_document(ROOT_PUBLIC, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_PUBLIC,
            ROOT_MODULE,
        )
        self.assertSilent(codes, FindingCode.ROOT_SYMBOL_UNEXPORTED)
        self.assertSilent(codes, FindingCode.ROOT_EXPORTS_UNOBSERVED)

    def test_a_private_name_is_refused(self) -> None:
        codes = report(
            v2_document(ROOT_PRIVATE, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_PRIVATE,
            ROOT_MODULE,
        )
        self.assertNamed(codes, FindingCode.ROOT_SYMBOL_UNEXPORTED)

    def test_a_nonexistent_name_is_refused(self) -> None:
        """The same refusal as the private one, and deliberately so: the arm
        asks `__all__`, not the spelling. A leading underscore is not what
        decides it -- `_private_components` reads MODULE path components and
        returns nothing for the bare root, so the private-surface arm never
        sees a root symbol at all."""
        codes = report(
            v2_document(ROOT_NONEXISTENT, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_NONEXISTENT,
            ROOT_MODULE,
        )
        self.assertNamed(codes, FindingCode.ROOT_SYMBOL_UNEXPORTED)
        self.assertSilent(codes, FindingCode.SURFACE_PRIVATE)

    def test_an_aliased_public_import_is_resolved_on_the_kernels_name(self) -> None:
        codes = report(
            v2_document(ROOT_ALIASED, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_ALIASED,
            ROOT_MODULE,
        )
        self.assertClean(codes)

    def test_an_alias_cannot_launder_a_private_name_into_a_public_one(self) -> None:
        """The near-miss that proves the arm reads the far side of `as`.

        `from dotmac_kernel import _Internal as Party` binds the LOCAL name
        `Party`, which IS in `__all__`. An arm asking what the statement bound
        locally would admit it. The Kernel's name is `_Internal`, and that is
        the name admission is decided on.
        """
        codes = report(
            v2_document(
                ROOT_ALIASED_TO_A_PUBLIC_NAME,
                ROOT_MODULE,
                required_surfaces=REQUIRED_ROOT,
            ),
            ROOT_ALIASED_TO_A_PUBLIC_NAME,
            ROOT_MODULE,
        )
        self.assertNamed(codes, FindingCode.ROOT_SYMBOL_UNEXPORTED)

    def test_a_module_only_import_names_no_export_and_is_admitted(self) -> None:
        """`import dotmac_kernel` imports the package and names nothing.

        There is no symbol to admit or refuse, so the symbol arm is silent --
        and the module is still MEASURED, so the declaration still has to
        classify it. Both halves matter: silence without classification would
        be a root import that escaped the inventory.
        """
        codes = report(
            v2_document(ROOT_MODULE_ONLY, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_MODULE_ONLY,
            ROOT_MODULE,
        )
        self.assertClean(codes)

    def test_a_module_only_import_still_has_to_be_classified(self) -> None:
        """The other half. Silence on symbols is not silence on inventory."""
        codes = report(
            v2_document(ROOT_MODULE_ONLY, ROOT_MODULE),
            ROOT_MODULE_ONLY,
            ROOT_MODULE,
        )
        self.assertNamed(codes, FindingCode.SURFACE_UNCLASSIFIED)

    def test_an_observer_that_never_read_all_is_refused_not_admitted(self) -> None:
        """The vacuity guard on the whole arm.

        If an empty `root_exports` were read as "no list, admit anything", the
        eight tests above would all pass over a catalogue nobody populated and
        the arm would be decoration. An empty list is a stated absence whose
        repair is in the OBSERVER, and it refuses.
        """
        codes = report(
            v2_document(ROOT_PUBLIC, ROOT_UNOBSERVED, required_surfaces=REQUIRED_ROOT),
            ROOT_PUBLIC,
            ROOT_UNOBSERVED,
        )
        self.assertNamed(codes, FindingCode.ROOT_EXPORTS_UNOBSERVED)

    def test_a_submodule_import_never_reaches_the_root_arm(self) -> None:
        """The near-miss for the branch itself: normalising the root must not
        change how a submodule is classified."""
        codes = report(
            v2_document(ONE_IMPORT, ONE_MODULE, required_surfaces=REQUIRED_ONE),
            ONE_IMPORT,
            ONE_MODULE,
        )
        self.assertSilent(codes, FindingCode.ROOT_SYMBOL_UNEXPORTED)
        self.assertSilent(codes, FindingCode.ROOT_EXPORTS_UNOBSERVED)

    def test_the_root_exports_are_bound_into_the_catalogue_digest(self) -> None:
        """A widened `__all__` is a different catalogue.

        Without this, an observer could quietly grow the admitted set and the
        declaration would go on matching. The digest is the coordinate that
        makes it a reviewable edit.
        """
        widened = catalogue(
            frozenset({"dotmac_kernel.messaging"}),
            root_exports=ROOT_EXPORTS | {"NotAThing"},
        )
        codes = report(
            # The document binds the NARROW catalogue; the run supplies the
            # widened one.
            v2_document(ROOT_PUBLIC, ROOT_MODULE, required_surfaces=REQUIRED_ROOT),
            ROOT_PUBLIC,
            widened,
        )
        self.assertNamed(codes, FindingCode.CATALOGUE_DISAGREES)

    def test_two_catalogues_differing_only_in_root_exports_differ(self) -> None:
        """The digest sensitivity proof, taken directly rather than through a
        finding: a check over two identical inputs proves nothing about the
        input it is supposed to be sensitive to."""
        common = {
            "version": "0.1.0a102",
            "revision": KERNEL_REVISION,
            "supported": frozenset({"dotmac_kernel.db"}),
            "internal": frozenset(),
        }
        self.assertNotEqual(
            catalogue_digest(**common, root_exports=frozenset({"Party"})),
            catalogue_digest(**common, root_exports=frozenset({"Party", "settings"})),
        )
        # And the near-miss: same lists, same digest.
        self.assertEqual(
            catalogue_digest(**common, root_exports=frozenset({"Party"})),
            catalogue_digest(**common, root_exports=frozenset({"Party"})),
        )


#: v1's rendering and digest over a fixed fact set, taken from the code at
#: `298eaad` -- the revision BEFORE `dmg-kernel-surface-v2` existed -- and
#: pinned here as bytes. This is how "v1 was not redefined" is proved rather
#: than assumed: any edit to `SOURCE_SURFACE_ALGORITHM`, to `SurfaceFact
#: .render`, to the field or record separators, to the sort, or to the trailing
#: newline moves one of these two values and fails. A test that only compared
#: v1 with itself would pass over a v1 that had been rewritten in place.
V1_GOLDEN_RENDERING = (
    "dmg-kernel-surface-v1\n"
    "a.py\tdotmac_kernel\tY\t-\n"
    "b.py\tdotmac_kernel.db\tSession,get_session\t-\n"
)
V1_GOLDEN_DIGEST = (
    "sha256:eb8891b4adf10c36a0477f82383a241254f32801eb00c41bec65422d756bf3c4"
)
V1_GOLDEN_FACTS = frozenset(
    {
        SurfaceFact(
            path=PurePosixPath("a.py"),
            module="dotmac_kernel",
            symbols=("Y",),
            star=False,
        ),
        SurfaceFact(
            path=PurePosixPath("b.py"),
            module="dotmac_kernel.db",
            symbols=("Session", "get_session"),
            star=False,
        ),
    }
)

#: The defect, in the smallest source that exhibits it: one local name, two
#: different Kernel symbols behind it.
ALIASED_A = {PurePosixPath("a.py"): "from dotmac_kernel import A as Y\n"}
ALIASED_B = {PurePosixPath("a.py"): "from dotmac_kernel import B as Y\n"}


class CanonicalKernelIdentity(Base):
    """`dmg-kernel-surface-v2`: the Kernel's name and the local one, kept apart.

    v1 records the names an import BINDS LOCALLY, so `A as Y` and `B as Y`
    render identically and share a `source_surface` digest -- a declaration
    stays bound to a surface that changed. Enforcement was never affected: the
    arms re-derive from `_KernelImport.names`, the Kernel-side spelling, on
    every run. What was weakened is the declaration-to-source BINDING, and only
    for aliased imports.

    v1 is frozen and stays frozen. This class proves the new algorithm closes
    the defect, proves v1 was not quietly redefined on the way, and proves the
    two cannot be confused for each other -- and then proves the new digest is
    STABLE, because a rule demonstrated only in the "it moved" direction is
    indistinguishable from one whose value is simply not reproducible.
    """

    def digest(self, sources: dict[PurePosixPath, str]) -> str:
        return surface_identity_digest(surface_identity_facts(sources))

    def test_two_kernel_symbols_behind_one_local_name_now_differ(self) -> None:
        """The defect, closed. This is the whole subject of the change."""
        self.assertNotEqual(self.digest(ALIASED_A), self.digest(ALIASED_B))

    def test_v1_still_conflates_them_because_v1_was_not_redefined(self) -> None:
        """The other half. Without it, the test above could pass because v1 had
        been edited to disagree -- which is the outcome the freeze forbids."""
        self.assertEqual(
            surface_digest(facts_of(ALIASED_A)), surface_digest(facts_of(ALIASED_B))
        )

    def test_v1_renders_and_digests_exactly_what_it_did_before_v2_existed(
        self,
    ) -> None:
        """v1 unredefined, proved against bytes taken at `298eaad` rather than
        against v1's present self. See `V1_GOLDEN_RENDERING`."""
        self.assertEqual(V1_GOLDEN_RENDERING, render_surface(V1_GOLDEN_FACTS))
        self.assertEqual(V1_GOLDEN_DIGEST, surface_digest(V1_GOLDEN_FACTS))

    def test_neither_digest_can_be_read_as_the_other(self) -> None:
        """Domain separation, and that it is STRUCTURAL rather than a check.

        The assertion that the two digests differ is the weaker half: it would
        also hold for two algorithms that merely happened to disagree. The
        load-bearing half is the second block -- each rendering's FIRST LINE is
        its own algorithm's name, so the two preimages differ before any fact
        is rendered at all. There is no comparison here that could be deleted
        to make a v1 value verify as a v2 one.
        """
        facts_v1 = facts_of(ALIASED_A)
        facts_v2 = surface_identity_facts(ALIASED_A)
        self.assertNotEqual(surface_digest(facts_v1), surface_identity_digest(facts_v2))

        self.assertNotEqual(SOURCE_SURFACE_ALGORITHM, SOURCE_SURFACE_IDENTITY_ALGORITHM)
        self.assertEqual(
            SOURCE_SURFACE_ALGORITHM, render_surface(facts_v1).split("\n")[0]
        )
        self.assertEqual(
            SOURCE_SURFACE_IDENTITY_ALGORITHM,
            render_surface_identity(facts_v2).split("\n")[0],
        )

    def test_an_unaliased_surface_digests_the_same_twice(self) -> None:
        """Admit control. A digest that never repeats detects every change and
        binds nothing, and is indistinguishable from one that works."""
        sources = {
            PurePosixPath("a.py"): "from dotmac_kernel import A\n",
            PurePosixPath("b.py"): "from dotmac_kernel.db import Session\n",
        }
        self.assertEqual(self.digest(sources), self.digest(sources))
        self.assertEqual(self.digest(sources), self.digest(dict(sources)))

    def test_reordering_reformatting_and_a_comment_move_nothing(self) -> None:
        """The near-miss. A coordinate that refuses on a comment gets deleted,
        and v2 inherits v1's exclusions rather than tightening them."""
        plain = {
            PurePosixPath("a.py"): (
                "from dotmac_kernel import A\n"
                "from dotmac_kernel.db import Session, get_session\n"
            )
        }
        churned = {
            PurePosixPath("a.py"): (
                "# a comment that binds nothing\n"
                "from dotmac_kernel.db import (\n"
                "    get_session,\n"
                ")\n"
                "\n"
                "from dotmac_kernel import A\n"
                "from dotmac_kernel.db import Session\n"
            )
        }
        self.assertEqual(self.digest(plain), self.digest(churned))

    def test_the_local_name_a_product_writes_is_still_recoverable(self) -> None:
        """Distinguishing the two halves is not the same as keeping both.

        An algorithm that recorded only the Kernel's name would close the
        defect above and lose the alias, which is the fact Platform's
        `known_aliases` block exists to carry. Both halves are in the
        rendering, in one field, separated by a character neither can contain.
        """
        rendered = render_surface_identity(surface_identity_facts(ALIASED_A))
        self.assertIn("A>Y", rendered)
        self.assertNotIn("A>Y", render_surface(facts_of(ALIASED_A)))

    def test_the_platform_alias_that_bit_the_fixture_is_distinguishable(self) -> None:
        """The instance that was found, in its real shape.

        Platform binds the Kernel's `UndeclaredCapabilityError` to
        `KernelUndeclaredCapabilityError`. Under v1 that surface is
        indistinguishable from a product that aliased some OTHER Kernel error
        to the same local name; #83 repaired the fixture, not the rule.
        """
        real = {
            PurePosixPath("src/vendor_cp/offers/catalog.py"): (
                "from dotmac_kernel import "
                "UndeclaredCapabilityError as KernelUndeclaredCapabilityError\n"
            )
        }
        other = {
            PurePosixPath("src/vendor_cp/offers/catalog.py"): (
                "from dotmac_kernel import "
                "UnknownCapabilityError as KernelUndeclaredCapabilityError\n"
            )
        }
        self.assertEqual(
            surface_digest(facts_of(real)), surface_digest(facts_of(other))
        )
        self.assertNotEqual(self.digest(real), self.digest(other))

    def test_a_module_alias_records_the_module_as_its_kernel_identity(self) -> None:
        """`import dotmac_kernel.db as k` names a MODULE and no symbol.

        Recorded as the pair `dotmac_kernel.db>k` rather than dropped: the
        alias is a local name like any other, and the Kernel identity behind it
        is the module path. It cannot collide with a `from` import, which
        renders under a different `module` field.
        """
        facts = surface_identity_facts(
            {PurePosixPath("b.py"): "import dotmac_kernel.db as k\n"}
        )
        self.assertEqual(
            (SurfaceBinding(kernel="dotmac_kernel.db", local="k"),),
            next(iter(facts)).bindings,
        )
        self.assertNotEqual(
            self.digest({PurePosixPath("b.py"): "import dotmac_kernel.db as k\n"}),
            self.digest({PurePosixPath("b.py"): "import dotmac_kernel.db as j\n"}),
        )

    # ── the contract admits BOTH algorithms, and the label SELECTS one ──────
    #
    # `test_no_document_contract_admits_the_new_algorithm_yet` stood here and
    # was true when it was written. It is now false and is DELETED rather than
    # skipped or inverted: a test whose name asserts a state that no longer
    # exists is a contradicting comment with a green tick on it.
    #
    # `_source_surface` accepts exactly `{v1, v2}` -- a closed set of two, each
    # with an evaluation behind it -- and `engine._check_source_surface`
    # dispatches on the declared name. `KernelAdoptionDeclaration.v2` is
    # unchanged: this is vocabulary widening, not a schema version.

    def aliased(self) -> dict[PurePosixPath, str]:
        """A source whose two digests DISAGREE, which is what makes the admit
        control below discriminating rather than decorative."""
        return {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import publish as send\n"
            )
        }

    def test_a_v2_coordinate_from_the_real_runner_is_admitted_end_to_end(
        self,
    ) -> None:
        """Admit control, and its non-vacuity is the whole design of it.

        The declared value is derived by `engine.observed_surface_identity` --
        the seam a migrating product actually calls -- not hand-built, so a
        renderer that drifted from the runner could not produce a passing
        document here.

        The discriminator: the source is ALIASED, so its v1 and v2 digests
        differ. The second half proves the v2 evaluation really ran, by showing
        that the value v1 would have derived is REFUSED under the v2 label. An
        implementation that admitted the document and then evaluated it as v1
        would pass the first assertion and fail this one.
        """
        sources = self.aliased()
        v2_digest, _ = observed_surface_identity(surface_identity_facts(sources))
        v1_digest = surface_digest(facts_of(sources))
        self.assertNotEqual(v1_digest, v2_digest)

        document = v2_document(
            sources,
            ONE_MODULE,
            required_surfaces=REQUIRED_ONE,
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": v2_digest,
            },
        )
        parsed = parse_declaration_v2(document)
        self.assertEqual(
            SOURCE_SURFACE_IDENTITY_ALGORITHM,
            None if parsed.source_surface is None else parsed.source_surface.algorithm,
        )
        self.assertClean(report(document, sources, ONE_MODULE))

        evaluated_as_v1 = v2_document(
            sources,
            ONE_MODULE,
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": v1_digest,
            },
        )
        self.assertNamed(
            report(evaluated_as_v1, sources, ONE_MODULE),
            FindingCode.SOURCE_SURFACE_DRIFT,
        )

    def test_a_v1_declaration_still_parses_and_still_evaluates_to_its_old_value(
        self,
    ) -> None:
        """v1 preserved THROUGH the contract, against bytes from `298eaad`.

        `V1_GOLDEN_DIGEST` was produced by v1's own code at the revision before
        `dmg-kernel-surface-v2` existed. Here it is declared literally in a
        document and the run is asked to accept it over source chosen to
        reproduce `V1_GOLDEN_FACTS`. So the parser, the dispatch, the merge and
        the renderer are all in the path: any of them moving v1's value fails,
        not just an edit to `render_surface`.

        """
        sources = {
            PurePosixPath("a.py"): "from dotmac_kernel import Y\n",
            PurePosixPath("b.py"): (
                "from dotmac_kernel.db import Session, get_session\n"
            ),
        }
        # Non-vacuity: these sources really do measure to the golden fact set.
        self.assertEqual(V1_GOLDEN_FACTS, facts_of(sources))

        item = catalogue(frozenset({"dotmac_kernel.db"}), root_exports=frozenset({"Y"}))
        document = v2_document(
            sources,
            item,
            source_surface={
                "algorithm": SOURCE_SURFACE_ALGORITHM,
                "digest": V1_GOLDEN_DIGEST,
            },
        )
        parsed = parse_declaration_v2(document)
        self.assertEqual(
            SOURCE_SURFACE_ALGORITHM,
            None if parsed.source_surface is None else parsed.source_surface.algorithm,
        )
        self.assertClean(report(document, sources, item))

    def test_an_unknown_algorithm_and_a_relabelled_v1_digest_are_both_refused(
        self,
    ) -> None:
        """Two refusals, and they happen in two different places on purpose.

        An UNKNOWN name is refused by the CONTRACT: the accepted set is closed
        at two, so a third name never reaches an arm.

        A v1 digest RELABELLED `dmg-kernel-surface-v2` PARSES, and that is not
        a hole -- it is what a digest is. Sixty-four hex characters carry no
        record of the rendering that produced them, and a document parser has
        no source to re-derive from, so no parser could tell. It is refused by
        the RUN, because the two algorithms take their digests over different
        bytes and the re-derived v2 value cannot equal a v1 one. That is
        precisely what domain separation is for: the refusal comes from the
        structure of the digests, not from a check somebody remembered to
        write. The standing rule -- a v1 receipt is never v2 evidence -- holds
        here by construction.
        """
        sources = self.aliased()
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration_v2(
                v2_document(
                    sources,
                    ONE_MODULE,
                    source_surface={
                        "algorithm": "somebody-elses-rendering-v1",
                        "digest": surface_digest(facts_of(sources)),
                    },
                )
            )
        message = str(caught.exception)
        self.assertIn(SOURCE_SURFACE_ALGORITHM, message)
        self.assertIn(SOURCE_SURFACE_IDENTITY_ALGORITHM, message)

        relabelled = v2_document(
            sources,
            ONE_MODULE,
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": surface_digest(facts_of(sources)),
            },
        )
        parse_declaration_v2(relabelled)
        self.assertNamed(
            report(relabelled, sources, ONE_MODULE), FindingCode.SOURCE_SURFACE_DRIFT
        )

    def test_a_kernel_symbol_swap_behind_one_alias_is_refused_under_v2_only(
        self,
    ) -> None:
        """The original defect, proved through the document rather than the
        renderer.

        Declare a surface for `publish as send`, then measure `emit as send`:
        the local name is untouched and the Kernel symbol behind it changed.
        Under v2 the declaration no longer describes the source and the run
        says so. Under v1 the same swap is CLEAN -- which is the defect, kept
        as a live assertion rather than a paragraph, and the reason v1 is not
        the algorithm a product should migrate to.
        """
        declared = self.aliased()
        swapped = {
            PurePosixPath("src/app/service.py"): (
                "from dotmac_kernel.messaging import emit as send\n"
            )
        }
        v2_declared = v2_document(
            declared,
            ONE_MODULE,
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": surface_identity_digest(surface_identity_facts(declared)),
            },
        )
        self.assertNamed(
            report(v2_declared, swapped, ONE_MODULE), FindingCode.SOURCE_SURFACE_DRIFT
        )

        v1_declared = v2_document(
            declared,
            ONE_MODULE,
            required_surfaces=REQUIRED_ONE,
            source_surface={
                "algorithm": SOURCE_SURFACE_ALGORITHM,
                "digest": surface_digest(facts_of(declared)),
            },
        )
        self.assertClean(report(v1_declared, swapped, ONE_MODULE))

    def test_a_v2_label_over_v1_shaped_facts_refuses_rather_than_coercing(
        self,
    ) -> None:
        """The shape confusion, refused structurally.

        `SurfaceFact` and `SurfaceIdentityFact` do not share a render method
        name -- `render` and `render_identity` -- so neither renderer can walk
        the other's facts. Handed the wrong shape, `render_surface_identity`
        raises with a message that names the confusion; `render_surface` raises
        `AttributeError`, which is a refusal with a poor message.

        The asymmetry is deliberate and is stated rather than tidied: giving
        v1's renderer a friendlier guard means editing v1, and v1 is frozen.
        The missing method is the refusal, and there is nothing to delete.
        """
        v1_facts = facts_of(self.aliased())
        with self.assertRaises(TypeError) as caught:
            render_surface_identity(v1_facts)  # type: ignore[arg-type]
        self.assertIn("SurfaceFact", str(caught.exception))

        v2_facts = surface_identity_facts(self.aliased())
        with self.assertRaises(AttributeError):
            render_surface(v2_facts)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
