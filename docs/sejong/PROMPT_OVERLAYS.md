# Prompt Overlays

King Sejong does not require `.codex/prompts/{role}.md` files.

The default path is to use Codex native role prompts through `agent_type`. Repo-local prompt files are optional overlays, not part of the required install surface.

## Resolution Order

When Sejong uses a Codex native subagent:

1. Select the native `agent_type` that matches the bounded task.
2. If `.codex/prompts/{role}.md` exists in the target repo, read it as a repo-specific overlay.
3. If the overlay does not exist, continue with the Codex native role prompt.
4. Pass the Sejong surface contract, shared evidence bundle, allowed output, forbidden decisions, and lead-owned gate rules in the task prompt.

Missing prompt overlay files are not install failures and should not block delegation.

TeamExecutor uses a separate runtime prompt path. For `$team` / tmux workers,
the run helper generates `workers/<worker-id>/prompt.md` under the Sejong team
run directory and feeds that prompt to the worker command. That file is
run-state, not a `.codex/prompts/{role}.md` overlay. It should carry the active
surface, source refs, role, scope, allowed outputs, forbidden authority claims,
return format, verification expectation, and stop condition for the specific
worker.

## When To Add Overlays

Add `.codex/prompts/{role}.md` only when the repo has stable role-specific rules that the native Codex role would not know:

- domain-specific evidence sources
- local build, test, or validation commands
- protected files or approval gates
- product vocabulary or naming policy
- recurring output format requirements

Do not add overlays just to restate generic Codex role behavior. Stale overlays are worse than no overlays.

## Sejong Mapping

Typical native role choices:

- `JangYeongsil`: `researcher`, `explore`, `analyst`, or `dependency-expert`
- `Jiphyeonjeon`: `critic`, `architect`, `analyst`, or `dependency-expert`
- `Uigwe` preflight: `architect`, `test-engineer`, `verifier`, or `writer`
- `Seungjeongwon`: `executor`, `test-engineer`, `code-reviewer`, or `verifier`
- `Sillok`: `verifier` or `writer`

The lead Sejong agent still owns synthesis, final routing, gates, and final verification.

Optional Codex custom agents may be documented or copied from examples when a repo wants project-scoped roles. See `docs/sejong/examples/codex-agents/` for narrow examples. These examples are not a required install surface, and they do not replace the Sejong lead.

## Overlay Contract

If an overlay exists, it should reinforce this structure:

- role purpose
- allowed inputs
- required output
- forbidden decisions
- source or file scope limits
- verification expectations
- handoff format back to the lead agent

It should not authorize the subagent to approve Uigwe gates, treat agreement as evidence, or replace lead-owned synthesis.

When hooks are enabled, `SubagentStart` should inject the active context summary
plus a bounded worker contract with source refs, allowed outputs, forbidden
claims, return format, and stop condition. `SubagentStop` should reject outputs
that claim gate approval, final synthesis, final verification, or majority-vote
decision ownership.
