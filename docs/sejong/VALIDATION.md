# Uigwe Validation Plan

**Status:** Draft

## Purpose

This document defines how to validate Uigwe as a planning method and Sejong-facing skill surface.

The goal is not to prove that a plan sounds good. Uigwe should be checked against frozen scenarios, explicit scorecards, bundle validators, and limited consumer dry runs before a planning change is treated as better.

## Validation Principles

- **Baseline first:** compare Uigwe against normal lightweight planning before claiming improvement.
- **Task-specific scoring:** score the planning behaviors Uigwe exists to improve.
- **Contract before taste:** schema, bundle, gate, and handoff contracts must pass before subjective quality scoring matters.
- **Shadow before default:** try Uigwe on real work in parallel before making it the default planning path for a new workflow.

## What To Compare

Use at least two baselines.

### Baseline A: Lightweight Planning

Normal planning without Uigwe packets, goal trees, readiness gates, or re-entry structure.

Examples:

- direct planning conversation
- short implementation plan
- manual requirements capture plus hand-written checklist

### Baseline B: Structured Planning Without Uigwe

Structured planning that does not use Uigwe's packet and goal-tree contract.

Examples:

- interview notes -> option comparison -> manual task list
- design brief -> implementation plan

### Candidate

- Uigwe through `$uigwe`
- Uigwe reached through `$sejong` when Sejong routes to formal planning

## What To Measure

### Sejong-Level Metrics

- `route_sequence_accuracy`: did Sejong choose the expected surface chain or an explicitly acceptable alternative?
- `overplanning_rate`: how often did Sejong invoke Uigwe or teams for direct tasks?
- `missed_research_rate`: how often did Sejong decide or execute before gathering required evidence?
- `decision_quality`: did Jiphyeonjeon compare serious options, reject weaker ones, and name a defensible next surface?
- `execution_success_rate`: did Seungjeongwon complete actionable leaves with reproducible verification evidence?
- `guardrail_violation_count`: did workers, hooks, or direct edits violate lead-owned gates, final synthesis, or protected paths?
- `continuity_preservation_rate`: did follow-up turns, pending gates, and compacted context keep the active Sejong workflow intact?
- `artifact_hygiene_rate`: did runtime artifacts stay under the Sejong artifact root unless explicitly promoted?
- `tokens_per_successful_scenario`: how many tokens were spent per passing scenario?
- `quality_delta_per_1k_tokens`: how much benchmark score improved for each additional 1,000 tokens.

### Core Metrics

- `mode_resolution_accuracy`: did Uigwe choose or recover to the correct effective mode?
- `packet_completeness_rate`: did it produce the required artifacts for that mode?
- `bundle_validation_pass_rate`: did the generated bundle pass `validate_bundle.py`?
- `handoff_leaf_rate`: how many Uigwe leaf nodes were truly ready for Seungjeongwon handoff?
- `actionable_leaf_rate`: how often did Seungjeongwon decomposition produce executable actionable leaves without weakening the Uigwe contract?
- `handoff_ready_rate`: how often could the plan be handed off without planning guesswork?
- `plan_acceptance_rate`: how often would a human approve the plan with only light edits?
- `approval_gate_violation_count`: how often did live-session gates get skipped or silently waived?
- `unnecessary_reentry_rate`: how often did Uigwe reopen earlier stages without enough justification?
- `human_edit_distance`: how much rewriting was needed after the generated bundle?
- `minutes_to_usable_plan`: how long it took to reach a usable bundle.

### Secondary Metrics

- `retained_alternative_quality`
- `goal_tree_coherence`
- `verification_clarity`
- `risk_summary_quality`
- `blocked_leaf_diagnosis_quality`
- `attempt_ledger_quality`

## Validation Phases

### Phase 1: Deterministic Contract Checks

Run these on every Uigwe contract or schema change:

```bash
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/brownfield-decompose-only
```

### Phase 2: Instruction-Surface Guardrail Benchmark

