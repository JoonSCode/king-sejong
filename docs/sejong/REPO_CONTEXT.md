# Repo Context Init And Refresh

**Status:** Draft

## Purpose

King Sejong can help create or refresh repository instruction context such as
`AGENTS.md`.

This is a guarded repo-context promotion workflow. It is not an always-on
updater, not a replacement for Codex's own context loading, and not permission
to rewrite a repository's instructions silently.

Use this workflow when a user asks for a Sejong-level equivalent of project
initialization, context refresh, session-wrap style instruction updates, or
durable promotion of lessons from a completed session into repo-local guidance.

## Modes

`init`

- Use when the target repository has no `AGENTS.md`, or when the user
  explicitly requests a new repo instruction file.
- Inspect the repository before drafting. At minimum check the current working
  tree, recent commits, README or docs index, project structure, and test or
  validation commands that are already documented.
- Produce an initial `AGENTS.md` candidate that is specific to that repository.
- Do not copy this source repository's `AGENTS.md` into target repositories.

`refresh`

- Use when `AGENTS.md` already exists and the user wants to preserve durable
  lessons from the current session, recent diffs, validation evidence, or
  repeated maintenance decisions.
- Deduplicate against existing guidance before proposing any change.
- Prefer small edits to the existing file's structure and voice.
- Reject transient status, one-off next steps, private evidence, secrets, and
  guidance that is not repo-specific.

## Guardrails

- Do not run as an always-on automatic updater.
- Do not edit tracked instruction files without explicit user approval or an
  explicit apply instruction.
- Produce a candidate diff before changing tracked files.
- Treat existing repository guidance as source of truth unless current evidence
  shows it is stale or wrong.
- Keep user-global preferences out of repo-local files unless they are necessary
  for that repository's maintenance contract.
- Keep temporary research, candidate notes, and rejected lesson inventories
  outside the target repository by default under the Sejong artifact root.
- When applying a diff, make the smallest scoped edit and verify the result.

## Evidence Inputs

Inspect only the evidence needed for the requested repo-context action:

- existing `AGENTS.md` or equivalent repo instruction files
- `README.md`, docs indexes, package manifests, build scripts, and validation docs
- `git status --short --branch`
- recent commit messages when they clarify direction
- current session outputs, validation results, and reviewed diffs
- user-provided durable decisions

Separate evidence into:

- `known`: directly observed repo facts
- `inferred`: conclusions supported by those facts
- `candidate_lessons`: guidance that might deserve promotion
- `rejected_lessons`: material intentionally kept out of repo instructions

## Workflow

1. Classify the request as `init` or `refresh`.
2. Inspect the target repository and existing instruction context.
3. Collect candidate durable lessons with evidence references.
4. Run the instruction pollution checks:
   - repo-specific
   - durable beyond the current session
   - non-secret
   - not already covered
   - not contradicted by current docs
   - useful for future agents
5. Produce a candidate diff and summarize rejected lessons.
6. Apply only after explicit user approval or an explicit apply instruction.
7. Verify with `git diff --check` and any repo-specific instruction validation
   that exists.

For a read-only first pass, use:

```bash
python3 docs/sejong/scripts/repo_context_candidate.py \
  --repo-root . \
  --lesson "Preserve release validation commands in maintainer guidance."
```

The helper emits a candidate block and rejected lesson inventory. It does not
write `AGENTS.md`; the Sejong lead still owns the final diff and approval gate.

For substantial changes to King Sejong's own repo-context behavior, follow the
material self-modification route:

```text
Jiphyeonjeon decision -> Uigwe planning/decomposition -> Seungjeongwon execution and verification
```

## Outputs

Before applying changes, report:

- target repository
- mode: `init` or `refresh`
- inspected evidence
- candidate lessons
- rejected lessons and reasons
- proposed diff or exact proposed sections
- required approval or apply instruction

After applying changes, report:

- files changed
- verification commands and status
- any remaining risks or follow-up decisions

## Artifact Storage

Repo-context research notes, rejected lesson inventories, and candidate diffs
are Sejong runtime artifacts. Store them outside the target repository by
default under:

```text
${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}
```

Create or modify tracked files such as `AGENTS.md` only when the user approves
the candidate diff or explicitly asks to apply it.

## Worker Boundaries

JangYeongsil workers may gather bounded evidence, and Jiphyeonjeon workers may
review candidate lessons or risks. Workers must not write the canonical
instruction file, approve the diff, or claim final synthesis.

The lead Sejong agent owns the final candidate diff, rejected-option record,
application decision, and verification.
