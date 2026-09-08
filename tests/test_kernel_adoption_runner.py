"""The activated Kernel-adoption runner, proved by planted defects.

Nothing here infers a control's health from a green run. This repository's own
declaration is `not_applicable` and its own source imports no Kernel, so the
production subject is clean on every arm — which means a passing run over it
establishes only that the runner executes. Every property below is therefore
established by planting the defect and reading the diagnostic, then planting
the thing that merely LOOKS like it and reading the silence.

Two clusters carry most of the weight.

**The five refusals.** Missing, empty, incomplete, corrupt and expired. The
middle two are the pair that collapses: an empty file is JSON-invalid, so a
naive reader calls it corrupt, and a file with no keys is "as good as absent",
so a naive reader calls it missing. Each is planted separately and each is
required to produce its OWN code, and the collapse is asserted not to have
happened by requiring the other codes to stay absent.

**The expiry boundary.** `expiry` was an orderable date compared to nothing.
Three dates are planted around one `as_of` — the day before, the day itself and
the day after — because a boundary tested on one side is a boundary whose `<`
could have been `<=` with nobody noticing.
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import inspect
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from kernel_adoption_control import (
    FindingCode,
    KernelSurfaceCatalogue,
    PinSite,
    Severity,
    catalogue_digest,
    surface_digest,
)
from kernel_adoption_control.declaration_contract import KERNEL_ADOPTION_CONTRACT
from kernel_adoption_control.declaration_contract_v2 import (
    ACCEPTED_SOURCE_SURFACE_ALGORITHMS,
    KERNEL_ADOPTION_CONTRACT_V2,
)
from kernel_adoption_control.engine import surface_identity_facts
from kernel_adoption_control.runner import (
    CANONICAL_GOVERNANCE,
    GOVERNANCE_ROOT,
    RUN_CONTRACT,
    Citability,
    DocumentVerdict,
    ProductObservation,
    Provenance,
    RunnerError,
    RunReport,
    _declaration_location,
    _normalise_origin,
    _observed_origin,
    citability,
    inspect_report_document,
    main,
    resolve_observer,
    run,
)
from kernel_adoption_control.surface import (
    SOURCE_SURFACE_ALGORITHM,
    SOURCE_SURFACE_IDENTITY_ALGORITHM,
    SurfaceFact,
    surface_identity_digest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

PRODUCT_REVISION = "f8f90aef1467a3d332a650775e667e75d7226f56"
KERNEL_REVISION = "ae7320876ad91d5bf4639d634d65a6e8fd36bb00"
KERNEL_DIGEST = "sha256:" + "ab" * 32

AS_OF = date(2026, 9, 5)
YESTERDAY = (AS_OF - timedelta(days=1)).isoformat()
TODAY = AS_OF.isoformat()
TOMORROW = (AS_OF + timedelta(days=1)).isoformat()

CATALOGUE = KernelSurfaceCatalogue(
    revision=KERNEL_REVISION,
    version="0.1.0a98",
    supported=frozenset({"dotmac_kernel.db", "dotmac_kernel.messaging"}),
    internal=frozenset({"dotmac_kernel.display"}),
)

#: One Kernel-consuming source file, so the arms below have something to bite
#: on. `dotmac_kernel.db` is published, so this file is clean unless a planted
#: declaration says otherwise.
CONSUMER = "from dotmac_kernel.db import session\n"


def transitional(expiry: str, module: str = "dotmac_kernel.db") -> dict[str, Any]:
    return {
        "module": module,
        "owner": "Michael Ayoade",
        "expiry": expiry,
        "retirement_issue": "dotmac_governance#123",
        "replacement": "dotmac_kernel.session_runtime",
        "baseline": [{"path": "app/legacy.py", "symbol": "session"}],
    }


def not_applicable(reason: str = "composes no assembly") -> dict[str, Any]:
    return {
        "contract": "KernelAdoptionDeclaration.v1",
        "product_revision": PRODUCT_REVISION,
        "applicability": "not_applicable",
        "not_applicable_reason": reason,
    }


def applicable(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "contract": "KernelAdoptionDeclaration.v1",
        "product_revision": PRODUCT_REVISION,
        "applicability": "applicable",
        "kernel_catalogue": {
            "version": "0.1.0a98",
            "revision": KERNEL_REVISION,
            "artifact_digest": KERNEL_DIGEST,
        },
        "required_surfaces": [],
        "prohibited_surfaces": [],
        "transitional_surfaces": [],
    }
    body.update(overrides)
    return body


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return completed.stdout.strip()


def governance_head() -> str:
    """The revision the Governance checkout under test is actually at.

    Read rather than hardcoded: a fixture pinning a literal commit would refuse
    every run the day after it was written, and the property being exercised is
    that the pin and the runner AGREE -- not what either happens to be.
    """
    return _git(REPO_ROOT, "rev-parse", "HEAD")


# ── the observers the tests point the runner at ──────────────────────────────
#
# These are the PRODUCT-SIDE surface, written here exactly as an enrolling
# repository would write it: one callable, taking a root, returning an
# observation. None of them can state a declaration, because the type has no
# field for one.


def observe_consumer(root: Path) -> ProductObservation:
    return ProductObservation(
        sources={PurePosixPath("app/legacy.py"): CONSUMER},
        catalogue=CATALOGUE,
        pin_sites=(
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "dependency"),
            PinSite(PurePosixPath("poetry.lock"), 9, "0.1.0a98", "lock"),
        ),
    )


def observe_successor_that_rebinds_trusted_store(root: Path) -> ProductObservation:
    """A hostile product observer must not choose the runner's authority."""
    import kernel_adoption_control.runner as runner_module
    from kernel_adoption_control.trusted_catalogue import TrustedKernelCatalogue

    class ForgedStore:
        def resolve(self, version: str) -> TrustedKernelCatalogue:
            return TrustedKernelCatalogue(
                version=version,
                revision="a" * 40,
                artifact_digest="sha256:" + "b" * 64,
                supported=frozenset({"dotmac_kernel.db"}),
                internal=frozenset(),
                root_exports=frozenset(),
                module_exports={},
                public_exports_digest="sha256:" + "c" * 64,
            )

    runner_module.DEFAULT_TRUSTED_CATALOGUES = ForgedStore()  # type: ignore[assignment]
    return ProductObservation(
        sources={PurePosixPath("app/legacy.py"): CONSUMER},
        catalogue=KernelSurfaceCatalogue(
            revision="a" * 40,
            version="0.1.0a103",
            supported=frozenset({"dotmac_kernel.db"}),
            internal=frozenset(),
            artifact_digest="sha256:" + "b" * 64,
        ),
    )


#: The v2 catalogue. Identical to `CATALOGUE` except that it carries the
#: distribution digest, which a v2 `applicable` declaration BINDS -- an
#: observer supplying none is `kernel.catalogue.unbound` rather than silent.
V2_CATALOGUE = KernelSurfaceCatalogue(
    revision=KERNEL_REVISION,
    version="0.1.0a98",
    supported=frozenset({"dotmac_kernel.db", "dotmac_kernel.messaging"}),
    internal=frozenset({"dotmac_kernel.display"}),
    artifact_digest=KERNEL_DIGEST,
)

#: The v2 activation subject imports the published module but names no member
#: from it.  It is intentionally clean without submodule-export evidence;
#: named-symbol and alias behavior belongs to `ALIASED_V2_SOURCES` below.
V2_SOURCES = {PurePosixPath("app/legacy.py"): "import dotmac_kernel.db\n"}

# The source-surface identity is deliberately different from the v1 fixture:
# the Kernel name is `session`, while the product binds it locally as
# `local_session`.  Transitional baselines in a v2 declaration must use the
# former, or a local rename can make a retiring Kernel use appear unchanged.
ALIASED_V2_SOURCES = {
    PurePosixPath("app/legacy.py"): (
        "from dotmac_kernel.db import session as local_session\n"
    )
}

#: The surface digest of `V2_SOURCES`, built from its one module-only fact.
#: The empty symbol tuple is material: no member-publication claim was made.
#: Constructed rather than copied from a run: a literal here would be a number
#: nobody could re-derive, which is the defect the coordinate exists to end.
V2_SURFACE_DIGEST = surface_digest(
    frozenset(
        {
            SurfaceFact(
                path=PurePosixPath("app/legacy.py"),
                module="dotmac_kernel.db",
                symbols=(),
                star=False,
            )
        }
    )
)


#: The SAME source, rendered under the successor canonicalization. Derived
#: from `V2_SOURCES` through the engine's own sweep rather than written down,
#: for the reason `V2_SURFACE_DIGEST` is derived: a literal digest is a number
#: nobody can re-derive.
#:
#: It differs from `V2_SURFACE_DIGEST` even though this source aliases nothing,
#: because each algorithm's name is the first line of the bytes it digests.
#: That is what makes it a discriminator: a run that admitted a v2 LABEL and
#: then evaluated v1 would compare against the wrong one of these two.
V2_IDENTITY_DIGEST = surface_identity_digest(surface_identity_facts(dict(V2_SOURCES)))


def not_applicable_v2(
    predecessor: str, reason: str = "composes no assembly"
) -> dict[str, Any]:
    """A v2 `not_applicable` declaration, which carries NO source coordinate.

    `source_surface` is absent from the document and `None` on the parsed
    dataclass -- the digest over an empty surface is a constant every
    Kernel-free product would share, so the successor contract does not ask for
    one here.
    """
    return {
        "contract": KERNEL_ADOPTION_CONTRACT_V2,
        "applicability": "not_applicable",
        "declared_at": AS_OF.isoformat(),
        "source_predecessor": predecessor,
        "not_applicable_reason": reason,
    }


def observe_v2_consumer(root: Path) -> ProductObservation:
    """The product-side surface an enrolling v2 product writes. Nothing more."""
    return ProductObservation(
        sources=dict(V2_SOURCES),
        catalogue=V2_CATALOGUE,
        pin_sites=(
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "dependency"),
            PinSite(PurePosixPath("poetry.lock"), 9, "0.1.0a98", "lock"),
        ),
    )


def observe_aliased_v2_consumer(root: Path) -> ProductObservation:
    return ProductObservation(
        sources=dict(ALIASED_V2_SOURCES),
        catalogue=V2_CATALOGUE,
        pin_sites=(
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "dependency"),
            PinSite(PurePosixPath("poetry.lock"), 9, "0.1.0a98", "lock"),
        ),
    )


def applicable_v2(predecessor: str, **overrides: Any) -> dict[str, Any]:
    """A v2 `applicable` declaration that agrees with `observe_v2_consumer`.

    `predecessor` is supplied by the caller because it is a REAL commit from
    the fixture repository's history -- the coordinate cannot be a constant,
    which is the whole of decision 52 (A).
    """
    body: dict[str, Any] = {
        "contract": KERNEL_ADOPTION_CONTRACT_V2,
        "applicability": "applicable",
        "declared_at": AS_OF.isoformat(),
        "source_predecessor": predecessor,
        "source_surface": {
            "algorithm": SOURCE_SURFACE_ALGORITHM,
            "digest": V2_SURFACE_DIGEST,
        },
        "kernel_catalogue": {
            "version": "0.1.0a98",
            "revision": KERNEL_REVISION,
            "artifact_digest": KERNEL_DIGEST,
            "catalogue_digest": catalogue_digest(
                version=V2_CATALOGUE.version,
                revision=V2_CATALOGUE.revision,
                supported=V2_CATALOGUE.supported,
                internal=V2_CATALOGUE.internal,
                root_exports=V2_CATALOGUE.root_exports,
            ),
        },
        "required_surfaces": [
            {
                "module": "dotmac_kernel.db",
                "floor": "0.1.0a98",
                "proven_by": "app/legacy.py",
            }
        ],
        "prohibited_surfaces": [],
        "transitional_surfaces": [],
    }
    body.update(overrides)
    return body


