# AGENTS.md

This repository is both the source repository and the distribution repository for King Sejong.

This file is for agents working on this source repository. It is not part of the installed King Sejong skill contract and must not be copied into target repositories by `scripts/install-sejong.sh`.

Its primary purpose is development continuity: future coding sessions should be able to recover the project direction, current architecture, and maintenance rules from the repository without the user restating chat context.

## Development Direction

King Sejong is a Codex-native skill and protocol distribution, not a separate runtime that replaces Codex, Claude, shell tools, or user-owned wrappers.

The stable shape is:

- `Sejong` is the broad user-facing front door for routing, decision support, execution, verification, and evidence records.
- `Uigwe` is the formal planning protocol when a direction needs gates, packets, decomposition, or promotion-ready artifacts.
- `Seungjeongwon` is the default execution and verification path for clear tasks.
- `TeamExecutor` is an optional backend for `$team` wrappers that coordinate separate CLI workers in `tmux` panes through Sejong-owned state, mailbox, and lease files.
- Hook guardrails are Codex-native lifecycle checks that inject active King Sejong context, guard protected self-modification paths, and keep subagent or `$team` output bounded. They must not be treated as a complete sandbox. User-scope install uses the marked King Sejong plugin block in `${CODEX_HOME:-~/.codex}/config.toml` as the canonical hook source; the old marked direct hook block is legacy fallback only and must not be enabled alongside the plugin hook.

Keep installed skills thin and keep durable behavior in `docs/sejong/`. Keep this file focused on source-repo maintenance direction for future development sessions, not product-facing explanation.

Do not make King Sejong depend on repo-local or tool-specific orchestration state. `$team` state belongs under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/`.

## Session Resume Protocol

For substantial source-repo work, start by reading this file and then the relevant source-of-truth docs below. Do not rely on chat history alone for project direction.

When the user asks to continue without repeating context, inspect the repository state before asking for clarification:

- `git status --short --branch`
- `git log --oneline -5`
- relevant source-of-truth docs from this file
- recent validation outputs when they are available in the working session

When a decision should survive into later sessions, promote it into `AGENTS.md` or the appropriate `docs/sejong/` contract instead of leaving it only in conversation. If the decision changes installed behavior, update the relevant docs, examples, and validation checks together.

Do not create tracked planning or status artifacts just to preserve a local working session unless the user asks for a shareable artifact. Temporary Sejong runtime state belongs outside the target repository under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`.

When handing off incomplete work, leave exact next files, commands, and validation state in the final response or commit message so another session can continue without reconstructing intent.

## Installed Surface

King Sejong is distributed through these managed paths:

- `.agents/skills/sejong/`
- `.agents/skills/jangyeongsil/`
- `.agents/skills/jiphyeonjeon/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `.agents/skills/why-gate/`
- `plugins/king-sejong/`
- `.agents/plugins/marketplace.json`
- `docs/sejong/`

For Codex user-scope installs, those same surfaces are copied under `${CODEX_HOME:-~/.codex}/skills`, with shared docs installed under `skills/sejong/docs/`.
The Codex plugin adapter is copied under `${CODEX_HOME:-~/.codex}/plugins/cache/king-sejong-local/king-sejong/0.1.0/` and enabled through a marked King Sejong plugin block in `${CODEX_HOME:-~/.codex}/config.toml`.
The plugin is a discovery and hook-metadata adapter; it must not become the source of truth for runtime behavior, durable docs, active context, or verification contracts.

Do not add root-level repository files such as `AGENTS.md` to the managed install surface unless the installer, README files, and verification docs are intentionally updated together.

## Source Of Truth

- Sejong routing: `docs/sejong/ROUTER.md`
- Sejong skill front door: `.agents/skills/sejong/SKILL.md`
- JangYeongsil research front door: `.agents/skills/jangyeongsil/SKILL.md`
- Jiphyeonjeon discussion front door: `.agents/skills/jiphyeonjeon/SKILL.md`
- Uigwe planning behavior: `.agents/skills/uigwe/SKILL.md` and `docs/sejong/PROTOCOL.md`
- Execution behavior: `.agents/skills/seungjeongwon/SKILL.md` and `docs/sejong/SEUNGJEONGWON_EXECUTOR.md`
- Rationale checkpoints: `.agents/skills/why-gate/SKILL.md` and `docs/sejong/DISCIPLINE_GATES.md`
- TeamExecutor behavior: `docs/sejong/TEAM_EXECUTOR.md` and `docs/sejong/scripts/team_executor.py`
- Live ambiguity clarification: `docs/sejong/AMBIGUITY_REGISTER.md` and `docs/sejong/ambiguity-register.schema.json`
- Runtime artifact storage: `docs/sejong/ARTIFACT_STORAGE.md`
- Hook guardrails: `docs/sejong/HOOKS.md` and `docs/sejong/scripts/king_sejong_hooks.py`
- Active context checkpoints: `docs/sejong/king-sejong-context.schema.json`
- Sillok trace and security guardrails: `docs/sejong/SILLOK_TRACE.md`, `docs/sejong/SECURITY.md`, and `docs/sejong/scripts/sillok_trace.py`
- Prompt overlays: `docs/sejong/PROMPT_OVERLAYS.md`
- Install behavior: `scripts/install-sejong.sh`
- Codex plugin adapter: `plugins/king-sejong/.codex-plugin/plugin.json` and `plugins/king-sejong/hooks/hooks.json`

## Maintenance Rules

- Keep skill files thin. Put durable contracts in `docs/sejong/`.
- Keep `AGENTS.md` source-only. Promote installed behavior to `docs/sejong/` and the relevant skill front door.
- Do not add `.codex/prompts/{role}.md` as a required install surface.
- Do not treat missing repo-local prompt overlays as an install failure.
- Do not reintroduce repo-local or tool-specific orchestration state as a Sejong dependency.
- Keep the Codex plugin adapter thin. It may expose hook metadata and marketplace packaging, but installer-owned user-scope skills and `docs/sejong/` remain the durable contract. Do not expose duplicate plugin-scoped Sejong skills when canonical user-scope skills are installed.
- Keep auxiliary King Sejong skills such as `why-gate` on the managed user-scope skill surface, not as plugin-scoped duplicate skills.
- Preserve bounded parallelism: subagents and `$team` workers may return bounded briefs, mailbox messages, implementation slices, or verification evidence, but the lead Sejong agent owns synthesis, routing, gates, and final verification.
- Prefer officially supported host team or teammate messaging when it exists and a bounded Jiphyeonjeon or JangYeongsil round needs peer challenge; otherwise use Sejong TeamExecutor mailbox state. Peer messages are worker evidence, not court-mode authority.
- Keep TeamExecutor mailbox traffic on the versioned `send-message` / `receive-messages` envelope; raw mailbox appends are compatibility-only and must not become the primary worker contract.
- Keep hook behavior test-first: add or update red fixtures before changing hook, active-context, or TeamExecutor authority behavior, then run the hook, TeamExecutor, and E2E guardrail tests.
- Keep Sillok/security behavior test-first: update trace schemas, examples, and `test_sillok_trace.py` when changing risk flags or approval rules.
- When changing Sejong or Uigwe instruction surfaces, run `python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets`.
- Validate JSON contracts and examples before claiming behavior changes are ready.
- Run `bash scripts/install-sejong.sh --verify .` after changing managed install paths or installer behavior.
