# King Sejong

![Sejong routing map](docs/sejong/assets/sejong-routing-map.svg)

King Sejong is a repo-local skill bundle for Codex-style agents.

It gives an agent one broad front door, `$sejong`, for deciding whether a request needs research, decision support, formal planning, an executor handoff, or direct action.

Uigwe is the formal planning protocol behind that front door. Sejong routes into Uigwe only when a durable planning bundle is useful.

## Naming

Use **Sejong**.

Do not write `SeJong`. The conventional romanization is `Sejong`, as in `King Sejong`.

Recommended names:

- Human-facing product name: `King Sejong`
- Skill name: `sejong`
- Invocation: `$sejong`
- Repository slug: `king-sejong`

## Install

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

The installer copies these managed paths into the target repository:

- `.agents/skills/sejong/`
- `.agents/skills/uigwe/`
- `docs/sejong/`

Keep those paths together. The skills are intentionally small and load their routing, planning, schema, and handoff contracts from `docs/sejong`.

## Use

Use Sejong when the right workflow is not obvious yet:

```text
$sejong research this and tell me whether it should become a plan
$sejong compare these options and recommend the next lane
$sejong turn this approved design into executable work
```

Use Uigwe directly when you already know you want formal planning:

```text
$uigwe full build a browser-based MVP for async interview practice
$uigwe design-to-plan this feature brief
$uigwe decompose-only docs/specs/approved-design.md
```

## Routing Model

| Lane | Use When | Output |
| --- | --- | --- |
| `research-brief` | The facts, history, or evidence are still unclear. | Known facts, inferences, unknowns, next decision. |
| `decision-brief` | The main job is choosing between options. | Options, rejected paths, recommendation, risks. |
| `uigwe-plan` | A durable planning bundle is useful. | Uigwe packets, `spec.md`, `rationale.md`, `goal-tree.json`. |
| `executor-handoff` | A validated bundle should be handed to execution. | RalphExecutor handoff artifacts. |
| `direct-action` | The task is already clear enough to do. | The completed work, under the target repo's rules. |

Court-inspired aliases are supported as user-facing language:

- `JangYeongsil` -> research
- `Jiphyeonjeon` -> decision support
- `Seungjeongwon` -> executor handoff
- `Sillok` -> evidence records
- `Danjong` -> rejected or retired options

## Read More

- [Sejong router contract](docs/sejong/ROUTER.md)
- [Uigwe protocol](docs/sejong/PROTOCOL.md)
- [Uigwe wrapper](docs/sejong/WRAPPER.md)
- [RalphExecutor handoff](docs/sejong/RALPH_EXECUTOR.md)
- [Bundle validator](docs/sejong/BUNDLE_VALIDATOR.md)
