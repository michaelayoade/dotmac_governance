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

import json
import tempfile
import unittest
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
    Severity,
    TransitionalSurfaceDeclaration,
    evaluate,
    read_declaration,
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


def declared(
    prohibited: frozenset[str] = frozenset(),
    transitional: tuple[TransitionalSurfaceDeclaration, ...] = (),
) -> DeclarationOutcome:
    return DeclarationPresent(
        KernelAdoptionDeclaration(
            section_version=1,
            applicability=KernelAdoptionApplicability.APPLICABLE,
            not_applicable_reason=None,
            prohibited_surfaces=tuple(sorted(prohibited)),
            transitional_surfaces=transitional,
        )
    )


def evaluate_sources(
    sources: dict[PurePosixPath, str],
    *,
    prohibited: frozenset[str] = frozenset(),
    pins: tuple[PinSite, ...] = (),
    transitional: tuple[TransitionalSurfaceDeclaration, ...] = (),
    declaration: DeclarationOutcome | None = None,
) -> AdoptionReport:
    return evaluate(
        KernelAdoptionInputs(
            sources=sources,
            catalogue=A98,
            pin_sites=pins,
            declaration=(
                declared(prohibited, transitional)
                if declaration is None
                else declaration
            ),
        )
    )


def codes_of(report: AdoptionReport, code: FindingCode) -> list[Finding]:
    return [item for item in report.findings if item.code == code]


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
        self.assertEqual([], list(report.findings), report.to_dict())


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
        notices = codes_of(report, FindingCode.PIN_DISAGREES)
        self.assertEqual(1, len(notices))
        self.assertIs(Severity.NOTICE, notices[0].severity)
        self.assertIn("cannot disagree with itself", notices[0].message)

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


class ProhibitedSurface(unittest.TestCase):
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
    engine at all: `standards_control.profile.parse_kernel_adoption` refuses
    the section, proved in `tests/test_standards_control.py`. What this arm
    catches is the shape that parses and still says nothing — a present field
    holding whitespace. A guard that only checked for absence would pass a
    declaration whose owner is a space.
    """

    def test_a_transitional_surface_with_neither_owner_nor_expiry_is_named(
        self,
    ) -> None:
        report = evaluate_sources(
            CLEAN,
            transitional=(
                TransitionalSurfaceDeclaration(
                    module="dotmac_kernel.db", owner="", expiry="  "
                ),
            ),
        )
        found = codes_of(report, FindingCode.TRANSITIONAL_UNOWNED)
        self.assertEqual(1, len(found))
        self.assertIn("dotmac_kernel.db", found[0].message)
        self.assertIn("owner", found[0].message)
        self.assertIn("expiry", found[0].message)

    def test_a_blank_owner_is_not_an_owner(self) -> None:
        report = evaluate_sources(
            CLEAN,
            transitional=(
                TransitionalSurfaceDeclaration(
                    module="dotmac_kernel.db", owner="   ", expiry="2026-12-01"
                ),
            ),
        )
        found = codes_of(report, FindingCode.TRANSITIONAL_UNOWNED)
        self.assertEqual(1, len(found))
        self.assertIn("owner", found[0].message)

    def test_a_fully_stated_transitional_surface_is_silent(self) -> None:
        report = evaluate_sources(
            CLEAN,
            transitional=(
                TransitionalSurfaceDeclaration(
                    module="dotmac_kernel.db",
                    owner="Michael Ayoade",
                    expiry="2026-12-01",
                ),
            ),
        )
        self.assertEqual([], codes_of(report, FindingCode.TRANSITIONAL_UNOWNED))


class BoundaryIsStructural(unittest.TestCase):
    """The package holds no profile parser, and that is asserted rather than said.

    `ApplicationFoundationProfile.v1` is owned and verified by
    `dotmac-deployment-foundation`. A second parser that exists but is unused is
    still a second parser, so its absence is a test rather than a paragraph.
    """

    def test_the_package_declares_no_profile_schema_and_no_digest(self) -> None:
        import kernel_adoption_control
        from kernel_adoption_control import (
            contracts,
            declaration,
            engine,
            foundation_binding,
        )

        for module in (
            kernel_adoption_control,
            contracts,
            declaration,
            engine,
            foundation_binding,
        ):
            names = set(dir(module))
            for forbidden in ("APPLICATION_PROFILE_SCHEMA", "canonical_bytes"):
                self.assertNotIn(forbidden, names, module.__name__)
            for name in names:
                self.assertNotIn("digest", name.lower(), f"{module.__name__}.{name}")

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
                "no section in .dotmac/standards-profile.json"
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
            declaration=DeclarationUnreadable("section_version 2 is not 1"),
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
        self.assertIn("prohibited_surfaces", found[0].message)

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
            declaration=DeclarationPresent(
                KernelAdoptionDeclaration(
                    section_version=1,
                    applicability=KernelAdoptionApplicability.NOT_APPLICABLE,
                    not_applicable_reason="this repository consumes no Kernel",
                    prohibited_surfaces=(),
                    transitional_surfaces=(),
                )
            ),
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
            declaration=DeclarationPresent(
                KernelAdoptionDeclaration(
                    section_version=1,
                    applicability=KernelAdoptionApplicability.NOT_APPLICABLE,
                    not_applicable_reason="composes no assembly",
                    prohibited_surfaces=(),
                    transitional_surfaces=(),
                )
            ),
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
        (self.root / ".dotmac" / "standards-profile.json").write_text(text)

    def test_an_absent_file_is_missing_not_empty(self) -> None:
        outcome = read_declaration(self.root)
        self.assertIsInstance(outcome, DeclarationMissing)

    def test_a_profile_without_the_section_is_missing(self) -> None:
        self.write(json.dumps({"schema_version": 12}))
        outcome = read_declaration(self.root)
        self.assertIsInstance(outcome, DeclarationMissing)
        self.assertIn("kernel_adoption", str(outcome))

    def test_invalid_json_is_unreadable_not_empty(self) -> None:
        self.write("{not json")
        self.assertIsInstance(read_declaration(self.root), DeclarationUnreadable)

    def test_a_section_that_does_not_parse_is_unreadable(self) -> None:
        self.write(
            json.dumps(
                {"kernel_adoption": {"section_version": 1, "applicability": "maybe"}}
            )
        )
        self.assertIsInstance(read_declaration(self.root), DeclarationUnreadable)

    def test_a_valid_section_is_present(self) -> None:
        self.write(
            json.dumps(
                {
                    "kernel_adoption": {
                        "section_version": 1,
                        "applicability": "applicable",
                        "prohibited_surfaces": ["dotmac_kernel.db"],
                        "transitional_surfaces": [],
                    }
                }
            )
        )
        outcome = read_declaration(self.root)
        assert isinstance(outcome, DeclarationPresent)
        self.assertEqual(("dotmac_kernel.db",), outcome.declaration.prohibited_surfaces)

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
