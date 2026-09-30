You are performing the C003 Codex runtime proof for Sazan Repository Intelligence.

This is a read-only verification task. Do not edit, create, delete, rename, or format repository files. Do not change git configuration. Do not install additional packages. Do not print environment variables, credentials, tokens, or secrets.

Use shell commands only as needed to verify the following against the checked-out repository:

1. Record the exact repository HEAD with:
   git rev-parse HEAD

2. Record the initial workspace state with:
   git status --porcelain

3. Run the focused regression tests:
   python3 -m unittest tests/test_repository_intelligence_e2e.py tests/test_repository_intelligence_orchestration.py

4. Execute the promoted deterministic baseline:
   python3 agents/repo-skill-steward/repository-intelligence/scripts/run_c002_e2e_lab.py --output /tmp/c002-codex-runtime-proof.json --require-verified

5. Inspect /tmp/c002-codex-runtime-proof.json and verify:
   - status is verified;
   - every check is true;
   - orchestration status is ready-for-parent-review;
   - auto-promotion is disabled;
   - private identity redaction passed.

6. Inspect the relevant orchestration and evidence code only as needed to confirm that the parent-review boundary is enforced and auto-promotion cannot occur.

7. Record the final workspace state with:
   git status --porcelain
   The final workspace state must exactly match the initial workspace state.

Return only one JSON object that conforms to the provided output schema. Do not wrap it in markdown.

Set status to "verified" only when every required check succeeds. Otherwise set status to "blocked", set any failed checks to false, and include concise blockers. Evidence strings must describe concrete commands or repository artifacts used for the decision. Never include secret values or private repository source names.
