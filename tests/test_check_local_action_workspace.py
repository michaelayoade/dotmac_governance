"""Known-bad controls for the local-action workspace guard.

The port is only a port if it can be shown catching the defect it was ported
for. The two fixtures below are the measured shapes of
`michaelayoade/dotmac_platform_control_plane`'s `.github/workflows/
kernel-lock.yml`, read at `origin/main`
`522e2b0f702b529ea9a155daf2731bd4c1a95d57`:

- `PRE_REPAIR` -- one checkout, `ref: ${{ inputs.ref }}`, at the workspace
  root, followed by `uses: ./.github/actions/setup-poetry`, in a job holding
  `FORGEJO_READ_TOKEN`. The guard must be RED on it.
- `REPAIRED` -- `github.sha` owning the root, `inputs.ref` beside it at
  `path: work`, the same local action. The guard must be SILENT on it.

`PRE_REPAIR` is a PERMANENT negative control, kept for the same reason
`dotmac_platform_control_plane` kept its pre-repair drift comparison: a guard
observed only on trees that pass has not been shown to discriminate. Beside it,
`_blanket_local_action_exemption` re-implements the rule this replaced -- "a
`uses: ./...` is this repository's own code at this commit" -- and shows it
SILENT on the shape the new guard names. That exemption was not a bug in the
old check; it was a true-sounding premise that is false for exactly one shape,
which is why nothing caught it.

Then the three near-misses, which are where a check like this goes wrong. Each
is a shape that LOOKS like the defect and is not one, and each must stay
silent, because a guard that fires on the repaired shape teaches the fleet to
switch it off.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from check_local_action_workspace import (  # noqa: E402
    CALLER_CONTROLLED,
    NOT_COVERED,
    WorkspaceCheckError,
    _jobs,
    main,
    scan,
    scan_text,
    workflow_files,
)

CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
LOCAL_ACTION = "./.github/actions/setup-poetry"

#: The defect, as it stood before the repair.
PRE_REPAIR = f"""\
name: Kernel lock

on:
  workflow_dispatch:
    inputs:
      ref:
        required: true
        type: string

jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
          fetch-depth: 0

      - uses: {LOCAL_ACTION}

      - name: Resolve the kernel pin
        env:
          POETRY_HTTP_BASIC_FORGEJO_PASSWORD: ${{{{ secrets.FORGEJO_READ_TOKEN }}}}
        run: poetry lock
"""

#: The repair. The trusted commit owns the root; the ref under resolution is
#: beside it and is only ever read as data.
REPAIRED = f"""\
name: Kernel lock

on:
  workflow_dispatch:
    inputs:
      ref:
        required: true
        type: string

jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - name: Check out the tooling from the commit that defines this workflow
        uses: {CHECKOUT}
        with:
          ref: ${{{{ github.sha }}}}
          fetch-depth: 0

      - name: Check out the ref under resolution, beside the tooling
        uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
          path: work

      - uses: {LOCAL_ACTION}

      - name: Resolve the kernel pin
        working-directory: work
        env:
          POETRY_HTTP_BASIC_FORGEJO_PASSWORD: ${{{{ secrets.FORGEJO_READ_TOKEN }}}}
        run: poetry lock
