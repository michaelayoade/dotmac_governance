# Evidence model

Status: draft. Not approved.

## Boundary

Governance mappings live in Git. Evidence remains in the controlled system that
produced it and is cited by immutable reference. Knowledge may index the
reference for discovery; it is not the evidence store and cannot make an
unevidenced claim true.

Evidence can be produced by CI, a controlled monitoring/export pipeline, a
signed approval system, or another named source system. It is not limited to
tests, but it must be attributable, addressable after the fact, tied to a
defined subject and period, and protected from silent mutation.

## What does not count

- An agent stating that it ran a check.
- A human stating that a control is in place without an attributable record.
- A Knowledge entry describing a control.
- A document asserting its own implementation.
- A commit or image label that has not been bound to the artefact bytes it
  claims to identify.

## Proposed typed reference

Each evidence reference should carry:

| Field | Meaning |
| --- | --- |
| `id` | Stable evidence-reference identifier. |
| `kind` | CI run, test report, build attestation, approval, monitoring snapshot, audit export, or other controlled kind. |
| `producer` | Named source system that created the evidence. |
| `subject` | Control, service, repository, release, risk, or review being evidenced. |
| `source_uri` | Immutable or retention-controlled reference. |
| `commit_or_digest` | Commit, artefact digest, or signed record identity. |
| `collected_at` | When the evidence was produced. |
| `valid_from` / `valid_until` | Period the evidence supports, when applicable. |
| `attested_by` | Named control owner attesting the evidence. |
| `verified_by` | Different named human verifying effectiveness. |
| `hash` | Content hash where the source system does not already provide immutable identity. |

No field may contain a secret value. References use an approved OpenBao path or
controlled local pointer when a protected source must be named.

## Control mapping

Each control interpretation carries:

| Field | Meaning |
| --- | --- |
| `control` | Standard/clause identifier only. No standard text. |
| `interpretation` | Dotmac's own statement of the requirement. |
| `implementation` | Owning repo, path, service, or process. |
| `evidence_refs` | One or more typed references. |
| `owner` | Named human accountable for the control. |
| `status` | `unimplemented`, `implemented-unevidenced`, or `evidenced`. |

`implemented-unevidenced` is an expected and legitimate state. It remains open
until the evidence source, retention, attestation, and independent verification
are established.

## Open

The serialization schema, retention requirements, freshness rules, tamper-
evident export, and reconciler are intentionally deferred. See
`open-decisions.md`.
