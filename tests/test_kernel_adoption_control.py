"""Six Kernel-adoption properties, each proved by a planted defect and a near-miss.

A green run over the fleet proves nothing about these arms, because the fleet
is currently clean: measured on 2026-09-05, no pin/lock disagreement exists in
`dotmac_platform_control_plane`, `dotmac_erp` or `dotmac_sub`, and no
product-local Kernel facade exists in any of them. So every arm below is
established the only way it can be — plant the defect and read the message, then
plant the thing that merely LOOKS like it and read the silence.

The near-misses are not decoration. Each is drawn from a real file that a
cruder detector would condemn:

- `dotmac_sub`'s `app/services/settings_kernel_bridge.py` imports four Kernel
  names and is an adapter, not a facade.
- `dotmac_erp`'s import-boundary guard keeps `from dotmac_kernel.db import ...`
  as a STRING fixture, so a text scanner reports the guard as the violation.
- `dotmac_kernel.display` is internal without being private, which keeps the
  unknown-surface arm and the private-surface arm from collapsing into one.

Two vacuity hazards are asserted directly rather than assumed: a run over no
source, and a pin arm handed too few sites to be capable of disagreeing.
"""

from __future__ import annotations

import dataclasses
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path, PurePosixPath

from kernel_adoption_control import (
    AdoptionReport,
    DeclarationMissing,
    DeclarationOutcome,
    DeclarationPresent,
    DeclarationUnreadable,
    Finding,
    FindingCode,
    KernelAdoptionApplicability,
    KernelAdoptionDeclaration,
    KernelAdoptionInputs,
    KernelSurfaceCatalogue,
    PinSite,
    ProhibitedSurface,
    Severity,
    SurfaceSite,
    TransitionalSurface,
    evaluate,
    read_declaration,
)
from kernel_adoption_control.declaration_contract import (
    KERNEL_ADOPTION_CONTRACT,
    DeclarationError,
    KernelCatalogueEvidence,
    parse_declaration,
)
from kernel_adoption_control.foundation_binding import (
    _MOVING_ALIAS,
    ABANDONED_VERSIONS,
    FOUNDATION_APPLICATION_PROFILE,
    AdoptionClaim,
    AdoptionState,
    BootstrapOnlyError,
    ContractBinding,
    CoordinateError,
)

# ── the catalogue, read from the Kernel rather than hand-typed ───────────────
#
# Read on 2026-09-05 from `dotmac_starter_mt` tag `dotmac-kernel-v0.1.0a98`,
# peeled commit `ae7320876ad91d5bf4639d634d65a6e8fd36bb00`, out of
# `packages/dotmac-kernel/src/dotmac_kernel/__init__.py`: 83 `SUPPORTED_MODULES`
# and 4 `INTERNAL_MODULES`. A98 is the version `dotmac_platform_control_plane`
# and `dotmac_erp` both pin.
#
# The subset below is a TEST FIXTURE and is labelled one. Production callers
# pass the real lists; a hardcoded subset in the engine would make an
# unknown-surface finding a fact about this file's staleness rather than about
# the product, which is why `KernelSurfaceCatalogue` is an input.
A98 = KernelSurfaceCatalogue(
    revision="ae7320876ad91d5bf4639d634d65a6e8fd36bb00",
    version="0.1.0a98",
    supported=frozenset(
        {
            "dotmac_kernel.db",
            "dotmac_kernel.security",
            "dotmac_kernel.settings_resolver",
            "dotmac_kernel.settings_models",
            "dotmac_kernel.setting_value_types",
            "dotmac_kernel.messaging",
            "dotmac_kernel.platform_auth",
            "dotmac_kernel.prerequisites",
        }
    ),
    internal=frozenset(
        {
            "dotmac_kernel._transactions",
            "dotmac_kernel.display",
            "dotmac_kernel.route_metadata",
            "dotmac_kernel.web_runtime",
        }
    ),
)

CLEAN = {
    PurePosixPath("app/services/usage.py"): (
        "from dotmac_kernel.messaging import publish\n"
        "from dotmac_kernel.prerequisites import require\n"
    )
}


PRODUCT_REVISION = "f8f90aef1467a3d332a650775e667e75d7226f56"

CATALOGUE_EVIDENCE = KernelCatalogueEvidence(
    version="0.1.0a98",
    revision="ae7320876ad91d5bf4639d634d65a6e8fd36bb00",
    artifact_digest="sha256:"
    + "27405c57c4af395224cdd2f4366c0144207e9df2eab4ca8a8ed1142c1d0859fa"[:64],
)


def declared(
    prohibited: frozenset[str] = frozenset(),
    transitional: tuple[TransitionalSurface, ...] = (),
) -> DeclarationOutcome:
    return DeclarationPresent(
        KernelAdoptionDeclaration(
            contract=KERNEL_ADOPTION_CONTRACT,
            product_revision=PRODUCT_REVISION,
            applicability=KernelAdoptionApplicability.APPLICABLE,
            not_applicable_reason=None,
            catalogue=CATALOGUE_EVIDENCE,
            required_surfaces=(),
            prohibited_surfaces=tuple(
                ProhibitedSurface(module=name, citation="dotmac_governance ADR 0042")
                for name in sorted(prohibited)
            ),
            transitional_surfaces=transitional,
        )
    )


def not_applicable(reason: str) -> DeclarationOutcome:
    return DeclarationPresent(
        KernelAdoptionDeclaration(
            contract=KERNEL_ADOPTION_CONTRACT,
            product_revision=PRODUCT_REVISION,
            applicability=KernelAdoptionApplicability.NOT_APPLICABLE,
            not_applicable_reason=reason,
            catalogue=None,
            required_surfaces=(),
            prohibited_surfaces=(),
            transitional_surfaces=(),
        )
    )


def transitional_surface(
    module: str = "dotmac_kernel.db",
    *,
    owner: str = "Michael Ayoade",
    expiry: str = "2026-12-01",
    baseline: tuple[SurfaceSite, ...] = (),
) -> TransitionalSurface:
    return TransitionalSurface(
        module=module,
        owner=owner,
        expiry=expiry,
        retirement_issue="dotmac_governance#123",
        replacement="dotmac_kernel.session_runtime",
        baseline=baseline,
    )


#: The date these fixtures are judged against. Fixed, not `date.today()`: an
#: expiry assertion whose meaning changes overnight is an assertion nobody can
#: re-read. `transitional_surface`'s default expiry is 2026-12-01, comfortably
#: after this, so no fixture below expires by accident.
AS_OF = date(2026, 9, 5)


def evaluate_sources(
    sources: dict[PurePosixPath, str],
    *,
    prohibited: frozenset[str] = frozenset(),
    pins: tuple[PinSite, ...] = (),
    transitional: tuple[TransitionalSurface, ...] = (),
    declaration: DeclarationOutcome | None = None,
    as_of: date = AS_OF,
) -> AdoptionReport:
    return evaluate(
        KernelAdoptionInputs(
            sources=sources,
            catalogue=A98,
            pin_sites=pins,
            as_of=as_of,
            declaration=(
                declared(prohibited, transitional)
                if declaration is None
                else declaration
            ),
        )
    )