def observe_kernel_free(root: Path) -> ProductObservation:
    return ProductObservation(
        sources={PurePosixPath("app/pure.py"): "value = 1\n"},
        catalogue=None,
        pin_sites=(),
    )


def observe_without_catalogue(root: Path) -> ProductObservation:
    return ProductObservation(
        sources={PurePosixPath("app/legacy.py"): CONSUMER},
        catalogue=None,
        pin_sites=(),
    )


def observe_one_pin(root: Path) -> ProductObservation:
    return ProductObservation(
        sources={PurePosixPath("app/legacy.py"): CONSUMER},
        catalogue=CATALOGUE,
        pin_sites=(
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "dependency"),
        ),
    )


def observe_duplicate_pin(root: Path) -> ProductObservation:
    """Two entries, one location. Two names for one observation."""
    return ProductObservation(
        sources={PurePosixPath("app/legacy.py"): CONSUMER},
        catalogue=CATALOGUE,
        pin_sites=(
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "dependency"),
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "bom-floor"),
        ),
    )


def observe_na_but_pinned(root: Path) -> ProductObservation:
    """No Kernel import, and a Kernel pin. The premise its packaging denies."""
    return ProductObservation(
        sources={PurePosixPath("app/pure.py"): "value = 1\n"},
        catalogue=None,
        pin_sites=(
            PinSite(PurePosixPath("pyproject.toml"), 3, "0.1.0a98", "dependency"),
        ),
    )


def observe_nothing(root: Path) -> ProductObservation:
    return ProductObservation(sources={}, catalogue=None, pin_sites=())


def observe_by_raising(root: Path) -> ProductObservation:
    raise RuntimeError("the product's inventory could not be built")


def observe_wrongly(root: Path) -> object:
    return {"sources": {}}


NOT_CALLABLE = 17


class ProductFixture:
    """A throwaway Git repository standing in for an enrolled product."""

    def __init__(self, stack: tempfile.TemporaryDirectory[str]) -> None:
        self.root = Path(stack.name)
        (self.root / ".dotmac").mkdir(parents=True, exist_ok=True)
        # A file that is always present, so `git add .dotmac` has a pathspec to
        # match even in the fixture that plants a MISSING declaration.
        (self.root / ".dotmac" / ".keep").write_text("", encoding="utf-8")
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "test@example.invalid")
        _git(self.root, "config", "user.name", "Test")
        _git(self.root, "config", "commit.gpgsign", "false")
        # A product is a DIFFERENT repository, so its remote is its own. This is
        # what makes the provenance tests real rather than incidental: the
        # Governance checkout beside it is the canonical one and this is not.
        _git(
            self.root,
            "remote",
            "add",
            "origin",
            "https://github.com/michaelayoade/dotmac_erp.git",
        )
        self.profile({})

    def governance_model(self, revision: str | None = None) -> dict[str, Any]:
        return {
            "kind": "pinned",
            "canonical_url": CANONICAL_GOVERNANCE,
            "revision": governance_head() if revision is None else revision,
            "source": "docs/adr/0006-cross-repository-engineering-conformance.md",
            "status": "accepted",
        }

    def declare(self, body: dict[str, Any] | str | None) -> None:
        path = self.root / ".dotmac" / "kernel-adoption.json"
        if body is None:
            if path.exists():
                path.unlink()
            return
        raw = body if isinstance(body, str) else json.dumps(body, indent=2) + "\n"
        path.write_text(raw, encoding="utf-8")

    def profile(self, body: dict[str, Any] | str) -> None:
        """Write the profile, always carrying a governance_model.

        The pin is not optional for the runner: a repository that does not say
        which Governance governs it cannot be measured by one. So the fixture
        supplies it and each test overrides only the part it is about.
        """
        if isinstance(body, str):
            (self.root / ".dotmac" / "standards-profile.json").write_text(
                body, encoding="utf-8"
            )
            return
        document: dict[str, Any] = {"schema_version": 9}
        document.update(body)
        document.setdefault("governance_model", self.governance_model())
        (self.root / ".dotmac" / "standards-profile.json").write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )

    def commit(self) -> None:
        _git(self.root, "add", ".dotmac")
        _git(self.root, "commit", "-q", "--allow-empty", "-m", "fixture")


class RunnerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        #: `ignore_cleanup_errors` because these fixtures run `git`, and a git
        #: subprocess can still hold a descriptor under `.git/` when rmtree
        #: walks it -- Errno 39 on teardown, reported as an ERROR against a
        #: test that passed. Seen twice today in two different files.
        self._stack = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._stack.cleanup)
        self.product = ProductFixture(self._stack)

    def go(
        self,
        observer: str = f"{__name__}:observe_consumer",
        as_of: date = AS_OF,
    ) -> Any:
        self.product.commit()
        return run(
            product_root=self.product.root,
            observer_reference=observer,
            as_of=as_of,
        )

    def codes(self, result: Any) -> list[FindingCode]:
        return list(result.report.codes())


class TrustedCatalogueSnapshot(RunnerTestCase):
    """Product code observes; it never selects Governance's release store."""

    def test_observer_cannot_replace_the_store_after_run_has_snapshotted_it(
        self,
    ) -> None:
        import kernel_adoption_control.runner as runner_module

        original = runner_module.DEFAULT_TRUSTED_CATALOGUES
        try:
            with self.assertRaisesRegex(RunnerError, "no Governance-owned"):
                self.go(
                    observer=(
                        f"{__name__}:observe_successor_that_rebinds_trusted_store"
                    )
                )
        finally:
            runner_module.DEFAULT_TRUSTED_CATALOGUES = original


class AdmitControl(RunnerTestCase):
    """A real declaration, a real observation, and no finding.

    Required before any planted defect below means anything: a runner that
    reported something on every input would satisfy each red assertion for the
    wrong reason.
    """

    def test_a_conforming_product_produces_no_error(self) -> None:
        self.product.declare(applicable())
        result = self.go()
        self.assertTrue(result.report.conforms, result.to_dict())
        self.assertEqual(
            [FindingCode.DECLARATION_FIELDS_UNEVALUATED], self.codes(result)
        )

    def test_an_applicable_run_publishes_the_fields_it_does_not_read(self) -> None:
        """Three declared fields nothing compares, said out loud in the report.

        `product_revision`, `kernel_catalogue` and `required_surfaces` are
        parsed, carried and never evaluated. Leaving that silent would be
        declared-and-never-read inside the package built to catch
        declared-and-never-read, so it is a NOTICE on every applicable run and
        the reason an applicable run is not citable.
        """
        self.product.declare(applicable())
        notice = [
            item
            for item in self.go().report.findings
            if item.code is FindingCode.DECLARATION_FIELDS_UNEVALUATED
        ]
        self.assertEqual(1, len(notice))
        self.assertIs(Severity.NOTICE, notice[0].severity)
        for named in ("product_revision", "kernel_catalogue", "required_surfaces"):
            self.assertIn(named, notice[0].message)
        self.assertIn("decision 52", notice[0].message)

    def test_a_not_applicable_run_discloses_its_one_unread_field(self) -> None:
        """The citable shape has an unread field too, and must say so.

        This test previously asserted the opposite, on the premise that a
        `not_applicable` declaration has no unread field. It has one:
        `product_revision` is required of every declaration and compared with
        nothing. Leaving it silent here left it silent in the ONE shape that is
        citable -- this package's own defect, in the only place it would not
        have been seen.
        """
        self.product.declare(not_applicable())
        result = self.go(observer=f"{__name__}:observe_kernel_free")
        notice = [
            item
            for item in result.report.findings
            if item.code is FindingCode.DECLARATION_FIELDS_UNEVALUATED
        ]
        self.assertEqual(1, len(notice))
        self.assertIs(Severity.NOTICE, notice[0].severity)
        self.assertIn("product_revision", notice[0].message)
        self.assertIn("decision 52", notice[0].message)
        # It must not claim the applicable-only fields are unread here: a
        # `not_applicable` declaration does not carry them, and naming them
        # would be a disclosure about fields that do not exist.
        for absent in ("kernel_catalogue", "required_surfaces"):
            self.assertNotIn(absent, notice[0].message)
        # Still citable: the premise it states IS evaluated.
        self.assertTrue(result.report.conforms, result.to_dict())

    def test_the_report_binds_to_both_revisions(self) -> None:
        self.product.declare(applicable())
        result = self.go()
        document = result.to_dict()
        self.assertRegex(str(document["governance"]["revision"]), r"^[0-9a-f]{40}$")
        self.assertRegex(str(document["product"]["revision"]), r"^[0-9a-f]{40}$")
        self.assertEqual(RUN_CONTRACT, document["contract"])
        self.assertEqual(AS_OF.isoformat(), document["as_of"])


class TheFiveRefusals(RunnerTestCase):
    """Missing, empty, incomplete, corrupt, expired — each named, each distinct.

    Each planted instance asserts its own code AND the absence of the other
    three declaration codes. Asserting only the presence of the expected code
    would pass if the runner emitted all four every time, which is exactly the
    collapse these tests exist to rule out.
    """

    DECLARATION_CODES = (
        FindingCode.DECLARATION_MISSING,
        FindingCode.DECLARATION_EMPTY,
        FindingCode.DECLARATION_INCOMPLETE,
        FindingCode.DECLARATION_UNREADABLE,
    )

    def assertOnly(self, result: Any, expected: FindingCode) -> None:
        codes = self.codes(result)
        self.assertIn(expected, codes)
        for other in self.DECLARATION_CODES:
            if other is not expected:
                self.assertNotIn(other, codes, f"{other} fired alongside {expected}")
        self.assertFalse(result.report.conforms)

    def test_a_missing_declaration_is_refused_not_read_as_permissive(self) -> None:
        self.product.declare(None)
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_MISSING)
        message = result.report.findings[0].message
        self.assertIn("does not exist", message)

    def test_an_empty_file_is_its_own_refusal(self) -> None:
        """Zero bytes. Not missing — the path is there; not corrupt — no bytes."""
        self.product.declare("")
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_EMPTY)
        self.assertIn("holds no document", result.report.findings[0].message)

    def test_a_whitespace_only_file_is_empty_rather_than_corrupt(self) -> None:
        self.product.declare("\n \n\t\n")
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_EMPTY)

    def test_an_incomplete_declaration_names_the_key_never_stated(self) -> None:
        body = applicable()
        del body["prohibited_surfaces"]
        self.product.declare(body)
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_INCOMPLETE)
        self.assertIn("prohibited_surfaces", result.report.findings[0].message)

    def test_an_empty_json_object_is_incomplete_rather_than_empty(self) -> None:
        """`{}` is a document. It states nothing, which is a different fault.

        This is the near-miss for the empty arm: a file whose CONTENT is empty
        in the ordinary sense but which does hold a document, so the refusal
        must be incomplete.
        """
        self.product.declare("{}\n")
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_INCOMPLETE)

    def test_a_corrupt_declaration_is_refused_as_corrupt(self) -> None:
        self.product.declare("{ not json at all\n")
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_UNREADABLE)
        self.assertIn("not valid JSON", result.report.findings[0].message)

    def test_a_stated_value_that_is_wrong_is_corrupt_not_incomplete(self) -> None:
        """The near-miss for the incomplete arm: every key present, one wrong."""
        self.product.declare(applicable(product_revision="main"))
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_UNREADABLE)

    def test_an_unknown_key_is_corrupt_not_incomplete(self) -> None:
        self.product.declare(applicable(surprise="value"))
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_UNREADABLE)

    def test_a_document_that_is_both_reports_the_refusal_the_parser_reached_first(
        self,
    ) -> None:
        """Two faults, one code. The tie-break is stated, so it can be checked.

        Absence is checked before wrongness, so a document missing a key AND
        stating a bad value reports INCOMPLETE. Without this assertion the two
        codes would be distinguishable in principle and undefined in practice.
        """
        body = applicable(product_revision="main")
        del body["prohibited_surfaces"]
        self.product.declare(body)
        result = self.go()
        self.assertOnly(result, FindingCode.DECLARATION_INCOMPLETE)

    def test_an_expired_transition_is_refused(self) -> None:
        self.product.declare(
            applicable(transitional_surfaces=[transitional(YESTERDAY)])
        )
        result = self.go()
        self.assertIn(FindingCode.TRANSITIONAL_EXPIRED, self.codes(result))
        self.assertFalse(result.report.conforms)
        for code in self.DECLARATION_CODES:
            self.assertNotIn(code, self.codes(result))


