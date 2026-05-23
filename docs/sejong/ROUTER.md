# Sejong Router

**Status:** Draft

## Purpose

Sejong is the all-in-one Codex front door that carries work through research, decision support, Uigwe planning, Seungjeongwon execution, verification, and evidence recording.

King Sejong is the full court-style orchestration system. `Sejong` is the lead router and synthesizer inside that system, not the whole system by itself. The other court names are bounded surfaces, roles, or evidence semantics that the Sejong lead routes through.

It exists because real user requests often say "research this", "think through this", "is this worth making", or "use Uigwe/의궤 for this" before the correct planning entry mode is known.

Sejong keeps Uigwe focused on its strongest job: converting clarified intent, evidence, and decisions into durable planning artifacts. Sejong owns the larger work loop around Uigwe: gather evidence, decide whether planning is useful, invoke Uigwe when needed, execute the selected work, verify the outcome, and record evidence.

This file is Sejong's routing contract. Sejong is not a new planning protocol and not a replacement for Uigwe. The internal surface ids are `jangyeongsil`, `jiphyeonjeon`, `uigwe`, `seungjeongwon`, and `sejong-direct`.

## Non-Goals

- It is not a replacement for the Uigwe protocol.
- It is not a replacement for Uigwe's planning protocol; it orchestrates execution through Codex direct action or native Seungjeongwon execution.
- It does not weaken Uigwe live-session approval gates.
- It does not create packets when the user only needs evidence or a lightweight decision.
- It does not turn `Danjong` into a separate execution lane.
- It does not create git-tracked repository artifacts unless the user explicitly asks to promote a shareable record or planning bundle.
- It does not silently rewrite repository instruction files such as `AGENTS.md`.

## Sejong Surfaces

Use Sejong language in public docs and user-facing responses. The English ids below are only compact internal handles for tests and examples.

Use `King Sejong` when referring to the total orchestration system: Sejong lead routing plus JangYeongsil research, Jiphyeonjeon decision support, Uigwe planning, Seungjeongwon execution, Sillok evidence, Danjong rejection semantics, hooks, and bounded worker backends.

| Surface | Internal id | Use it for |
| --- | --- | --- |
| `Sejong` | chained or `sejong-direct` | All-in-one front door for research, planning, execution, verification, and evidence |
| `JangYeongsil` / `장영실` | `jangyeongsil` | Research, experiment, evidence gathering, and unknown discovery |
| `Jiphyeonjeon` / `집현전` | `jiphyeonjeon` | Discussion, debate, option comparison, recommendation, and decision support |
| `Uigwe` / `의궤` | `uigwe` | Formal planning with Uigwe modes and artifacts |
| `Seungjeongwon` / `승정원` | `seungjeongwon` | Native execution and verification after a scope or bundle is approved |
| `Sillok` / `실록` | evidence record | Scorecards, promotion notes, proof, and decision history |
| `Danjong` / `단종` | retired option | Retired, rejected, or deposed options |

Uigwe is the whole formal planning surface. It has entry modes such as `full`, `design-to-plan`, and `decompose-only`, but the Sejong surface name remains `uigwe`.

## Boundary Rules

The three pre-execution surfaces are intentionally different:

- `JangYeongsil`: use when facts, history, evidence, external constraints, or experiments are still unclear. Its job is to discover and separate known, inferred, and unknown material.
- `Jiphyeonjeon`: use when enough material exists to hold a discussion, but the direction is not settled. Its job is to weigh options, surface trade-offs, argue for and against paths, reject weaker alternatives, and recommend what to do next.
- `Uigwe`: use when the direction is ready to become a durable planning bundle. Its job is not open-ended discussion; it turns clarified intent or a selected design into formal artifacts and executable leaves.

In short: `JangYeongsil` gathers the evidence, `Jiphyeonjeon` discusses and decides, and `Uigwe` writes the formal plan.

`Jiphyeonjeon` is not mandatory in every Sejong chain. Use it as a short deliberation pass only when the gathered evidence leaves a meaningful choice.

## Active Sejong Session

Invoking `Sejong`, `$sejong`, or any court surface starts an active Sejong workflow for the current conversation.

While that workflow is active, treat follow-up user turns as Sejong turns even when they do not repeat the invocation token. Carry forward the current evidence, decisions, pending gates, selected surface, rejected options, and verification state. Do not drop back to ordinary one-shot assistant behavior merely because the next turn says "continue", "do that", "what about this", or gives another instruction without naming Sejong.

The user should not need to retype `$sejong` for each clarification, approval, correction, implementation step, or verification request inside the same workflow.

End or hand off the active Sejong workflow only when one of these is true:

