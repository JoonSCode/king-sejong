# Sejong Hook Context Lifecycle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the approved A-first and C-ready King Sejong hook/context lifecycle fix.

**Architecture:** Keep the plugin hook as the canonical user-scope hook adapter and migrate older direct config hook blocks away by default. Narrow Stop receipt enforcement so it is driven by explicit pending gates or live execution artifacts, while leaving a documented path toward stronger repo/session-scoped context isolation.

**Tech Stack:** Bash installer, Python hook guardrails, Python unittest, TOML text-block migration, JSON runtime context fixtures.

---

### Task 1: Capture Design And Execution Receipt

**Files:**
- Create: `docs/plans/2026-06-01-sejong-hook-context-lifecycle-design.md`
- Create: `docs/plans/2026-06-01-sejong-hook-context-lifecycle.md`
- Runtime: `${SEJONG_HOME:-~/.codex/sejong}/runs/king-sejong/hook-context-lifecycle-2026-06-01/seungjeongwon-run.json`

**Step 1: Confirm design doc exists**

Run:

```bash
test -f docs/plans/2026-06-01-sejong-hook-context-lifecycle-design.md
```

Expected: exit code 0.

**Step 2: Confirm the implementation plan exists**

Run:

```bash
test -f docs/plans/2026-06-01-sejong-hook-context-lifecycle.md
```

Expected: exit code 0.

**Step 3: Record Seungjeongwon attempt evidence**

Use `seungjeongwon_run.py record-attempt` for todo `T1`, then complete todo `T1`.

Expected: run artifact validates with `seungjeongwon_run.py check`.

### Task 2: Write Failing Stop-Receipt Tests

**Files:**
- Modify: `docs/sejong/scripts/test_king_sejong_hooks.py`
- Test: `docs/sejong/scripts/test_king_sejong_hooks.py`

**Step 1: Add a regression test for route-only receipt enforcement**

Add a test that builds a valid context with:

```python
"required_route_sequence": ["jiphyeonjeon", "uigwe", "seungjeongwon"],
"route_sequence": ["sejong", "jiphyeonjeon", "uigwe", "seungjeongwon"],
"pending_gates": [],
"artifact_refs": [],
```

Call `dispatch("Stop", {}, context)`.

Expected future result:

```python
assert result == {}
```

Current expected red result: it returns a block reason containing `seungjeongwon_receipt_required`.

**Step 2: Add a test for explicit receipt gate blocking**

Use the same context but with:

```python
"pending_gates": ["seungjeongwon_receipt_required"]
```

Expected:

```python
assert result["decision"] == "block"
assert "seungjeongwon_receipt_required" in result["reason"]
```

**Step 3: Run focused tests**

Run:

```bash
python3 -m unittest docs.sejong.scripts.test_king_sejong_hooks -v
```

Expected: the route-only test fails before implementation.

### Task 3: Implement Stop-Receipt Predicate Narrowing

**Files:**
- Modify: `docs/sejong/scripts/king_sejong_hooks.py`
- Test: `docs/sejong/scripts/test_king_sejong_hooks.py`

**Step 1: Replace route-sequence-only receipt requirement**

Change `pending_seungjeongwon_receipt_unsatisfied` so route history alone does not require a receipt.

The predicate should be equivalent to:

```python
def pending_seungjeongwon_receipt_unsatisfied(context):
    return has_pending_seungjeongwon_receipt(context) and not has_valid_seungjeongwon_receipt(context)
```

Keep active run blocking in `handle_stop`, because active run artifacts are checked later by `active_seungjeongwon_run_summaries`.

**Step 2: Run focused tests**

Run:

```bash
python3 -m unittest docs.sejong.scripts.test_king_sejong_hooks -v
```

Expected: Stop receipt tests pass.

### Task 4: Add Installer Duplicate-Hook Detection

**Files:**
- Modify: `scripts/install-sejong.sh`
- Modify or create tests under the existing installer test location.

**Step 1: Locate existing installer tests**

Run:

```bash
rg -n "install-sejong|King Sejong hooks|King Sejong plugin|config.toml" .
```

Expected: identify the existing shell or Python test surface for installer behavior.

**Step 2: Add red duplicate-hook verification test**

Create a fixture config containing both:

```toml
# BEGIN King Sejong hooks
...
# END King Sejong hooks

# BEGIN King Sejong plugin
...
[plugins."king-sejong@king-sejong-local"]
enabled = true
...
# END King Sejong plugin
```

Expected future result: verifier reports duplicate hook registration or fails install verification.

**Step 3: Implement migration/verification logic**

Add installer behavior that:

- Removes the managed direct hook block by default when enabling the plugin hook.
- Allows direct hooks only in an explicit legacy mode.
- Fails `--verify` if both active direct hooks and plugin hooks are present.

**Step 4: Run focused installer tests**

Run the identified test command. If there is no dedicated installer test yet, add one and run it directly.

Expected: duplicate-hook fixture fails before implementation and passes after implementation.

### Task 5: C-Ready Context Scope Tests

**Files:**
- Modify: `docs/sejong/scripts/test_king_sejong_hooks.py`
- Optional docs update: `docs/sejong/HOOKS.md`

**Step 1: Add context mismatch no-op coverage**

Build a context whose `repo_root` differs from payload `cwd`. For `Stop`, expect no block.

Expected:

```python
assert dispatch("Stop", {"cwd": "/tmp/other"}, context) == {}
```

This documents that stale context should not complete-block unrelated work.

**Step 2: Add future-field documentation**

Document that future C-level work should add `status`, `scope_kind`, and `intent_scope` before removing global fallback behavior.

### Task 6: Verification And Commit

**Files:**
- All changed files.

**Step 1: Run focused tests**

Run:

```bash
python3 -m unittest docs.sejong.scripts.test_king_sejong_hooks -v
```

Expected: pass.

**Step 2: Run broader validation**

Run as feasible:

```bash
python3 -m unittest discover -s docs/sejong/scripts -p 'test_*.py' -v
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/validate_json_contracts.py
bash scripts/install-sejong.sh --verify .
```

Expected: pass or record exact blocker.

**Step 3: Complete Seungjeongwon run artifact**

Record attempts for completed tasks, complete all todos, and mark the runtime run completed with verification evidence.

**Step 4: Commit**

Run:

```bash
git status --short
git add docs/plans docs/sejong scripts
git commit -m "fix(sejong): canonicalize hooks and narrow receipt gate"
```

Expected: commit succeeds if the user wants this work committed in the current branch.
