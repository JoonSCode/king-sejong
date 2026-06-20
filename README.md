![King Sejong banner](docs/sejong/assets/king-sejong-banner.png)

# King Sejong

[Korean, Joseon-style](README.ko.md)

King Sejong gives **Codex** a disciplined workflow for work that should not stop at "analysis".

It is designed for maintainers who use Codex on real repositories: pull request review, issue triage, release preparation, installer checks, security guardrails, documentation consistency, and other open-source maintenance workflows where an agent should gather evidence before it edits.

It gives an agent one broad front door, `$sejong`, for moving from research to decision, planning, execution, verification, and evidence recording. Follow-up turns stay in that active Sejong workflow until the user explicitly exits it or switches to another non-Sejong workflow.

Use it when a request starts vague, touches several files or decisions, or needs proof that the agent actually finished the outcome. King Sejong is a skill bundle and protocol surface, not a replacement runtime: Codex still owns the model loop, tools, shell, files, and approvals; King Sejong owns routing, gates, handoffs, verification shape, and evidence records.

## Why Use It

- Turn broad requests into a concrete path instead of forcing every job into one planning mode.
- Keep research, discussion, planning, execution, and verification connected across follow-up turns.
- Use Uigwe only when a durable planning bundle is worth the overhead.
- Hand approved work to Seungjeongwon for execution, verification, retry, and evidence.
- Make large or parallel attempts auditable with discipline gates, outcome checks, and workflow-run evidence instead of treating worker agreement as proof.
- Keep temporary research, planning, runtime, and evidence artifacts outside the target repository unless the user explicitly promotes them, then compact and prune them by policy.
- Install once per repo or once into `${CODEX_HOME:-~/.codex}/skills` for workspace-wide Codex use.

## When To Use It

| If the work needs... | Start with... | What happens |
| --- | --- | --- |
| Evidence before deciding | `$sejong` or `$jangyeongsil` | Facts, inferences, unknowns, and the next decision are separated. |
| A recommendation between real options | `$sejong` or `$jiphyeonjeon` | Trade-offs, rejected paths, risks, and a next-surface recommendation are synthesized. |
| A durable plan | `$sejong` or `$uigwe` | Uigwe produces planning artifacts and handoff leaves tied to success criteria. |
| Implementation with proof | `$sejong` or `$seungjeongwon` | The executor decomposes the scope, makes changes, verifies them, and reports evidence. |
| A large or parallel workflow experiment | `$sejong` | Worker output stays subordinate while workflow-run and outcome evidence decide whether the tactic is worth keeping. |
| A small exact task | `$sejong` | Sejong can act directly and report the completed work plus verification. |