- the user explicitly says to stop, leave Sejong, use normal Codex, or stop using the skill
- the user explicitly invokes another non-Sejong skill or workflow and the request is not a Sejong sub-surface
- the current conversation/workflow ends in the host environment

If a follow-up seems unrelated but the user has not exited Sejong, still route it through Sejong. For an exact task, that route can be `Sejong direct`; for ambiguous scope, ask the smallest clarifying question needed to decide whether it belongs to the active Sejong workflow.

This continuity is conversational state, not permanent memory. It does not require creating repository artifacts unless the user asks to promote a shareable record or planning bundle.

For substantial or hook-mediated workflows, this conversational state may also be mirrored into an external active context checkpoint that follows [king-sejong-context.schema.json](king-sejong-context.schema.json). The checkpoint stores route id, current surface, route sequence, pending gates, protected paths, evidence refs, artifact refs, team refs, subagent refs, and exit conditions under the Sejong artifact root. It is runtime state and is not tracked by the target repository by default.

## Sejong Self-Modification

Changes to Sejong itself need a higher routing bar than ordinary repository edits.

Material self-modification includes changes to:

- `.agents/skills/sejong/`, `.agents/skills/uigwe/`, or `.agents/skills/seungjeongwon/`
- `docs/sejong/ROUTER.md`, `PROTOCOL.md`, `WRAPPER.md`, `SEUNGJEONGWON_EXECUTOR.md`, `ARTIFACT_STORAGE.md`, or other durable behavior contracts
- `scripts/install-sejong.sh`
- schemas, validation tasks, benchmark scripts, or scorecards that define Sejong/Uigwe behavior
- public docs when the wording changes behavioral expectations rather than only presentation

For material self-modification, route through:

```text
Jiphyeonjeon decision -> Uigwe planning/decomposition -> Seungjeongwon execution and verification
```

Use `Jiphyeonjeon` when the policy, behavior, naming, or boundary decision is not already settled. Use `Uigwe` to turn the selected direction into executable leaves with done criteria and verification. Use `Seungjeongwon` to make the edits and prove the guardrails pass.

`Sejong direct` remains allowed for narrow non-behavioral maintenance, such as typo fixes, broken links, formatting-only edits, deterministic scorecard regeneration, or mechanical corrections that do not change routing, planning, execution, installer, validation, or artifact-storage behavior.

Hook-backed environments should treat the material self-modification list as `protected_paths` in the active context checkpoint. A supported `PreToolUse` or `PermissionRequest` hook may deny protected edits until the route sequence contains `jiphyeonjeon`, `uigwe`, and `seungjeongwon` in order.

## Parallel Workers

Sejong may use bounded workers to increase parallelism, but workers are an optional execution tactic rather than a separate Sejong surface. The safe shape is hub-and-spoke: workers return bounded briefs, mailbox messages, implementation slices, or verification evidence, and the lead Sejong agent owns routing, synthesis, final decision, and final verification.

Supported worker backends include:

- Codex native subagents for host-managed bounded delegation
- `$team` / `TeamExecutor` wrappers that launch separate Codex CLI, Claude CLI, or compatible workers in `tmux` panes and coordinate through Sejong-owned state files

`$team` state belongs under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/`. It must not depend on `.omx` paths or OMX state. See [TEAM_EXECUTOR.md](TEAM_EXECUTOR.md) for the mailbox, tmux worker, and lease contract.

Codex native subagents remain a valid backend, but `$team` is the preferred shape when the intended workers are independent CLI processes rather than host-managed `spawn_agent` calls.

Both worker backends must carry the active King Sejong context when available. Workers may return evidence, implementation slices, verification observations, objections, or mailbox messages. They must not approve Uigwe gates, claim final synthesis, make majority-vote decisions, or override the Sejong lead.

Codex native role prompt resolution:

1. Use the host Codex native role prompt as the default source for `agent_type` behavior.
2. If `.codex/prompts/{role}.md` exists in the target repo, read it as a repo-local overlay before spawning that role.
3. If the overlay file is absent, proceed with the Codex native role prompt; absence is not a blocker or install failure.
4. Do not copy `.codex/prompts` as part of the default King Sejong install. A target repo should add prompt overlays only when it has stable, repo-specific role rules worth preserving.

See [PROMPT_OVERLAYS.md](PROMPT_OVERLAYS.md) for optional overlay guidance.

Use bounded workers when independent work can run in parallel without blocking the next local step:

- `JangYeongsil`: split evidence gathering across independent sources, docs, repo history, or external references.
- `Jiphyeonjeon`: compare serious options through separate advocate, critic, or specialist perspectives before the lead agent synthesizes a recommendation.
- `Uigwe`: keep live-session approval gates with the lead agent; use workers only for bounded side research, preflight, readiness, or artifact checks that do not decide the gate.
- `Seungjeongwon`: split implementation or verification across disjoint file scopes, test surfaces, or review lanes.
- `Sillok`: have a verifier collect evidence while execution continues, then let the lead agent decide what belongs in the final record.

Do not use workers for trivial direct edits, single-source lookups, or duplicated readings of the same context. Worker agreement is not evidence, approval, or verification. The lead Sejong agent owns routing, synthesis, final decision, and final verification.

## Artifact Storage

Sejong follows the storage contract in [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md).

Security-sensitive evidence, verification, and tool decisions should be recorded
through the Sillok trace contract in [SILLOK_TRACE.md](SILLOK_TRACE.md) and the
guardrails in [SECURITY.md](SECURITY.md).

By default, JangYeongsil research notes, Jiphyeonjeon council briefs, temporary Uigwe artifacts, Seungjeongwon evidence snapshots, and Sillok records are external nontracked artifacts under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`.

