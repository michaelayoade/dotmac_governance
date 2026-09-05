"""Report-only Kernel-adoption conformance over product source.

This package holds no profile parser. `ApplicationFoundationProfile.v1` is
owned and verified by `dotmac-deployment-foundation`; see `contracts` for the
boundary and ADR 0042 for the decision and its three open blockers.
"""

from .contracts import (
    AdoptionReport,
    Finding,
    FindingCode,
    KernelAdoptionInputs,
    KernelSurfaceCatalogue,
    PinSite,
    Severity,
    TransitionalSurface,
)
from .engine import KERNEL_ROOT, evaluate

__all__ = [
    "KERNEL_ROOT",
    "AdoptionReport",
    "Finding",
    "FindingCode",
    "KernelAdoptionInputs",
    "KernelSurfaceCatalogue",
    "PinSite",
    "Severity",
    "TransitionalSurface",
    "evaluate",
]
