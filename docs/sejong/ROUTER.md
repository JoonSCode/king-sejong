# Sejong Router

**Status:** Draft

## Purpose

Sejong is the all-in-one Codex front door that carries work through research, decision support, Uigwe planning, Seungjeongwon execution, verification, and evidence recording.

It exists because real user requests often say "research this", "think through this", "is this worth making", or "use Uigwe/의궤 for this" before the correct planning entry mode is known.

Sejong keeps Uigwe focused on its strongest job: converting clarified intent, evidence, and decisions into durable planning artifacts. Sejong owns the larger work loop around Uigwe: gather evidence, decide whether planning is useful, invoke Uigwe when needed, execute the selected work, verify the outcome, and record evidence.

This file is Sejong's routing contract. Sejong is not a new planning protocol and not a replacement for Uigwe. The internal surface ids are `jangyeongsil`, `jiphyeonjeon`, `uigwe`, `seungjeongwon`, and `sejong-direct`.

## Non-Goals

- It is not a replacement for the Uigwe protocol.
- It is not a replacement for Uigwe's planning protocol; it orchestrates execution through Codex direct action or native Seungjeongwon execution.
- It does not weaken Uigwe live-session approval gates.
- It does not create packets when the user only needs evidence or a lightweight decision.
- It does not turn `Danjong` into a separate execution lane.

## Sejong Surfaces

Use Sejong language in public docs and user-facing responses. The English ids below are only compact internal handles for tests and examples.

| Surface | Internal id | Use it for |
| --- | --- | --- |
| `Sejong` | chained or `sejong-direct` | All-in-one front door for research, planning, execution, verification, and evidence |
| `JangYeongsil` / `장영실` | `jangyeongsil` | Research, experiment, evidence gathering, and unknown discovery |
| `Jiphyeonjeon` / `집현전` | `jiphyeonjeon` | Debate, option comparison, recommendation, and decision support |
| `Uigwe` / `의궤` | `uigwe` | Formal planning with Uigwe modes and artifacts |
| `Seungjeongwon` / `승정원` | `seungjeongwon` | Native execution and verification after a scope or bundle is approved |
| `Sillok` / `실록` | evidence record | Scorecards, promotion notes, proof, and decision history |
| `Danjong` / `단종` | retired option | Retired, rejected, or deposed options |

Uigwe is the whole formal planning surface. It has entry modes such as `full`, `design-to-plan`, and `decompose-only`, but the Sejong surface name remains `uigwe`.

## Internal Structure

Sejong actively owns the end-to-end loop and then calls the selected surface:

| Role | Responsibility | Active call |
| --- | --- | --- |
| `Sejong` | All-in-one front door | choose the next surface, execute it, and continue when the user asked for an outcome |
| `JangYeongsil` | Research surface | gather evidence and produce a research note |
| `Jiphyeonjeon` | Decision surface | compare options and produce a decision note |
| `Uigwe` | Formal planning protocol | run `full`, `design-to-plan`, or `decompose-only` |
| `Seungjeongwon` | Native execution surface | execute and verify an approved scope or validated bundle |
| `Sillok` | Evidence records | update scorecards, promotion notes, or decision history |
| `Danjong` | Rejected or retired option semantics | record rejection or retirement inside a decision or evidence artifact |
| `Sejong direct` | Clear immediate work | perform the task under normal workspace rules |

## Active Invocation Protocol

Do not stop at naming the surface. After classifying a request, execute the selected surface when enough context is available:

1. `JangYeongsil`: inspect the available evidence, separate known/inferred/unknown facts, and name the next decision.
2. `Jiphyeonjeon`: compare options, reject weaker paths with reasons, recommend one path, and name the next surface.
3. `Uigwe`: call into the Uigwe skill or protocol surface and preserve its live-session approval gates.
4. `Seungjeongwon`: inspect the bundle, execute through Seungjeongwon, and require execution feedback before claiming completion.
5. `Sejong direct`: state briefly that formal planning is not needed, perform the clear task, and verify the result.
6. `Sillok` or `Danjong`: write evidence, archive, rejection, or promotion records rather than creating a new execution lane.

If the user asked for an outcome such as "research, plan, and do it", Sejong may chain surfaces:

```text
JangYeongsil research -> Jiphyeonjeon decision -> Uigwe planning -> Seungjeongwon execution -> verification -> Sillok evidence
```

Stop early only when missing evidence, a user decision, or an approval gate is genuinely required.

## Surfaces

### `JangYeongsil`

Use for evidence gathering and situation understanding.

Required output:

- `known`: sourced facts from files, commands, official docs, or reviewed evidence
- `inferred`: conclusions that follow from the known facts
- `unknown`: unresolved facts or missing evidence
- `decision_question`: the decision this research is meant to enable
- `next_surface`: usually `Jiphyeonjeon`, `Uigwe`, or `Sejong direct`

This surface is useful for the user's broad "만능/리서치" usage because it prevents early packet generation from hiding weak evidence.

### `Jiphyeonjeon`

Use when the task is about choosing a direction.

Required output:

- decision to make
- options
- rejected options and reasons
- recommended option
- confidence
- risks
- next surface

This surface should be used before Uigwe planning when the main uncertainty is strategic rather than structural.

### `Uigwe`

Use when the desired output is a canonical Uigwe bundle.

Mode resolution:

1. `decompose-only` if there is an approved design artifact.
2. `design-to-plan` if intent is clear enough but design still needs selection.
3. `full` if intent, scope, non-goals, constraints, or success criteria remain materially unclear.

The router must call into the Uigwe skill or protocol surface rather than duplicating its packet rules.

### `Seungjeongwon`

Use after planning succeeds and the user wants execution, verification, or a persistent completion loop.

The router should invoke Seungjeongwon by default.

### `Sejong Direct`

Use when a request is already clear enough to implement, answer, or verify directly in the current Codex session.

This protects Uigwe from becoming performative planning overhead while keeping execution inside Sejong's all-in-one surface.

## Routing Matrix

| User shape | Surface | Uigwe mode |
| --- | --- | --- |
| "세종으로 기획 잡아줘", "Sejong으로 라우팅해줘" | `Uigwe` when a bundle is needed, otherwise the best Sejong surface | resolved by evidence |
| "장영실처럼 조사해봐", "JangYeongsil로 실험/근거 봐줘" | `JangYeongsil` | none yet |
| "집현전에서 토론해봐", "Jiphyeonjeon에서 선택지 비교해줘" | `Jiphyeonjeon` | none yet |
| "승정원으로 실행 넘겨", "Seungjeongwon handoff" | `Seungjeongwon` | existing bundle |
| "실록에 남겨", "Sillok evidence" | evidence or promotion record | none |
| "단종 처리해", "Danjong archive" | `Jiphyeonjeon` rejected or retired option | none yet |
| "조사해봐", "히스토리 긁어봐", "근거 확인해봐" | `JangYeongsil` | none yet |
| "어떤 선택이 맞아?", "분화할까?", "할 만해?" | `Jiphyeonjeon` | none yet |
| vague product or system goal | `Uigwe` | `full` |
| clarified intent, no approved design | `Uigwe` | `design-to-plan` |
| approved design or packet set | `Uigwe` | `decompose-only` |
| existing bundle, now execute | `Seungjeongwon` | existing bundle |
| exact implementation task | `Sejong direct` | none |
| "조사해서 계획하고 실행까지 해줘", "research, plan, implement, and verify" | chained surfaces | resolved by evidence |

## Verification

Router quality should be checked with concrete examples, not vibes.

For this public install package, use a small scenario list when changing the router:

- evidence-only request -> `JangYeongsil`
- option comparison -> `Jiphyeonjeon`
- vague build goal -> `Uigwe`
- validated bundle execution -> `Seungjeongwon`
- exact implementation task -> `Sejong direct`

Run JSON and example-bundle checks when the router change touches schemas, packet examples, wrapper docs, executor docs, or execution handoff behavior.

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

- If research evidence is stale or unavailable, stay with `JangYeongsil`.
- If options are still underspecified, stay with `Jiphyeonjeon`.
- If Uigwe planning reveals missing intent or design boundaries, re-enter the relevant Uigwe stage.
- If the user asked for direct implementation, do not force a Uigwe plan.
