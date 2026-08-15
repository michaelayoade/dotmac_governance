# ADR 0018 conformance backlog: fixture-only sensitivity proofs in `dotmac_starter_mt`

Status: **BACKLOG — nothing here is fixed, and this correction is deliberately
not expanded into a fleet rewrite.** Recorded so the finding is not lost when the
external-connector work ends.

Owner repository: `dotmac_starter_mt` (READ-ONLY from here; every path below is
in that repository, not in `dotmac_governance`).

Date of survey: 2026-08-15. Method: static read of all 62 test files under
`tests/architecture/` plus the repo-wide structural guards under `tests/`. **No
test suite was executed** — this is a source survey, not a run.

## Why this is tracked here

ADR 0018 requires a detector to carry a **sensitivity proof**: evidence that the
guard would actually fire. A proof built entirely from a synthetic input — a
`tmp_path` file, an inline source string handed to `ast.parse`, a fabricated
manifest or a scratch `MetaData` — proves the **predicate** and says nothing
about the **wiring**. A guard whose discovery has silently stopped reaching the
real tree (a moved package root, a renamed directory, an empty `rglob`) passes
green with a fixture-only proof, and a green over an empty set is the failure
mode ADR 0018 exists to prevent. That is the same defect class the external
connector arms were just corrected for, which is why the survey happened; it is
NOT the same code and must not be swept into the same change.

The distinction used throughout:

* **fixture-only** — the firing proof uses a synthetic input only.
* **in-situ** — the firing proof drives the guard's own discovery over the real
  corpus and shows it naming a real file, usually by mutating real state inside a
  rollback / restore.
* **non-vacuity only** — the guard asserts its scan found *something*, but never
  shows it firing. Weaker than a fixture proof in one direction, stronger in the
  other; listed separately in § 3.

## 1. Fixture-only sensitivity proofs — 25 files, 41 proof functions

