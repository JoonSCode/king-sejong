# Sejong Artifact Storage

**Status:** Draft

## Purpose

Sejong can produce research notes, council briefs, Uigwe planning bundles, execution evidence, and Sillok records while it works across repositories.

Those artifacts must not surprise the user by appearing in the target repository's `git status`.

This document defines the default storage contract for Sejong, Uigwe, and Seungjeongwon.

## Default Policy

The default artifact policy is:

- runtime, research, discussion, evidence, and temporary planning artifacts are stored outside the target repository
- generated artifacts are not git-tracked by default
- tracked repository files are created only when the user explicitly asks to preserve, promote, or commit a shareable artifact
- the installer does not ask for an artifact tracking policy during normal install

The default external root is:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}
```

Runs should be stored under a repository-scoped run directory such as:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/runs/<repo-id>/<timestamp>-<run-id>/
```

`<repo-id>` should be stable enough to separate repositories and short enough to read in reports. A slug plus a short hash of the repository root is sufficient.

Team worker coordination state should be stored under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/
```

Do not use `.omx/state/team` for King Sejong. OMX-specific paths are outside the Sejong contract.

## Artifact Classes

External nontracked artifacts include:

- raw JangYeongsil research notes
- Jiphyeonjeon council briefs
- TeamExecutor mailbox logs, worker notes, leases, and bounded challenge-round messages
- temporary Uigwe packets and preflight notes
- wrapper results produced during live planning
- Seungjeongwon execution evidence snapshots
- Sillok evidence logs that were not explicitly requested as repository records

Repository-tracked artifacts are allowed only by explicit user request. Suitable promoted artifacts include:

- `spec.md`
- `rationale.md`
- `goal-tree.json`
- reviewed packet JSON files
- compact Sillok decision records meant for team review

Raw research logs, scratch notes, runtime snapshots, and unreviewed sensitive evidence should not be promoted automatically.

## Explicit Promotion

Promotion means copying or generating selected artifacts into a repository path where git may track them.

Treat these as explicit promotion requests:

- "write this plan into the repo"
- "leave a tracked Uigwe bundle"
- "commit-ready Sillok record"
- "repo에 계획 파일로 남겨"
- "의궤 번들을 저장소에 남겨"
- "실록 기록을 커밋 가능하게 남겨"

Do not infer promotion only because a task used Uigwe, produced a plan, or reached Sillok. Planning and evidence can be durable without being repository-tracked.

## Reporting Requirements

When a Sejong run generates artifacts, the final response should report:

- the external run directory when artifacts were written
- whether any repository-tracked artifacts were created
- how to request promotion if the user may want the result kept in the repo

If no tracked artifacts were created, say so directly.

## Installer Contract

Normal installation must not prompt for artifact tracking behavior.

The installer should install the skill and documentation surface only. It should not edit a target repository's `.gitignore` or `.git/info/exclude` merely to hide Sejong runtime artifacts, because the default runtime location is outside the repository.

Advanced repo-local artifact policies may be added later as an explicit configuration surface, but they must not weaken the default nontracked behavior.

## Failure Handling

If the external artifact root cannot be created or written:

1. report the storage failure
2. continue with an in-response summary when possible
3. ask before writing fallback artifacts inside the target repository

Do not silently fall back to tracked repository files.

## Retention And Privacy

External artifact roots may contain sensitive research notes and execution evidence. Implementations should:

- create storage directories with user-private permissions where the host allows it
- keep repository namespaces separate
- support pruning old runs
- avoid promoting secrets or raw private evidence into tracked files
