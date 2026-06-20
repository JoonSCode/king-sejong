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

Active King Sejong context checkpoints should be stored inside the same run directory. Recommended names:

```text
king-sejong-context.json
ambiguity-register.json
continuity-capsule.json
seungjeongwon-run.json
workflow-run.json
route-decisions.jsonl
execution-feedback.json
execution-ledger.jsonl
sillok-record.jsonl
```

The context checkpoint should follow `docs/sejong/king-sejong-context.schema.json`. It is the shared runtime state for hooks, native subagents, TeamExecutor workers, Seungjeongwon execution feedback, and Sillok evidence refs.

Ambiguity registers should follow `docs/sejong/ambiguity-register.schema.json`.
The active context should reference them through `artifact_refs` rather than
duplicating the full clarification state.

Continuity capsules should follow `docs/sejong/continuity-capsule.schema.json`.
They are compact AI working-set indexes for compaction and session resumption.
The active context should reference them through `artifact_refs`. Store refs to
Sillok traces, Uigwe packets, ambiguity registers, Seungjeongwon run artifacts,
and route decisions instead of copying raw logs or private evidence into the
capsule.

Seungjeongwon active run artifacts should follow
`docs/sejong/seungjeongwon-run.schema.json`. The active context should reference
them through `artifact_refs` so hooks can block premature stop or compaction
while execution remains active or invalid.

Seungjeongwon run and checkpoint artifacts must include provenance:

- `created_by`: Sejong surface or worker id that created the artifact
- `source_repo`: repository root the artifact describes
- `source_commit`: git commit for that repository, or the explicit value
  `unknown` when the host cannot capture it
- `skill_version`: King Sejong skill or plugin version, or `unknown` when the
  version cannot be identified
- `host`: host runtime, such as `codex`
- `model`: model identifier, or `unknown` when the host does not expose it
- `generated_at`: artifact creation timestamp
- `input_refs`: source bundle, run, context, or evidence refs used as inputs
- `verification_refs`: checks, commands, or evidence refs that support the
  artifact state

## Evidence Manifests

A run directory may include `evidence-manifest.json` when the workflow needs a
compact integrity index over runtime artifacts. The manifest is evidence
integrity metadata, not a sandbox and not an approval gate by itself.

Recommended fields:

- `format`: `sejong.evidence-manifest/v0.1-draft`
- `manifest_id`: stable id for the manifest
- `run_id`: Sejong or Seungjeongwon run id
- `repo_root`: repository root the manifest describes
- `generated_at`: manifest creation timestamp
- `producer`: Sejong surface, helper, or worker that produced the manifest
- `parent_event_refs`: Sillok event ids, hook events, or run ids that explain
  why the manifest was generated
- `artifacts`: list of artifact records with `ref`, `sha256`, `size_bytes`,
  `artifact_format`, `producer`, and `verification_refs`

Use SHA-256 hashes to detect accidental drift or tampering in referenced
runtime artifacts. Do not describe a passing hash check as proof that tool
execution was contained, permissions were safe, or untrusted content was
sanitized.

Hooks may use the manifest at `Stop` or `PreCompact` time to detect broken or
changed evidence refs when a workflow explicitly references it. A mismatch
should trigger continuation or re-verification, not silent completion.

Codex-migrated or mocked workflow-like backend runs should follow
`docs/sejong/workflow-run.schema.json`. Use
`docs/sejong/scripts/sejong_workflow_run.py` to record mapped court surfaces,
bounded workers, backend provenance, worker/concurrency metrics, evidence
ledgers, quality comparison, authority violations, and the final recommendation.
These artifacts are subordinate evidence for Sejong and Seungjeongwon; they are
not Uigwe packets, do not approve gates, and do not permit hidden calls to
Claude CLI, Claude API, or an external Claude workflow runtime.
The helper rejects repo-local workflow-run creation unless the caller provides
an explicit promoted-artifact ref.

Sillok trace events should follow `docs/sejong/sillok-trace-event.schema.json`.
Use [SILLOK_TRACE.md](SILLOK_TRACE.md) for the JSONL event contract and security
review rules.

Team worker coordination state should be stored under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/
```

Do not store King Sejong team state in repo-local or tool-specific orchestration directories. Team worker coordination state is part of the Sejong contract only when it is rooted under `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`.

## Artifact Classes

External nontracked artifacts include:

- active King Sejong context checkpoints
- ambiguity registers for live clarification
- continuity capsules for AI working-set projection across compaction
- route decision logs
- raw JangYeongsil research notes
- Jiphyeonjeon council briefs
- hook simulation inputs and outputs
- TeamExecutor mailbox logs, worker notes, leases, and bounded challenge-round messages
- temporary Uigwe packets and preflight notes
- wrapper results produced during live planning
- Seungjeongwon execution evidence snapshots
- Seungjeongwon actionable decomposition notes and execution attempt ledgers
- Seungjeongwon active run artifacts
- workflow-run shadow comparisons for Codex-migrated dynamic workflow,
  deep-research-style, or mocked backends
- outcome-quality comparison artifacts
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
- the active context id when a checkpoint was created or updated
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
- keep context checkpoints compact and reference large artifacts by path
- support pruning old runs
- avoid promoting secrets or raw private evidence into tracked files

## Completion And Cleanup Lifecycle

External storage is not a reason to keep every runtime file forever. Sejong
runs should be compacted when they finish and pruned by policy after they are no
longer needed for resume, debugging, or review.

The default lifecycle is:

1. During an active run, keep runtime artifacts needed for planning,
   execution, verification, and resume.
2. At completion, write a compact `run-summary.json` and preserve compact
   evidence such as `sillok-record.jsonl`, `evidence-manifest.json`,
   `execution-feedback.json`, and continuity or checkpoint files.
3. For successful runs, delete raw research notes, temporary Uigwe packets,
   worker mailbox state, scratch logs, and unreviewed execution snapshots once
   the compact record exists.
4. For failed or blocked runs, keep raw artifacts for the failure retention
   window so the user or a later session can debug or resume the work.
5. Periodically prune completed run directories whose compact record is older
   than the retention window, while preserving the newest configured number of
   completed runs per repository.

Cleanup must be conservative:

- never delete the active run referenced by the active King Sejong context
- never delete a run that contains a promotion marker such as
  `promoted-artifacts.json` or `.sejong-promoted`
- never delete repository-tracked artifacts as part of external runtime cleanup
- require an explicit execution flag for destructive cleanup; dry-run reporting
  is the default
- report deleted and retained paths with reasons

Default retention values live in `policy.defaults.json`. The intended defaults
are:

- successful run raw artifacts: prune at finalization after compact evidence is
  written
- failed or blocked run raw artifacts: keep for 14 days
- compact run records: keep for 90 days, while preserving the newest 50 compact
  runs per repository
- sensitive raw evidence: compact or redact, then prune as soon as safely
  possible