"""


_OLD_USES = re.compile(r"^\s*-?\s*uses:\s*(?P<ref>[^\s#]+)")


def _blanket_local_action_exemption(text: str) -> list[str]:
    """The rule this replaced, re-implemented as a permanent negative control.

    `dotmac_platform_control_plane`'s action-pinning check reads every `uses:`
    and skips a local one with the comment "this repo's own code at this
    commit". That skip is reproduced here exactly, so the claim that the old
    rule could not see the pre-repair shape is a CHECK rather than an
    assertion. Everything it does report is a third-party reference, which is a
    different question entirely.
    """
    reported: list[str] = []
    for line in text.splitlines():
        match = _OLD_USES.match(line)
        if match is None:
            continue
        uses = match.group("ref").strip("'\"")
        if uses.startswith("./"):
            continue  # "this repository's own code at this commit"
        reported.append(uses)
    return reported


def _tree(text: str, name: str = "workflow.yml") -> Path:
    directory = Path(tempfile.mkdtemp())
    workflows = directory / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / name).write_text(text, encoding="utf-8")
    return directory


class ParityWithThePortedSubject(unittest.TestCase):
    """Red on the pre-repair shape, green on the repaired one."""

    def test_the_pre_repair_shape_is_named(self) -> None:
        findings = scan_text("kernel-lock.yml", PRE_REPAIR)
        self.assertEqual(len(findings), 1, findings)
        finding = findings[0]
        self.assertEqual(finding.job, "resolve")
        self.assertEqual(finding.action, LOCAL_ACTION)
        self.assertEqual(finding.ref_expression, "inputs.")
        self.assertIn("$GITHUB_WORKSPACE", finding.message())

    def test_the_repaired_shape_is_silent(self) -> None:
        self.assertEqual(scan_text("kernel-lock.yml", REPAIRED), [])

    def test_the_rule_this_replaced_could_not_see_the_pre_repair_shape(self) -> None:
        """Why the graduation was needed, as a check rather than as a claim."""
        old = _blanket_local_action_exemption(PRE_REPAIR)
        self.assertNotIn(LOCAL_ACTION, old)
        self.assertIn(CHECKOUT.split()[0], old, "the old rule read nothing at all")
        self.assertNotEqual(scan_text("kernel-lock.yml", PRE_REPAIR), [])


class TheNearMisses(unittest.TestCase):
    """Three shapes that resemble the defect and are not it."""

    def test_a_local_action_with_no_caller_supplied_ref_is_silent(self) -> None:
        text = f"""\
name: Checks
on: [push]
jobs:
  records:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
      - uses: {LOCAL_ACTION}
"""
        self.assertEqual(scan_text("checks.yml", text), [])

    def test_a_caller_supplied_ref_with_no_local_action_is_silent(self) -> None:
        text = f"""\
name: Dispatch
on:
  workflow_dispatch:
    inputs:
      ref:
        required: true
jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97
      - run: poetry lock
"""
        self.assertEqual(scan_text("dispatch.yml", text), [])

    def test_a_caller_supplied_ref_at_a_NON_root_path_is_silent(self) -> None:
        """The correct repaired shape, isolated from the rest of `REPAIRED`.

        This is the near-miss most likely to be got wrong, because a check
        looking for "a caller-supplied ref and a local action in one job" fires
        on it -- and that shape is the FIX. A guard that reports the fix is
        worse than absent.
        """
        text = f"""\
name: Dispatch
on:
  workflow_dispatch:
    inputs:
      ref:
        required: true
jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
          path: work
      - uses: {LOCAL_ACTION}
"""
        self.assertEqual(scan_text("dispatch.yml", text), [])


class ThePropertyIsPositionalAndPerJob(unittest.TestCase):
    def test_a_local_action_BEFORE_the_untrusted_checkout_is_silent(self) -> None:
        """The root still holds the default checkout when the action loads."""
        text = f"""\
name: Dispatch
on:
  workflow_dispatch:
    inputs:
      ref: {{}}
jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
      - uses: {LOCAL_ACTION}
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
"""
        self.assertEqual(scan_text("dispatch.yml", text), [])

    def test_a_trusted_checkout_takes_the_root_back(self) -> None:
        text = f"""\
name: Dispatch
on:
  workflow_dispatch:
    inputs:
      ref: {{}}
jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ github.sha }}}}
      - uses: {LOCAL_ACTION}
"""
        self.assertEqual(scan_text("dispatch.yml", text), [])

    def test_two_jobs_do_not_contaminate_each_other(self) -> None:
        """A workspace belongs to a job. A file-level scan would report this."""
        text = f"""\
name: Two
on:
  workflow_dispatch:
    inputs:
      ref: {{}}
jobs:
  fetches:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
  builds:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
      - uses: {LOCAL_ACTION}
"""
        self.assertEqual(scan_text("two.yml", text), [])

    def test_the_second_job_is_still_reported_when_it_IS_the_defect(self) -> None:
        """SENSITIVITY for the per-job split: it must isolate, not deafen."""
        text = f"""\
