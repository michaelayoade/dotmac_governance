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
from .engine import KERNEL_ROOT, evaluate
from .runner import (
    RUN_CONTRACT,
    ProductObservation,
    RunnerError,
    RunReport,
    is_enforced,
    resolve_observer,
    run,
)

__all__ = [
    "KERNEL_ADOPTION_CONTRACT",
    "KERNEL_ROOT",
    "DECLARATION_PATH",
    "RUN_CONTRACT",
    "AdoptionReport",
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
    "KernelAdoptionInputs",
    "KernelSurfaceCatalogue",
    "PinSite",
    "Severity",
    "DeclarationError",
    "IncompleteDeclarationError",
    "KernelCatalogueEvidence",
    "ProductObservation",
    "ProhibitedSurface",
    "RequiredSurface",
    "RunReport",
    "RunnerError",
    "SurfaceSite",
    "TransitionalSurface",
    "evaluate",
    "is_enforced",
    "parse_declaration",
    "read_declaration",
    "resolve_observer",
    "run",
]
