# Policies

Empty by design. No policy has been approved.

A policy is normative and states what Dotmac requires. It is distinct from:

- an **ADR**, which records a decision and its reasoning;
- a **control interpretation**, which states what a specific ISO clause requires
  in Dotmac's context;
- **evidence**, which is produced by CI and merely cited here.

## Lifecycle

1. Drafted as a pull request. An agent may write the draft.
2. Reviewed by a named human who is not the author.
3. Approved by a named human, recorded in a commit separate from the draft.
4. Superseded explicitly, never edited into a different meaning. The history of
   what was required, and when, is part of the record.

Nothing lands here until `docs/open-decisions.md` item 1 (named approvers) is
resolved — an unapproved policy file would be a document that looks normative
and is not, which is worse than an empty directory.