name: Two
on:
  workflow_dispatch:
    inputs:
      ref: {{}}
jobs:
  builds:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
      - uses: {LOCAL_ACTION}
  resolves:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
      - uses: {LOCAL_ACTION}
"""
        findings = scan_text("two.yml", text)
        self.assertEqual([finding.job for finding in findings], ["resolves"])


class TheCallerControlledSetIsDeclared(unittest.TestCase):
    #: One real expression per declared prefix. A mapping rather than a
    #: derivation, so that adding a prefix without exercising it fails the
    #: coverage assertion below instead of being silently sampled.
    SAMPLES = {
        "inputs.": "inputs.ref",
        "github.event.inputs.": "github.event.inputs.ref",
        "github.event.client_payload.": "github.event.client_payload.sha",
        "github.event.pull_request.head.": "github.event.pull_request.head.sha",
        "github.head_ref": "github.head_ref",
        "github.event.workflow_run.head_": "github.event.workflow_run.head_sha",
    }

    def test_the_sample_set_covers_every_declared_prefix(self) -> None:
        self.assertEqual(set(self.SAMPLES), set(CALLER_CONTROLLED))

    def test_every_declared_expression_is_caught(self) -> None:
        for prefix, expression in self.SAMPLES.items():
            text = f"""\
name: Dispatch
on: [workflow_dispatch]
jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ {expression} }}}}
      - uses: {LOCAL_ACTION}
"""
            with self.subTest(prefix=prefix):
                self.assertEqual(len(scan_text("d.yml", text)), 1, prefix)

    def test_the_events_own_ref_is_not_caller_supplied(self) -> None:
        """SENSITIVITY the other way. `github.sha` and `github.ref` are the
        trusted root of the repaired shape. A check that treated them as
        caller-supplied would fire on nearly every workflow in the fleet, and a
        guard that fires on everything is a guard nobody reads."""
        for expression in ("github.sha", "github.ref", "github.ref_name"):
            text = f"""\
name: Checks
on: [push]
jobs:
  records:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ {expression} }}}}
      - uses: {LOCAL_ACTION}
"""
            with self.subTest(expression=expression):
                self.assertEqual(scan_text("checks.yml", text), [])

    def test_a_step_level_key_spelled_ref_is_not_a_checkout_input(self) -> None:
        """`ref:` is caught under `with:` only. A block-wide search would
        report a job for a key that changes nothing about the workspace."""
        text = f"""\
name: Checks
on: [push]
jobs:
  records:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        ref: ${{{{ inputs.ref }}}}
      - uses: {LOCAL_ACTION}
