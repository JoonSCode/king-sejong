# Uigwe Wrapper Surface Draft

**Status:** Draft

## Purpose

The Uigwe wrapper surface is the future outer entry point for invoking the Uigwe protocol through a stable request and result contract.

It exists to make Uigwe easier to call without redefining the protocol itself.

When this document refers to `deep-interview`, `brainstorming`, and `decomposition`, those names mean Uigwe's internal protocol stage ids.
Machine-readable re-entry target ids remain `local_reexploration`, `brainstorming`, `deep_interview`, and `human_review`.
The `deep_interview` re-entry target maps back to the `deep-interview` stage.
The preferred user-facing labels are `Intent Clarification`, `Design Exploration`, and `Execution Planning`.
They are not separate required skills.

Current repo-local draft skill:

- `../../.agents/skills/uigwe/SKILL.md`

Installed skill surfaces may exist as repo-backed front doors, but the repo-local skill remains the behavioral source of truth for live-session wording and stage guidance.

The wrapper is not:

- the planner core
- the default consumer
- a replacement for packet and goal-tree artifacts
- the Sejong router/front door

Instead, it is a thin orchestration surface that:

- accepts a request
- determines the correct Uigwe entry mode
- runs the relevant Uigwe protocol phases or delegates their orchestration without changing their internal ownership
- returns a structured result that points to the canonical Uigwe artifacts

## Sejong Compatibility

`Sejong` may route a broad request into the wrapper, but the wrapper must still preserve Uigwe's stage ownership. User-facing Sejong language must not rename or skip Uigwe's live stages: `1단계: 기획 명확화`, `2단계: 설계 명확화`, and `3단계: 실행 계획화`.

When Sejong routes to formal planning, the wrapper should resolve `full`, `design-to-plan`, or `decompose-only` exactly as it would for Uigwe. When Sejong routes to execution, the wrapper should record Seungjeongwon handoff metadata only after the Uigwe bundle is valid.

## Boundary Rules

The wrapper must preserve these boundaries.

### Wrapper Responsibilities

- accept invocation requests
- select or confirm the entry mode
- package input artifacts for Uigwe
- preserve Uigwe's interactive stage behavior in live sessions rather than collapsing it into one-shot artifact generation
- return result metadata and artifact locations
- record the requested post-planning handoff lane without executing it itself

### Protocol Responsibilities

- conduct Uigwe's internal `Intent Clarification` (`deep-interview`), `Design Exploration` (`brainstorming`), and `Execution Planning` (`decomposition`) phases
- apply readiness-gated entry logic
- manage re-entry and backtracking
- generate packets, `goal-tree`, `spec`, and `rationale`

In a live session, the wrapper must surface Uigwe's clarification questions and approval requests to the user. It must not silently waive those gates unless the context is explicitly non-interactive or the user explicitly waives them.
In those user-facing messages, the wrapper should prefer plain-language stage descriptions such as `1단계: 기획 명확화`, `2단계: 설계 명확화`, and `3단계: 실행 계획화`, plus approximate readiness with the main unresolved areas. It should avoid leading with packet names by default and should not promise a fixed number of next questions.

### Consumer Responsibilities

- execute `executable_leaf` nodes
- enforce dispatch, critic, and verifier rules
- emit consumer feedback

### Executor Responsibilities

- accept the validated Uigwe bundle after planning
- preserve the bundle as the source of truth for execution
- hand off execution to Seungjeongwon
- return execution feedback or re-entry recommendations

The wrapper must not absorb planner or consumer logic into its own contract.

## Invocation Modes

The wrapper supports the same effective entry modes as Uigwe:

- `auto`
- `full`
- `design-to-plan`
- `decompose-only`

## Suggested User-Facing Invocation

This draft assumes a skill-style surface such as:

- `$uigwe <brief>`
- `$uigwe full <brief>`
- `$uigwe design-to-plan <brief-or-intent-artifact>`
- `$uigwe decompose-only <approved-design-artifact>`

The wrapper contract does not require this exact syntax, but these examples represent the intended shape of a lightweight user-facing surface.

### `auto`

The wrapper inspects the provided artifacts and selects the strongest valid entry point.

This should be the default mode.

### `full`

Use when only a vague goal or brief exists.

### `design-to-plan`

