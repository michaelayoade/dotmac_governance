# Processes

Adopted life-cycle process definitions for the Dotmac development model.

A process states how a kind of work is done, what records it produces, who
approves it, and what detects when it was skipped. It is distinct from:

- an **ADR**, which records one decision and its reasoning;
- a **policy**, which states what Dotmac requires in general terms;
- a **work product**, which is the engineering output the process governs.

Processes are normative only when `Status: Accepted`. ADR 0002 adopts the model
these definitions implement.

## Status

Every process carries exactly one, with the same meanings as an ADR:
`Proposed`, `Accepted`, `Superseded by <slug>`, or `Rejected`.

Processes are named by slug, not number. A process is a standing description of
how work is done, so it is referenced by what it governs — `architecture-and-decision`
— rather than by the order it was written in. ADR numbering exists because
decisions are events in sequence; processes are not.

## Required content

| Field | Meaning |
| --- | --- |
| `Status`, `Date`, `Owner`, `Approver`, `Classification` | As for ADRs. |
| `Model version` | The development-model version this definition targets. |
| Purpose | What the process is for, in one paragraph. |
| Standards mapping | 12207 process identifier; 27001 and 42001 clause identifiers. Identifiers and Dotmac's interpretation only — never standard text. An unmapped identifier is recorded as unmapped, not guessed. |
| Inputs, activities, outcomes | What starts it, what happens, what is true at the end. |
| `required_information_items` | Records the process must produce, each with a location and content expectation. These are what a conformance check may demand. |
| `work_products` | Engineering output the process governs. Never subject to an information-item requirement. |
| Approval gate | Who approves, and what the attributable event is. |
| Effectiveness verification | Whether a separate named verifier is required, and who. Required only where declared — see ADR 0002. |
| Agent participation | Which activities an agent may perform, and which it may not. |
| Enforcement | The CI check that verifies the process, or the explicitly named human who performs it manually. |

## The enforcement rule

Every process declares either a CI check or a named human owner. A process with
neither is **deleted**, not marked aspirational.

A process document that nobody enforces and nobody owns describes a practice
that is not happening, and it is worse than its absence because it reads as
coverage. This is the same reason `policies/` stays honestly empty.

`enforcement: manual` is a legitimate declaration. `enforcement: none` is not.

## Information items are not work products

15289 governs information items — the records a process produces. It does not
govern source code, schemas, migrations, or built artefacts.

A validator may require that an information item exists and has certain
content. It must never require that a work product take a documentary shape.
Conflating the two produces a model that demands documentation of things that
document themselves, which is how process discipline earns its reputation.

## Deviations

A repository declares deviations in its `.governance.yml`. A deviation must
carry an owning Issue and an expiry date. A deviation with no expiry is not a
deviation; it is the shape of the system, undeclared.

## Derived artefacts

`.governance.yml` and its validator are **derived from these definitions**, not
designed ahead of them. The declaration block in each process is the input to
that schema. Expect the schema to change once a second and third process exist;
that is the intended order, not a failure of the first attempt.