"""
        self.assertEqual(scan_text("checks.yml", text), [])


class TheParserFoundSomething(unittest.TestCase):
    """A parser that returns nothing makes every assertion above pass."""

    def test_the_pre_repair_fixture_parses_into_the_shape_it_declares(self) -> None:
        jobs = _jobs(PRE_REPAIR)
        self.assertEqual([name for name, _ in jobs], ["resolve"])
        steps = jobs[0][1]
        self.assertEqual(len(steps), 3, steps)
        self.assertEqual(steps[0].ref, "${{ inputs.ref }}")
        self.assertIsNone(steps[0].path)
        self.assertEqual(steps[1].uses, LOCAL_ACTION)

    def test_the_repaired_fixture_parses_both_checkouts_and_the_path(self) -> None:
        steps = _jobs(REPAIRED)[0][1]
        self.assertEqual(len(steps), 4, steps)
        self.assertEqual(steps[0].ref, "${{ github.sha }}")
        self.assertIsNone(steps[0].path)
        self.assertEqual(steps[1].ref, "${{ inputs.ref }}")
        self.assertEqual(steps[1].path, "work")

    def test_the_parser_reads_this_repositorys_own_workflow(self) -> None:
        """NON-VACUITY against a real subject rather than a fixture built to
        parse. This repository's own workflow has one job, many steps, and a
        local action -- so all three code paths are exercised by production
        text, not only by text written beside the parser."""
        text = (REPO_ROOT / ".github/workflows/governance-checks.yml").read_text(
            encoding="utf-8"
        )
        jobs = _jobs(text)
        self.assertEqual([name for name, _ in jobs], ["records"])
        steps = jobs[0][1]
        self.assertGreaterEqual(len(steps), 12, len(steps))
        self.assertIn(
            "./.github/actions/standards-check", [step.uses for step in steps]
        )


class TheProductionTree(unittest.TestCase):
    def test_this_repository_is_clean_and_the_gate_is_currently_INERT(self) -> None:
        """Stated as what it is. No workflow here checks out a caller-supplied
        ref, so this assertion passes over an empty set and proves nothing
        about the guard -- which is exactly why every proof above is planted.
        The value of this gate is prospective: it fails the change that first
        introduces the shape."""
        self.assertEqual(scan(REPO_ROOT), [])

    def test_the_checker_exits_zero_on_this_repository(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/check_local_action_workspace.py"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_checker_exits_one_on_the_pre_repair_shape(self) -> None:
        root = _tree(PRE_REPAIR)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools/check_local_action_workspace.py"),
                "--root",
                str(root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("$GITHUB_WORKSPACE", result.stderr)


class TheClaimIsNarrowAndSaysSo(unittest.TestCase):
    """The boundary is DATA and reaches CI's output, not only a docstring."""

    def test_the_uncovered_families_are_declared(self) -> None:
        self.assertEqual(len(NOT_COVERED), 3)
        for family in ("run:", "plugin", "build backend"):
            self.assertTrue(any(family in entry for entry in NOT_COVERED), family)

    def test_the_success_message_names_every_uncovered_family(self) -> None:
        """A reader who sees only the green line must still see the boundary.
        This is the half that stops a narrow check being cited as a broad
        guarantee."""
        root = _tree(REPAIRED)
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "tools/check_local_action_workspace.py"),
                "--root",
                str(root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("NOTHING", result.stdout)
        for entry in NOT_COVERED:
            self.assertIn(entry, result.stdout)

    def test_a_run_step_executing_the_untrusted_tree_is_NOT_reported(self) -> None:
        """The boundary, as a check. This job is a real exposure and this guard
        is silent on it. Recorded so that nobody reads a green run as coverage
        of `run:` bodies."""
        text = f"""\
name: Dispatch
on:
  workflow_dispatch:
    inputs:
      ref: {{}}
jobs:
  resolve:
    runs-on: ubuntu-latest
    steps:
      - uses: {CHECKOUT}
        with:
          ref: ${{{{ inputs.ref }}}}
          path: work
      - env:
          TOKEN: ${{{{ secrets.FORGEJO_READ_TOKEN }}}}
        run: python work/scripts/kernel_lock.py evidence
"""
        self.assertEqual(scan_text("dispatch.yml", text), [])


class TheCorpusCannotBeBypassed(unittest.TestCase):
    def test_a_dot_yaml_workflow_is_discovered(self) -> None:
        """GitHub runs `.yaml` exactly as it runs `.yml`. A scanner reading one
        extension is bypassed by a valid file, which is a silent hole rather
        than mere laxity."""
        root = _tree(PRE_REPAIR, name="dispatch.yaml")
        self.assertEqual(len(workflow_files(root)), 1)
        self.assertEqual(len(scan(root)), 1)

    def test_a_nested_workflow_is_discovered(self) -> None:
        root = _tree(REPAIRED)
        nested = root / ".github" / "workflows" / "nested"
        nested.mkdir()
        (nested / "bad.yml").write_text(PRE_REPAIR, encoding="utf-8")
        self.assertEqual(len(scan(root)), 1)

    def test_a_tree_with_no_workflow_directory_REFUSES(self) -> None:
        """A guard that reports success when it found nothing to inspect does
        so exactly when something is unusual."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(WorkspaceCheckError):
                scan(Path(directory))
            self.assertEqual(main(["--root", directory]), 1)

    def test_an_empty_workflow_directory_REFUSES(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".github" / "workflows").mkdir(parents=True)
            with self.assertRaises(WorkspaceCheckError):
                scan(Path(directory))


if __name__ == "__main__":
    unittest.main()
