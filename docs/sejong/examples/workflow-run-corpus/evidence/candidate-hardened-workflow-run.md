# Candidate: Hardened Workflow Run Gate

The candidate is the promoted workflow-run evidence gate implemented by
`docs/sejong/scripts/sejong_workflow_run.py`, the benchmark matrix, the
comparison benchmark, the stability benchmark, and the risk audit.

Current verification output:

```text
workflow_run_benchmark ok: cases=18/18 performance=0.006551s/1.0s workers=1000 evidence=2000
workflow_run_comparison ok: baseline=0.3409 candidate=1.0 delta=0.6591 min_delta=0.1 multi=0.982 min_multi=0.9
workflow_run_stability ok: samples=9 failures=0 candidate_p95=0.010107s candidate_max=0.010107s
```

The promoted behavior is the evidence gate itself: workflow-backed tactics may
advance from shadow only when they preserve Sejong authority, use reviewable
baseline and candidate evidence, pass promotion approval, and satisfy the
strict corpus audit.
