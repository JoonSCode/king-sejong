# Sejong Router

**Status:** Draft

## Purpose

Sejong is the all-in-one OMX-style front door that decides the next useful lane and carries work through research, decision support, Uigwe planning, execution, verification, and evidence recording.

It exists because real user requests often say "research this", "think through this", "is this worth making", or "use Uigwe/의궤 for this" before the correct planning entry mode is known.

Sejong keeps Uigwe focused on its strongest job: converting clarified intent, evidence, and decisions into durable planning artifacts. Sejong owns the larger work loop around Uigwe: gather evidence, decide whether planning is useful, invoke Uigwe when needed, execute the selected work, verify the outcome, and record evidence.

This file is Sejong's routing contract. Sejong is not a new planning protocol and not a replacement for Uigwe. The canonical machine lane ids are `research-brief`, `decision-brief`, `uigwe-plan`, `executor-handoff`, and `direct-action`.

## Non-Goals

- It is not a replacement for the Uigwe protocol.
- It is not a replacement for the host execution backend; it orchestrates execution through Codex direct action or a handoff backend.
- It does not weaken Uigwe live-session approval gates.
- It does not create packets when the user only needs evidence or a lightweight decision.
- It does not create new active Korean lane ids; Korean names are user-facing aliases only.
- It does not turn `Danjong` into an active route.

## Sejong Naming Layer

Use Sejong language when it helps the user understand the broad front door:

| User-facing name | Canonical meaning | Machine contract |
| --- | --- | --- |
| `Sejong` | All-in-one front door for research, planning, execution, verification, and evidence | one or more existing router lanes |
| `JangYeongsil` | Research, experiment, evidence gathering, and unknown discovery | `research-brief` |
| `Jiphyeonjeon` | Debate, option comparison, recommendation, and decision support | `decision-brief` |
| `Seungjeongwon` | Execution handoff after a validated Uigwe bundle exists | `executor-handoff` through RalphExecutor |
| `Sillok` | Evidence records, scorecards, promotion notes, and decision history | validation and promotion artifacts |
| `Danjong` | Retired, rejected, or deposed options | rejected-alternative or archive semantics only |

Uigwe remains the formal planning protocol. When the router decides a canonical planning bundle is useful, Sejong routes to `uigwe-plan` and lets Uigwe own `Intent Clarification`, `Design Exploration`, and `Execution Planning`.

## Internal Structure

Sejong actively owns the end-to-end loop and then calls the selected surface:

| Role | Responsibility | Active call |
| --- | --- | --- |
| `Sejong` | All-in-one front door | choose the next lane, execute it, and continue when the user asked for an outcome |
| `JangYeongsil` | Research lane | gather evidence and produce a `research-brief` |
| `Jiphyeonjeon` | Decision lane | compare options and produce a `decision-brief` |
| `Uigwe` | Formal planning protocol | run `full`, `design-to-plan`, or `decompose-only` |
| `Seungjeongwon` | Persistent execution handoff lane | prepare RalphExecutor handoff from a validated bundle |
| `Sillok` | Evidence records | update scorecards, promotion notes, or decision history |
| `Danjong` | Rejected or retired option semantics | record rejection or retirement inside a decision/evidence artifact |
| `direct-action` | Clear immediate work | perform the task under normal workspace rules |

## Active Invocation Protocol

Do not stop at naming the lane. After classifying a request, execute the selected lane when enough context is available:

1. `research-brief`: inspect the available evidence, separate known/inferred/unknown facts, and name the next decision.
2. `decision-brief`: compare options, reject weaker paths with reasons, recommend one path, and name the next lane.
3. `uigwe-plan`: call into the Uigwe skill or protocol surface and preserve its live-session approval gates.
4. `executor-handoff`: inspect the bundle, prepare RalphExecutor handoff artifacts, and require execution feedback from the handoff backend before claiming completion.
5. `direct-action`: state briefly that planning is not needed, perform the clear task, and verify the result.
6. `Sillok` or `Danjong`: write evidence, archive, rejection, or promotion records rather than creating a new active lane.

If the user asked for an outcome such as "research, plan, and do it", Sejong may chain lanes:

```text
research-brief -> decision-brief -> uigwe-plan -> direct-action or executor-handoff -> evidence record
```

Stop early only when missing evidence, a user decision, or an approval gate is genuinely required.

