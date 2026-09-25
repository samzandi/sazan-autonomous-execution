# Candidate Lab

Third-party repository, skill, and agent candidates are not installed into production projects directly.

## First candidate: skills CLI

Pinned candidate:

- canonical source: vercel-labs/skills
- package: skills
- observed version: 1.7.0
- license: MIT
- minimum Node.js requirement observed in the source package: 22.20.0

## Security observations

The CLI includes optional telemetry and a remote audit lookup. The source exposes both DO_NOT_TRACK and DISABLE_TELEMETRY controls. Steward lab runs set both variables and do not provide repository, cloud, or production secrets.

The package has no preinstall, install, or postinstall lifecycle script in its own package.json. Lab execution also sets npm_config_ignore_scripts=true so dependency lifecycle scripts are not executed during the smoke test.

## Lab boundary

The first smoke test is deliberately read-only:

1. resolve the pinned package version;
2. print version;
3. exercise global help and update help;
4. list skills in an isolated empty directory as JSON;
5. verify that no project skill lock or agent skill directories are created.

The lab does not run the update command itself against real installed skills. Update mutation is a later test with disposable fixtures.

## Promotion rule

A successful read-only smoke test moves the candidate from approved-for-lab to readonly-smoke-passed. It does not authorize global installation or updates on the user's machines.
