# Sejong Discipline Gates

**Status:** Draft

## Purpose

Discipline gates define why King Sejong should perform a workflow step, what
failure that step prevents, which court surface owns it, how strongly it is
enforced, and how the behavior is verified.

They exist so King Sejong can absorb the useful discipline from external
workflow systems without making those systems the authority layer. Sejong stays
the lead router. OMX, Superpowers, native subagents, host teams, and shell tools
remain subordinate techniques or runtimes.

## Force Levels

Use the lightest force level that prevents the real failure.

| Level | Meaning | Use when |
| --- | --- | --- |
| `hard` | Block completion, protected edits, or handoff until the gate is satisfied. | A false positive would corrupt source-of-truth behavior, protected paths, or completion claims. |
| `route` | Move the workflow to the correct Sejong surface. | The current answer would stop too early or use the wrong court mode. |
| `advisory` | Require visible reasoning or evidence, but do not block by itself. | The rule improves judgment but may have legitimate exceptions. |
| `shadow` | Record and evaluate without changing behavior yet. | The rule is promising but not proven enough for default enforcement. |

Do not use `hard` when `route` is enough. Over-enforcement creates ceremony and
encourages users or agents to bypass Sejong. Under-enforcement recreates the
same failure the gate was meant to prevent.

## Gate Matrix

### Sejong Router First

- **Why:** Broad requests need one authority that decides whether the next useful
  step is research, discussion, planning, execution, verification, or evidence
  recording.
- **Prevents:** A subordinate skill or runtime becoming the de facto
  orchestrator; generic skill-first behavior overriding the active Sejong route.
- **Owner:** Sejong.
- **Force:** `route`.
- **Behavior:** When Sejong or a court surface is active, route through Sejong
  first. Use OMX, Superpowers, native subagents, host teams, or shell helpers
  only as subordinate techniques selected by the current court mode.
- **Verification:** Active context, hook-injected continuation, or final report
  names the current Sejong surface and the next surface when the task is not
  complete.

### Research To Uigwe

- **Why:** Research that is gathered to choose a strategy or prepare execution is
  not the final output; it is planning evidence.
- **Prevents:** A research summary being mistaken for a decision, plan, or
  completed outcome.
- **Owner:** JangYeongsil returns evidence; Sejong owns promotion; Uigwe owns the
  resulting planning contract.
- **Force:** `route`.
- **Behavior:** If research is explicitly for deciding, planning, comparing
  options, or feeding Uigwe, keep `uigwe_promotion_required` pending until Uigwe
  starts or the user narrows the request to research-only.
- **Verification:** The output includes evidence, decision question, serious
  options when applicable, Uigwe input summary, and `next_surface: uigwe`.

### Outcome Completion

- **Why:** Many user requests ask for a result, not a recommendation.
- **Prevents:** Stopping after advice, research, or a plan when the requested
  outcome still needs execution and verification.
- **Owner:** Sejong owns route continuity; Uigwe owns the handoff contract;
  Seungjeongwon owns execution and verification.
- **Force:** `route`.
- **Behavior:** For create/change/fix/implement/validate/prepare/ship requests,
  treat research and advice as helper surfaces. Route through Uigwe before
  Seungjeongwon unless the user explicitly narrows the work to research-only,
  advice-only, plan-only, or no-execution output.
- **Verification:** Final report shows either verified execution evidence,
  explicit blocker evidence, or the approved narrower terminal scope.

### Uigwe To Seungjeongwon

- **Why:** Planning truth and execution truth must be separated. The executor can
  adapt tactics, but not silently change the success contract.
- **Prevents:** Direct edits bypassing an approved Uigwe bundle; execution
  weakening success criteria to make completion easier.
- **Owner:** Uigwe defines the contract; Seungjeongwon executes it.
- **Force:** `hard` for handoff-ready goal-bearing bundles; `route` for
  borderline scope.
- **Behavior:** A handoff-ready Uigwe bundle enters Seungjeongwon for actionable
  decomposition, execution attempts, verification, and feedback. Sejong direct is
  reserved for small exact non-goal operations.
