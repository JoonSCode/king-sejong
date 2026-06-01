# App-Scoped Runtime Strategy

**Status:** Draft strategy, first Seungjeongwon execution pass implemented

## Execution Status

The first execution pass implements the low-overhead runtime hardening path:

- Phase 0 context integrity: implemented through `sejong_context.py repair`,
  doctor repair guidance, and invalid-list-item regression tests.
- Phase 1 repo mismatch visibility: implemented for continuation events with
  `repo_mismatch=true` context and explicit-exit preservation.
- Phase 2 repo-scoped context selection: implemented by resolving the newest
  valid matching run context from `${SEJONG_HOME}/runs` when the active pointer
  is stale or missing.
- Phase 3 Seungjeongwon receipt gate: implemented through the
  `seungjeongwon_receipt_required` pending gate for write-like actions,
  permission requests, and premature stop attempts. The residual manual-gate
  risk is closed by `sejong_context.py --goal-bearing`,
  `--require-seungjeongwon-receipt`, and by making the receipt requirement an
  explicit pending gate rather than inferring it from `required_route_sequence`.
- Phase 4 completion-state split: implemented in the Seungjeongwon closeout
  contract and guarded by an instruction-surface benchmark scenario.
- Phase 5 compaction continuity: implemented by injecting active
  Seungjeongwon run id and open todo count into context summaries.
- Phase 6 replay: covered by a deterministic CoupleInvestmentApp replay hook
  test that keeps "다음" inside the gate and blocks writes before receipt.

Still deferred:

- No strategy phases are intentionally deferred in this pass. The remaining
  boundary is intentional: hooks do not block non-Sejong work when no active
  Sejong context exists. Future work should focus on outcome-quality replay
  comparisons rather than adding broader runtime machinery.

## Purpose

This document turns the CoupleInvestmentApp workflow failure analysis into a
King Sejong improvement strategy.

The problem was not only that one app task needed better verification. The
failure pattern showed that a goal-bearing app workflow can produce useful code
while King Sejong's live runtime state is stale, invalid, or scoped to another
repository. In that state, Seungjeongwon discipline becomes a post-hoc audit
instead of the execution controller.

The strategy below keeps King Sejong Codex-native. It does not introduce an
OMX/OMO-style replacement runtime, and it does not turn every app edit into a
hard block. It adds the smallest runtime checks needed to prevent the observed
failure:

- no silent stale active context
- no product-code execution before an explicit Seungjeongwon receipt when a
  goal-bearing Sejong context requires one
- no completion claim that collapses local, canonical, and external gate states
- no compaction loss for an active app leaf

## Evidence Base

Primary failure artifact:

- `/Users/junsu/.codex/sejong/artifacts/couple-investment-app/2026-06-01/couple-app-history-runtime-cause-and-verification.md`

Current source surfaces:

- [ROUTER.md](ROUTER.md)
- [DISCIPLINE_GATES.md](DISCIPLINE_GATES.md)
- [HOOKS.md](HOOKS.md)
- [RUNTIME_CONTRACT.md](RUNTIME_CONTRACT.md)
- [SEUNGJEONGWON_EXECUTOR.md](SEUNGJEONGWON_EXECUTOR.md)
- [king-sejong-context.schema.json](king-sejong-context.schema.json)
- [seungjeongwon-run.schema.json](seungjeongwon-run.schema.json)

External patterns reviewed during the failure analysis:

- Superpowers: mandatory skill-before-action and verification-before-completion.
- OMX: repo session resume, HUD, durable task/review state, explicit verdict.
- OMO: compaction context and todo capture/restore.
- Codex: lifecycle hooks and repo instruction surfaces are primitives, not a
  full Sejong runtime by themselves.

## Decision Question

How should King Sejong prevent the CoupleInvestmentApp failure mode without
over-engineering the runtime?

## Serious Options

### Option A: Hook-only hard enforcement

Make hooks deny most write-like actions whenever Sejong is active and
Seungjeongwon is not the current surface.

Pros:

- Simple mental model.
- Catches many bypasses.
- Strongly communicates that Seungjeongwon is the execution path.

Cons:

- High false-positive risk for small direct fixes, user-explicit direct work,
  and non-goal maintenance.
- Hooks cannot reliably infer user intent from every tool call.
- Users and agents may bypass Sejong if it feels ceremonial.

Decision: reject as default. Use hard blocks only when an active context already
declares the specific pending gate.

### Option B: Separate full runtime with HUD, task graph, and scheduler

Build a new Sejong runtime surface similar to OMX/OMO with repo sessions,
current-run HUD, task graph, compaction restore, worker coordination, and
execution ledger.

Pros:

- Strong continuity.
- Better for long unattended tasks.
- More replayable than conversation-only state.

Cons:

- Too broad for the observed failure.
- Duplicates existing Uigwe, Seungjeongwon run, TeamExecutor, and hook surfaces.
- Raises maintenance burden before there is enough outcome-quality evidence.

Decision: keep in shadow. Borrow specific patterns, not the whole runtime.

### Option C: Repo-scoped context plus explicit execution receipt

Keep the current King Sejong architecture, but add:

- context validity repair and doctor coverage
- repo-scoped context selection or mismatch surfacing
- a context-driven pre-edit gate for goal-bearing work
- a current-run receipt that references a Seungjeongwon run artifact
- completion-claim split for local, canonical, and external states
- replay tests based on the CoupleInvestmentApp sequence

Pros:

- Directly targets the observed failure.
- Fits existing `active-context`, `seungjeongwon-run`, hooks, and discipline
  gates.
- Can be introduced in phases with shadow metrics before hard enforcement.
- Avoids blocking ordinary direct work unless Sejong has declared a gate.

Cons:

- Requires careful migration from the single active pointer model.
- Needs clear tests to avoid silent no-op behavior.
- Still relies on an active Sejong context existing for the target repo; once
  the context requires Seungjeongwon, the receipt gate no longer depends on a
  manually copied pending-gate string.

Decision: selected strategy.

## Strategy

### Phase 0: Repair context integrity

Goal:

- Make active context validity trustworthy before adding new behavior.

Changes:

- Add a small repair or migration path for invalid active contexts where
  `evidence_refs` or other list fields contain non-string values.
- Make `sejong_context.py doctor` print the exact repair suggestion, not only
  the failure.
- Add a regression fixture for the invalid context shape observed in the app
  failure analysis.

Verification:

- `python3 docs/sejong/scripts/test_sejong_context.py`
- new context doctor test for invalid list item repair guidance
- manual doctor command against a copied invalid fixture

Exit criteria:

- Invalid active context never looks silently usable.
- The user or installer has an obvious repair path.

### Phase 1: No silent repo mismatch

Goal:

- Prevent an active context from another repo from failing closed with no model
  signal.

Changes:

- Update hook dispatch so `UserPromptSubmit`, `SessionStart`, and `PostCompact`
  surface a compact repo-mismatch warning when context exists but does not cover
  the current `cwd`.
- Do not hard-deny ordinary writes on mismatch in this phase. The hook cannot
  prove the current work is goal-bearing yet.
- Add an optional `sejong_context.py doctor --repo-root <path>` message that
  names both the context repo and requested repo.

Verification:

- Hook test: app `cwd` plus `king-sejong` context returns additional context
  explaining the mismatch.
- Hook test: matching `cwd` still injects normal active context.
- Hook test: explicit Sejong exit remains quiet.

Exit criteria:

- The CoupleInvestmentApp mismatch would have been visible before the next app
  edit.

### Phase 2: Repo-scoped context selection

Goal:

- Avoid one global stale active pointer becoming the only runtime truth.

Changes:

- Add a context resolver that can select the newest valid context whose
  `repo_root` contains the current `cwd`.
- Keep the existing `state/active-context.json` pointer for compatibility.
- Add a repository-scoped index or lookup helper under `${SEJONG_HOME}/runs`
  before introducing a new schema version.
- If no matching context exists, hooks should either return a mismatch warning
  from the stale active context or no-op with an explicit "no active Sejong
  context for this repo" context when the prompt mentions Sejong.

