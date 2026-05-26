# Sejong Outcome Evaluation

**Status:** Draft

## Purpose

King Sejong needs to prove more than "the requested behavior fired." For outcome work, the question is whether the final artifact is better against the user's goal.

This document defines the first deterministic outcome-quality harness. It is intentionally small and auditable: task-specific JSON checks score a baseline and candidate artifact against the same dimensions.

## Research Basis

Recent agent-eval guidance converges on the same shape:

- OpenAI's eval guidance frames evals as structured tests for model applications and recommends explicit test data, criteria, and analysis loops.
- OpenAI graders return numeric scores, support partial credit, and can combine checks.
- OpenAI trace grading evaluates full agent traces to locate where behavior succeeded or failed, not only the final response.
- Anthropic's agent-evals guidance separates deterministic, model-based, and human graders; deterministic graders are preferred where possible, while subjective work needs calibrated human or model review.
- Karpathy's Software 3.0 framing is useful as a direction of travel: intent, context, tools, and verification become the programming surface. It is not a substitute for repo-local pass criteria.

References:

- <https://developers.openai.com/api/docs/guides/evaluation-best-practices>
- <https://developers.openai.com/api/docs/guides/evals>
- <https://developers.openai.com/api/docs/guides/graders>
- <https://developers.openai.com/api/docs/guides/trace-grading>
- <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>
- <https://www.youtube.com/watch?v=LCEmiRjPEtQ>

## What This Harness Proves

The deterministic harness proves that a candidate result artifact is more complete against a declared rubric than a baseline result artifact.

It does not prove:

- that the real product succeeded
- that marketing improved real acquisition
- that a model will always generate the candidate artifact
- that human review is unnecessary

For product and marketing work, treat this as a pre-launch quality gate before real analytics, user interviews, A/B tests, or production monitoring.

Use [product_evidence_gate.py](scripts/product_evidence_gate.py) for that field-validation layer. The outcome-quality evaluator can promote a better strategy artifact, but `product_evidence_gate.py` is the gate that decides whether external analytics, controlled-experiment, and user-research evidence support a product-success claim.

## Artifact Formats

Task file:

```json
{
  "format": "sejong.outcome-quality-task/v0.1-draft",
  "task_id": "tagback-growth",
  "prompt": "...",
  "goal": "...",
  "min_promote_delta": 0.12,
  "required_dimensions": [
    {
      "id": "causal_diagnosis",
      "weight": 1.2,
      "checks": ["root_causes", "why_now", "rejected_hypotheses"]
    }
  ]
}
```

Result file:

```json
{
  "format": "sejong.outcome-quality-result/v0.1-draft",
  "run_id": "candidate-runtime-contracts",
  "label": "candidate",
  "summary": "...",
  "dimensions": {
    "causal_diagnosis": {
      "root_causes": ["..."],
      "why_now": ["..."],
      "rejected_hypotheses": ["..."]
    }
  }
}
```

Comparison output:

```bash
python3 docs/sejong/scripts/outcome_quality_evaluator.py compare \
  --task docs/sejong/examples/outcome-evaluation/tagback-growth/task.json \
  --baseline docs/sejong/examples/outcome-evaluation/tagback-growth/baseline-current-sot.result.json \
  --candidate docs/sejong/examples/outcome-evaluation/tagback-growth/candidate-runtime-contracts.result.json \
  --min-delta 0.12
```

## TagBack Growth Scenario

The seed scenario asks:

```text
TagBack 앱을 성공시키려면 어떻게 해야 하는지, 특히 마케팅이라면 방법, 이유, 원인 분석, 계획까지 제시한다.
```

The rubric scores:

- causal diagnosis
- audience and job-to-be-done clarity
- marketing strategy
- experiment prioritization
- instrumentation
- Codex-owned vs user-owned action split
- risk controls
- evidence quality
- actionable plan

This shape directly tests the user's requirement: a better answer should explain causes, reasons, marketing method, and a plan with measurable execution, not only produce a plausible checklist.

The same scenario also includes a field-validation plan:

```bash
python3 docs/sejong/scripts/product_evidence_gate.py check-plan \
  --plan docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-plan.json
python3 docs/sejong/scripts/product_evidence_gate.py judge-result \
  --plan docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-plan.json \
  --result docs/sejong/examples/outcome-evaluation/tagback-growth/field-validation-result.example.json \
  --require-success
```

The plan requires analytics evidence, a controlled experiment, and user research. The bundled result is an example fixture, not a claim about real TagBack performance.

## Promotion Rule

Promote a candidate only when:

- same task prompt
- same available evidence
- same scoring rubric
- candidate score exceeds baseline by at least `min_promote_delta`
- no protected dimension regresses in a way that undermines the goal
- the result still names real-world validation needed after the agent artifact

If the candidate improves contract behavior but not artifact quality, keep it shadowed.

If the candidate improves artifact quality but lacks external product evidence, do not claim product success. Promote only the strategy artifact and proceed to field validation.