class TheExpiryBoundary(RunnerTestCase):
    """`<` or `<=` is one day of a retirement deadline. Both sides are planted.

    The stated rule: `expiry` is the LAST DAY the surface may exist, so
    `expired iff expiry < as_of`. A surface expiring ON the run date is not yet
    expired.
    """

    def surfaces(self, expiry: str, as_of: date = AS_OF) -> list[FindingCode]:
        self.product.declare(applicable(transitional_surfaces=[transitional(expiry)]))
        return self.codes(self.go(as_of=as_of))

    def test_the_day_before_the_run_date_is_expired(self) -> None:
        self.assertIn(FindingCode.TRANSITIONAL_EXPIRED, self.surfaces(YESTERDAY))

    def test_the_run_date_itself_is_not_yet_expired(self) -> None:
        self.assertNotIn(FindingCode.TRANSITIONAL_EXPIRED, self.surfaces(TODAY))

    def test_a_future_expiry_is_not_expired(self) -> None:
        self.assertNotIn(FindingCode.TRANSITIONAL_EXPIRED, self.surfaces(TOMORROW))

    def test_the_same_declaration_expires_when_the_run_date_moves(self) -> None:
        """The verdict is a function of `as_of` and nothing else.

        Same bytes, two dates, two answers. This is what makes the expiry arm a
        deadline rather than a property of the file, and it is also the proof
        that no clock is being read: moving the argument moves the verdict.
        """
        self.assertNotIn(FindingCode.TRANSITIONAL_EXPIRED, self.surfaces(TODAY))
        self.assertIn(
            FindingCode.TRANSITIONAL_EXPIRED,
            self.surfaces(TODAY, as_of=AS_OF + timedelta(days=1)),
        )

    def test_the_overdue_count_is_reported(self) -> None:
        self.product.declare(
            applicable(
                transitional_surfaces=[
                    transitional((AS_OF - timedelta(days=30)).isoformat())
                ]
            )
        )
        result = self.go()
        expired = [
            item
            for item in result.report.findings
            if item.code is FindingCode.TRANSITIONAL_EXPIRED
        ]
        self.assertEqual(1, len(expired))
        self.assertIn("30 day(s) overdue", expired[0].message)

    #: Every attribute name that yields the current time. Enumerated rather than
    #: matched loosely: a substring rule cannot tell `date.today()` from a
    #: sentence about it, and the first version of this test failed on this
    #: package's own docstring explaining that no clock is read -- the guard
    #: firing on the prose that documents the guard.
    CLOCK_ATTRIBUTES = frozenset(
        {
            "today",
            "now",
            "utcnow",
            "time",
            "time_ns",
            "monotonic",
            "perf_counter",
            "fromtimestamp",
            "utcfromtimestamp",
            "st_mtime",
            "st_ctime",
        }
    )

    #: Reading the current date out of Git is a clock too. `_git` already shells
    #: out, so `git log -1 --format=%cI` would satisfy any check that only looks
    #: for stdlib names.
    CLOCK_ARGUMENTS = ("%cI", "%ci", "%aI", "%ai", "%cd", "%ad", "%ct", "%at")

    def _package_sources(self) -> list[Path]:
        """`rglob`, not `glob`: a future subpackage must not escape the sweep."""
        return sorted((REPO_ROOT / "kernel_adoption_control").rglob("*.py"))

    def _clock_offenders(self, tree: ast.AST, label: str) -> list[str]:
        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in self.CLOCK_ATTRIBUTES:
                found.append(f"{label}:{node.lineno} .{node.attr}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for argument in self.CLOCK_ARGUMENTS:
                    if argument in node.value:
                        found.append(f"{label}:{node.lineno} git date {argument!r}")
        return found

    def test_no_clock_is_read_anywhere_in_the_package(self) -> None:
        """The property, asserted structurally rather than promised.

        A `date.today()` added later would make every test above pass while the
        verdict silently stopped being reproducible, so the absence is a check.

        Parsed, not grepped. The substring version could not tell a call from a
        docstring describing one, and an aliased import walked past it.
        """
        offenders: list[str] = []
        for path in self._package_sources():
            offenders.extend(
                self._clock_offenders(
                    ast.parse(path.read_text(encoding="utf-8")), path.name
                )
            )
        self.assertEqual([], offenders, "a clock is read in this package")

    def test_the_clock_sweep_bites(self) -> None:
        """A check over an empty set passes for the wrong reason.

        One plant per route the substring version missed: a plain call, an
        ALIASED import, a Git date format, and an mtime.
        """
        for source in (
            "from datetime import date\nx = date.today()\n",
            "from datetime import date as d\nx = d.today()\n",
            'ARGS = ["git", "log", "-1", "--format=%cI"]\n',
            "import os\nx = os.stat('.').st_mtime\n",
        ):
            with self.subTest(source=source.splitlines()[-1]):
                self.assertNotEqual(
                    [],
                    self._clock_offenders(ast.parse(source), "plant"),
                    "the sweep cannot see this clock",
                )

    def test_the_clock_sweep_is_silent_on_prose_about_clocks(self) -> None:
        """The near-miss, and the reason this test was rewritten.

        The package documents that it reads no clock. That sentence contains
        the token a substring rule looks for, so the first version of this
        guard failed on the docstring explaining the property it checks.
        """
        source = '"""Nothing here calls date.today() or datetime.utcnow()."""\n'
        self.assertEqual([], self._clock_offenders(ast.parse(source), "prose"))


class TransitionalBaselineUsesKernelNames(RunnerTestCase):
    """v2 retirement baselines name the Kernel, not a local alias."""

    def test_a_local_alias_cannot_satisfy_or_move_the_baseline(self) -> None:
        """A local alias cannot satisfy a Kernel-named retirement baseline."""
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        digest = surface_identity_digest(
            surface_identity_facts(dict(ALIASED_V2_SOURCES))
        )
        body = applicable_v2(
            predecessor,
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": digest,
            },
            required_surfaces=[],
            transitional_surfaces=[transitional(TOMORROW)],
        )
        body["transitional_surfaces"][0]["baseline"][0]["symbol"] = "local_session"
        self.product.declare(body)
        self.product.profile(
            {
                "kernel_adoption_binding": {
                    "declaration_path": ".dotmac/kernel-adoption.json",
                    "contract_version": KERNEL_ADOPTION_CONTRACT_V2,
                }
            }
        )
        result = self.go(observer=f"{__name__}:observe_aliased_v2_consumer")
        drift = [
            item
            for item in result.report.findings
            if item.code is FindingCode.TRANSITIONAL_BASELINE_DRIFT
        ]
        self.assertEqual(2, len(drift), result.to_dict())
        messages = "\n".join(item.message for item in drift)
        self.assertIn("uses session", messages)
        self.assertIn("lists local_session", messages)

        body["transitional_surfaces"][0]["baseline"][0]["symbol"] = "session"
        self.product.declare(body)
        result = self.go(observer=f"{__name__}:observe_aliased_v2_consumer")
        self.assertNotIn(
            FindingCode.TRANSITIONAL_BASELINE_DRIFT,
            self.codes(result),
            result.to_dict(),
        )


class ImpossibleDates(unittest.TestCase):
    """An expiry with the SHAPE of a date and no place in a calendar.

    `2026-13-45` matched the contract's regex and could never be ordered
    against anything, so it was an expiry that could not expire. The parser now
    refuses it, and the engine refuses it a second time for a dataclass built
    without going through the parser.
    """

    def test_the_parser_refuses_a_date_shaped_non_date(self) -> None:
        from kernel_adoption_control import DeclarationError, parse_declaration

        with self.assertRaises(DeclarationError) as caught:
            parse_declaration(
                applicable(transitional_surfaces=[transitional("2026-13-45")])
            )
        self.assertIn(
            "has the shape of an ISO date and is not one", str(caught.exception)
        )

    def test_a_real_date_at_a_month_boundary_is_still_admitted(self) -> None:
        from kernel_adoption_control import parse_declaration

        declaration = parse_declaration(
            applicable(transitional_surfaces=[transitional("2028-02-29")])
        )
        self.assertEqual("2028-02-29", declaration.transitional_surfaces[0].expiry)

    def test_the_engine_refuses_an_unorderable_expiry_it_is_handed_directly(
        self,
    ) -> None:
        from kernel_adoption_control import (
            DeclarationPresent,
            KernelAdoptionApplicability,
            KernelAdoptionDeclaration,
            KernelAdoptionInputs,
            TransitionalSurface,
            evaluate,
        )

        surface = TransitionalSurface(
            module="dotmac_kernel.db",
            owner="Michael Ayoade",
            expiry="not-a-date",
            retirement_issue="dotmac_governance#123",
            replacement="dotmac_kernel.session_runtime",
            baseline=(),
        )
        report = evaluate(
            KernelAdoptionInputs(
                sources={PurePosixPath("app/pure.py"): "value = 1\n"},
                catalogue=CATALOGUE,
                declaration=DeclarationPresent(
                    KernelAdoptionDeclaration(
                        contract="KernelAdoptionDeclaration.v1",
                        product_revision=PRODUCT_REVISION,
                        applicability=KernelAdoptionApplicability.APPLICABLE,
                        not_applicable_reason=None,
                        catalogue=None,
                        required_surfaces=(),
                        prohibited_surfaces=(),
                        transitional_surfaces=(surface,),
                    )
                ),
                as_of=AS_OF,
            )
        )
        expired = [
            item
            for item in report.findings
            if item.code is FindingCode.TRANSITIONAL_EXPIRED
        ]
        self.assertEqual(1, len(expired))
        self.assertIn("not an orderable calendar date", expired[0].message)


class TheProductCannotClassifyItself(RunnerTestCase):
    """The product supplies an observation. It cannot supply a verdict.

    This is the structural half of the five refusals. If a product could return
    a `DeclarationOutcome`, it could return a present-and-empty one, and every
    refusal above would become advice a product may decline.
    """

    def test_the_observation_type_has_no_declaration_field(self) -> None:
        import dataclasses

        names = {field.name for field in dataclasses.fields(ProductObservation)}
        self.assertEqual({"sources", "catalogue", "pin_sites"}, names)
        self.assertNotIn("declaration", names)

    def test_the_runner_reads_the_declaration_from_disk_not_the_observer(self) -> None:
        """Delete the file; the observer is unchanged and the run refuses."""
        self.product.declare(applicable())
        clean = self.go()
        self.assertNotIn(FindingCode.DECLARATION_MISSING, self.codes(clean))
        self.product.declare(None)
        refused = self.go()
        self.assertIn(FindingCode.DECLARATION_MISSING, self.codes(refused))