Verification:

- Unit test: resolver picks the matching app context over a newer unrelated
  context.
- Unit test: invalid contexts are skipped and reported.
- E2E test: two repositories can have separate active contexts without the
  second losing the first.

Exit criteria:

- Follow-up turns in one repo cannot accidentally inherit another repo's route
  authority.

### Phase 3: Context-driven pre-edit Seungjeongwon receipt

Goal:

- Prevent implementation-by-backfill when Sejong has already classified the work
  as goal-bearing and requiring Seungjeongwon.

Changes:

- Introduce a pending gate name:

```text
seungjeongwon_receipt_required
```

- When this gate is present, deny write-like product edits until:
  - `route_sequence` includes `seungjeongwon`
  - `current_surface` is `seungjeongwon`
  - `artifact_refs` includes a readable valid `sejong.seungjeongwon-run/v0.1-draft`
    artifact or an explicit `native_goal_unavailable` execution-feedback ref
    for small direct execution
- Keep protected self-modification behavior unchanged.
- Keep the gate context-driven; do not infer it from every write-like tool call
  or from `required_route_sequence` alone.

Verification:

- PreToolUse test: write-like app edit is denied while
  `seungjeongwon_receipt_required` is pending.
- PreToolUse test: route-only mention of `seungjeongwon` is allowed when the
  explicit pending-gate string is missing.
- PreToolUse test: read-only actions are allowed.
- PreToolUse test: write-like edit is allowed after a valid Seungjeongwon run
  receipt exists.
- Stop test: completion is blocked while the receipt gate remains pending.

Exit criteria:

- A future CoupleInvestmentApp-style implementation cannot start after Uigwe
  handoff without an execution receipt.

### Phase 4: Completion-state split

Goal:

- Stop "locally verified", "integrated into canonical repo", and "externally
  distributable" from being collapsed into one completion claim.

Changes:

- Add a documented completion claim template to [SEUNGJEONGWON_EXECUTOR.md](SEUNGJEONGWON_EXECUTOR.md)
  or [DISCIPLINE_GATES.md](DISCIPLINE_GATES.md):
  - local implementation state
  - canonical repo/branch state
  - verification evidence
  - external gates
  - warnings/noise still present
- Add optional Seungjeongwon execution feedback fields later only if the template
  proves useful enough. Do not expand schemas first.

Verification:

- Instruction benchmark target for a "deployable?" app question requires the
  state split.
- Completion-audit test fixture checks that final answer does not claim external
  readiness from simulator/build evidence alone.

Exit criteria:

- Future answers cannot pass validation if they treat TestFlight/App Store,
  CloudKit two-account proof, or eligible-device AI proof as done from local
  tests alone.

### Phase 5: Compaction-safe current-run continuity

Goal:

- Preserve the current app leaf across compaction and short follow-up prompts.

Changes:

- Use existing `seungjeongwon-run` artifacts as the current-run authority.
- Store the run artifact path in active context `artifact_refs`.
- Extend `PreCompact` and `PostCompact` tests so context summary includes:
  - current repo
  - current surface
  - pending gates
  - active Seungjeongwon run id and open todo count
- Avoid a new `current-run.json` format until `seungjeongwon-run` proves
  insufficient.

Verification:

- PreCompact blocks broken or invalid run refs, as it does today.
- PostCompact injects active run summary.
- Replay test: "다음" after compaction still sees the active leaf and gate.

Exit criteria:

- Compaction cannot erase the active execution leaf or pending gate.

### Phase 6: CoupleInvestmentApp replay acceptance test

Goal:

- Verify the strategy against the actual failure pattern, not only unit tests.

Replay prompts:

1. `배포 가능한 퀄리티인지 검토해봐`
2. `추천순서대로 진행해`
3. `다음`
4. `승정원으로 마무리까지 진행`

Expected behavior:

- The first prompt creates or requests an app-scoped Sejong context.
- No product-code write occurs before Uigwe or an explicit direct-scope contract.
- When the work becomes implementation, `seungjeongwon_receipt_required` is set
  explicitly; `required_route_sequence` alone does not imply the receipt gate.
- PreToolUse denies writes until the Seungjeongwon receipt exists.
- "다음" is classified as same leaf, new child leaf, Uigwe re-entry, research-only,
  or external gate.
- The final answer splits local, canonical, and external gates.

Verification:

- Add a deterministic hook replay script or unittest fixture first.
- Record baseline current behavior and candidate behavior.
- Use [OUTCOME_EVALUATION.md](OUTCOME_EVALUATION.md) style paired comparison
  only if the replay result quality, not only routing behavior, is being
  promoted as better.

Exit criteria:

- The exact app-history failure can no longer reproduce in the supported hook
  path.

## Uigwe Handoff Contract

Objective:

- Harden King Sejong runtime behavior so goal-bearing app work cannot silently
  bypass app-scoped context and Seungjeongwon execution receipt.

Non-goals:

- Do not build a new full scheduler, HUD, or task graph runtime in the first
  pass.
- Do not hard-block every write-like action when no active goal-bearing Sejong
  context exists.
- Do not store Sejong runtime state in `.omx`, `.omo`, target repo tracked
  paths, or plugin adapter state.
- Do not treat route-marker success as proof of better user outcomes.

Must preserve:

- Existing protected self-modification guardrails.
- Existing research-to-Uigwe gate.
- Existing ambiguity-register and Seungjeongwon-run Stop/PreCompact behavior.
- Thin plugin adapter boundary.
- Source-repo clean install and user-scope verification behavior.

Success criteria:

- Invalid active context is detected with repair guidance.
- Repo mismatch is visible instead of silent for continuation events.
- A matching repo context can be selected without losing compatibility with the
  existing active pointer.
- `seungjeongwon_receipt_required` blocks write-like execution until a valid
  receipt exists; route-only `seungjeongwon` expectations do not block by
  themselves.
- Completion reports split local, canonical, and external gate states.
- CoupleInvestmentApp replay passes.
- Existing hook, context, installer, and JSON contract tests pass.

Recommended implementation order:

1. Phase 0 context integrity.
2. Phase 1 mismatch surfacing.
3. Phase 3 receipt gate using existing schema fields.
4. Phase 5 compaction summary improvements.
5. Phase 6 replay acceptance test.
6. Phase 2 repo-scoped resolver if mismatch surfacing alone is not enough.
7. Phase 4 instruction/template hardening after the gate behavior is stable.

Why Phase 2 is not first:

- Repo-scoped selection is useful, but it is easier to over-engineer. The more
  urgent failure is silent mismatch plus missing receipt gate. Make those
  visible and testable first.

## Verification Commands

Minimum verification for strategy implementation:

```bash
python3 docs/sejong/scripts/test_sejong_context.py
python3 docs/sejong/scripts/test_king_sejong_hooks.py
SEJONG_HOME="$(mktemp -d)" python3 docs/sejong/scripts/test_king_sejong_e2e.py
python3 docs/sejong/scripts/validate_json_contracts.py
bash scripts/install-sejong.sh --verify .
```

If instruction surfaces change:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
```

If outcome-quality promotion is claimed:

```bash
python3 docs/sejong/scripts/outcome_quality_evaluator.py compare \
  --task <task.json> \
  --baseline <baseline.result.json> \
  --candidate <candidate.result.json> \
  --min-delta 0.12
```

## Rejected Shortcuts

- "Just document that agents should use Seungjeongwon first."
  - Rejected because the observed failure happened despite instruction-level
    guidance.
- "Hard block all writes whenever active context is missing."
  - Rejected because hooks cannot prove intent and this would break normal
    direct work.
- "Move Sejong runtime state into each target repo."
  - Rejected because Sejong state belongs under `${SEJONG_HOME}` unless the user
    explicitly promotes an artifact.
- "Adopt OMX or OMO wholesale."
  - Rejected because the useful pieces are context durability, mismatch
    visibility, and compaction continuity, not a new authority layer.
