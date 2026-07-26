# Open decisions

These items require a named human decision. An agent drafted the surrounding
scaffold and deliberately did not infer scope, identity, or evidence claims.

| # | Decision | Why it is blocking | Owner |
| --- | --- | --- | --- |
| 1 | ~~ISMS scope statement for ISO/IEC 27001:2022~~ | Closes if ADR 0002 is approved: replaced by the governed-scope repository list. See decision 9. | Michael |
| 2 | ~~AIMS scope statement for ISO/IEC 42001:2023~~ | Closes if ADR 0002 is approved: replaced by the agent-participation process. | Michael |
| 3 | ~~Named independent evidence verifier(s)~~ | Closes if ADR 0002 is approved: independent verification is certification machinery. Human approval of changes still applies. | Michael |
| 4 | Evidence schema, retention, freshness, and tamper-evident export | Deliberately deferred. Under ADR 0002 this is derived from adopted processes and their information items, so it cannot be designed until the six processes exist. | Control owners |
| 5 | Human/agent identity separation in GitHub and Knowledge | An agent operating through Michael's account is not distinguishable from Michael's own action. Under ADR 0002 this blocks the agent-participation process being verifiable, so it moves ahead of the process definitions. | Michael |
| 6 | Relationship to `dotmac_sub`'s source-of-truth standard | Under ADR 0002 this becomes the architecture-and-design process definition rather than a standalone policy. Confirm that framing. | Michael |
| 7 | Enforced branch protection | Directed 2026-07-26: closed by publishing the repository. ADR 0003 records the decision and its conditions; the item stays open until protected `main` is verified by API. | Michael |
| 8 | Managed Codex/Claude policy rollout and cutover | Still gated on decision 5, but under ADR 0002 it is the distribution mechanism for the agent-participation process rather than a separate programme. | Michael |
| 9 | Governed scope beyond the initial six repositories | `dotmac_academy_app`, `dotmac_voice`, `dotmac_mobile`, `dotmac_vtu`, `dotmac_starter_mt`, `dotmac_data`, and `flutter-xcode-cloud-starter` are active but out of initial scope. In or out, deliberately. | Michael |
| 10 | Canonical location of `dotmac_field` | Referenced in operational practice, but not found under this account or any organization it belongs to. Scope cannot include a repository whose canonical URL is unknown. | Michael |
| 11 | Public default branches for governed repositories | `dotmac_sub`, `dotmac_crm`, `dotmac_erp`, and `dotmac-integration-client` are public. ADR 0003 resolves this for `dotmac_governance` only; whether public default branches are compatible with the configuration-and-secrets process across the governed set is still undecided. | Michael |
| 12 | Self-hosted runner exposure on a public repository | `governance-checks.yml` runs on `pull_request` against the Seabone self-hosted runner. Public forks can execute code on it unless Actions requires approval for all outside contributors. ADR 0003 makes this a condition of publication; it must be verified, not assumed. | Michael |

Decisions 1, 2, and 3 are struck through pending ADR 0002 approval. While that
record is `Proposed` they remain open, because a proposed record closes nothing.

## Directed bootstrap decisions

Michael has already directed:

- `dotmac_governance` owns organization-wide policies, control definitions,
  global ADRs, templates, and generated indexes. It was private at bootstrap;
  Michael directed on 2026-07-26 that it become public so branch protection is
  technically enforceable. ADR 0003 records that decision, narrows hard rule 5
  from visibility to classification, and makes an Actions fork-approval policy
  a condition of publication.
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
