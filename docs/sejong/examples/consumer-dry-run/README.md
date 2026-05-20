# Consumer Dry-Run Example

This folder contains the minimal scaffold for recording limited Codex consumer dry-run results over Uigwe leaves.

## Included Files

- `consumer-dry-run.result.schema.json`
  - the wrapper result schema for a small, explicit leaf subset
- `consumer-dry-run.result.template.json`
  - a blank run template to copy before recording a real dry run
- `consumer-dry-run.result.example.json`
  - a populated example that shows how to wrap `codex-consumer-feedback`

## Usage

1. Select a small set of `executable_leaf` nodes.
2. Fill in the template with run metadata and the selected node IDs.
3. Embed the Codex consumer feedback object from the dry run.
4. Keep the run limited so it remains a small contract exercise, not a broad readiness claim.

## Source Of Truth

The leaf-level execution record remains the nested consumer feedback object:

- `docs/sejong/codex-consumer-feedback.schema.json`
