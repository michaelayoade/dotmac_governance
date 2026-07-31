"""Dotmac agent bootstrap and conformance control plane."""

from .contracts import (
    AgentProfile,
    BootstrapResult,
    ConformanceReport,
    Diagnostic,
    RepositoryIdentity,
)
from .engine import bootstrap_repository, verify_repository
from .profile import ProfileError, load_profile

__all__ = [
    "AgentProfile",
    "BootstrapResult",
    "ConformanceReport",
    "Diagnostic",
    "ProfileError",
    "RepositoryIdentity",
    "bootstrap_repository",
    "load_profile",
    "verify_repository",
]