def codes_of(report: AdoptionReport, code: FindingCode) -> list[Finding]:
    return [item for item in report.findings if item.code == code]


def errors_of(report: AdoptionReport) -> list[Finding]:
    """Findings that make a report non-conforming.

    Distinct from "no findings at all", which stopped being the shape of a
    clean run when an `applicable` declaration began publishing its
    unevaluated fields as a notice.
    """

    return [item for item in report.findings if item.severity is Severity.ERROR]


class AdmitControl(unittest.TestCase):
    """The clean case, so a later failure is attributable to the plant."""

    def test_realistic_clean_source_produces_no_error(self) -> None:
        report = evaluate_sources(
            CLEAN,
            pins=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(PurePosixPath("poetry.lock"), 118, "0.1.0a98", "lock"),
            ),
        )
        # No ERROR, which is what this test is named for. Not an empty list:
        # an `applicable` declaration now publishes
        # `kernel.declaration.fields-unevaluated` as a NOTICE on every run,
        # because three declared fields are read by nothing and a reader must
        # not infer from a clean report that they were checked.
        self.assertEqual([], errors_of(report), report.to_dict())
        self.assertIn(
            FindingCode.DECLARATION_FIELDS_UNEVALUATED, report.codes(), report.to_dict()
        )


class Vacuity(unittest.TestCase):
    """A sweep that cannot fail must not read as one that passed."""

    def test_a_run_over_no_source_is_a_measurement_failure(self) -> None:
        report = evaluate_sources({})
        self.assertIn(FindingCode.INVENTORY_EMPTY, report.codes())
        self.assertFalse(report.conforms)

    def test_the_pin_arm_says_so_when_it_cannot_disagree(self) -> None:
        report = evaluate_sources(
            CLEAN,
            pins=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
            ),
        )
        # An ERROR, not a notice. One observation cannot disagree with itself,
        # so this arm established nothing -- and a report carrying only a
        # notice was citable, which made "the pin agrees" indistinguishable
        # from "the pin was never compared". That is the vacuous pass this
        # class exists to refuse, and it was inside the vacuity guard itself.
        found = codes_of(report, FindingCode.PIN_UNDETECTABLE)
        self.assertEqual(1, len(found))
        self.assertIs(Severity.ERROR, found[0].severity)
        self.assertFalse(report.conforms)
        self.assertEqual([], codes_of(report, FindingCode.PIN_DISAGREES))

    def test_unparseable_source_is_refused_not_reported_clean(self) -> None:
        report = evaluate_sources({PurePosixPath("app/broken.py"): "def (:\n"})
        found = codes_of(report, FindingCode.SOURCE_UNREADABLE)
        self.assertEqual(1, len(found))
        self.assertEqual(PurePosixPath("app/broken.py"), found[0].path)
        self.assertIn("unmeasured file", found[0].message)


class PinDisagreement(unittest.TestCase):
    """Planted, never claimed.

    No pin disagreement exists in Platform, ERP or Sub. A test asserting a
    current mismatch would be false, so the defect is constructed here.
    """

    def test_a_planted_lock_disagreement_names_both_sites_and_both_versions(
        self,
    ) -> None:
        report = evaluate_sources(
            CLEAN,
            pins=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(PurePosixPath("poetry.lock"), 118, "0.1.0a94", "lock"),
            ),
        )
        found = codes_of(report, FindingCode.PIN_DISAGREES)
        self.assertEqual(2, len(found))
        rendered = " | ".join(item.message for item in found)
        self.assertIn("pyproject.toml:32", rendered)
        self.assertIn("poetry.lock:118", rendered)
        self.assertIn("0.1.0a98", rendered)
        self.assertIn("0.1.0a94", rendered)
        self.assertTrue(all(item.severity is Severity.ERROR for item in found))

    def test_four_agreeing_sites_are_silent(self) -> None:
        """Sub states its pin in four places, kept in lockstep by its own test."""
        report = evaluate_sources(
            CLEAN,
            pins=(
                PinSite(PurePosixPath("pyproject.toml"), 52, "0.1.0a94", "pep621"),
                PinSite(PurePosixPath("pyproject.toml"), 80, "0.1.0a94", "poetry"),
                PinSite(PurePosixPath("pyproject.toml"), 116, "0.1.0a94", "dev-extra"),
                PinSite(PurePosixPath("pyproject.toml"), 371, " 0.1.0a94 ", "constant"),
            ),
        )
        self.assertEqual([], codes_of(report, FindingCode.PIN_DISAGREES))

    def test_a_dated_historical_mention_in_source_is_not_a_pin_site(self) -> None:
        """A record of an OLD version is a record, not a second pin.

        `dotmac_platform_control_plane`'s `pyproject.toml` carries a comment
        naming an earlier release's `Requires-Dist`. Prose about history states
        no adoption, and an arm that read it would report a disagreement
        between the product and its own changelog.
        """
        report = evaluate_sources(
            {
                PurePosixPath("app/notes.py"): (
                    '"""a6 carried Requires-Dist: dotmac-kernel (>=0.1.0a90)."""\n'
                    "# superseded on 2026-08-01 by 0.1.0a94\n"
                    "from dotmac_kernel.messaging import publish\n"
                )
            },
            pins=(
                PinSite(PurePosixPath("pyproject.toml"), 32, "0.1.0a98", "dependency"),
                PinSite(PurePosixPath("poetry.lock"), 118, "0.1.0a98", "lock"),
            ),
        )
        self.assertEqual([], codes_of(report, FindingCode.PIN_DISAGREES))


class UnknownSurface(unittest.TestCase):
    def test_an_unpublished_module_is_named_with_its_file_and_line(self) -> None:
        report = evaluate_sources(
            {
                PurePosixPath("app/boot.py"): (
                    "import os\nfrom dotmac_kernel.credential_lifecycl import reset\n"
                )
            }
        )
        found = codes_of(report, FindingCode.SURFACE_UNKNOWN)
        self.assertEqual(1, len(found))
        self.assertEqual(PurePosixPath("app/boot.py"), found[0].path)
        self.assertEqual(2, found[0].line)
        self.assertIn("dotmac_kernel.credential_lifecycl", found[0].message)
        self.assertIn("0.1.0a98", found[0].message)
        self.assertIn(A98.revision, found[0].message)

    def test_a_published_module_is_silent(self) -> None:
        report = evaluate_sources(
            {PurePosixPath("app/boot.py"): "from dotmac_kernel.db import session\n"}
        )
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_UNKNOWN))

    def test_an_internal_but_published_module_is_silent(self) -> None:
        """`dotmac_kernel.display` is INTERNAL and therefore known."""
        report = evaluate_sources(
            {PurePosixPath("app/web.py"): "from dotmac_kernel.display import fmt\n"}
        )
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_UNKNOWN))


