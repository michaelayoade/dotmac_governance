"""Known-good and known-bad controls for the Foundation bridge evidence."""

from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from standards_control import foundation_bootstrap as bootstrap


class FoundationBootstrapTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = (
            Path(__file__).parents[1] / "policies/foundation-profile-bootstrap.json"
        )
        self.body = json.loads(self.policy.read_text(encoding="utf-8"))

    @staticmethod
    def _source(*, complete: bool = True) -> bytes:
        lines = [b"class ApplicationFoundationProfile: pass"]
        if complete:
            lines.extend(
                [
                    b"def canonical_profile_bytes(): pass",
                    b"def profile_digest(): pass",
                    b"def verify_profile_against_candidate(): pass",
                    b"def require_profile_readback(): pass",
                ]
            )
        return b"\n".join(lines)

    def _wheel(
        self,
        directory: str,
        record: bootstrap.FoundationContractBootstrap,
        source: bytes,
        *,
        extra: str | None = None,
    ) -> Path:
        wheel = Path(directory) / record.wheel_filename
        with zipfile.ZipFile(wheel, "w") as archive:
            if extra is not None:
                archive.writestr(extra, b"x = 1")
            archive.writestr(record.wheel_member, source)
        return wheel

    def _synthetic_record(
        self, wheel: Path, source: bytes, record: bootstrap.FoundationContractBootstrap
    ) -> bootstrap.FoundationContractBootstrap:
        return replace(
            record,
            wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(),
            contract_sha256=hashlib.sha256(source).hexdigest(),
            contract_size=len(source),
        )

    @staticmethod
    def _zip_bytes(members: dict[str, bytes]) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        return stream.getvalue()

    @staticmethod
    def _receipt(record: bootstrap.FoundationContractBootstrap) -> bytes:
        return json.dumps(
            {
                "artifact_id": str(record.candidate_artifact_id),
                "artifact_size_bytes": record.candidate_archive_size,
                "expires_at": record.evidence_expires_at,
                "facility": "dotmac-deployment-foundation",
                "filename": record.wheel_filename,
                "published": False,
                "repository": "michaelayoade/dotmac_starter_mt",
                "retention_requested_days": record.receipt_retention_days,
                "run_id": str(record.run_id),
                "schema": "CandidateArtifact.v1",
                "sdist": {
                    "filename": record.sdist_filename,
                    "sha256": record.sdist_sha256,
                    "size_bytes": record.sdist_size,
                },
                "sha256": record.wheel_sha256,
                "size_bytes": record.wheel_size,
                "source_sha": record.source_commit,
                "tagged": False,
                "version": record.candidate_version,
            },
            separators=(",", ":"),
        ).encode()

    def test_valid_record_and_materialized_wheel(self) -> None:
        record = bootstrap.load_foundation_bootstrap(self.body)
        source = self._source()
        with tempfile.TemporaryDirectory() as directory:
            wheel = self._wheel(directory, record, source)
            synthetic = self._synthetic_record(wheel, source, record)
            bootstrap._verify_materialized_wheel(
                synthetic, wheel, as_of=datetime(2026, 9, 5, tzinfo=UTC)
            )

    def test_immutable_full_commit_and_digests(self) -> None:
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap(
                {**self.body, "source_commit": "0" * 40}
            )
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap(
                {**self.body, "run_source_commit": "0" * 40}
            )
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap({**self.body, "wheel_sha256": "0" * 64})
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap({**self.body, "sdist_sha256": "0" * 64})
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap(
                {**self.body, "candidate_archive_digest": "sha256:" + "0" * 64}
            )
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap(
                {**self.body, "receipt_sha256": "0" * 64}
            )

    def test_exact_false_claims_and_proposed_cannot_authorize_adoption(self) -> None:
        record = bootstrap.load_foundation_bootstrap(self.body)
        self.assertEqual(record.status, "proposed")
        self.assertEqual(
            record.claims,
            (
                ("released", False),
                ("published", False),
                ("installed", False),
                ("runtime_adoption_authorized", False),
            ),
        )
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap({**self.body, "status": "accepted"})
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap(
                {
                    **self.body,
                    "claims": {
                        **self.body["claims"],
                        "runtime_adoption_authorized": True,
                    },
                }
            )

    def test_materialized_wheel_refusals_are_distinct(self) -> None:
        record = bootstrap.load_foundation_bootstrap(self.body)
        with tempfile.TemporaryDirectory() as directory:
            source = self._source()
            wheel = self._wheel(directory, record, source)
            synthetic = self._synthetic_record(wheel, source, record)
            wrong_hash = replace(synthetic, wheel_sha256="0" * 64)
            with self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "wheel SHA-256"
            ):
                bootstrap._verify_materialized_wheel(
                    wrong_hash, wheel, as_of=datetime(2026, 9, 5, tzinfo=UTC)
                )

            missing = Path(directory) / "missing.whl"
            with zipfile.ZipFile(missing, "w") as archive:
                archive.writestr("other.py", source)
            missing_record = replace(
                synthetic, wheel_sha256=hashlib.sha256(missing.read_bytes()).hexdigest()
            )
            missing_record = replace(missing_record, wheel_filename=missing.name)
            with self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "missing the contract member"
            ):
                bootstrap._verify_materialized_wheel(
                    missing_record, missing, as_of=datetime(2026, 9, 5, tzinfo=UTC)
                )

            changed = replace(synthetic, contract_sha256="0" * 64)
            with self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "contract member SHA-256"
            ):
                bootstrap._verify_materialized_wheel(
                    changed, wheel, as_of=datetime(2026, 9, 5, tzinfo=UTC)
                )

            incomplete = self._source(complete=False)
            incomplete_wheel = self._wheel(directory, record, incomplete)
            incomplete_record = self._synthetic_record(
                incomplete_wheel, incomplete, record
            )
            with self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "missing named symbols"
            ):
                bootstrap._verify_materialized_wheel(
                    incomplete_record,
                    incomplete_wheel,
                    as_of=datetime(2026, 9, 5, tzinfo=UTC),
                )

            unsafe_wheel = self._wheel(directory, record, source, extra="../unsafe.py")
            unsafe_record = self._synthetic_record(unsafe_wheel, source, record)
            with self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "unsafe ZIP"
            ):
                bootstrap._verify_materialized_wheel(
                    unsafe_record, unsafe_wheel, as_of=datetime(2026, 9, 5, tzinfo=UTC)
                )

    def test_naive_and_expired_as_of_are_refused(self) -> None:
        record = bootstrap.load_foundation_bootstrap(self.body)
        with tempfile.TemporaryDirectory() as directory:
            source = self._source()
            wheel = self._wheel(directory, record, source)
            synthetic = self._synthetic_record(wheel, source, record)
            with self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "timezone-aware"
            ):
                bootstrap._verify_materialized_wheel(
                    synthetic, wheel, as_of=datetime(2026, 9, 5)
                )
            with self.assertRaisesRegex(bootstrap.FoundationBootstrapError, "expired"):
                bootstrap._verify_materialized_wheel(
                    synthetic,
                    wheel,
                    as_of=datetime(2026, 12, 3, 21, 13, 17, tzinfo=UTC),
                )

    def test_public_entry_points_have_fixed_inputs_and_clock(self) -> None:
        with self.assertRaises(TypeError):
            bootstrap.verify_materialized_wheel(  # type: ignore[call-arg]
                Path("candidate.whl"), self.body
            )
        with self.assertRaises(TypeError):
            bootstrap.verify_materialized_evidence(  # type: ignore[call-arg]
                Path("candidate.zip"), Path("receipt.zip"), datetime.now(UTC)
            )
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / self.body["wheel_filename"]
            wheel.write_bytes(b"synthetic")
            with (
                patch.object(
                    bootstrap,
                    "_utc_now",
                    return_value=datetime(2026, 12, 3, 21, 13, 17, tzinfo=UTC),
                ),
                patch.object(
                    Path, "stat", return_value=SimpleNamespace(st_size=449612)
                ),
            ):
                with self.assertRaisesRegex(
                    bootstrap.FoundationBootstrapError, "expired"
                ):
                    bootstrap.verify_materialized_wheel(wheel)

    def test_public_size_gates_precede_read_bytes(self) -> None:
        record = bootstrap.load_foundation_bootstrap(self.body)
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory) / record.wheel_filename
            candidate = Path(directory) / "candidate.zip"
            receipt = Path(directory) / "receipt.zip"
            cases: tuple[tuple[Path, int, Callable[[], None]], ...] = (
                (
                    wheel,
                    record.wheel_size + 1,
                    lambda: bootstrap.verify_materialized_wheel(wheel),
                ),
                (
                    candidate,
                    record.candidate_archive_size + 1,
                    lambda: bootstrap.verify_materialized_evidence(candidate, receipt),
                ),
            )
            for path, size, call in cases:
                path.write_bytes(b"wrong")
                with (
                    patch.object(
                        Path,
                        "read_bytes",
                        side_effect=AssertionError("read_bytes called"),
                    ),
                    patch.object(
                        Path, "stat", return_value=SimpleNamespace(st_size=size)
                    ),
                    self.assertRaisesRegex(bootstrap.FoundationBootstrapError, "size"),
                ):
                    call()
            candidate.write_bytes(b"candidate")
            receipt.write_bytes(b"receipt")
            with (
                patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("read_bytes called"),
                ),
                patch.object(
                    Path,
                    "stat",
                    autospec=True,
                    side_effect=lambda self: SimpleNamespace(
                        st_size=(
                            record.candidate_archive_size
                            if self == candidate
                            else record.receipt_archive_size + 1
                        )
                    ),
                ),
                self.assertRaisesRegex(
                    bootstrap.FoundationBootstrapError, "receipt archive size"
                ),
            ):
                bootstrap.verify_materialized_evidence(candidate, receipt)

    def test_receipt_linkage_shape_and_archive_members_are_closed(self) -> None:
        record = bootstrap.load_foundation_bootstrap(self.body)
        receipt = self._receipt(record)
        with self.assertRaisesRegex(
            bootstrap.FoundationBootstrapError, "receipt file size"
        ):
            bootstrap._verify_receipt(record, receipt)
        with self.assertRaisesRegex(bootstrap.FoundationBootstrapError, "linkage"):
            bootstrap._verify_receipt(
                replace(
                    record,
                    receipt_file_size=2,
                    receipt_sha256=hashlib.sha256(b"{}").hexdigest(),
                ),
                b"{}",
            )

    def test_synthetic_archives_bind_candidate_and_receipt(self) -> None:
        base = bootstrap.load_foundation_bootstrap(self.body)
        contract = self._source()
        wheel = self._zip_bytes({base.wheel_member: contract})
        sdist = b"synthetic sdist"
        candidate = self._zip_bytes(
            {base.wheel_filename: wheel, base.sdist_filename: sdist}
        )
        candidate_record = replace(
            base,
            wheel_size=len(wheel),
            wheel_sha256=hashlib.sha256(wheel).hexdigest(),
            contract_sha256=hashlib.sha256(contract).hexdigest(),
            contract_size=len(contract),
            sdist_size=len(sdist),
            sdist_sha256=hashlib.sha256(sdist).hexdigest(),
            candidate_archive_size=len(candidate),
            candidate_archive_digest="sha256:" + hashlib.sha256(candidate).hexdigest(),
        )
        receipt = self._receipt(candidate_record)
        receipt_archive = self._zip_bytes({base.receipt_filename: receipt})
        record = replace(
            candidate_record,
            receipt_file_size=len(receipt),
            receipt_sha256=hashlib.sha256(receipt).hexdigest(),
            receipt_archive_size=len(receipt_archive),
            receipt_archive_digest="sha256:"
            + hashlib.sha256(receipt_archive).hexdigest(),
        )
        bootstrap._verify_materialized_evidence_bytes(
            record,
            candidate,
            receipt_archive,
            as_of=datetime(2026, 9, 5, tzinfo=UTC),
        )
        with self.assertRaisesRegex(
            bootstrap.FoundationBootstrapError, "candidate archive digest"
        ):
            bootstrap._verify_materialized_evidence_bytes(
                replace(record, candidate_archive_digest="sha256:" + "0" * 64),
                candidate,
                receipt_archive,
                as_of=datetime(2026, 9, 5, tzinfo=UTC),
            )
        receipt_value = json.loads(receipt)
        mutations = {
            "source_sha": "0" * 40,
            "run_id": "0",
            "artifact_id": "0",
            "filename": "wrong.whl",
            "sha256": "0" * 64,
            "size_bytes": 1,
            "sdist": {
                "filename": record.sdist_filename,
                "sha256": "0" * 64,
                "size_bytes": record.sdist_size,
            },
        }
        for field, value in mutations.items():
            planted = dict(receipt_value)
            planted[field] = value
            planted_bytes = json.dumps(planted, separators=(",", ":")).encode()
            planted_archive = self._zip_bytes({record.receipt_filename: planted_bytes})
            planted_record = replace(
                record,
                receipt_file_size=len(planted_bytes),
                receipt_sha256=hashlib.sha256(planted_bytes).hexdigest(),
                receipt_archive_size=len(planted_archive),
                receipt_archive_digest="sha256:"
                + hashlib.sha256(planted_archive).hexdigest(),
            )
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(bootstrap.FoundationBootstrapError, "linkage"),
            ):
                bootstrap._verify_materialized_evidence_bytes(
                    planted_record,
                    candidate,
                    planted_archive,
                    as_of=datetime(2026, 9, 5, tzinfo=UTC),
                )

    def test_outer_zip_member_sizes_refuse_before_read(self) -> None:
        base = bootstrap.load_foundation_bootstrap(self.body)
        contract = self._source()
        wheel = self._zip_bytes({base.wheel_member: contract})
        sdist = b"synthetic sdist"
        candidate = self._zip_bytes(
            {base.wheel_filename: wheel, base.sdist_filename: sdist}
        )
        candidate_record = replace(
            base,
            wheel_size=len(wheel),
            wheel_sha256=hashlib.sha256(wheel).hexdigest(),
            contract_sha256=hashlib.sha256(contract).hexdigest(),
            contract_size=len(contract),
            sdist_size=len(sdist),
            sdist_sha256=hashlib.sha256(sdist).hexdigest(),
            candidate_archive_size=len(candidate),
            candidate_archive_digest="sha256:" + hashlib.sha256(candidate).hexdigest(),
        )
        receipt = self._receipt(candidate_record)
        receipt_archive = self._zip_bytes({base.receipt_filename: receipt})
        record = replace(
            candidate_record,
            receipt_file_size=len(receipt),
            receipt_sha256=hashlib.sha256(receipt).hexdigest(),
            receipt_archive_size=len(receipt_archive),
            receipt_archive_digest="sha256:"
            + hashlib.sha256(receipt_archive).hexdigest(),
        )

        def info(filename: str, size: int) -> zipfile.ZipInfo:
            result = zipfile.ZipInfo(filename)
            result.file_size = size
            return result

        oversized_wheel = info(record.wheel_filename, record.wheel_size + 1)
        exact_sdist = info(record.sdist_filename, record.sdist_size)
        candidate_archive_mock = MagicMock()
        candidate_archive_mock.infolist.return_value = (oversized_wheel, exact_sdist)
        candidate_archive_mock.getinfo.side_effect = {
            record.wheel_filename: oversized_wheel,
            record.sdist_filename: exact_sdist,
        }.get
        candidate_archive_mock.read.side_effect = AssertionError("read called")
        candidate_context = MagicMock()
        candidate_context.__enter__.return_value = candidate_archive_mock
        with (
            patch.object(zipfile, "ZipFile", return_value=candidate_context),
            self.assertRaisesRegex(bootstrap.FoundationBootstrapError, "wheel size"),
        ):
            bootstrap._verify_materialized_evidence_bytes(
                record,
                candidate,
                receipt_archive,
                as_of=datetime(2026, 9, 5, tzinfo=UTC),
            )
        candidate_archive_mock.read.assert_not_called()

        exact_wheel = info(record.wheel_filename, record.wheel_size)
        candidate_archive_mock = MagicMock()
        candidate_archive_mock.infolist.return_value = (exact_wheel, exact_sdist)
        candidate_archive_mock.getinfo.side_effect = {
            record.wheel_filename: exact_wheel,
            record.sdist_filename: exact_sdist,
        }.get
        candidate_archive_mock.read.side_effect = {
            exact_wheel: wheel,
            exact_sdist: sdist,
        }.get
        candidate_context = MagicMock()
        candidate_context.__enter__.return_value = candidate_archive_mock
        oversized_receipt = info(record.receipt_filename, record.receipt_file_size + 1)
        receipt_archive_mock = MagicMock()
        receipt_archive_mock.infolist.return_value = (oversized_receipt,)
        receipt_archive_mock.getinfo.return_value = oversized_receipt
        receipt_archive_mock.read.side_effect = AssertionError("read called")
        receipt_context = MagicMock()
        receipt_context.__enter__.return_value = receipt_archive_mock
        with (
            patch.object(
                zipfile,
                "ZipFile",
                side_effect=(candidate_context, receipt_context),
            ),
            self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "receipt file size"
            ),
        ):
            bootstrap._verify_materialized_evidence_bytes(
                record,
                candidate,
                receipt_archive,
                as_of=datetime(2026, 9, 5, tzinfo=UTC),
            )
        receipt_archive_mock.read.assert_not_called()

        oversized_contract = info(record.wheel_member, record.contract_size + 1)
        wheel_archive_mock = MagicMock()
        wheel_archive_mock.namelist.return_value = [record.wheel_member]
        wheel_archive_mock.getinfo.return_value = oversized_contract
        wheel_archive_mock.read.side_effect = AssertionError("read called")
        wheel_context = MagicMock()
        wheel_context.__enter__.return_value = wheel_archive_mock
        wheel_bytes = b"synthetic wheel"
        with (
            patch.object(zipfile, "ZipFile", return_value=wheel_context),
            self.assertRaisesRegex(
                bootstrap.FoundationBootstrapError, "contract member size"
            ),
        ):
            bootstrap._verify_wheel_bytes(
                replace(
                    record,
                    wheel_sha256=hashlib.sha256(wheel_bytes).hexdigest(),
                ),
                wheel_bytes,
                as_of=datetime(2026, 9, 5, tzinfo=UTC),
            )
        wheel_archive_mock.read.assert_not_called()

    def test_unknown_fields_are_refused(self) -> None:
        with self.assertRaises(bootstrap.FoundationBootstrapError):
            bootstrap.load_foundation_bootstrap({**self.body, "extra": "planted"})


if __name__ == "__main__":
    unittest.main()
