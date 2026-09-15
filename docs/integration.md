# Integration Guide

Sazan Autonomous Execution is a policy layer. Integrate it by making `SKILL.md` and the relevant repository/project instructions available to the agent before task execution.

## ChatGPT / tool-using agents

Use `SKILL.md` as the execution policy for multi-step work. The agent should perform available safe tool actions consecutively, verify material results, and return control only at completion or a genuine blocker.

Current evidence: the ChatGPT + GitHub path has a recorded real multi-step run in `tests/runtime-integration-evidence.md`.

## Codex / coding agents

Place or reference the policy in the project instruction context. Project-specific build/test commands remain authoritative. The autonomous policy controls continuation and escalation; it does not replace repository-specific engineering rules.

Status: integration guidance defined; runtime verification not yet recorded in this repository.

## Claude Code

Expose the policy as project instructions or a reusable skill according to the environment's supported mechanism. Keep any Claude-specific adapter separate from the platform-neutral core.

Status: integration guidance defined; runtime verification not yet recorded in this repository.

## GitHub agents

Use `AGENTS.md` plus `SKILL.md` where supported. Repository-specific issue/PR acceptance criteria should become task acceptance criteria and evidence gates.

Status: policy compatible; connector-based GitHub operations verified through ChatGPT, but independent GitHub-agent runtime verification is not yet recorded.

## Other agents

Map the state machine to the platform's planning/tool loop without weakening:

- the non-stop rule;
- strict stop conditions;
- recovery before escalation;
- evidence-based completion;
- production-ready restrictions.

## Support matrix

| Environment | Policy defined | Real runtime evidence |
| --- | --- | --- |
| ChatGPT + GitHub connector | YES | YES |
| Codex | YES | NO |
| Claude Code | YES | NO |
| Independent GitHub agent runtime | YES | NO |
| Other agents | Generic | NO |

Do not interpret platform-neutral design as proof of runtime behavior on every platform.
