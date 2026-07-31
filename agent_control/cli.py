"""Command-line adapter for the shared agent-control engine."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .activation import activate_local, rollback_local
from .contracts import (
    BootstrapResult,
    ConformanceReport,
    DeploymentMode,
    DeploymentResult,
    DoctorReport,
    LocalActivationResult,
    ReconciliationReport,
    RollbackResult,
)
from .engine import (
    bootstrap_repository,
    doctor_repository,
    render_instructions,
    verify_repository,
)
from .managed import deploy_endpoint, reconcile_endpoint
from .profile import ProfileError, load_profile

DEFAULT_PROFILE = ".dotmac/agent-profile.json"
DEFAULT_POLICY = ".dotmac/managed-agent-policy.json"


def _root_and_profile(args: argparse.Namespace) -> tuple[Path, Path]:
    root = Path(args.root).resolve()
    profile = Path(args.profile)
    if not profile.is_absolute():
        profile = root / profile
    return root, profile


def _print_conformance(report: ConformanceReport) -> None:
    for diagnostic in report.diagnostics:
        location = f" [{diagnostic.path.as_posix()}]" if diagnostic.path else ""
        print(
            f"{diagnostic.severity.value}: {diagnostic.code.value}{location}: "
            f"{diagnostic.message}"
        )
    if report.conforms:
        print(
            f"ok: profile={report.profile_id} model={report.model_version} "
            f"revision={report.source_revision or 'unavailable'} "
            f"warnings={len(report.warnings)}"
        )
    else:
        print(
            f"failed: profile={report.profile_id} errors={len(report.errors)} "
            f"warnings={len(report.warnings)}"
        )


def _print_bootstrap(result: BootstrapResult) -> None:
    action = "applied" if result.applied else "planned"
    for category, paths in (
        ("create", result.created),
        ("update", result.updated),
        ("unchanged", result.unchanged),
        ("refused", result.refused),
    ):
        for path in paths:
            print(f"{action}: {category}: {path.as_posix()}")
    _print_conformance(result.report)


def _print_doctor(report: DoctorReport) -> None:
    _print_conformance(report.conformance)
    for client in report.clients:
        print(
            "client: "
            f"{client.surface.value}: executable={client.executable or 'not-found'} "
            f"version={client.version or 'unavailable'}"
        )
    print(
        "rollout: "
        f"mode={report.rollout_mode.value} "
        f"managed_configuration={str(report.managed_configuration).lower()} "
        f"blockers={len(report.blockers)}"
    )
    for blocker in report.blockers:
        print(f"blocker: {blocker}")


def _print_deployment(result: DeploymentResult) -> None:
    print(
        f"deployment: mode={result.mode.value} "
        f"endpoint={result.plan.endpoint.endpoint_id} "
        f"policy={result.plan.policy.policy_id}@{result.plan.policy.version} "
        f"activation_permitted="
        f"{str(result.plan.activation_permitted).lower()}"
    )
    for diagnostic in result.plan.diagnostics:
        print(
            f"{diagnostic.severity.value}: {diagnostic.code.value}: "
            f"{diagnostic.message}"
        )
    for action, paths in (
        ("created", result.created),
        ("unchanged", result.unchanged),
        ("refused", result.refused),
    ):
        for path in paths:
            print(f"{action}: {path.as_posix()}")


def _print_reconciliation(report: ReconciliationReport) -> None:
    print(
        f"reconciliation: endpoint={report.plan.endpoint.endpoint_id} "
        f"policy={report.plan.policy.policy_id}@{report.plan.policy.version} "
        f"artifacts_match={str(report.artifacts_match).lower()} "
        f"dependencies_available={str(report.dependencies_available).lower()} "
        f"activation_permitted={str(report.plan.activation_permitted).lower()} "
        f"ready_for_activation={str(report.ready_for_activation).lower()}"
    )
    for observation in report.observations:
        print(
            f"artifact: {observation.state.value}: "
            f"{observation.kind.value}: {observation.target.as_posix()}"
        )
    print(f"dependency: credential_environment={report.credential_environment.value}")
    for diagnostic in report.plan.diagnostics:
        print(
            f"{diagnostic.severity.value}: {diagnostic.code.value}: "
            f"{diagnostic.message}"
        )


def _print_activation(result: LocalActivationResult) -> None:
    print(
        f"activation: endpoint={result.plan.endpoint.endpoint_id} "
        f"policy={result.plan.policy.policy_id}@{result.plan.policy.version} "
        f"succeeded={str(result.succeeded).lower()} "
        f"backup_root={result.backup_root}"
    )
    for diagnostic in result.diagnostics:
        print(
            f"{diagnostic.severity.value}: {diagnostic.code.value}: "
            f"{diagnostic.message}"
        )
    for action, paths in (
        ("created", result.created),
        ("replaced", result.replaced),
        ("unchanged", result.unchanged),
        ("refused", result.refused),
    ):
        for path in paths:
            print(f"{action}: {path.as_posix()}")


def _print_rollback(result: RollbackResult) -> None:
    print(
        f"rollback: succeeded={str(result.succeeded).lower()} "
        f"manifest={result.manifest_path}"
    )
    for diagnostic in result.diagnostics:
        print(
            f"{diagnostic.severity.value}: {diagnostic.code.value}: "
            f"{diagnostic.message}"
        )
    for action, paths in (
        ("restored", result.restored),
        ("removed", result.removed),
        ("unchanged", result.unchanged),
        ("refused", result.refused),
    ):
        for path in paths:
            print(f"{action}: {path.as_posix()}")


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        default=".",
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help=f"profile path, relative to root by default (default: {DEFAULT_PROFILE})",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dotmac-agent",
        description=(
            "Bootstrap and verify structured Codex/Claude repository guidance "
            "from one Git-owned profile."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser(
        "verify",
        help="validate profile, instruction structure, rollout gates, and Git identity",
    )
    _add_common_arguments(verify)
    verify.add_argument("--format", choices=("text", "json"), default="text")

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="plan or apply idempotent repository instruction projections",
    )
    _add_common_arguments(bootstrap)
    bootstrap.add_argument(
        "--apply",
        action="store_true",
        help="write safe repository projections; endpoint policy is never installed",
    )
    bootstrap.add_argument("--format", choices=("text", "json"), default="text")

    doctor = subparsers.add_parser(
        "doctor",
        help="report conformance, client availability, and rollout blockers",
    )
    _add_common_arguments(doctor)
    doctor.add_argument("--format", choices=("text", "json"), default="text")

    render = subparsers.add_parser(
        "render",
        help="render one instruction projection to standard output",
    )
    _add_common_arguments(render)
    render.add_argument("--kind", choices=("agents", "claude"), required=True)

    deploy = subparsers.add_parser(
        "deploy",
        help=(
            "stage a content-addressed endpoint bundle; direct system activation "
            "fails closed"
        ),
    )
    deploy.add_argument(
        "--root",
        default=".",
        help="governance repository root (default: current directory)",
    )
    deploy.add_argument(
        "--policy",
        default=DEFAULT_POLICY,
        help=f"managed policy path (default: {DEFAULT_POLICY})",
    )
    deploy.add_argument(
        "--endpoint",
        required=True,
        help="checked endpoint-enrollment JSON path",
    )
    deploy.add_argument(
        "--output",
        required=True,
        help="directory for the staged, non-secret bundle",
    )
    deploy.add_argument(
        "--apply",
        action="store_true",
        help="request direct activation; currently refused by design",
    )
    deploy.add_argument("--format", choices=("text", "json"), default="text")

    reconcile = subparsers.add_parser(
        "reconcile",
        help="report desired-versus-observed endpoint state without changing it",
    )
    reconcile.add_argument(
        "--root",
        default=".",
        help="governance repository root (default: current directory)",
    )
    reconcile.add_argument(
        "--policy",
        default=DEFAULT_POLICY,
        help=f"managed policy path (default: {DEFAULT_POLICY})",
    )
    reconcile.add_argument(
        "--endpoint",
        required=True,
        help="checked endpoint-enrollment JSON path",
    )
    reconcile.add_argument(
        "--target-root",
        default="/",
        help="endpoint filesystem root or an offline mounted root (default: /)",
    )
    reconcile.add_argument("--format", choices=("text", "json"), default="text")

    activate = subparsers.add_parser(
        "activate-local",
        help="apply an accepted local pilot with mandatory backup and rollback manifest",
    )
    activate.add_argument(
        "--root",
        default=".",
        help="governance repository root (default: current directory)",
    )
    activate.add_argument(
        "--policy",
        default=DEFAULT_POLICY,
        help=f"managed policy path (default: {DEFAULT_POLICY})",
    )
    activate.add_argument(
        "--endpoint",
        required=True,
        help="accepted endpoint-enrollment JSON path",
    )
    activate.add_argument(
        "--backup-root",
        required=True,
        help="new or empty local directory for backup files and manifest",
    )
    activate.add_argument(
        "--migrate-existing",
        action="store_true",
        help="back up and replace reviewed existing instruction/configuration files",
    )
    activate.add_argument("--format", choices=("text", "json"), default="text")

    rollback = subparsers.add_parser(
        "rollback-local",
        help="restore an activation only when targets still match its manifest",
    )
    rollback.add_argument(
        "--manifest",
        required=True,
        help="activation manifest path",
    )
    rollback.add_argument("--format", choices=("text", "json"), default="text")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one CLI command and return a stable process exit code."""

    args = _parser().parse_args(argv)
    root = Path(getattr(args, "root", ".")).resolve()

    try:
        if args.command == "deploy":
            policy_path = Path(args.policy)
            endpoint_path = Path(args.endpoint)
            if not policy_path.is_absolute():
                policy_path = root / policy_path
            if not endpoint_path.is_absolute():
                endpoint_path = root / endpoint_path
            deployment = deploy_endpoint(
                policy_path,
                endpoint_path,
                root,
                Path(args.output),
                mode=(DeploymentMode.APPLY if args.apply else DeploymentMode.STAGE),
            )
            if args.format == "json":
                print(json.dumps(deployment.to_dict(), indent=2, sort_keys=True))
            else:
                _print_deployment(deployment)
            return 0 if deployment.succeeded else 1

        if args.command == "reconcile":
            policy_path = Path(args.policy)
            endpoint_path = Path(args.endpoint)
            if not policy_path.is_absolute():
                policy_path = root / policy_path
            if not endpoint_path.is_absolute():
                endpoint_path = root / endpoint_path
            reconciliation = reconcile_endpoint(
                policy_path,
                endpoint_path,
                root,
                Path(args.target_root),
            )
            if args.format == "json":
                print(
                    json.dumps(
                        reconciliation.to_dict(),
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                _print_reconciliation(reconciliation)
            return 0 if reconciliation.ready_for_activation else 1

        if args.command == "activate-local":
            policy_path = Path(args.policy)
            endpoint_path = Path(args.endpoint)
            if not policy_path.is_absolute():
                policy_path = root / policy_path
            if not endpoint_path.is_absolute():
                endpoint_path = root / endpoint_path
            activation = activate_local(
                policy_path,
                endpoint_path,
                root,
                Path(args.backup_root),
                migrate_existing=args.migrate_existing,
            )
            if args.format == "json":
                print(json.dumps(activation.to_dict(), indent=2, sort_keys=True))
            else:
                _print_activation(activation)
            return 0 if activation.succeeded else 1

        if args.command == "rollback-local":
            rollback = rollback_local(Path(args.manifest))
            if args.format == "json":
                print(json.dumps(rollback.to_dict(), indent=2, sort_keys=True))
            else:
                _print_rollback(rollback)
            return 0 if rollback.succeeded else 1

        _, profile_path = _root_and_profile(args)
        if args.command == "verify":
            report = verify_repository(profile_path, root)
            if args.format == "json":
                print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
            else:
                _print_conformance(report)
            return 0 if report.conforms else 1

        if args.command == "bootstrap":
            result = bootstrap_repository(
                profile_path,
                root,
                apply=args.apply,
            )
            if args.format == "json":
                print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            else:
                _print_bootstrap(result)
            return 0 if result.succeeded else 1

        if args.command == "doctor":
            doctor = doctor_repository(profile_path, root)
            if args.format == "json":
                print(json.dumps(doctor.to_dict(), indent=2, sort_keys=True))
            else:
                _print_doctor(doctor)
            return 0 if doctor.conformance.conforms else 1

        if args.command == "render":
            profile = load_profile(profile_path)
            rendered = render_instructions(profile)
            print(rendered.agents if args.kind == "agents" else rendered.claude, end="")
            return 0
    except (OSError, ProfileError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(f"error: unsupported command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
