# 0029. A production-accepted profile never publishes a simulation

- Status: Accepted
- Date: 2026-08-31
- Effective: 2026-08-31
- Owner: Michael Ayoade
- Approver: Michael Ayoade
- Scope: Governance-enrolled Dotmac repositories, and every assembly that selects its published surfaces by profile
- Classification: Internal

## Context

### The measured instance

`dotmac_platform_control_plane` (Platform CP), repaired in pull request #93,
*Stop publishing the provisioning simulation in production*, merged
`8a2ac5a2eba4a4f82c144deb2d6fd1dd2094da24` at 2026-08-31T07:59:27+01:00. The
product's own record is its ADR-0015, *The production surface policy, and the
profile that states it*, `ACCEPTED` 2026-08-31, path
`docs/adr/0015-production-surface-policy.md`. Every claim below was read from
that repository at the merge commit and at its parent, not restated from a
summary.

`vendor_cp.providers.build_provisioning_provider` builds exactly one
implementation of the kernel's provisioning contract:
`LaboratoryProvisioningProvider` (`src/vendor_cp/provisioning/laboratory.py:28`),
a side-effect-free simulation that invents a plan, pretends to apply it, and can
be asked to pretend to fail. It is not a stub standing in for a real driver
behind the same routes. **There is no other implementation.**

The `production-bootstrap` profile, at version 2, withheld `licence_delivery`
and `offers`. It did not withhold `provisioning`. The production host therefore
published four authenticated routes —

```
POST /platform/vendor/provisioning/plan
POST /platform/vendor/provisioning/apply
GET  /platform/vendor/provisioning/operations/{id}
POST /platform/vendor/provisioning/operations/{id}/cancel
```

— in the real response shapes, with nothing marking them as fiction. An operator
calling `apply` received a fabricated result through an authenticated production
API and had no signal that would let them tell the difference.

The second half is quieter and was found in the same pass.
`load_deployment_profile` fell back to the `full` profile whenever
`VENDOR_DEPLOYMENT_PROFILE` was unset — **everywhere, including production** —
and `full` publishes every withheld surface. `scripts/deploy_production.sh`
greps the host env file for the exact line, which covers the deploy path and
only the deploy path: a container restarted by `docker compose up`, by the
Docker daemon's restart policy, or by a host reboot never passes that grep.

### Why this is a fleet rule and not a Platform CP fix

It is a category error, not a misconfiguration. Any assembly that selects its
published surfaces by profile can make it, and three of them are governed here:
`dotmac_starter_mt`, `dotmac_sub` and `dotmac_erp` each compose modules behind a
profile or feature switch.