Run this when changing `.agents/skills`, router docs, README guidance, live-session rules, or validation docs:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
```

This benchmark is deterministic. It checks whether the installed skill surface still exposes the required routing, live-session, output, validation, bounded-parallelism, active-context, hook, protected-route, and repo-context init/refresh contracts.

### Phase 2B: King Sejong Guardrail TDD

Run these when changing active context checkpoints, hooks, TeamExecutor authority, protected self-modification rules, or runtime artifact retention:

```bash
python3 docs/sejong/scripts/test_king_sejong_hooks.py
python3 docs/sejong/scripts/test_sejong_context.py
python3 docs/sejong/scripts/test_team_executor.py
python3 docs/sejong/scripts/test_sillok_trace.py
SEJONG_HOME="$(mktemp -d)" python3 docs/sejong/scripts/test_king_sejong_e2e.py
```

Expected red tests before implementation:

- protected Sejong path edits pass without route evidence
- follow-up prompts fail to receive active King Sejong context
- subagents can claim Uigwe gate approval or final synthesis
- `$team` workers can claim final decisions by majority vote
- runtime artifacts affect the target repository working tree

Expected green behavior:

- `UserPromptSubmit` injects active context
- `sejong_context.py` can start, update, diagnose, and close the active context pointer without writing runtime state into the target repository
- `PreToolUse` and `PermissionRequest` guard protected paths
- `SubagentStop` rejects gate and final-authority claims
- `Stop` continues when verification gates remain
- TeamExecutor invalid authority fixtures fail for the expected reason
- Sillok trace events reject private-data, untrusted-content, external-action combinations without a human approval ref
- runtime artifacts stay under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`

### Phase 2C: Sejong Surface Seed Benchmark

Run this when changing Sejong routing, active-session behavior, TeamExecutor guidance, hooks, Seungjeongwon handoff behavior, validation scorecards, or evaluation docs:

```bash
python3 docs/sejong/scripts/benchmark_sejong_surface.py --require-targets
```

Use `--write` only when intentionally refreshing the deterministic scorecard artifacts:

```bash
python3 docs/sejong/scripts/benchmark_sejong_surface.py --write --require-targets
```

This benchmark does not call an LLM. It validates that `examples/validation/sejong-seed-task-set.json` remains a complete, gradeable Sejong-level scenario set with route sequences, acceptable alternatives, forbidden surfaces, guardrail expectations, observable artifacts, and resource budgets.

### Phase 2D: Outcome Quality Pairwise Evaluation

Run this when the change claims that Sejong produces better work products, not only better routing or guardrail behavior:

```bash
python3 docs/sejong/scripts/outcome_quality_evaluator.py compare \
  --task docs/sejong/examples/outcome-evaluation/tagback-growth/task.json \
  --baseline docs/sejong/examples/outcome-evaluation/tagback-growth/baseline-current-sot.result.json \
  --candidate docs/sejong/examples/outcome-evaluation/tagback-growth/candidate-runtime-contracts.result.json \
  --min-delta 0.12
```

The seed TagBack growth scenario grades causal diagnosis, audience/JTBD clarity, marketing strategy, experiment prioritization, instrumentation, owner split, risk controls, evidence quality, and actionability. It is a deterministic artifact-quality gate. It does not replace real product analytics, A/B tests, user interviews, or human judgment.

### Phase 2D.1: Discipline Gate Contract Review

