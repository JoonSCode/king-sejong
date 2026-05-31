# Sejong + Uigwe

Sejong is the all-in-one user-facing front door for broad agent work.
It can research, decide, plan, execute, verify, and record evidence instead of forcing every request through formal planning.

Use `sejong` when the request is broad and the agent should choose whether to research, decide, plan, execute, verify, or record evidence.

Uigwe is the formal planning protocol inside Sejong. Use it when the output should be a durable planning bundle with packets, rationale, and Seungjeongwon handoff leaves.
In live chat usage, Uigwe is supposed to do that interactively.
Progress should be presented as approximate readiness such as `기획 준비도 68%`, paired with the main weak areas.
During decomposition, Uigwe repeatedly selects candidate objectives, reviews them against the parent objective, reselects weak or invalid candidates, and recurses until each selected branch is ready as a Seungjeongwon handoff leaf. Seungjeongwon then owns todo listup, todo verification, subtodo decomposition to actionable leaves, execution, verification, evidence, and retry loops.

## Installed Layout

The installer can copy this contract surface into either a target repository or a Codex user skill directory.

Repo scope:

- `.agents/skills/sejong/`
- `.agents/skills/jangyeongsil/`
- `.agents/skills/jiphyeonjeon/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `docs/sejong/`

User scope under `${CODEX_HOME:-~/.codex}/skills`:

- `sejong/`
- `jangyeongsil/`
- `jiphyeonjeon/`
- `uigwe/`
- `seungjeongwon/`

In user scope, this docs tree is installed under `skills/sejong/docs/`, and the installed skill files are rewritten to load contracts from that user-scope docs copy.

User-scope install also copies the Codex plugin adapter to `${CODEX_HOME:-~/.codex}/plugins/cache/king-sejong-local/king-sejong/local/`, manages the King Sejong hook and plugin blocks in `${CODEX_HOME:-~/.codex}/config.toml`, sets `[features].hooks = true`, and creates `${CODEX_HOME:-~/.codex}/sejong/state/active-context.json` if it does not already exist. The managed blocks are marked and idempotent, so rerunning the installer replaces only King Sejong's sections.

The plugin adapter is a discovery and hook-metadata surface. It does not replace the installer-owned skills, docs, active context, or verification contracts.

User-scope install writes a compact generic Codex guidance block to `${CODEX_HOME:-~/.codex}/AGENTS.md` by default so King Sejong stays available as an always-on research, analysis, debate, planning, execution, and verification discipline across workspaces. Use `--codex-guidance none` to opt out, or `--print-codex-guidance` to inspect the block without installing. This does not copy this source repository's `AGENTS.md`. The guidance is generic Codex wording and includes the rule: do not use `.omx` paths as Sejong state.

The installer also owns explicit update maintenance. `--check-updates` fetches the configured upstream and reports whether the King Sejong source checkout is up to date, behind, ahead, dirty, or diverged. `--auto-update` refuses dirty or diverged source checkouts, uses `git pull --ff-only` when updates are available, then refreshes the selected managed install with force semantics and normal verification. Hooks must not silently self-update King Sejong during ordinary session start.

The skill files stay short by design. They load the detailed contracts from the installed Sejong docs only when needed.

## Start Here

For normal use:

1. Read [RUNTIME_CONTRACT.md](RUNTIME_CONTRACT.md) for the Codex-native runtime contract.
2. Read [ROLE_SEPARATION.md](ROLE_SEPARATION.md) for court-mode boundaries.
3. Read [DISCIPLINE_GATES.md](DISCIPLINE_GATES.md) for why-based force levels and quality gates.
4. Read [ROUTER.md](ROUTER.md) to understand Sejong's lanes.
5. Read [PROTOCOL.md](PROTOCOL.md) to understand Uigwe's planning model.
6. Read [WRAPPER.md](WRAPPER.md) if you want machine-consumable packet flow.
7. Read [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md) to understand where research, planning, runtime, and evidence artifacts are stored.
8. Read [PROMPT_OVERLAYS.md](PROMPT_OVERLAYS.md) if you want repo-local role prompt overlays.
9. Read [HOOKS.md](HOOKS.md) if you want deterministic Codex lifecycle guardrails.
10. Read [SECURITY.md](SECURITY.md) and [SILLOK_TRACE.md](SILLOK_TRACE.md) if a workflow mixes private data, untrusted content, external actions, or durable evidence records.
11. Read [REPO_CONTEXT.md](REPO_CONTEXT.md) if you want guarded `AGENTS.md` init or refresh behavior.
12. Read [SEUNGJEONGWON_EXECUTOR.md](SEUNGJEONGWON_EXECUTOR.md) if you want to execute and verify a validated plan.
13. Read [TEAM_EXECUTOR.md](TEAM_EXECUTOR.md) if you want `$team` tmux workers coordinated by Sejong mailbox and state files.
14. Read [AMBIGUITY_REGISTER.md](AMBIGUITY_REGISTER.md) when live clarification needs a durable readiness and open-ambiguity record.
15. Read [OUTCOME_EVALUATION.md](OUTCOME_EVALUATION.md) when behavior changes must prove better resulting artifacts, not only correct routing.
16. Read [WORKFLOW_RUN.md](WORKFLOW_RUN.md) when evaluating dynamic workflow, deep-research, ultracode-style, or many-agent backend ideas without giving them Sejong authority.
17. Read [VALIDATION.md](VALIDATION.md) if you are changing Uigwe or Sejong behavior and need benchmark gates.

## Practical Usage

Use Sejong when the correct workflow is still uncertain:

```text
$sejong investigate the history and tell me the next decision
$sejong compare these options and recommend a path
$sejong this approved design should become a Seungjeongwon handoff contract
$sejong research the problem, plan the fix, implement it, and verify it
```

Use JangYeongsil or Jiphyeonjeon directly when you already know the needed court mode:

```text
$jangyeongsil inspect the repo history and separate known/inferred/unknown evidence
$jiphyeonjeon compare these options with advocate, critic, and risk-review lenses
```

After Sejong is invoked, follow-up turns remain inside the active Sejong workflow until the user explicitly exits Sejong or switches to another non-Sejong workflow. The user should not have to repeat `$sejong` for every clarification, approval, correction, implementation step, or verification request.

When the user asks Sejong to achieve a goal, research and advice are helper surfaces rather than terminal outputs. Research-only and advice-only requests may stop at evidence or a recommendation, but approving that recommendation, asking to make it concrete, or asking to execute it routes the work into Uigwe before Seungjeongwon execution. After Uigwe reaches a handoff-ready outcome contract, execution and verification go through Seungjeongwon, not Sejong direct. `Sejong direct` is reserved for small exact commands, simple answers, obvious non-behavioral fixes, and mechanical corrections.

For substantial workflows, this active state can be mirrored into an external King Sejong context checkpoint. The checkpoint is validated by [king-sejong-context.schema.json](king-sejong-context.schema.json) and can be used by hooks, subagents, TeamExecutor, and Seungjeongwon evidence records.

When live clarification must be preserved across a long run, reference an ambiguity register from the active context `artifact_refs`. The register records the current stage, readiness percentage, unclear items, recommended options, free-response path, user responses, and next required user action. If any item remains `open`, Sejong must not advance or claim completion unless the user explicitly waives it.

When long-run execution must survive compaction or unattended continuation, reference a Seungjeongwon run artifact from active context `artifact_refs`. The run follows [seungjeongwon-run.schema.json](seungjeongwon-run.schema.json) and records active todos, attempts, verification evidence, blockers, and Uigwe re-entry requests. `Stop` should not conclude while that run is active or invalid.

Use Sejong repo-context init/refresh when a target repository needs an initial `AGENTS.md` or an existing instruction file should absorb durable lessons from recent work. That workflow is candidate-diff first: inspect the repo, deduplicate lessons, reject transient or unsafe material, and apply tracked instruction edits only after explicit user approval or an explicit apply instruction. See [REPO_CONTEXT.md](REPO_CONTEXT.md).

Court modes can also be helper calls inside another active mode. JangYeongsil can gather missing evidence for Sejong, Uigwe, or Jiphyeonjeon, then return `known` / `inferred` / `unknown` evidence to the calling mode. Jiphyeonjeon can provide decision support from Sejong, Uigwe, JangYeongsil, or Seungjeongwon whenever multiple perspectives would improve accuracy, then return a decision note and next-surface recommendation. These helper calls do not approve Uigwe gates, finalize packets, or replace lead synthesis.

For larger Sejong work, parallelism is allowed when it is genuinely separable:

- `JangYeongsil` can fan out across independent evidence sources and fan in to one `known` / `inferred` / `unknown` synthesis.
- `Jiphyeonjeon` can run bounded council briefs in parallel, such as advocate, critic, specialist, operator, and risk reviewer. Substantial decisions may use `$team` tmux workers with Sejong mailbox/state files for a bounded challenge round. The mailbox uses versioned `send-message` / `receive-messages` envelopes. The workers do not vote; the lead Sejong agent opens and closes rounds and synthesizes the recommendation.
- `Uigwe` can overlap only through preflight checks such as artifact inventory, readiness review, or validation planning. JangYeongsil evidence lanes or Jiphyeonjeon option review may run beside that preflight, but formal packets and live-session gates remain lead/user-owned.
- Execution parallelism belongs in `Seungjeongwon` after scope approval, with disjoint file scopes or test surfaces.

If the current host runtime officially supports team or teammate messaging, Sejong can use that native backend for bounded peer challenge. Otherwise, use `$team` / TeamExecutor mailbox messages. In both cases peer messages are evidence for the Sejong lead, not gate approval, final synthesis, or final verification.

Sejong does not require `.codex/prompts/{role}.md`. If a target repo has such a file, treat it as a repo-local overlay on top of the Codex native role prompt. If it is absent, continue with the native role prompt. See [PROMPT_OVERLAYS.md](PROMPT_OVERLAYS.md).

When changing Sejong itself, use the full Sejong chain unless the edit is purely non-behavioral. Material changes to routing, Uigwe planning, Seungjeongwon execution, installer behavior, validation, or artifact storage should go through Jiphyeonjeon decision support, Uigwe handoff-contract planning, then Seungjeongwon actionable decomposition, execution, and verification. In short, material behavior changes should follow the full Sejong chain.

Use Uigwe directly when you already want formal planning:

```text
$uigwe full <brief>
$uigwe design-to-plan <clear intent or feature brief>
$uigwe decompose-only <approved design artifact>
```

Use Seungjeongwon directly when the scope is approved and execution should start:

```text
$seungjeongwon execute this validated Uigwe bundle and verify the result
$seungjeongwon finish these handoff leaves from docs/sejong/examples/brownfield-decompose-only
```

## What Uigwe Produces

Depending on mode, Uigwe produces:

- `Intent Packet`
- `Design Packet`
- `Plan Packet`
- `spec.md`
- `rationale.md`
- `goal-tree.json`

These artifacts are meant for both human review and downstream machine consumption.

By default, Sejong stores runtime, research, discussion, ambiguity registers, evidence, and temporary planning artifacts outside the target repository under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`. `$team` worker state belongs under that root at `state/team/<run-id>/`. Sejong does not create git-tracked repository files unless the user explicitly asks to promote a shareable artifact into the repo. See [ARTIFACT_STORAGE.md](ARTIFACT_STORAGE.md).

