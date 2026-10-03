# Sazan Frontend Quality Gate

Use this gate for material UI work before a frontend change is considered verified.

## 1. Design contract

- A project-local DESIGN.md or equivalent design brief exists.
- The product purpose, audience, primary task, visual direction, and platform are explicit.
- The child visual identity inherits Sazan brand DNA without blindly copying another Sazan product.
- Existing product constraints override generic external design examples.

## 2. Theme behavior

For application UI, the default target is Light + Dark + System.

- System follows the operating-system preference.
- A user override is allowed when the platform supports it.
- The user's explicit choice persists.
- Both themes preserve contrast, hierarchy, legibility, and brand identity.
- Theme switching must not create layout shifts or unreadable assets.

A project may document a justified exception when its surface genuinely does not support theming.

## 3. Responsive and interaction quality

- Validate intended phone, tablet, and desktop breakpoints when applicable.
- No clipped primary actions, accidental horizontal scrolling, or unreachable controls.
- Keyboard access and visible focus are required for interactive web UI.
- Hover-only behavior cannot hide essential actions.
- Reduced-motion preferences must be respected.
- Loading, empty, error, offline, and success states must be designed where relevant.

## 4. Visual quality

Reject obvious generic AI output such as:

- arbitrary purple/blue gradients with no product rationale;
- cookie-cutter card grids used as a default;
- inconsistent radii, spacing, shadows, or typography;
- decorative animation that obscures function;
- oversized branding that dominates the product task;
- copied reference styling that conflicts with the Sazan child identity.

Use the official Anthropic frontend-design skill for primary visual direction, selected Taste Skill subskills for specialist work, and Awesome Design MD only as a reference library.

## 5. Standards audit

For web UI:

- run the pinned Vercel web-design-guidelines review;
- classify findings as blocking, important, or advisory;
- fix blocking accessibility and interaction defects before promotion.

Do not load mutable remote guidance from an unpinned branch during a production decision.

## 6. Browser verification

For runnable web UI, use the steward-approved pinned Playwright CLI after it has passed the candidate lab.

Minimum evidence:

- application opens successfully;
- primary user flow completes;
- no uncaught console errors during the tested flow;
- screenshots exist for the primary desktop and mobile states;
- Light and Dark are checked when both are supported;
- System mode behavior is checked where the runtime exposes it;
- failed scenarios are captured, not silently ignored.

## 7. Completion language

- Designed: design contract and intended UI are defined.
- Implemented: code contains the intended UI behavior.
- Verified: the quality gate was executed and evidence was inspected.
- Production-ready: only after project-specific end-to-end requirements also pass.

No evidence = not verified.