Run this review when adding or changing why-based Sejong discipline gates:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/benchmark_sejong_surface.py --require-targets
```

Each gate must state:

- why the behavior exists
- what failure it prevents
- owning court surface
- force level: `hard`, `route`, `advisory`, or `shadow`
- verification evidence

Do not promote an external workflow pattern into Sejong unless it maps to a
Sejong-owned surface and a concrete prevented failure. Keep unproven patterns in
`shadow` until outcome-quality or integrated validation justifies stronger
enforcement.

### Phase 2D.2: Dynamic Workflow Shadow Comparison

Run this when evaluating external dynamic workflow concepts such as documented
Claude Code dynamic workflows, `/deep-research`, `ultracode`-style behavior, or
any workflow-like backend idea for King Sejong:

See [WORKFLOW_RUN.md](WORKFLOW_RUN.md) for the workflow-run lifecycle, promotion
rules, result interpretation, and remaining-risk audit model.

```bash
python3 docs/sejong/scripts/sejong_workflow_run.py check --path <workflow-run.json>
python3 docs/sejong/scripts/benchmark_workflow_run.py
python3 docs/sejong/scripts/benchmark_workflow_run_comparison.py --min-score-delta 0.10 --min-multi-metric-score 0.90
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/benchmark_sejong_surface.py --require-targets
python3 docs/sejong/scripts/sejong_integrated_quality_gate.py --work-dir "$(mktemp -d)"
```

Start in `shadow`. The candidate workflow may produce evidence, a proposed route,
or a proposed Seungjeongwon backend plan, but it must not alter Uigwe approval
gates, final route selection, execution scope, or completion status during the
shadow run.

Do not call Claude CLI, Claude API, or an external Claude workflow runtime as a
hidden backend. The candidate must be migrated to Codex-native subagents,
host-native team support, TeamExecutor, `manual_shadow`, or
`codex_mock_workflow`, or it must remain unpromoted.

Record at minimum:

- a `sejong.workflow-run/v0.1-draft` artifact that validates against
  `docs/sejong/workflow-run.schema.json`
- structured `backend_provenance` proving the backend is Codex-native,
  host-native, TeamExecutor, `manual_shadow`, `codex_mock_workflow`, or an
  explicitly approved non-Claude mock
- structured `artifact_storage`; repo-local workflow-run files require an
  explicit promotion ref, while normal runtime artifacts remain under the
  external Sejong store
- structured `metrics` with `worker_count`, `max_concurrency`,
  `unsupported_claim_count`, `token_or_cost_overhead_ref`, and
  `write_scopes_disjoint`
- whether the workflow maps to JangYeongsil, Jiphyeonjeon, Uigwe,
  Seungjeongwon, TeamExecutor, or Sillok rather than becoming a new court mode
- worker count, max concurrency, and whether write scopes were disjoint
- backend value, proving it is Codex-native, host-native, TeamExecutor,
  `manual_shadow`, `codex_mock_workflow`, or another explicitly approved
  non-Claude mock
- source refs, discarded claims, unsupported-claim count, and cross-check status
  for deep-research-style runs
- whether any worker claimed Uigwe gate approval, final synthesis, final
  verification, consensus approval, or majority-vote authority
- whether runtime state was retained under
  `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`
- baseline result, candidate result, outcome-quality delta, token or cost
  overhead, and the final recommendation: promote, reject, or keep shadowing
- reviewable baseline/candidate refs, non-empty task-specific acceptance
  criteria, and matching quality-comparison and final recommendations once the
  run is completed

Promotion requires:

- no protected guardrail scenario regressions
- no approval-gate or worker-authority violations
- no live ambiguity bypass
- explicit `promotion_approval` from the user or from an already approved Uigwe
  scope
- fresh verification evidence against the original Uigwe or direct-scope
  success criteria
- `outcome_quality_delta >= 0.10` for promoted behavior
- `manual_shadow` must not be the promoted backend; migrate the behavior to a
  Codex-native, host-native, TeamExecutor, or approved mock backend first
- `backend=other` provenance must use specific summaries and reviewable command
  refs rather than self-attested text
- candidate quality that beats the baseline enough to justify orchestration
  overhead under the promotion thresholds below

Sejong should be proactive after these checks. If all promotion gates pass,
report `Promotion candidate: yes` with the evidence summary, remaining risks,
and concrete behavior change, then wait for explicit promotion approval. If any
gate fails, report `Promotion candidate: no` with the failed gate and the next
evidence needed. A recommendation is not approval.

Use `docs/sejong/scripts/benchmark_workflow_run.py` and
`docs/sejong/scripts/test_sejong_workflow_run.py` to exercise the representative
matrix: deep-research shadow evidence, dynamic workflow Codex mock promotion,
TeamExecutor rejection after authority violation, ultracode-style subagent
shadowing, hidden-Claude rejection, weak positive-delta promotion rejection,
empty acceptance-criteria rejection, final-recommendation mismatch rejection,
manual-shadow promoted-backend rejection, overhead-adjusted promotion rejection,
explicit `other` backend provenance, repo-local artifact hygiene, duplicate ids,
unsupported surfaces, overlapping write scopes, and large-ledger validation performance.

Use `docs/sejong/scripts/benchmark_workflow_run_comparison.py` to compare the
hardened workflow-run validator against the legacy lightweight ledger baseline.
Promotion requires at least `0.10` score improvement on the same use-case matrix,
candidate score `1.0`, candidate weighted multi-metric score at least `0.90`,
zero critical misses, and passing large-ledger validation. The multi-metric
scorecard weights `promotion_decision_quality` first, then `outcome_quality`,
`efficiency_cost`, `parallelism_efficiency`, `reliability_reproducibility`,
`observability_diagnosability`, and `human_developer_experience`. Candidate
dimension hard minimums are `1.00` for promotion decision quality, parallelism,
and reliability, `0.90` for outcome quality, observability, and human/developer
experience, and `0.60` for efficiency/cost. If the comparison misses either the
10 percent improvement gate, the multi-metric gate, or any dimension hard
minimum, keep the workflow shadowed and redesign the validator before promotion.

Dynamic workflow promotion summary: candidate quality that beats the baseline enough to justify orchestration overhead must be shown before a shadowed workflow-backed behavior is promoted.

### Phase 2D.3: Dynamic Workflow Remaining-Risk Verification

Run this after Phase 2D.2 when the remaining concern is not whether the
workflow-run contract works, but whether its residual risks are observable:

```bash
python3 docs/sejong/scripts/benchmark_workflow_run_stability.py --samples 9 --warmups 1 --max-large-ledger-seconds 1.0 --max-p95-seconds 1.0
python3 docs/sejong/scripts/audit_workflow_run_risks.py --repo-root . --artifact <workflow-run.json>
python3 docs/sejong/scripts/audit_workflow_run_risks.py --repo-root . --artifact-dir <workflow-run-corpus-dir> --strict-local-refs --min-artifacts 5 --min-workflow-kinds 3 --min-backends 3 --require-promoted
python3 docs/sejong/scripts/test_benchmark_workflow_run_stability.py
python3 docs/sejong/scripts/test_audit_workflow_run_risks.py
```

The source repository's promoted workflow-run evidence-gate corpus is
`docs/sejong/examples/workflow-run-corpus/`. It should pass the strict corpus
audit command above with `--require-promoted`. Passing that corpus promotes the
workflow-run gate as the checked evidence shape; it does not grant default
authority to any new external workflow backend.

The checked workflow-run evidence gate is applied directly in this repository
after explicit user approval. Future unproven workflow-backed behaviors still
start shadowed until their own artifact, comparison, approval, and strict audit
evidence pass.

This phase verifies three residual risks:

- **Timing flake risk:** repeated large-ledger samples report candidate
  `median`, `p95`, `max`, failure rate, and per-sample timings instead of a
  single wall-clock run.
- **Evidence/provenance string risk:** workflow-run artifacts are audited for
  schema validity, hidden runtime failures, repo-local artifact policy,
  baseline/candidate ref kinds, missing local evidence refs, and symbolic refs
  that cannot serve as promotion proof.
- **Real-work corpus risk:** a workflow-backed behavior may not leave `shadow`
  solely from curated fixtures. Promotion proof needs a corpus audit with enough
  artifacts, workflow kinds, backend types, and at least one promoted run when
  `--require-promoted` is set. Use `--strict-local-refs` so baseline and
  candidate refs resolve to existing local files or URLs.

Passing this phase still does not claim real product or engineering success by
itself. It proves that the remaining risks are measurable and that promotion
claims have concrete workflow-run evidence to inspect.

### Phase 2E: Integrated Quality Gate

Run this when a change must prove it composes with the latest Sejong SOT rather than only passing in isolation:

```bash
python3 docs/sejong/scripts/sejong_integrated_quality_gate.py --work-dir "$(mktemp -d)"
python3 docs/sejong/scripts/test_sejong_integrated_quality_gate.py
```

This gate checks that the TagBack outcome-quality comparison, research-to-Uigwe write gate, active Seungjeongwon run state, TeamExecutor persuasion mailbox, visible todo events, paired result comparison, and product-evidence gate can all operate together. Passing this gate means the Sejong runtime pieces are compatible and produce a stronger strategy artifact for the seed goal. It still does not prove real-world product success.

### Phase 2E.1: Long-Session Outcome Entry Gate

Use this phase before promoting long-session behavior for any task class:

```bash
python3 docs/sejong/scripts/long_session_experiment_gate.py judge \
  --task docs/sejong/examples/outcome-evaluation/sejong-long-session/task.json \
  --baseline docs/sejong/examples/outcome-evaluation/sejong-long-session/baseline-short.result.json \
  --candidate docs/sejong/examples/outcome-evaluation/sejong-long-session/candidate-route-only.result.json \
  --min-delta 0.2 \
  --max-token-ratio 2.0