Use when intent is already clarified strongly enough to skip the Uigwe `Intent Clarification` (`deep-interview`) phase.

If that assumption proves false during live interaction, the wrapper must re-enter `deep-interview` and continue interactively with the user.

### `decompose-only`

Use when an approved design already exists and `Execution Planning` (`decomposition`) is the only missing stage.

## Inputs

The wrapper accepts one request object.

The request includes:

- a natural-language brief
- explicit profile selection
- explicit mode selection
- explicit executor handoff selection
- explicit direct consumer handoff selection
- existing packet paths
- existing `spec` or `rationale` paths
- output directory preferences
- a request to prepare post-planning execution handoff metadata

The request should always carry both routing fields:

- `executor_handoff`
- `consumer_handoff`

Use `none` for any lane that is not requested.

The wrapper should prefer explicit artifacts over inferred context.

## Artifact Storage

The wrapper follows [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md).

Default generated artifacts are external nontracked artifacts under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`. The wrapper should still return artifact locations, but those locations should not be assumed to be repository-tracked paths.

If the user explicitly asks for a repo-tracked plan or bundle, the wrapper may resolve the output directory to a repository path and should report that promotion clearly.

## Outputs

The wrapper returns one result object.

The result includes:

- resolved mode
- resolved profile
- planning status
- generated artifact paths
- requested executor handoff
- requested direct consumer handoff
- whether planner re-entry was needed
- high-level notes or blockers

The wrapper result is a summary layer. The canonical planning truth remains in Uigwe artifacts such as:

- `Intent Packet`
- `Design Packet`
- `Plan Packet`
- `goal-tree.json`

## Resolution Rules

### Mode Resolution

If the user or caller selects `auto`, the wrapper should resolve mode in this order:

1. `decompose-only` if a valid design artifact is present
2. `design-to-plan` if intent is strong enough but design is not yet sufficient
3. `full` otherwise

### Profile Resolution

If the user or caller selects `auto`, the wrapper should resolve profile based on whether the work is primarily:

- `greenfield`
- `brownfield`

If mixed, the wrapper should prefer `brownfield` whenever existing system constraints materially dominate execution safety.

## Handoff Rules

The wrapper should always echo the selected routing fields in both the request and result.

After planning completes:

- route substantial execution to Seungjeongwon when `executor_handoff = seungjeongwon`
- request a lower-level direct consumer lane only when `consumer_handoff = codex`
- keep those two active post-planning lanes mutually exclusive

Allowed executor handoff values:

- `none`
- `seungjeongwon`

Allowed direct consumer handoff values:

- `none`
- `codex`

Operational recommendation:

- use `executor_handoff = seungjeongwon` as the default substantial-work execution path after planning
- use `consumer_handoff = codex` only when a lower-level direct consumer lane is explicitly desired
- use `executor_handoff = none` and `consumer_handoff = none` when planning should stop without execution preparation

Even when either handoff is requested, the wrapper should not claim execution success on behalf of the executor or consumer.

It may only report:

- planning completed and executor handoff prepared
- planning completed and Seungjeongwon execution requested
- planning completed and direct consumer handoff requested
- planning blocked before handoff

## Failure And Escalation

The wrapper should surface these outcomes explicitly:

- `completed`
- `blocked`
- `needs_human_review`

The wrapper should recommend rather than hide escalation when:

- supplied artifacts disagree
- the selected mode is invalid for the available artifacts
- readiness gates fail
- Uigwe re-entry indicates unresolved upstream ambiguity

## Canonical Artifact Bundle

When planning succeeds, the wrapper should point to the generated Uigwe bundle:

- `intent_packet_path` when generated
- `design_packet_path` when generated
- `plan_packet_path`
- `goal_tree_path`
- `spec_path`
- `rationale_path`

If executor handoff is prepared, the wrapper should also report:

- `executor_request_path`
- `handoff_prompt_path`
- `execution_feedback_path`
- `executor_result_path`

If `executor_handoff = none`, those executor artifact paths should be omitted rather than invented.

## Non-Goals

This wrapper draft does not define:

- a CLI syntax
- a chat-command syntax
- an automation schedule format
- implementation details of any specific shell, app, or IDE integration

Those should be layered on top of the wrapper contract rather than mixed into it.
