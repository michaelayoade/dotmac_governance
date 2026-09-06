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
)
from kernel_adoption_control.runner import (
    CANONICAL_GOVERNANCE,
    GOVERNANCE_ROOT,
    RUN_CONTRACT,
    ProductObservation,
    Provenance,
    RunnerError,
    _declaration_location,
    _normalise_origin,
    _observed_origin,
    is_enforced,
    main,
    resolve_observer,
    run,
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
        self._stack = tempfile.TemporaryDirectory()
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
        enforced, reason = is_enforced(self.base())
        self.assertTrue(enforced, reason)

    def test_a_document_that_is_not_a_run_report_is_not_enforcement(self) -> None:
        document = self.base()
        document["contract"] = "SomethingElse.v1"
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("predating the runner produces none", reason)

    def test_an_absent_contract_key_is_not_enforcement(self) -> None:
        """The shape a pre-runner Governance revision leaves behind: nothing."""
        enforced, reason = is_enforced({})
        self.assertFalse(enforced)
        self.assertIn(RUN_CONTRACT, reason)

    def test_a_report_naming_another_repository_is_not_enforcement(self) -> None:
        """The vendoring claim, checked at the predicate as well as at the run."""
        document = self.base()
        governance = dict(document["governance"])
        governance["origin"] = "https://github.com/michaelayoade/dotmac_erp"
        document["governance"] = governance
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not the authority behind it", reason)

    def test_a_report_with_no_established_provenance_is_not_enforcement(self) -> None:
        document = self.base()
        governance = dict(document["governance"])
        governance["provenance"] = "assumed"
        document["governance"] = governance
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not an established one", reason)

    def test_an_applicable_declaration_is_not_citable(self) -> None:
        """The narrowing that makes the rest honest.

        Three declared fields are unread, so a run over an applicable
        declaration cannot be cited as enforcing that declaration. Governance's
        truthful `not_applicable` self-run has no unread fields and stays
        citable, which is what makes this a self-enforcement foundation rather
        than a product gate that overclaims.
        """
        document = self.base()
        product = dict(document["product"])
        product["declaration"] = {"state": "present", "applicability": "applicable"}
        document["product"] = product
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("decision 52", reason)
        self.assertIn("required_surfaces", reason)

    def test_a_refused_declaration_is_not_citable(self) -> None:
        document = self.base()
        product = dict(document["product"])
        product["declaration"] = {"state": "DeclarationMissing", "detail": "gone"}
        document["product"] = product
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("which is a refusal", reason)

    def test_a_moving_governance_coordinate_is_not_enforcement(self) -> None:
        document = self.base()
        governance = dict(document["governance"])
        governance["revision"] = "main"
        document["governance"] = governance
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not a peeled commit", reason)

    def test_a_dirty_governance_checkout_is_not_enforcement(self) -> None:
        document = self.base()
        governance = dict(document["governance"])
        governance["worktree_clean"] = False
        document["governance"] = governance
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not the code that ran", reason)

    def test_a_dirty_product_checkout_is_not_enforcement(self) -> None:
        document = self.base()
        product = dict(document["product"])
        product["worktree_clean"] = False
        document["product"] = product
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not the source that was read", reason)

    def test_an_empty_inventory_is_not_enforcement(self) -> None:
        document = self.base()
        document["observation"] = {"source_count": 0}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("passes for the wrong reason", reason)

    def test_a_non_conforming_run_is_not_enforcement(self) -> None:
        document = self.base()
        document["findings"] = {"conforms": False, "findings": []}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
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
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("10 error finding(s)", reason)

    def test_a_notice_only_report_is_still_citable(self) -> None:
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
        enforced, reason = is_enforced(document)
        self.assertTrue(enforced, reason)
        self.assertIn("2 notice(s), no errors", reason)

    def test_an_unrecognised_severity_is_refused_not_read_as_harmless(self) -> None:
        for severity in ("warning", "ERROR", "", None, 3, {"level": "error"}):
            with self.subTest(severity=severity):
                document = self.base()
                document["findings"] = {
                    "conforms": True,
                    "findings": [{"code": "x", "severity": severity}],
                }
                enforced, reason = is_enforced(document)
                self.assertFalse(enforced)
                self.assertIn("not read as a harmless one", reason)

    def test_a_findings_section_with_no_list_is_refused(self) -> None:
        for value in ({"conforms": True}, {"conforms": True, "findings": "none"}):
            with self.subTest(value=value):
                enforced, reason = is_enforced({**self.base(), "findings": value})
                self.assertFalse(enforced)
                self.assertIn("summarises nothing", reason)

    def test_a_finding_that_is_not_an_object_is_refused(self) -> None:
        document = self.base()
        document["findings"] = {"conforms": True, "findings": ["kernel.pin.disagrees"]}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("is not an object", reason)

    def test_a_boolean_source_count_is_not_one_file(self) -> None:
        """`isinstance(True, int)` is True, so `source_count: true` read as 1."""
        document = self.base()
        document["observation"] = {"source_count": True}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("malformed report", reason)

    def test_a_real_run_produces_a_document_the_predicate_accepts(self) -> None:
        """Non-vacuity: the predicate is satisfiable by the runner's own output.

        A predicate that rejected every real report would make every assertion
        above pass while nothing could ever be enforced. The satisfiable shape
        is a truthful `not_applicable` declaration -- which is exactly the shape
        this repository has, and exactly the scope activation now claims.
        """
        self.product.declare(not_applicable())
        document = self.go(observer=f"{__name__}:observe_kernel_free").to_dict()
        # The Governance worktree under test is the one this suite runs from and
        # may legitimately be dirty; substitute only that one fact.
        document["governance"] = dict(document["governance"])
        document["governance"]["worktree_clean"] = True
        enforced, reason = is_enforced(document)
        self.assertTrue(enforced, reason)


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
