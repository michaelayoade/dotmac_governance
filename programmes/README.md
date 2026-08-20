# Cross-repository programmes

This directory holds the canonical identity, ordering and gate state for a
Dotmac programme that crosses repository boundaries. It does not copy product
inventories or become a business-decision owner. Product repositories retain
their technical ADRs, source audits, implementation and cutover evidence.

Every matrix is strict JSON validated by `python3 -m programme_control`.
Stable control, cohort, decision, assembly and component identifiers are never
reused for a different meaning. A state may become `verified` only with an
immutable controlled-source reference. Proposed records are non-normative and
cannot claim verified controls.

The lifecycle is:

1. draft the matrix and governing ADR as `proposed`;
2. obtain attributable approval from the named human;
3. pin exact product decision and evidence revisions;
4. move one control or cohort state only in a reviewed change carrying the
   evidence reference; and
5. preserve superseded identifiers and history rather than editing their
   meaning.

CI validates structure and internal state. It does not decide that an approval,
cutover or retirement is correct.
