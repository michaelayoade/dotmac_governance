"""Known-good and known-bad controls for the authority-cutover receipt registry.

Every guard in `tools/check_receipts.py` is proved by construction here: the
prohibited shape is built and the guard is observed firing on it. A validator
asserted only against the production tree proves that the production tree is
currently clean, which is a different and much weaker statement.

The two that matter most, because they are the ones a plausible implementation
gets wrong:

- **Rename plus rewrite.** A diff reader sees one deletion and one addition,
  and an addition is exactly what this registry is for. The test moves a
  receipt to a new name AND changes its contents, and the guard must still
  fire.
- **A registry with zero receipts.** Every structural check over an empty
  directory holds trivially. The guard must report `not_applicable`, never
  `executed_passed` — otherwise the first green result means "nothing was
  measured" while reading as "the discipline is evidenced".
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from check_receipts import (  # noqa: E402
    RECEIPT_DIR,
    GateVerdict,
    RegistryError,
    load_registry,
    merge_base,
    validate_registry,
)

COMMIT_A = "1111111111111111111111111111111111111111"
COMMIT_B = "2222222222222222222222222222222222222222"
DIGEST_A = "sha256:" + "ab" * 32


def receipt(**overrides: Any) -> dict[str, Any]:
    """A valid envelope. Every known-bad case below is this, minus one thing."""
    body: dict[str, Any] = {
        "schema_version": 1,
        "receipt_id": "sub-chat-authority-to-selfcare",
        "old_authority": {
            "system": "dotmac_crm",
            "resource": "live-chat routing decision for subscriber conversations",
        },
        "new_authority": {
            "system": "dotmac_sub",
            "resource": "live-chat routing decision for subscriber conversations",
        },
        "coordinates": {
            "old": {"repository": "michaelayoade/dotmac_crm", "commit": COMMIT_A},
            "new": {"repository": "michaelayoade/dotmac_sub", "commit": COMMIT_B},
        },
        "effective_time": "2026-08-30T09:15:00Z",
        "runtime_evidence_digest": DIGEST_A,
        "old_writer_retirement_status": {
            "status": "still_live",
            "owner": "Michael Ayoade",
            "retirement_condition": "CHAT_LIVE_ENABLED removed from production",
        },
    }
    body.update(overrides)
    return body


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )


class RegistryFixture:
    """A throwaway Git repository holding a receipt registry."""

    def __init__(self, stack: tempfile.TemporaryDirectory[str]) -> None:
        self.root = Path(stack.name)
        (self.root / RECEIPT_DIR).mkdir(parents=True, exist_ok=True)
        _git(self.root, "init", "-q", "-b", "main")
        _git(self.root, "config", "user.email", "test@example.invalid")
        _git(self.root, "config", "user.name", "Test")
        _git(self.root, "config", "commit.gpgsign", "false")

    def write(self, name: str, body: dict[str, Any] | str) -> None:
        raw = body if isinstance(body, str) else json.dumps(body, indent=2) + "\n"
        (self.root / RECEIPT_DIR / name).write_text(raw, encoding="utf-8")

    def remove(self, name: str) -> None:
        (self.root / RECEIPT_DIR / name).unlink()

    def commit(self, message: str) -> None:
        _git(self.root, "add", "-A")
        _git(self.root, "commit", "-q", "-m", message)

    def branch(self, name: str) -> None:
        _git(self.root, "checkout", "-q", "-b", name)


class ReceiptRegistryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._stack = tempfile.TemporaryDirectory()
        self.addCleanup(self._stack.cleanup)
        self.fixture = RegistryFixture(self._stack)

    def verdict(self, base: str | None = None) -> tuple[GateVerdict, list[str]]:
        return validate_registry(self.fixture.root, base)

    def assertFires(self, needle: str, base: str | None = None) -> None:
        result, errors = self.verdict(base)
        self.assertIs(result, GateVerdict.EXECUTED_FAILED, f"errors: {errors}")
        joined = "\n".join(errors)
        self.assertIn(needle, joined)

    # ---------------------------------------------------------------- happy

    def test_a_valid_receipt_passes(self) -> None:
        self.fixture.write("sub-chat-authority-to-selfcare.json", receipt())
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    def test_an_optional_pointer_and_supersedes_are_accepted(self) -> None:
        self.fixture.write("sub-chat-authority-to-selfcare.json", receipt())
        self.fixture.write(
            "sub-chat-authority-to-selfcare-retired.json",
            receipt(
                receipt_id="sub-chat-authority-to-selfcare-retired",
                supersedes_receipt="sub-chat-authority-to-selfcare",
                private_evidence_pointer="bao://secret/dotmac/sub/chat-cutover-evidence",
                old_writer_retirement_status={
                    "status": "retired",
                    "revision": COMMIT_B,
                },
            ),
        )
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    # -------------------------------------------------------- non-vacuity

    def test_an_empty_registry_is_not_applicable_and_never_passes(self) -> None:
        """The registry validator over an empty directory passes for the wrong reason.

        Every structural check below holds vacuously at zero receipts. If this
        returned `executed_passed` the very first green result would mean
        "nothing was measured" while reading as "the discipline is evidenced",
        so the verdict has to be able to say so.
        """
        result, errors = self.verdict()
        self.assertEqual(errors, [])
        self.assertIs(result, GateVerdict.NOT_APPLICABLE)
        self.assertIsNot(result, GateVerdict.EXECUTED_PASSED)

    def test_a_missing_registry_directory_is_refused(self) -> None:
        (self.fixture.root / RECEIPT_DIR).rmdir()
        self.assertFires("does not exist")

    def test_the_production_registry_parses(self) -> None:
        """The checked-in registry is readable and internally consistent.

        The expected verdict is derived from occupancy rather than hardcoded,
        so this stays honest on the day the first receipt lands: empty means
        `not_applicable`, and only a populated registry may report
        `executed_passed`.
        """
        files = load_registry(REPO_ROOT)
        verdict, errors = validate_registry(REPO_ROOT, None)
        self.assertEqual(errors, [])
        self.assertIs(
            verdict,
            GateVerdict.EXECUTED_PASSED if files else GateVerdict.NOT_APPLICABLE,
        )

    # ------------------------------------------------------------ envelope

    def test_a_missing_required_field_fires(self) -> None:
        body = receipt()
        del body["runtime_evidence_digest"]
        self.fixture.write("sub-chat-authority-to-selfcare.json", body)
        self.assertFires("required field 'runtime_evidence_digest' is missing")

    def test_every_required_field_is_individually_load_bearing(self) -> None:
        """Removing any one required field must fail. A guard that only notices
        some of them is a guard whose completeness nobody can see."""
        for field in (
            "schema_version",
            "receipt_id",
            "old_authority",
            "new_authority",
            "coordinates",
            "effective_time",
            "runtime_evidence_digest",
            "old_writer_retirement_status",
        ):
            with self.subTest(field=field):
                body = receipt()
                del body[field]
                self.fixture.write("sub-chat-authority-to-selfcare.json", body)
                result, errors = self.verdict()
                self.assertIs(result, GateVerdict.EXECUTED_FAILED, f"{field}: {errors}")

    def test_a_field_outside_the_envelope_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(rollback_boundary="four hours, then irreversible"),
        )
        self.assertFires("outside the declared envelope")

    def test_an_authority_without_a_resource_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(old_authority={"system": "dotmac_crm"}),
        )
        self.assertFires("old_authority.resource is missing")

    def test_a_branch_name_is_not_a_coordinate(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(
                coordinates={
                    "old": {"repository": "michaelayoade/dotmac_crm", "commit": "main"},
                    "new": {
                        "repository": "michaelayoade/dotmac_sub",
                        "commit": COMMIT_B,
                    },
                }
            ),
        )
        self.assertFires("a branch name or floating alias")

    def test_an_unpeeled_tag_is_not_a_coordinate(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(
                coordinates={
                    "old": {
                        "repository": "michaelayoade/dotmac_crm",
                        "commit": "v1.4.2",
                    },
                    "new": {
                        "repository": "michaelayoade/dotmac_sub",
                        "commit": COMMIT_B,
                    },
                }
            ),
        )
        self.assertFires("an unpeeled tag or version string")

    def test_an_image_tag_is_not_a_coordinate(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(
                coordinates={
                    "old": {
                        "repository": "michaelayoade/dotmac_crm",
                        "commit": "ghcr.io/dotmac/crm:2026.08",
                    },
                    "new": {
                        "repository": "michaelayoade/dotmac_sub",
                        "commit": COMMIT_B,
                    },
                }
            ),
        )
        self.assertFires("an image tag")

    def test_a_non_utc_effective_time_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(effective_time="2026-08-30T09:15:00+01:00"),
        )
        self.assertFires("effective_time")

    def test_an_evidence_artefact_in_place_of_a_digest_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(runtime_evidence_digest="barrier engaged at 09:15 for 412 rows"),
        )
        self.assertFires("runtime_evidence_digest must be")

    def test_a_receipt_id_that_disagrees_with_its_filename_fires(self) -> None:
        self.fixture.write("some-other-name.json", receipt())
        self.assertFires("the filename says")

    def test_a_wrong_schema_version_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json", receipt(schema_version=2)
        )
        self.assertFires("schema_version must be 1")

    def test_a_non_json_receipt_fires(self) -> None:
        self.fixture.write("sub-chat-authority-to-selfcare.json", "{not json")
        self.assertFires("is not valid JSON")

    def test_an_undeclared_file_in_the_registry_fires(self) -> None:
        (self.fixture.root / RECEIPT_DIR / "notes.txt").write_text(
            "x", encoding="utf-8"
        )
        self.assertFires("one JSON receipt per file")

    # ------------------------------------------------------- retirement

    def test_a_boolean_retirement_status_fires(self) -> None:
        """The failure the field exists to prevent, reintroduced by the schema."""
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(old_writer_retirement_status=True),
        )
        self.assertFires("is a boolean")

    def test_an_absent_retirement_status_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(old_writer_retirement_status={}),
        )
        self.assertFires("Absence is not a status")

    def test_a_status_outside_the_vocabulary_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(old_writer_retirement_status={"status": "probably_fine"}),
        )
        self.assertFires("expected one of retired, transferred, still_live")

    def test_a_status_with_no_detail_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(old_writer_retirement_status={"status": "retired"}),
        )
        self.assertFires("names no revision")

    def test_a_retired_status_needs_an_immutable_revision(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(
                old_writer_retirement_status={"status": "retired", "revision": "main"}
            ),
        )
        self.assertFires("not a peeled 40-character commit")

    # ----------------------------------------------------------- secrets

    def test_an_inlined_secret_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(private_evidence_pointer="ghp_" + "a" * 36),
        )
        self.assertFires("possible literal secret found")

    def test_a_private_key_anywhere_in_the_envelope_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(
                old_authority={
                    "system": "dotmac_crm",
                    "resource": "-----BEGIN PRIVATE KEY-----",
                }
            ),
        )
        self.assertFires("possible literal secret found")

    def test_a_pointer_holding_a_value_rather_than_an_address_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(private_evidence_pointer="the password is in the runbook"),
        )
        self.assertFires("not an approved pointer")

    # ------------------------------------------------------ supersession

    def test_superseding_a_receipt_that_does_not_exist_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(supersedes_receipt="never-written"),
        )
        self.assertFires("is not a receipt in this registry")

    def test_a_receipt_superseding_itself_fires(self) -> None:
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(supersedes_receipt="sub-chat-authority-to-selfcare"),
        )
        self.assertFires("supersedes itself")

    def test_two_live_heads_on_one_chain_fire(self) -> None:
        self.fixture.write("sub-chat-authority-to-selfcare.json", receipt())
        for name in ("correction-one", "correction-two"):
            self.fixture.write(
                f"{name}.json",
                receipt(
                    receipt_id=name,
                    supersedes_receipt="sub-chat-authority-to-selfcare",
                ),
            )
        self.assertFires("two live heads")

    def test_a_cyclic_chain_fires(self) -> None:
        self.fixture.write(
            "receipt-one.json",
            receipt(receipt_id="receipt-one", supersedes_receipt="receipt-two"),
        )
        self.fixture.write(
            "receipt-two.json",
            receipt(receipt_id="receipt-two", supersedes_receipt="receipt-one"),
        )
        self.assertFires("cyclic")

    # ------------------------------------------------------- append-only

    def _seed(self) -> None:
        self.fixture.write("sub-chat-authority-to-selfcare.json", receipt())
        self.fixture.commit("seed the registry")
        self.fixture.branch("change")

    def test_adding_a_receipt_is_allowed(self) -> None:
        self._seed()
        self.fixture.write("second-cutover.json", receipt(receipt_id="second-cutover"))
        self.assertEqual(self.verdict("main"), (GateVerdict.EXECUTED_PASSED, []))

    def test_editing_an_existing_receipt_fires(self) -> None:
        self._seed()
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(effective_time="2026-08-31T09:15:00Z"),
        )
        self.assertFires("differs from its bytes at the merge base", base="main")

    def test_a_whitespace_only_edit_still_fires(self) -> None:
        """Bytes, not semantics. A receipt is addressed by its content."""
        self._seed()
        path = self.fixture.root / RECEIPT_DIR / "sub-chat-authority-to-selfcare.json"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertFires("differs from its bytes at the merge base", base="main")

    def test_deleting_an_existing_receipt_fires(self) -> None:
        self._seed()
        self.fixture.remove("sub-chat-authority-to-selfcare.json")
        self.assertFires("existed at the merge base", base="main")

    def test_a_rename_plus_a_rewrite_fires(self) -> None:
        """The case a diff reader cannot see.

        Moving the file to a new name and changing its contents presents as one
        deletion and one addition. An addition is exactly what this registry is
        for, so a guard reading the diff's SHAPE reports a clean append while a
        receipt has in fact been rewritten out of existence. Comparing bytes
        against the merge base is what catches it.
        """
        self._seed()
        self.fixture.remove("sub-chat-authority-to-selfcare.json")
        self.fixture.write(
            "sub-chat-authority-to-selfcare-v2.json",
            receipt(
                receipt_id="sub-chat-authority-to-selfcare-v2",
                effective_time="2026-08-31T09:15:00Z",
            ),
        )
        self.assertFires("existed at the merge base", base="main")

    # -------------------------------------------------------- fail closed

    def test_an_unresolvable_base_is_refused_rather_than_passed(self) -> None:
        self._seed()
        self.assertFires("does not resolve to a commit", base="no-such-ref")

    def test_an_empty_base_ref_is_refused(self) -> None:
        self._seed()
        self.assertFires("no base ref was supplied", base="")

    def test_merge_base_raises_rather_than_guessing(self) -> None:
        self._seed()
        with self.assertRaises(RegistryError):
            merge_base(self.fixture.root, "no-such-ref")

    def test_no_base_runs_the_envelope_arm_and_says_so(self) -> None:
        """`--no-base` narrows the scope; it does not turn a failure green."""
        self._seed()
        self.fixture.write(
            "sub-chat-authority-to-selfcare.json",
            receipt(effective_time="2026-08-31T09:15:00Z"),
        )
        self.assertEqual(self.verdict(None), (GateVerdict.EXECUTED_PASSED, []))
        self.assertFires("differs from its bytes at the merge base", base="main")


if __name__ == "__main__":
    unittest.main()
