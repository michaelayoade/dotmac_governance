"""Known-good and known-bad controls for the commit-identity guard.

Every prohibited shape is CONSTRUCTED as a real commit in a throwaway
repository and the guard is observed firing on it. Asserting that this
repository's own commits are clean would prove that this repository's own
commits are clean, which is not the property the guard exists to hold.

The case that matters most is the last group. A guard that cannot establish the
commit range must ERROR, and it is the part most likely to be got wrong,
because every convenient failure mode — an empty range, an unresolved ref, a
shallow clone — reads naturally as "nothing to check" and therefore as green.
An established-but-empty range is separated from an unestablishable one
deliberately: they are different facts and they get different verdicts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from check_commit_identity import (  # noqa: E402
    GateVerdict,
    RangeError,
    commit_range,
    validate_commits,
)

HUMAN_NAME = "Michael Ayoade"
HUMAN_EMAIL = "32591929+michaelayoade@users.noreply.github.com"


def _git(root: Path, *args: str, **env: str) -> None:
    environment = dict(os.environ)
    environment.update(env)
    subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
        env=environment,
    )


class CommitFixture:
    """A throwaway repository with a clean `main` and a branch under review."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.counter = 0
        _git(root, "init", "-q", "-b", "main")
        _git(root, "config", "user.name", HUMAN_NAME)
        _git(root, "config", "user.email", HUMAN_EMAIL)
        _git(root, "config", "commit.gpgsign", "false")
        self.commit("base commit")
        _git(root, "checkout", "-q", "-b", "review")

    def commit(
        self,
        message: str,
        *,
        author_name: str = HUMAN_NAME,
        author_email: str = HUMAN_EMAIL,
        committer_name: str = HUMAN_NAME,
        committer_email: str = HUMAN_EMAIL,
    ) -> None:
        self.counter += 1
        (self.root / f"file{self.counter}.txt").write_text(
            str(self.counter), encoding="utf-8"
        )
        _git(self.root, "add", "-A")
        _git(
            self.root,
            "-c",
            f"user.name={committer_name}",
            "-c",
            f"user.email={committer_email}",
            "commit",
            "-q",
            "--author",
            f"{author_name} <{author_email}>",
            "-m",
            message,
        )


class CommitIdentityTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.fixture = CommitFixture(Path(self._dir.name))

    def verdict(
        self, base: str = "main", head: str = "HEAD"
    ) -> tuple[GateVerdict, list[str]]:
        return validate_commits(self.fixture.root, base, head)

    def assertFires(self, needle: str, base: str = "main") -> None:
        result, errors = self.verdict(base=base)
        self.assertIs(result, GateVerdict.EXECUTED_FAILED, f"errors: {errors}")
        self.assertIn(needle, "\n".join(errors))

    # ---------------------------------------------------------------- happy

    def test_an_accountable_commit_passes(self) -> None:
        self.fixture.commit("Do the work")
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    def test_a_forge_squash_committer_is_not_an_ai_identity(self) -> None:
        """`GitHub <noreply@github.com>` is how every squash merge is committed.

        A denylist that caught it would fail every merge commit, which is how a
        guard gets switched off.
        """
        self.fixture.commit(
            "Merge pull request #1",
            committer_name="GitHub",
            committer_email="noreply@github.com",
        )
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    def test_a_human_whose_name_merely_contains_a_prohibited_substring_passes(
        self,
    ) -> None:
        """`Claudia` is not `Claude`. The name patterns are word-bounded because
        a substring match would refuse a real person's commits."""
        self.fixture.commit(
            "Do the work",
            author_name="Claudia Okonkwo",
            author_email="claudia.okonkwo@example.com",
        )
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    def test_a_second_human_co_author_is_still_refused(self) -> None:
        """Michael's rule is absolute, and it is the only enforceable version.

        A co-author line is free text; a check on whether the value named a
        model would be a check on how the value was spelled.
        """
        self.fixture.commit(
            "Do the work\n\nCo-Authored-By: Okaka Confidence <okaka@example.com>"
        )
        self.assertFires("trailer")

    # -------------------------------------------------------- the incident

    def test_the_incident_shape_fires_on_the_author(self) -> None:
        """A local `user.email` override of `noreply@anthropic.com`.

        This is not hypothetical: it is the exact configuration accident that
        put that address on more than a thousand commits reachable from
        `dotmac_sub` main.
        """
        self.fixture.commit(
            "Do the work",
            author_name="michaelayoade",
            author_email="noreply@anthropic.com",
        )
        self.assertFires("author email 'noreply@anthropic.com'")

    def test_the_incident_shape_fires_on_the_committer(self) -> None:
        """A rebase or cherry-pick rewrites the committer and keeps the author.

        Checking only the author would miss half of the ways the wrong identity
        arrives, and in the motivating incident both fields were affected but by
        different counts, so neither field alone describes it.
        """
        self.fixture.commit(
            "Do the work",
            committer_name="michaelayoade",
            committer_email="noreply@anthropic.com",
        )
        self.assertFires("committer email 'noreply@anthropic.com'")

    def test_a_vendor_subdomain_fires(self) -> None:
        self.fixture.commit("Do the work", author_email="agent@mail.anthropic.com")
        self.assertFires("the vendor domain 'anthropic.com'")

    def test_an_assistant_forge_account_fires(self) -> None:
        self.fixture.commit(
            "Do the work",
            author_name="claude-bot",
            author_email="claude-bot@users.noreply.github.com",
        )
        self.assertFires("an assistant account address")

    def test_a_model_display_name_fires(self) -> None:
        self.fixture.commit(
            "Do the work",
            author_name="Claude Opus 5",
            author_email="somebody@example.com",
        )
        self.assertFires("a model or assistant product name")

    def test_a_vendor_display_name_on_the_committer_fires(self) -> None:
        self.fixture.commit(
            "Do the work",
            committer_name="Anthropic",
            committer_email="somebody@example.com",
        )
        self.assertFires("committer name 'Anthropic'")

    # ---------------------------------------------------------- trailers

    def test_a_co_authored_by_model_trailer_fires(self) -> None:
        self.fixture.commit(
            "Do the work\n\n"
            "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
        )
        self.assertFires("'Co-Authored-By'")

    def test_a_lowercase_trailer_key_still_fires(self) -> None:
        """Git's own trailers are case-insensitive, so the guard must be too."""
        self.fixture.commit("Do the work\n\nco-authored-by: Somebody <s@example.com>")
        self.assertFires("trailer")

    def test_a_claude_session_trailer_fires(self) -> None:
        self.fixture.commit(
            "Do the work\n\nClaude-Session: https://claude.ai/code/session_x"
        )
        self.assertFires("'Claude-Session'")

    def test_an_assisted_by_trailer_fires(self) -> None:
        self.fixture.commit("Do the work\n\nAssisted-By: an AI agent")
        self.assertFires("'Assisted-By'")

    def test_a_generated_footer_without_a_colon_fires(self) -> None:
        """Prose attribution carries no colon, so the trailer scan cannot see it.

        A guard that only parsed trailers would pass the single most common
        generated footer there is.
        """
        self.fixture.commit(
            "Do the work\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"
        )
        self.assertFires("AI attribution as prose")

    def test_a_normal_message_mentioning_a_colon_is_not_a_trailer(self) -> None:
        self.fixture.commit("Fix: the thing\n\nNote: this was fiddly.")
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    # -------------------------------------------------------------- scope

    def test_a_prohibited_commit_already_on_the_base_is_out_of_scope(self) -> None:
        """History is not repaired by a gate.

        The guard's claim is "nothing NEW arrives wrong". A guard over history
        would be permanently red on a repository that already has the problem,
        and a permanently red guard is switched off.
        """
        _git(self.fixture.root, "checkout", "-q", "main")
        self.fixture.commit("Old work", author_email="noreply@anthropic.com")
        _git(self.fixture.root, "checkout", "-q", "review")
        _git(self.fixture.root, "rebase", "-q", "main")
        self.fixture.commit("New work")
        self.assertEqual(self.verdict(), (GateVerdict.EXECUTED_PASSED, []))

    def test_every_commit_in_the_range_is_checked_not_only_the_tip(self) -> None:
        self.fixture.commit("First", author_email="noreply@anthropic.com")
        self.fixture.commit("Second")
        self.fixture.commit("Third")
        self.assertFires("noreply@anthropic.com")

    # -------------------------------------------------------- fail closed

    def test_an_unresolvable_base_errors_rather_than_passing(self) -> None:
        """The case the whole guard turns on.

        Every convenient failure mode reads naturally as "nothing to check" and
        therefore as green. This must be red.
        """
        self.fixture.commit("Do the work")
        self.assertFires("does not resolve to a commit", base="no-such-ref")

    def test_an_empty_base_ref_errors(self) -> None:
        self.fixture.commit("Do the work")
        self.assertFires("no base ref was supplied", base="")

    def test_the_all_zero_sha_errors_rather_than_reading_as_empty(self) -> None:
        """A newly created branch or a deleted ref pushes `000…0` as `before`.

        Read as a range it is empty, and an empty range is a pass. It is not a
        range at all, so it is an error.
        """
        self.fixture.commit("Do the work")
        self.assertFires("all-zero SHA", base="0" * 40)

    def test_an_unresolvable_head_errors(self) -> None:
        self.fixture.commit("Do the work")
        result, errors = validate_commits(self.fixture.root, "main", "no-such-head")
        self.assertIs(result, GateVerdict.EXECUTED_FAILED)
        self.assertIn("head ref", "\n".join(errors))

    def test_a_directory_that_is_not_a_repository_errors(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            result, errors = validate_commits(Path(name), "main", "HEAD")
        self.assertIs(result, GateVerdict.EXECUTED_FAILED)
        self.assertIn("refusing to report success", "\n".join(errors))

    def test_commit_range_raises_rather_than_returning_empty(self) -> None:
        """The library call must not have a quiet failure mode either.

        A caller that got `[]` back from an unresolvable range would conclude
        "no commits, all clean" — the exact silent pass the CLI refuses.
        """
        self.fixture.commit("Do the work")
        with self.assertRaises(RangeError):
            commit_range(self.fixture.root, "no-such-ref", "HEAD")

    # ------------------------------------------------------- non-vacuity

    def test_an_established_empty_range_is_not_applicable_not_a_pass(self) -> None:
        """Distinct from the failures above, and distinct from a clean pass.

        "There were no commits to check" and "the commits checked were clean"
        are different facts. Reporting the first as the second is the same
        defect as reporting an unestablishable range as green.
        """
        result, errors = validate_commits(self.fixture.root, "main", "main")
        self.assertEqual(errors, [])
        self.assertIs(result, GateVerdict.NOT_APPLICABLE)
        self.assertIsNot(result, GateVerdict.EXECUTED_PASSED)


if __name__ == "__main__":
    unittest.main()
