"""Strict validation for canonical cross-repository programme matrices."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]

IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
CANONICAL_REPOSITORY = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"
)

TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "programme_id",
        "title",
        "status",
        "owner",
        "approver",
        "authority",
        "tracks",
        "records",
        "cutover_control_ids",
        "controls",
        "cohorts",
        "capability_scope",
        "capability_roster",
        "open_decisions",
        "resolved_decisions",
    }
)
AUTHORITY_FIELDS = frozenset({"source", "target"})
SOURCE_FIELDS = frozenset({"assembly_id", "repository", "authority_state"})
TARGET_FIELDS = frozenset(
    {
        "assembly_id",
        "repository_status",
        "repository",
        "database_boundary",
        "authority_state",
    }
)
TRACK_FIELDS = frozenset({"track_id", "role", "assembly_id", "responsibility"})
RECORD_FIELDS = frozenset({"record_id", "repository", "revision", "path", "role"})
CONTROL_FIELDS = frozenset(
    {"control_id", "name", "owner", "state", "depends_on", "evidence_refs"}
)
EVIDENCE_FIELDS = frozenset({"producer", "repository", "revision", "subject"})
COHORT_FIELDS = frozenset(
    {
        "cohort_id",
        "sequence",
        "name",
        "state",
        "depends_on",
        "current_authority",
        "target_authority",
        "components",
    }
)
COMPONENT_FIELDS = frozenset({"component_id", "owner_id", "disposition"})
# Optional because "declares no sibling requirement" is the common, correct
# state; see `_strict_fields`.
COMPONENT_OPTIONAL_FIELDS = frozenset({"requires"})
ROSTER_FIELDS = frozenset({"component_id", "disposition", "rationale"})
# A capability that is not carried by a cohort must still be disposed of
# explicitly. These are the only three ways to do that.
ROSTER_DISPOSITIONS = frozenset({"retain", "replace", "retire"})
DECISION_FIELDS = frozenset({"decision_id", "question", "owner", "state", "blocks"})
# A decision that was MADE needs somewhere to live. `open_decisions` accepts
# only `state: "open"`, so resolving one used to mean deleting it — which threw
# away the answer, the person who gave it, and the revision that proves when.
# ADR 0012 forbids changing a stable identifier's meaning and requires explicit
# history; silently dropping the identifier is the same loss by another route.
RESOLVED_DECISION_FIELDS = frozenset(
    {"decision_id", "question", "owner", "resolution", "evidence_refs"}
)

PROGRAMME_STATUSES = frozenset({"proposed", "accepted", "active", "complete"})
CONTROL_STATES = frozenset(
    {"pending-approval", "blocked", "not-started", "in-progress", "verified"}
)
COHORT_STATES = frozenset({"blocked", "not-started", "in-progress", "verified"})
DISPOSITIONS = frozenset({"adjudicate", "adopt", "build", "release", "reuse", "retire"})
RECORD_ROLES = frozenset(
    {"governing-decision", "measured-evidence", "technical-source"}
)
TRACK_ROLES = frozenset({"source-cutover", "target-construction"})


def _object(value: object, location: str, errors: list[str]) -> JsonObject | None:
    if not isinstance(value, dict):
        errors.append(f"{location}: expected an object")
        return None
    if not all(isinstance(key, str) for key in value):
        errors.append(f"{location}: object keys must be strings")
        return None
    return cast(JsonObject, value)


def _array(value: object, location: str, errors: list[str]) -> list[object] | None:
    if not isinstance(value, list):
        errors.append(f"{location}: expected an array")
        return None
    return cast(list[object], value)


def _strict_fields(
    record: JsonObject,
    expected: frozenset[str],
    location: str,
    errors: list[str],
    optional: frozenset[str] = frozenset(),
) -> None:
    """Every expected field present, and nothing beyond expected + optional.

    `optional` exists for fields whose ABSENCE is a meaningful declaration
    rather than an omission — a component with no `requires` is asserting it
    needs no sibling capability, which is the common case and should not have
    to be written out 54 times.
    """
    for field in sorted(expected - record.keys()):
        errors.append(f"{location}: missing field {field!r}")
    for field in sorted(record.keys() - expected - optional):
        errors.append(f"{location}: unknown field {field!r}")


def _string(
    record: JsonObject,
    field: str,
    location: str,
    errors: list[str],
) -> str | None:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{location}.{field}: expected a non-empty string")
        return None
    return value


def _identifier(
    record: JsonObject,
    field: str,
    location: str,
    errors: list[str],
) -> str | None:
    value = _string(record, field, location, errors)
    if value is not None and not IDENTIFIER.fullmatch(value):
        errors.append(f"{location}.{field}: invalid stable identifier {value!r}")
        return None
    return value


def _enum(
    record: JsonObject,
    field: str,
    allowed: frozenset[str],
    location: str,
    errors: list[str],
) -> str | None:
    value = _string(record, field, location, errors)
    if value is not None and value not in allowed:
        errors.append(
            f"{location}.{field}: expected one of {', '.join(sorted(allowed))}, "
            f"found {value!r}"
        )
        return None
    return value


def _string_array(
    record: JsonObject,
    field: str,
    location: str,
    errors: list[str],
) -> list[str]:
    values = _array(record.get(field), f"{location}.{field}", errors)
    if values is None:
        return []
    result: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{location}.{field}[{index}]: expected a non-empty string")
        else:
            result.append(value)
    return result


def _unique_id(
    value: str | None,
    label: str,
    seen: set[str],
    errors: list[str],
) -> None:
    if value is None:
        return
    if value in seen:
        errors.append(f"duplicate {label} {value!r}")
    seen.add(value)


def _validate_authority(
    root: JsonObject, errors: list[str]
) -> tuple[str | None, str | None]:
    authority = _object(root.get("authority"), "authority", errors)
    if authority is None:
        return None, None
    _strict_fields(authority, AUTHORITY_FIELDS, "authority", errors)

    source = _object(authority.get("source"), "authority.source", errors)
    target = _object(authority.get("target"), "authority.target", errors)
    source_id: str | None = None
    target_id: str | None = None

    if source is not None:
        _strict_fields(source, SOURCE_FIELDS, "authority.source", errors)
        source_id = _identifier(source, "assembly_id", "authority.source", errors)
        repository = _string(source, "repository", "authority.source", errors)
        if repository is not None and not CANONICAL_REPOSITORY.fullmatch(repository):
            errors.append("authority.source.repository: expected a canonical HTTPS URL")
        _enum(
            source,
            "authority_state",
            frozenset({"source-authoritative"}),
            "authority.source",
            errors,
        )

    if target is not None:
        _strict_fields(target, TARGET_FIELDS, "authority.target", errors)
        target_id = _identifier(target, "assembly_id", "authority.target", errors)
        repository_status = _enum(
            target,
            "repository_status",
            frozenset({"assigned", "unassigned"}),
            "authority.target",
            errors,
        )
        repository = _string(target, "repository", "authority.target", errors)
        if repository_status == "assigned" and (
            repository is None or not CANONICAL_REPOSITORY.fullmatch(repository)
        ):
            errors.append(
                "authority.target: assigned target repository must be a canonical "
                "HTTPS URL"
            )
        if repository_status == "unassigned" and repository != "unassigned":
            errors.append(
                "authority.target: unassigned target repository must use the "
                "literal 'unassigned'"
            )
        _enum(
            target,
            "database_boundary",
            frozenset({"independent"}),
            "authority.target",
            errors,
        )
        _enum(
            target,
            "authority_state",
            frozenset({"candidate"}),
            "authority.target",
            errors,
        )

    if source_id is not None and source_id == target_id:
        errors.append("authority: source and target assembly_id must differ")
    return source_id, target_id


def _validate_tracks(
    root: JsonObject,
    source_id: str | None,
    target_id: str | None,
    errors: list[str],
) -> None:
    tracks = _array(root.get("tracks"), "tracks", errors)
    if tracks is None:
        return

    seen_ids: set[str] = set()
    seen_roles: set[str] = set()
    expected_assemblies = {
        "source-cutover": source_id,
        "target-construction": target_id,
    }
    for index, value in enumerate(tracks):
        location = f"tracks[{index}]"
        track = _object(value, location, errors)
        if track is None:
            continue
        _strict_fields(track, TRACK_FIELDS, location, errors)
        track_id = _identifier(track, "track_id", location, errors)
        _unique_id(track_id, "track_id", seen_ids, errors)
        role = _enum(track, "role", TRACK_ROLES, location, errors)
        assembly_id = _identifier(track, "assembly_id", location, errors)
        _string(track, "responsibility", location, errors)
        if role is None:
            continue
        if role in seen_roles:
            errors.append(f"duplicate track role {role!r}")
        seen_roles.add(role)
        expected_assembly = expected_assemblies[role]
        if expected_assembly is not None and assembly_id != expected_assembly:
            errors.append(
                f"{location}.assembly_id: track role {role!r} must use "
                f"{expected_assembly!r}"
            )

    missing_roles = sorted(TRACK_ROLES - seen_roles)
    if missing_roles:
        errors.append(f"tracks: missing required roles: {', '.join(missing_roles)}")


def _validate_records(root: JsonObject, errors: list[str]) -> None:
    records = _array(root.get("records"), "records", errors)
    if records is None:
        return
    if not records:
        errors.append("records: expected at least one controlled record")
    seen: set[str] = set()
    for index, value in enumerate(records):
        location = f"records[{index}]"
        record = _object(value, location, errors)
        if record is None:
            continue
        _strict_fields(record, RECORD_FIELDS, location, errors)
        record_id = _identifier(record, "record_id", location, errors)
        _unique_id(record_id, "record_id", seen, errors)
        repository = _string(record, "repository", location, errors)
        if repository is not None and not CANONICAL_REPOSITORY.fullmatch(repository):
            errors.append(f"{location}.repository: expected a canonical HTTPS URL")
        revision = _string(record, "revision", location, errors)
        if (
            revision is not None
            and revision != "SELF"
            and not GIT_REVISION.fullmatch(revision)
        ):
            errors.append(
                f"{location}.revision: must be SELF or a 40-character lower-case "
                "Git revision"
            )
        path = _string(record, "path", location, errors)
        if path is not None and (path.startswith("/") or ".." in Path(path).parts):
            errors.append(f"{location}.path: expected a repository-relative path")
        _enum(record, "role", RECORD_ROLES, location, errors)


def _validate_evidence(values: list[object], location: str, errors: list[str]) -> None:
    for index, value in enumerate(values):
        evidence_location = f"{location}[{index}]"
        evidence = _object(value, evidence_location, errors)
        if evidence is None:
            continue
        _strict_fields(evidence, EVIDENCE_FIELDS, evidence_location, errors)
        _string(evidence, "producer", evidence_location, errors)
        repository = _string(evidence, "repository", evidence_location, errors)
        if repository is not None and not CANONICAL_REPOSITORY.fullmatch(repository):
            errors.append(
                f"{evidence_location}.repository: expected a canonical HTTPS URL"
            )
        revision = _string(evidence, "revision", evidence_location, errors)
        if revision is not None and not GIT_REVISION.fullmatch(revision):
            errors.append(
                f"{evidence_location}.revision: expected an immutable 40-character "
                "lower-case Git revision"
            )
        _string(evidence, "subject", evidence_location, errors)


def _cycle_nodes(dependencies: dict[str, list[str]]) -> list[str]:
    visited: set[str] = set()
    active: set[str] = set()
    cycle: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            cycle.add(node)
            return
        if node in visited:
            return
        active.add(node)
        for dependency in dependencies.get(node, []):
            if dependency in dependencies:
                visit(dependency)
                if dependency in cycle:
                    cycle.add(node)
        active.remove(node)
        visited.add(node)

    for node in dependencies:
        visit(node)
    return sorted(cycle)


def _validate_controls(
    root: JsonObject, errors: list[str]
) -> tuple[set[str], dict[str, str]]:
    controls = _array(root.get("controls"), "controls", errors)
    if controls is None:
        return set(), {}
    if not controls:
        errors.append("controls: expected at least one programme control")

    seen: set[str] = set()
    states: dict[str, str] = {}
    dependencies: dict[str, list[str]] = {}
    for index, value in enumerate(controls):
        location = f"controls[{index}]"
        control = _object(value, location, errors)
        if control is None:
            continue
        _strict_fields(control, CONTROL_FIELDS, location, errors)
        control_id = _identifier(control, "control_id", location, errors)
        _unique_id(control_id, "control_id", seen, errors)
        _string(control, "name", location, errors)
        _string(control, "owner", location, errors)
        state = _enum(control, "state", CONTROL_STATES, location, errors)
        depends_on = _string_array(control, "depends_on", location, errors)
        evidence = _array(
            control.get("evidence_refs"), f"{location}.evidence_refs", errors
        )
        if evidence is not None:
            _validate_evidence(evidence, f"{location}.evidence_refs", errors)
        if state == "verified" and not evidence:
            errors.append(f"{location}: verified control has no evidence_refs")
        if state == "blocked" and not depends_on:
            errors.append(f"{location}: blocked control must name depends_on")
        if control_id is not None:
            states[control_id] = state or ""
            dependencies[control_id] = depends_on

    for control_id, control_dependencies in dependencies.items():
        for dependency in control_dependencies:
            if dependency not in seen:
                errors.append(
                    f"control {control_id!r}: unknown dependency {dependency!r}"
                )
            if dependency == control_id:
                errors.append(f"control {control_id!r}: depends on itself")
    cycle = _cycle_nodes(dependencies)
    if cycle:
        errors.append(f"control dependency cycle: {', '.join(cycle)}")
    return seen, states


def _cohort_sequence(
    location: str | None, cohorts: list[object], errors: list[str]
) -> int:
    """The declared `sequence` of the cohort a component was recorded under.

    `component_cohorts` stores the cohort's JSON location (`cohorts[3]`) rather
    than its id, so ordering is read back from the same declaration the rest of
    this module validates instead of a second index that could disagree.
    """
    if location is None:
        return 0
    index = int(location[len("cohorts[") : -1])
    cohort = cohorts[index]
    if not isinstance(cohort, dict):
        return 0
    sequence = cohort.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        return 0
    return sequence


def _validate_components(
    values: list[object],
    location: str,
    component_cohorts: dict[str, str],
    component_requires: dict[str, list[str]],
    errors: list[str],
) -> None:
    if not values:
        errors.append(f"{location}: expected at least one component")
    for index, value in enumerate(values):
        component_location = f"{location}[{index}]"
        component = _object(value, component_location, errors)
        if component is None:
            continue
        _strict_fields(
            component,
            COMPONENT_FIELDS,
            component_location,
            errors,
            optional=COMPONENT_OPTIONAL_FIELDS,
        )
        component_id = _identifier(
            component, "component_id", component_location, errors
        )
        _identifier(component, "owner_id", component_location, errors)
        _enum(
            component,
            "disposition",
            DISPOSITIONS,
            component_location,
            errors,
        )
        if component_id is None:
            continue
        previous = component_cohorts.get(component_id)
        if previous is not None:
            errors.append(
                f"component {component_id!r} appears in both {previous} and "
                f"{location.rsplit('.', 1)[0]}"
            )
        else:
            component_cohorts[component_id] = location.rsplit(".", 1)[0]
        # A component may name the other components it cannot operate without.
        # Cohort `depends_on` orders the SWITCHES; this orders the CAPABILITIES,
        # and the two are not the same claim — a module whose manifest declares
        # `dependencies=(...)` can sit in an earlier cohort than the module it
        # depends on without any cohort edge being violated.
        if "requires" in component:
            component_requires[component_id] = _string_array(
                component, "requires", component_location, errors
            )


def _validate_cohorts(
    root: JsonObject,
    source_id: str | None,
    target_id: str | None,
    control_states: dict[str, str],
    cutover_control_ids: list[str],
    errors: list[str],
) -> set[str]:
    cohorts = _array(root.get("cohorts"), "cohorts", errors)
    if cohorts is None:
        return set()
    if not cohorts:
        errors.append("cohorts: expected at least one migration cohort")

    seen: set[str] = set()
    sequences: dict[str, int] = {}
    dependencies: dict[str, list[str]] = {}
    cohort_states: dict[str, str] = {}
    component_cohorts: dict[str, str] = {}
    component_requires: dict[str, list[str]] = {}
    for index, value in enumerate(cohorts):
        location = f"cohorts[{index}]"
        cohort = _object(value, location, errors)
        if cohort is None:
            continue
        _strict_fields(cohort, COHORT_FIELDS, location, errors)
        cohort_id = _identifier(cohort, "cohort_id", location, errors)
        _unique_id(cohort_id, "cohort_id", seen, errors)
        sequence_value = cohort.get("sequence")
        if not isinstance(sequence_value, int) or isinstance(sequence_value, bool):
            errors.append(f"{location}.sequence: expected an integer")
            sequence: int | None = None
        else:
            sequence = sequence_value
            if sequence < 1:
                errors.append(f"{location}.sequence: must be at least 1")
        _string(cohort, "name", location, errors)
        state = _enum(cohort, "state", COHORT_STATES, location, errors)
        depends_on = _string_array(cohort, "depends_on", location, errors)
        current_authority = _identifier(cohort, "current_authority", location, errors)
        target_authority = _identifier(cohort, "target_authority", location, errors)
        if source_id is not None and current_authority != source_id:
            errors.append(
                f"{location}.current_authority: expected source assembly {source_id!r}"
            )
        if target_id is not None and target_authority != target_id:
            errors.append(
                f"{location}.target_authority: expected target assembly {target_id!r}"
            )
        components = _array(cohort.get("components"), f"{location}.components", errors)
        if components is not None:
            _validate_components(
                components,
                f"{location}.components",
                component_cohorts,
                component_requires,
                errors,
            )
        if cohort_id is not None:
            dependencies[cohort_id] = depends_on
            cohort_states[cohort_id] = state or ""
            if sequence is not None:
                sequences[cohort_id] = sequence

    expected_sequences = list(range(1, len(sequences) + 1))
    actual_sequences = sorted(sequences.values())
    if actual_sequences != expected_sequences:
        errors.append(
            f"cohorts: sequence values must be contiguous from 1; found "
            f"{actual_sequences!r}"
        )

    for cohort_id, cohort_dependencies in dependencies.items():
        for dependency in cohort_dependencies:
            if dependency not in seen:
                errors.append(
                    f"cohort {cohort_id!r}: unknown dependency {dependency!r}"
                )
                continue
            if sequences.get(dependency, 0) >= sequences.get(cohort_id, 0):
                errors.append(
                    f"cohort {cohort_id!r}: dependency {dependency!r} must point "
                    "to an earlier cohort"
                )

    # Component-level ordering. ADR 0012 forbids starting a cohort before its
    # dependencies, but until now that was only ever checked between cohorts.
    # A component could therefore be scheduled ahead of a capability it
    # declares it needs — as `dotmac-fulfillment` (cohort 4) was, ahead of the
    # `dotmac-durable-timers` (cohort 5) its manifest names in
    # `dependencies=("durable_timers",)`. Same cohort is permitted: a cohort is
    # one sealed switch, so its members cut over together.
    for component_id, required in sorted(component_requires.items()):
        holder = component_cohorts.get(component_id)
        for requirement in required:
            supplier = component_cohorts.get(requirement)
            if supplier is None:
                errors.append(
                    f"component {component_id!r}: requires unknown component "
                    f"{requirement!r}"
                )
                continue
            if requirement == component_id:
                errors.append(f"component {component_id!r}: requires itself")
                continue
            if _cohort_sequence(supplier, cohorts, errors) > _cohort_sequence(
                holder, cohorts, errors
            ):
                errors.append(
                    f"component {component_id!r}: requires {requirement!r}, which "
                    "is scheduled in a later cohort"
                )

    for cohort_id, state in cohort_states.items():
        if state not in {"in-progress", "verified"}:
            continue
        unverified = [
            control_id
            for control_id in cutover_control_ids
            if control_states.get(control_id) != "verified"
        ]
        if unverified:
            errors.append(
                f"cohort {cohort_id!r}: state {state!r} requires verified "
                f"cutover controls; unverified: {', '.join(unverified)}"
            )
    return seen


def _validate_capability_roster(root: JsonObject, errors: list[str]) -> None:
    """Every in-scope capability is carried by a cohort or explicitly disposed.

    The ordering checks catch a component scheduled ahead of what it needs, and
    a `requires` that names nothing. Neither can see a capability that was
    simply never mentioned — `dotmac-work-orders` was a built, ledger-allocated
    module with a package on Starter main that appeared in no cohort at all,
    and every check passed. Omission is the one failure mode a matrix cannot
    detect from its own contents, so the scope has to be declared separately
    and reconciled against them.

    `capability_scope` is that declaration: the capabilities this programme is
    answerable for. Each must appear in exactly one cohort, or carry a
    retain/replace/retire disposition in `capability_roster` with a rationale.
    Adding a module to the scope therefore forces the question rather than
    letting silence answer it.
    """
    scope = _string_array(root, "capability_scope", "capability_scope", errors)
    scoped = set(scope)
    for duplicate in sorted({item for item in scope if scope.count(item) > 1}):
        errors.append(f"capability_scope: duplicate entry {duplicate!r}")

    in_cohorts: set[str] = set()
    cohorts = root.get("cohorts")
    if isinstance(cohorts, list):
        for cohort in cohorts:
            if not isinstance(cohort, dict):
                continue
            components = cohort.get("components")
            if not isinstance(components, list):
                continue
            for component in components:
                if isinstance(component, dict):
                    component_id = component.get("component_id")
                    if isinstance(component_id, str):
                        in_cohorts.add(component_id)

    rostered: set[str] = set()
    entries = _array(root.get("capability_roster"), "capability_roster", errors)
    for index, value in enumerate(entries or []):
        location = f"capability_roster[{index}]"
        entry = _object(value, location, errors)
        if entry is None:
            continue
        _strict_fields(entry, ROSTER_FIELDS, location, errors)
        component_id = _identifier(entry, "component_id", location, errors)
        _enum(entry, "disposition", ROSTER_DISPOSITIONS, location, errors)
        # A disposition with no reason is how "retain" becomes a shrug.
        _string(entry, "rationale", location, errors)
        if component_id is None:
            continue
        if component_id in rostered:
            errors.append(f"{location}: duplicate roster entry {component_id!r}")
        rostered.add(component_id)
        if component_id in in_cohorts:
            errors.append(
                f"{location}: {component_id!r} is already carried by a cohort; "
                "a capability is disposed of in one place, not two"
            )

    for component_id in sorted(in_cohorts - scoped):
        errors.append(f"cohorts: component {component_id!r} is not in capability_scope")
    for component_id in sorted(rostered - scoped):
        errors.append(f"capability_roster: {component_id!r} is not in capability_scope")
    for component_id in sorted(scoped - in_cohorts - rostered):
        errors.append(
            f"capability_scope: {component_id!r} has no cohort and no "
            "retain/replace/retire disposition"
        )


def _validate_open_decisions(
    root: JsonObject,
    block_targets: set[str],
    errors: list[str],
) -> None:
    decisions = _array(root.get("open_decisions"), "open_decisions", errors)
    if decisions is None:
        return
    seen: set[str] = set()
    for index, value in enumerate(decisions):
        location = f"open_decisions[{index}]"
        decision = _object(value, location, errors)
        if decision is None:
            continue
        _strict_fields(decision, DECISION_FIELDS, location, errors)
        decision_id = _identifier(decision, "decision_id", location, errors)
        _unique_id(decision_id, "decision_id", seen, errors)
        _string(decision, "question", location, errors)
        _string(decision, "owner", location, errors)
        _enum(
            decision,
            "state",
            frozenset({"open"}),
            location,
            errors,
        )
        blocks = _string_array(decision, "blocks", location, errors)
        if not blocks:
            errors.append(f"{location}: open decision must block a control or cohort")
        for target in blocks:
            if target not in block_targets:
                errors.append(f"{location}: unknown block target {target!r}")


def _validate_resolved_decisions(
    root: JsonObject,
    open_ids: set[str],
    errors: list[str],
) -> None:
    """Every resolved decision keeps its question and cites immutable evidence.

    The question is retained deliberately. A resolution recorded without the
    question it answers is unreadable a month later, and re-deriving it from a
    deleted `open_decisions` entry means reading Git history to understand a
    record whose whole purpose is to make that unnecessary.

    An id may not appear in both lists. A decision is open or it is answered;
    holding both states is how two readers reach opposite conclusions from the
    same file.
    """

    decisions = _array(root.get("resolved_decisions"), "resolved_decisions", errors)
    if decisions is None:
        return
    seen: set[str] = set()
    for index, value in enumerate(decisions):
        location = f"resolved_decisions[{index}]"
        decision = _object(value, location, errors)
        if decision is None:
            continue
        _strict_fields(decision, RESOLVED_DECISION_FIELDS, location, errors)
        decision_id = _identifier(decision, "decision_id", location, errors)
        _unique_id(decision_id, "decision_id", seen, errors)
        if decision_id is not None and decision_id in open_ids:
            errors.append(
                f"{location}: {decision_id!r} is also listed as open; a "
                "decision is open or answered, never both"
            )
        _string(decision, "question", location, errors)
        _string(decision, "owner", location, errors)
        _string(decision, "resolution", location, errors)
        evidence = _array(
            decision.get("evidence_refs"), f"{location}.evidence_refs", errors
        )
        if not evidence:
            errors.append(
                f"{location}: a resolved decision must cite immutable evidence; "
                "an agent-authored assertion is not a decision record"
            )
        else:
            _validate_evidence(evidence, f"{location}.evidence_refs", errors)


def validate_matrix(path: Path) -> list[str]:
    """Return every structural and state error for one programme matrix."""
    errors: list[str] = []
    try:
        data: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: cannot read valid JSON: {exc}"]

    root = _object(data, path.name, errors)
    if root is None:
        return errors
    _strict_fields(root, TOP_LEVEL_FIELDS, path.name, errors)

    schema_version = root.get("schema_version")
    if schema_version != 1:
        errors.append(f"{path.name}.schema_version: expected 1")
    _identifier(root, "programme_id", path.name, errors)
    _string(root, "title", path.name, errors)
    status = _enum(root, "status", PROGRAMME_STATUSES, path.name, errors)
    _string(root, "owner", path.name, errors)
    _string(root, "approver", path.name, errors)

    source_id, target_id = _validate_authority(root, errors)
    _validate_tracks(root, source_id, target_id, errors)
    _validate_records(root, errors)
    control_ids, control_states = _validate_controls(root, errors)
    cutover_control_ids = _string_array(root, "cutover_control_ids", path.name, errors)
    if not cutover_control_ids:
        errors.append(f"{path.name}.cutover_control_ids: expected at least one control")
    if len(cutover_control_ids) != len(set(cutover_control_ids)):
        errors.append(f"{path.name}.cutover_control_ids: duplicate control reference")
    for control_id in cutover_control_ids:
        if control_id not in control_ids:
            errors.append(
                f"{path.name}.cutover_control_ids: unknown control {control_id!r}"
            )

    cohort_ids = _validate_cohorts(
        root,
        source_id,
        target_id,
        control_states,
        cutover_control_ids,
        errors,
    )
    _validate_capability_roster(root, errors)
    open_ids = {
        decision.get("decision_id")
        for decision in (root.get("open_decisions") or [])
        if isinstance(decision, dict) and isinstance(decision.get("decision_id"), str)
    }
    _validate_open_decisions(root, control_ids | cohort_ids, errors)
    _validate_resolved_decisions(root, open_ids, errors)

    if status == "proposed":
        verified = sorted(
            control_id
            for control_id, state in control_states.items()
            if state == "verified"
        )
        if verified:
            errors.append(
                f"{path.name}: proposed programme cannot claim verified controls: "
                f"{', '.join(verified)}"
            )
    return errors


def verify_repository(root: Path) -> list[str]:
    """Return errors for every canonical matrix in a Governance checkout."""
    programme_dir = root / "programmes"
    if not programme_dir.is_dir():
        return [f"{programme_dir}: directory does not exist"]
    matrices = sorted(programme_dir.glob("*.json"))
    if not matrices:
        return [f"{programme_dir}: no programme matrices found"]
    errors: list[str] = []
    seen_programmes: set[str] = set()
    for path in matrices:
        matrix_errors = validate_matrix(path)
        errors.extend(matrix_errors)
        if matrix_errors:
            continue
        data: object = json.loads(path.read_text(encoding="utf-8"))
        root_record = cast(JsonObject, data)
        programme_id = cast(str, root_record["programme_id"])
        if programme_id in seen_programmes:
            errors.append(f"duplicate programme_id {programme_id!r}")
        seen_programmes.add(programme_id)
    return errors
