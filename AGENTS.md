# AGENTS.md

This repository is both the source repository and the distribution repository for King Sejong.

This file is for agents working on this source repository. It is not part of the installed King Sejong skill contract and must not be copied into target repositories by `scripts/install-sejong.sh`.

## Installed Surface

King Sejong is distributed through these managed paths:

- `.agents/skills/sejong/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `docs/sejong/`

For Codex user-scope installs, those same surfaces are copied under `${CODEX_HOME:-~/.codex}/skills`, with shared docs installed under `skills/sejong/docs/`.

Do not add root-level repository files such as `AGENTS.md` to the managed install surface unless the installer, README files, and verification docs are intentionally updated together.

## Source Of Truth

- Sejong routing: `docs/sejong/ROUTER.md`
- Sejong skill front door: `.agents/skills/sejong/SKILL.md`
- Uigwe planning behavior: `.agents/skills/uigwe/SKILL.md` and `docs/sejong/PROTOCOL.md`
- Execution behavior: `.agents/skills/seungjeongwon/SKILL.md` and `docs/sejong/SEUNGJEONGWON_EXECUTOR.md`
- Prompt overlays: `docs/sejong/PROMPT_OVERLAYS.md`
- Install behavior: `scripts/install-sejong.sh`

## Maintenance Rules

- Keep skill files thin. Put durable contracts in `docs/sejong/`.
- Do not add `.codex/prompts/{role}.md` as a required install surface.
- Do not treat missing repo-local prompt overlays as an install failure.
- Preserve bounded parallelism: subagents may return bounded briefs, but the lead Sejong agent owns synthesis, routing, gates, and final verification.
- When changing Sejong or Uigwe instruction surfaces, run `python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets`.
- Validate JSON contracts and examples before claiming behavior changes are ready.
- Run `bash scripts/install-sejong.sh --verify .` after changing managed install paths or installer behavior.
