# OSS Maintainer Workflows

King Sejong is intended for maintainers who use Codex on real open-source repositories. It gives the agent a route discipline for deciding when to research, when to compare options, when to create a durable plan, when to execute, and when to verify before claiming completion.

## Pull Request Review

Use Sejong or Why Gate when a review needs both defect finding and rationale pressure:

```text
$sejong review this pull request for behavioral regressions, missing tests, and verification evidence
$why-gate review this diff for weak rationale behind abstractions or ownership boundaries
```

Expected behavior:

- findings first when concrete defects exist
- known, inferred, and unknown evidence separated
- rejected alternatives recorded when a design choice matters
- validation commands named before completion

## Issue Triage

Use Sejong when an issue is not yet ready for implementation:

```text
$sejong triage this issue, identify missing evidence, and recommend the next surface
```

Typical route:

```text
JangYeongsil research -> Jiphyeonjeon option judgment -> Uigwe planning or Danjong rejection
```

This keeps vague reports from turning into direct edits before the maintainer knows the risk, scope, and verification bar.

## Release Preparation

Use Seungjeongwon when the release scope is already selected:

```text
$seungjeongwon verify the release checklist and report remaining blockers
```

Useful checks include:

- installer verification
- schema validation
- hook and active-context tests
- example bundle validation
- changelog and README consistency
- user-scope install verification when installer behavior changed

## Security And Hook Guardrails

Use Sejong for security-sensitive changes because hook guardrails are not a sandbox. They need source inspection, explicit rationale, and fresh verification evidence.

Relevant surfaces:

- `docs/sejong/SECURITY.md`
- `docs/sejong/HOOKS.md`
- `docs/sejong/SILLOK_TRACE.md`
- `docs/sejong/scripts/king_sejong_hooks.py`
- `docs/sejong/scripts/sejong_context.py`

## API Credit Use

For Codex-based OSS maintenance, API credits are most useful when they support repeatable maintainer workflows:

- pull request review and regression analysis
- issue triage and evidence gathering
- release checklist automation
- installer and hook validation
- documentation consistency checks
- routing, verification, and outcome-quality benchmark runs

Credits should be used on public repositories the maintainer owns or has permission to administer, and should avoid sending secrets, private session logs, or unrelated local data.
