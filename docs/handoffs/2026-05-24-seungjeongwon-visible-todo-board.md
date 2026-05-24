# Handoff: Seungjeongwon Visible Todo Board Follow-up

Date: 2026-05-24

## Current State

This handoff continues the King Sejong source-repo work that made Seungjeongwon execution more visible to the user through Codex todo/update_plan.

The active source changes cover two related contract areas:

- Seungjeongwon visible execution board: actionable leaves should be published through Codex todo tooling before implementation, and material execution reshaping should append explicit redefinition and replacement todos rather than silently rewriting the board.
- Cross-stage helper calls: JangYeongsil and Jiphyeonjeon can be bounded helper calls inside another active court mode, but they return evidence or decision notes to the caller and must not approve Uigwe gates, finalize packets, claim consensus, or override lead synthesis.

The Tagback experiment used only to exercise the visible todo flow was intentionally deleted at the user's request. Do not continue that Tagback price-CTA experiment unless the user explicitly restarts it.

## Files Changed In This Work

Expected King Sejong source changes include:

- `.agents/skills/sejong/SKILL.md`
- `.agents/skills/uigwe/SKILL.md`
- `.agents/skills/seungjeongwon/SKILL.md`
- `docs/sejong/ROUTER.md`
- `docs/sejong/PROTOCOL.md`
- `docs/sejong/README.md`
- `docs/sejong/TEAM_EXECUTOR.md`
- `docs/sejong/SEUNGJEONGWON_EXECUTOR.md`
- `docs/sejong/examples/validation/uigwe-instruction-surface-task-set.json`
- `docs/sejong/scripts/benchmark_instruction_surface.py`
- regenerated `docs/sejong/examples/validation/runs/uigwe-instruction-surface.scorecard.*`

This handoff document is source-repo only and is intentionally outside `docs/sejong/`, so it is not part of the managed King Sejong install surface.

## Verification State

Before handoff, rerun and confirm:

```bash
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/validate_json_contracts.py
bash scripts/install-sejong.sh --verify .
bash scripts/install-sejong.sh --scope user --force
bash scripts/install-sejong.sh --scope user --verify
git diff --check
```

Expected benchmark result after the cross-stage helper-call scenario is included: `15/0` pass.

## Next Session Targets

1. Decide whether the visible todo board needs a machine-readable execution-feedback field such as `visible_todo_events`.
2. Add a concrete example or fixture showing `T2 -> R1 -> T2a/T2b` redefinition semantics if the contract should be testable beyond instruction-surface text.
3. Consider whether TeamExecutor helper-call examples need positive and negative fixtures for helper mode `current_surface` and source-of-truth handback.
4. Keep runtime evidence and session artifacts outside the repo unless the user explicitly asks for another shareable handoff.

## Cleanup Already Done

- Removed `/Users/junsu/Develop/Tagback-settings-price-cta`.
- Deleted local branch `codex/tagback-settings-price-cta`.
- Left `/Users/junsu/Develop/Tagback` unchanged except for its pre-existing state: `main...origin/main [behind 1]` with untracked `.agents/` and `docs/sejong/`.
