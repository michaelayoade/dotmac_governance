"""Kernel-adoption conformance over product source, and the runner that runs it.

This package holds no profile parser. `ApplicationFoundationProfile.v1` is
owned and verified by `dotmac-deployment-foundation`; see `contracts` for the
boundary and ADR 0042 for the decision and its three open blockers.

Since ADR 0042's amendment of 2026-09-05 it is no longer report-only: `runner`
is the activated gate, and `python3 -m kernel_adoption_control` is how a
repository evaluates its own declaration against its own source. The run
happens in the MEASURED repository's CI, because a declaration in another
repository's checkout is not a repository-local fact for Governance
(ADR 0013 § 1).
"""

from .contracts import (
    AdoptionReport,
    DeclarationEmpty,
    DeclarationIncomplete,
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
    TransitionalSurface,
)
from .declaration import DECLARATION_PATH, read_declaration
from .declaration_contract import (
    KERNEL_ADOPTION_CONTRACT,
    DeclarationError,
    IncompleteDeclarationError,
    KernelCatalogueEvidence,
    ProhibitedSurface,
    RequiredSurface,
    SurfaceSite,
    parse_declaration,
)
from .declaration_contract_v2 import (
    KERNEL_ADOPTION_CONTRACT_V2,
    AnyKernelAdoptionDeclaration,
    KernelAdoptionDeclarationV2,
    KernelCatalogueBinding,
    SourceSurfaceCoordinate,
    parse_any_declaration,
    parse_declaration_v2,
)
from .engine import KERNEL_ROOT, evaluate
from .runner import (
    RUN_CONTRACT,
    Citability,
    DocumentVerdict,
    ProductObservation,
    RunnerError,
    RunReport,
    citability,
    inspect_report_document,
    resolve_observer,
    run,
)
from .surface import (
    CATALOGUE_DIGEST_ALGORITHM,
    SOURCE_SURFACE_ALGORITHM,
    SOURCE_SURFACE_IDENTITY_ALGORITHM,
    SurfaceBinding,
    SurfaceFact,
    SurfaceIdentityFact,
    catalogue_digest,
    surface_digest,
    surface_identity_digest,
)
from .versions import VersionError, compare_versions

__all__ = [
    "CATALOGUE_DIGEST_ALGORITHM",
    "DECLARATION_PATH",
    "KERNEL_ADOPTION_CONTRACT",
    "KERNEL_ADOPTION_CONTRACT_V2",
    "KERNEL_ROOT",
    "RUN_CONTRACT",
    "SOURCE_SURFACE_ALGORITHM",
    "SOURCE_SURFACE_IDENTITY_ALGORITHM",
    "AdoptionReport",
    "AnyKernelAdoptionDeclaration",
    "Citability",
    "DocumentVerdict",
    "DeclarationEmpty",
    "DeclarationIncomplete",
    "DeclarationMissing",
    "DeclarationOutcome",
    "DeclarationPresent",
    "DeclarationUnreadable",
    "Finding",
    "FindingCode",
    "KernelAdoptionApplicability",
    "KernelAdoptionDeclaration",
    "KernelAdoptionDeclarationV2",
    "KernelAdoptionInputs",
    "KernelSurfaceCatalogue",
    "PinSite",
    "Severity",
    "DeclarationError",
    "IncompleteDeclarationError",
    "KernelCatalogueBinding",
    "KernelCatalogueEvidence",
    "ProductObservation",
    "ProhibitedSurface",
    "RequiredSurface",
    "RunReport",
    "RunnerError",
    "SourceSurfaceCoordinate",
    "SurfaceBinding",
    "SurfaceFact",
    "SurfaceIdentityFact",
    "SurfaceSite",
    "TransitionalSurface",
    "VersionError",
    "catalogue_digest",
    "citability",
    "compare_versions",
    "evaluate",
    "inspect_report_document",
    "parse_any_declaration",
    "parse_declaration",
    "parse_declaration_v2",
    "read_declaration",
    "resolve_observer",
    "run",
    "surface_digest",
    "surface_identity_digest",
]
