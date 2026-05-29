# Baseline: Legacy Lightweight Ledger

The baseline is the legacy lightweight workflow validation path used by
`docs/sejong/scripts/benchmark_workflow_run_comparison.py`.

Current verification output:

```text
workflow_run_comparison ok: baseline=0.3409 candidate=1.0 delta=0.6591 min_delta=0.1 multi=0.982 min_multi=0.9
```

This baseline is reviewable but insufficient for promoted workflow-backed
behavior because it does not enforce all authority, provenance, promotion
approval, multi-metric, and strict evidence gates.
