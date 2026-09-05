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
    FOREIGN_REPRODUCTIONS,
    SCANNED_SUFFIXES,
    Finding,
    ReferenceCheckError,
    corpus,
    evaluate,
    local_adr_numbers,
    scan,
    scan_text,
)

#: The records the fixture repository holds. It models
#: `dotmac_platform_control_plane` at the exhibit's revision: 0003, 0014, 0015
#: and 0016 exist, 0018 does NOT, and 0004 does not either. That matters more
#: than it looks -- the exhibit's line cites four numbers, and the guard must
#: report exactly the one the repository lacks. A smaller held-set made the
#: test pass a guard that reported all four, which CI caught.
HELD = frozenset({"0003", "0014", "0015", "0016"})


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
            "the exhibit must be reported, and NOTHING ELSE on the same line: "
            "0003, 0014 and 0015 resolve in that repository and 0018 does not, "
            "so this asserts the guard discriminates within one line rather "
            "than objecting to the line",
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


class ForeignReproductionExclusionControls(unittest.TestCase):
    """A structural exemption states an ENFORCEABLE premise, or the region is
    unmonitored rather than exempt.

    `FOREIGN_REPRODUCTIONS` drops files from the corpus, and a dropped file is
    invisible to this guard. That is only defensible if two things hold, and
    each fails differently:

    - it hides a REAL report. An exclusion covering nothing looks identical to
      one covering something, and would pass forever after its subject changed.
    - it hides ONLY the declared paths. An exclusion that quietly widened would
      make regions unmonitored with no diff to review.

    Both are checked here rather than argued in a comment, because the reasoning
    that produced this exclusion was originally recorded only in a commit
    message and a one-off measurement -- neither of which is a check.
    """

    @staticmethod
    def _tracked_scanned() -> set[Path]:
        """Every tracked file the corpus WOULD hold with no exclusions."""
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return {
            Path(name)
            for name in result.stdout.splitlines()
            if name
            and Path(name).suffix.lower() in SCANNED_SUFFIXES
            and (REPO_ROOT / name).is_file()
        }

    def test_each_declared_reproduction_would_otherwise_be_reported(self) -> None:
        """The load-bearing side. Scanned directly, the file yields a finding --
        so the exclusion suppresses a real report rather than nothing."""
        held = local_adr_numbers(REPO_ROOT)
        for relative in sorted(FOREIGN_REPRODUCTIONS):
            with self.subTest(path=relative.as_posix()):
                target = REPO_ROOT / relative
                self.assertTrue(
                    target.is_file(), "a declaration whose subject vanished"
                )
                findings = scan_text(
                    target.read_text(),
                    held=held,
                    path=relative.as_posix(),
                )
                self.assertNotEqual(
                    findings,
                    [],
                    "this exclusion hides nothing: either the reproduction no "
                    "longer carries a foreign citation, or the guard stopped "
                    "seeing it. Remove the entry or find out which",
                )

    def test_the_corpus_omits_exactly_the_declared_paths(self) -> None:
        """The other side: no broader corpus. The difference between what is
        tracked and what is scanned must be exactly the two declared
        exclusions -- so a widened exemption fails rather than going quiet."""
        scanned = {path.relative_to(REPO_ROOT) for path in corpus(REPO_ROOT)}
        omitted = self._tracked_scanned() - scanned
        self.assertEqual(omitted, {BASELINE_PATH} | set(FOREIGN_REPRODUCTIONS))

    def test_the_same_bytes_at_an_undeclared_path_are_still_reported(self) -> None:
        """The exclusion is keyed on the PATH, not on the content. A copy
        elsewhere is a citation this repository makes, and is reported."""
        held = local_adr_numbers(REPO_ROOT)
        relative = sorted(FOREIGN_REPRODUCTIONS)[0]
        body = (REPO_ROOT / relative).read_text()
        findings = scan_text(body, held=held, path="docs/not-a-reproduction.md")
        self.assertNotEqual(findings, [])

    def test_the_declared_set_is_not_empty(self) -> None:
        """A check over an empty set passes for the wrong reason. If the last
        reproduction is retired, the exclusion goes with it."""
        self.assertNotEqual(FOREIGN_REPRODUCTIONS, frozenset())


if __name__ == "__main__":
    unittest.main()