class PrivateSurface(unittest.TestCase):
    def test_a_private_module_is_named(self) -> None:
        report = evaluate_sources(
            {
                PurePosixPath("app/tx.py"): (
                    "from dotmac_kernel._transactions import commit\n"
                )
            }
        )
        found = codes_of(report, FindingCode.SURFACE_PRIVATE)
        self.assertEqual(1, len(found))
        self.assertEqual(1, found[0].line)
        self.assertIn("_transactions", found[0].message)

    def test_internal_without_an_underscore_is_not_private(self) -> None:
        """The near-miss that keeps `unknown` and `private` from collapsing.

        `dotmac_kernel.display` sits in the same `INTERNAL_MODULES` tuple as
        `dotmac_kernel._transactions`. Only one of them is private, and a
        detector that read the tuple instead of the name would condemn both.
        """
        report = evaluate_sources(
            {PurePosixPath("app/web.py"): "from dotmac_kernel.display import fmt\n"}
        )
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_PRIVATE))

    def test_a_dunder_is_not_a_private_component(self) -> None:
        report = evaluate_sources(
            {PurePosixPath("app/v.py"): "from dotmac_kernel import __version__\n"}
        )
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_PRIVATE))


class ProhibitedSurfaceArm(unittest.TestCase):
    def test_a_prohibited_import_is_named_with_file_and_line(self) -> None:
        report = evaluate_sources(
            {
                PurePosixPath("app/repo.py"): (
                    "import os\n\nfrom dotmac_kernel.db import get_platform_db\n"
                )
            },
            prohibited=frozenset({"dotmac_kernel.db"}),
        )
        found = codes_of(report, FindingCode.SURFACE_PROHIBITED)
        self.assertEqual(1, len(found))
        self.assertEqual(PurePosixPath("app/repo.py"), found[0].path)
        self.assertEqual(3, found[0].line)
        self.assertIn("dotmac_kernel.db", found[0].message)

    def test_a_string_fixture_naming_the_prohibited_module_is_silent(self) -> None:
        """`dotmac_erp`'s own import-boundary guard is this shape.

        It keeps the forbidden import as a STRING so it can assert the guard
        rejects it. A text scanner would report the guard as the violation it
        exists to prevent, which is the reason this engine reads the parse tree.
        """
        report = evaluate_sources(
            {
                PurePosixPath("tests/test_kernel_import_boundary.py"): (
                    "# ERP forbids `from dotmac_kernel.db import Session`.\n"
                    'FORBIDDEN = "from dotmac_kernel.db import Session"\n'
                    "\n"
                    "def test_guard() -> None:\n"
                    "    assert FORBIDDEN\n"
                )
            },
            prohibited=frozenset({"dotmac_kernel.db"}),
        )
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_PROHIBITED))

    def test_a_sibling_module_sharing_a_prefix_is_silent(self) -> None:
        """`dotmac_kernel.db_utils` is not under `dotmac_kernel.db`."""
        report = evaluate_sources(
            {PurePosixPath("app/x.py"): "from dotmac_kernel.db_utils import q\n"},
            prohibited=frozenset({"dotmac_kernel.db"}),
        )
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_PROHIBITED))

    def test_a_non_py_suffix_is_measured_when_supplied(self) -> None:
        """`rotation_runtime_oracle.pyprogram` is the reason this matters.

        `dotmac_platform_control_plane` keeps a Python program under a suffix a
        `.py` sweep skips, importing `dotmac_kernel.db` at line 17. The engine
        measures whatever source it is handed, so the blind spot belongs to the
        caller's inventory rather than to the detector.
        """
        report = evaluate_sources(
            {
                PurePosixPath("src/vendor_cp/rotation_runtime_oracle.pyprogram"): (
                    "\n" * 16 + "from dotmac_kernel.db import runtime\n"
                )
            },
            prohibited=frozenset({"dotmac_kernel.db"}),
        )
        found = codes_of(report, FindingCode.SURFACE_PROHIBITED)
        self.assertEqual(1, len(found))
        self.assertEqual(17, found[0].line)


class LocalFacade(unittest.TestCase):
    def test_a_reexporting_module_is_named_with_the_forwarded_names(self) -> None:
        report = evaluate_sources(
            {
                PurePosixPath("app/kernel.py"): (
                    "from dotmac_kernel.db import session\n"
                    "from dotmac_kernel.security import hash_password\n"
                    '__all__ = ["session", "hash_password"]\n'
                )
            }
        )
        found = codes_of(report, FindingCode.FACADE_LOCAL)
        self.assertEqual(2, len(found))
        rendered = " | ".join(item.message for item in found)
        self.assertIn("session", rendered)
        self.assertIn("hash_password", rendered)
        self.assertTrue(
            all(item.path == PurePosixPath("app/kernel.py") for item in found)
        )

    def test_a_star_reexport_is_a_facade(self) -> None:
        report = evaluate_sources(
            {PurePosixPath("app/kernel.py"): "from dotmac_kernel.db import *\n"}
        )
        found = codes_of(report, FindingCode.FACADE_LOCAL)
        self.assertEqual(1, len(found))
        self.assertIn("wholesale", found[0].message)

    def test_the_sub_settings_bridge_adapter_stays_silent(self) -> None:
        """The permanent negative control, kept in this file's real shape.

        `dotmac_sub` `origin/main` `360ca63e3927bfd694d35aa2b1932a51b3202f48`,
        `app/services/settings_kernel_bridge.py` lines 32-35 and 44-74: four
        Kernel imports, NO `__all__`, and functions that translate Sub's own
        `SettingSpec` into the Kernel registry. It is an adapter, and a
        detector that fired on "imports Kernel names" would condemn the correct
        shape.
        """
        report = evaluate_sources(
            {
                PurePosixPath("app/services/settings_kernel_bridge.py"): (
                    "from dotmac_kernel.setting_value_types import (\n"
                    "    SettingValueType as KernelValueType,\n"
                    ")\n"
                    "from dotmac_kernel.settings_models import (\n"
                    "    SettingDomain as KernelSettingDomain,\n"
                    ")\n"
                    "from dotmac_kernel.settings_resolver import (\n"
                    "    SettingSpec as KernelSettingSpec,\n"
                    ")\n"
                    "from dotmac_kernel.settings_resolver import register_specs\n"
                    "\n"
                    "def to_kernel_spec(spec: object) -> KernelSettingSpec:\n"
                    "    return KernelSettingSpec(spec)\n"
                    "\n"
                    "def register_with_kernel() -> int:\n"
                    "    return register_specs(())\n"
                )
            }
        )
        self.assertEqual([], codes_of(report, FindingCode.FACADE_LOCAL))

    def test_an_all_listing_only_the_products_own_names_is_silent(self) -> None:
        """The second near-miss: `__all__` alone does not make a facade."""
        report = evaluate_sources(
            {
                PurePosixPath("app/service.py"): (
                    "from dotmac_kernel.db import session\n"
                    "\n"
                    "def load() -> None:\n"
                    "    session()\n"
                    '__all__ = ["load"]\n'
                )
            }
        )
        self.assertEqual([], codes_of(report, FindingCode.FACADE_LOCAL))

    def test_the_facade_guard_still_bites(self) -> None:
        """A guard whose subject set is empty in the fleet proves nothing.

        No product-local Kernel facade exists in Platform, ERP or Sub today, so
        this arm's health cannot be read off a green run. The two silent
        near-misses above and this bite together are the whole evidence.
        """
        report = evaluate_sources(
            {
                PurePosixPath("app/kernel.py"): (
                    'from dotmac_kernel.db import session\n__all__ = ["session"]\n'
                )
            }
        )
        self.assertEqual(1, len(codes_of(report, FindingCode.FACADE_LOCAL)))


