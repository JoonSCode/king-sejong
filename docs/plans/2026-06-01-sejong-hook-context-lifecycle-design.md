# Sejong Hook And Context Lifecycle Design

Date: 2026-06-01

## Goal

Fix the current King Sejong hook behavior so user-scope installs do not double-inject hook prompts, stale active contexts do not leak into unrelated work, and Seungjeongwon receipt enforcement applies only to real execution workflows.

## Current Problem

The current installed user state showed two separate failures:

- The same King Sejong hooks were registered through both the managed `~/.codex/config.toml` hook block and the `king-sejong-local` plugin `hooks.json`.
- A stale `ctx-king-sejong-user-install` context for `/Users/junsu/Develop/king-sejong` kept requiring a Seungjeongwon receipt during unrelated analysis and design replies.

The repeated Stop hook prompts were a direct symptom of both issues: duplicated hook registration made the prompt appear twice, and the receipt predicate treated `required_route_sequence` containing `seungjeongwon` as sufficient reason to block completion even when no explicit receipt gate was pending.

## Comparable Host-Surface Patterns

External workflow tools commonly separate installation surfaces by host:

- Codex uses native skill discovery through user-scope skill directories.
- Legacy Codex bootstrap blocks are removed during migration.
- Claude/OpenCode plugin hooks stay narrow and bootstrap only the workflow discipline.
- Tests use isolated homes and explicit skill-trigger fixtures to catch regressions without depending on the maintainer's local state.

The useful pattern for Sejong is not to copy another workflow, but to copy the ownership boundary: one canonical injection path per host, explicit migration from legacy paths, and isolated verification of install state.

## Decision

Use an A-first, C-ready design.

### A: Plugin Hook Canonicalization

Make the Codex plugin hook the canonical user-scope hook surface. Keep the plugin hook as a thin adapter that delegates to the installed user-scope `skills/sejong/docs/scripts/king_sejong_hooks.py` script.

During user-scope install/update:

- Install and enable the local King Sejong plugin.
- Remove the legacy managed direct hook block from `~/.codex/config.toml` by default.
- Keep direct hook installation only behind an explicit legacy flag or when plugin installation is unavailable.
- Make `--verify` fail when both direct King Sejong hooks and plugin King Sejong hooks are active.

### C-Ready: Scoped Context Lifecycle

Do not fully replace the context model in this patch. Add guardrails that make the future strong isolation model straightforward:

- Treat stale or mismatched repo context as non-applicable, not as a global workflow requirement.
- Prepare docs and tests around context status and scope fields such as `status`, `scope_kind`, `repo_root`, and `intent_scope`.
- Avoid relying on a single global active context as the only durable state lookup path.

## Receipt Enforcement

Receipt enforcement should block completion only when there is an explicit execution obligation.

The Stop hook should require a valid Seungjeongwon receipt when one of these is true:

- `pending_gates` contains `seungjeongwon_receipt_required`.
- A referenced Seungjeongwon run artifact exists and is still active.
- A future context status/scope field marks the current workflow as execution-bound and incomplete.

The Stop hook should not block merely because `required_route_sequence` includes `seungjeongwon`. That field records the route contract, not final completion evidence by itself.

Read-only analysis, research-only answers, advice-only comparisons, and design planning must be able to finish without a Seungjeongwon receipt unless the context explicitly carries the receipt gate.

## Migration Behavior

The installer should support three user states:

1. New install with no King Sejong hooks:
   Install plugin hook only.

2. Existing install with direct hooks only:
   Install plugin hook, remove the legacy direct hook block, and verify only one hook source remains.

3. Maintainer or recovery install needing direct hooks:
   Allow an explicit legacy/direct-hook mode, but verify that plugin hooks are not simultaneously enabled.

This keeps normal users on one path while preserving a controlled escape hatch.

## Validation

Add or update tests for:

- Fresh user-scope install produces one canonical hook source.
- Updating an older direct-hook install removes or disables the legacy block.
- `--verify` fails on duplicated direct plus plugin hooks.
- Stop does not block when only `required_route_sequence` contains `seungjeongwon`.
- Stop blocks when `pending_gates` explicitly contains `seungjeongwon_receipt_required`.
- Repo-mismatched context is not applied to unrelated work.

Run the existing Sejong validation bundle after implementation:

```bash
python3 -m unittest discover -s docs/sejong/scripts -p 'test_*.py' -v
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/validate_json_contracts.py
bash scripts/install-sejong.sh --verify .
```

If managed install paths or user-scope installer behavior changes, also run a user-scope install/verify pass in an isolated temporary home or a controlled local user-scope check.
