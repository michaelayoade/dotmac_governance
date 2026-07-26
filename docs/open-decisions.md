# Open decisions

These items require a named human decision. An agent drafted the surrounding
scaffold and deliberately did not infer scope, identity, or evidence claims.

| # | Decision | Why it is blocking | Owner |
| --- | --- | --- | --- |
| 1 | ~~ISMS scope statement for ISO/IEC 27001:2022~~ | **Closed** by accepted ADR 0002: replaced by the governed-scope repository list. | — |
| 2 | ~~AIMS scope statement for ISO/IEC 42001:2023~~ | **Closed** by accepted ADR 0002: replaced by the agent-participation process. | — |
| 3 | Named effectiveness verifier per process | Narrowed by accepted ADR 0002, not closed. Human approval stays mandatory everywhere; a separate verifier is named only where an adopted process declares one. Each of the six processes must state which it is. | Process owners |
| 4 | Evidence schema, retention, freshness, and tamper-evident export | Deliberately deferred. Under ADR 0002 this is derived from adopted processes and their information items, so it cannot be designed until the six processes exist. | Control owners |
| 5 | Human/agent identity separation in GitHub and Knowledge | An agent operating through Michael's account is not distinguishable from Michael's own action. Under ADR 0002 this blocks the agent-participation process being verifiable, so it moves ahead of the process definitions. | Michael |
| 6 | Relationship to `dotmac_sub`'s source-of-truth standard | Under ADR 0002 this becomes the architecture-and-design process definition rather than a standalone policy. Confirm that framing. | Michael |
| 7 | Enforced branch protection | Resolution corrected 2026-07-26: pay for the capability rather than publish. Closes when GitHub Pro is active and protection is verified by API **on the private repository**. Protection configured while public does not evidence it. | Michael |
| 8 | Managed Codex/Claude policy rollout and cutover | Still gated on decision 5, but under ADR 0002 it is the distribution mechanism for the agent-participation process rather than a separate programme. | Michael |
| 9 | ~~Governed scope beyond the initial six repositories~~ | **Decided** 2026-07-26: the initial six are the governed set. Every other repository stays out until explicitly onboarded by an amendment to ADR 0002. Silence never onboards. | — |
| 10 | ~~Canonical location of `dotmac_field`~~ | **Decided** 2026-07-26: out of scope until a canonical repository exists. A governed system cannot be identified by operational practice alone. | — |
| 11 | Visibility per governed repository | **Framing decided** 2026-07-26: visibility is decided per repository from its classification and threat model, never as a global rule. `dotmac_governance` is private (ADR 0003). `dotmac_sub`, `dotmac_crm`, `dotmac_erp`, and `dotmac-integration-client` are public and each still needs its own assessment — starting with whether any uses a self-hosted runner. | Michael |
| 12 | ~~Self-hosted runner exposure on a public repository~~ | **Dissolved** by ADR 0003: restoring private removes the condition rather than mitigating it. Reopens for any governed repository that is public *and* uses a self-hosted runner — see decision 11. | — |

Decisions 1 and 2 are closed by accepted ADR 0002. Decision 3 is narrowed
rather than closed: human approval stays mandatory everywhere, and separate
effectiveness verification is now a per-process declaration. Decisions 9, 10,
and 12 are resolved as struck through. Decision 11 has a decided framing and
per-repository work remaining.

A decision is struck through only when an accepted record closes it. Nothing
here is closed by a `Proposed` ADR.

## Directed bootstrap decisions

Michael has already directed:

- `dotmac_governance` is private and owns organization-wide policies, control
  definitions, global ADRs, templates, and generated indexes. It was briefly
  published on 2026-07-26 to obtain branch protection; that was reversed as
  conflicting with accepted ADR 0001, and ADR 0003 closes the enforcement gap
  by paying for the capability instead. Hard rule 5 is unchanged.
- Initial standards scope is ISO/IEC 27001 and ISO/IEC 42001, with
  ISO/IEC/IEEE 12207:2026 and ISO/IEC/IEEE 15289:2019 as engineering
  references. ADR 0002 proposes inverting this — 12207 and 15289 as the spine,
  27001 and 42001 as overlays — and is not yet approved.
- The product is a standards-based development model, not a certification
  programme. ADR 0002 records this; until it is approved the destination stated
  in ADR 0001 stands.
- ISO 9001 certification is deferred until a customer, procurement, or
  company-wide QMS requirement exists.
- Interim accountable approval roles are recorded in ADR 0001. The surrounding
  ADR was explicitly accepted by Michael on 2026-07-25 and becomes effective
  when its accepted revision merges to `main`.

## Resolved operational control: private CI

The repository had been made public as a workaround for unavailable hosted
Actions. That conflicted with the directed private boundary and was corrected on
2026-07-24. The replacement control is a repository-scoped Seabone
self-hosted runner.

Private-repository CI was verified green in GitHub Actions run
[`30128057161`](https://github.com/michaelayoade/dotmac_governance/actions/runs/30128057161).
The run selected the Seabone runner, exercised the known-good and known-bad ADR
controls, and validated the production record set. This closes CI availability;
it does not close open decision 7 because the current plan still cannot require
that check before merge.