class TransitionalOwnership(unittest.TestCase):
    """Two layers, and both are proved.

    A transitional entry that OMITS `owner` or `expiry` cannot reach this
    engine at all: `parse_declaration` refuses the document, proved in
    `DeclarationContract` below. What the blankness arm catches is the shape a
    caller can still construct directly — a present field holding whitespace —
    and it stays because a guard removed on the grounds that another guard
    covers it is how a seam becomes unmonitored.

    The arm that bites on real input is the BASELINE RATCHET, and it is
    two-directional.
    """

    def test_a_transitional_surface_with_neither_owner_nor_expiry_is_named(
        self,
    ) -> None:
        report = evaluate_sources(
            CLEAN,
            transitional=(transitional_surface(owner="", expiry="  "),),
        )
        found = codes_of(report, FindingCode.TRANSITIONAL_UNOWNED)
        self.assertEqual(1, len(found))
        self.assertIn("dotmac_kernel.db", found[0].message)
        self.assertIn("owner", found[0].message)
        self.assertIn("expiry", found[0].message)

    def test_a_blank_owner_is_not_an_owner(self) -> None:
        report = evaluate_sources(
            CLEAN, transitional=(transitional_surface(owner="   "),)
        )
        found = codes_of(report, FindingCode.TRANSITIONAL_UNOWNED)
        self.assertEqual(1, len(found))
        self.assertIn("owner", found[0].message)

    def test_a_fully_stated_transitional_surface_with_no_uses_is_silent(self) -> None:
        report = evaluate_sources(CLEAN, transitional=(transitional_surface(),))
        self.assertEqual([], codes_of(report, FindingCode.TRANSITIONAL_UNOWNED))
        self.assertEqual([], codes_of(report, FindingCode.TRANSITIONAL_BASELINE_DRIFT))

    def test_a_use_outside_the_baseline_is_growth_and_is_named(self) -> None:
        """Direction one: a surface being retired must not quietly grow."""
        report = evaluate_sources(
            {PurePosixPath("app/new.py"): ("from dotmac_kernel.db import session\n")},
            transitional=(transitional_surface(),),
        )
        found = codes_of(report, FindingCode.TRANSITIONAL_BASELINE_DRIFT)
        self.assertEqual(1, len(found))
        self.assertEqual(PurePosixPath("app/new.py"), found[0].path)
        self.assertIn("session", found[0].message)
        self.assertIn("dotmac_governance#123", found[0].message)
        self.assertIn("dotmac_kernel.session_runtime", found[0].message)

    def test_a_baseline_entry_with_no_use_is_named(self) -> None:
        """Direction two: a list that only grows stops describing anything.

        Removing the last use is the good outcome, and it must be recorded in
        the same change — otherwise the baseline silently overstates the work
        remaining and nobody notices the surface became retirable.
        """
        report = evaluate_sources(
            CLEAN,
            transitional=(
                transitional_surface(
                    baseline=(
                        SurfaceSite(path=PurePosixPath("app/old.py"), symbol="session"),
                    )
                ),
            ),
        )
        found = codes_of(report, FindingCode.TRANSITIONAL_BASELINE_DRIFT)
        self.assertEqual(1, len(found))
        self.assertIn("no such use was measured", found[0].message)
        self.assertIn("app/old.py", found[0].message)

    def test_a_baseline_that_matches_exactly_is_silent(self) -> None:
        """The near-miss for both directions: an accurate baseline says nothing."""
        report = evaluate_sources(
            {
                PurePosixPath("app/legacy.py"): (
                    "from dotmac_kernel.db import session\n"
                )
            },
            transitional=(
                transitional_surface(
                    baseline=(
                        SurfaceSite(
                            path=PurePosixPath("app/legacy.py"), symbol="session"
                        ),
                    )
                ),
            ),
        )
        self.assertEqual([], codes_of(report, FindingCode.TRANSITIONAL_BASELINE_DRIFT))


