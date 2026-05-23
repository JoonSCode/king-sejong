# Uigwe Example Set

This folder contains draft example flows for Uigwe.

`deep-interview`, `brainstorming`, and `decomposition` in these examples are Uigwe internal phase ids, not separate required skills.
The preferred user-facing labels are `Intent Clarification`, `Design Exploration`, and `Executor Handoff Contract`.

## Included Examples

### `greenfield-full-flow/`

Demonstrates:

- `Intent Clarification (deep-interview) -> Design Exploration (brainstorming) -> Executor Handoff Contract (decomposition)`
- a `greenfield` profile
- full packet progression:
  - `intent.packet.json`
  - `design.packet.json`
  - `plan.packet.json`
  - `goal-tree.json`

### `brownfield-decompose-only/`

Demonstrates:

- `decompose-only` entry
- a `brownfield` profile
- starting from an already approved design packet
- producing:
  - `design.packet.json`
  - `plan.packet.json`
  - `goal-tree.json`

## Notes

- These examples are illustrative protocol artifacts, not production task plans.
- Paths inside the example packets may refer to hypothetical workspaces or future files.
- The schema-validated artifacts are the JSON packet and goal-tree files.
