# Open decisions

These items require a named human decision. An agent drafted the surrounding
scaffold and deliberately did not infer scope, identity, or evidence claims.

| # | Decision | Why it is blocking | Owner |
| --- | --- | --- | --- |
| 1 | ISMS scope statement for ISO/IEC 27001:2022 | Determines which systems, sites, people, and data are governed. | Michael |
| 2 | AIMS scope statement for ISO/IEC 42001:2023 | Determines which AI systems and assisted processes are governed. | Michael |
| 3 | Named independent evidence verifier(s) | Michael is the interim accountable approver, but evidence effectiveness requires a different named human. | Michael |
| 4 | Evidence schema, retention, freshness, and tamper-evident export | `evidence-model.md` defines the proposed meaning, not the final implementation contract. | Control owners |
| 5 | Human/agent identity separation in GitHub and Knowledge | An agent operating through Michael's account is not distinguishable from Michael's own action; approval provenance is therefore incomplete. | Michael |
| 6 | Relationship to `dotmac_sub`'s source-of-truth standard | Decide whether it is promoted to an organization policy here or remains a repository-local standard. | Michael |
| 7 | Enforced branch protection for private repositories | The current GitHub plan returned HTTP 403 for branch protection; CI-before-merge is not technically enforced. | Michael |
| 8 | Managed Codex/Claude policy rollout and cutover | The vendor-neutral bundle, managed permissions/hooks, repository adoption checks, fallback retirement, and drift reconciler need a separate approved design after identity/RBAC. | Michael |

## Directed bootstrap decisions

Michael has already directed:

- `dotmac_governance` is private and owns organization-wide policies, control
  definitions, global ADRs, templates, and generated indexes.
- Initial standards scope is ISO/IEC 27001 and ISO/IEC 42001, with
  ISO/IEC/IEEE 12207:2026 and ISO/IEC/IEEE 15289:2019 as engineering
  references.
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
