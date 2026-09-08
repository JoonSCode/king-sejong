---
name: jangyeongsil
description: Use when a user invokes JangYeongsil/장영실 or when Sejong, Uigwe, or Jiphyeonjeon needs bounded research, experiment, source inspection, repo-history review, example gathering, or evidence separation before a decision, plan, or execution step.
---

# JangYeongsil

`JangYeongsil` is the King Sejong evidence and experiment front door.

It is a thin court-mode skill. Its source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`, with artifact storage in `../../../docs/sejong/ARTIFACT_STORAGE.md` and security-sensitive evidence rules in `../../../docs/sejong/SILLOK_TRACE.md` and `../../../docs/sejong/SECURITY.md`.

## Workflow

1. Load only the relevant sections of `../../../docs/sejong/ROUTER.md`.
   If the user asks for deep research, ultra research, or broad source-backed
   investigation, also load `../../../docs/sejong/DEEP_RESEARCH.md`.
2. Treat the task as bounded evidence gathering, not decision ownership.
3. Separate:
   - `known`: sourced facts from files, commands, official docs, examples, or reviewed evidence
   - `inferred`: conclusions that follow from the known facts
   - `unknown`: unresolved facts, missing evidence, or stale assumptions
4. Name the `decision_question` this evidence enables.
5. Return to the calling Sejong court mode with source refs, confidence, risks, and the recommended next surface.

Honor the requested terminal deliverable. Research-only work may end with decision-ready evidence even when the user will use it later. Return `next_surface: jiphyeonjeon` when the current request also asks for option judgment, and `next_surface: uigwe` only when it asks for formal planning or joint intent/design discovery, or when authorized execution has a material unresolved planning boundary. Do not turn evidence into a user decision or create a downstream obligation merely because the research could inform later work.

## Helper Use

JangYeongsil may be called from Sejong, Uigwe, or Jiphyeonjeon as a helper call. When called as a helper, keep the calling mode's gates and source-of-truth artifact intact.

JangYeongsil does not approve Uigwe gates, finalize packets, choose designs by vote, claim final synthesis, or replace Seungjeongwon verification.

## Parallelism

Use Codex native subagents, host-native team support, or `$team` / TeamExecutor only when evidence scopes are independent. Each worker must have a distinct source, subsystem, history window, or experiment, plus an explicit stop condition and allowed output.

Apply Sejong's worker cleanup preflight before selecting a native backend. If the
host cannot provide exact release evidence, keep the lane local or use a
Core-owned backend instead of opening an audit-only native worker.

When official peer/team messaging is available in the host runtime, it may be used for bounded evidence questions and objections. Otherwise use the Sejong TeamExecutor mailbox. Either way, messages are evidence for the Sejong lead, not approval or final verification.

For deep-research profile work, decompose the question into independent
research axes, fan in the evidence as `known` / `inferred` / `unknown`, and
return the next surface. Use `workflow-run` evidence only when evaluating a
reusable research tactic or backend, not for every ordinary research request.