| # | File (under `dotmac_starter_mt/`) | Proof function(s) | Rule guarded | Proof construct | Real-corpus discovery in the same file? |
| --- | --- | --- | --- | --- | --- |
| 1 | `tests/architecture/test_application_directory_module.py` | `test_the_detector_catches_a_planted_column` | no person/role/grant column on `ApplicationBinding` (ADR-0021 §3) | synthetic name tuple; the sweep is never called | partial — the real column loop lives in another test |
| 2 | `tests/architecture/test_auth_oidc_public_surface.py` | `test_the_import_checker_fires_on_a_planted_violation`, `test_the_concern_checker_fires_on_a_planted_violation`, `test_the_concern_checker_is_not_fooled_by_prose` | `dotmac-auth-oidc` imports no kernel/ORM | inline source strings | **no** — `PACKAGE_ROOT.rglob` never asserted non-empty |
| 3 | `tests/architecture/test_kernel_public_surface.py` | `test_checker_flags_private_and_internal_imports` | assembly imports only documented kernel surface | inline strings, fake path `app/_probe_.py` | **no** — `_iter_app_files()` never asserted non-empty |
| 4 | `tests/architecture/test_ui_public_surface.py` | `test_checker_flags_private_and_undeclared_imports` | assembly ↔ `dotmac_ui` public surface | inline strings, fake paths | **no** |
| 5 | `tests/architecture/test_capability_ownership.py` | `test_the_capability_literal_guard_bites`, `test_the_conformance_exemption_premise_is_enforced`, `test_the_transport_import_guard_bites` | `dotmac-integration` enumerates no capability id, imports no transport | inline one-liners | **no** |
| 6 | `tests/architecture/test_capacity_is_a_row.py` | `test_the_detector_actually_detects` | no capacity as Enum/CHECK on an identity table (ADR-0019 §5a) | synthetic tables in a scratch `MetaData` | partial — real loop `continue`s on missing tables |
| 7 | `tests/architecture/test_ci_runs_canonical_check.py` | `test_the_comparison_detects_a_planted_drift`, `test_the_recipe_detector_bites` | CI quality matrix == `make check` prerequisites | inline Makefile/workflow strings; the recipe proof **re-implements the production regex** | yes for parsing (`test_the_parsers_find_something`) |
| 8 | `tests/architecture/test_declared_publication.py` | `test_the_guard_fires_on_an_unrecorded_unpublished_declaration`, `…_when_a_recorded_entry_has_been_published`, `…_when_a_bump_outruns_its_ledger_entry` | declared-but-unpublished versions carry a ledger entry | synthetic survey dict for a nonexistent distribution | yes (real package survey elsewhere) |
| 9 | `tests/architecture/test_external_connector_ratchet.py` | 10 functions (`test_the_detector_distinguishes_a_client_from_a_type_annotation`, `…_a_generic_api_key_is_not_counted…`, `…_a_rotation_cursor_is_not_a_sync_checkpoint`, `…_narrowing_the_cursor_rule_did_not_blind…`, `…_still_bites`, `…_an_unreadable_file_is_reported…`, `…_an_unclassified_fleet_distribution_is_named`, `…_a_classified_repository_is_not_reported…`, `…_a_nested_checkout_is_pruned…`, `…_tests_and_migrations_are_not_application_runtime`) | fleet direct-connector surface is frozen (ADR-0024 §6) | inline `ast.parse` strings + whole synthetic fleets under `tmp_path` | **effectively no** — the fleet measurement `pytest.skip`s when sibling repos are absent |
| 10 | `tests/architecture/test_feature_flags.py` | `test_the_expiry_check_would_actually_fail` | no flag past its removal date | synthetic `FeatureFlagSpec` | yes (real catalogue non-empty) |
| 11 | `tests/architecture/test_feature_manifests.py` | `test_nav_paths_coherence_detects_bogus_entry` | `NavItem.path` resolves to a mounted route | synthetic manifest | partial (the contract-drift half **is** in-situ) |
| 12 | `tests/architecture/test_fleet_decomposition_matrix.py` | `test_destination_detector_rejects_transitions_and_metadata`, `test_family_row_detector_is_sensitive` | every family row resolves to kernel/UI/module | inline markdown rows | yes for the positive direction |
| 13 | `tests/architecture/test_fleet_fact_registry.py` | `test_withdrawal_detector_is_sensitive` | a withdrawn ownership claim may not reappear | two inline prose strings | negative direction only |
| 14 | `tests/architecture/test_module_lineage_locator.py` | `test_a_locator_returning_the_wrong_path_is_rejected`, `…_an_ambiguous_or_missing_import_root_fails…`, `…_the_reader_detects_a_present_and_an_absent_locator`, `…_the_lineage_detector_follows_revisions_not_directories` | every lineage module exposes a correct `versions_dir()` | whole synthetic packages under `tmp_path` | **yes, strongly** (`len(_LINEAGE) >= 8` over real packages) |
| 15 | `tests/architecture/test_module_version_sync.py` | `test_the_comparison_catches_drift_in_every_position` | `__version__` / pyproject / manifest agree | synthetic dict, fictitious distribution | yes (allowlist non-empty) |
| 16 | `tests/architecture/test_product_vision.py` | `test_product_vision_contract_detector_is_sensitive` | `PRODUCT_VISION.md` keeps the recomposition clauses | inline prose blob | partial (compliant direction only) |
| 17 | `tests/architecture/test_publishable_packages_ship_no_secret_shape.py` | `test_the_detector_bites_on_each_marker`, `test_the_marker_list_is_not_empty` | no secret-shaped filename ships (ADR-0009) | parametrized synthetic filenames | yes (`test_the_scan_reaches_a_real_file_tree`) |
| 18 | `tests/architecture/test_secrets_are_held.py` | `test_the_check_would_notice_a_network_import` | no network import on the settings-resolution path (ADR-0009) | `tmp_path` file | partial — paths asserted to exist, never a real positive |
| 19 | `tests/architecture/test_template_studio_module.py` | `test_a_module_cannot_invent_an_unallocated_namespace` | namespace ledger refuses unallocated schemas | fabricated `ModuleManifest` | partial (the re-point test mutates the **real** manifest) |
| 20 | `tests/architecture/test_web_conventions.py` | `test_the_safe_filter_guard_still_bites`, `test_timestamp_filter_check_catches_bypass_attempts` | `\| safe` needs a sanitize comment; timestamps go through filters | inline template snippets; the `\| safe` proof **re-implements the production check** as a local `_flags()` | yes (`test_template_scan_is_not_vacuous`) |
| 21 | `tests/architecture/test_capability_enforcement.py` | `test_an_undeclared_capability_fails_the_boot`, `test_the_reference_walker_finds_a_stamped_code` | every referenced capability is declared | throwaway `FastAPI()` app | partial (real app imported in a different test) |
| 22 | `tests/architecture/test_workflow_action_pinning.py` | `test_the_checker_would_catch_a_mutable_tag` | third-party action refs are full SHAs | regex-only assertions on literals | **yes** — real `.github` probe files are discovered elsewhere in the file |
| 23 | `tests/architecture/test_adapter_release_lane.py` | `test_a_module_entry_missing_a_stateful_fact_does_not_resolve` + 5 synthetic-allowlist tests | adapter lane publishes only allowlisted stateless adapters | fabricated `release-adapters.json` under `tmp_path` | yes (real allowlist driven elsewhere) |
| 24 | `tests/architecture/test_connector_release_policy.py` | `test_a_wrong_classification_is_refused`, `test_a_real_adapter_with_the_same_classification_is_still_refused`, `test_a_distribution_must_register_exactly_one_connector` | connector lane gated by `release-connectors.json` | real policy copied, mutated into `tmp_path`, `ALLOWLIST` monkeypatched | yes (real policy driven elsewhere) |
| 25 | `tests/architecture/test_settings_env_is_bootstrap_only.py` | `test_the_scan_would_notice_a_reintroduced_read` | only `seed_settings_from_env` reads the environment | `tmp_path` file | **yes** — a real-file positive already exists; weakest entry on this list |

