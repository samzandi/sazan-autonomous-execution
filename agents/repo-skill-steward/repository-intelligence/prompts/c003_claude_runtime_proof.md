You are performing the C003 Claude Code runtime proof for Sazan Repository Intelligence.

This is a read-only verification task. Do not edit, create, delete, rename, or format repository files. Do not change git configuration. Do not install packages. Do not print environment variables, credentials, tokens, or secrets.

Verify the checked-out repository by using only the explicitly allowed read-only tools and commands:

1. Record the exact repository HEAD:
   git rev-parse HEAD

2. Record the initial workspace state:
   git status --porcelain

3. Record the Claude Code CLI version:
   claude --version

4. Run the focused regression tests:
   python3 -m unittest tests/test_repository_intelligence_e2e.py tests/test_repository_intelligence_orchestration.py

5. Execute the promoted deterministic baseline:
   python3 agents/repo-skill-steward/repository-intelligence/scripts/run_c002_e2e_lab.py --output /tmp/c002-claude-runtime-proof.json --require-verified

6. Read /tmp/c002-claude-runtime-proof.json and verify:
   - status is verified;
   - every check is true;
   - orchestration status is ready-for-parent-review;
   - auto-promotion is disabled;
   - private identity redaction passed.

7. Inspect the orchestration/evidence code only as needed to confirm that parent review remains mandatory and automatic promotion is impossible.

8. Record the final workspace state:
   git status --porcelain
   It must exactly match the initial workspace state.

Return structured output only. Set status to "verified" only when every required check succeeds. Otherwise set status to "blocked" and include concise blockers. Evidence strings must describe concrete commands or repository artifacts. Never include secret values or private repository source names.