- **Verification:** Seungjeongwon output references the Uigwe source of truth,
  completed or blocked handoff leaves, and verification evidence.

### Root Cause Before Fix

- **Why:** A bug fix without root-cause evidence is usually a symptom patch.
- **Prevents:** Random changes, repeated failed fixes, and tests passing for the
  wrong reason.
- **Owner:** JangYeongsil gathers evidence when the cause is unclear;
  Seungjeongwon owns the execution attempt loop.
- **Force:** `hard` for failures, bugs, regressions, test failures, build
  failures, and unexpected behavior; `advisory` for small non-risky cleanup.
- **Behavior:** Before changing behavior to fix a failure, reproduce or inspect
  the failure, identify where it originates, and state the hypothesis the fix
  will test.
- **Verification:** Attempt ledger or final report records the symptom, evidence,
  root-cause hypothesis, action, verification command or observable proof, and
  result.

### Verification Before Completion

- **Why:** Completion claims are trust-bearing claims and require fresh proof.
- **Prevents:** "Looks done" reports, partial checks, stale verification, or
  trusting worker success reports without independent evidence.
- **Owner:** Seungjeongwon owns final verification; Sillok may record durable
  evidence.
- **Force:** `hard`.
- **Behavior:** Before claiming complete/fixed/passing/ready, identify what would
  prove the claim, run or perform the proof, read the output, and report the
  evidence or the exact validation gap.
- **Verification:** Final report includes fresh command output summary,
  observable proof, schema check, bundle validation, manual runtime result, or
  explicit blocker evidence.

### Decision Justification

- **Why:** Material choices should pass because they are better for the stated
  goal, not because they are the first plausible option.
- **Prevents:** Arbitrary selection, overbuilt designs, missed simpler
  alternatives, hidden trade-offs, and execution that cannot explain why it is
  changing the current system.
- **Owner:** Jiphyeonjeon owns option comparison; Uigwe owns design and handoff choices; Seungjeongwon owns tactical execution choices inside the approved contract.
- **Force:** `route` for material design, planning, or policy choices;
  `advisory` for low-risk local tactics; `hard` only when a choice changes
  protected scope, success criteria, non-goals, or verification bars.
- **Behavior:** For material choices, record the selected option, serious alternatives, rejection reasons, simplest viable alternative, and the falsification or re-entry signal that would reopen the decision.
- **Verification:** Decision notes, `rationale.md`, `goal-tree.json`
  alternatives, or execution feedback show why the selected path remains valid
  and what evidence would make Jiphyeonjeon or Uigwe re-enter the decision.

### Bounded Worker Authority

- **Why:** Parallel workers improve coverage, but they do not own the decision.
- **Prevents:** Majority vote, worker consensus, or subagent confidence becoming
  gate approval, final synthesis, or final verification.
- **Owner:** Sejong owns synthesis and routing; Uigwe owns planning gates;
  Seungjeongwon owns final verification.
- **Force:** `hard` for authority claims; `advisory` for ordinary worker quality.
- **Behavior:** Workers receive a bounded role, scope, allowed outputs,
  forbidden claims, verification expectation, and stop condition. Worker output
  is evidence for the lead, not approval.
- **Verification:** TeamExecutor checks, subagent stop checks, or lead synthesis
  reject claims of Uigwe gate approval, final synthesis, final verification, or
  majority-vote authority.

### Jiphyeonjeon Scholar Sub-Research

- **Why:** A Jiphyeonjeon scholar can make a stronger bounded argument when the
  factual issue behind a claim, objection, or question is checked directly
  instead of left as rhetoric.
- **Prevents:** Lead-only research bottlenecks, evidence-free debate,
  scholar-private evidence hoarding, cherry-picked support, unbounded recursive
  councils, and helper research becoming a hidden decision authority.
- **Owner:** Jiphyeonjeon owns the council brief, scholar scopes, challenge
  rounds, and final synthesis. JangYeongsil-style helper lanes own evidence
  separation only. Sejong owns route authority, and Uigwe owns later planning
  gates.