Do not ask for an artifact tracking policy during normal install or normal routing. Create git-tracked repository artifacts only when the user explicitly asks to promote a shareable plan, Uigwe bundle, or Sillok record into the repository.

When artifacts are generated, report the external run directory and whether any tracked repository files were created.

Hook and worker evidence should reference active context artifacts instead of copying runtime state into the repository. For hook behavior, see [HOOKS.md](HOOKS.md).

## Repo Context Init And Refresh

Sejong can initialize or refresh repo-local instruction context such as
`AGENTS.md` through the contract in [REPO_CONTEXT.md](REPO_CONTEXT.md).

This is a guarded repo-context promotion workflow:

- `init` inspects a target repository and drafts an initial `AGENTS.md`
  candidate when one is missing or explicitly requested.
- `refresh` collects durable lessons from the current session, recent diffs,
  docs, and validation evidence, then deduplicates them against existing repo
  guidance.
- Both modes produce a candidate diff before changing tracked files.
- Tracked instruction files are applied only after explicit user approval or an
  explicit apply instruction.
- The source repository's `AGENTS.md` is maintainer guidance for this repository
  and must not be copied into target repositories.

Use `JangYeongsil` when the repo facts are unclear, `Jiphyeonjeon` when candidate
lessons need judgment, and `Seungjeongwon` when an approved candidate diff should
be applied and verified. Use Uigwe only when the repo-context policy or Sejong
behavior itself is changing materially.

### Parallel Patterns

`JangYeongsil` supports research fan-out and fan-in:

- Split by independent source, subsystem, history window, benchmark, or external reference.
- Give each lane a non-overlapping evidence scope and require `known`, `inferred`, `unknown`, confidence, source list, and the decision it enables.
- Merge only after the lead reconciles conflicts and names unresolved unknowns.
- Do not let research lanes vote on strategy, create Uigwe packets, or duplicate the same source read.

`Jiphyeonjeon` supports a parallel chamber:

- Start with a shared council brief: `decision_question`, `shared_evidence_bundle`, `fixed_options`, criteria, constraints, non-goals, allowed output, forbidden decisions, stop condition, and verification requirement.
- Start bounded perspectives such as option advocate, counter-advocate, critic, domain specialist, operator, or risk reviewer.
- Prefer independent first-round briefs, then a lead-mediated challenge round when the strongest objections need response.
- For substantial Jiphyeonjeon work, a mailbox-mediated `$team` challenge round is allowed: workers may append bounded `claim`, `objection`, `question`, `response`, `evidence_ref`, or `risk` messages to the run mailbox, and may reference earlier message ids when answering each other.
- Treat subagent agreement as signal, not evidence or approval. The lead synthesizes the final recommendation, rejected options, risks, confidence, and next surface.
- Do not run open-ended worker-to-worker chat, majority voting, or debate-as-verification. The lead Sejong agent opens and closes each challenge round, resolves conflicts, and owns the final decision note.

Mailbox-mediated Jiphyeonjeon is useful when cross-examination will improve the decision faster than serial lead questioning. It should still stay bounded:

- use one shared council brief and fixed option set unless the lead explicitly reopens the question
- require every message to name its role, scope, message kind, and target message id when replying
- cap challenge rounds; default to one challenge round after independent briefs
- store the mailbox as external run evidence, not as a tracked repository artifact unless explicitly promoted
- never allow a worker message to approve Uigwe gates, finalize packets, claim consensus, or override lead synthesis

`Uigwe` supports only preflight parallelism before gates:

- Allowed: artifact inventory, readiness check, schema or bundle validation, missing-context scan, and risk review.
- Forbidden before lead/user approval: competing canonical packets, finalized `spec.md`, finalized `rationale.md`, finalized `goal-tree.json`, or any gate decision.
- If Jiphyeonjeon is still unsettled, Uigwe preflight may prepare questions and mode-readiness notes but must not harden the plan.

Research, discussion, and planning may overlap only in this limited pipeline:

1. While `JangYeongsil` gathers evidence, the lead may draft decision axes and candidate options.
2. `Jiphyeonjeon` may begin once there is enough stable material for real comparison, but its final recommendation waits for blocking research lanes.
3. `Uigwe` may run preflight checks once a likely direction exists, but formal planning waits for the lead-owned recommendation and any live-session approval gate.
4. Execution waits for a clear direct task, approved scope, or validated bundle.

## Internal Structure

Sejong actively owns the end-to-end loop and then calls the selected surface:

| Role | Responsibility | Active call |
| --- | --- | --- |
| `Sejong` | All-in-one front door | choose the next surface, execute it, and continue when the user asked for an outcome |
| `JangYeongsil` | Research surface | gather evidence and produce a research note |
| `Jiphyeonjeon` | Discussion and decision surface | compare options, argue trade-offs, and produce a decision note |
| `Uigwe` | Formal planning protocol | run `full`, `design-to-plan`, or `decompose-only` |
| `Seungjeongwon` | Native execution surface | execute and verify an approved scope or validated bundle |
| `Sillok` | Evidence records | update scorecards, promotion notes, or decision history |
| `Danjong` | Rejected or retired option semantics | record rejection or retirement inside a decision or evidence artifact |
| `Sejong direct` | Clear immediate work | perform the task under normal workspace rules |

## Active Invocation Protocol

Do not stop at naming the surface. After classifying a request, execute the selected surface when enough context is available:

1. `JangYeongsil`: inspect the available evidence, separate known/inferred/unknown facts, and name the next decision.
2. `Jiphyeonjeon`: hold a structured discussion over the available options, argue for and against each serious path, reject weaker paths with reasons, recommend one path, and name the next surface.
3. `Uigwe`: call into the Uigwe skill or protocol surface and preserve its live-session approval gates.
4. `Seungjeongwon`: inspect the bundle, execute through Seungjeongwon, and require execution feedback before claiming completion.
5. `Sejong direct`: state briefly that formal planning is not needed, perform the clear task, and verify the result.
6. `Sillok` or `Danjong`: write evidence, archive, rejection, or promotion records rather than creating a new execution lane.

If the user asked for an outcome such as "research, plan, and do it", Sejong may chain surfaces:

```text
JangYeongsil research -> Jiphyeonjeon discussion -> Uigwe planning -> Seungjeongwon execution -> verification -> Sillok evidence
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

Use when the task is about discussing options and choosing a direction.

Common use cases:

- "Should we do A or B?"
- "Is this worth making?"
- "Should this be a separate skill, part of Sejong, or retired?"
- "Which architecture, naming, product, or workflow direction is stronger?"
- "Given this research, should we plan, execute, or stop?"
- "Which option should become Danjong?"

Required output:

- decision to make
- options
- arguments for and against serious options
- rejected options and reasons
- recommended option
- confidence
- risks
- next surface

This surface should be used before Uigwe planning when the main uncertainty is strategic rather than structural.
If the missing part is evidence, route back to `JangYeongsil`; if the choice is settled and the next job is artifact generation, route to `Uigwe`.
Skip this surface when research already settles the direction or when the user gave an exact implementation task.

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
| "집현전에서 논의해봐", "집현전에서 토론해봐", "Jiphyeonjeon에서 선택지 비교해줘" | `Jiphyeonjeon` | none yet |
| "승정원으로 실행 넘겨", "Seungjeongwon handoff" | `Seungjeongwon` | existing bundle |
| "AGENTS.md 초기화", "refresh repo instructions", "Codex init 같은 것" | repo-context init/refresh through `JangYeongsil` or `Jiphyeonjeon`, then `Seungjeongwon` only after approval | none unless Sejong behavior changes |
| "실록에 남겨", "Sillok evidence" | evidence or promotion record | none |
| "단종 처리해", "Danjong archive" | `Jiphyeonjeon` rejected or retired option | none yet |
| "조사해봐", "히스토리 긁어봐", "근거 확인해봐" | `JangYeongsil` | none yet |
| "어떤 선택이 맞아?", "분화할까?", "할 만해?", "논의해보자" | `Jiphyeonjeon` | none yet |
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