By default, Sejong keeps research, planning, runtime, and evidence artifacts outside the target repository under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`. It does not create git-tracked planning files unless the user explicitly asks to promote a shareable artifact into the repo.

Completed runs should not keep raw runtime files forever. King Sejong can compact a run into `run-summary.json` plus Sillok evidence, then prune raw artifacts with a dry-run-first cleanup helper.

## Maintainer Workflows

King Sejong is early, but it is built around repeatable maintainer work rather than a demo-only agent loop:

- review a change with evidence, rationale, and verification expectations before editing
- triage issues into research, decision, planning, execution, or rejected-option paths
- turn approved designs into executable leaves with Seungjeongwon verification
- validate install surfaces, hooks, schemas, examples, and instruction contracts before release
- keep runtime artifacts outside the target repository unless a maintainer asks to promote a tracked record

See [OSS maintainer workflows](docs/sejong/OSS_MAINTAINER_WORKFLOWS.md) for concrete examples.

## Naming

Use **Sejong**.

Do not write `SeJong`. The conventional romanization is `Sejong`, as in `King Sejong`.

Recommended names:

- Human-facing product name: `King Sejong`
- Skill name: `sejong`
- Invocation: `$sejong`
- Repository slug: `king-sejong`

## Quick Install

For the current repository:

```bash
tmp=$(mktemp -d)
git clone --depth 1 https://github.com/JoonSCode/king-sejong.git "$tmp/king-sejong"
bash "$tmp/king-sejong/scripts/install-sejong.sh" "$PWD"
bash "$tmp/king-sejong/scripts/install-sejong.sh" --verify "$PWD"
rm -rf "$tmp"
```

For Codex user scope, available from any workspace:

```bash
tmp=$(mktemp -d)
git clone --depth 1 https://github.com/JoonSCode/king-sejong.git "$tmp/king-sejong"
bash "$tmp/king-sejong/scripts/install-sejong.sh" --scope user
bash "$tmp/king-sejong/scripts/install-sejong.sh" --scope user --verify
rm -rf "$tmp"
```

User-scope install also writes a managed King Sejong guidance block to `${CODEX_HOME:-~/.codex}/AGENTS.md` by default. That keeps Sejong available as an always-on research, analysis, debate, planning, execution, and verification discipline across Codex workspaces. Use `--codex-guidance none` if you only want the skills, hooks, and active context.

Then try one of these:

```text
$sejong research this bug, choose the safest fix, implement it, and verify it
$sejong compare these implementation options and turn the selected path into executable work
$uigwe design-to-plan this approved feature brief
```

Agent-assisted install prompt:

```text
Install King Sejong into this repository from https://github.com/JoonSCode/king-sejong.
Run scripts/install-sejong.sh against the current repo, then verify the install with --verify.
```

## Manual Install

Clone this repository, then install the bundle into the repository where you want to use it:

```bash
git clone https://github.com/JoonSCode/king-sejong.git
cd king-sejong
bash scripts/install-sejong.sh /path/to/your-repo
```

To replace an existing install:

```bash
bash scripts/install-sejong.sh --force /path/to/your-repo
```

To check an existing install without copying files:

```bash
bash scripts/install-sejong.sh --verify /path/to/your-repo
```

To check whether your King Sejong source checkout has upstream updates:

```bash
bash scripts/install-sejong.sh --check-updates
```

To fast-forward the King Sejong source checkout and refresh the Codex user-scope install:

```bash
bash scripts/install-sejong.sh --auto-update --scope user
```

`--auto-update` refuses dirty or diverged source checkouts, uses `git pull --ff-only`, then refreshes the selected managed install with force semantics and normal verification. King Sejong hooks do not silently self-update during ordinary sessions.

To install into the current Codex user scope instead:

```bash
bash scripts/install-sejong.sh --scope user
bash scripts/install-sejong.sh --scope user --verify
```

Set `CODEX_HOME` first if your Codex home is not `~/.codex`.

Use `bash scripts/install-sejong.sh --scope user --codex-guidance none` to skip the managed `${CODEX_HOME:-~/.codex}/AGENTS.md` guidance block.

Repo scope copies these managed paths into the target repository:

- `.agents/skills/sejong/`
- `.agents/skills/jangyeongsil/`
- `.agents/skills/jiphyeonjeon/`
- `.agents/skills/uigwe/`
- `.agents/skills/seungjeongwon/`
- `.agents/skills/why-gate/`
- `docs/sejong/`

User scope copies these managed paths into `${CODEX_HOME:-~/.codex}/skills`:

- `sejong/`
- `jangyeongsil/`
- `jiphyeonjeon/`
- `uigwe/`
- `seungjeongwon/`
- `why-gate/`

In user scope, shared Sejong docs are installed under `skills/sejong/docs/`, and the installed skill files are rewritten to load those docs from the user skill tree.
User scope also copies the Codex plugin adapter to `${CODEX_HOME:-~/.codex}/plugins/cache/king-sejong-local/king-sejong/0.1.0/` and enables it through a marked King Sejong plugin block in `${CODEX_HOME:-~/.codex}/config.toml`.
That plugin hook is the canonical user-scope hook source. Reinstalling user scope removes the older marked direct hook block by default; use `--legacy-direct-hooks` only as an explicit fallback and never together with the plugin hook.

Keep each scope's managed paths together. The skills are intentionally small and load their routing, planning, schema, and handoff contracts from the installed Sejong docs. The plugin adapter is hook metadata only, so the user-facing skill remains `$sejong`.

## Runtime Artifact Cleanup

External run artifacts live under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs`. Use the cleanup helper to inspect, finalize, and prune those run directories without touching repository-tracked files:

