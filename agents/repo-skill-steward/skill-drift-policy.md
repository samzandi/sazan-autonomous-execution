# Skill Drift Guard

A project-local Skill must never be overwritten merely because a canonical Skill with the same name exists.

## Classification

- exact-copy: canonical and installed contents are identical. A verified refresh may be proposed later, but replacement still requires normal provenance, security, lab, and PR gates.
- same-name-local-drift: names match but contents differ. Treat the installed copy as potentially adapted. Preserve it and require a manual upstream review.
- different-skill: names differ. Do not sync.
- unverified-drift: metadata is incomplete or cannot establish identity. Do not sync.

## Rule

Same name is not proof that the local copy should match upstream. Project-specific instructions, acceptance gates, security rules, deployment constraints, or business context may intentionally diverge.

The Steward may generate a diff or migration proposal. It must not silently replace the project-local Skill.
