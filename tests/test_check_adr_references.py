"""Known-bad controls for the ADR citation guard.

`dotmac_governance` ADR 0031 fixes this guard's non-vacuity in advance, and
these tests are that requirement rather than a restatement of it:

- it must go RED on the EXHIBIT -- the `Relates to:` header in
  `dotmac_platform_control_plane` ADR-0016, which cites "ADR-0018 in
  `dotmac_governance`" for a rule that is `dotmac_starter_mt`'s;
- it must NOT fire on a bare reference to a number the repository DOES hold,
  which is the overwhelming majority of the 2,477 occurrences measured in
  `dotmac_starter_mt`'s docs. A citation checker that flags those has made the
  convention unusable and will be turned off.

Both halves are observed. A detector shown only failing has not been shown to
discriminate, and this fleet has four measured cases of a negative control that
could not fail.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from check_adr_references import (  # noqa: E402
    BASELINE_PATH,
    Finding,
    ReferenceCheckError,
    evaluate,
    local_adr_numbers,
    scan,
    scan_text,
)

HELD = frozenset({"0015", "0016"})


def ref(number: str) -> str:
    """Build a citation token without SPELLING one in this file.

    This guard reads text. A test that planted the literal string would make
    this file a repository citing records it does not hold, and the guard would
    correctly report its own fixtures -- the self-reference family that cost
    this fleet three CI cycles in one day.

    The repair is a property rather than an exemption: no allowlist, no
    baseline entry, no "tests are exempt" directory rule. The file simply does
    not contain a citation, because it builds its fixtures at runtime. What the
    scanner reads is what a reader reads, which is the invariant that makes the
    guard trustworthy anywhere else.
    """
    return "ADR-" + number


def _text(*lines: str) -> str:
    return "\n".join(lines) + "\n"


class ScanTextControls(unittest.TestCase):
    """The citation-versus-reproduction decision, one property at a time."""

    def test_the_exhibit_is_red(self) -> None:
        """The known-bad case ADR 0031 names. A guard passing it is not this guard.

        Reproduced with its real line break: the number ends one line and the
        repository name begins the next, which is why a same-line qualifier
        window reports it -- and the finding is correct independently, because
        that repository holds no ADR-0018.
        """
        exhibit = _text(
            "- **Relates to:** ADR-0003 (a deployment profile selects surfaces and",
            "  nothing else), ADR-0014 (the console has one browser authentication",
            "  owner), ADR-0015 (a production profile publishes no simulation),",
            f"  {ref('0018')} in",
            "  `dotmac_governance` (a guard exemption states an enforceable premise)",
        )
        findings = scan_text(exhibit, held=HELD, path="docs/adr/0016.md")

        self.assertEqual(
            [f.number for f in findings],
            ["0018"],
            "the exhibit must be reported, and nothing else on it",
        )
        self.assertEqual(findings[0].key(), "docs/adr/0016.md:4:ADR-0018")

    def test_a_bare_reference_to_a_held_number_is_silent(self) -> None:
        """The half that keeps the guard usable.

        This is the shape of the 2,477 bare references measured in
        `dotmac_starter_mt`, every one of which resolves locally. Firing on
        them would train a reader to ignore the guard.
        """
        held_locally = _text(
            "Adapters are thin (ADR-0015).",
            "See ADR 0016 for the surface policy, and ADR-0015 again.",
        )
        self.assertEqual(scan_text(held_locally, held=HELD, path="AGENTS.md"), [])

    def test_a_qualified_reference_is_silent(self) -> None:
        """Naming the owning repository is the repair, so it must clear."""
        for line in (
            "See `dotmac_starter_mt` ADR-0018 for the exemption rule.",
            "Accepted fleet-wide as dotmac_governance ADR 0031.",
            "This follows kernel ADR-0018 rule 5.",
            "Per Platform CP ADR-0016 section 6, the port is owed.",
        ):
            with self.subTest(line=line):
                self.assertEqual(
                    scan_text(_text(line), held=HELD, path="docs/x.md"), []
                )

    def test_an_unknown_qualifier_is_not_a_qualifier(self) -> None:
        """A typo in a repository name produces a finding rather than passing.

        The vocabulary is closed on purpose. An open one would accept
        `dotmac_startr_mt` and report nothing, which is the guard agreeing with
        the defect.
        """
        findings = scan_text(
            _text("See dotmac_startr_mt ADR-0018."), held=HELD, path="docs/x.md"
        )
        self.assertEqual([f.number for f in findings], ["0018"])

    def test_a_fenced_block_is_a_specimen(self) -> None:
        """A record showing the correct form of a citation is not making one."""
        specimen = _text(
            "The qualified form:",
            "```",
            "dotmac_starter_mt ADR-0018",
            ref("0099"),
            "```",
            "and back to prose.",
        )
        self.assertEqual(scan_text(specimen, held=HELD, path="docs/adr/0031.md"), [])

    def test_a_blockquote_is_a_reproduction(self) -> None:
        """Quoting a defective header reports a citation; it does not issue one.

        ADR 0030 and ADR 0031 both quote the exhibit deliberately. A guard that
        fired on them would make the record that defines the rule the record
        that violates it.
        """
        quoted = _text(
            "The header reads:",
            "",
            "> ADR-0018 in `dotmac_governance` (a guard exemption states an",
            "> enforceable premise)",
            "",
            "That is the wrong repository.",
        )
        self.assertEqual(scan_text(quoted, held=HELD, path="docs/adr/0031.md"), [])

    def test_prose_explaining_the_rule_still_needs_a_qualifier(self) -> None:
        """Deliberate: outside a quote or fence, prose cites like anything else.

        Excluding comments or prose wholesale would gut the check -- most of
        the 43 findings measured in `dotmac_platform_control_plane` are in
        comments and docstrings. The repair for narration is the same as for a
        citation: name the repository, which is also more informative.
        """
        narration = _text(f'A duplicate number means "ADR {"0004"}" names two records.')
        self.assertEqual(
            [f.number for f in scan_text(narration, held=HELD, path="tools/x.py")],
            ["0004"],
        )
        repaired = _text(
            "A duplicate number means `dotmac_sub` ADR 0004 names two records."
        )
        self.assertEqual(scan_text(repaired, held=HELD, path="tools/x.py"), [])


class BaselineRatchetControls(unittest.TestCase):
    """A set, not a count, failing in both directions."""

    @staticmethod
    def _repo(name: str) -> Path:
        """A minimal real repository: the corpus comes from `git ls-files`."""
        root = Path(name)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        (root / "docs" / "adr").mkdir(parents=True)
        (root / "docs" / "adr" / "0001-only-record.md").write_text("# 0001. X\n")
        (root / ".dotmac").mkdir()
        return root

    def test_a_new_finding_fails(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = self._repo(name)
            (root / "AGENTS.md").write_text(f"See {ref('0044')}.\n")

            new, stale = evaluate(root)
            self.assertEqual(new, [f"AGENTS.md:1:{ref('0044')}"])
            self.assertEqual(stale, [])

    def test_a_declared_finding_passes(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = self._repo(name)
            (root / "AGENTS.md").write_text(f"See {ref('0044')}.\n")
            (root / BASELINE_PATH).write_text(
                json.dumps(
                    {"known_unresolvable_references": [f"AGENTS.md:1:{ref('0044')}"]}
                )
            )

            self.assertEqual(evaluate(root), ([], []))

    def test_a_repaired_finding_fails_until_its_entry_is_removed(self) -> None:
        """The downward direction. Seven repaired while an eighth appears must
        not net to silence, and a stale entry is an exemption nobody checks."""
        with tempfile.TemporaryDirectory() as name:
            root = self._repo(name)
            (root / "AGENTS.md").write_text(f"See `dotmac_sub` {ref('0044')}.\n")
            (root / BASELINE_PATH).write_text(
                json.dumps(
                    {"known_unresolvable_references": [f"AGENTS.md:1:{ref('0044')}"]}
                )
            )

            new, stale = evaluate(root)
            self.assertEqual(new, [])
            self.assertEqual(stale, [f"AGENTS.md:1:{ref('0044')}"])

    def test_a_swap_is_not_silent(self) -> None:
        """One repaired and one added nets to zero as a COUNT and must not pass."""
        with tempfile.TemporaryDirectory() as name:
            root = self._repo(name)
            (root / "AGENTS.md").write_text(f"See `dotmac_sub` {ref('0044')}.\n")
            (root / "README.md").write_text(f"See {ref('0055')}.\n")
            (root / BASELINE_PATH).write_text(
                json.dumps(
                    {"known_unresolvable_references": [f"AGENTS.md:1:{ref('0044')}"]}
                )
            )

            new, stale = evaluate(root)
            self.assertEqual(new, [f"README.md:1:{ref('0055')}"])
            self.assertEqual(stale, [f"AGENTS.md:1:{ref('0044')}"])

    def test_the_baseline_is_not_its_own_corpus(self) -> None:
        """A ledger that catches its own entries measures itself."""
        with tempfile.TemporaryDirectory() as name:
            root = self._repo(name)
            (root / BASELINE_PATH).write_text(
                json.dumps(
                    {"known_unresolvable_references": [f"AGENTS.md:1:{ref('0044')}"]}
                )
            )

            self.assertEqual(scan(root), [])

    def test_a_malformed_baseline_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = self._repo(name)
            (root / BASELINE_PATH).write_text('{"known_unresolvable_references": 3}')

            with self.assertRaises(ReferenceCheckError):
                evaluate(root)


class ProductionTreeControls(unittest.TestCase):
    """Properties of this repository, so the guard is not proven only on toys."""

    def test_this_repository_is_green_against_its_declared_baseline(self) -> None:
        new, stale = evaluate(REPO_ROOT)
        self.assertEqual(new, [], "new unresolvable citations arrived")
        self.assertEqual(stale, [], "a baseline entry stopped firing")

    def test_the_baseline_is_not_vacuous(self) -> None:
        """An empty baseline would pass every ratchet test for the wrong reason."""
        declared = json.loads((REPO_ROOT / BASELINE_PATH).read_text())
        self.assertTrue(declared["known_unresolvable_references"])

    def test_the_local_record_set_is_read_from_the_directory(self) -> None:
        held = local_adr_numbers(REPO_ROOT)
        self.assertIn("0031", held)
        self.assertNotIn("0010", held, "0010 is the number this repository lacks")

    def test_finding_keys_are_addressable(self) -> None:
        self.assertEqual(
            Finding(path="a/b.md", line=7, number="0018").key(),
            f"a/b.md:7:{ref('0018')}",
        )


if __name__ == "__main__":
    unittest.main()