```bash
python3 docs/sejong/scripts/sejong_cleanup.py report
python3 docs/sejong/scripts/sejong_cleanup.py finalize-run ~/.codex/sejong/runs/<repo-id>/<run-id> --status success
python3 docs/sejong/scripts/sejong_cleanup.py prune-runs
```

Cleanup is conservative by default. It reports what would be deleted unless `--execute` is passed, refuses paths outside the Sejong runs root, and protects active runs or runs marked with `promoted-artifacts.json` or `.sejong-promoted`.

## Compatibility

King Sejong is distributed as Codex skills with a thin Codex plugin adapter, not as an npm package, Python package, or standalone CLI.

| Host | Support | Notes |
| --- | --- | --- |
| Codex with repo-local `.agents/skills` | Supported | Primary target for repository-specific use. |
| Codex with user-scope `${CODEX_HOME:-~/.codex}/skills` plus the local plugin cache | Supported | Use when you want `$sejong`, `$jangyeongsil`, `$jiphyeonjeon`, `$uigwe`, and `$seungjeongwon` available across workspaces with plugin hook metadata. |
| Codex-style hosts that read `.agents/skills` and repo docs | Possible | Install the same managed paths and verify behavior in that host. |
| OpenCode, Claude Code, Gemini CLI, Cursor | Not packaged yet | Their plugin/extension formats need separate adapters. |

If you use several agent harnesses, install King Sejong separately for each harness once an adapter exists.

## Codex And Execution

This package is explicitly for Codex-style skills:

- In repo scope, Codex loads `.agents/skills/sejong/SKILL.md` for `$sejong`.
- In user scope, Codex loads `${CODEX_HOME:-~/.codex}/skills/sejong/SKILL.md` for `$sejong`.
- The `king-sejong` plugin exposes hook metadata only; it does not add a second plugin-scoped `$sejong` skill.
- The same scope contains `$jangyeongsil`, `$jiphyeonjeon`, `$uigwe`, and `$seungjeongwon`.
- Codex can execute clear tasks directly through Sejong when formal planning is not needed.
- The docs include Codex consumer contracts for downstream execution feedback.

Execution is part of Sejong's job, and King Sejong includes its own executor:

- `Seungjeongwon` / `승정원`

Seungjeongwon is King Sejong's native execution loop. It executes approved scopes or validated Uigwe bundles, verifies the result, and reports evidence.

Sejong can finish work in two ways:

- direct execution in the current Codex session when the task is clear enough
- native Seungjeongwon execution when a plan or bundle needs implementation and verification

What is included:

- direct execution for clear implementation and verification work
- recursive Uigwe decomposition that keeps selected leaves tied to the parent goal and verification criteria
- `Seungjeongwon` native executor skill
- Seungjeongwon execution contract
- Why Gate rationale checkpoints for reviews, planning choices, retrospectives, and self-audits
- repo-context `AGENTS.md` init/refresh contract with candidate diffs
- runtime contracts, discipline gates, workflow-run evidence, and outcome-quality validation helpers
- external runtime cleanup, retention defaults, and active-run protection for Sejong run directories
- schema, bundle, and instruction-surface validation helpers
- install and verify script for managed repo-local and Codex user-scope paths

What is not included:

- a guarantee that non-Codex hosts understand the handoff automatically
- an always-on automatic updater for repository instruction files
- adapters for OpenCode, Claude Code, Gemini CLI, or Cursor

## Work Loop

Sejong can run the full arc when the user asks for an outcome:

```text
JangYeongsil research -> Jiphyeonjeon discussion -> Uigwe planning -> Seungjeongwon execution -> verification -> Sillok evidence
```

It should only stop early when the next step truly needs missing evidence, a user decision, or an approval gate.

## Use

Use Sejong when the right workflow is not obvious yet:

```text
$sejong research this and tell me whether it should become a plan
$sejong discuss these options and recommend the next surface
$sejong turn this approved design into executable work
```

Use Uigwe directly when you already know you want formal planning:

```text
$uigwe full build a browser-based MVP for async interview practice
$uigwe design-to-plan this feature brief
$uigwe decompose-only docs/specs/approved-design.md
```

## Routing Model

| Surface | Use When | Output |
| --- | --- | --- |
| `JangYeongsil` / `장영실` | The facts, history, or evidence are still unclear. | Known facts, inferences, unknowns, next decision. |
| `Jiphyeonjeon` / `집현전` | The main job is discussing options and choosing a direction. | Arguments for and against, rejected paths, recommendation, risks. |
| `Uigwe` / `의궤` | A durable planning bundle is useful. | Uigwe packets, `spec.md`, `rationale.md`, `goal-tree.json`. |
| `Seungjeongwon` / `승정원` | A validated scope or bundle needs execution. | Execution, verification, and feedback. |
| `Sillok` / `실록` | Evidence should be preserved. | Scorecards, promotion notes, decision history. |
| `Danjong` / `단종` | An option should be rejected or retired. | Rejected-option record. |
| `Sejong direct` | The task is clear enough to do now. | Completed work plus verification evidence. |

Court-inspired names are supported as user-facing language:

- `JangYeongsil` -> research
- `Jiphyeonjeon` -> discussion, debate, and decision support
- `Uigwe` -> formal planning
- `Seungjeongwon` -> execution
- `Sillok` -> evidence records
- `Danjong` -> rejected or retired options

Use `JangYeongsil` when evidence is missing, `Jiphyeonjeon` when evidence exists but the team needs discussion, and `Uigwe` when the selected direction should become a formal plan.

`Jiphyeonjeon` is optional. It should appear as a short council pass only when evidence leaves a meaningful choice; skip it when the direction is already clear enough for Uigwe, Seungjeongwon, or direct action.

Bounded workers can increase parallelism for independent research branches, option reviews, implementation slices, or verification lanes. Codex native subagents are one backend; `$team` tmux workers are another. They are not a required step; the lead Sejong agent still owns synthesis, routing, and final verification.

For larger Sejong runs, use research fan-out in `JangYeongsil`, bounded council briefs in `Jiphyeonjeon`, and only preflight checks in `Uigwe` before approval gates. Substantial `Jiphyeonjeon` decisions may use `$team` tmux workers coordinated through Sejong mailbox/state files under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/`. Worker or subagent agreement is never evidence, approval, or verification by itself.

No `.codex/prompts/{role}.md` files are required. King Sejong uses Codex native role prompts by default and treats repo-local prompt files as optional overlays when a target repo provides them.

When changing King Sejong itself, material behavior changes should follow the full Sejong chain: Jiphyeonjeon decision support, Uigwe planning and decomposition, then Seungjeongwon implementation and verification. Use direct edits only for non-behavioral typo, link, formatting, or mechanical fixes.

## Next

- Start with [the Sejong docs index](docs/sejong/README.md) when you want the full contract surface.
- Read [the runtime contract](docs/sejong/RUNTIME_CONTRACT.md) only if you are installing, maintaining, or changing King Sejong itself.
- Run `bash scripts/install-sejong.sh --verify .` after changing managed install paths or installer behavior.
- [Sejong router contract](docs/sejong/ROUTER.md)
- [Repo context init and refresh](docs/sejong/REPO_CONTEXT.md)
- [Artifact storage](docs/sejong/ARTIFACT_STORAGE.md)
- [Team executor](docs/sejong/TEAM_EXECUTOR.md)
- [Workflow-run dynamic workflow evidence contract](docs/sejong/WORKFLOW_RUN.md)
- [OSS maintainer workflows](docs/sejong/OSS_MAINTAINER_WORKFLOWS.md)
- [Prompt overlays](docs/sejong/PROMPT_OVERLAYS.md)
- [Uigwe protocol](docs/sejong/PROTOCOL.md)
- [Uigwe wrapper](docs/sejong/WRAPPER.md)
- [Seungjeongwon executor](docs/sejong/SEUNGJEONGWON_EXECUTOR.md)
- [Bundle validator](docs/sejong/BUNDLE_VALIDATOR.md)

## License

MIT. This keeps installation and reuse low-friction for personal, internal, and public agent workflows.