**A simulation published in production is worse than an absent surface.**
Absence is legible: the route 404s, the caller sees the gap, someone fixes it. A
fabricated success is not legible: the caller receives a well-formed response,
in the real shape, asserting work that never happened. This is the family
[ADR 0026](0026-a-running-object-states-its-identity.md) § Context named for a
different subject — a system that answers from whatever it can see "will always
find an answer, and the answer is unfalsifiable." It is the same family as a
check that cannot fail for the reason it is named for
(`dotmac_starter_mt` ADR-0018's 2026-08-26 amendment) and as a receipt that
records intent rather than effect ([ADR 0018](0018-authority-cutovers-leave-receipts-and-decommissions-retire-delegations.md)
§ 1's `runtime_observation`).

### An enforced control was already adjacent, and it did not cover this

This is the part of the context that changes what may be claimed elsewhere, so
it is stated exactly.

[ADR 0008](0008-kernel-testing-kit-import-locality.md) (`Accepted` 2026-08-11)
does carry a real Governance engine control: standards-profile schema 4's
`testing_kit_boundary` and the diagnostic `testing-kit.import.forbidden`, which
fires when non-test runtime code imports `dotmac_kernel.testing`. That record's
Consequences named this very product:

> `dotmac_vendor_control_plane/src/vendor_cp/providers.py` currently imports
> `FakeProvisioningProvider` from the kit at runtime. Schema-version-4 adoption
> must repair that product defect […]

Measured at Platform CP `main` `8a2ac5a2`: there is **no remaining runtime
import of `dotmac_kernel.testing`** anywhere under `src/`, and the repository's
profile is at `schema_version` 9 with a `testing_kit_boundary` declaring
`test_roots: ["tests"]`, no kit source roots and no conformance probes. The
detector is green, and correct to be green: the product imports only the kernel
provisioning CONTRACT (`dotmac_kernel.providers.provisioning`), never the kit.

The sequence that produced that green is the finding. Platform CP PR #35,
`babad31`, merged 2026-08-11T12:56 — **the same day ADR 0008 was accepted** —
introduced `src/vendor_cp/provisioning/laboratory.py` and removed the last
`FakeProvisioningProvider` reference from `src/`. The named product defect was
discharged by making the simulation **product-local** rather than kit-sourced.
The simulation then stayed mounted in the production profile for a further
twenty days, until PR #93.

No intent is asserted here, and neither is the ordering: both fall on
2026-08-11, and which came first within that day was not established. The
effect is what matters and it is measurable. An import-locality detector answers
"where did this simulation come from", and the harm depends on "what does this
profile publish". **A control was satisfied by
relocating its subject, while the risk it was adjacent to was untouched.** A
product-local simulating provider is structurally invisible to
`testing-kit.import.forbidden`, and this record must not be read as extending
that family's coverage.

### Authority status

Michael Ayoade ratified the rule below on 2026-08-31 and directed the same
ordering as [ADR 0028](0028-a-deployment-verifies-only-what-it-can-repair-or-prove-provisioned.md):
the ruling lands here before the corresponding Knowledge entry is promoted, so
the checked-in record is the authority and Knowledge is discovery support. The
approval is his; § "Acceptance — 2026-08-31" records it as an attributable
event and is transcribed, not made, by the drafting agent.

## Decision

### 1. The standard

> A production-accepted profile may not publish a surface whose only
> implementation simulates.

**"Publish" is the operative verb.** The defect is not that a simulating
implementation exists — every product needs one — but that a profile a
production host may run MOUNTS it, so the surface answers real callers. The same
object reachable only from a laboratory profile is a fixture; reachable from a
production-accepted profile it is a fabrication service.

The rule has three parts. They are stated separately because they **fail
separately**, and a system holding only some of them is covered only in part.

### 2. Structural — the invalid combination cannot be represented

A profile exposing a simulating surface **declares itself a laboratory**, and a
laboratory profile can **never** be production-accepted. Both halves are checked
at **construction**, so the invalid pairing cannot be written down at all rather
than being caught by a test that someone must remember to run.

The reference shape, `VendorDeploymentProfile.__post_init__`
(`src/vendor_cp/deployment_profile.py:209-220`), refuses in two clauses:

```python
if self.exposes(PROVISIONING_SURFACE) and not self.laboratory:
    raise ValueError(... "must declare laboratory=True (ADR-0015)")
if self.laboratory and self.production_accepted:
    raise ValueError(... "a laboratory answers operators with "
                     "fabricated results and is never accepted in production")
```

Two clauses and not one: the first binds the surface to the declaration, the
second binds the declaration to the acceptance. Collapsing them would let a
profile that simply forgets the flag pass the second.

### 3. Environmental — production refuses at boot, keyed on the PROVIDER MODE

A production environment **refuses at boot** a profile that mounts a simulating
surface. The refusal is keyed on the **provider mode — the fact — and never on
the profile's own laboratory flag, which is a claim.**

This is the load-bearing part and the easiest to get wrong, because the obvious
implementation trusts the profile's declaration. **A profile that lies about
itself passes a check keyed on its own flag.** § 2 protects the profiles
declared inside one repository; § 3 protects the process that actually boots,
including a profile § 2 never saw.

The reference shape, `validate_profile_for_environment`
(`src/vendor_cp/deployment_profile.py:365-393`), takes `provider_mode` as a
parameter and compares it — not `profile.laboratory` — against the fake-provider
mode, raising `ProductionProfileRefusedError`. Its docstring states the reason
in the same terms:

> the provider mode is what decides whether an operator calling
> `POST /platform/vendor/provisioning/apply` receives a real result or an
> invented one, and that is the harm being prevented.

§ 2 makes § 3 unreachable in that repository today. **§ 3 is written anyway**,
and a system that argues § 2 makes § 3 redundant has misunderstood which of them
is load-bearing.

### 4. No silent fallback to a permissive default

Production has **no default profile**. An unset or blank profile selector in a
production environment **fails the boot**; it does not inherit a composition.

Outside production a default is correct — a developer should see the whole
assembly. In production the permissive default publishes exactly the surfaces
every other rule withholds, so the fallback silently defeats §§ 2 and 3 without
either of them being wrong.

A deploy-script check on the host environment file is a legitimate **early**
check and is never the only one: it covers the deploy path and nothing else. A
container restarted by the daemon's restart policy or by a host reboot does not
traverse the deploy script.

### 5. The guard derives its subject set from the assembly

A guard over a **hand-maintained list of what to check** is a guard with a hole
that grows every time the system does. The set a guard iterates is **derived
from the composition it is guarding**, never enumerated beside it.

This is stated as a rule because the measured instance demonstrated it, and the
demonstration is precise. At `8a2ac5a2^`,
`tests/architecture/test_deployment_profile.py::test_every_profile_composes_all_persistence_owners`
asserted five stateful modules by hand — `release_catalog`,
`entitlement_allocation`, `approvals`, `commercial_agreements`, `licensing` —
while `vendor_cp.assembly.STATEFUL_MODULES` composed **six**.
`deployment_control_module` was covered by nothing, and the assertion was green.

The repaired form iterates the assembly's own tuple:

```python
stateful = {module.code for module in assembly.STATEFUL_MODULES}
for profile in PROFILES:
    assert not (profile.withheld_surfaces & stateful), profile.code
```

The hole was **not introduced by the repair**; it pre-existed it, and the repair
closed it. That is the ordinary shape: a hand-maintained guard is correct on the
day it is written and silently narrows afterwards, which is
`dotmac_starter_mt` ADR-0018 rule 1 — enumerate the family, not the members.

### 6. What this record does not do

- It does not forbid simulating implementations. It governs which profiles may
  publish them.
- It does not require a real implementation to exist before a surface may be
  designed. A surface with no real implementation is withheld, not faked.
- It does not extend ADR 0008's `testing_kit_boundary` family. A product-local
  simulation is invisible to `testing-kit.import.forbidden`, and claiming
  otherwise would be the coverage error this record is about.
- It does not decide whether any of this becomes an engine control — open
  decision 35 — nor whether the other three profile-selecting assemblies are
  measured against it, which is open decision 36.

## Consequences

- Every assembly that selects surfaces by profile must be able to say, per
  profile, which of its published surfaces have only a simulating
  implementation. Some will not currently be able to answer, which is the record
  functioning.
- A surface with no real implementation becomes visibly unfinished rather than
  apparently working. Roadmaps that read as "done" because a route responds will
  be corrected downward.
- §§ 2 and 3 are deliberately redundant in a healthy system. A reviewer who
  removes one as duplication has removed the half that protects against the
  other's premise being false.
- § 5 makes hand-enumerated guards a review finding fleet-wide, and the fleet has
  more of them than the one measured here.
- Discharging a control by relocating its subject — as the kit-import repair did
  — is now a named pattern rather than an unremarkable refactor. It is not
  misconduct; it is a thing a reviewer must look for, because the control goes
  green either way.
- Enrolled repositories acquire no new failing check from this record.

## Drift prevention

**Enforcement status: none yet.** No `standards_control` rule evaluates this
record, no `standards-profile.schema.json` field represents a profile's
production-acceptance or its providers' modes, and no engine diagnostic exists
for it. This is stated review discipline, which ADR 0013 § 5 permits so long as
it is said plainly rather than implied.

Confirmed at this repository's `main` `fb06c4f` rather than carried over from
[ADR 0028](0028-a-deployment-verifies-only-what-it-can-repair-or-prove-provisioned.md):
`standards_control._governance` resolves exactly the one path each enrolled
profile declares as `governance_model.source` and reads a single `- Status:`
line from it; nothing in `standards_control`, `gate_control`, `agent_control`,
`programme_control` or `.github/workflows/` reads the ADR directory at all —
only `tools/check_adrs.py`, which runs in this repository's own CI. All seven
enrolled profiles pin the same source,
`docs/adr/0006-cross-repository-engineering-conformance.md`, expecting status
`accepted`. **Adding this record turns no gate red in any enrolled repository.**

What would be **decidable from repository content**, stated in advance so a
future family cannot be built without its known-bad cases:

- a declared production-accepted profile whose published surface set includes a
  surface the repository also declares as simulation-only;
- a profile-selection function whose unset branch returns a profile rather than
  raising, on a path reachable with a production environment value;
- an environment refusal that reads the profile's own laboratory-style flag
  instead of the provider mode — a check keyed on the claim, which is § 3
  violated in a way visible in the source;
- a guard iterating a literal collection of module or surface names where the
  assembly exports the corresponding tuple — the § 5 shape, and the one most
  likely to be read as style rather than as a hole.

**Not decidable, and outside what this repository may assert** under ADR 0013
§ 1: which profile a production host actually ran, and whether any real caller
received a fabricated result. Those are `deployment_run`-shaped facts and no
machine-readable contract declares that oracle (open decision 17, unchanged).
This record therefore describes what the production host *published*, which is
derivable from the profile definition, and does not assert what it *served*.

**Non-vacuity.** Any future family gets a planted violation shown RED beside a
conforming repository shown green. The specific trap, and the reason this record
exists: **a checker that verifies a profile declares itself correctly passes a
profile that declares itself incorrectly.** § 3's whole content is that the
declaration is not the fact. A detector that reads only declarations has
reproduced the defect it was built to find — the same shape as ADR 0028's trap,
arriving from the opposite direction.

Whether any of this is built, and by whom, is open decision 35. Acceptance of
this record does not make that decision and does not create the family described:
a standard being normative is not evidence that a control enforces it.

## Acceptance — 2026-08-31

Michael Ayoade approved this record on 2026-08-31. Under `AGENTS.md` an agent may
not occupy the approver role or approve its own output; neither happened here.
The standard in § 1 and the three-part shape in §§ 2-4 are his, transcribed;
§ 5 is the generalisation he directed from the same repair's coverage defect.

Acceptance covers the standard and its parts. It does not assign an enforcement
owner, does not schedule any measurement of the other profile-selecting
assemblies, and does not extend this repository's `Amends:` relationship to
`dotmac_starter_mt` ADR-0018 or to Platform CP ADR-0015 — that field is scoped to
this repository's own ADR directory, so both relationships are stated in prose
above, and their propagation is open decision 36, the same situation as open
decisions 20, 31 and 34.