class DeclarationContract(unittest.TestCase):
    """`KernelAdoptionDeclaration.v1` refuses every ambiguous document.

    One format for every product. Nothing below is parameterised by product,
    and a field that had to differ per product would mean the format is wrong.
    """

    def document(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "contract": KERNEL_ADOPTION_CONTRACT,
            "product_revision": PRODUCT_REVISION,
            "applicability": "applicable",
            "kernel_catalogue": {
                "version": "0.1.0a98",
                "revision": "ae7320876ad91d5bf4639d634d65a6e8fd36bb00",
                "artifact_digest": "sha256:" + "a" * 64,
            },
            "required_surfaces": [
                {
                    "module": "dotmac_kernel.messaging",
                    "floor": "0.1.0a98",
                    "proven_by": "tests/architecture/test_kernel_compatibility.py",
                }
            ],
            "prohibited_surfaces": [
                {
                    "module": "dotmac_kernel.db",
                    "citation": "dotmac_erp tests/architecture/test_kernel_import_boundary.py",
                }
            ],
            "transitional_surfaces": [
                {
                    "module": "dotmac_kernel.planes",
                    "owner": "Michael Ayoade",
                    "expiry": "2026-12-01",
                    "retirement_issue": "dotmac_governance#123",
                    "replacement": "dotmac_kernel.namespaces",
                    "baseline": [{"path": "app/x.py", "symbol": "Plane"}],
                }
            ],
        }
        base.update(overrides)
        return base

    def assertRefused(self, document: object, needle: str) -> None:
        with self.assertRaises(DeclarationError) as caught:
            parse_declaration(document)
        self.assertIn(needle, str(caught.exception))

    def test_the_admit_control_parses(self) -> None:
        parsed = parse_declaration(self.document())
        self.assertEqual(KERNEL_ADOPTION_CONTRACT, parsed.contract)
        self.assertEqual(frozenset({"dotmac_kernel.db"}), parsed.prohibited_modules)
        self.assertEqual(1, len(parsed.transitional_surfaces))
        self.assertIsNotNone(parsed.catalogue)

    def test_a_not_applicable_document_parses_and_carries_no_surfaces(self) -> None:
        parsed = parse_declaration(
            {
                "contract": KERNEL_ADOPTION_CONTRACT,
                "product_revision": PRODUCT_REVISION,
                "applicability": "not_applicable",
                "not_applicable_reason": "composes no assembly",
            }
        )
        self.assertEqual((), parsed.prohibited_surfaces)
        self.assertIsNone(parsed.catalogue)

    def test_a_foreign_contract_is_refused_rather_than_read_leniently(self) -> None:
        self.assertRefused(
            self.document(contract="ApplicationFoundationProfile.v1"),
            "this parser reads",
        )

    def test_a_moving_product_revision_is_refused(self) -> None:
        for value in ("main", "HEAD", "v1.2.3", "deadbeef"):
            with self.subTest(value=value):
                self.assertRefused(
                    self.document(product_revision=value),
                    "peeled 40-character commit",
                )

    def test_a_surface_outside_the_kernel_namespace_is_refused(self) -> None:
        """A name that is classified and never measured is worse than none."""
        self.assertRefused(
            self.document(
                prohibited_surfaces=[
                    {"module": "sqlalchemy.orm", "citation": "house style"}
                ]
            ),
            "not a dotmac_kernel module path",
        )

    def test_a_prohibition_without_a_citation_is_refused(self) -> None:
        self.assertRefused(
            self.document(prohibited_surfaces=[{"module": "dotmac_kernel.db"}]),
            "missing keys: citation",
        )

    def test_a_transitional_surface_missing_any_obligation_is_refused(self) -> None:
        for dropped in (
            "owner",
            "expiry",
            "retirement_issue",
            "replacement",
            "baseline",
        ):
            with self.subTest(dropped=dropped):
                entry = dict(self.document()["transitional_surfaces"][0])  # type: ignore[index]
                del entry[dropped]
                self.assertRefused(
                    self.document(transitional_surfaces=[entry]),
                    f"missing keys: {dropped}",
                )

    def test_an_unorderable_expiry_is_refused(self) -> None:
        entry = dict(self.document()["transitional_surfaces"][0])  # type: ignore[index]
        entry["expiry"] = "soon"
        self.assertRefused(
            self.document(transitional_surfaces=[entry]), "cannot expire"
        )

    def test_a_module_cannot_hold_two_undertakings(self) -> None:
        self.assertRefused(
            self.document(
                required_surfaces=[
                    {
                        "module": "dotmac_kernel.db",
                        "floor": "0.1.0a98",
                        "proven_by": "tests/x.py",
                    }
                ]
            ),
            "declared both required and prohibited",
        )

    def test_not_applicable_carrying_surfaces_is_refused(self) -> None:
        """A list nothing will read is worse than no list: it looks measured."""
        self.assertRefused(
            {
                "contract": KERNEL_ADOPTION_CONTRACT,
                "product_revision": PRODUCT_REVISION,
                "applicability": "not_applicable",
                "not_applicable_reason": "none",
                "prohibited_surfaces": [],
            },
            "unknown keys",
        )

    def test_a_catalogue_without_an_immutable_digest_is_refused(self) -> None:
        self.assertRefused(
            self.document(
                kernel_catalogue={
                    "version": "0.1.0a98",
                    "revision": "ae7320876ad91d5bf4639d634d65a6e8fd36bb00",
                    "artifact_digest": "latest",
                }
            ),
            "adopts BY DIGEST",
        )

    def test_an_absolute_baseline_path_is_refused(self) -> None:
        entry = dict(self.document()["transitional_surfaces"][0])  # type: ignore[index]
        entry["baseline"] = [{"path": "/etc/passwd", "symbol": "x"}]
        self.assertRefused(
            self.document(transitional_surfaces=[entry]), "repository-relative"
        )


#: Every digest-named attribute this package may hold, module-qualified, and
#: what each one is.
#:
#: This REPLACED a blanket "no attribute whose name contains 'digest'" rule
#: plus a named exemption for `declaration_contract`. That shape stopped
#: working the moment the package acquired digests OF ITS OWN -- the v2
#: source-surface and catalogue coordinates -- and the available repairs were
#: to exempt three more modules wholesale or to state the premise exactly. A
#: blanket exemption turns "reviewed and correct" into "unmonitored", so the
#: premise is stated: the boundary is that no FOUNDATION PROFILE digest lives
#: here, not that the word may not appear.
#:
#: It is a two-directional ratchet. A new digest-named attribute fails until it
#: is named here with a reason, and a name that disappears fails until it is
#: removed -- an allowlist that may only grow stops describing the package.
PACKAGE_OWNED_DIGEST_NAMES: dict[str, frozenset[str]] = {
    # The pattern validating a `sha256:` coordinate, shared by both contracts.
    "declaration_contract": frozenset({"_DIGEST"}),
    "declaration_contract_v2": frozenset({"_DIGEST", "_digest"}),
    # The two v2 coordinates and the canonicalization one of them is taken
    # under. Both identify PRODUCT source or the KERNEL catalogue; neither is a
    # Foundation profile, which is the thing this boundary exists to keep out.
    # `surface_identity_digest` is the source-surface coordinate's successor
    # canonicalization (`dmg-kernel-surface-v2`), which records the Kernel's
    # own name for a symbol separately from the local name it was bound to. It
    # digests the same PRODUCT source the frozen v1 coordinate does, so it
    # crosses no boundary v1 did not.
    "surface": frozenset(
        {
            "CATALOGUE_DIGEST_ALGORITHM",
            "catalogue_digest",
            "surface_digest",
            "surface_identity_digest",
        }
    ),
    # Imported, not defined: the engine is where the coordinates are compared.
    # BOTH source-surface coordinates are compared here -- `_check_source_surface`
    # dispatches on the declared algorithm, and the parser admits exactly
    # `{dmg-kernel-surface-v1, dmg-kernel-surface-v2}`. An earlier revision of
    # this comment said v2 was derived and compared nowhere; that was true
    # before the contract was widened in this same branch.
    "engine": frozenset(
        {"catalogue_digest", "surface_digest", "surface_identity_digest"}
    ),
    # Imported, not defined. The runner RECORDS which canonicalization the run
    # compared under, on the report -- the artifact that is the evidence.
    # `kernel_catalogue` carries no `algorithm` field, so without this a stored
    # receipt could not say whether its catalogue digest was a v1 or a v2
    # value, and Michael's ruling of 2026-09-06 requires it be recorded. Still
    # a KERNEL catalogue coordinate and still not a Foundation profile, which
    # is the boundary this ratchet holds.
    "runner": frozenset({"CATALOGUE_DIGEST_ALGORITHM"}),
    "__init__": frozenset(
        {
            "CATALOGUE_DIGEST_ALGORITHM",
            "catalogue_digest",
            "surface_digest",
            "surface_identity_digest",
        }
    ),
}