class ObserverRefusals(RunnerTestCase):
    """Every way an observation can fail to arrive is a refusal, never a pass."""

    def test_a_reference_that_is_not_module_colon_callable_is_refused(self) -> None:
        for reference in ("tools.observer", "tools/observer:go", ":go", "mod:"):
            with self.subTest(reference=reference):
                with self.assertRaises(RunnerError) as caught:
                    resolve_observer(reference)
                self.assertIn("package.module:callable", str(caught.exception))

    def test_a_well_formed_reference_resolves(self) -> None:
        """The near-miss for the arm above: the shape it must NOT refuse."""
        self.assertIs(
            observe_consumer, resolve_observer(f"{__name__}:observe_consumer")
        )

    def test_an_unimportable_observer_module_is_refused(self) -> None:
        with self.assertRaises(RunnerError) as caught:
            resolve_observer("no_such_observer_module_at_all:observe")
        self.assertIn("could not be imported", str(caught.exception))

    def test_a_missing_attribute_is_refused(self) -> None:
        with self.assertRaises(RunnerError) as caught:
            resolve_observer(f"{__name__}:no_such_callable")
        self.assertIn("declares no", str(caught.exception))

    def test_a_non_callable_attribute_is_refused(self) -> None:
        with self.assertRaises(RunnerError) as caught:
            resolve_observer(f"{__name__}:NOT_CALLABLE")
        self.assertIn("is not callable", str(caught.exception))

    def test_an_observer_that_raises_refuses_the_run(self) -> None:
        self.product.declare(applicable())
        with self.assertRaises(RunnerError) as caught:
            self.go(observer=f"{__name__}:observe_by_raising")
        self.assertIn("reporting nothing as", str(caught.exception))

    def test_an_observer_returning_the_wrong_type_refuses_the_run(self) -> None:
        self.product.declare(applicable())
        with self.assertRaises(RunnerError) as caught:
            self.go(observer=f"{__name__}:observe_wrongly")
        self.assertIn("not a ProductObservation", str(caught.exception))

    def test_an_empty_inventory_is_a_measurement_failure_not_a_pass(self) -> None:
        self.product.declare(applicable())
        result = self.go(observer=f"{__name__}:observe_nothing")
        self.assertIn(FindingCode.INVENTORY_EMPTY, self.codes(result))
        self.assertFalse(result.report.conforms)


class TheCatalogueMayBeAbsentAndNotSilent(RunnerTestCase):
    """A stated absence, and the refusal that stops it buying silence."""

    def test_a_kernel_import_with_no_catalogue_is_refused(self) -> None:
        self.product.declare(applicable())
        result = self.go(observer=f"{__name__}:observe_without_catalogue")
        self.assertIn(FindingCode.CATALOGUE_ABSENT, self.codes(result))
        self.assertFalse(result.report.conforms)

    def test_no_kernel_import_and_no_catalogue_is_silent(self) -> None:
        """The near-miss, and this repository's own real shape."""
        self.product.declare(applicable())
        result = self.go(observer=f"{__name__}:observe_kernel_free")
        self.assertNotIn(FindingCode.CATALOGUE_ABSENT, self.codes(result))
        self.assertNotIn(FindingCode.SURFACE_UNKNOWN, self.codes(result))


class WhereTheDeclarationLives(RunnerTestCase):
    """The binding is honoured, and an unreadable profile refuses."""

    def test_a_bound_non_default_path_is_read(self) -> None:
        self.product.profile(
            {
                "kernel_adoption_binding": {
                    "declaration_path": ".dotmac/elsewhere.json",
                    "contract_version": "KernelAdoptionDeclaration.v1",
                }
            }
        )
        (self.product.root / ".dotmac" / "elsewhere.json").write_text(
            json.dumps(applicable()) + "\n", encoding="utf-8"
        )
        result = self.go()
        self.assertEqual(
            [FindingCode.DECLARATION_FIELDS_UNEVALUATED],
            self.codes(result),
            result.to_dict(),
        )
        self.assertEqual(
            ".dotmac/elsewhere.json", result.to_dict()["product"]["declaration_path"]
        )

    def test_the_default_path_is_read_when_no_profile_exists(self) -> None:
        self.product.declare(applicable())
        result = self.go()
        self.assertEqual(
            ".dotmac/kernel-adoption.json",
            result.to_dict()["product"]["declaration_path"],
        )

    def test_an_unreadable_profile_refuses_the_run(self) -> None:
        """An unreadable profile stops the run before anything is measured.

        Provenance is established first and reads the same file, so this is
        where an end-to-end run refuses now. The fall-back property itself is
        asserted directly below, because a property observed only through
        another check's ordering stops being observed the day that ordering
        changes.
        """
        self.product.declare(applicable())
        self.product.profile("{ not json\n")
        with self.assertRaises(RunnerError) as caught:
            self.go()
        self.assertIn("could not be read", str(caught.exception))

    def test_the_reader_never_falls_back_to_the_default_path(self) -> None:
        """Directly: an unreadable profile may bind elsewhere, so refuse.

        Reading SOME file and reporting on it would answer a question that
        could not be answered.
        """
        self.product.profile("{ not json\n")
        with self.assertRaises(RunnerError) as caught:
            _declaration_location(self.product.root)
        self.assertIn(
            "where the declaration lives is now unknown", str(caught.exception)
        )

    def test_a_profile_with_no_binding_uses_the_default(self) -> None:
        """The near-miss: a readable profile that simply states no binding."""
        self.product.declare(applicable())
        self.product.profile({"schema_version": 9})
        result = self.go()
        self.assertEqual(
            ".dotmac/kernel-adoption.json",
            result.to_dict()["product"]["declaration_path"],
        )


class ProvenanceIsBoundToGovernance(RunnerTestCase):
    """A copy of this package is a copy of the code, not the authority.

    Before this, `GOVERNANCE_ROOT` was the package's own parent directory and
    nothing else. A product that vendored the package got its own root, its own
    peeled HEAD, and a report claiming enforcement at a revision that is not a
    Governance commit -- including from a MODIFIED copy, which is the case that
    matters, because a modified copy can be made to conform.
    """

    def vendor(self) -> Path:
        """A product tree holding a COPY of the package, with its own remote."""
        vendored = self.product.root / "kernel_adoption_control"
        shutil.copytree(GOVERNANCE_ROOT / "kernel_adoption_control", vendored)
        return self.product.root

    def test_a_vendored_copy_cannot_assert_it_is_governance(self) -> None:
        root = self.vendor()
        self.product.declare(not_applicable())
        self.product.commit()
        with self.assertRaises(RunnerError) as caught:
            run(
                product_root=root,
                governance_root=root,
                observer_reference=f"{__name__}:observe_kernel_free",
                as_of=AS_OF,
            )
        self.assertIn("dotmac_erp", str(caught.exception))
        self.assertIn(CANONICAL_GOVERNANCE, str(caught.exception))

    def test_a_product_measured_against_a_governance_it_did_not_pin_is_refused(
        self,
    ) -> None:
        """The pin is the product's consent to be measured by that code.

        A product pinning an older Governance must not be reported as enforced
        by a newer one it has not adopted -- which is the whole sequencing
        claim, made checkable instead of asserted.
        """
        self.product.declare(applicable())
        self.product.profile(
            {"governance_model": self.product.governance_model("c" * 40)}
        )
        with self.assertRaises(RunnerError) as caught:
            self.go()
        self.assertIn("pins Governance at " + "c" * 40, str(caught.exception))

    def test_a_pin_to_some_other_repository_is_refused(self) -> None:
        model = self.product.governance_model()
        model["canonical_url"] = "https://github.com/michaelayoade/dotmac_erp"
        self.product.declare(applicable())
        self.product.profile({"governance_model": model})
        with self.assertRaises(RunnerError) as caught:
            self.go()
        self.assertIn("pins governance at", str(caught.exception))

    def test_a_product_claiming_a_local_governance_model_is_refused(self) -> None:
        """`local` is Governance's own statement, and this is not Governance."""
        self.product.declare(applicable())
        self.product.profile(
            {
                "governance_model": {
                    "kind": "local",
                    "source": "docs/adr/0006-x.md",
                    "status": "accepted",
                }
            }
        )
        with self.assertRaises(RunnerError) as caught:
            self.go()
        self.assertIn(
            "only the Governance repository itself may state", str(caught.exception)
        )

    def test_a_product_with_no_profile_is_refused(self) -> None:
        self.product.declare(applicable())
        (self.product.root / ".dotmac" / "standards-profile.json").unlink()
        with self.assertRaises(RunnerError) as caught:
            self.go()
        self.assertIn("states no governance_model", str(caught.exception))

    def test_the_matching_pin_is_admitted(self) -> None:
        """The near-miss all four refusals above must not be catching."""
        self.product.declare(applicable())
        self.assertIs(Provenance.PINNED, self.go().provenance)

    def test_governance_measuring_itself_is_self_provenance(self) -> None:
        result = run(
            product_root=REPO_ROOT,
            observer_reference="tools.kernel_adoption_observation:observe",
            as_of=AS_OF,
        )
        self.assertIs(Provenance.SELF, result.provenance)


class TheOriginIsObservedNotAsserted(RunnerTestCase):
    """The report must carry what was MEASURED, and the measurement must be literal.

    `to_dict` used to emit the module constant `CANONICAL_GOVERNANCE`, so every
    copy of this runner -- vendored or not -- reported the canonical URL. The
    predicate's vendoring arm therefore could not fail on any report the runner
    produced: the run-side check was real and the predicate-side one was
    decoration, satisfiable only by a hand-built document.
    """

    def configure_origin(self, url: str) -> None:
        _git(self.product.root, "config", "--local", "remote.origin.url", url)

    def test_a_report_carries_the_origin_that_was_observed(self) -> None:
        self.product.declare(not_applicable())
        document = self.go(observer=f"{__name__}:observe_kernel_free").to_dict()
        self.assertEqual(
            CANONICAL_GOVERNANCE, document["governance"]["origin"], document
        )
        self.assertIn(
            "dotmac_governance", str(document["governance"]["origin_configured"])
        )

    def test_an_insteadof_rewrite_does_not_move_the_observed_value(self) -> None:
        """The bypass the literal read exists to close.

        `git remote get-url` applies `url.<base>.insteadOf`, so ONE rewrite
        rule -- in the runner's global config, leaving nothing in the tree --
        makes any remote report as the canonical one. `git config --local
        --get` returns the configured value and ignores the rewrite. Both
        halves are asserted here: the bypass is shown WORKING against the
        rejected instrument, and shown ineffective against the chosen one.
        """
        self.configure_origin("https://github.com/michaelayoade/dotmac_erp.git")
        _git(
            self.product.root,
            "config",
            "--local",
            f"url.{CANONICAL_GOVERNANCE}.insteadOf",
            "https://github.com/michaelayoade/dotmac_erp",
        )
        rewritten = _git(self.product.root, "remote", "get-url", "origin")
        self.assertIn("dotmac_governance", rewritten, "the bypass no longer works")

        literal, observed = _observed_origin(self.product.root)
        self.assertIn("dotmac_erp", literal)
        self.assertEqual("https://github.com/michaelayoade/dotmac_erp", observed)

    def test_the_three_accepted_spellings_normalise_to_one(self) -> None:
        for spelling in (
            "https://github.com/michaelayoade/dotmac_governance",
            "https://github.com/michaelayoade/dotmac_governance.git",
            "https://GitHub.com/michaelayoade/dotmac_governance.git/",
            "ssh://git@github.com/michaelayoade/dotmac_governance.git",
            "git@github.com:michaelayoade/dotmac_governance.git",
        ):
            with self.subTest(spelling=spelling):
                self.assertEqual(CANONICAL_GOVERNANCE, _normalise_origin(spelling))

    def test_a_spelling_nobody_wrote_a_rule_for_is_refused(self) -> None:
        """Refused, not guessed at. A guess here is the whole provenance claim."""
        for spelling in (
            "file:///tmp/governance",
            "../governance",
            "/srv/git/governance",
            "https://github.com/",
            "",
        ):
            with self.subTest(spelling=spelling):
                self.assertIsNone(_normalise_origin(spelling))

    def test_a_near_miss_repository_is_not_normalised_into_the_canonical_one(
        self,
    ) -> None:
        """The normaliser must not be so eager that it erases the difference."""
        for spelling in (
            "https://github.com/michaelayoade/dotmac_governance_fork",
            "https://github.com/someone/dotmac_governance",
            "https://gitlab.com/michaelayoade/dotmac_governance",
            "https://github.com/Michaelayoade/dotmac_governance",
        ):
            with self.subTest(spelling=spelling):
                self.assertNotEqual(CANONICAL_GOVERNANCE, _normalise_origin(spelling))

    def test_a_checkout_with_no_configured_origin_is_refused(self) -> None:
        _git(self.product.root, "remote", "remove", "origin")
        with self.assertRaises(RunnerError) as caught:
            _observed_origin(self.product.root)
        self.assertIn("configures no local remote.origin.url", str(caught.exception))


