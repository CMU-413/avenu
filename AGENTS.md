# Agent Operating Guidelines

## Planning Workflow

### 1. Understand Goals
- Ask clarifying questions to fully understand user intent before planning.

### 2. Analyze Existing Code
- Inspect the current codebase before proposing changes.
- Use existing abstractions and patterns as the foundation.

### 3. Create Plan File
- Create a markdown file in `docs/02-plans/`:
  - Format: `plan-<slug>.md`
- Plans must:
  - Be concise and implementation-focused
  - Avoid unnecessary prose
  - Be incrementally executable (2–3 logical phases)

---

## Plan Structure Requirements

### Phases
Each phase must include:
- Affected files
- Summary of changes per file
- Inline unit tests (only relevant, lightweight tests)

### Task Checklist
- At the top of the plan
- Organized by phase
- Use checkboxes:
  - ☐ incomplete
  - ☑ complete
- Keep tasks concise and actionable

---

## Code Design Principles

### Simplicity First
- Prefer **simple over easy**
- Avoid unnecessary abstractions
- Minimize coupling

### Avoid Complecting
- Keep concerns independent:
  - State vs time
  - Data vs behavior
  - Config vs code
- Prefer composition over interleaving

### Favor Values
- Prefer immutable data
- Scope mutable state tightly

### Declarative > Imperative
- Describe *what* should happen, not *how*

### Naming
- Follow existing conventions
- Use terse, descriptive, idiomatic names

---

## Testing Rules

- Only include **unit tests**
- No:
  - manual testing
  - integration tests
  - UI tests
  - heavy mocking
- Tests must:
  - directly validate logic introduced in the phase
  - be colocated with relevant phase

---

## Strict Constraints

- DO NOT include:
  - exploration steps (e.g. searching, grepping)
  - migration plans
  - backward compatibility layers
  - feature flags
  - release plans
  - “future work” sections
  - summaries or conclusions

---

## Open Questions

- MUST be clearly listed at the top of the plan
- Required when ambiguity exists
- Ask for clarification before proceeding if needed

---

## Quality Bar

A valid plan should:
- Be immediately implementable
- Require minimal interpretation
- Avoid hidden complexity
- Allow a new engineer to modify parts independently

---

## Core Philosophy

Follow principles inspired by Rich Hickey:

- Simple over easy
- Composition over entanglement
- Data over state
- Clarity over convenience

Evaluate decisions based on:
- Changeability
- Readability
- Independence of components
