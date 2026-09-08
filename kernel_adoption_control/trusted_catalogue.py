"""Governance-held Kernel release catalogues; product lists are observations."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from .contracts import KernelSurfaceCatalogue
from .versions import VersionError, compare_versions

PUBLIC_EXPORTS_SCHEMA = "dotmac.kernel-public-exports.v1"
RELEASE_EVIDENCE_SCHEMA = "KernelReleaseEvidence.v2"
LEGACY_KERNEL_CEILING = "0.1.0a102"
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_KERNEL_VERSION = re.compile(
    r"^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)(?:a|b|rc)[1-9][0-9]*$"
)
_RECORD_KEYS = frozenset(
    {
        "schema",
        "version",
        "tag",
        "tag_object",
        "tag_disposition",
        "source_sha",
        "authorization",
        "publisher",
        "verifier",
        "verification_receipt_sha256",
        "verification_receipt_artifact",
        "tag_decision_receipt_sha256",
        "tag_decision_receipt_artifact",
        "registry",
        "files",
        "public_exports",
    }
)


class TrustedCatalogueError(ValueError):
    """No admissible Governance-owned catalogue can classify this release."""


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TrustedCatalogueError(f"duplicate JSON field {key!r}")
        result[key] = value
    return result


def _json(raw: bytes, label: str, *, indent: int | None) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TrustedCatalogueError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise TrustedCatalogueError(f"{label} must be a JSON object")
    if indent is None:
        canonical_text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    else:
        canonical_text = json.dumps(value, sort_keys=True, indent=2)
    canonical = (canonical_text + "\n").encode()
    if raw != canonical:
        raise TrustedCatalogueError(f"{label} is not canonical JSON")
    return value


def _str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TrustedCatalogueError(f"{label} must be a non-empty string")
    return value


def _hex(value: object, label: str, matcher: re.Pattern[str]) -> str:
    result = _str(value, label)
    if not matcher.fullmatch(result):
        raise TrustedCatalogueError(f"{label} has the wrong digest shape")
    return result


def _canonical_kernel_filenames(version: str) -> frozenset[str]:
    if not _KERNEL_VERSION.fullmatch(version):
        raise TrustedCatalogueError(
            "kernel version is not a canonical public prerelease"
        )
    return frozenset(
        {
            f"dotmac_kernel-{version}-py3-none-any.whl",
            f"dotmac_kernel-{version}.tar.gz",
        }
    )


def _release_identity(evidence: dict[str, object], version: str, revision: str) -> None:
    """Mirror the producer's v2 identity checks, not a weaker look-alike."""
    authorization = evidence["authorization"]
    if not isinstance(authorization, dict) or set(authorization) != {
        "schema",
        "state",
        "source_sha",
        "authorization_commit",
        "authorization",
    }:
        raise TrustedCatalogueError("authorization binding fields differ")
    allocation = authorization["authorization"]
    if not isinstance(allocation, dict) or set(allocation) != {
        "latest_tag",
        "latest_tag_object",
        "latest_tag_commit",
        "base_sha",
        "target_version",
        "normalized_release_input_digest",
    }:
        raise TrustedCatalogueError("authorization allocation fields differ")
    if (
        authorization["schema"] != "KernelReleaseSourceBinding.v1"
        or authorization["state"] != "allocated"
        or authorization["source_sha"] != revision
        or allocation["target_version"] != version
    ):
        raise TrustedCatalogueError("authorization binding identity differs")
    _hex(authorization["authorization_commit"], "authorization_commit", _HEX40)
    for field in ("latest_tag_object", "latest_tag_commit", "base_sha"):
        _hex(allocation[field], f"authorization.{field}", _HEX40)
    _str(allocation["latest_tag"], "authorization.latest_tag")
    normalized = _str(
        allocation["normalized_release_input_digest"],
        "authorization.normalized_release_input_digest",
    )
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", normalized):
        raise TrustedCatalogueError("authorization input digest differs")

    publisher, verifier, registry = (
        evidence["publisher"],
        evidence["verifier"],
        evidence["registry"],
    )
    if not isinstance(publisher, dict) or set(publisher) != {
        "repository",
        "workflow_path",
        "head_branch",
        "run_id",
        "run_attempt",
        "artifact_id",
    }:
        raise TrustedCatalogueError("publisher fields differ")
    if not isinstance(verifier, dict) or set(verifier) != {
        "repository",
        "ref",
        "source_sha",
        "run_id",
        "run_attempt",
    }:
        raise TrustedCatalogueError("verifier fields differ")
    if not isinstance(registry, dict) or set(registry) != {
        "index_origin",
        "observed_identity",
        "facility_http_methods",
    }:
        raise TrustedCatalogueError("registry fields differ")
    if (
        publisher["repository"] != "michaelayoade/dotmac_starter_mt"
        or publisher["workflow_path"] != ".github/workflows/release-kernel.yml"
        or publisher["head_branch"] != "main"
        or publisher["run_attempt"] != 1
        or not isinstance(publisher["run_id"], int)
        or publisher["run_id"] <= 0
        or not isinstance(publisher["artifact_id"], int)
        or publisher["artifact_id"] <= 0
        or verifier["repository"] != "michaelayoade/dotmac_starter_mt"
        or verifier["ref"] != "refs/heads/main"
        or verifier["source_sha"] != revision
        or verifier["run_attempt"] != 1
        or not isinstance(verifier["run_id"], int)
        or verifier["run_id"] <= 0
        or registry["index_origin"] != "https://registry.dotmac.io"
        or registry["observed_identity"] != {"login": "ci-reader", "is_admin": False}
        or registry["facility_http_methods"] != ["GET"]
    ):
        raise TrustedCatalogueError("release provider identity differs")