python3 docs/sejong/scripts/long_session_experiment_gate.py judge \
  --task docs/sejong/examples/outcome-evaluation/sejong-long-session/task.json \
  --baseline docs/sejong/examples/outcome-evaluation/sejong-long-session/baseline-short.result.json \
  --candidate docs/sejong/examples/outcome-evaluation/sejong-long-session/candidate-long-session.result.json \
  --min-delta 0.2 \
  --max-token-ratio 2.0
python3 docs/sejong/scripts/test_long_session_experiment_gate.py
```

The bundled long-session examples are smoke fixtures. A real promotion proof must pass the same gate with `--require-promotion`, real `--baseline-root` and `--candidate-root` directories, and host-observed `--baseline-events` and `--candidate-events` from the runs. The task and both results must carry the same `task_class`; `code-review-defect-analysis` additionally requires defect-first critic evidence.

Use [blind_semantic_quality_gate.py](scripts/blind_semantic_quality_gate.py) only as supporting semantic evidence after deterministic gates pass:

```bash
python3 docs/sejong/scripts/blind_semantic_quality_gate.py pack \
  --task <task.json> \
  --baseline-result <baseline.result.json> \
  --candidate-result <candidate.result.json> \
  --baseline-root <baseline-worktree> \
  --candidate-root <candidate-worktree> \
  --judge-goal "<artifact-quality objective, not the experiment comparison>" \
  --write-packet <blind.packet.json> \
  --write-key <blind.key.json>
