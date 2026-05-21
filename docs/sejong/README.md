# Sejong + Uigwe

Sejong is the all-in-one user-facing front door for broad agent work.
It can research, decide, plan, execute, verify, and record evidence instead of forcing every request through formal planning.

Use `sejong` when the request is broad and the agent should choose whether to research, decide, plan, execute, verify, or record evidence.

Uigwe is the formal planning protocol inside Sejong. Use it when the output should be a durable planning bundle with packets, rationale, and executable leaves.
In live chat usage, Uigwe is supposed to do that interactively.
Progress should be presented as approximate readiness such as `기획 준비도 68%`, paired with the main weak areas.

## Installed Layout

The installer can copy this contract surface into either a target repository or a Codex user skill directory.

Repo scope:

- `.agents/skills/sejong/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `docs/sejong/`

User scope under `${CODEX_HOME:-~/.codex}/skills`:

- `sejong/`
- `uigwe/`
- `seungjeongwon/`

In user scope, this docs tree is installed under `skills/sejong/docs/`, and the installed skill files are rewritten to load contracts from that user-scope docs copy.

The skill files stay short by design. They load the detailed contracts from the installed Sejong docs only when needed.

## Start Here

For normal use:

1. Read [ROUTER.md](ROUTER.md) to understand Sejong's lanes.
2. Read [PROTOCOL.md](PROTOCOL.md) to understand Uigwe's planning model.
3. Read [WRAPPER.md](WRAPPER.md) if you want machine-consumable packet flow.
4. Read [PROMPT_OVERLAYS.md](PROMPT_OVERLAYS.md) if you want repo-local role prompt overlays.
5. Read [SEUNGJEONGWON_EXECUTOR.md](SEUNGJEONGWON_EXECUTOR.md) if you want to execute and verify a validated plan.
6. Read [VALIDATION.md](VALIDATION.md) if you are changing Uigwe or Sejong behavior and need benchmark gates.

## Practical Usage

Use Sejong when the correct workflow is still uncertain:

```text
$sejong investigate the history and tell me the next decision
$sejong compare these options and recommend a path
$sejong this approved design should become executable work
$sejong research the problem, plan the fix, implement it, and verify it
```

For larger Sejong work, parallelism is allowed when it is genuinely separable:

- `JangYeongsil` can fan out across independent evidence sources and fan in to one `known` / `inferred` / `unknown` synthesis.
- `Jiphyeonjeon` can run bounded council briefs in parallel, such as advocate, critic, specialist, operator, and risk reviewer. The agents do not vote; the lead Sejong agent synthesizes the recommendation.
- `Uigwe` can overlap only through preflight checks such as artifact inventory, readiness review, or validation planning. Formal packets and live-session gates remain lead/user-owned.
- Execution parallelism belongs in `Seungjeongwon` after scope approval, with disjoint file scopes or test surfaces.

Sejong does not require `.codex/prompts/{role}.md`. If a target repo has such a file, treat it as a repo-local overlay on top of the Codex native role prompt. If it is absent, continue with the native role prompt. See [PROMPT_OVERLAYS.md](PROMPT_OVERLAYS.md).

Use Uigwe directly when you already want formal planning:

```text
$uigwe full <brief>
$uigwe design-to-plan <clear intent or feature brief>
$uigwe decompose-only <approved design artifact>
```

Use Seungjeongwon directly when the scope is approved and execution should start:

```text
$seungjeongwon execute this validated Uigwe bundle and verify the result
$seungjeongwon finish these executable leaves from docs/sejong/examples/brownfield-decompose-only
```

## What Uigwe Produces

Depending on mode, Uigwe produces:

- `Intent Packet`
- `Design Packet`
- `Plan Packet`
- `spec.md`
- `rationale.md`
- `goal-tree.json`

These artifacts are meant for both human review and downstream machine consumption.

## Validation Helpers

This public package includes schema checks, bundle validation, frozen benchmark scaffolds, and an instruction-surface guardrail runner. It intentionally does not ship private benchmark runs or score histories.

Useful commands:

```bash
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
python3 docs/sejong/scripts/project_summary.py docs/sejong/examples/greenfield-full-flow --write
```