#: What may never appear in ANY module here, at any time, under any premise.
#: These are Foundation's, and a second one is the defect ADR 0042 § 1 names.
FORBIDDEN_EVERYWHERE = ("APPLICATION_PROFILE_SCHEMA", "canonical_bytes")


def _package_modules() -> dict[str, object]:
    """Every module in the package, imported, keyed by stem. Derived from disk.

    ADR 0034: a gate that enumerates its targets must admit every one of them.
    A hand-written module list is the shape that silently stops covering a
    package -- the next module is added, every assertion stays green, and the
    new file is unmonitored rather than clean.
    """
    import importlib

    package = Path(__file__).resolve().parent.parent / "kernel_adoption_control"
    found: dict[str, object] = {}
    for path in sorted(package.glob("*.py")):
        if path.stem == "__main__":
            continue
        name = (
            "kernel_adoption_control"
            if path.stem == "__init__"
            else f"kernel_adoption_control.{path.stem}"
        )
        found[path.stem] = importlib.import_module(name)
    return found


class BoundaryIsStructural(unittest.TestCase):
    """The package holds no profile parser, and that is asserted rather than said.

    `ApplicationFoundationProfile.v1` is owned and verified by
    `dotmac-deployment-foundation`. A second parser that exists but is unused is
    still a second parser, so its absence is a test rather than a paragraph.
    """

    def test_the_sweep_covers_every_module_in_the_package(self) -> None:
        """Non-vacuity for everything below: the target set is not empty.

        A sweep derived from a glob passes trivially if the glob finds nothing,
        and the modules it names would then be unmonitored rather than clean.
        """
        modules = _package_modules()
        self.assertGreaterEqual(len(modules), 9, sorted(modules))
        for expected in ("contracts", "engine", "runner", "declaration_contract_v2"):
            self.assertIn(expected, modules)

    def test_no_module_declares_a_profile_schema_or_a_canonical_serializer(
        self,
    ) -> None:
        for stem, module in _package_modules().items():
            names = set(dir(module))
            for forbidden in FORBIDDEN_EVERYWHERE:
                self.assertNotIn(forbidden, names, stem)

    def test_every_digest_named_attribute_is_one_this_package_owns(self) -> None:
        """The premise, stated exactly rather than exempted wholesale.

        Two directions. An unlisted digest-named attribute fails -- which is how
        a Foundation profile digest would arrive. A LISTED one that no longer
        exists fails too, so the allowlist cannot outlive the code it describes.
        """
        for stem, module in _package_modules().items():
            allowed = PACKAGE_OWNED_DIGEST_NAMES.get(stem, frozenset())
            present = {name for name in dir(module) if "digest" in name.lower()}
            self.assertEqual(
                allowed,
                present,
                f"kernel_adoption_control.{stem}: the digest-named attributes "
                "present and the ones declared package-owned disagree. A new "
                "one is named here with a reason, or it is a Foundation "
                "concern that does not belong in this package",
            )

    def test_the_allowlist_names_no_module_that_does_not_exist(self) -> None:
        """The other half of the ratchet, at module granularity."""
        self.assertLessEqual(set(PACKAGE_OWNED_DIGEST_NAMES), set(_package_modules()))

    def test_the_digest_arm_bites(self) -> None:
        """Sensitivity. A clean tree proves nothing about the detector itself.

        Planted: a module carrying an undeclared digest-named attribute is
        NAMED. Near-miss: an attribute whose name merely CONTAINS a substring of
        it -- `digestible` contains "digest" and would be caught, so the
        near-miss is a name that does not, and must stay silent.
        """
        import types

        planted = types.ModuleType("planted")
        planted.PROFILE_DIGEST = "sha256:x"  # type: ignore[attr-defined]
        present = {name for name in dir(planted) if "digest" in name.lower()}
        self.assertIn("PROFILE_DIGEST", present)

        near_miss = types.ModuleType("near_miss")
        near_miss.artifact_reference = "sha256:x"  # type: ignore[attr-defined]
        quiet = {name for name in dir(near_miss) if "digest" in name.lower()}
        self.assertEqual(set(), quiet)

    def test_the_one_module_carrying_the_frozen_contract_still_holds_its_digest(
        self,
    ) -> None:
        """`KernelCatalogueEvidence.artifact_digest` is v1's and stays v1's.

        v1 is frozen. The successor carries its own catalogue binding, and this
        asserts the frozen one was not quietly edited into it.
        """
        self.assertIn(
            "artifact_digest",
            {field.name for field in dataclasses.fields(KernelCatalogueEvidence)},
        )

    def test_no_finding_code_speaks_about_a_profile_document(self) -> None:
        for code in FindingCode:
            self.assertTrue(
                code.value.startswith("kernel."),
                f"{code.value} leaves this package's own subject",
            )
            for foreign in ("profile", "schema", "digest", "canonical"):
                self.assertNotIn(foreign, code.value, code.value)