class PinSufficiencyIsApplicabilityAware(RunnerTestCase):
    """ "Enough to detect a disagreement" is a different number for each state.

    The arm previously emitted a NOTICE below two sites and the report stayed
    conforming and citable -- a check that structurally could not fail, counted
    as one that passed.
    """

    def test_an_applicable_declaration_with_one_pin_site_is_an_error(self) -> None:
        self.product.declare(applicable())
        result = self.go(observer=f"{__name__}:observe_one_pin")
        self.assertIn(FindingCode.PIN_UNDETECTABLE, self.codes(result))
        self.assertFalse(result.report.conforms)

    def test_two_observations_at_one_location_are_one_observation(self) -> None:
        """Independence is a distinct (path, line), not a count of entries."""
        self.product.declare(applicable())
        result = self.go(observer=f"{__name__}:observe_duplicate_pin")
        self.assertIn(FindingCode.PIN_UNDETECTABLE, self.codes(result))

    def test_two_independent_observations_are_enough(self) -> None:
        """The near-miss: the arm becomes capable of failing and stays silent."""
        self.product.declare(applicable())
        result = self.go()
        self.assertNotIn(FindingCode.PIN_UNDETECTABLE, self.codes(result))

    def test_a_not_applicable_declaration_that_pins_the_kernel_is_refused(self) -> None:
        """Zero pin sites AND zero imports, or the stated premise is false."""
        self.product.declare(not_applicable())
        result = self.go(observer=f"{__name__}:observe_na_but_pinned")
        self.assertIn(FindingCode.DECLARATION_PREMISE_FALSE, self.codes(result))
        self.assertFalse(result.report.conforms)

    def test_a_not_applicable_declaration_with_no_pins_raises_no_error(
        self,
    ) -> None:
        """The near-miss, and this repository's own real shape.

        Silent about PINS, not silent overall: the run still discloses its one
        unread field. Asserting an empty list would make this test fail the day
        that disclosure was added, which is what happened.
        """
        self.product.declare(not_applicable())
        result = self.go(observer=f"{__name__}:observe_kernel_free")
        self.assertEqual(
            [],
            [
                item
                for item in result.report.findings
                if item.severity is Severity.ERROR
            ],
            result.to_dict(),
        )
        self.assertNotIn(FindingCode.PIN_UNDETECTABLE, self.codes(result))
        self.assertNotIn(FindingCode.PIN_DISAGREES, self.codes(result))

    def test_a_refused_declaration_leaves_the_sufficiency_question_unanswered(
        self,
    ) -> None:
        """The requirement is a function of an applicability nobody stated.

        So the pin arm reports nothing, and the refusal says so rather than
        letting the silence read as a pass.
        """
        self.product.declare(None)
        result = self.go(observer=f"{__name__}:observe_one_pin")
        self.assertNotIn(FindingCode.PIN_UNDETECTABLE, self.codes(result))
        message = result.report.findings[0].message
        self.assertIn("Arms 1, 4, 6 and 7", message)


