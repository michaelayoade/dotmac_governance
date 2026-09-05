"""Closed, pure parsing and comparison for ADR 0017 retirement declarations.

This module deliberately consumes supplied evidence.  It neither opens a
database nor resolves a workflow run: target collection and authorization stay
with the product and its named authorization system.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath

from .contracts import (
    AuthorityId,
    CatalogueRetirementEdge,
    CompatibilityRetirement,
    PythonSymbol,
    RetirementHistory,
    SourceReference,
    StaticRetirementEdge,
)

_SLUG = re.compile(r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
HTTPS_REPOSITORY = re.compile(r"^https://[^/\s]+/[^/\s]+/[^/\s]+$")
_SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
_STATIC_KINDS = frozenset(
    {
        "local_decision_writer",
        "compatibility_writer",
        "reverse_feed",
        "fallback_writer",
        "reader",
        "caller",
        "import",
        "orm_relationship",
        "dependency",
        "repair_job",
        "refresh_job",
        "consumer",
    }
)
_CATALOGUE_KINDS = frozenset(
    {
        "foreign_key",
        "constraint",
        "trigger",
        "grant",
        "column_grant",
        "dependent_relation",
        "function",
        "refresh_object",
        "other_dependency",
    }
)
_EXIT_KINDS = frozenset(
    {"archival", "external_clients", "old_process_drain", "restart_prevention"}
)
_CHECK_IDS = frozenset(
    {
        "source_edges_zero",
        "consumers_zero",
        "writers_absent_or_exact_teardown",
        "catalogue_matches_reviewed_teardown",
        "projection_fixed_point",
        "archival_exit_settled",
        "external_clients_exited",
        "old_processes_drained",
        "old_process_restart_prevented",
        "deletion_lineage_owned",
        "exclusive_nowait_fences_held",
        "inventory_rechecked_under_fence",
        "teardown_in_dependency_order",
        "drop_restrict_used",
        "failure_rolls_back_without_partial_teardown",
        "post_upgrade_objects_absent",
        "owner_paths_pass_without_fallback",
        "intended_revision_running",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$")


class RetirementError(ValueError):
    """A closed retirement declaration was malformed."""


@dataclass(frozen=True)
class Artifact:
    name: str
    sha256: str
    path: PurePosixPath


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    outcome: str
    evidence_selector: str


@dataclass(frozen=True)
class ProductTransactionAttempt:
    scenario: str
    transaction_outcome: str
    refusal_stage: str
    catalogue_coverage: str
    catalogue_edges: tuple[CatalogueRetirementEdge, ...]
    checks: tuple[CheckResult, ...]


@dataclass(frozen=True)
class ProductRevisionEvidence:
    repository: str
    commit: str
    governance_revision: str
    run_id: int
    run_attempt: int
    artifact: Artifact
    collector: SourceReference
    observed_at: str
    catalogue_coverage: str
    catalogue_edges: tuple[CatalogueRetirementEdge, ...]
    checks: tuple[CheckResult, ...]
    transaction_attempts: tuple[ProductTransactionAttempt, ...]


@dataclass(frozen=True)
class TargetRetirementEvidence:
    repository: str
    commit: str
    governance_revision: str
    run_id: int
    run_attempt: int
    image_digest: str
    target: str
    phase: str
    transaction_outcome: str | None
    refusal_stage: str | None
    observation_id: str
    preceding_observation_id: str | None
    deletion_migration: SourceReference
    artifact: Artifact
    observed_at: str
    refresh_owner: str
    refresh_before: str
    catalogue_coverage: str
    catalogue_edges: tuple[CatalogueRetirementEdge, ...]
    checks: tuple[CheckResult, ...]


@dataclass(frozen=True)
class RetirementObservation:
    retirement_id: str
    source_coverage: str
    measured_kinds: tuple[str, ...]
    static_edges: tuple[StaticRetirementEdge, ...]
    canonical_decision_writers: tuple[SourceReference, ...]
    unavailable_regions: tuple[PurePosixPath, ...]
    migration_database: ProductRevisionEvidence | None
    deployed_target: tuple[TargetRetirementEvidence, ...]


@dataclass(frozen=True)
class RetirementObservationBundle:
    repository: str
    product_revision: str
    governance_revision: str
    producer_id: str
    normalization_version: str
    observations: tuple[RetirementObservation, ...]


def _object(value: object, location: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise RetirementError(f"{location} must be an object")
    return value


def _array(value: object, location: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise RetirementError(f"{location} must be an array")
    return value


def _keys(data: Mapping[str, object], expected: frozenset[str], location: str) -> None:
    missing = sorted(expected - data.keys())
    unknown = sorted(data.keys() - expected)
    if missing:
        raise RetirementError(f"{location} missing keys: {', '.join(missing)}")
    if unknown:
        raise RetirementError(f"{location} has unknown keys: {', '.join(unknown)}")


def _string(value: object, location: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise RetirementError(f"{location} must be a non-empty safe string")
    return value.strip()


def _slug(value: object, location: str) -> str:
    result = _string(value, location)
    if not _SLUG.fullmatch(result):
        raise RetirementError(f"{location} must be a stable slug")
    return result


def _path(value: object, location: str) -> PurePosixPath:
    raw = _string(value, location)
    result = PurePosixPath(raw)
    if result.is_absolute() or ".." in result.parts or raw == ".":
        raise RetirementError(f"{location} must be a repository-relative path")
    return result


def _source(value: object, location: str) -> SourceReference:
    data = _object(value, location)
    kind = _string(data.get("kind"), f"{location}.kind")
    if kind == "python_symbol":
        _keys(data, frozenset({"kind", "path", "symbol"}), location)
        member = _string(data["symbol"], f"{location}.symbol")
        if not _SYMBOL.fullmatch(member):
            raise RetirementError(
                f"{location}.symbol must be a qualified Python symbol"
            )
    elif kind == "document_section":
        _keys(data, frozenset({"kind", "path", "anchor"}), location)
        member = _string(data["anchor"], f"{location}.anchor")
    else:
        raise RetirementError(
            f"{location}.kind must be python_symbol or document_section"
        )
    return SourceReference(kind, _path(data["path"], f"{location}.path"), member)


def _edge(value: object, location: str) -> StaticRetirementEdge:
    data = _object(value, location)
    _keys(
        data,
        frozenset({"kind", "path", "symbol", "target", "fingerprint", "consumer_id"}),
        location,
    )
    kind = _string(data["kind"], f"{location}.kind")
    if kind not in _STATIC_KINDS:
        raise RetirementError(f"{location}.kind is not a static edge kind")
    symbol = _string(data["symbol"], f"{location}.symbol")
    fingerprint = _string(data["fingerprint"], f"{location}.fingerprint")
    if not _SYMBOL.fullmatch(symbol) or not _SHA.fullmatch(fingerprint):
        raise RetirementError(
            f"{location} has an invalid symbol or SHA-256 fingerprint"
        )
    consumer_id = data["consumer_id"]
    if consumer_id is not None:
        consumer_id = _slug(consumer_id, f"{location}.consumer_id")
    return StaticRetirementEdge(
        kind,
        _path(data["path"], f"{location}.path"),
        PythonSymbol(symbol),
        _string(data["target"], f"{location}.target"),
        fingerprint,
        consumer_id,
    )


def _catalogue(value: object, location: str) -> CatalogueRetirementEdge:
    data = _object(value, location)
    _keys(data, frozenset({"kind", "identity", "definition_sha256"}), location)
    kind = _string(data["kind"], f"{location}.kind")
    digest = _string(data["definition_sha256"], f"{location}.definition_sha256")
    if kind not in _CATALOGUE_KINDS or not _SHA.fullmatch(digest):
        raise RetirementError(f"{location} has an invalid catalogue kind or SHA-256")
    return CatalogueRetirementEdge(
        kind, _string(data["identity"], f"{location}.identity"), digest
    )


def _artifact(value: object, location: str) -> Artifact:
    data = _object(value, location)
    _keys(data, frozenset({"name", "sha256", "path"}), location)
    digest = _string(data["sha256"], f"{location}.sha256")
    if not _SHA.fullmatch(digest):
        raise RetirementError(f"{location}.sha256 must be a lower-case SHA-256")
    return Artifact(
        _string(data["name"], f"{location}.name"),
        digest,
        _path(data["path"], f"{location}.path"),
    )


def _check_result(value: object, location: str) -> CheckResult:
    data = _object(value, location)
    _keys(data, frozenset({"check_id", "outcome", "evidence_selector"}), location)
    check_id = _string(data["check_id"], f"{location}.check_id")
    if check_id not in _CHECK_IDS:
        raise RetirementError(f"{location}.check_id is not a declared check")
    evidence_selector = _string(
        data["evidence_selector"], f"{location}.evidence_selector"
    )
    if not _SAFE_ID.fullmatch(evidence_selector):
        raise RetirementError(f"{location}.evidence_selector is unsafe")
    outcome = _string(data["outcome"], f"{location}.outcome")
    if outcome not in {"pass", "fail", "unknown"}:
        raise RetirementError(f"{location}.outcome must be pass, fail, or unknown")
    return CheckResult(
        check_id,
        outcome,
        evidence_selector,
    )


def _positive(value: object, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RetirementError(f"{location} must be a positive integer")
    return value


def _product_transaction_attempt(
    value: object, location: str
) -> ProductTransactionAttempt:
    data = _object(value, location)
    _keys(
        data,
        frozenset(
            {
                "scenario",
                "transaction_outcome",
                "refusal_stage",
                "catalogue_coverage",
                "catalogue_edges",
                "checks",
            }
        ),
        location,
    )
    scenario = _string(data["scenario"], f"{location}.scenario")
    stages = {
        "lock_contention": "fence_acquisition",
        "inventory_mismatch": "inventory_validation",
        "drop_restrict_dependency": "teardown",
    }
    if (
        scenario not in stages
        or _string(data["refusal_stage"], f"{location}.refusal_stage")
        != stages[scenario]
    ):
        raise RetirementError(f"{location} scenario/refusal stage mismatch")
    outcome = _string(data["transaction_outcome"], f"{location}.transaction_outcome")
    if outcome not in {"refused", "rolled_back"}:
        raise RetirementError(
            f"{location}.transaction_outcome must refuse or roll back"
        )
    coverage = _string(data["catalogue_coverage"], f"{location}.catalogue_coverage")
    if coverage not in {"measured", "unmeasured"}:
        raise RetirementError(f"{location}.catalogue_coverage is invalid")
    edges = tuple(
        _catalogue(item, f"{location}.catalogue_edges[{index}]")
        for index, item in enumerate(
            _array(data["catalogue_edges"], f"{location}.catalogue_edges")
        )
    )
    checks = tuple(
        _check_result(item, f"{location}.checks[{index}]")
        for index, item in enumerate(_array(data["checks"], f"{location}.checks"))
    )
    if coverage == "unmeasured" and edges:
        raise RetirementError(
            f"{location} unmeasured catalogue coverage cannot carry edges"
        )
    expected_coverage = "unmeasured" if scenario == "lock_contention" else "measured"
    if coverage != expected_coverage:
        raise RetirementError(f"{location} catalogue coverage does not match scenario")
    if len({item.key for item in edges}) != len(edges) or len(
        {item.check_id for item in checks}
    ) != len(checks):
        raise RetirementError(f"{location} identities must be unique")
    return ProductTransactionAttempt(
        scenario, outcome, stages[scenario], coverage, edges, checks
    )


def _product_revision_evidence(value: object, location: str) -> ProductRevisionEvidence:
    data = _object(value, location)
    _keys(
        data,
        frozenset(
            {
                "kind",
                "repository",
                "commit",
                "governance_revision",
                "run_id",
                "run_attempt",
                "artifact",
                "collector",
                "observed_at",
                "catalogue_coverage",
                "catalogue_edges",
                "checks",
                "transaction_attempts",
            }
        ),
        location,
    )
    if _string(data["kind"], f"{location}.kind") != "product_revision_check":
        raise RetirementError(f"{location}.kind must be product_revision_check")
    repository = _string(data["repository"], f"{location}.repository")
    commit = _string(data["commit"], f"{location}.commit")
    governance = _string(data["governance_revision"], f"{location}.governance_revision")
    if (
        not HTTPS_REPOSITORY.fullmatch(repository)
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not re.fullmatch(r"[0-9a-f]{40}", governance)
    ):
        raise RetirementError(f"{location} has invalid immutable coordinates")
    observed_at = _string(data["observed_at"], f"{location}.observed_at")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", observed_at):
        raise RetirementError(f"{location}.observed_at must be RFC3339 UTC-Z")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise RetirementError(
            f"{location}.observed_at must be a real UTC timestamp"
        ) from error
    coverage = _string(data["catalogue_coverage"], f"{location}.catalogue_coverage")
    if coverage not in {"measured", "unmeasured"}:
        raise RetirementError(f"{location}.catalogue_coverage is invalid")
    edges = tuple(
        _catalogue(item, f"{location}.catalogue_edges[{index}]")
        for index, item in enumerate(
            _array(data["catalogue_edges"], f"{location}.catalogue_edges")
        )
    )
    checks = tuple(
        _check_result(item, f"{location}.checks[{index}]")
        for index, item in enumerate(_array(data["checks"], f"{location}.checks"))
    )
    attempts = tuple(
        _product_transaction_attempt(item, f"{location}.transaction_attempts[{index}]")
        for index, item in enumerate(
            _array(data["transaction_attempts"], f"{location}.transaction_attempts")
        )
    )
    if coverage == "unmeasured" and edges:
        raise RetirementError(
            f"{location} unmeasured catalogue coverage cannot carry edges"
        )
    if (
        len({item.key for item in edges}) != len(edges)
        or len({item.check_id for item in checks}) != len(checks)
        or {item.scenario for item in attempts}
        != {"lock_contention", "inventory_mismatch", "drop_restrict_dependency"}
        or len(attempts) != 3
    ):
        raise RetirementError(
            f"{location} has duplicate or incomplete evidence identities"
        )
    return ProductRevisionEvidence(
        repository,
        commit,
        governance,
        _positive(data["run_id"], f"{location}.run_id"),
        _positive(data["run_attempt"], f"{location}.run_attempt"),
        _artifact(data["artifact"], f"{location}.artifact"),
        _source(data["collector"], f"{location}.collector"),
        observed_at,
        coverage,
        edges,
        checks,
        attempts,
    )


def _target_retirement_evidence(
    value: object, location: str
) -> TargetRetirementEvidence:
    data = _object(value, location)
    required = frozenset(
        {
            "kind",
            "repository",
            "commit",
            "governance_revision",
            "run_id",
            "run_attempt",
            "image_digest",
            "target",
            "phase",
            "transaction_outcome",
            "refusal_stage",
            "observation_id",
            "preceding_observation_id",
            "deletion_migration",
            "artifact",
            "observed_at",
            "refresh_owner",
            "refresh_before",
            "catalogue_coverage",
            "catalogue_edges",
            "checks",
        }
    )
    _keys(data, required, location)
    if _string(data["kind"], f"{location}.kind") != "target_retirement_observation":
        raise RetirementError(f"{location}.kind is invalid")
    phase = _string(data["phase"], f"{location}.phase")
    expected_refresh = {
        "pre_drop": "cutover_authorization",
        "atomic_teardown": "fenced_teardown",
        "post_upgrade": "completion_claim",
    }
    if (
        phase not in expected_refresh
        or _string(data["refresh_before"], f"{location}.refresh_before")
        != expected_refresh[phase]
    ):
        raise RetirementError(f"{location} phase/refresh mapping is invalid")
    outcome_raw = data["transaction_outcome"]
    refusal_raw = data["refusal_stage"]
    if phase == "atomic_teardown":
        if not isinstance(outcome_raw, str) or outcome_raw not in {
            "committed",
            "refused",
            "rolled_back",
        }:
            raise RetirementError(f"{location} atomic outcome is invalid")
        if outcome_raw == "committed" and refusal_raw is not None:
            raise RetirementError(f"{location} committed atomic record cannot refuse")
        if outcome_raw in {"refused", "rolled_back"}:
            if not isinstance(refusal_raw, str) or refusal_raw not in {
                "fence_acquisition",
                "inventory_validation",
                "teardown",
            }:
                raise RetirementError(
                    f"{location} refused atomic record needs a refusal stage"
                )
        elif refusal_raw is not None:
            raise RetirementError(f"{location} committed atomic record cannot refuse")
    elif outcome_raw is not None or refusal_raw is not None:
        raise RetirementError(
            f"{location} non-atomic phase cannot have transaction fields"
        )
    preceding = data["preceding_observation_id"]
    if (phase == "pre_drop") != (preceding is None):
        raise RetirementError(f"{location} preceding observation is invalid for phase")
    digest = _string(data["image_digest"], f"{location}.image_digest")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RetirementError(f"{location}.image_digest is invalid")
    coverage = _string(data["catalogue_coverage"], f"{location}.catalogue_coverage")
    if coverage not in {"measured", "unmeasured"}:
        raise RetirementError(f"{location}.catalogue_coverage is invalid")
    edges = tuple(
        _catalogue(item, f"{location}.catalogue_edges[{index}]")
        for index, item in enumerate(
            _array(data["catalogue_edges"], f"{location}.catalogue_edges")
        )
    )
    checks = tuple(
        _check_result(item, f"{location}.checks[{index}]")
        for index, item in enumerate(_array(data["checks"], f"{location}.checks"))
    )
    if coverage == "unmeasured" and edges:
        raise RetirementError(
            f"{location} unmeasured catalogue coverage cannot carry edges"
        )
    if phase == "pre_drop" or outcome_raw == "committed":
        expected_coverage = "measured"
    elif refusal_raw == "fence_acquisition":
        expected_coverage = "unmeasured"
    else:
        expected_coverage = "measured"
    if coverage != expected_coverage:
        raise RetirementError(f"{location} catalogue coverage does not match phase")
    if len({item.key for item in edges}) != len(edges) or len(
        {item.check_id for item in checks}
    ) != len(checks):
        raise RetirementError(f"{location} identities must be unique")
    repository = _string(data["repository"], f"{location}.repository")
    commit = _string(data["commit"], f"{location}.commit")
    governance = _string(data["governance_revision"], f"{location}.governance_revision")
    observed_at = _string(data["observed_at"], f"{location}.observed_at")
    if not HTTPS_REPOSITORY.fullmatch(repository):
        raise RetirementError(f"{location}.repository is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not re.fullmatch(
        r"[0-9a-f]{40}", governance
    ):
        raise RetirementError(f"{location} has invalid immutable coordinates")
    if not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", observed_at):
        raise RetirementError(f"{location}.observed_at must be RFC3339 UTC-Z")
    try:
        datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise RetirementError(
            f"{location}.observed_at must be a real UTC timestamp"
        ) from error
    if not isinstance(outcome_raw, (str, type(None))) or not isinstance(
        refusal_raw, (str, type(None))
    ):
        raise RetirementError(f"{location} transaction fields must be strings or null")
    return TargetRetirementEvidence(
        repository,
        commit,
        governance,
        _positive(data["run_id"], f"{location}.run_id"),
        _positive(data["run_attempt"], f"{location}.run_attempt"),
        digest,
        _string(data["target"], f"{location}.target"),
        phase,
        outcome_raw,
        refusal_raw,
        _slug(data["observation_id"], f"{location}.observation_id"),
        None
        if preceding is None
        else _slug(preceding, f"{location}.preceding_observation_id"),
        _source(data["deletion_migration"], f"{location}.deletion_migration"),
        _artifact(data["artifact"], f"{location}.artifact"),
        observed_at,
        _string(data["refresh_owner"], f"{location}.refresh_owner"),
        expected_refresh[phase],
        coverage,
        edges,
        checks,
    )


def _unique[T](values: tuple[T, ...], location: str) -> tuple[T, ...]:
    if len(set(values)) != len(values):
        raise RetirementError(f"{location} must not contain duplicates")
    return values


def _immutable_record(
    value: object, location: str
) -> tuple[str, str, PurePosixPath, str]:
    data = _object(value, location)
    _keys(data, frozenset({"repository", "commit", "path", "sha256"}), location)
    repository = _string(data["repository"], f"{location}.repository")
    commit = _string(data["commit"], f"{location}.commit")
    digest = _string(data["sha256"], f"{location}.sha256")
    if not HTTPS_REPOSITORY.fullmatch(repository) or not re.fullmatch(
        r"[0-9a-f]{40}", commit
    ):
        raise RetirementError(f"{location} has invalid immutable coordinates")
    if not _SHA.fullmatch(digest):
        raise RetirementError(f"{location}.sha256 must be a lower-case SHA-256")
    return repository, commit, _path(data["path"], f"{location}.path"), digest


def _schema_relation(value: object, location: str) -> str:
    result = _string(value, location)
    parts = result.split(".")
    if len(parts) != 2 or any(
        not part or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) for part in parts
    ):
        raise RetirementError(f"{location} must be schema-qualified")
    return result


def _retirement(value: object, index: int) -> CompatibilityRetirement:
    location = f"compatibility_retirements[{index}]"
    data = _object(value, location)
    expected = frozenset(
        {
            "retirement_id",
            "authority_transition",
            "accountable_owner",
            "relation",
            "disposition",
            "source_state",
            "requested_gate",
            "consumers",
            "static_baseline",
            "catalogue_baseline",
            "collector",
            "deletion",
            "external_exit_conditions",
        }
    )
    _keys(data, expected, location)
    relation = _object(data["relation"], f"{location}.relation")
    _keys(
        relation,
        frozenset({"kind", "identity", "owner_lineage"}),
        f"{location}.relation",
    )
    relation_kind = _string(relation["kind"], f"{location}.relation.kind")
    if relation_kind not in {
        "table",
        "view",
        "materialized_view",
        "cache",
        "read_model",
    }:
        raise RetirementError(f"{location}.relation.kind is not supported")
    identity = _string(relation["identity"], f"{location}.relation.identity")
    if relation_kind in {"table", "view", "materialized_view"} and "." not in identity:
        raise RetirementError(f"{location}.relation.identity must be schema-qualified")
    transition = _object(
        data["authority_transition"], f"{location}.authority_transition"
    )
    state = _string(transition.get("state"), f"{location}.authority_transition.state")
    if state == "legacy_active":
        _keys(
            transition,
            frozenset(
                {
                    "state",
                    "current_authority_id",
                    "current_writer",
                    "target_module_authority_id",
                }
            ),
            f"{location}.authority_transition",
        )
        displaced: AuthorityId | None = None
        target = AuthorityId(
            _slug(
                transition["target_module_authority_id"],
                f"{location}.authority_transition.target_module_authority_id",
            )
        )
    elif state == "module_active":
        _keys(
            transition,
            frozenset(
                {
                    "state",
                    "current_authority_id",
                    "current_writer",
                    "displaced_authority",
                    "activation_record",
                }
            ),
            f"{location}.authority_transition",
        )
        displaced_data = _object(
            transition["displaced_authority"],
            f"{location}.authority_transition.displaced_authority",
        )
        _keys(
            displaced_data,
            frozenset({"authority_id", "writer", "historical_profile"}),
            f"{location}.authority_transition.displaced_authority",
        )
        displaced = AuthorityId(
            _slug(
                displaced_data["authority_id"],
                f"{location}.authority_transition.displaced_authority.authority_id",
            )
        )
        _source(
            displaced_data["writer"],
            f"{location}.authority_transition.displaced_authority.writer",
        )
        historical = _object(
            displaced_data["historical_profile"],
            f"{location}.authority_transition.displaced_authority.historical_profile",
        )
        _keys(
            historical,
            frozenset({"repository", "commit", "path", "sha256"}),
            f"{location}.authority_transition.displaced_authority.historical_profile",
        )
        _immutable_record(
            historical,
            f"{location}.authority_transition.displaced_authority.historical_profile",
        )
        target = None
    else:
        raise RetirementError(
            f"{location}.authority_transition.state must be legacy_active "
            "or module_active"
        )
    current = AuthorityId(
        _slug(
            transition["current_authority_id"],
            f"{location}.authority_transition.current_authority_id",
        )
    )
    writer = _source(
        transition["current_writer"], f"{location}.authority_transition.current_writer"
    )
    source_state = _string(data["source_state"], f"{location}.source_state")
    gate = _string(data["requested_gate"], f"{location}.requested_gate")
    if source_state not in {"draining", "drained"} or gate not in {
        "none",
        "pre_drop",
        "post_upgrade",
    }:
        raise RetirementError(
            f"{location} has an invalid source_state or requested_gate"
        )
    if (source_state == "drained" or gate != "none") and state != "module_active":
        raise RetirementError(
            f"{location} requires module_active authority for drained state "
            "or a requested gate"
        )
    if state == "module_active":
        if displaced == current:
            raise RetirementError(
                f"{location}.displaced_authority must differ from current authority"
            )
        activation_location = f"{location}.authority_transition.activation_record"
        activation = _object(transition["activation_record"], activation_location)
        _keys(
            activation,
            frozenset(
                {
                    "repository",
                    "commit",
                    "path",
                    "sha256",
                    "retirement_id",
                    "relation_identity",
                }
            ),
            activation_location,
        )
        _immutable_record(
            {
                key: activation[key]
                for key in ("repository", "commit", "path", "sha256")
            },
            activation_location,
        )
        if (
            _slug(activation["retirement_id"], f"{activation_location}.retirement_id")
            != _slug(data["retirement_id"], f"{location}.retirement_id")
            or _string(
                activation["relation_identity"],
                f"{activation_location}.relation_identity",
            )
            != identity
        ):
            raise RetirementError(
                f"{location}.activation_record does not match retirement"
            )
    disposition = _object(data["disposition"], f"{location}.disposition")
    kind = _string(disposition.get("kind"), f"{location}.disposition.kind")
    authority: AuthorityId | None = None
    projection_kind: str | None = None
    projection_writer: SourceReference | None = None
    if kind == "delete":
        _keys(disposition, frozenset({"kind"}), f"{location}.disposition")
    elif kind == "migrate_to_module":
        _keys(
            disposition,
            frozenset({"kind", "module_authority_id"}),
            f"{location}.disposition",
        )
        authority = AuthorityId(
            _slug(
                disposition["module_authority_id"],
                f"{location}.disposition.module_authority_id",
            )
        )
        expected_authority = target if state == "legacy_active" else current
        if authority != expected_authority:
            raise RetirementError(
                f"{location}.migrate_to_module authority does not match transition"
            )
    elif kind == "retain_product_record":
        _keys(
            disposition,
            frozenset({"kind", "authority_id", "reason"}),
            f"{location}.disposition",
        )
        authority = AuthorityId(
            _slug(disposition["authority_id"], f"{location}.disposition.authority_id")
        )
        _string(disposition["reason"], f"{location}.disposition.reason")
    elif kind == "temporary_projection":
        _keys(disposition, frozenset({"kind", "projection"}), f"{location}.disposition")
        projection = _object(
            disposition["projection"], f"{location}.disposition.projection"
        )
        projection_kind = _string(
            projection.get("kind"), f"{location}.disposition.projection.kind"
        )
        required = {
            "kind",
            "derivation",
            "provenance",
            "freshness",
            "retirement_condition",
        }
        if projection_kind == "stored":
            required |= {"canonical_writer", "drift_invariant", "repair_path"}
            projection_writer = _source(
                projection["canonical_writer"],
                f"{location}.disposition.projection.canonical_writer",
            )
        elif projection_kind != "ordinary_view":
            raise RetirementError(f"{location}.disposition.projection.kind is invalid")
        _keys(projection, frozenset(required), f"{location}.disposition.projection")
        for field in ("derivation", "provenance", "freshness", "retirement_condition"):
            _string(
                projection[field],
                f"{location}.disposition.projection.{field}",
            )
        if projection_kind == "stored":
            _string(
                projection["drift_invariant"],
                f"{location}.disposition.projection.drift_invariant",
            )
            _path(
                projection["repair_path"],
                f"{location}.disposition.projection.repair_path",
            )
    else:
        raise RetirementError(f"{location}.disposition.kind is invalid")
    deletion = data["deletion"]
    deletion_migration: SourceReference | None = None
    deletion_owner: str | None = None
    teardown: tuple[CatalogueRetirementEdge, ...] = ()
    fences: tuple[str, ...] = ()
    if deletion is not None:
        deletion_data = _object(deletion, f"{location}.deletion")
        _keys(
            deletion_data,
            frozenset(
                {"migration", "owner_lineage", "teardown_set", "fence_relations"}
            ),
            f"{location}.deletion",
        )
        deletion_migration = _source(
            deletion_data["migration"], f"{location}.deletion.migration"
        )
        deletion_owner = _slug(
            deletion_data["owner_lineage"], f"{location}.deletion.owner_lineage"
        )
        teardown = tuple(
            _catalogue(item, f"{location}.deletion.teardown_set[{number}]")
            for number, item in enumerate(
                _array(
                    deletion_data["teardown_set"], f"{location}.deletion.teardown_set"
                )
            )
        )
        if len({item.key for item in teardown}) != len(teardown):
            raise RetirementError(
                f"{location}.deletion.teardown_set identities must be unique"
            )
        fences = _unique(
            tuple(
                _schema_relation(item, f"{location}.deletion.fence_relations[{number}]")
                for number, item in enumerate(
                    _array(
                        deletion_data["fence_relations"],
                        f"{location}.deletion.fence_relations",
                    )
                )
            ),
            f"{location}.deletion.fence_relations",
        )
        if not fences or identity not in fences:
            raise RetirementError(
                f"{location}.deletion.fence_relations must include the "
                "compatibility relation"
            )
    if (kind == "retain_product_record") != (deletion is None):
        raise RetirementError(f"{location}.disposition and deletion contract disagree")
    consumer_values: list[str] = []
    consumer_blockers: list[SourceReference] = []
    for number, raw in enumerate(_array(data["consumers"], f"{location}.consumers")):
        consumer_location = f"{location}.consumers[{number}]"
        consumer = _object(raw, consumer_location)
        _keys(
            consumer,
            frozenset({"consumer_id", "need", "blocked_by"}),
            consumer_location,
        )
        consumer_values.append(
            _slug(consumer["consumer_id"], f"{consumer_location}.consumer_id")
        )
        _string(consumer["need"], f"{consumer_location}.need")
        consumer_blockers.append(
            _source(consumer["blocked_by"], f"{consumer_location}.blocked_by")
        )
    consumers = _unique(tuple(consumer_values), f"{location}.consumers")
    static = tuple(
        _edge(item, f"{location}.static_baseline[{number}]")
        for number, item in enumerate(
            _array(data["static_baseline"], f"{location}.static_baseline")
        )
    )
    catalogue = tuple(
        _catalogue(item, f"{location}.catalogue_baseline[{number}]")
        for number, item in enumerate(
            _array(data["catalogue_baseline"], f"{location}.catalogue_baseline")
        )
    )
    if len({edge.identity for edge in static}) != len(static) or len(
        {edge.key for edge in catalogue}
    ) != len(catalogue):
        raise RetirementError(f"{location} baseline identities must be unique")
    declared_consumers = set(consumers)
    edge_consumers = {edge.consumer_id for edge in static if edge.kind == "consumer"}
    if any(edge.kind == "consumer" and edge.consumer_id is None for edge in static):
        raise RetirementError(
            f"{location}.static_baseline consumer edges require consumer_id"
        )
    if edge_consumers != declared_consumers:
        raise RetirementError(f"{location} consumer declarations and edges must match")
    exits = _array(
        data["external_exit_conditions"], f"{location}.external_exit_conditions"
    )
    exit_values: list[tuple[str, str]] = []
    exit_ids: list[str] = []
    for number, raw in enumerate(exits):
        item = _object(raw, f"{location}.external_exit_conditions[{number}]")
        status = _string(
            item.get("status"), f"{location}.external_exit_conditions[{number}].status"
        )
        exit_kind = _string(
            item.get("kind"), f"{location}.external_exit_conditions[{number}].kind"
        )
        expected_exit = frozenset(
            {
                "condition_id",
                "kind",
                "status",
                "accountable_owner",
                "requirement" if status == "required" else "rationale",
            }
        )
        _keys(item, expected_exit, f"{location}.external_exit_conditions[{number}]")
        if exit_kind not in _EXIT_KINDS or status not in {"required", "not_applicable"}:
            raise RetirementError(
                f"{location}.external_exit_conditions[{number}] is invalid"
            )
        exit_ids.append(
            _slug(
                item["condition_id"],
                f"{location}.external_exit_conditions[{number}].condition_id",
            )
        )
        _string(
            item["accountable_owner"],
            f"{location}.external_exit_conditions[{number}].accountable_owner",
        )
        exit_field = "requirement" if status == "required" else "rationale"
        _string(
            item[exit_field],
            f"{location}.external_exit_conditions[{number}].{exit_field}",
        )
        exit_values.append((exit_kind, status))
    if (
        {kind for kind, _ in exit_values} != _EXIT_KINDS
        or len(exit_values) != 4
        or len(set(exit_ids)) != 4
    ):
        raise RetirementError(
            f"{location}.external_exit_conditions must cover each required kind once"
        )
    collector = _object(data["collector"], f"{location}.collector")
    _keys(
        collector,
        frozenset({"source", "workflow_path", "producer_id", "normalization_version"}),
        f"{location}.collector",
    )
    normalization = _string(
        collector["normalization_version"],
        f"{location}.collector.normalization_version",
    )
    _path(collector["workflow_path"], f"{location}.collector.workflow_path")
    _slug(collector["producer_id"], f"{location}.collector.producer_id")
    if normalization != "python-ast-v1":
        raise RetirementError(
            f"{location}.collector.normalization_version must be python-ast-v1"
        )
    return CompatibilityRetirement(
        _slug(data["retirement_id"], f"{location}.retirement_id"),
        relation_kind,
        identity,
        _slug(relation["owner_lineage"], f"{location}.relation.owner_lineage"),
        state,
        current,
        writer,
        target,
        displaced,
        _string(data["accountable_owner"], f"{location}.accountable_owner"),
        kind,
        authority,
        projection_kind,
        projection_writer,
        source_state,
        gate,
        _unique(consumers, f"{location}.consumers"),
        tuple(consumer_blockers),
        static,
        catalogue,
        _source(collector["source"], f"{location}.collector.source"),
        _path(collector["workflow_path"], f"{location}.collector.workflow_path"),
        _slug(collector["producer_id"], f"{location}.collector.producer_id"),
        normalization,
        deletion_migration,
        deletion_owner,
        teardown,
        fences,
        tuple(exit_values),
    )


def parse_retirements(
    retirements: object, history: object
) -> tuple[tuple[CompatibilityRetirement, ...], tuple[RetirementHistory, ...]]:
    active = tuple(
        _retirement(item, number)
        for number, item in enumerate(_array(retirements, "compatibility_retirements"))
    )
    if len({item.retirement_id for item in active}) != len(active) or len(
        {item.relation_identity for item in active}
    ) != len(active):
        raise RetirementError("compatibility_retirements identities must be unique")
    # History's byte-level preservation is compared to the trusted base by the engine;
    # this parser reserves its identities and rejects malformed/unknown variants now.
    parsed: list[RetirementHistory] = []
    for number, raw in enumerate(_array(history, "retirement_history")):
        item = _object(raw, f"retirement_history[{number}]")
        _keys(
            item,
            frozenset(
                {
                    "retirement_id",
                    "relation_identity",
                    "displaced_authority",
                    "current_authority_id",
                    "activation_record",
                    "closure_record",
                }
            ),
            f"retirement_history[{number}]",
        )
        displaced = _object(
            item["displaced_authority"],
            f"retirement_history[{number}].displaced_authority",
        )
        _keys(
            displaced,
            frozenset({"authority_id", "writer", "historical_profile"}),
            f"retirement_history[{number}].displaced_authority",
        )
        history_location = f"retirement_history[{number}]"
        _source(displaced["writer"], f"{history_location}.displaced_authority.writer")
        _immutable_record(
            displaced["historical_profile"],
            f"{history_location}.displaced_authority.historical_profile",
        )
        activation_location = f"{history_location}.activation_record"
        activation = _object(item["activation_record"], activation_location)
        _keys(
            activation,
            frozenset(
                {
                    "repository",
                    "commit",
                    "path",
                    "sha256",
                    "retirement_id",
                    "relation_identity",
                }
            ),
            activation_location,
        )
        _immutable_record(
            {
                key: activation[key]
                for key in ("repository", "commit", "path", "sha256")
            },
            activation_location,
        )
        retirement_id = _slug(
            item["retirement_id"], f"{history_location}.retirement_id"
        )
        relation_identity = _string(
            item["relation_identity"], f"{history_location}.relation_identity"
        )
        if (
            _slug(activation["retirement_id"], f"{activation_location}.retirement_id")
            != retirement_id
            or _string(
                activation["relation_identity"],
                f"{activation_location}.relation_identity",
            )
            != relation_identity
        ):
            raise RetirementError(f"{activation_location} does not match history entry")
        closure = _object(
            item["closure_record"], f"retirement_history[{number}].closure_record"
        )
        closure_kind = _string(
            closure.get("kind"), f"retirement_history[{number}].closure_record.kind"
        )
        if closure_kind not in {"deleted", "retained_product_record"}:
            raise RetirementError(
                f"retirement_history[{number}].closure_record.kind is invalid"
            )
        if closure_kind == "deleted":
            _keys(
                closure,
                frozenset({"kind", "post_upgrade_observation"}),
                f"{history_location}.closure_record",
            )
            observation = _target_retirement_evidence(
                closure["post_upgrade_observation"],
                f"{history_location}.closure_record.post_upgrade_observation",
            )
            if observation.phase != "post_upgrade":
                raise RetirementError(
                    f"{history_location} deleted closure needs post_upgrade evidence"
                )
        else:
            _keys(
                closure,
                frozenset(
                    {
                        "kind",
                        "repository",
                        "commit",
                        "path",
                        "sha256",
                        "authority_id",
                        "reason",
                    }
                ),
                f"{history_location}.closure_record",
            )
            _immutable_record(
                {
                    key: closure[key]
                    for key in ("repository", "commit", "path", "sha256")
                },
                f"{history_location}.closure_record",
            )
            _slug(
                closure["authority_id"],
                f"{history_location}.closure_record.authority_id",
            )
            _string(closure["reason"], f"{history_location}.closure_record.reason")
        parsed.append(
            RetirementHistory(
                retirement_id,
                relation_identity,
                AuthorityId(
                    _slug(
                        displaced["authority_id"],
                        f"retirement_history[{number}].displaced_authority.authority_id",
                    )
                ),
                AuthorityId(
                    _slug(
                        item["current_authority_id"],
                        f"retirement_history[{number}].current_authority_id",
                    )
                ),
                closure_kind,
            )
        )
    histories = tuple(parsed)
    reserved = {item.retirement_id for item in histories} | {
        item.relation_identity for item in histories
    }
    if (
        len({item.retirement_id for item in histories}) != len(histories)
        or len({item.relation_identity for item in histories}) != len(histories)
        or any(
            item.retirement_id in reserved or item.relation_identity in reserved
            for item in active
        )
    ):
        raise RetirementError(
            "retirement history identities are permanent reservations"
        )
    return active, histories


def parse_observation_bundle(value: object) -> RetirementObservationBundle:
    """Parse only generated evidence; this does not authenticate its producer."""
    data = _object(value, "observation")
    _keys(
        data,
        frozenset(
            {
                "schema_version",
                "repository",
                "product_revision",
                "governance_revision",
                "producer_id",
                "normalization_version",
                "observations",
            }
        ),
        "observation",
    )
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise RetirementError("observation.schema_version must be integer 1")
    repository = _string(data["repository"], "observation.repository")
    product_revision = _string(data["product_revision"], "observation.product_revision")
    governance_revision = _string(
        data["governance_revision"], "observation.governance_revision"
    )
    if not HTTPS_REPOSITORY.fullmatch(repository):
        raise RetirementError("observation.repository is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", product_revision) or not re.fullmatch(
        r"[0-9a-f]{40}", governance_revision
    ):
        raise RetirementError("observation revisions must be full lower-case Git SHAs")
    normalization = _string(
        data["normalization_version"], "observation.normalization_version"
    )
    if normalization != "python-ast-v1":
        raise RetirementError("observation.normalization_version must be python-ast-v1")
    parsed: list[RetirementObservation] = []
    for number, raw in enumerate(
        _array(data["observations"], "observation.observations")
    ):
        location = f"observation.observations[{number}]"
        item = _object(raw, location)
        _keys(
            item,
            frozenset(
                {
                    "retirement_id",
                    "source_inventory",
                    "migration_database",
                    "deployed_target",
                }
            ),
            location,
        )
        inventory_location = f"{location}.source_inventory"
        inventory = _object(item["source_inventory"], inventory_location)
        _keys(
            inventory,
            frozenset(
                {
                    "coverage",
                    "measured_kinds",
                    "edges",
                    "canonical_decision_writers",
                    "unavailable_regions",
                }
            ),
            inventory_location,
        )
        source_coverage = _string(
            inventory["coverage"], f"{inventory_location}.coverage"
        )
        if source_coverage not in {"measured", "unmeasured"}:
            raise RetirementError(f"{inventory_location}.coverage is invalid")
        measured_kinds = _unique(
            tuple(
                _string(kind, f"{inventory_location}.measured_kinds[{index}]")
                for index, kind in enumerate(
                    _array(
                        inventory["measured_kinds"],
                        f"{inventory_location}.measured_kinds",
                    )
                )
            ),
            f"{inventory_location}.measured_kinds",
        )
        if any(kind not in _STATIC_KINDS for kind in measured_kinds):
            raise RetirementError(
                f"{inventory_location}.measured_kinds contains an invalid kind"
            )
        unavailable = _unique(
            tuple(
                _path(path, f"{inventory_location}.unavailable_regions[{index}]")
                for index, path in enumerate(
                    _array(
                        inventory["unavailable_regions"],
                        f"{inventory_location}.unavailable_regions",
                    )
                )
            ),
            f"{inventory_location}.unavailable_regions",
        )
        if source_coverage == "measured" and (
            set(measured_kinds) != set(_STATIC_KINDS) or unavailable
        ):
            raise RetirementError(
                f"{inventory_location} measured coverage must cover every "
                "static kind and no unavailable regions"
            )
        edges = tuple(
            _edge(edge, f"{inventory_location}.edges[{index}]")
            for index, edge in enumerate(
                _array(inventory["edges"], f"{inventory_location}.edges")
            )
        )
        if len({edge.identity for edge in edges}) != len(edges):
            raise RetirementError(
                f"{inventory_location}.edges identities must be unique"
            )
        writers = tuple(
            _source(writer, f"{inventory_location}.canonical_decision_writers[{index}]")
            for index, writer in enumerate(
                _array(
                    inventory["canonical_decision_writers"],
                    f"{inventory_location}.canonical_decision_writers",
                )
            )
        )
        if len(set(writers)) != len(writers):
            raise RetirementError(
                f"{inventory_location}.canonical_decision_writers must be unique"
            )
        migration_raw = item["migration_database"]
        migration = (
            None
            if migration_raw is None
            else _product_revision_evidence(
                migration_raw, f"{location}.migration_database"
            )
        )
        targets = tuple(
            _target_retirement_evidence(target, f"{location}.deployed_target[{index}]")
            for index, target in enumerate(
                _array(item["deployed_target"], f"{location}.deployed_target")
            )
        )
        observation_ids = {target.observation_id for target in targets}
        if len(observation_ids) != len(targets):
            raise RetirementError(
                f"{location}.deployed_target observation ids must be unique"
            )
        if targets:
            previous_time: datetime | None = None
            for index, target in enumerate(targets):
                if target.preceding_observation_id != (
                    None if index == 0 else targets[index - 1].observation_id
                ):
                    raise RetirementError(
                        f"{location}.deployed_target predecessor chain is invalid"
                    )
                if index == 0 and target.phase != "pre_drop":
                    raise RetirementError(
                        f"{location}.deployed_target must begin with pre_drop"
                    )
                if (
                    index
                    and {"pre_drop": 0, "atomic_teardown": 1, "post_upgrade": 2}[
                        target.phase
                    ]
                    < {"pre_drop": 0, "atomic_teardown": 1, "post_upgrade": 2}[
                        targets[index - 1].phase
                    ]
                ):
                    raise RetirementError(
                        f"{location}.deployed_target phases cannot go backward"
                    )
                if target.phase == "post_upgrade" and (
                    index == 0
                    or targets[index - 1].phase != "atomic_teardown"
                    or targets[index - 1].transaction_outcome != "committed"
                ):
                    raise RetirementError(
                        f"{location}.post_upgrade must immediately follow "
                        "committed atomic teardown"
                    )
                try:
                    current_time = datetime.fromisoformat(
                        target.observed_at.replace("Z", "+00:00")
                    )
                except ValueError as error:
                    raise RetirementError(
                        f"{location}.deployed_target timestamp is invalid"
                    ) from error
                if previous_time is not None and current_time <= previous_time:
                    raise RetirementError(
                        f"{location}.deployed_target timestamps must increase strictly"
                    )
                previous_time = current_time
        parsed.append(
            RetirementObservation(
                _slug(item["retirement_id"], f"{location}.retirement_id"),
                source_coverage,
                measured_kinds,
                edges,
                writers,
                unavailable,
                migration,
                targets,
            )
        )
    observations = tuple(parsed)
    if len({item.retirement_id for item in observations}) != len(observations):
        raise RetirementError("observation retirement ids must be unique")
    return RetirementObservationBundle(
        repository,
        product_revision,
        governance_revision,
        _slug(data["producer_id"], "observation.producer_id"),
        normalization,
        observations,
    )
