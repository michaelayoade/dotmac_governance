"""Successor Kernel publication authority is Governance-held, not observed."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path, PurePosixPath

import pytest

from kernel_adoption_control import KernelSurfaceCatalogue, catalogue_digest, evaluate
from kernel_adoption_control.contracts import (
    DeclarationPresent,
    FindingCode,
    KernelAdoptionInputs,
)
from kernel_adoption_control.declaration_contract_v2 import parse_declaration_v2
from kernel_adoption_control.engine import (
    _check_module_alias_attributes,
    observed_surface_identity,
    surface_identity_facts,
)
from kernel_adoption_control.trusted_catalogue import (
    PUBLIC_EXPORTS_SCHEMA,
    RELEASE_EVIDENCE_SCHEMA,
    TrustedCatalogueError,
    TrustedCatalogueStore,
    load_trusted_catalogue,
    trusted_surface_catalogue,
)


def canonical(value: object, *, indent: int | None = None) -> bytes:
    kwargs: dict[str, object] = {"sort_keys": True}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return (json.dumps(value, **kwargs) + "\n").encode()


def pair() -> tuple[bytes, bytes]:
    exports = {
        "schema": PUBLIC_EXPORTS_SCHEMA,
        "supported_modules": ["dotmac_kernel.db"],
        "internal_modules": [],
        "root_exports": ["DatabaseRuntime"],
        "modules": {
            "dotmac_kernel.db": {
                "classification": "supported",
                "status": "declared",
                "exports": ["DatabaseRuntime"],
            }
        },
    }
    raw = canonical(exports, indent=2)
    record = {
        "schema": RELEASE_EVIDENCE_SCHEMA,
        "version": "0.1.0a103",
        "tag": "dotmac-kernel-v0.1.0a103",
        "tag_object": "c" * 40,
        "tag_disposition": "CREATE",
        "source_sha": "a" * 40,
        "authorization": {
            "schema": "KernelReleaseSourceBinding.v1",
            "state": "allocated",
            "source_sha": "a" * 40,
            "authorization_commit": "1" * 40,
            "authorization": {
                "latest_tag": "dotmac-kernel-v0.1.0a102",
                "latest_tag_object": "2" * 40,
                "latest_tag_commit": "3" * 40,
                "base_sha": "4" * 40,
                "target_version": "0.1.0a103",
                "normalized_release_input_digest": "sha256:" + "5" * 64,
            },
        },
        "publisher": {
            "repository": "michaelayoade/dotmac_starter_mt",
            "workflow_path": ".github/workflows/release-kernel.yml",
            "head_branch": "main",
            "run_id": 1,
            "run_attempt": 1,
            "artifact_id": 1,
        },
        "verifier": {
            "repository": "michaelayoade/dotmac_starter_mt",
            "ref": "refs/heads/main",
            "source_sha": "a" * 40,
            "run_id": 1,
            "run_attempt": 1,
        },
        "registry": {
            "index_origin": "https://registry.dotmac.io",
            "observed_identity": {"login": "ci-reader", "is_admin": False},
            "facility_http_methods": ["GET"],
        },
        "verification_receipt_sha256": "d" * 64,
        "verification_receipt_artifact": "kernel-release-verification-receipt",
        "tag_decision_receipt_sha256": "e" * 64,
        "tag_decision_receipt_artifact": "kernel-release-tag-decision",
        "files": [
            {
                "name": "dotmac_kernel-0.1.0a103-py3-none-any.whl",
                "size": 1,
                "sha256": "b" * 64,
            },
            {"name": "dotmac_kernel-0.1.0a103.tar.gz", "size": 1, "sha256": "f" * 64},
        ],
        "public_exports": {
            "name": "dotmac_kernel/public_exports.json",
            "schema": PUBLIC_EXPORTS_SCHEMA,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        },
    }
    return canonical(record), raw


def observed(**overrides: object) -> KernelSurfaceCatalogue:
    result: dict[str, object] = {
        "revision": "a" * 40,
        "version": "0.1.0a103",
        "supported": frozenset({"dotmac_kernel.db"}),
        "internal": frozenset(),
        "artifact_digest": "sha256:" + "b" * 64,
        "root_exports": frozenset({"DatabaseRuntime"}),
    }
    result.update(overrides)
    return KernelSurfaceCatalogue(**result)  # type: ignore[arg-type]


def trusted_store() -> TrustedCatalogueStore:
    record, exports = pair()
    return TrustedCatalogueStore({"0.1.0a103": (record, exports)})


def test_successor_uses_governance_lists_not_a_coordinated_product_forgery() -> None:
    # The product can make its lists and declaration digest agree. It still
    # cannot replace the Governance-held release lists.
    forged = observed(supported=frozenset({"dotmac_kernel.db", "dotmac_kernel.evil"}))
    assert catalogue_digest(
        version=forged.version,
        revision=forged.revision,
        supported=forged.supported,
        internal=forged.internal,
        root_exports=forged.root_exports,
    ).startswith("sha256:")
    with pytest.raises(TrustedCatalogueError, match="supported_modules"):
        trusted_surface_catalogue(forged, trusted_store())


def test_successor_without_governance_evidence_refuses() -> None:
    with pytest.raises(TrustedCatalogueError, match="no Governance-owned"):
        trusted_surface_catalogue(observed(), TrustedCatalogueStore())


def test_wrong_wheel_hash_refuses() -> None:
    with pytest.raises(TrustedCatalogueError, match="artifact_digest"):
        trusted_surface_catalogue(
            observed(artifact_digest="sha256:" + "0" * 64), trusted_store()
        )


def test_direct_private_submodule_name_is_refused_against_trusted_exports() -> None:
    catalogue = trusted_surface_catalogue(observed(), trusted_store())
    assert catalogue is not None
    sources = {PurePosixPath("x.py"): "from dotmac_kernel.db import SessionLocal\n"}
    source_digest, _ = observed_surface_identity(surface_identity_facts(sources))
    declaration = parse_declaration_v2(
        {
            "contract": "KernelAdoptionDeclaration.v2",
            "applicability": "applicable",
            "declared_at": "2026-09-01",
            "source_predecessor": "2" * 40,
            "kernel_catalogue": {
                "version": "0.1.0a103",
                "revision": "a" * 40,
                "artifact_digest": "sha256:" + "b" * 64,
                "catalogue_digest": catalogue_digest(
                    version=catalogue.version,
                    revision=catalogue.revision,
                    supported=catalogue.supported,
                    internal=catalogue.internal,
                    root_exports=catalogue.root_exports,
                ),
            },
            "source_surface": {
                "algorithm": "dmg-kernel-surface-v2",
                "digest": source_digest,
            },
            "required_surfaces": [],
            "prohibited_surfaces": [],
            "transitional_surfaces": [],
        }
    )
    report = evaluate(
        KernelAdoptionInputs(
            sources=sources,
            catalogue=catalogue,
            declaration=DeclarationPresent(declaration),
            as_of=__import__("datetime").date(2026, 9, 2),
            pin_sites=(),
            predecessor=None,
        )
    )
    assert FindingCode.MODULE_SYMBOL_UNEXPORTED in {
        item.code for item in report.findings
    }


def test_alias_attribute_is_refused_against_trusted_exports() -> None:
    catalogue = trusted_surface_catalogue(observed(), trusted_store())
    assert catalogue is not None
    # The engine's import pass sees the module; the attribute pass must not
    # lose SessionLocal merely because the product called the module ``d``.
    tree = ast.parse("import dotmac_kernel.db as d\nd.SessionLocal\n")
    findings = _check_module_alias_attributes(PurePosixPath("x.py"), tree, catalogue)
    assert [item.code for item in findings] == [FindingCode.MODULE_SYMBOL_UNEXPORTED]


def test_root_import_alias_paths_refuse_private_and_admit_public() -> None:
    catalogue = trusted_surface_catalogue(observed(), trusted_store())
    assert catalogue is not None
    private_from = ast.parse("from dotmac_kernel import db as d\nd.SessionLocal\n")
    private_root = ast.parse("import dotmac_kernel as k\nk.db.SessionLocal\n")
    public = ast.parse("import dotmac_kernel.db\ndotmac_kernel.db.DatabaseRuntime\n")
    for tree in (private_from, private_root):
        assert [
            item.code
            for item in _check_module_alias_attributes(
                PurePosixPath("x.py"), tree, catalogue
            )
        ] == [FindingCode.MODULE_SYMBOL_UNEXPORTED]
    assert (
        _check_module_alias_attributes(PurePosixPath("x.py"), public, catalogue) == []
    )


def test_nested_kernel_import_paths_are_explicitly_unmeasured() -> None:
    catalogue = trusted_surface_catalogue(observed(), trusted_store())
    assert catalogue is not None
    nested_function = ast.parse(
        "def use():\n    from dotmac_kernel import db as d\n    d.SessionLocal\n"
    )
    nested_if = ast.parse(
        "if enabled:\n    import dotmac_kernel as k\n    k.db.SessionLocal\n"
    )
    for tree in (nested_function, nested_if):
        assert [
            item.code
            for item in _check_module_alias_attributes(
                PurePosixPath("x.py"), tree, catalogue
            )
        ] == [FindingCode.MODULE_ATTRIBUTE_UNMEASURED]


def test_a102_legacy_near_miss_keeps_existing_catalogue_path() -> None:
    legacy = KernelSurfaceCatalogue(
        "a" * 40, "0.1.0a102", frozenset({"dotmac_kernel.db"}), frozenset()
    )
    assert trusted_surface_catalogue(legacy, TrustedCatalogueStore()) is legacy


def test_store_reads_only_governance_owned_pair_paths(tmp_path: Path) -> None:
    record, exports = pair()
    root = tmp_path / "inventories"
    (root / "kernel-release-verifications").mkdir(parents=True)
    (root / "kernel-public-exports").mkdir()
    (root / "kernel-release-verifications" / "0.1.0a103.json").write_bytes(record)
    (root / "kernel-public-exports" / "0.1.0a103.json").write_bytes(exports)
    assert (
        TrustedCatalogueStore(evidence_root=root).resolve("0.1.0a103").revision
        == "a" * 40
    )


def test_release_resource_hash_and_duplicate_keys_refuse() -> None:
    record, exports = pair()
    with pytest.raises(TrustedCatalogueError, match="size|digest"):
        load_trusted_catalogue(
            record, exports.replace(b"DatabaseRuntime", b"SessionLocal____")
        )
    with pytest.raises(TrustedCatalogueError, match="duplicate"):
        load_trusted_catalogue(record, b'{"schema":"x","schema":"x"}\n')


def test_empty_and_non_kernel_catalogues_refuse_with_matching_digest() -> None:
    record, exports = pair()
    evidence = json.loads(record)
    document = json.loads(exports)
    plants = (
        ({}, [], "module entries"),
        (
            {
                "evil": {
                    "classification": "supported",
                    "status": "declared",
                    "exports": [],
                }
            },
            ["evil"],
            "not a Kernel module",
        ),
    )
    for modules, supported, expected in plants:
        document["modules"] = modules
        document["supported_modules"] = supported
        altered = canonical(document, indent=2)
        evidence["public_exports"]["size"] = len(altered)
        evidence["public_exports"]["sha256"] = hashlib.sha256(altered).hexdigest()
        with pytest.raises(TrustedCatalogueError, match=expected):
            load_trusted_catalogue(canonical(evidence), altered)