class FoundationBinding(unittest.TestCase):
    """Governance names the Foundation contract by coordinate and parses nothing.

    The intended end state is a released-version binding. It is unavailable:
    measured 2026-09-05, `application_profile.py` is in none of the three
    `dotmac-deployment-foundation` tags, and `main`'s `0.4.0a1` is recorded
    `declared-unpublished`. So the binding is made to the immutable commit the
    bytes live at, and the absence of a release is a stated fact rather than a
    silent one.
    """

    def test_the_shipped_binding_is_an_immutable_coordinate(self) -> None:
        binding = FOUNDATION_APPLICATION_PROFILE
        self.assertRegex(binding.revision, r"^[0-9a-f]{40}$")
        self.assertEqual("michaelayoade/dotmac_starter_mt", binding.repository)
        self.assertIn("application_profile.py", binding.path.as_posix())

    def test_the_missing_release_is_stated_rather_than_implied(self) -> None:
        """A binding that is not yet by release must SAY so.

        `released_version=None` read as "no opinion" would be the unstated
        absence this fleet keeps paying for; `requires_release` makes it a
        readable fact and open decision 50 owns the resolution.
        """
        self.assertTrue(FOUNDATION_APPLICATION_PROFILE.requires_release)
        self.assertIsNone(FOUNDATION_APPLICATION_PROFILE.released_version)

    def test_a_planted_moving_reference_is_refused_by_name(self) -> None:
        for alias in ("main", "latest", "HEAD", "stable", "edge"):
            with self.subTest(alias=alias):
                with self.assertRaises(CoordinateError) as caught:
                    ContractBinding(
                        repository="michaelayoade/dotmac_starter_mt",
                        revision=alias,
                        path=PurePosixPath("a.py"),
                        symbol="S",
                    )
                self.assertIn("branch name or floating alias", str(caught.exception))

    def test_a_planted_non_hex_revision_is_refused(self) -> None:
        for value in ("v0.2.0a2", "0.4.0a1", "deadbeef", "g" * 40):
            with self.subTest(value=value):
                with self.assertRaises(CoordinateError) as caught:
                    ContractBinding(
                        repository="michaelayoade/dotmac_starter_mt",
                        revision=value,
                        path=PurePosixPath("a.py"),
                        symbol="S",
                    )
                self.assertIn("peeled 40-character commit", str(caught.exception))

    def test_a_real_peeled_commit_is_accepted(self) -> None:
        """The near-miss for the alias arm: `55750e10...` is the `v0.2.0a2` peel.

        A refusal that fired on every value would be indistinguishable from one
        that works, so the accepted case is asserted with a real coordinate
        rather than a placeholder.
        """
        binding = ContractBinding(
            repository="michaelayoade/dotmac_starter_mt",
            revision="55750e104df3dd94b6f9f70bf8c8db53986394c7",
            path=PurePosixPath("a.py"),
            symbol="S",
        )
        # Bound by revision with no released_version, so a release is still
        # owed: `requires_release` is the stated absence, not a defect.
        self.assertTrue(binding.requires_release)
        self.assertIn("55750e10", binding.cite())

    def test_a_blank_released_version_is_not_a_release(self) -> None:
        with self.assertRaises(CoordinateError) as caught:
            ContractBinding(
                repository="r",
                revision="55750e104df3dd94b6f9f70bf8c8db53986394c7",
                path=PurePosixPath("a.py"),
                symbol="S",
                released_version="   ",
            )
        self.assertIn("reads as a release nobody named", str(caught.exception))

    def test_the_alias_vocabulary_agrees_with_the_receipt_registry(self) -> None:
        """Two lists that must match and are never compared will not match.

        `tools/check_receipts.py` is the AUTHORITY for receipt coordinates
        (ADR 0018 § 3, ADR 0019). This module expresses the same refusal for a
        contract binding, so their agreement is asserted here instead of being
        left to whoever edits one of them next.
        """
        import importlib.util

        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "_receipts_under_test", root / "tools" / "check_receipts.py"
        )
        assert spec is not None and spec.loader is not None
        receipts = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(receipts)

        registry_alias = receipts.NON_COORDINATES[0][0]
        for word in (
            "latest",
            "current",
            "head",
            "HEAD",
            "main",
            "master",
            "stable",
            "edge",
            "mainline",
            "stables",
            "release",
        ):
            with self.subTest(word=word):
                self.assertEqual(
                    bool(registry_alias.fullmatch(word)),
                    bool(_MOVING_ALIAS.fullmatch(word)),
                    f"{word!r} is classified differently by the two lists",
                )


class DeclarationStates(unittest.TestCase):
    """Three states, and the third is why the section is required.

    Michael's ruling of 2026-09-05: applicable, an explicit typed absence, or a
    refusal. An absent section must not read as "nothing is prohibited" and an
    unreadable one must not read as an empty list. Both are planted here and
    both refuse.
    """

    PROHIBITED_SOURCE = {
        PurePosixPath("app/repo.py"): "from dotmac_kernel.db import session\n"
    }

    def test_a_planted_missing_declaration_refuses_rather_than_passing(self) -> None:
        report = evaluate_sources(
            self.PROHIBITED_SOURCE,
            declaration=DeclarationMissing(
                ".dotmac/kernel-adoption.json does not exist"
            ),
        )
        found = codes_of(report, FindingCode.DECLARATION_MISSING)
        self.assertEqual(1, len(found))
        self.assertIs(Severity.ERROR, found[0].severity)
        self.assertIn("UNMONITORED", found[0].message)
        self.assertFalse(report.conforms)
        # And the arms it gates report nothing, rather than reporting clean.
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_PROHIBITED))

    def test_a_planted_corrupt_declaration_refuses_rather_than_emptying(self) -> None:
        report = evaluate_sources(
            self.PROHIBITED_SOURCE,
            declaration=DeclarationUnreadable(
                ".dotmac/kernel-adoption.json: declaration.contract is 'v0'"
            ),
        )
        found = codes_of(report, FindingCode.DECLARATION_UNREADABLE)
        self.assertEqual(1, len(found))
        self.assertIn("UNMONITORED", found[0].message)
        self.assertFalse(report.conforms)

    def test_an_applicable_declaration_drives_the_prohibited_arm(self) -> None:
        """The near-miss for both refusals above: a real section, and it works."""
        report = evaluate_sources(
            self.PROHIBITED_SOURCE, prohibited=frozenset({"dotmac_kernel.db"})
        )
        self.assertEqual([], codes_of(report, FindingCode.DECLARATION_MISSING))
        self.assertEqual([], codes_of(report, FindingCode.DECLARATION_UNREADABLE))
        found = codes_of(report, FindingCode.SURFACE_PROHIBITED)
        self.assertEqual(1, len(found))
        self.assertEqual(1, found[0].line)
        # The message names the offending module and carries the citation.
        # Asserting the JSON field name instead would tie this test to a
        # spelling the message deliberately does not use.
        self.assertIn("dotmac_kernel.db", found[0].message)
        self.assertIn("ADR 0042", found[0].message)

    def test_a_declaration_that_prohibits_nothing_is_a_statement_somebody_made(
        self,
    ) -> None:
        """Empty tuples are fine WHEN DECLARED. That is the whole distinction."""
        report = evaluate_sources(self.PROHIBITED_SOURCE, prohibited=frozenset())
        self.assertEqual([], codes_of(report, FindingCode.SURFACE_PROHIBITED))
        self.assertEqual([], codes_of(report, FindingCode.DECLARATION_MISSING))

    def test_not_applicable_is_checked_against_the_repositorys_own_imports(
        self,
    ) -> None:
        """An exemption states an ENFORCEABLE premise. This is the enforcement."""
        report = evaluate_sources(
            self.PROHIBITED_SOURCE,
            declaration=not_applicable("this repository consumes no Kernel"),
        )
        found = codes_of(report, FindingCode.DECLARATION_PREMISE_FALSE)
        self.assertEqual(1, len(found))
        self.assertEqual(PurePosixPath("app/repo.py"), found[0].path)
        self.assertEqual(1, found[0].line)
        self.assertIn("dotmac_kernel.db", found[0].message)
        self.assertIn("consumes no Kernel", found[0].message)

    def test_a_true_not_applicable_premise_is_silent(self) -> None:
        """The near-miss: a repository that really imports no Kernel."""
        report = evaluate_sources(
            {PurePosixPath("tools/thing.py"): "import json\n\nprint(json)\n"},
            declaration=not_applicable("composes no assembly"),
        )
        self.assertEqual([], codes_of(report, FindingCode.DECLARATION_PREMISE_FALSE))


