# Repo & Skill Steward validation scenarios

## Goal

Validate the read-only repository inventory and the policy gates before any update automation is promoted.

## Scenario 1 — authenticated inventory

Given a valid GitHub token with repository read access, the inventory command must:

- enumerate accessible repositories;
- report visibility and default branch;
- detect common dependency manifests;
- detect AGENTS.md, SKILL.md, and START_HERE.md;
- detect top-level test directories;
- list GitHub Actions workflow filenames when available;
- perform no write operation.

Expected result: inventory JSON is produced and no repository content changes.

## Scenario 2 — missing credential

Given no GitHub token, the command must exit with a non-zero status and a clear credential error.

Expected result: no network write and no partial update.

## Scenario 3 — private repository privacy

Given a private repository and the public-safe flag, the output must redact its full repository name.

Expected result: the record remains useful for aggregate analysis without disclosing the private repository identity.

## Scenario 4 — partial API failure

Given one repository whose contents cannot be read, the inventory should record an error for that repository and continue scanning the rest.

Expected result: one failure does not invalidate the whole inventory.

## Scenario 5 — update candidate

Given a repository with a dependency manifest and CI workflows, the steward may classify it as update-capable, but it must not promote an update until:

1. a candidate version or upstream change is identified;
2. security review is complete;
3. project-specific tests run;
4. behavior is verified;
5. a rollback path exists.

## Scenario 6 — skill or agent candidate

Given a new skill or agent from an external source, the steward must record provenance, license, requested permissions, maintenance status, duplication risk, and lab result before promotion.

Expected result: no direct installation into a production project from discovery alone.
