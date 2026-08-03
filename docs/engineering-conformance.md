# Cross-repository engineering conformance

`standards_control` is the development-only engine proposed by ADR 0006. The
checked-in profile is `candidate` because the ADR is `Proposed`; a green run is
not activated policy or a compliance claim.

Each strict profile names repository URL/default branch, its checked-in
governance source, protected resources with one owner/writer boundary, drift
tests, and exact Python contract surfaces. The typed gate rejects `Any`, missing
or bare public annotations, unannotated record fields, and mutable boundary
records. Schema version 1 has no waiver mechanism.

Run locally (where `origin/HEAD` resolves the default branch):

```bash
python3 -m standards_control verify --root . \
  --profile .dotmac/standards-profile.json
```

CI passes trusted repository metadata explicitly:

```bash
python3 -m standards_control verify --root . \
  --profile .dotmac/standards-profile.json \
  --default-branch main --format json
```

Product CI consumes the composite action at the exact accepted Governance
commit; a mutable branch or tag is not an admissible policy identity:

```yaml
- name: Enforce Dotmac engineering standards
  uses: michaelayoade/dotmac_governance/.github/actions/standards-check@<accepted-40-character-sha>
  with:
    default-branch: ${{ github.event.repository.default_branch }}
```

The action invokes the Governance-owned engine against the caller workspace.
It installs nothing into the product runtime and retrieves no credential.
Repository access for private actions remains runner configuration, not logic
copied into the action.

Product rollout is inventory, candidate profile, local repairs with sabotage
proofs, accepted governance plus required mode, green CI merge, then protected
branch read-modify-write and independent readback. Git and product CI remain
authoritative; Knowledge may index only source pointers and structured results.
