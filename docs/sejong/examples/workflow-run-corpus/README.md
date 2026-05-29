# Workflow Run Promotion Corpus

This corpus is the source-repository promotion proof for the workflow-run
evidence gate. It records the user's explicit promotion request and keeps the
promotion bounded to Codex-owned, host-native, TeamExecutor, or mocked workflow
backends under Sejong authority.

It does not promote external Claude runtimes, worker majority decisions,
unreviewed manual shadows, or arbitrary workflow scripts. Those still need a
separate workflow-run artifact and the same promotion gates.

Validate the corpus with:

```bash
python3 docs/sejong/scripts/audit_workflow_run_risks.py \
  --repo-root . \
  --artifact-dir docs/sejong/examples/workflow-run-corpus \
  --strict-local-refs \
  --min-artifacts 5 \
  --min-workflow-kinds 3 \
  --min-backends 3 \
  --require-promoted
```