- **Force:** `route` when a scholar needs a bounded evidence lane; `hard` for
  shared evidence, no final-authority claims, no Uigwe gate approval, and no
  private evidence; `advisory` for ordinary spawn-budget tuning unless the
  workflow is large enough that cost, traceability, or promotion claims make the
  budget part of the success contract.
- **Behavior:** A scholar may open or request sub-research only for an explicit
  `research_question` tied to a visible `decision_claim`, objection, or
  question, with a note on whether the answer could change the decision. The
  lane returns `known`, `inferred`, `unknown`, source refs, confidence, and
  residual risk into the shared evidence bundle. Scholars may cite or rebut that
  evidence during the bounded challenge or persuasion round, but the lead
  synthesizes the decision note.
- **Verification:** The council record or TeamExecutor run shows the
  `research_question`, linked claim or objection, shared evidence ref, source
  refs, separated known/inferred/unknown output, spawn budget or extra-lane
  reason, and absence of claims that the scholar, helper lane, consensus, or
  majority vote approved the final decision or Uigwe gate.

### External Dynamic Workflow Adoption

- **Why:** Dynamic workflow runtimes can improve large research, review, and
  verification work by keeping intermediate worker state outside the lead model
  context and by making fan-out, cross-checking, retry, and synthesis steps
  repeatable. They are useful because they reduce context pollution, make
  independent evidence lanes easier to compare, and can run the same validation
  pattern again instead of relying on one-off prompting.
- **Benefit summary:** dynamic workflow runtimes can improve large research, review, and verification work when the task benefits from repeatable fan-out, cross-checking, retry, and synthesis outside the lead context.
- **Prevents:** Treating an external workflow script, deep-research report,
  ultracode-style mode, or many-agent backend as a new Sejong authority layer;
  promoting a workflow because it ran rather than because it produced a better
  verified result; letting runtime state become a competing Uigwe plan; or
  secretly calling an external Claude CLI, Claude API, or Claude workflow
  runtime as a Sejong backend.
- **Blocked authority summary:** external workflow script, deep-research report, ultracode-style mode, or many-agent backend output is evidence or runtime feedback, not court authority.
- **Owner:** Sejong owns route selection and synthesis. JangYeongsil owns
  research evidence. Jiphyeonjeon owns material option comparison. Uigwe owns
  the normative contract and approval gates. Seungjeongwon owns execution,
  workflow-backend use, verification, and feedback. Sillok owns durable evidence
  records.
- **Force:** `shadow` by default for new workflow-backed behavior that is
  unproven. The workflow-run evidence gate itself is directly promoted after
  explicit user approval and validation. Use `route` when a request should enter
  JangYeongsil, Jiphyeonjeon, Uigwe, or Seungjeongwon before workflow use; use
  `hard` for protected edits, live ambiguity, worker authority claims, external
  actions, and completion claims.