@dataclass(frozen=True)
class TrustedKernelCatalogue:
    version: str
    revision: str
    artifact_digest: str
    supported: frozenset[str]
    internal: frozenset[str]
    root_exports: frozenset[str]
    module_exports: Mapping[str, frozenset[str] | None]
    public_exports_digest: str

    def as_surface_catalogue(self) -> KernelSurfaceCatalogue:
        return KernelSurfaceCatalogue(
            revision=self.revision,
            version=self.version,
            supported=self.supported,
            internal=self.internal,
            artifact_digest=self.artifact_digest,
            root_exports=self.root_exports,
            module_exports=self.module_exports,
        )


def load_trusted_catalogue(
    record: bytes, public_exports: bytes
) -> TrustedKernelCatalogue:
    """Parse exact v2 evidence plus the wheel package-data it hashes."""
    evidence = _json(record, "KernelReleaseEvidence.v2", indent=None)
    if set(evidence) != _RECORD_KEYS:
        raise TrustedCatalogueError("release evidence has unknown or missing fields")
    if evidence["schema"] != RELEASE_EVIDENCE_SCHEMA:
        raise TrustedCatalogueError(
            "release evidence schema is not KernelReleaseEvidence.v2"
        )
    version = _str(evidence["version"], "version")
    if evidence["tag"] != f"dotmac-kernel-v{version}" or evidence[
        "tag_disposition"
    ] not in {"CREATE", "ALREADY"}:
        raise TrustedCatalogueError("release tag does not bind its version")
    revision = _hex(evidence["source_sha"], "source_sha", _HEX40)
    _hex(evidence["tag_object"], "tag_object", _HEX40)
    for field in ("verification_receipt_sha256", "tag_decision_receipt_sha256"):
        _hex(evidence[field], field, _HEX64)
    for field in ("verification_receipt_artifact", "tag_decision_receipt_artifact"):
        _str(evidence[field], field)
    if (
        evidence["verification_receipt_artifact"]
        != "kernel-release-verification-receipt"
    ):
        raise TrustedCatalogueError("verification receipt artifact differs")
    if evidence["tag_decision_receipt_artifact"] != "kernel-release-tag-decision":
        raise TrustedCatalogueError("tag decision receipt artifact differs")
    _release_identity(evidence, version, revision)
    files = evidence["files"]
    if not isinstance(files, list) or len(files) != 2:
        raise TrustedCatalogueError("release files must be exactly wheel and sdist")
    wheel: str | None = None
    file_names: set[str] = set()
    expected_names = _canonical_kernel_filenames(version)
    for item in files:
        if not isinstance(item, dict) or set(item) != {"name", "size", "sha256"}:
            raise TrustedCatalogueError("release file entry is invalid")
        name = _str(item["name"], "release file name")
        size = item["size"]
        if (
            not isinstance(size, int)
            or isinstance(size, bool)
            or size <= 0
            or name in file_names
        ):
            raise TrustedCatalogueError("release file name or size is invalid")
        file_names.add(name)
        digest = _hex(item["sha256"], "release file sha256", _HEX64)
        if name.endswith(".whl"):
            wheel = "sha256:" + digest
    if file_names != expected_names or wheel is None:
        raise TrustedCatalogueError(
            "release files do not match the version-derived wheel and sdist names"
        )
    advertised = evidence["public_exports"]
    if not isinstance(advertised, dict) or set(advertised) != {
        "name",
        "schema",
        "size",
        "sha256",
    }:
        raise TrustedCatalogueError(
            "public_exports evidence has unknown or missing fields"
        )
    if (
        advertised["name"] != "dotmac_kernel/public_exports.json"
        or advertised["schema"] != PUBLIC_EXPORTS_SCHEMA
    ):
        raise TrustedCatalogueError("public_exports coordinate is invalid")
    # Parse before comparing the outer commitment.  Duplicate keys make the
    # bytes ambiguous; reporting only their changed size would hide that the
    # parser itself cannot name a document.
    document = _json(public_exports, "public_exports", indent=2)
    if (
        not isinstance(advertised["size"], int)
        or isinstance(advertised["size"], bool)
        or advertised["size"] != len(public_exports)
    ):
        raise TrustedCatalogueError("public_exports size does not match bytes")
    digest = _hex(advertised["sha256"], "public_exports sha256", _HEX64)
    actual = hashlib.sha256(public_exports).hexdigest()
    if digest != actual:
        raise TrustedCatalogueError("public_exports digest does not match bytes")
    if (
        set(document)
        != {
            "schema",
            "supported_modules",
            "internal_modules",
            "root_exports",
            "modules",
        }
        or document["schema"] != PUBLIC_EXPORTS_SCHEMA
    ):
        raise TrustedCatalogueError("public_exports has unknown fields or schema")

    def names(key: str) -> frozenset[str]:
        value = document[key]
        if (
            not isinstance(value, list)
            or any(not isinstance(item, str) or not item for item in value)
            or value != sorted(set(value))
        ):
            raise TrustedCatalogueError(f"{key} must be sorted unique names")
        return frozenset(value)

    supported, internal, root = (
        names("supported_modules"),
        names("internal_modules"),
        names("root_exports"),
    )
    if supported & internal:
        raise TrustedCatalogueError("supported and internal modules overlap")
    modules = document["modules"]
    if (
        not isinstance(modules, dict)
        or not modules
        or set(modules) != supported | internal
    ):
        raise TrustedCatalogueError("module entries do not match classified modules")
    exported: dict[str, frozenset[str] | None] = {}
    for module, entry in modules.items():
        if not isinstance(module, str) or not (
            module == "dotmac_kernel" or module.startswith("dotmac_kernel.")
        ):
            raise TrustedCatalogueError("module export key is not a Kernel module")
        if not isinstance(entry, dict) or set(entry) != {
            "classification",
            "status",
            "exports",
        }:
            raise TrustedCatalogueError(f"invalid export entry for {module!r}")
        classification, status, values = (
            entry["classification"],
            entry["status"],
            entry["exports"],
        )
        if classification not in {"supported", "internal"} or (
            (classification == "supported") != (module in supported)
        ):
            raise TrustedCatalogueError(f"classification disagrees for {module!r}")
        if status == "unavailable" and values is None:
            exported[module] = None
        elif (
            status == "declared"
            and isinstance(values, list)
            and values == sorted(set(values))
            and all(isinstance(item, str) and item for item in values)
        ):
            exported[module] = frozenset(values)
        else:
            raise TrustedCatalogueError(f"invalid exports for {module!r}")
    return TrustedKernelCatalogue(
        version,
        revision,
        wheel,
        supported,
        internal,
        root,
        MappingProxyType(exported),
        "sha256:" + actual,
    )