## Validation Helpers

This public package includes schema checks, bundle validation, frozen benchmark scaffolds, and an instruction-surface guardrail runner. It intentionally does not ship private benchmark runs or score histories.

Useful commands:

```bash
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow
python3 docs/sejong/scripts/sejong_workflow_run.py check --path docs/sejong/examples/workflow-run.example.json
python3 docs/sejong/scripts/benchmark_workflow_run.py
python3 docs/sejong/scripts/benchmark_workflow_run_comparison.py --min-score-delta 0.10 --min-multi-metric-score 0.90
python3 docs/sejong/scripts/benchmark_workflow_run_stability.py --samples 9 --warmups 1
python3 docs/sejong/scripts/audit_workflow_run_risks.py --repo-root . --artifact docs/sejong/examples/workflow-run.example.json
python3 docs/sejong/scripts/audit_workflow_run_risks.py --repo-root . --artifact-dir docs/sejong/examples/workflow-run-corpus --strict-local-refs --min-artifacts 5 --min-workflow-kinds 3 --min-backends 3 --require-promoted
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/benchmark_sejong_surface.py --require-targets
python3 docs/sejong/scripts/sejong_integrated_quality_gate.py --work-dir "$(mktemp -d)"
python3 docs/sejong/scripts/compare_scorecards.py <baseline.scorecard.json> <candidate.scorecard.json>
python3 docs/sejong/scripts/outcome_quality_evaluator.py compare --task docs/sejong/examples/outcome-evaluation/tagback-growth/task.json --baseline docs/sejong/examples/outcome-evaluation/tagback-growth/baseline-current-sot.result.json --candidate docs/sejong/examples/outcome-evaluation/tagback-growth/candidate-runtime-contracts.result.json --min-delta 0.12
python3 docs/sejong/scripts/product_evidence_gate.py check-plan --plan docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-plan.json
python3 docs/sejong/scripts/seungjeongwon_run.py check --path <seungjeongwon-run.json>
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_sejong_integrated_quality_gate.py
python3 docs/sejong/scripts/test_product_evidence_gate.py
python3 docs/sejong/scripts/test_sejong_context.py
python3 docs/sejong/scripts/test_seungjeongwon_run.py
python3 docs/sejong/scripts/test_outcome_quality_evaluator.py
python3 docs/sejong/scripts/test_team_executor.py
python3 docs/sejong/scripts/test_sillok_trace.py
SEJONG_HOME="$(mktemp -d)" python3 docs/sejong/scripts/test_king_sejong_e2e.py
python3 docs/sejong/scripts/project_summary.py docs/sejong/examples/greenfield-full-flow --write
python3 docs/sejong/scripts/team_executor.py check <team-run-dir>
```