- **Behavior:** Map `/deep-research`-style workflows to JangYeongsil evidence
  gathering plus optional Sillok evidence, not to a final decision or plan. Map
  dynamic workflow concepts to Codex native subagents, host-native teams,
  TeamExecutor, `manual_shadow`, or `codex_mock_workflow` tactics after an
  approved Uigwe contract or clear direct scope, not to a new court mode. Do not
  invoke Claude CLI, Claude API, or an external Claude workflow runtime as a
  hidden backend. Migrate the concept, mock the operational shape, or keep it
  shadowed. A workflow run may hold operational state, but the Uigwe contract
  remains the source of truth for goal, non-goals, success criteria,
  verification bar, must-preserve behavior, and re-entry triggers. Store
  workflow evidence under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`
  unless the user explicitly promotes a reviewed artifact. Record shadowed or
  limited backend runs as `sejong.workflow-run/v0.1-draft` artifacts validated
  by `docs/sejong/scripts/sejong_workflow_run.py`. See
  `docs/sejong/WORKFLOW_RUN.md` for the lifecycle, promotion rules, and
  remaining-risk audit model.
- **Ownership summary:** Sejong owns route selection and synthesis. JangYeongsil owns research evidence. Uigwe owns the normative contract and approval gates. Seungjeongwon owns execution, workflow-backend use, verification, and feedback.
- **Deep research mapping summary:** Map `/deep-research`-style workflows to JangYeongsil evidence gathering plus optional Sillok evidence.
- **Mapping summary:** Map `/deep-research`-style concepts to JangYeongsil evidence gathering plus optional Sillok evidence. Map dynamic workflow concepts to Codex-native or mocked Seungjeongwon and TeamExecutor tactics. In both cases, the Uigwe contract remains the source of truth and Claude runtimes are not invoked.
- **No hidden runtime summary:** Do not invoke Claude CLI, Claude API, or an external Claude workflow runtime.
- **Storage summary:** Store workflow evidence under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless the user explicitly promotes a reviewed artifact.
- **Worker output summary:** worker outputs remain evidence-only.
- **Verification:** Shadow-run workflow-backed candidates against the same
  acceptance criteria as the baseline. Record worker counts, discarded claims,
  unsupported-claim counts, max concurrency, disjoint write scopes, backend
  provenance, cost or token overhead, verification refs, authority violations,
  and outcome-quality delta. Promote only when guardrail scenarios pass, worker
  outputs remain evidence-only, runtime state is externally retained, and the
  candidate result is better enough to justify the overhead.
  Validate the workflow-run artifact with
  `python3 docs/sejong/scripts/sejong_workflow_run.py check --path <workflow-run.json>`
  before using it as promotion evidence.
- **Promotion proposal behavior:** Users should not need to read raw benchmark
  JSON to notice promotion readiness. When all gates pass, Sejong should
  proactively report `Promotion candidate: yes`, summarize the evidence,
  residual risks, and concrete behavior change, then request an explicit user
  decision or cite an already approved Uigwe scope. When gates fail, report
  `Promotion candidate: no` with the failed gate and next evidence needed.
  Recommendation is not approval.
- **Comparison benchmark:** Run
  `python3 docs/sejong/scripts/benchmark_workflow_run_comparison.py --min-score-delta 0.10 --min-multi-metric-score 0.90`
  before promotion. If the hardened workflow-run validator does not beat the
  legacy lightweight baseline by at least `0.10`, reach weighted multi-metric
  score `0.90`, and keep `critical_miss_rate` at `0` on the representative
  use-case matrix, keep it shadowed and redesign the workflow contract. Promoted
  behavior also requires `outcome_quality_delta >= 0.10`, reviewable
  baseline/candidate refs, task-specific acceptance criteria, matching
  comparison/final recommendations, explicit `promotion_approval`, and
  dimension hard minimums for promotion decision quality, outcome quality,
  efficiency/cost, parallelism, reliability, observability, and human/developer
  experience.
- **Remaining-risk verification:** Use
  `python3 docs/sejong/scripts/benchmark_workflow_run_stability.py --samples 9 --warmups 1`
  for timing flake risk and
  `python3 docs/sejong/scripts/audit_workflow_run_risks.py --repo-root . --artifact <workflow-run.json>`
  or `--artifact-dir <workflow-run-corpus-dir> --strict-local-refs` for
  evidence/provenance string risk and real-work corpus risk. These checks make
  residual risk observable; they do not replace actual product or engineering
  success evidence.
- **Promotion summary:** The workflow-run evidence gate is promoted directly in
  this repository by explicit user request.
  Shadow-run workflow-backed candidates against the same acceptance criteria as the baseline before promotion.
  Promote only when future unproven workflow-backed candidate quality beats the
  baseline enough to justify orchestration overhead with fresh verification
  evidence.

### Durable Runtime State

- **Why:** Long workflows must survive compaction, follow-up turns, and handoff
  without requiring the user to reconstruct context.
- **Prevents:** Dropped pending gates, forgotten blockers, duplicated planning,
  and repo pollution with runtime artifacts.
- **Owner:** Sejong active context, Uigwe artifacts, Seungjeongwon run artifacts,
  TeamExecutor state, and Sillok traces.
- **Force:** `route` for substantial workflows; `hard` when Stop or PreCompact
  would lose an active gate or invalid run artifact.
- **Behavior:** Runtime state belongs under
  `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` by default, not `.omx` and not
  target-repo tracked paths.
- **Verification:** Hook checks, context doctor, Seungjeongwon run checks, or
  TeamExecutor checks validate active state and keep repository `git status`
  free of unintended runtime artifacts.

### Outcome Quality Over Route Success

- **Why:** A workflow can route correctly and still produce a worse answer,
  patch, plan, or product artifact.
- **Prevents:** Promoting a behavior because hooks, goals, teams, or route
  markers fired, even though the final artifact is not better.
- **Owner:** Seungjeongwon for execution results; Sillok and outcome-evaluation
  helpers for promotion evidence.
- **Force:** `shadow` by default; `hard` when a change claims improved artifact
  quality or product success.
- **Behavior:** Compare candidate and baseline outputs against the same
  acceptance criteria before promoting a new workflow behavior as better.
- **Verification:** Outcome-quality evaluator, paired result comparison, product
  evidence gate, or task-specific rubric shows the candidate is better enough,
  or the change remains shadowed.

### No Silent Success Redefinition

- **Why:** The fastest way for an agent to appear successful is to change what
  success means after failing.
- **Prevents:** Weakening verification, dropping non-goals, moving scope, or
  redefining done criteria without Uigwe re-entry or user approval.
- **Owner:** Uigwe owns success criteria and re-entry triggers; Seungjeongwon
  owns execution feedback when the contract proves unstable.
- **Force:** `hard`.
- **Behavior:** Execution may adapt tactics and decompose tasks, but it must not
  change the approved goal, non-goals, success criteria, must-preserve behavior,
  verification bar, or re-entry triggers without Uigwe re-entry or human review.
- **Verification:** Execution feedback names any deviation, replacement,
  blocker, or re-entry target. Completion evidence is judged against the
  original approved contract.

## External Technique Mapping

External workflow systems may supply useful techniques, but their authority is
mapped into Sejong surfaces:

| External pattern | Sejong mapping | Note |
| --- | --- | --- |
| Skill-first discipline | Sejong Router First | Sejong is the authority; skills are subordinate. |
| Systematic debugging | Root Cause Before Fix | Use JangYeongsil evidence and Seungjeongwon attempts. |
| Verification before completion | Verification Before Completion | Hard gate before completion claims. |
| Decision records / why review | Decision Justification | Material choices keep alternatives, rejection reasons, and re-entry signals visible. |
| TDD / test-first | Uigwe To Seungjeongwon, Verification Before Completion | Use when behavior changes need executable proof; do not force for every doc/config edit. |
| Brainstorming approval | Uigwe live-session gates | Use for material design choices, not tiny exact tasks. |
| Subagent review loops | Bounded Worker Authority | Reviewers provide evidence; lead owns synthesis. |
| Dynamic workflow scripts | External Dynamic Workflow Adoption / Seungjeongwon backend | Useful for repeatable fan-out, cross-checking, and verification; never a new court mode or Uigwe replacement. |
| Deep-research workflows | JangYeongsil evidence + Sillok evidence | Cited reports and claim ledgers are evidence; decision-prep research still promotes to Uigwe. |
| Worktree isolation | Durable Runtime State / execution safety | Useful tactic, not a Sejong authority requirement. |
| OMX Team | TeamExecutor backend | Optional runtime backend under Sejong state and lead ownership. |
| OMX Ultragoal ledger | Durable Runtime State | Useful ledger pattern; do not store Sejong state in `.omx`. |

## Enforcement Guidance

1. Prefer `route` gates when the next correct action is another court surface.
2. Use `hard` gates for completion claims, protected self-modification, worker
   authority violations, and silent success redefinition.
3. Keep `advisory` gates visible in rationale or final reports when they shape a
   decision.
4. Keep unproven behavior in `shadow` until outcome-quality or integrated
   validation justifies promotion.
5. If a gate creates more process than risk reduction, lower its force level or
   narrow its trigger.