python3 docs/sejong/scripts/blind_semantic_quality_gate.py judge-result \
  --packet <blind.packet.json> \
  --key <blind.key.json> \
  --judgment <blind.judgment.json> \
  --min-delta 0.5
```

Do not promote long-session globally from one class. Keep it shadowed for each class until repeated strict evidence shows better artifacts with acceptable overhead and no direct-task regression.

### Phase 2F: Product Evidence Gate

Run this when Sejong would otherwise be tempted to claim that a product, marketing, or growth plan actually succeeded:

```bash
python3 docs/sejong/scripts/product_evidence_gate.py check-plan \
  --plan docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-plan.json
python3 docs/sejong/scripts/product_evidence_gate.py judge-result \
  --plan docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-plan.json \
  --result docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-result.example.json \
  --require-success
python3 docs/sejong/scripts/test_product_evidence_gate.py
```

This gate separates artifact-quality promotion from real product-success claims. It requires external evidence refs plus analytics, controlled experiment, and user research results before `can_claim_product_success=true`.

### Phase 3: Frozen Planning Benchmark

Use `examples/validation/uigwe-seed-task-set.json` as the first task set.

For each scenario:

1. run Baseline A
2. fill a scorecard
3. run Baseline B
4. fill a scorecard
5. run Uigwe
6. fill a scorecard
7. compare aggregate metrics and scenario-level deltas

Patch Uigwe only after reviewing where it actually lost.

### Phase 4: Shadow Planning

Run Uigwe in parallel on real work without making it authoritative.

Recommended sample:

- `5` small greenfield tasks
- `5` small brownfield tasks

Use this to find scenario types the frozen benchmark missed.

### Phase 5: Limited Executor/Consumer Dry Run

Take a small subset of Uigwe `handoff_leaf` nodes and hand them to Seungjeongwon. Seungjeongwon should first run todo listup, todo verification, and subtodo decomposition until `actionable_leaf` units exist, then dispatch those actionable leaves to the Codex consumer only when a lower-level consumer lane is explicitly part of the run.

Record the result with:

- `consumer-dry-run-result.schema.json`
- `codex-consumer-feedback.schema.json`

Do not claim full executor readiness from a limited dry run. Use it to expose whether handoff leaves decompose into actionable leaves and whether the execution attempt ledger produces useful evidence.

### Phase 5B: Implicit Native Goal Handoff Comparison

Compare the current non-goal-backed Seungjeongwon handoff against `implicit native goal handoff` before promoting goal-backed execution as the default for a workflow class.

Baseline:

- Uigwe produces a handoff-ready bundle.
- Seungjeongwon runs the adaptive todo loop without a host-native goal.
- Completion relies on visible board state, execution feedback, verification evidence, and the final assistant report.

Candidate:

- Uigwe produces the same handoff-ready bundle.
- Seungjeongwon creates or attaches a native goal automatically at execution entry when the host supports it.
- The native goal carries only the broad objective, completion criteria, verification evidence requirements, blocker policy, and Uigwe re-entry triggers.
- Seungjeongwon still owns todo verification, subtodo decomposition, redefinition events, attempt ledger entries, verification, and execution feedback.

Score both runs on:

- `goal_activation_accuracy`: native goals are created for handoff-ready outcome-completion work and not created for research-only, advice-only, plan-only, open-ambiguity, or Sejong-direct work
- `goal_payload_quality`: the goal captures the approved objective and completion bar without embedding the executor todo tree
- `adaptive_todo_preservation`: Seungjeongwon still performs todo verification, decomposition, visible board updates, and redefinition/replacement events
- `outcome_result_quality`: the candidate's final answer, chosen experiments, implementation patch, or action split is better than the baseline against the same acceptance criteria
- `hypothesis_quality`: the candidate identifies stronger root-cause hypotheses, separates known facts from assumptions, and rejects weak hypotheses with reasons
- `actionability_delta`: the candidate produces clearer Codex-owned next actions, user-owned next actions, dependencies, and first verification steps
- `completion_evidence_quality`: completion is tied to fresh verification evidence, not only goal status
- `blocked_state_quality`: blockers name the repeated condition, required user or external action, and Uigwe re-entry target when applicable
- `continuity_gain`: compacted or resumed work has enough state to continue without the user reconstructing context
- `overhead_delta`: native goal backing does not add ceremony when the work is small or direct

The comparison must judge the resulting work product, not only route intent or goal activation. For each paired run, record:

- same starting prompt and same available evidence
- baseline final result
- candidate final result
- acceptance-criteria score for each result
- evidence quality and unsupported-claim count
- executable Codex action quality
- user-owned action quality
- verification or measurement plan quality
- cost, turns, and tool-call overhead
- final recommendation: promote, reject, or keep shadowing implicit native goal handoff for that task class

The comparison itself should be run through Seungjeongwon's verification decomposition loop. First list the perspectives needed to judge the result, then define how each perspective will be checked, verify whether those checks are sufficient, split weak perspectives, and only then score the paired outputs.

Use strategy tasks such as the TagBack growth scenario to test this comparison. A good run investigates product, marketing, distribution, monetization, onboarding, App Store presence, user feedback, analytics gaps, and code/release constraints before selecting experiments. It must separate Codex-owned actions from user-owned business actions and must not claim product success without measurable external evidence.

### Phase 6: Scorecard Comparison

Compare a baseline scorecard and candidate scorecard before promoting a Sejong or Uigwe behavior change:

```bash
python3 docs/sejong/scripts/compare_scorecards.py <baseline.scorecard.json> <candidate.scorecard.json> --require-non-regression
```

When the scorecards include `resource_usage`, review:

- `quality_delta`
- `token_ratio`
- `cost_ratio`
- `cost_normalized_gain`
- scenario-level regressions

Token and cost deltas are secondary metrics. They should not hide a real quality improvement, but a candidate that spends substantially more tokens without score gains should not be promoted by default.

## Recommended Promotion Gates

Do not promote a planning-method change unless the frozen benchmark and shadow runs meet these first-pass targets:

- `mode_resolution_accuracy >= 0.80`
- `packet_completeness_rate >= 0.90`
- `bundle_validation_pass_rate >= 0.90`
- `handoff_leaf_rate >= 0.85`
- `actionable_leaf_rate >= 0.80`
- `handoff_ready_rate >= 0.80`
- `plan_acceptance_rate >= 0.70`
- `approval_gate_violation_count == 0`
- `unnecessary_reentry_rate <= 0.15`
- `median_human_edit_distance` improves over Baseline B
- Sejong surface benchmark has no partial or failing scenarios
- scorecard comparison has no scenario-level regressions for protected guardrail scenarios
- if `token_ratio > 1.25`, require either `quality_delta >= 0.10` or an explicit overhead justification
- if `token_ratio > 1.50` and `quality_delta < 0.05`, hold the change for redesign

These are initial targets, not permanent truth.

## How To Grade

Code-grade what can be checked mechanically:

- schema validity
- bundle validity
- artifact presence
- required field completeness
- expected mode match
- instruction-surface guardrail preservation

Human or LLM-grade what needs judgment:

- whether re-entry was appropriate
- whether retained alternatives were meaningful
- whether a human would approve the plan with light edits
- whether handoff leaves are truly ready for Seungjeongwon
- whether actionable leaves are truly executable

Prefer bounded judgments:

- `pass`
- `partial`
- `fail`

or numeric scores in `[0, 1]`.

## Current Deliverables

This validation pack includes:

- this plan
- task-set and scorecard schemas
- a seed frozen planning task set
- a seed Sejong surface task set
- an instruction-surface task set
- a scorecard template
- a deterministic instruction-surface benchmark runner
- a deterministic Sejong surface benchmark runner
- a scorecard comparison helper with token and cost deltas
- a Sillok trace-event schema for evidence, verification, handoff, and security-review records
- King Sejong hook, TeamExecutor, and end-to-end guardrail tests
- Seungjeongwon active run schema and lifecycle helper
- a deterministic outcome-quality evaluator and TagBack growth paired-comparison fixture
- an integrated quality gate that combines latest SOT guardrails with the runtime-quality additions
- a product-evidence gate for analytics, controlled experiment, and user-research based success claims
- a run output directory for benchmark scorecards

## Failure Cases

Treat Uigwe as failing a scenario when:

- it chooses the wrong entry mode and does not recover
- it generates incomplete packets for the chosen mode
- it skips or silently waives live-session approval gates
- it marks ambiguous nodes as handoff leaves
- Seungjeongwon marks broad or unverifiable todos as actionable leaves
- it repeatedly re-enters earlier stages without improving plan quality
- the plan still requires major human restructuring

## Why Real Usage Is Not Enough

Real usage is necessary, but it is not enough.

It helps discover friction, missing scenarios, and handoff problems. It does not prove that Uigwe beats the existing planning workflow, that re-entry is improving quality, or that leaf execution is safer.