class TrustedCatalogueStore:
    """Governance's immutable resource mapping. Products cannot populate it."""

    def __init__(
        self,
        records: Mapping[str, tuple[bytes, bytes]] | None = None,
        evidence_root: Path | None = None,
    ):
        self._records = MappingProxyType(dict(records or {}))
        self._evidence_root = evidence_root

    def resolve(self, version: str) -> TrustedKernelCatalogue:
        pair = self._records.get(version)
        if pair is None:
            if self._evidence_root is not None:
                record = (
                    self._evidence_root
                    / "kernel-release-verifications"
                    / f"{version}.json"
                )
                catalogue = (
                    self._evidence_root / "kernel-public-exports" / f"{version}.json"
                )
                if record.is_file() and catalogue.is_file():
                    pair = record.read_bytes(), catalogue.read_bytes()
            if pair is None:
                raise TrustedCatalogueError(
                    f"no Governance-owned KernelReleaseEvidence.v2 pair exists for {version}; legacy ceiling is {LEGACY_KERNEL_CEILING}"
                )
        result = load_trusted_catalogue(*pair)
        if result.version != version:
            raise TrustedCatalogueError(
                "Governance record key disagrees with its version"
            )
        return result

    def snapshot(self) -> TrustedCatalogueStore:
        """Read Governance inventory bytes before untrusted observer code runs.

        The runner calls this before importing product code.  The returned
        store has no path and therefore cannot be redirected by rebinding the
        default store later in the process.  This is integrity within the
        normal runner discipline, not a Python sandbox against arbitrary code.
        """
        captured = dict(self._records)
        if self._evidence_root is not None:
            records = self._evidence_root / "kernel-release-verifications"
            catalogues = self._evidence_root / "kernel-public-exports"
            if records.is_dir() and catalogues.is_dir():
                for record in records.glob("*.json"):
                    catalogue = catalogues / record.name
                    if catalogue.is_file():
                        captured.setdefault(
                            record.stem, (record.read_bytes(), catalogue.read_bytes())
                        )
        return TrustedCatalogueStore(captured)


