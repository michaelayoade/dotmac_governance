# 0004. Code quality reference model

- Status: Proposed
- Date: 2026-07-27
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Canonical Dotmac engineering repositories in ADR 0002's governed scope
- Classification: Public
- Amends: 0002 — the adopted-references list, which contains no product quality standard

## Context

ADR 0002 adopts 12207 for process, 15289 for information items, 27001 for
security, and 42001 for AI. None of those says anything about whether the code
is any good. 12207 governs *that* verification happens; it does not supply the
vocabulary for what verification is looking for.

The result is a development model whose verification process would have to
invent its own quality vocabulary, which is how "clean code" and "looks fine to
me" end up as review outcomes. A review comment that cannot name what it is
about is a preference, and preferences do not survive disagreement.

The gap is specific and the standards that fill it are a different family from
the ones already adopted.

## Decision

Two standards are adopted as the code quality reference model.

- **ISO/IEC 25010** supplies the product quality vocabulary. Every quality
  claim in a review, a gate, or a process definition names one of its
  characteristics.
- **ISO/IEC 5055** supplies the automated source code measure layer. It
  defines what a tool can detect, which bounds what a gate can honestly
  assert.

Two more are adopted as references without immediate obligation, for use when
the processes that need them are written:

- **ISO/IEC 20246** for typed work product reviews, when the change-and-review
  process is defined.
- **ISO/IEC/IEEE 29119** for test design, when the verification process is
  defined.

Certification and formal evaluation remain out of scope on ADR 0002's terms.
25023 and the wider 25000 evaluation series are **not** adopted; measuring
against a licensed evaluation method is certification-shaped work.

### Mapping status

Licensed access is not in place for any of these. Following ADR 0002's rule for
12207, characteristic and clause identifiers are recorded as **provisional**
and are not treated as verified until licensed copies exist. Dotmac's own
interpretations below stand on their own and do not depend on the mapping.

Standard text is never reproduced — here, in Knowledge, or in a prompt.

### Dotmac's interpretation

Six principles, stated in Dotmac's words. These are the substance; the
identifiers are traceability.

1. **Quality is decomposed, never asserted.** A quality claim names a
   characteristic. "This is cleaner" is not reviewable; "this reduces coupling
   between the resolver and the adapter" is.
2. **Maintainability is the characteristic that pays rent** on systems run for
   years, and it decomposes into modularity, reusability, analysability,
   modifiability, and testability. Those five are the working code review
   lens, and they align with the architecture process already: a thin adapter
   is modularity, one canonical writer is modifiability.
3. **Product quality is not quality in use.** A service can satisfy every
   internal measure and still fail an engineer at 2am. Both are measured;
   neither substitutes for the other.
4. **A measure without a decision is decoration.** Every quality measure
   declares attribute, measure, threshold, and the decision the threshold
   drives. Coverage reported and not gated is a number on a dashboard.
5. **Automatable weakness is a subset of quality.** 5055-style measures cover
   what a tool finds. Whether an abstraction matches the domain, whether a
   name is honest, and whether a boundary is in the right place are human
   review. A gate that claims the first covers the second is theatre.
6. **Security is a quality characteristic, not a parallel activity.** It sits
   in the same model as reliability and maintainability, which is why 27001's
   development controls overlay the verification process rather than forming a
   separate track.

### Where this becomes binding

In the **verification** process, when it is written. There, each principle
becomes a declared check with a threshold, a gate, and an enforcement
mechanism. Until that process is accepted, this ADR establishes vocabulary and
adopted references — it does not impose a gate on any repository.

Knowledge entries carrying these principles are discovery aids. They are not
enforcement, they are not evidence, and they do not make a repository conform
to anything.

## Consequences

- The verification process has a vocabulary to consolidate rather than invent,
  and review comments have somewhere to attach.
- Two more standards are needed in licensed form. The reading list grows before
  the mapping can be completed.
- Existing tooling — `ruff`, `mypy`, `pytest`, architecture tests, secret
  scanning — is reframed as partial coverage of named characteristics rather
  than as a complete quality gate. Expect that reframing to expose
  characteristics with no coverage at all; performance efficiency and
  reliability are the likely gaps.
- Nothing in any repository changes until the verification process is accepted.
  This ADR is vocabulary, and adopting vocabulary that never becomes a gate
  would be exactly the unenforced-process failure ADR 0002 prohibits.
- 25010's characteristic set was revised in its 2023 edition. Interpretations
  written against remembered names risk being subtly wrong, which is why they
  are marked provisional rather than recorded as mapped.

## Drift prevention

- Provisional identifiers are labelled provisional in every record that carries
  them, and are not promoted to mapped without a licensed copy.
- The verification process, when written, must declare which characteristics it
  covers and which it does not. A process claiming complete coverage of the
  quality model fails review on its face.
- A quality gate declares attribute, measure, threshold, and decision. A gate
  missing the decision is deleted under ADR 0002's enforce-or-delete rule.
- Knowledge entries derived from this ADR carry its identifier and are marked
  non-authoritative, so a projection cannot be mistaken for the adopted model.
- Adding a standard to the adopted list requires an amendment to this ADR or to
  ADR 0002. A tool, a linter rule, or a Knowledge entry does not adopt a
  standard.
