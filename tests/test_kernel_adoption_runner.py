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

import json
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any

from kernel_adoption_control import (
    FindingCode,
    KernelSurfaceCatalogue,
    PinSite,
)
from kernel_adoption_control.runner import (
    GOVERNANCE_ROOT,
    RUN_CONTRACT,
    ProductObservation,
    RunnerError,
    is_enforced,
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


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


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

    def declare(self, body: dict[str, Any] | str | None) -> None:
        path = self.root / ".dotmac" / "kernel-adoption.json"
        if body is None:
            if path.exists():
                path.unlink()
            return
        raw = body if isinstance(body, str) else json.dumps(body, indent=2) + "\n"
        path.write_text(raw, encoding="utf-8")

    def profile(self, body: dict[str, Any] | str) -> None:
        raw = body if isinstance(body, str) else json.dumps(body, indent=2) + "\n"
        (self.root / ".dotmac" / "standards-profile.json").write_text(
            raw, encoding="utf-8"
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
        self.assertEqual([], self.codes(result), result.to_dict())
        self.assertTrue(result.report.conforms)

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

    def test_no_clock_is_read_anywhere_in_the_package(self) -> None:
        """The property, asserted structurally rather than promised.

        A `date.today()` added later would make every test above pass while the
        verdict silently stopped being reproducible, so the absence is a check.
        """
        package = REPO_ROOT / "kernel_adoption_control"
        for path in sorted(package.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for forbidden in ("date.today(", "datetime.now(", "datetime.utcnow("):
                self.assertNotIn(forbidden, text, f"{path.name} reads a clock")


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
        self.assertEqual([], self.codes(clean))
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
        self.assertEqual([], self.codes(result), result.to_dict())
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

    def test_an_unreadable_profile_refuses_rather_than_falling_back(self) -> None:
        """A profile that may name a non-default path, and cannot be read.

        Falling back to the default would answer a question that could not be
        answered: the declaration's location is unknown, so reading SOME file
        and reporting on it is worse than refusing.
        """
        self.product.declare(applicable())
        self.product.profile("{ not json\n")
        with self.assertRaises(RunnerError) as caught:
            self.go()
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
            "governance": {"revision": "a" * 40, "worktree_clean": True},
            "product": {"revision": "b" * 40, "worktree_clean": True},
            "observation": {"source_count": 12},
            "findings": {"conforms": True},
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

    def test_a_moving_governance_coordinate_is_not_enforcement(self) -> None:
        document = self.base()
        document["governance"] = {"revision": "main", "worktree_clean": True}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not a peeled commit", reason)

    def test_a_dirty_governance_checkout_is_not_enforcement(self) -> None:
        document = self.base()
        document["governance"] = {"revision": "a" * 40, "worktree_clean": False}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("not the code that ran", reason)

    def test_a_dirty_product_checkout_is_not_enforcement(self) -> None:
        document = self.base()
        document["product"] = {"revision": "b" * 40, "worktree_clean": False}
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
        document["findings"] = {"conforms": False}
        enforced, reason = is_enforced(document)
        self.assertFalse(enforced)
        self.assertIn("did not conform", reason)

    def test_a_real_run_produces_a_document_the_predicate_accepts(self) -> None:
        """Non-vacuity: the predicate is satisfiable by the runner's own output.

        A predicate that rejected every real report would make every assertion
        above pass while nothing could ever be enforced.
        """
        self.product.declare(applicable())
        document = self.go().to_dict()
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