### 1.1 Priority within the backlog

Ordered by how much a stale discovery would cost, highest first:

1. **Entries 2, 3, 4, 5, 9** — the guard's own discovery is an unasserted
   `rglob`/`skip`. These are the ones that can go green over an empty set today.
   An in-situ proof here is mostly one assertion (`the scan opened these real
   files`) plus one real-file positive.
2. **Entries 7 and 20** — the proof re-implements the production check inside the
   test. The re-implementation can drift from production silently, so the proof
   can stay green while the real guard rots. Fix by calling the production helper.
3. **Entries 1, 6, 16, 18, 21** — a real loop exists but is never shown firing.
4. **Everything else** — real-corpus discovery is already asserted in the same
   file; only the violating direction is synthetic. Cheapest to close, least
   urgent.

### 1.2 What "closing an entry" means

The shape proved workable in `dotmac_governance` (see
`docs/inventories/two-arm-correction-adjudication.md` § 9) is four steps:

1. assert the guard's **own** discovery reached a named real file;
2. inject a representative violation into that real corpus (bytes on disk inside
   `try/finally`, a rolled-back transaction, or a copy of the real object);
3. require the **real** classification path to fire and to NAME that real file;
4. restore, and prove the corpus is byte-identical and the tree Git-clean.

## 2. Guards that already carry an in-situ proof (the backlog is a delta)

`tests/test_rls_catalog.py` (`test_audit_flags_a_broken_table` — real
`CREATE TABLE` + `GRANT` in a rolled-back transaction),
`tests/test_module_schema_catalog.py`, `tests/test_platform_only_module_isolation.py`,
`tests/architecture/test_kernel_imports_without_a_database.py`,
`test_packages_import_without_a_database.py`, `test_imports_module.py`,
`test_manifest_declarations.py`, `test_module_catalog.py`,
`test_palette_ratchet.py`, `test_product_first_extraction.py`,
`test_session_authority.py`, `test_permission_seam_is_single.py`,
`test_presentation_boundary.py`, `test_integration_ingress_hygiene.py`
(`assert len(_sources()) >= 15` inside the proof itself),
`test_approval_workflow_source_audit.py`, `test_ui_release_contract.py`,
`test_test_database_is_loopback_bound.py`, `test_release_freshness_guard.py`,
`test_module_release_allowlist.py`, `test_files_module.py`,
`test_ticketing_module.py`, and the `.github`-probe half of
`test_workflow_action_pinning.py`.

## 3. Adjacent: guards with no sensitivity proof at all

Weaker than fixture-only in the direction that matters — nothing shows these
firing, ever. Several have a non-vacuity assertion, which is the partial
substitute:

* non-vacuity only — `tests/architecture/test_cache_scope.py`,
  `test_thin_wrappers.py`, `test_settings_typed_contract.py`,
  `test_no_orphan_settings.py` (allowlist accuracy only).
* no proof and no non-vacuity — `tests/architecture/test_route_guards.py`,
  `test_no_feature_rollback.py`, `test_vendored_fonts.py`,
  `test_lockfile_path_packages.py`, `test_root_version_sync.py`,
  `test_kernel_version_sync.py`, `test_integration_parity.py`,
  `test_party_archetype_names.py`.

## 4. Scope note

The brief estimated "about a dozen". The measured figure is **25 files / 41 proof
functions** fixture-only, plus 12 more with no firing proof at all. That is a
`dotmac_starter_mt` backlog to be scheduled on its own terms, in that repository,
by whoever owns ADR 0018 there. It is recorded here only because the survey was
produced as a side effect of the external-connector adjudication, and losing it
would cost more than writing it down.