## Lanes

### `research-brief`

Use for evidence gathering and situation understanding.

Required output:

- `known`: sourced facts from files, commands, official docs, or reviewed evidence
- `inferred`: conclusions that follow from the known facts
- `unknown`: unresolved facts or missing evidence
- `decision_question`: the decision this research is meant to enable
- `next_lane`: usually `decision-brief`, `uigwe-plan`, or `direct-action`

This lane is useful for the user's broad "만능/리서치" planning usage because it prevents early packet generation from hiding weak evidence.

### `decision-brief`

Use when the task is about choosing a direction.

Required output:

- decision to make
- options
- rejected options and reasons
- recommended option
- confidence
- risks
- next lane

This lane should be used before Uigwe planning when the main uncertainty is strategic rather than structural.

### `uigwe-plan`

Use when the desired output is a canonical Uigwe bundle.

Mode resolution:

1. `decompose-only` if there is an approved design artifact.
2. `design-to-plan` if intent is clear enough but design still needs selection.
3. `full` if intent, scope, non-goals, constraints, or success criteria remain materially unclear.

The router must call into the Uigwe skill or protocol surface rather than duplicating its packet rules.

### `executor-handoff`

Use after planning succeeds and the user wants persistent execution or a long-running completion loop.

The router may prepare RalphExecutor handoff instructions and should require execution feedback before reporting the end-to-end task as complete.

### `direct-action`

Use when a request is already clear enough to implement, answer, or verify directly in the current Codex session.

This protects Uigwe from becoming performative planning overhead while keeping execution inside Sejong's all-in-one surface.

## Routing Matrix

| User shape | Lane | Uigwe mode |
| --- | --- | --- |
| "세종으로 기획 잡아줘", "Sejong으로 라우팅해줘" | `uigwe-plan` when a bundle is needed, otherwise the best existing lane | resolved by evidence |
| "장영실처럼 조사해봐", "JangYeongsil로 실험/근거 봐줘" | `research-brief` | none yet |
| "집현전에서 토론해봐", "Jiphyeonjeon에서 선택지 비교해줘" | `decision-brief` | none yet |
| "승정원으로 실행 넘겨", "Seungjeongwon handoff" | `executor-handoff` | existing bundle |
| "실록에 남겨", "Sillok evidence" | evidence or promotion record | none |
| "단종 처리해", "Danjong archive" | `decision-brief` rejected or retired option | none yet |
| "조사해봐", "히스토리 긁어봐", "근거 확인해봐" | `research-brief` | none yet |
| "어떤 선택이 맞아?", "분화할까?", "할 만해?" | `decision-brief` | none yet |
| vague product or system goal | `uigwe-plan` | `full` |
| clarified intent, no approved design | `uigwe-plan` | `design-to-plan` |
| approved design or packet set | `uigwe-plan` | `decompose-only` |
| existing bundle, now execute | `executor-handoff` | existing bundle |
| exact implementation task | `direct-action` | none |
| "조사해서 계획하고 실행까지 해줘", "research, plan, implement, and verify" | chained lanes | resolved by evidence |

## Verification

Router quality should be checked with concrete examples, not vibes.

For this public install package, use a small scenario list when changing the router:

- evidence-only request -> `research-brief`
- option comparison -> `decision-brief`
- vague build goal -> `uigwe-plan`
- validated bundle execution -> `executor-handoff`
- exact implementation task -> `direct-action`

Run JSON and example-bundle checks when the router change touches schemas, packet examples, wrapper docs, executor docs, or Ralph handoff behavior.

## Improvement Loop

Use Uigwe itself to improve the router:

1. Write or update a Uigwe planning bundle for the router change.
2. State the evaluation method and pass criteria in `spec.md`.
3. Implement the smallest candidate change.
4. Run focused router examples plus JSON and bundle validation.
5. Treat failures as Actionable Side Information.
6. Mutate only the smallest surface that explains the failure.
7. Promote only when targets pass and the diff stays within the planned scope.

## Failure Handling

- If research evidence is stale or unavailable, stay in `research-brief`.
- If options are still underspecified, stay in `decision-brief`.
- If Uigwe planning reveals missing intent or design boundaries, re-enter the relevant Uigwe stage.
- If the user asked for direct implementation, do not force a Uigwe plan.
