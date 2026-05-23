# Sejong Validation Examples

This folder contains frozen benchmark inputs and scorecard templates for validating Uigwe and the broader King Sejong surface.

Use these artifacts to compare:

- `baseline-lightweight`
- `baseline-structured`
- `uigwe`
- `sejong-uigwe`
- `sejong-surface`

The deterministic instruction-surface benchmark can be run with:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
```

The deterministic Sejong surface seed benchmark can be run with:

```bash
python3 docs/sejong/scripts/benchmark_sejong_surface.py --require-targets
```

The broader planning and Sejong surface task sets are intentionally runner-agnostic. Fill scorecards after each baseline, Uigwe, or Sejong run, then compare aggregate metrics, scenario-level failure notes, and `resource_usage` deltas.
