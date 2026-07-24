# Open decisions

Decisions this repository needs from a human, listed rather than assumed. An
agent drafted the surrounding scaffold and deliberately did not resolve any of
these, because each one either names a person, fixes a scope boundary, or makes
a compliance claim — and none of those are an agent's to make.

| # | Decision | Why it is blocking | Owner |
| --- | --- | --- | --- |
| 1 | **Named approvers**, including the interim arrangement | Nothing can move from `Proposed` to `Accepted` without one. Every document here is currently non-normative. | Michael |
| 2 | **ISMS scope statement** (ISO/IEC 27001:2022) — which systems, sites, and data are in scope | Determines which controls apply at all. Guessing it produces a mapping that audits against the wrong boundary. | Michael |
| 3 | **AIMS scope statement** (ISO/IEC 42001:2023) — which AI-assisted processes are in scope | Same, for the AI management system. Agent-assisted engineering is the obvious candidate but the boundary is a decision. | Michael |
| 4 | **Evidence mapping format** — file layout, CI validation, freshness checking | `evidence-model.md` defines the fields but not the mechanism. | — |
| 5 | **Repository visibility and access** — who can read, who can approve | Currently a private repo owned by one account. Approver separation needs at least a second party to be meaningful. | Michael |
| 6 | **Relationship to `dotmac_sub`'s SOT standard** — whether the source-of-truth standard becomes a policy here or stays in `dotmac_sub` | It is currently a Knowledge entry plus `dotmac_sub` docs. Under ADR 0001, a Knowledge entry is not normative. | Michael |

## Note on item 1

Until approvers are named, this repository is a scaffold with no authority. That
is a truthful state and it is fine to sit in briefly — but it means nothing here
should be cited as policy yet, including by agents reading it as context.