class TheExitCodeConsultsCitability(RunnerTestCase):
    """`is_enforced` was printed and nothing acted on it.

    A step could go green while its own log said the result was not citable,
    and the badge is what gets quoted.
    """

    def invoke(self) -> int:
        self.product.commit()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            return main(
                [
                    "--root",
                    str(self.product.root),
                    "--observer",
                    f"{__name__}:observe_consumer",
                    "--as-of",
                    AS_OF.isoformat(),
                ]
            )

    def test_a_conforming_applicable_run_exits_nonzero(self) -> None:
        """Conforming and NOT citable is its own outcome, and it is not success."""
        self.product.declare(applicable())
        self.assertEqual(3, self.invoke())

    def test_a_run_with_findings_exits_one(self) -> None:
        self.product.declare(None)
        self.assertEqual(1, self.invoke())

    def test_a_refused_run_exits_two(self) -> None:
        self.product.declare(applicable())
        self.product.profile("{ not json\n")
        self.assertEqual(2, self.invoke())

    def test_a_citable_run_exits_zero(self) -> None:
        """The admit control. Without it every assertion above could hold while
        nothing at all could ever succeed."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = main(
                [
                    "--root",
                    str(REPO_ROOT),
                    "--observer",
                    "tools.kernel_adoption_observation:observe",
                    "--as-of",
                    AS_OF.isoformat(),
                ]
            )
        if code == 3 and "uncommitted changes" in buffer.getvalue():
            self.skipTest(
                "this checkout is dirty; CI runs on a clean one and that is "
                "the run whose exit code is the claim"
            )
        self.assertEqual(0, code, buffer.getvalue())


class TheImportRootIsScopedAndRestored(RunnerTestCase):
    """The measured checkout is on `sys.path` for the observer load and no longer.

    It used to be inserted at position 0 and left there, making the measured
    tree the primary import root for the rest of the process -- broader than
    the "an observer is called" exposure ADR 0042 § A9 names.
    """

    def test_sys_path_is_unchanged_after_a_run(self) -> None:
        self.product.declare(applicable())
        before = list(sys.path)
        self.go()
        self.assertEqual(before, sys.path)

    def test_sys_path_is_unchanged_after_a_refused_observer(self) -> None:
        """The finally arm. A refusal must not leave the path widened."""
        self.product.declare(applicable())
        before = list(sys.path)
        with self.assertRaises(RunnerError):
            self.go(observer=f"{__name__}:observe_by_raising")
        self.assertEqual(before, sys.path)


class EnforcementIsVisible(RunnerTestCase):
    """A run report is what "CI-enforced" must exhibit, and each way it fails.

    The sequencing this protects: a product pinning a Governance revision from
    before the runner existed produces NO report, and no report is not a pass.
    A report that exists but fails a binding condition says so, with the
    reason, rather than being indistinguishable from an enforced one.
    """

    def base(self) -> dict[str, Any]:
        return {
            "contract": RUN_CONTRACT,
            "as_of": TODAY,
            "governance": {
                "provenance": "self",
                "origin_configured": CANONICAL_GOVERNANCE + ".git",
                "origin": CANONICAL_GOVERNANCE,
                "revision": "a" * 40,
                "worktree_clean": True,
            },
            "product": {
                "revision": "b" * 40,
                "worktree_clean": True,
                "declaration": {
                    "state": "present",
                    "applicability": "not_applicable",
                },
            },
            "observation": {"source_count": 12},
            "findings": {
                "conforms": True,
                "findings": [
                    {
                        "code": "kernel.declaration.fields-unevaluated",
                        "severity": "notice",
                        "message": "disclosed",
                    }
                ],
            },
        }

    def test_a_complete_conforming_report_is_citable(self) -> None:
        verdict, reason = inspect_report_document(self.base())
        self.assertIs(DocumentVerdict.WELL_FORMED, verdict, reason)

    def test_a_document_that_is_not_a_run_report_is_not_enforcement(self) -> None:
        document = self.base()
        document["contract"] = "SomethingElse.v1"
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("predating the runner produces none", reason)

    def test_an_absent_contract_key_is_not_enforcement(self) -> None:
        """The shape a pre-runner Governance revision leaves behind: nothing."""
        verdict, reason = inspect_report_document({})
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn(RUN_CONTRACT, reason)

    def test_a_report_naming_another_repository_is_not_enforcement(self) -> None:
        """The vendoring claim, checked at the predicate as well as at the run."""
        document = self.base()
        governance = dict(document["governance"])
        governance["origin"] = "https://github.com/michaelayoade/dotmac_erp"
        document["governance"] = governance
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("not the authority behind it", reason)

    def test_a_report_with_no_established_provenance_is_not_enforcement(self) -> None:
        document = self.base()
        governance = dict(document["governance"])
        governance["provenance"] = "assumed"
        document["governance"] = governance
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("not an established one", reason)

    def test_a_refused_declaration_is_not_citable(self) -> None:
        document = self.base()
        product = dict(document["product"])
        product["declaration"] = {"state": "DeclarationMissing", "detail": "gone"}
        document["product"] = product
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("which is a refusal", reason)

    def test_a_moving_governance_coordinate_is_not_enforcement(self) -> None:
        document = self.base()
        governance = dict(document["governance"])
        governance["revision"] = "main"
        document["governance"] = governance
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("not a peeled commit", reason)

    def test_a_dirty_governance_checkout_is_not_enforcement(self) -> None:
        document = self.base()
        governance = dict(document["governance"])
        governance["worktree_clean"] = False
        document["governance"] = governance
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("not the code that ran", reason)

    def test_a_dirty_product_checkout_is_not_enforcement(self) -> None:
        document = self.base()
        product = dict(document["product"])
        product["worktree_clean"] = False
        document["product"] = product
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("not the source that was read", reason)

    def test_an_empty_inventory_is_not_enforcement(self) -> None:
        document = self.base()
        document["observation"] = {"source_count": 0}
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("passes for the wrong reason", reason)

    def test_a_non_conforming_run_is_not_enforcement(self) -> None:
        document = self.base()
        document["findings"] = {"conforms": False, "findings": []}
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("disagrees with itself", reason)

    def test_a_report_that_contradicts_itself_is_refused(self) -> None:
        """`conforms` was taken on trust, so ten errors could sit beneath it.

        The predicate checked the report's SHAPE and never checked the report
        against ITSELF -- a summary verdict nothing recomputes, which is the
        same defect as a declared field nothing reads.
        """
        document = self.base()
        document["findings"] = {
            "conforms": True,
            "findings": [
                {"code": "kernel.surface.prohibited", "severity": "error"}
                for _ in range(10)
            ],
        }
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("10 error finding(s)", reason)

    def test_a_notice_only_report_is_still_well_formed(self) -> None:
        """The admit control for the arm above.

        Without it the consistency check is indistinguishable from one that
        rejects everything -- and this repository's own citable run IS
        notice-only, because it discloses its unread `product_revision`.
        """
        document = self.base()
        document["findings"] = {
            "conforms": True,
            "findings": [
                {"code": "kernel.declaration.fields-unevaluated", "severity": "notice"},
                {"code": "kernel.declaration.fields-unevaluated", "severity": "notice"},
            ],
        }
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.WELL_FORMED, verdict, reason)
        self.assertIn("2 notice(s), no errors", reason)

    def test_an_unrecognised_severity_is_refused_not_read_as_harmless(self) -> None:
        for severity in ("warning", "ERROR", "", None, 3, {"level": "error"}):
            with self.subTest(severity=severity):
                document = self.base()
                document["findings"] = {
                    "conforms": True,
                    "findings": [{"code": "x", "severity": severity}],
                }
                verdict, reason = inspect_report_document(document)
                self.assertIs(DocumentVerdict.MALFORMED, verdict)
                self.assertIn("not read as a harmless one", reason)

    def test_a_findings_section_with_no_list_is_refused(self) -> None:
        for value in ({"conforms": True}, {"conforms": True, "findings": "none"}):
            with self.subTest(value=value):
                verdict, reason = inspect_report_document(
                    {**self.base(), "findings": value}
                )
                self.assertIs(DocumentVerdict.MALFORMED, verdict)
                self.assertIn("summarises nothing", reason)

    def test_a_finding_that_is_not_an_object_is_refused(self) -> None:
        document = self.base()
        document["findings"] = {"conforms": True, "findings": ["kernel.pin.disagrees"]}
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("is not an object", reason)

    def test_a_boolean_source_count_is_not_one_file(self) -> None:
        """`isinstance(True, int)` is True, so `source_count: true` read as 1."""
        document = self.base()
        document["observation"] = {"source_count": True}
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.MALFORMED, verdict)
        self.assertIn("malformed report", reason)

    def test_a_real_run_produces_a_document_the_inspector_accepts(self) -> None:
        """Non-vacuity: the arm is satisfiable by the runner's own output.

        An inspector that rejected every real report would make every assertion
        above pass while nothing could ever be well-formed. What it establishes
        is only that the document agrees with itself -- see
        `ADocumentCannotEstablishThatARunProducedIt` for the claim it can never
        make.
        """
        self.product.declare(not_applicable())
        document = self.go(observer=f"{__name__}:observe_kernel_free").to_dict()
        # The Governance worktree under test is the one this suite runs from and
        # may legitimately be dirty; substitute only that one fact.
        document["governance"] = dict(document["governance"])
        document["governance"]["worktree_clean"] = True
        verdict, reason = inspect_report_document(document)
        self.assertIs(DocumentVerdict.WELL_FORMED, verdict, reason)


class ADocumentCannotEstablishThatARunProducedIt(RunnerTestCase):
    """Open decision 52 (5). The defect, its repair, and the repair's boundary.

    **The defect, exhibited by this suite's own history.** `is_enforced` was a
    predicate over a REPORT, not over a repository: anyone who could write the
    JSON could write a passing one. The admit control for it -- the test
    directly above, before this change -- was a hand-built dictionary that
    returned `True`. A predicate whose positive case had only ever been
    exhibited by a fabricated input was not measuring what its name said.

    **The repair is structural rather than an added condition.**
    `inspect_report_document` returns a `DocumentVerdict`, whose value set does
    not CONTAIN a citable member, so no amount of document-writing produces the
    claim. Citability is asked of a `RunReport` OBJECT and requires identity
    membership of the set `run()` populates.

    **The boundary, asserted rather than promised:** serialising a citable
    report and reading it back yields a document, and the document is only ever
    well-formed. Crossing that boundary needs decision 17's oracle.
    """

    def _clean(self, report: RunReport) -> RunReport:
        """The same report with the two worktree facts forced clean.

        The Governance checkout this suite runs from may legitimately be dirty,
        and that is a fact about the developer's tree rather than about the
        predicate. `dataclasses.replace` keeps this OUT of `_PRODUCED`, which is
        exactly what the first assertion below needs.
        """
        return dataclasses.replace(
            report, governance_worktree_clean=True, product_worktree_clean=True
        )

    def test_a_hand_built_report_is_not_citable_however_plausible(self) -> None:
        """The planted violation. Every field is right and it did not run."""
        self.product.declare(not_applicable())
        produced = self.go(observer=f"{__name__}:observe_kernel_free")
        forged = self._clean(produced)
        verdict, reason = citability(forged)
        self.assertIs(Citability.NOT_CITABLE, verdict)
        self.assertIn("not produced by run() in this process", reason)

    def test_a_produced_report_is_citable(self) -> None:
        """The admit control. Without it the arm above rejects everything.

        Skipped rather than forced when the developer's own checkout is dirty:
        the substitution that makes the assertion possible is the same
        substitution the planted violation uses, so it cannot be applied here.
        CI runs on a clean checkout and that is the run whose verdict is the
        claim.
        """
        self.product.declare(not_applicable())
        produced = self.go(observer=f"{__name__}:observe_kernel_free")
        if not produced.governance_worktree_clean:
            self.skipTest("this Governance checkout is dirty; CI runs on a clean one")
        verdict, reason = citability(produced)
        self.assertIs(Citability.CITABLE, verdict, reason)
        self.assertIn("produced by this run", reason)

    def test_serialising_a_citable_report_yields_only_a_document(self) -> None:
        """The boundary. A report on disk is not self-authenticating."""
        self.product.declare(not_applicable())
        produced = self.go(observer=f"{__name__}:observe_kernel_free")
        document = json.loads(json.dumps(produced.to_dict()))
        document["governance"]["worktree_clean"] = True
        verdict, _ = inspect_report_document(document)
        self.assertIs(DocumentVerdict.WELL_FORMED, verdict)
        self.assertNotIn(
            "citable",
            {member.value for member in DocumentVerdict},
            "DocumentVerdict must have no citable member: a value set that "
            "cannot express the claim is what stops a document making it",
        )

    def test_a_v1_applicable_run_is_not_citable(self) -> None:
        """The narrowing ADR 0042 § A8 settled, moved to where it can be true.

        It used to be a condition over a dictionary, so it was satisfied by
        writing `"applicability": "not_applicable"` into one. It is now read
        off the declaration the runner itself parsed.
        """
        self.product.declare(applicable())
        produced = self.go()
        verdict, reason = citability(produced)
        self.assertIs(Citability.NOT_CITABLE, verdict)
        self.assertIn("KernelAdoptionDeclaration.v1", reason)
        self.assertIn("required_surfaces", reason)


class V2ApplicableActivationEndToEnd(RunnerTestCase):
    """The admit control for ACTIVATION itself, through the real runner and CLI.

    Engine-only tests do not prove activation. Every arm proved in
    `test_kernel_adoption_v2` is a function of inputs somebody handed the
    engine; the path a product will actually take is `run()` and `main()`, and
    until it is exercised end to end the claim "a v2 applicable product can be
    CI-enforced" rests on a composition nobody performed.

    That matters more here than anywhere else in this package, because the
    failure mode of an unproved activation is a product believing it is
    enforced when nothing ran. Every previous pass on this package was caught
    by the same shape -- a rule proved only in the refusing direction.

    Four properties, none of them stubbed:

    1. **A strict predecessor, decided by real Git.** The declaration names the
       fixture repository's FIRST commit and is then committed on top, so the
       coordinate is a genuine ancestor of the measured revision and
       `_predecessor_observation` runs against a real history. No
       `PredecessorObservation` is constructed anywhere in this class.
    2. **Produced-report identity.** The report `citability` accepts is the one
       `run()` returned, identity-present in the set it populated -- item 5's
       whole claim, exercised on the activation path rather than on a fixture.
    3. **CITABLE**, which a v1 `applicable` declaration can never be.
    4. **Exit 0** from `main`, which is what a product's CI step actually reads.
    """

    def enrol(self) -> Any:
        """Write and commit a v2 declaration the way a product really would.

        The order is the point and is not an artefact of the fixture. A product
        commits its source, reads the resulting HEAD, writes that commit into
        `source_predecessor`, and commits the declaration -- at which point HEAD
        has moved and the coordinate is strictly behind it. A declaration
        naming the revision that contains it is not merely refused here; it
        could not have been written.
        """
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        self.product.declare(applicable_v2(predecessor))
        self.product.commit()
        measured = _git(self.product.root, "rev-parse", "HEAD")
        self.assertNotEqual(predecessor, measured)
        return predecessor, measured

    def test_a_v2_applicable_product_runs_clean_and_is_citable(self) -> None:
        predecessor, measured = self.enrol()
        result = run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_v2_consumer",
            as_of=AS_OF,
        )
        self.assertEqual([], self.codes(result), result.to_dict())
        self.assertEqual(measured, result.product_revision)

        # (1) the ancestor check ran for real and decided TRUE.
        summary = result.to_dict()["product"]["declaration"]
        self.assertEqual(predecessor, summary["source_predecessor"])
        self.assertEqual(KERNEL_ADOPTION_CONTRACT_V2, summary["contract"])
        self.assertEqual("applicable", summary["applicability"])

        # (2)+(3) the produced report is identity-present and citable.
        if not result.governance_worktree_clean:
            self.skipTest(
                "this Governance checkout is dirty; CI runs on a clean one and "
                "that is the run whose verdict is the claim"
            )
        verdict, reason = citability(result)
        self.assertIs(Citability.CITABLE, verdict, reason)
        self.assertIn("produced by this run", reason)
        self.assertIn(KERNEL_ADOPTION_CONTRACT_V2, reason)

    def test_the_cli_exits_zero_for_a_v2_applicable_product(self) -> None:
        """(4). The exit code is what a product's CI step actually reads.

        A v1 applicable product exits 3 here -- asserted in
        `TheExitCodeConsultsCitability` -- so this is the difference the
        successor contract makes, read at the surface a workflow sees.
        """
        self.enrol()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = main(
                [
                    "--root",
                    str(self.product.root),
                    "--observer",
                    f"{__name__}:observe_v2_consumer",
                    "--as-of",
                    AS_OF.isoformat(),
                ]
            )
        if code == 3 and "uncommitted changes" in buffer.getvalue():
            self.skipTest("this Governance checkout is dirty; CI runs on a clean one")
        self.assertEqual(0, code, buffer.getvalue())
        self.assertIn("citable as enforcement: citable", buffer.getvalue())

    def test_the_same_product_under_v1_is_not_citable(self) -> None:
        """The contrast that makes the admit control mean something.

        Same repository, same observation, same clean report -- and a v1
        `applicable` declaration. It must NOT be citable, or the assertion
        above is measuring the runner rather than the contract.
        """
        self.product.declare(applicable())
        result = self.go(observer=f"{__name__}:observe_v2_consumer")
        verdict, reason = citability(result)
        self.assertIs(Citability.NOT_CITABLE, verdict)
        self.assertIn("KernelAdoptionDeclaration.v1", reason)

    def test_a_real_non_ancestor_is_refused_end_to_end(self) -> None:
        """The planted defect against the real probe, not a constructed verdict.

        The predecessor is a genuine commit of this repository -- made on a
        sibling branch -- which is therefore PRESENT and yet not behind what was
        measured. That distinction is the one the probe has to get right: an
        ABSENT commit exits 128 and is reported undecided, so a plant using a
        fabricated hash would exercise the undecided arm while appearing to
        exercise this one.

        **Why the equality case is not planted here.** A declaration naming the
        revision that contains it cannot be produced by a commit flow: writing
        the declaration and committing it advances HEAD, so the named commit
        becomes a real ancestor. That is not a gap in this test -- it is the
        premise the coordinate rests on, "a committed file cannot contain its
        own commit", showing up as an unreachable state. An earlier draft of
        this test tried to plant it anyway and silently became a second admit
        control: it produced NO findings and asserted one. The refutation is
        unit-tested where it can actually be reached, against a real
        repository, in `ThePredecessorProbe
        ::test_the_measured_revision_itself_is_refused`.
        """
        self.product.commit()
        _git(self.product.root, "checkout", "-q", "-b", "sibling")
        self.product.commit()
        sibling = _git(self.product.root, "rev-parse", "HEAD")
        _git(self.product.root, "checkout", "-q", "main")
        self.product.declare(applicable_v2(sibling))
        self.product.commit()
        measured = _git(self.product.root, "rev-parse", "HEAD")
        self.assertNotEqual(sibling, measured)
        result = run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_v2_consumer",
            as_of=AS_OF,
        )
        self.assertIn(FindingCode.PREDECESSOR_NOT_ANCESTOR, self.codes(result))

    def test_a_stale_surface_digest_is_refused_end_to_end(self) -> None:
        """The other coordinate, through the real path: source moved, declaration did not."""
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        body = applicable_v2(predecessor)
        body["source_surface"] = {
            "algorithm": SOURCE_SURFACE_ALGORITHM,
            "digest": "sha256:" + "0" * 64,
        }
        self.product.declare(body)
        self.product.commit()
        result = run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_v2_consumer",
            as_of=AS_OF,
        )
        self.assertIn(FindingCode.SOURCE_SURFACE_DRIFT, self.codes(result))


class TheReportRecordsWhichAlgorithmWasSelected(RunnerTestCase):
    """`source_surface_algorithm`: provenance, and NOTHING stronger.

    Its exact meaning, and the whole of it: **the algorithm selected by the
    parsed declaration.** It does not say the evaluation completed, does not
    say it passed, and is never an input to any verdict. `citability` and the
    exit code are where a pass lives.

    It exists because two canonicalizations are now selectable. A reader
    holding only this artifact could not otherwise tell which one the run
    compared under, and Michael's standing rule -- a v1 receipt is never v2
    evidence -- needs receipts that say which they are.

    It is ADDITIVE and OPTIONAL within `KernelAdoptionRun.v1`. The report
    carries no digest and its reader permits keys it does not know, so no
    contract version moves. The last test here holds that: remove the key and
    the document is still well-formed. If it ever becomes mandatory, or if
    anything starts reading it as evidence of a passed evaluation, the report
    contract has to be versioned and that test is where it will be noticed.
    """

    def enrol(self, **overrides: Any) -> tuple[str, str]:
        """A committed v2 declaration whose predecessor is real. See
        `V2ApplicableActivationEndToEnd.enrol` for why the order matters."""
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        self.product.declare(applicable_v2(predecessor, **overrides))
        self.product.commit()
        return predecessor, _git(self.product.root, "rev-parse", "HEAD")

    def go_v2(self) -> Any:
        return run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_v2_consumer",
            as_of=AS_OF,
        )

    def summary(self, result: Any) -> dict[str, Any]:
        value: dict[str, Any] = result.to_dict()["product"]["declaration"]
        return value

    # ── (1) one parsed declaration, one access path ─────────────────────────

    def test_the_recorded_algorithm_is_the_parsed_declarations_own_object(
        self,
    ) -> None:
        """Not a second read that could diverge -- the SAME string object.

        `assertIs`, not `assertEqual`. Equality would also hold for a summary
        that re-parsed the document off disk and happened to agree; identity
        holds only if the value came off the very dataclass the engine
        dispatched on.
        """
        self.enrol(
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": V2_IDENTITY_DIGEST,
            }
        )
        result = self.go_v2()
        coordinate = result.declaration.declaration.source_surface
        self.assertIsNotNone(coordinate)
        self.assertIs(
            coordinate.algorithm, self.summary(result)["source_surface_algorithm"]
        )

    def test_the_runner_reads_the_declaration_once_and_shares_that_one_object(
        self,
    ) -> None:
        """The structural half of (1), read off `run()`'s own syntax tree.

        A behavioural test can only show the two AGREED on the inputs it was
        given. This shows they cannot disagree at all: `run()` calls
        `read_declaration` exactly once, binds it to one name, and passes that
        same name to the evaluator's inputs and to the report. There is no
        second parse for the summary to drift from.
        """
        tree = ast.parse(inspect.getsource(run))
        reads = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "read_declaration"
        ]
        self.assertEqual(1, len(reads), "run() must parse the declaration once")

        passed_to = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and any(
                keyword.arg == "declaration"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "outcome"
                for keyword in node.keywords
            )
        }
        self.assertEqual({"KernelAdoptionInputs", "RunReport"}, passed_to)

    # ── (2) the caller cannot supply it ─────────────────────────────────────

    def test_no_caller_can_supply_the_recorded_algorithm(self) -> None:
        """A field a caller can set records the caller's claim, not the fact.

        Three closures, together: `run()` takes no such parameter, `RunReport`
        holds no such field, and the key is assigned in exactly ONE place in
        the whole package -- from an attribute of the parsed declaration, never
        from an argument. The last is the one that matters: a second assignment
        anywhere, from anything else, fails here.
        """
        self.assertNotIn("source_surface_algorithm", inspect.signature(run).parameters)
        self.assertNotIn(
            "source_surface_algorithm",
            {field.name for field in dataclasses.fields(RunReport)},
        )

        package = REPO_ROOT / "kernel_adoption_control"
        writes: list[tuple[str, str]] = []
        for path in sorted(package.glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.slice, ast.Constant)
                        and target.slice.value == "source_surface_algorithm"
                    ):
                        writes.append((path.name, ast.dump(node.value)))
        self.assertEqual(1, len(writes), writes)
        name, value = writes[0]
        self.assertEqual("runner.py", name)
        # Derived from the declaration, and from nothing a caller reaches.
        self.assertIn("attr='algorithm'", value)
        self.assertIn("attr='source_surface'", value)
        self.assertIn("id='declaration'", value)

    def test_the_recorded_value_can_only_ever_be_one_the_contract_admits(
        self,
    ) -> None:
        """The other half of (2): even the document cannot smuggle a value in.

        A product writes `source_surface.algorithm` itself, so the field IS
        product-supplied text in the loosest sense. What stops it being the
        caller's claim is that the parser admits exactly two names, so the
        recorded value is always one the runner has an evaluation for.
        """
        self.enrol()
        result = self.go_v2()
        self.assertIn(
            self.summary(result)["source_surface_algorithm"],
            ACCEPTED_SOURCE_SURFACE_ALGORITHMS,
        )
        self.assertEqual(2, len(ACCEPTED_SOURCE_SURFACE_ALGORITHMS))

    # ── (3) both algorithms, through the real runner ────────────────────────

    def test_a_real_run_records_v1_when_v1_was_declared(self) -> None:
        self.enrol()
        result = self.go_v2()
        self.assertEqual([], self.codes(result), result.to_dict())
        self.assertEqual(
            SOURCE_SURFACE_ALGORITHM,
            self.summary(result)["source_surface_algorithm"],
        )

    def test_a_real_run_records_v2_when_v2_was_declared(self) -> None:
        """The same product, the same observation, the successor algorithm.

        Clean, so the v2 evaluation really ran against `V2_IDENTITY_DIGEST` --
        a value only the v2 canonicalization produces. The pair with the test
        above is what makes the field a record of a CHOICE rather than a
        constant.
        """
        self.enrol(
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": V2_IDENTITY_DIGEST,
            }
        )
        result = self.go_v2()
        self.assertEqual([], self.codes(result), result.to_dict())
        self.assertEqual(
            SOURCE_SURFACE_IDENTITY_ALGORITHM,
            self.summary(result)["source_surface_algorithm"],
        )

    def test_the_two_runs_do_not_record_the_same_value(self) -> None:
        """Non-vacuity for the pair above: a field hard-coded to either name
        would pass one of them and fail here."""
        self.assertNotEqual(SOURCE_SURFACE_ALGORITHM, SOURCE_SURFACE_IDENTITY_ALGORITHM)
        self.assertNotEqual(V2_SURFACE_DIGEST, V2_IDENTITY_DIGEST)

    # ── (4) null for not_applicable; nothing manufactured otherwise ─────────

    def test_a_not_applicable_v2_declaration_records_null_not_an_algorithm(
        self,
    ) -> None:
        """The key is PRESENT and the value is `None`.

        "No coordinate was declared" and "this artifact does not speak about
        coordinates" are different readings, and omitting the key would merge
        them.
        """
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        self.product.declare(not_applicable_v2(predecessor))
        self.product.commit()
        result = run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_kernel_free",
            as_of=AS_OF,
        )
        summary = self.summary(result)
        self.assertIn("source_surface_algorithm", summary)
        self.assertIsNone(summary["source_surface_algorithm"])

    def test_a_missing_or_unreadable_declaration_manufactures_nothing(self) -> None:
        """The key is ABSENT, and that is a third reading kept distinct.

        This is the arm that stops the `None` above from being vacuous. An
        implementation that emitted `None` for every non-`present` declaration
        would pass the test above and would be MANUFACTURING a coordinate
        reading for a document it could not read. Both states are driven here,
        through the real runner, and both are asserted to omit the key.
        """
        self.product.declare(None)
        self.product.commit()
        missing = run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_kernel_free",
            as_of=AS_OF,
        )
        self.assertEqual("DeclarationMissing", self.summary(missing)["state"])
        self.assertNotIn("source_surface_algorithm", self.summary(missing))

        self.product.declare("{ not json")
        self.product.commit()
        unreadable = run(
            product_root=self.product.root,
            observer_reference=f"{__name__}:observe_kernel_free",
            as_of=AS_OF,
        )
        self.assertEqual("DeclarationUnreadable", self.summary(unreadable)["state"])
        self.assertNotIn("source_surface_algorithm", self.summary(unreadable))

    def test_the_three_readings_stay_distinguishable(self) -> None:
        """Present-with-a-name, present-with-null, absent -- and a fourth case.

        A `KernelAdoptionDeclaration.v1` document also omits the key, because
        v1 has no such coordinate at all. That is a fourth state sharing the
        "absent" spelling, and it is distinguishable by `contract` and `state`,
        which is asserted here rather than assumed.
        """
        self.product.declare(applicable())
        self.product.commit()
        v1_summary = self.summary(self.go(observer=f"{__name__}:observe_v2_consumer"))
        self.assertNotIn("source_surface_algorithm", v1_summary)
        self.assertEqual("present", v1_summary["state"])
        self.assertEqual(KERNEL_ADOPTION_CONTRACT, v1_summary["contract"])

    # ── (5) the field is not a pass ─────────────────────────────────────────

    def test_a_drifted_run_still_fails_while_naming_a_supported_algorithm(
        self,
    ) -> None:
        """The non-vacuity arm, and the one misreading that would matter.

        The declaration names `dmg-kernel-surface-v2`, the field records it,
        and the run REFUSES: the digest does not describe the measured source.
        A reader who took the field for a verdict would read this artifact as a
        pass. It is not one, and the exit code says so.
        """
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        self.product.declare(
            applicable_v2(
                predecessor,
                source_surface={
                    "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                    "digest": "sha256:" + "0" * 64,
                },
            )
        )
        self.product.commit()
        result = self.go_v2()
        self.assertEqual(
            SOURCE_SURFACE_IDENTITY_ALGORITHM,
            self.summary(result)["source_surface_algorithm"],
        )
        self.assertIn(FindingCode.SOURCE_SURFACE_DRIFT, self.codes(result))
        self.assertTrue(
            any(
                finding.severity is Severity.ERROR for finding in result.report.findings
            )
        )

    # ── (6) editing it in a stored report changes nothing ───────────────────

    def test_editing_the_field_in_a_stored_report_cannot_make_it_citable(
        self,
    ) -> None:
        """Provenance is identity, not content -- for this field like any other.

        Two closures. A DOCUMENT can never be citable: `inspect_report_document`
        has no citable verdict to return, so editing a key in a file cannot
        reach one however plausible the edit. And `citability` tests identity
        membership of the set `run()` populates, so a hand-built `RunReport`
        carrying a supported algorithm is refused -- `eq=False` is what stops a
        field-for-field copy testing as the original.
        """
        self.enrol(
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": V2_IDENTITY_DIGEST,
            }
        )
        result = self.go_v2()
        document = json.loads(json.dumps(result.to_dict()))
        document["product"]["declaration"]["source_surface_algorithm"] = (
            SOURCE_SURFACE_ALGORITHM
        )
        verdict, _ = inspect_report_document(document)
        self.assertIn(verdict, (DocumentVerdict.WELL_FORMED, DocumentVerdict.MALFORMED))
        self.assertNotIn("citable", [member.value for member in DocumentVerdict])

        forged = RunReport(
            **{
                field.name: getattr(result, field.name)
                for field in dataclasses.fields(RunReport)
            }
        )
        self.assertIsNot(result, forged)
        citable, reason = citability(forged)
        self.assertIs(Citability.NOT_CITABLE, citable)
        self.assertIn("not produced by run() in this process", reason)

    # ── additive and optional; the report contract did not move ─────────────

    def test_the_field_is_optional_and_the_report_contract_did_not_move(
        self,
    ) -> None:
        """`KernelAdoptionRun.v1` is unchanged, and this is why it may be.

        The report carries no digest, so adding a key cannot invalidate a
        stored one, and its reader permits keys it does not know. Removing the
        field from a real report's serialization leaves the document
        well-formed -- which is the operational meaning of "optional", and the
        assertion that would fail the day it became mandatory or the day
        something started reading it as a verdict.
        """
        self.assertEqual("KernelAdoptionRun.v1", RUN_CONTRACT)
        self.enrol(
            source_surface={
                "algorithm": SOURCE_SURFACE_IDENTITY_ALGORITHM,
                "digest": V2_IDENTITY_DIGEST,
            }
        )
        result = self.go_v2()
        if not result.governance_worktree_clean:
            self.skipTest(
                "this Governance checkout is dirty, which makes every report "
                "it produces malformed for a reason that is not this field. "
                "CI runs on a clean one and that is the run whose verdict is "
                "the claim"
            )
        document = json.loads(json.dumps(result.to_dict()))
        self.assertIs(DocumentVerdict.WELL_FORMED, inspect_report_document(document)[0])
        del document["product"]["declaration"]["source_surface_algorithm"]
        self.assertIs(
            DocumentVerdict.WELL_FORMED,
            inspect_report_document(document)[0],
            "the field must stay ADDITIVE: a reader that requires it has "
            "changed the report contract without versioning it",
        )


class TheRunnerRunsWhereTheSubjectIs(unittest.TestCase):
    """This repository is a subject of the standard, not only its author."""

    def test_this_repository_declares_its_own_kernel_adoption(self) -> None:
        path = REPO_ROOT / ".dotmac" / "kernel-adoption.json"
        self.assertTrue(path.is_file(), "the runner's own repository must declare")

    def test_the_governance_root_is_derived_and_not_supplied(self) -> None:
        """A product that could name the Governance root could name a revision.

        `GOVERNANCE_ROOT` comes from this package's own file location, so the
        revision a report claims is the revision that ran.
        """
        self.assertEqual(REPO_ROOT, GOVERNANCE_ROOT)

    def test_this_repository_passes_its_own_gate(self) -> None:
        """The admit control on the real subject, per ADR 0034's shape.

        A guard observed only failing is indistinguishable from one that
        refuses everything. `--as-of` is fixed rather than read from a clock so
        this assertion means the same thing in every future run.
        """
        import tools.kernel_adoption_observation as observation

        result = run(
            product_root=REPO_ROOT,
            observer_reference="tools.kernel_adoption_observation:observe",
            as_of=AS_OF,
        )
        self.assertGreater(result.source_count, 20)
        self.assertTrue(result.report.conforms, result.to_dict())
        self.assertIsNotNone(observation.observe)


class TheBindingNamesAContractAndTheDocumentMustBeIt(RunnerTestCase):
    """Defect 2. `contract_version` was parsed, validated and read by nothing.

    `#82` shipped the v2 DECLARATION parser without widening the PROFILE
    binding vocabulary, so `KERNEL_ADOPTION_CONTRACT_VERSIONS` admitted only
    `KernelAdoptionDeclaration.v1` and a v2 product could not bind its own
    document. Widening that set alone would have been half a repair: the field
    was compared with nothing, so a v1 binding over a v2 document passed in
    silence. Both halves are here.

    The refusal is a `RunnerError` and not a `Finding`, and the boundary is
    why: `FindingCode` is a closed vocabulary about PRODUCT SOURCE, held there
    by `test_no_finding_code_speaks_about_a_profile_document`. A code about a
    profile binding would be this package acquiring an opinion on a document
    `standards_control` owns.
    """

    def bind(self, contract: str, path: str = ".dotmac/kernel-adoption.json") -> None:
        self.product.profile(
            {
                "kernel_adoption_binding": {
                    "declaration_path": path,
                    "contract_version": contract,
                }
            }
        )

    def enrol_v2(self) -> str:
        """Commit source, read HEAD, write a v2 naming it. `go` commits again.

        The order is the coordinate's own requirement, not a fixture habit: a
        committed file cannot contain its own commit, so `source_predecessor`
        has to be read before the declaration that names it is committed.
        """
        self.product.commit()
        predecessor = _git(self.product.root, "rev-parse", "HEAD")
        self.product.declare(applicable_v2(predecessor))
        return predecessor

    # -- 1. the one most likely to be skipped --------------------------------

    def test_a_stated_binding_never_falls_back_to_the_default_path(self) -> None:
        """A bound path that is not there REFUSES; it does not read the default.

        The plant is deliberate and is the whole test: a perfectly good,
        conforming declaration is written at `.dotmac/kernel-adoption.json`,
        and the binding names `.dotmac/elsewhere.json`, which does not exist.
        A runner that fell back would find the good document, report a clean
        run, and tell the product its own choice had been honoured. The correct
        outcome is `kernel.declaration.missing` naming the BOUND path.
        """
        self.product.declare(applicable())
        self.bind("KernelAdoptionDeclaration.v1", ".dotmac/elsewhere.json")
        result = self.go()
        self.assertIn(FindingCode.DECLARATION_MISSING, self.codes(result))
        self.assertFalse(result.report.conforms)
        self.assertEqual(
            ".dotmac/elsewhere.json",
            result.to_dict()["product"]["declaration_path"],
        )
        # The fall-back is refuted by NAME, not only by outcome: the default
        # document exists and conforms, so a clean run here would have been a
        # run over the wrong file.
        detail = result.to_dict()["product"]["declaration"]["detail"]
        self.assertIn(".dotmac/elsewhere.json", detail)
        self.assertNotIn("kernel-adoption.json", detail)

    def test_the_near_miss_a_bound_path_that_exists_is_read(self) -> None:
        """The paired near-miss. Refusing every bound path would satisfy the
        test above for the wrong reason."""
        self.product.declare(None)
        self.bind("KernelAdoptionDeclaration.v1", ".dotmac/elsewhere.json")
        (self.product.root / ".dotmac" / "elsewhere.json").write_text(
            json.dumps(applicable()) + "\n", encoding="utf-8"
        )
        result = self.go()
        self.assertNotIn(FindingCode.DECLARATION_MISSING, self.codes(result))
        self.assertEqual(
            ".dotmac/elsewhere.json",
            result.to_dict()["product"]["declaration_path"],
        )

    # -- 2. missing or corrupt bound file ------------------------------------

    def test_a_corrupt_bound_file_fails(self) -> None:
        self.product.declare(None)
        self.bind("KernelAdoptionDeclaration.v1", ".dotmac/elsewhere.json")
        (self.product.root / ".dotmac" / "elsewhere.json").write_text(
            "{ not json\n", encoding="utf-8"
        )
        result = self.go()
        self.assertIn(FindingCode.DECLARATION_UNREADABLE, self.codes(result))
        self.assertFalse(result.report.conforms)

    def test_an_empty_bound_file_fails_as_its_own_refusal(self) -> None:
        """Empty is not missing and not corrupt. Asserted here too, because a
        bound path is exactly where the three are easiest to collapse."""
        self.product.declare(None)
        self.bind("KernelAdoptionDeclaration.v1", ".dotmac/elsewhere.json")
        (self.product.root / ".dotmac" / "elsewhere.json").write_text(
            "   \n", encoding="utf-8"
        )
        result = self.go()
        self.assertIn(FindingCode.DECLARATION_EMPTY, self.codes(result))

    # -- 3. an unknown version -----------------------------------------------

    def test_an_unknown_contract_version_refuses_the_run(self) -> None:
        """Widening the vocabulary to two must not open it to any string.

        This is the sensitivity proof for the widening itself: had the check
        been dropped rather than widened, this would go quiet.
        """
        self.product.declare(applicable())
        self.bind("KernelAdoptionDeclaration.v3")
        with self.assertRaises(RunnerError) as caught:
            self.go()
        self.assertIn("does not parse", str(caught.exception))
        self.assertIn("points at nothing", str(caught.exception))

    def test_an_empty_contract_version_refuses_the_run(self) -> None:
        """The near-miss on the same arm: not an unrecognised NAME, but a value
        with no name in it at all."""
        self.product.declare(applicable())
        self.bind("")
        with self.assertRaises(RunnerError):
            self.go()

    # -- 4. and 5. the binding and the document must agree -------------------

    def test_a_v1_binding_over_a_v2_document_fails(self) -> None:
        """The half a vocabulary widening alone would have left silent."""
        self.enrol_v2()
        self.bind("KernelAdoptionDeclaration.v1")
        with self.assertRaises(RunnerError) as caught:
            self.go(observer=f"{__name__}:observe_v2_consumer")
        message = str(caught.exception)
        self.assertIn(KERNEL_ADOPTION_CONTRACT, message)
        self.assertIn(KERNEL_ADOPTION_CONTRACT_V2, message)
        self.assertIn("not a binding", message)

    def test_a_v2_binding_over_a_v1_document_fails(self) -> None:
        self.product.declare(applicable())
        self.bind("KernelAdoptionDeclaration.v2")
        with self.assertRaises(RunnerError) as caught:
            self.go()
        message = str(caught.exception)
        self.assertIn(KERNEL_ADOPTION_CONTRACT_V2, message)
        self.assertIn(KERNEL_ADOPTION_CONTRACT, message)

    def test_an_unbound_repository_is_not_told_its_contract_disagrees(self) -> None:
        """The near-miss for the comparison arm.

        A repository that states no binding has claimed no contract, so there
        is nothing to disagree with and the default path is read. Had the arm
        been written to REQUIRE agreement rather than to check a stated one, it
        would refuse every unbound product -- including the enrolled ones that
        carry no binding.
        """
        self.product.declare(applicable())
        self.product.profile({})
        result = self.go()
        self.assertEqual(
            [FindingCode.DECLARATION_FIELDS_UNEVALUATED], self.codes(result)
        )

    def test_a_binding_over_an_absent_document_reports_the_absence(self) -> None:
        """The other near-miss: the contract arm must not fire over a refusal.

        The document is missing, so there is no contract to compare. Reporting
        a contract disagreement here would send the reader to the profile when
        the repair is to write the file.
        """
        self.product.declare(None)
        self.bind("KernelAdoptionDeclaration.v2")
        result = self.go()
        self.assertIn(FindingCode.DECLARATION_MISSING, self.codes(result))

    # -- 6. the admit control ------------------------------------------------

    def test_a_v2_binding_over_a_v2_document_passes(self) -> None:
        """Without this, the refusals above are indistinguishable from a rule
        that refuses everything.

        This is also the shape the defect made unreachable: before the
        vocabulary was widened, a v2 product's only admissible binding named
        v1, so it had to either bind the wrong contract or omit the binding and
        thereby state no contract at all.
        """
        predecessor = self.enrol_v2()
        self.bind("KernelAdoptionDeclaration.v2")
        result = self.go(observer=f"{__name__}:observe_v2_consumer")
        self.assertEqual([], self.codes(result), result.to_dict())
        summary = result.to_dict()["product"]["declaration"]
        self.assertEqual(KERNEL_ADOPTION_CONTRACT_V2, summary["contract"])
        self.assertEqual(predecessor, summary["source_predecessor"])
