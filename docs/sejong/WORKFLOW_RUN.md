# Workflow Run Contract

**Status:** Draft

## Purpose

`workflow-run` is the evidence contract for trying dynamic workflow ideas inside
King Sejong without giving those ideas court authority.

It exists for cases where a workflow-like tactic may help:

- deep-research-style evidence gathering
- many-agent review or verification
- ultracode-style parallel execution experiments
- TeamExecutor or host-native team backends
- mocked or shadowed dynamic workflow concepts

The contract does not call Claude CLI, Claude API, or an external Claude
workflow runtime. It records a Codex-native, host-native, TeamExecutor, manual
shadow, or approved mock run so Sejong can decide whether the result is good
enough to keep shadowing, reject, or promote.

## Court Mapping

Workflow runs are subordinate to Sejong court modes:

- `JangYeongsil` owns research evidence and claim separation.
- `Jiphyeonjeon` owns bounded option comparison and challenge rounds.
- `Uigwe` owns the normative contract: goal, non-goals, success criteria,
  verification bar, must-preserve behavior, and re-entry triggers.
- `Seungjeongwon` owns execution tactics, backend use, verification, and
  execution feedback.
- `Sillok` owns durable evidence records when risk or promotion decisions need
  traceability.

A workflow-run artifact is evidence. It is not a Uigwe packet, does not approve
gates, does not vote, and does not replace lead synthesis.

## Lifecycle

New workflow-backed behavior starts in `shadow`.

Recommended lifecycle:

1. Create a workflow-run artifact outside the target repository.
2. Record mapped court surfaces and backend provenance.
3. Add bounded worker lanes only when their scopes are independent.
4. Add evidence ledger entries for sources, cross-checks, findings, discarded
   claims, cost, authority violations, and verification refs.
5. Record baseline-vs-candidate quality comparison.
6. Complete with `promote`, `reject`, or `keep_shadowing`.
7. Run schema, benchmark, comparison, stability, and risk-audit checks.

Use:

```bash
python3 docs/sejong/scripts/sejong_workflow_run.py check --path <workflow-run.json>
```

## Promotion Rules

Promotion requires more than "many agents ran".

A promoted workflow-backed behavior must show:

- no hidden Claude runtime reference
- no worker authority violation
- no live ambiguity bypass
- fresh verification evidence
- `outcome_quality_delta >= 0.10`
- reviewable baseline/candidate refs
- non-empty task-specific acceptance criteria
- matching `quality_comparison.recommendation` and `final_recommendation`
- candidate score `1.0` on the workflow-run benchmark matrix
- comparison delta at least `0.10` over the legacy lightweight baseline
- weighted multi-metric score at least `0.90`
- dimension hard minimums for promotion decision quality, outcome quality,
  efficiency/cost, parallelism, reliability, observability, and human/developer
  experience

`manual_shadow` cannot be promoted directly. If a manual shadow proves useful,
migrate it to a Codex-native, host-native, TeamExecutor, or approved mock backend
before promotion.

`backend=other` must have a specific provenance summary and reviewable command
refs. Self-attested text such as "trust me" is not promotion evidence.

## Validation Commands

Run the main matrix and comparison gates:

```bash
python3 docs/sejong/scripts/benchmark_workflow_run.py
python3 docs/sejong/scripts/benchmark_workflow_run_comparison.py --min-score-delta 0.10 --min-multi-metric-score 0.90
```

Run remaining-risk verification:

```bash
python3 docs/sejong/scripts/benchmark_workflow_run_stability.py --samples 9 --warmups 1 --max-large-ledger-seconds 1.0 --max-p95-seconds 1.0
python3 docs/sejong/scripts/audit_workflow_run_risks.py --repo-root . --artifact <workflow-run.json>
```

Use strict audit for promotion proof over real artifacts:

```bash
python3 docs/sejong/scripts/audit_workflow_run_risks.py \
  --repo-root . \
  --artifact-dir <workflow-run-corpus-dir> \
  --strict-local-refs \
  --min-artifacts 5 \
  --min-workflow-kinds 3 \
  --min-backends 3 \
  --require-promoted
```

## How To Read Results

`benchmark_workflow_run.py` answers whether the validator catches the protected
guardrail scenarios.

`benchmark_workflow_run_comparison.py` answers whether the hardened validator is
meaningfully better than the old lightweight ledger check, and whether it passes
the multi-metric promotion bar.

`benchmark_workflow_run_stability.py` answers whether large-ledger validation is
stable across repeated samples instead of passing once by luck.

`audit_workflow_run_risks.py` answers whether workflow-run artifacts are usable
as evidence. In non-strict mode it can audit shadow examples with symbolic refs.
In strict mode, baseline and candidate refs must resolve to existing local files
or URLs. A shadow example should fail strict promoted proof unless it contains
real promoted evidence.

## Remaining Limits

These gates prove contract behavior, evidence hygiene, and benchmark stability.
They do not prove product success, market impact, or that a workflow will always
beat ordinary execution on every real task.

For product-success claims, use the product evidence gate in
`docs/sejong/VALIDATION.md`. For real workflow promotion, keep a reviewed corpus
of workflow-run artifacts and run strict risk audit before changing defaults.
