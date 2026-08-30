# Agent constraints

These constraints bind any AI agent (Claude Code, Codex, or otherwise) operating
on this repository or producing governance material for Dotmac.

## Authority and status

- Checked-in policies and `Accepted` ADRs are authoritative for their declared
  scope. A `Proposed` ADR is a draft and must never be cited as policy.
- Knowledge MCP aids discovery and continuity. It does not approve, activate,
  or override governance records.
- Issues own actions and deadlines. Do not hide a corrective action inside a
  document paragraph.
- GitHub and controlled source systems produce approval/execution evidence.
  An agent's statement that a check ran is not evidence.

## An agent may

- Draft policies, ADRs, control interpretations, and evidence mappings.
- Review a change and record findings.
- Propose corrective actions as Issues.
- Point out that a control is unimplemented, an evidence mapping is missing, or
  a claim is unsupported.

## An agent may not

- **Occupy any approver role.** Approval is a human act by a named person.
- **Approve its own output.** An agent that drafted a change cannot be the same
  agent whose review is treated as the quality gate for it.
- **Declare compliance.** An agent may state that a control has an evidence
  mapping and that CI produced the evidence. It may not conclude that Dotmac
  *is compliant* with anything — that is an audit finding, not a model output.
- **Assert evidence.** Evidence is produced by CI and cited by reference. An
  agent's own statement that it ran something is not evidence.
- **Copy ISO text** into this repository, a prompt, a Knowledge entry, or a
  commit message. Clause identifiers and Dotmac's own words only.
- **Write secret values** anywhere, including drafts and scratch files.
- **Promote an inference into a standard.** A cross-cutting finding is surfaced
  as a candidate for a human decision; it is not silently adopted.

## Required workflow

1. Search Knowledge for relevant decisions, then verify them against the
   checked-in source of truth.
2. Work on a non-default branch. Do not commit directly to `main`.
3. Keep new governance records `Proposed` unless a named human explicitly
   approves them through the recorded process.
4. Run the local validation commands. **These are the whole local set** —
   static parsing, formatting, typing and record validation. The acceptance
   suite (`unittest`) is deliberately absent: it is owned by CI, and a local
   pass is not evidence and must not be reported as any. The split is declared
   in `.dotmac/validation-contract.json`, and step 4's block, that file,
   `.dotmac/agent-profile.json`'s `validation_commands` and
   `.github/workflows/` are held in agreement by
   `tools/check_validation_contract.py`, which fails when any of them moves
   without the others.

   ```bash
   python3 -m ruff check --select E4,E7,E9,F,I,B,UP agent_control gate_control programme_control standards_control tests/test_agent_control.py tests/test_check_receipts.py tests/test_check_validation_contract.py tests/test_gate_control.py tests/test_programme_control.py tests/test_standards_control.py tools/check_receipts.py tools/check_validation_contract.py tools/dotmac-agent tools/dotmac-gates tools/dotmac-programme tools/dotmac-standards
   python3 -m ruff format --check agent_control gate_control programme_control standards_control tests/test_agent_control.py tests/test_check_receipts.py tests/test_check_validation_contract.py tests/test_gate_control.py tests/test_programme_control.py tests/test_standards_control.py tools/check_receipts.py tools/check_validation_contract.py tools/dotmac-agent tools/dotmac-gates tools/dotmac-programme tools/dotmac-standards
   python3 -m mypy --strict --scripts-are-modules agent_control gate_control programme_control standards_control tools/check_receipts.py tools/check_validation_contract.py tools/dotmac-agent tools/dotmac-gates tools/dotmac-programme tools/dotmac-standards
   python3 tools/check_adrs.py
   python3 tools/check_receipts.py --base origin/main
   python3 tools/check_validation_contract.py
   python3 -m agent_control verify --root . --profile .dotmac/agent-profile.json
   python3 -m programme_control --root .
   python3 -m standards_control verify --root . --profile .dotmac/standards-profile.json --default-branch main
   ```

5. Push the branch and let CI run the acceptance suite. CI is the acceptance
   owner: do not run the tests locally, and never start a service, container or
   daemon to make one runnable. Report the run, not your own execution of it.
6. Open a pull request that states the governance effect, the authority status,
   the named approver, evidence references, and every unresolved decision.
7. Never merge unless the configured checks are green and the required human
   approval is present. If GitHub cannot technically enforce the rule, report
   that enforcement gap rather than pretending the control exists.

## Collaboration records

- Stand-up summaries are source-linked observations. They create no policy.
- Decisions become ADRs; actions become owned Issues; evidence stays in its
  producing system and is cited by immutable reference.
- Codex and Claude may challenge each other's drafts. Two agents are not two
  independent approvers.

## Reporting

When an agent finishes governance work it states plainly what it drafted, what
remains unapproved, and which decisions it deliberately did not make. Silence
about an open decision reads as closure, which is the failure mode this file
exists to prevent.
