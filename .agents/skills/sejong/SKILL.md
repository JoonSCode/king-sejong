---
name: sejong
description: Use when a user invokes Sejong/$sejong or court aliases JangYeongsil/장영실, Jiphyeonjeon/집현전, Seungjeongwon/승정원, Sillok/실록, or Danjong/단종 for all-in-one research, decision support, formal planning, execution, verification, evidence records, rejected-option handling, or when continuing an active Sejong workflow that the user has not explicitly ended.
---

# Sejong

`sejong` is the lead router inside King Sejong, the full court-style orchestration system for broad research, decision support, planning triage, execution, verification, evidence recording, or direct action.

It is not a shim over another skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`.

When hooks or TeamExecutor are involved, active workflow context is represented by the checkpoint contract in `../../../docs/sejong/king-sejong-context.schema.json` and the hook guardrails in `../../../docs/sejong/HOOKS.md`. Live clarification state may be recorded as an ambiguity register described in `../../../docs/sejong/AMBIGUITY_REGISTER.md`.

When security-sensitive evidence, verification, or tool actions are involved, follow the Sillok trace contract in `../../../docs/sejong/SILLOK_TRACE.md` and the security guardrails in `../../../docs/sejong/SECURITY.md`.

When repo instruction context such as `AGENTS.md` should be initialized or refreshed, use the guarded candidate-diff workflow in `../../../docs/sejong/REPO_CONTEXT.md`; do not silently rewrite tracked instruction files.

## Routing

1. Load `../../../docs/sejong/ROUTER.md`.
2. Classify the request into the next useful Sejong surface.
3. Execute the selected surface when enough context is available; do not stop at only naming it.
4. If the user asked for an outcome rather than a single artifact, continue through downstream surfaces until the work is executed, verified, or blocked on a real missing decision.
5. Once invoked, keep follow-up turns inside the active Sejong workflow until the user explicitly exits Sejong or switches to another non-Sejong workflow; do not require the user to repeat `$sejong` on every turn.
6. For material changes to Sejong, Uigwe, Seungjeongwon, installer, validation, or artifact-storage behavior, use Jiphyeonjeon for unsettled decisions, Uigwe for handoff-contract planning, and Seungjeongwon for actionable decomposition, implementation, and verification; reserve Sejong direct for non-behavioral typo, link, or formatting fixes.
7. Treat Korean court names as active user-facing surfaces:
   - `JangYeongsil` -> research, experiment, and evidence gathering
   - `Jiphyeonjeon` -> discussion, debate, option comparison, and decision support
   - `Uigwe` -> formal planning with Uigwe modes and artifacts
   - `Seungjeongwon` -> execution and verification through the native Seungjeongwon executor
   - `Sillok` -> evidence and promotion records
   - `Danjong` -> retired or rejected option semantics, never an execution surface

Canonical internal surface ids are `jangyeongsil`, `jiphyeonjeon`, `uigwe`, `seungjeongwon`, and `sejong-direct`. Execution and verification are required behavior for `sejong-direct` and for any completed `seungjeongwon` path.

Treat JangYeongsil, Jiphyeonjeon, Uigwe, Seungjeongwon, Sillok, and Danjong as Sejong court modes, not peer agents. For non-trivial workflows, surface the current mode to the user in plain language such as `조사 중`, `판단 중`, `계획 정리 중`, `실행 중`, `기록 중`, or `제외/보류 중`, and state what the user can do next.

Boundary rule: use `JangYeongsil` when facts or evidence are unclear, `Jiphyeonjeon` when enough material exists but options need discussion, and `Uigwe` when the chosen direction should become a durable planning bundle. Preserve Uigwe live-session gates when routing there.

Research-to-Uigwe rule: when research is explicitly for deciding a strategy, choosing what to try, preparing a later plan, or feeding Uigwe, do not end with a research conclusion. Treat JangYeongsil and optional Jiphyeonjeon as pre-Uigwe evidence, keep `uigwe_promotion_required` pending in active context when available, output the Uigwe input summary, and route to `Uigwe` unless the user explicitly says the task is research-only.

Advice-only rule: Jiphyeonjeon may stop at a recommendation when the user only asked for judgment or comparison. If the user approves the recommendation, asks to make it concrete, or asks to execute it, route to `Uigwe` with the recommendation as input.

Outcome-completion rule: when the user asks Sejong to create, change, fix, implement, validate, clean up, prepare a usable artifact, or otherwise reach a stated goal, research and advice are helper surfaces; enter `Uigwe` before `Seungjeongwon` unless the user explicitly narrows the request to research-only or advice-only. Keep `Sejong direct` limited to small exact commands, simple answers, obvious non-behavioral typo or link fixes, deterministic regeneration under an approved contract, and mechanical corrections.

When a live Sejong or Uigwe clarification uses an ambiguity register, do not advance the stage or claim completion while any ambiguity remains `open`. Show the user the stage readiness percentage, unclear items, recommended options, and a free-response path until readiness reaches `100%` or the user explicitly waives the remaining ambiguity.

`JangYeongsil` and `Jiphyeonjeon` can be primary routes or helper calls inside another active court mode. Use JangYeongsil from Sejong, Uigwe, or Jiphyeonjeon when facts, examples, repo history, experiments, or external evidence are needed; return `known` / `inferred` / `unknown` evidence to the calling mode. Use Jiphyeonjeon from Sejong, Uigwe, JangYeongsil, or Seungjeongwon whenever multiple perspectives would materially improve accuracy; return a decision note, rejected options, risks, and the next surface. Helper calls do not approve Uigwe gates, finalize packets, claim consensus, or override lead synthesis.

`Jiphyeonjeon` is an optional deliberation pass, not a required step in every Sejong chain. Use bounded workers only when independent research, option-review, implementation, or verification lanes would materially improve speed or confidence; the lead Sejong agent owns synthesis, final routing, and final verification.

For parallel Jiphyeonjeon, use bounded briefs from advocate, critic, specialist, operator, or risk-review lenses over the same evidence bundle; do not use worker or subagent agreement as evidence or approval. Substantial Jiphyeonjeon work may use host-native team messaging when the runtime officially supports it, otherwise `$team` mailbox-mediated challenge rounds. The lead Sejong agent opens and closes rounds and owns synthesis. Research, discussion, and planning may overlap only as bounded preflight work: JangYeongsil evidence lanes may run while Uigwe prepares readiness checks, and Jiphyeonjeon option review may run while Uigwe inventories artifacts, but Uigwe gates and final packets remain lead/user-owned.

Codex native subagents, host-native team/teammate support, and `$team` tmux workers are different backends. Prefer official host-native team messaging when the current runtime exposes it and the task needs peer challenge. Use Codex native subagents for parent-mediated side tasks. For `$team`, use Sejong state under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/` instead of repo-local or tool-specific orchestration state. Before starting workers, write a role assignment with current court mode, route context, source-of-truth refs, worker role, assigned scope, allowed outputs, verification expectation, stop condition, and forbidden claims. When using Codex native subagents, `.codex/prompts/{role}.md` is an optional repo-local overlay. If it is absent, use the Codex native role prompt and continue; do not treat missing overlays as a Sejong install failure.