class DeclarationReading(unittest.TestCase):
    """`read_declaration` turns every failure into an outcome and never raises.

    A caller that has to remember a `try` is a caller that will one day report
    a clean run over a file it could not open.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".dotmac").mkdir()

    def write(self, text: str) -> None:
        (self.root / ".dotmac" / "kernel-adoption.json").write_text(text)

    def test_an_absent_file_is_missing_not_empty(self) -> None:
        outcome = read_declaration(self.root)
        self.assertIsInstance(outcome, DeclarationMissing)

    def test_a_document_that_is_not_an_object_is_unreadable(self) -> None:
        self.write(json.dumps(["not", "a", "declaration"]))
        self.assertIsInstance(read_declaration(self.root), DeclarationUnreadable)

    def test_invalid_json_is_unreadable_not_empty(self) -> None:
        self.write("{not json")
        self.assertIsInstance(read_declaration(self.root), DeclarationUnreadable)

    def test_a_document_that_does_not_parse_is_unreadable(self) -> None:
        self.write(
            json.dumps(
                {
                    "contract": KERNEL_ADOPTION_CONTRACT,
                    "product_revision": PRODUCT_REVISION,
                    "applicability": "maybe",
                }
            )
        )
        self.assertIsInstance(read_declaration(self.root), DeclarationUnreadable)

    def test_a_valid_declaration_is_present(self) -> None:
        self.write(
            json.dumps(
                {
                    "contract": KERNEL_ADOPTION_CONTRACT,
                    "product_revision": PRODUCT_REVISION,
                    "applicability": "not_applicable",
                    "not_applicable_reason": "composes no assembly",
                }
            )
        )
        outcome = read_declaration(self.root)
        assert isinstance(outcome, DeclarationPresent)
        self.assertIs(
            KernelAdoptionApplicability.NOT_APPLICABLE,
            outcome.declaration.applicability,
        )

    def test_a_bound_non_default_path_is_honoured(self) -> None:
        """The binding names WHERE; it never carries the contents."""
        (self.root / "elsewhere").mkdir()
        (self.root / "elsewhere" / "adoption.json").write_text(
            json.dumps(
                {
                    "contract": KERNEL_ADOPTION_CONTRACT,
                    "product_revision": PRODUCT_REVISION,
                    "applicability": "not_applicable",
                    "not_applicable_reason": "composes no assembly",
                }
            )
        )
        outcome = read_declaration(self.root, PurePosixPath("elsewhere/adoption.json"))
        self.assertIsInstance(outcome, DeclarationPresent)

    def test_a_bound_path_that_is_absent_is_missing_not_defaulted(self) -> None:
        """A binding to nothing must not silently fall back to the default."""
        self.write(
            json.dumps(
                {
                    "contract": KERNEL_ADOPTION_CONTRACT,
                    "product_revision": PRODUCT_REVISION,
                    "applicability": "not_applicable",
                    "not_applicable_reason": "composes no assembly",
                }
            )
        )
        outcome = read_declaration(self.root, PurePosixPath("elsewhere/adoption.json"))
        self.assertIsInstance(outcome, DeclarationMissing)
        self.assertIn("elsewhere/adoption.json", str(outcome))

    def test_this_repositorys_own_declaration_reads(self) -> None:
        """The admit control over the real file, not a fixture."""
        outcome = read_declaration(Path(__file__).resolve().parent.parent)
        assert isinstance(outcome, DeclarationPresent)
        self.assertIs(
            KernelAdoptionApplicability.NOT_APPLICABLE,
            outcome.declaration.applicability,
        )


class BootstrapOnlyStates(unittest.TestCase):
    """A revision-bound binding cannot be made to count. Structurally.

    Michael's ruling of 2026-09-05 permits the immutable source coordinate
    "only as a temporary, report-only bootstrap" and says it "must never count
    as installed, admitted, or adopted". This class is the enforcement: the
    claim cannot be CONSTRUCTED, so there is no later place for someone to
    decide the bootstrap was good enough.
    """

    RELEASED = ContractBinding(
        repository="michaelayoade/dotmac_starter_mt",
        revision="55750e104df3dd94b6f9f70bf8c8db53986394c7",
        path=PurePosixPath("a.py"),
        symbol="S",
        released_version="0.2.0a2",
    )

    def test_a_revision_binding_cannot_be_installed_admitted_or_adopted(self) -> None:
        for state in (
            AdoptionState.INSTALLED,
            AdoptionState.ADMITTED,
            AdoptionState.ADOPTED,
        ):
            with self.subTest(state=state):
                with self.assertRaises(BootstrapOnlyError) as caught:
                    AdoptionClaim(FOUNDATION_APPLICATION_PROFILE, state)
                message = str(caught.exception)
                self.assertIn(state.value, message)
                self.assertIn("report-only bootstrap", message)
                self.assertIn(FOUNDATION_APPLICATION_PROFILE.revision, message)

    def test_the_shipped_binding_may_hold_bootstrap(self) -> None:
        """The admit control. A guard that refused every state would prove nothing."""
        claim = AdoptionClaim(FOUNDATION_APPLICATION_PROFILE, AdoptionState.BOOTSTRAP)
        self.assertIs(AdoptionState.BOOTSTRAP, claim.state)

    def test_a_released_binding_may_hold_every_state(self) -> None:
        """The near-miss that keeps the refusal a property of the COORDINATE KIND.

        If this failed too, the guard would be "AdoptionClaim always raises"
        rather than "a source revision cannot establish a release fact", and the
        test above would pass for the wrong reason.
        """
        for state in AdoptionState:
            with self.subTest(state=state):
                self.assertIs(state, AdoptionClaim(self.RELEASED, state).state)

    def test_the_guard_would_fail_if_a_revision_binding_were_made_to_count(
        self,
    ) -> None:
        """The sensitivity proof stated as the thing that must stay true.

        `requires_release` is the only input to the refusal. If a later change
        made a revision-bound binding report `requires_release == False`, every
        release-only state would silently become constructible over it — so the
        property is asserted directly rather than inferred from the raises
        above.
        """
        self.assertTrue(FOUNDATION_APPLICATION_PROFILE.requires_release)
        self.assertFalse(self.RELEASED.requires_release)

    def test_the_abandoned_version_is_refused_by_name(self) -> None:
        """`0.4.0a1` is on `main`, unpublished, and must never be bound."""
        self.assertIn("0.4.0a1", ABANDONED_VERSIONS)
        for version in ABANDONED_VERSIONS:
            with self.subTest(version=version):
                with self.assertRaises(CoordinateError) as caught:
                    ContractBinding(
                        repository="michaelayoade/dotmac_starter_mt",
                        revision="55750e104df3dd94b6f9f70bf8c8db53986394c7",
                        path=PurePosixPath("a.py"),
                        symbol="S",
                        released_version=version,
                    )
                self.assertIn("abandoned", str(caught.exception))

    def test_a_genuinely_published_version_is_not_refused(self) -> None:
        """The near-miss: `0.2.0a2` is a real tag and must bind cleanly."""
        self.assertEqual("0.2.0a2", self.RELEASED.released_version)


if __name__ == "__main__":
    unittest.main()
