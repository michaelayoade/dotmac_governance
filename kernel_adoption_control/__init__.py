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
    TransitionalSurfaceDeclaration,
)
from .declaration import PROFILE_PATH, SECTION_KEY, read_declaration
from .engine import KERNEL_ROOT, evaluate

__all__ = [
    "KERNEL_ROOT",
    "PROFILE_PATH",
    "SECTION_KEY",
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
    "evaluate",
    "read_declaration",
]
