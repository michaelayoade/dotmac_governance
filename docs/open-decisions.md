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
| 8 | Managed Codex/Claude policy rollout and cutover | Partially resolved for one endpoint only: on 2026-07-31 Michael accepted ADR 0005 for `agent:michael-workstation`, designated the local sudo-backed installer, and authorized backup-backed guidance migration. Organization-wide rollout remains gated on decision 5. Adding endpoints, retiring the old Knowledge-bootstrap guidance writer, or broadening policy requires a separate decision after this pilot is verified. | Michael |
| 9 | Governed scope beyond the initial six repositories | `dotmac_academy_app`, `dotmac_voice`, `dotmac_mobile`, `dotmac_vtu`, `dotmac_starter_mt`, `dotmac_data`, and `flutter-xcode-cloud-starter` are active but out of initial scope. In or out, deliberately. | Michael |
| 10 | Canonical location of `dotmac_field` | Referenced in operational practice, but not found under this account or any organization it belongs to. Scope cannot include a repository whose canonical URL is unknown. | Michael |
| 11 | Public default branches for governed repositories | `dotmac_sub`, `dotmac_crm`, `dotmac_erp`, and `dotmac-integration-client` are public. ADR 0003 resolves this for `dotmac_governance` only; whether public default branches are compatible with the configuration-and-secrets process across the governed set is still undecided. | Michael |
| 12 | Self-hosted runner exposure on a public repository | `governance-checks.yml` runs on `pull_request` against the Seabone self-hosted runner. Public forks can execute code on it unless Actions requires approval for all outside contributors. ADR 0003 makes this a condition of publication; it must be verified, not assumed. | Michael |
| 13 | ~~Coordinated Dotmac ISP construction and Sub cutover programme~~ | Resolved 2026-08-20: Michael explicitly accepted ADR 0012 and authorized its acceptance amendment. Acceptance approves the two-track programme boundary but moves no production authority; every cohort remains blocked by its own evidence controls. | Michael |
| 14 | Production deployment ownership for the canonical ISP target | Michael assigned `michaelayoade/dotmac-isp`, its independent thin runtime and independent database boundary in the 2026-08-20 working session. The production deployment owner and any target host remain deliberately unassigned. | Michael |
| 15 | Enforceable legacy Sub transition rule | The intended exception classes are containment, evidence repair, migration or shadow adapters, and bounded in-place module adoption that retires one local writer without claiming target cutover. The enforcement owner, detector, exception approval and sensitivity proof must be approved before the programme relies on the rule. | Michael |
| 16 | Analytics and reporting owner for the final ISP cohort | Starter's measured family remains source-unassigned. The final cohort cannot begin by turning that measurement bucket into a package name. | Michael |
| 17 | Machine-readable representation of ADR 0013's oracle kinds | ADR 0013 defines four typed oracle kinds and their required coordinates, but adds no `standards-profile.schema.json` field and no `standards_control` rule. Whether the profile carries external claims — and therefore whether § 3 and § 4 are enforced or remain review discipline — is a separate decision gated on ADR 0013 being accepted. | Michael |
| 18 | Resolving oracle citations against their producing systems | ADR 0013 can check that a citation carries a run id, peeled commit, digest and path. It cannot check that the run did what the citation says. Closing that gap means the control plane calling GitHub and the private index, which raises access, credential, retention and rate-limit questions the current evidence model has not decided. Stated as a gap rather than closed. | Michael |
| 19 | ~~Where an authority-cutover receipt is stored, and who owns that store~~ | Resolved 2026-08-30: Michael assigned the cross-repository authority-cutover receipt registry to Governance — append-only, versioned, non-sensitive envelopes only, corrections by supersession. Products retain their local evidence and Knowledge remains discovery support, not the authority. Recorded in ADR 0018 § 3, which also decides files-in-this-repository over a service. The registry's directory, schema, parser and validator are decision 21. | Michael |
| 20 | Propagating ADR 0018 into the fleet authority-cutover record | The parent standard is `dotmac_starter_mt` ADR-0031, `Accepted` and fleet-scoped, read at commit `ed3ac864b350d4556808a69496f999f764682442`. This repository's `Amends:` field is scoped to its own ADR directory, so ADR 0018 states the relationship in prose. Whether ADR-0031 gains a matching in-document amendment — and who makes that change in a repository Governance does not own — is undecided. | Michael |
| 21 | Receipt-registry directory, envelope schema and append-only enforcement | **Engineering half delivered, authorization half still open.** ADR 0019 (`Proposed`) creates `receipts/`, the closed envelope, the strict parser and the append-only validator (`tools/check_receipts.py`, comparing an existing receipt's bytes against the merge base, never the diff's shape; known-bad controls in `tests/test_check_receipts.py`). The registry ships **empty**: authorizing the first receipt is Michael's, and no receipt may be written until he approves one. Whether the envelope is represented in `standards-profile.schema.json` also remains undecided. | Michael |

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
