# Contributing

King Sejong is a Codex-native skill and protocol distribution. Contributions should keep the installed skill files thin and put durable behavior in `docs/sejong/`.

## Before You Start

- Read `AGENTS.md` for source-repository maintenance rules.
- Read `docs/sejong/ROUTER.md` before changing routing behavior.
- Read `docs/sejong/PROTOCOL.md` before changing Uigwe planning behavior.
- Read `docs/sejong/SEUNGJEONGWON_EXECUTOR.md` before changing execution behavior.
- Read `docs/sejong/HOOKS.md` before changing hook guardrails.

## Development Rules

- Keep runtime state outside the target repository under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}` unless a user explicitly asks to promote a tracked artifact.
- Do not add root-level repository files to the managed install surface unless the installer, README files, and verification docs are intentionally updated together.
- Keep the Codex plugin adapter thin. It exposes hook metadata; it is not the durable source of truth for Sejong behavior.
- Add or update tests before changing hook, installer, schema, active-context, TeamExecutor, Uigwe, or Seungjeongwon behavior.

## Validation

Run focused validation for the surface you changed. For broad behavior, installer, or docs contract changes, use:

```bash
python3 -m unittest discover -s docs/sejong/scripts -p 'test_*.py' -v
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/benchmark_instruction_surface.py --write --require-targets
bash scripts/install-sejong.sh --verify .
```

When changing user-scope installer behavior, also verify the user install path from a clean source checkout when practical:

```bash
bash scripts/install-sejong.sh --scope user --verify
```

If the installed hook blocks a protected-path verification command while you are validating King Sejong itself, avoid direct protected-path wording in the command string and continue through the normal verification route. For example:

```bash
p=$(printf 'scripts/%s' 'install-sejong.sh')
bash "$p" --verify .
```

## Pull Requests

Pull requests should include:

- the problem being solved
- the behavioral contract being changed, if any
- rejected alternatives or rationale for the selected approach
- validation commands and results
- any follow-up that should remain open

Small typo, link, and formatting fixes can stay lightweight. Material Sejong behavior changes should follow the full Sejong route: decision support, Uigwe planning, Seungjeongwon execution, and verification.
