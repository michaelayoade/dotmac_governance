# Evidence model

Status: draft. Not approved.

## What counts as evidence

Evidence is an artefact produced by a pipeline, addressable after the fact, and
tied to a specific commit. In practice: a CI run ID, a build attestation, a
signed image digest, a test report, a generated report committed by automation.

## What does not count

- An agent stating that it ran a check.
- A human stating that a control is in place.
- A Knowledge entry describing a control.
- A checked-in document asserting a state of the world (a document is *policy*;
  it is not evidence that policy was followed).

This distinction is the whole point of splitting Git and CI in
[ADR 0001](adr/0001-governance-authority-model.md). Prose is cheap to produce and
impossible to audit; a pipeline artefact is neither.

## Mapping shape

Each control interpretation carries a mapping with these fields. The mapping
lives in Git; the evidence it points at does not.

| Field | Meaning |
| --- | --- |
| `control` | Clause identifier only (e.g. `ISO/IEC 27001:2022 A.8.28`). No standard text. |
| `interpretation` | Dotmac's own statement of what this requires here. |
| `implementation` | Where the control is implemented — repo, path, service. |
| `evidence` | How CI produces the artefact, and where it lands. |
| `owner` | Named human accountable. Not a team, not an agent. |
| `status` | `unimplemented` \| `implemented-unevidenced` \| `evidenced`. |

`implemented-unevidenced` is an expected, legitimate state. Recording it
honestly is the mechanism by which the gap stays visible; collapsing it into
`evidenced` because a document describes the control is the failure this model
exists to prevent.

## Open

The concrete mapping format (file layout, whether it is validated by CI, whether
evidence freshness is checked) is undecided. See `open-decisions.md`.
