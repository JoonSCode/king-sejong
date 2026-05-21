# Uigwe Validation Examples

This folder contains frozen benchmark inputs and scorecard templates for validating Uigwe.

Use these artifacts to compare:

- `baseline-lightweight`
- `baseline-structured`
- `uigwe`
- `sejong-uigwe`

The deterministic instruction-surface benchmark can be run with:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
```

The broader planning task set is intentionally runner-agnostic. Fill scorecards after each baseline or Uigwe run, then compare aggregate metrics and scenario-level failure notes.
