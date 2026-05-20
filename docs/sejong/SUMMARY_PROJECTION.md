# Uigwe Summary Projection

**Status:** Draft

## Purpose

The summary projection gives Uigwe a lighter human-facing review surface.

It is derived from the canonical bundle artifacts instead of being authored separately.

That means Uigwe can keep:

- packets
- goal graph
- consumer-ready leaf contracts

while still giving reviewers a shorter view of:

- selected mode
- selected plan
- selected approach
- retained alternatives
- top risks
- leaf summary
- optional harness notes for executor-facing bundles

## Current Implementation Draft

- `scripts/project_summary.py`

## Inputs

Accept either:

- a bundle directory
- a `wrapper.result.json` path

## Outputs

When `--write` is used, the projector writes:

- `planning-summary.json`
- `planning-summary.md`

into the bundle directory.

## Example

```bash
python3 docs/sejong/scripts/project_summary.py docs/sejong/examples/brownfield-decompose-only --write
```

## Why It Matters

Planning bundles can be strong for machines and still feel heavy for quick human review.

This projection reduces review overhead without weakening the underlying contract.

## Optional Harness Notes

When a bundle is meant for executor handoff, the projection may include a compact `Harness Notes` section derived from the canonical artifacts.

Keep it short. It should expose only:

- context map: the files, docs, commands, logs, UI surfaces, or runtime state the executor should inspect first
- proof sources: the commands or observable evidence that prove completion
- failure evidence: what to capture if execution fails and needs Uigwe re-entry
- overhead note: whether the harness details are materially longer than the baseline summary

Do not use `Harness Notes` to repeat the whole plan, introduce a new packet type, or bypass the canonical leaf contracts.