# The runner reads only these Governance-owned repository paths.  No product
# observer or command-line argument selects them.  They are intentionally
# empty until a real successor publishes both immutable bytes; a102 remains on
# its explicitly retained legacy path and no a103 evidence is fabricated here.
_GOVERNANCE_INVENTORIES = (
    Path(__file__).resolve().parent.parent / "docs" / "inventories"
)
DEFAULT_TRUSTED_CATALOGUES = TrustedCatalogueStore(
    evidence_root=_GOVERNANCE_INVENTORIES
)


def trusted_surface_catalogue(
    observed: KernelSurfaceCatalogue | None,
    store: TrustedCatalogueStore = DEFAULT_TRUSTED_CATALOGUES,
) -> KernelSurfaceCatalogue | None:
    """Use trusted successor lists, verifying product coordinate facts first."""
    if observed is None:
        return None
    try:
        newer = (
            compare_versions(
                observed.version,
                LEGACY_KERNEL_CEILING,
                where="trusted Kernel catalogue",
            )
            > 0
        )
    except VersionError as error:
        raise TrustedCatalogueError(str(error)) from error
    if not newer:
        return observed
    trusted = store.resolve(observed.version)
    disagreements = [
        name
        for name, actual, expected in (
            ("revision", observed.revision, trusted.revision),
            ("artifact_digest", observed.artifact_digest, trusted.artifact_digest),
            ("supported_modules", observed.supported, trusted.supported),
            ("internal_modules", observed.internal, trusted.internal),
            ("root_exports", observed.root_exports, trusted.root_exports),
        )
        if actual != expected
    ]
    if disagreements:
        raise TrustedCatalogueError(
            "product observer disagrees with Governance-owned release evidence on "
            + ", ".join(disagreements)
        )
    return trusted.as_surface_catalogue()


__all__ = [
    "DEFAULT_TRUSTED_CATALOGUES",
    "LEGACY_KERNEL_CEILING",
    "PUBLIC_EXPORTS_SCHEMA",
    "RELEASE_EVIDENCE_SCHEMA",
    "TrustedCatalogueError",
    "TrustedCatalogueStore",
    "TrustedKernelCatalogue",
    "load_trusted_catalogue",
    "trusted_surface_catalogue",
]
