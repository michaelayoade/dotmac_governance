"""Report-only Kernel-adoption conformance over product source.

This package holds no profile parser. `ApplicationFoundationProfile.v1` is
owned and verified by `dotmac-deployment-foundation`; see `contracts` for the
boundary and ADR 0042 for the decision and its three open blockers.
"""

from .contracts import (
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
    TransitionalSurface,
)
from .declaration import DECLARATION_PATH, read_declaration
from .declaration_contract import (
    KERNEL_ADOPTION_CONTRACT,
    DeclarationError,
    KernelCatalogueEvidence,
    ProhibitedSurface,
    RequiredSurface,
    SurfaceSite,
    parse_declaration,
)
from .engine import KERNEL_ROOT, evaluate

__all__ = [
    "KERNEL_ADOPTION_CONTRACT",
    "KERNEL_ROOT",
    "DECLARATION_PATH",
    "AdoptionReport",
    "DeclarationMissing",
    "DeclarationOutcome",
    "DeclarationPresent",
    "DeclarationUnreadable",
    "Finding",
    "FindingCode",
    "KernelAdoptionApplicability",
    "KernelAdoptionDeclaration",
    "KernelAdoptionInputs",
    "KernelSurfaceCatalogue",
    "PinSite",
    "Severity",
    "TransitionalSurfaceDeclaration",
    "DeclarationError",
    "KernelCatalogueEvidence",
    "ProhibitedSurface",
    "RequiredSurface",
    "SurfaceSite",
    "TransitionalSurface",
    "evaluate",
    "parse_declaration",
    "read_declaration",
]
