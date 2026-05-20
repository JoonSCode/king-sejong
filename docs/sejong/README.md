# Sejong + Uigwe

Sejong is the all-in-one user-facing front door for broad agent work.
It can research, decide, plan, execute, verify, and record evidence instead of forcing every request through formal planning.

Uigwe is the formal planning protocol inside Sejong. Use it when the output should be a durable planning bundle with packets, rationale, and executable leaves.

## Installed Layout

The installer copies this whole contract surface into a target repository:

- `.agents/skills/sejong/`
- `.agents/skills/uigwe/`
- `docs/sejong/`

The skill files stay short by design. They load the detailed contracts from this directory only when needed.

## Start Here

For normal use:

1. Read [ROUTER.md](ROUTER.md) to understand Sejong's lanes.
2. Read [PROTOCOL.md](PROTOCOL.md) to understand Uigwe's planning model.
3. Read [WRAPPER.md](WRAPPER.md) if you want machine-consumable packet flow.
4. Read [RALPH_EXECUTOR.md](RALPH_EXECUTOR.md) if you want to hand a validated plan to execution.

## Practical Usage

Use Sejong when the correct workflow is still uncertain:

```text
$sejong investigate the history and tell me the next decision
$sejong compare these options and recommend a path
$sejong this approved design should become executable work
$sejong research the problem, plan the fix, implement it, and verify it
```

Use Uigwe directly when you already want formal planning:

```text
$uigwe full <brief>
$uigwe design-to-plan <clear intent or feature brief>
$uigwe decompose-only <approved design artifact>
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

This public package includes schema and bundle validation helpers, but it intentionally does not ship private benchmark runs or score histories.

Useful commands:

```bash
python3 docs/sejong/scripts/validate_json_contracts.py
python3 docs/sejong/scripts/validate_bundle.py docs/sejong/examples/greenfield-full-flow
python3 docs/sejong/scripts/project_summary.py docs/sejong/examples/greenfield-full-flow --write
```
