#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
REQUEST_FORMAT = "uigwe.ralph-executor-request/v0.4-draft"
RESULT_FORMAT = "uigwe.ralph-executor-result/v0.4-draft"
BACKEND = "codex-native-ralph-skill"
ALLOWED_REENTRY_TARGETS = [
    "local_reexploration",
    "brainstorming",
    "deep_interview",
    "human_review",
]
EXECUTION_RULES = [
    "Treat the Uigwe bundle as the source of truth in this order: plan.packet.json, goal-tree.json, spec.md, rationale.md, planning-summary.md when present.",
    "Execute only the executable_leaf nodes included in execution_scope.",
    "Respect dependency order and do not dispatch a leaf before its dependencies complete.",
    "Run leaves in parallel only when file scopes do not overlap, risk is not high, and the leaf's consumer hints allow parallel execution.",
    "Do not reopen planning or widen scope unless execution discovers a real contradiction in the bundle or codebase.",
    "Gather fresh verification evidence before claiming a leaf is complete.",
    "Apply the handoff git_policy: do not create commits unless mode is create_commits, and group dependency-ready leaves into coherent commit groups rather than forcing one commit per leaf.",
    "Treat clean finish as no unintended tracked changes in the target scope; do not delete ignored caches or build artifacts to satisfy clean checks.",
    "Escalate contradictions through the allowed re-entry targets instead of guessing.",
]
OUTPUT_EXPECTATIONS = [
    "Report which leaf ids completed, blocked, or were invalidated.",
    "Capture verification evidence for each dispatched leaf.",
    "List modified files or generated artifacts.",
    "Report git policy outcome for every run; completed create_commits runs must include commit group ids, commit shas, and tracked worktree clean evidence.",
    "If execution blocks, recommend exactly one re-entry target when possible.",
    "Persist execution feedback and executor result artifacts at the suggested root-level paths unless an explicit harness policy overrides them.",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a RalphExecutor handoff request from an Uigwe bundle.")
    parser.add_argument("bundle_path", help="Uigwe bundle directory or wrapper.result.json path")
    parser.add_argument("--write", action="store_true", help="Write ralph-executor.request.json and ralph-next-step.md into the bundle directory")
    parser.add_argument("--json", action="store_true", help="Print JSON handoff request to stdout")
    parser.add_argument(
        "--git-policy",
        choices=["no_commit", "prepare_only", "create_commits"],
        default="prepare_only",
        help="Git closeout policy to include in the Ralph handoff. create_commits requires Ralph to persist commit evidence before completed.",
    )
    return parser.parse_args()


def resolve_bundle_path(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path.resolve()
    return input_path.resolve().parent


def rel_repo(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT)) or "."
    except ValueError:
        pass
    resolved_str = str(resolved)
    repo_str = str(REPO_ROOT)
    repo_prefix = repo_str + "/"
    if resolved_str.lower().startswith(repo_prefix.lower()):
        return resolved_str[len(repo_prefix) :]
    return str(resolved)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_file(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return path


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return load_json(path)
    except Exception:
        return None


def wrapper_artifact_path(wrapper_result: dict[str, Any], key: str, fallback: Path) -> Path:
    artifacts = wrapper_result.get("artifacts", {})
    raw_path = artifacts.get(key)
    if raw_path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return require_file(path)
    return require_file(fallback)


def validate_wrapper_result(wrapper_result: dict[str, Any]) -> None:
    status = wrapper_result.get("status")
    if status != "completed":
        raise ValueError(f"wrapper.result.json status must be 'completed', got {status!r}")
    blockers = wrapper_result.get("blockers") or []
    if blockers:
        raise ValueError("wrapper.result.json still reports blockers; resolve them before execution handoff.")


def load_bundle(bundle_dir: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, str]]:
    wrapper_result = load_json(require_file(bundle_dir / "wrapper.result.json"))
    validate_wrapper_result(wrapper_result)

    plan_packet_path = wrapper_artifact_path(wrapper_result, "plan_packet_path", bundle_dir / "plan.packet.json")
    goal_tree_path = wrapper_artifact_path(wrapper_result, "goal_tree_path", bundle_dir / "goal-tree.json")
    spec_path = wrapper_artifact_path(wrapper_result, "spec_path", bundle_dir / "spec.md")
    rationale_path = wrapper_artifact_path(wrapper_result, "rationale_path", bundle_dir / "rationale.md")

    plan_packet = load_json(plan_packet_path)
    goal_tree = load_json(goal_tree_path)

    if plan_packet.get("ready_for_consumer") is not True:
        raise ValueError("plan.packet.json is not marked ready_for_consumer=true; do not hand it to Ralph yet.")

    bundle = {
        "plan_packet_path": rel_repo(plan_packet_path),
        "goal_tree_path": rel_repo(goal_tree_path),
        "spec_path": rel_repo(spec_path),
        "rationale_path": rel_repo(rationale_path),
    }

    summary_path = bundle_dir / "planning-summary.md"
    if summary_path.exists():
        bundle["planning_summary_path"] = rel_repo(summary_path)

    return wrapper_result, plan_packet, goal_tree, bundle


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def normalize_pathish(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return rel_repo(path)
    return value


def collect_leaf_contracts(plan_packet: dict[str, Any], goal_tree: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    plan_leaves = {leaf["id"]: leaf for leaf in plan_packet.get("leaf_tasks", [])}
    goal_nodes = {node["id"]: node for node in goal_tree.get("nodes", [])}

    executable_ids = [
        leaf_id
        for leaf_id in [leaf["id"] for leaf in plan_packet.get("leaf_tasks", [])]
        if goal_nodes.get(leaf_id, {}).get("status") == "executable_leaf"
    ]
    for node in goal_tree.get("nodes", []):
        if node.get("status") == "executable_leaf" and node["id"] not in executable_ids:
            executable_ids.append(node["id"])

    if not executable_ids:
        raise ValueError("goal-tree.json does not expose any executable_leaf nodes for Ralph to execute.")

    notes: list[str] = []
    leaf_contracts: list[dict[str, Any]] = []
    for leaf_id in executable_ids:
        leaf = plan_leaves.get(leaf_id, {})
        node = goal_nodes.get(leaf_id, {})
        dependencies = ordered_unique(list(leaf.get("dependencies", [])) + list(node.get("depends_on", [])))
        contract = {
            "id": leaf_id,
            "title": leaf.get("title") or node.get("title") or leaf_id,
            "description": leaf.get("description") or node.get("description") or "",
            "why": leaf.get("why") or node.get("why") or "",
            "done_criteria": leaf.get("done_criteria") or node.get("done_criteria") or [],
            "file_scope": [normalize_pathish(item) for item in (leaf.get("file_scope") or node.get("file_scope") or [])],
            "dependencies": dependencies,
            "verification": leaf.get("verification") or node.get("verification") or [],
            "risk_level": leaf.get("risk_level") or node.get("risk_level") or "medium",
            "consumer_hints": normalize_consumer_hints(leaf.get("consumer_hints") or node.get("consumer_hints") or {}),
        }
        if leaf_id not in plan_leaves:
            notes.append(f"Executable leaf {leaf_id} was recovered from goal-tree.json because it was missing from plan.packet.json leaf_tasks.")
        leaf_contracts.append(contract)

    ordered_ids, ordering_notes = topological_leaf_order(leaf_contracts)
    notes.extend(ordering_notes)
    return leaf_contracts, ordered_ids, notes


def topological_leaf_order(leaf_contracts: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    leaf_ids = [leaf["id"] for leaf in leaf_contracts]
    leaf_id_set = set(leaf_ids)
    indegree = {leaf_id: 0 for leaf_id in leaf_ids}
    outgoing: dict[str, list[str]] = {leaf_id: [] for leaf_id in leaf_ids}
    notes: list[str] = []

    for leaf in leaf_contracts:
        for dependency in leaf.get("dependencies", []):
            if dependency not in leaf_id_set:
                notes.append(
                    f"Leaf {leaf['id']} depends on {dependency}, which is outside the executable leaf set. Ralph should confirm it is already satisfied before dispatch."
                )
                continue
            indegree[leaf["id"]] += 1
            outgoing[dependency].append(leaf["id"])

    queue = deque([leaf_id for leaf_id in leaf_ids if indegree[leaf_id] == 0])
    ordered: list[str] = []
    while queue:
        current = queue.popleft()
        ordered.append(current)
        for nxt in outgoing[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(ordered) != len(leaf_ids):
        notes.append("Leaf dependency ordering contained a cycle, so Ralph should fall back to the bundle order and review dependencies manually.")
        return leaf_ids, notes
    return ordered, notes


def normalize_consumer_hints(consumer_hints: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(consumer_hints)
    if "expected_artifacts" in normalized:
        normalized["expected_artifacts"] = [normalize_pathish(item) for item in normalized.get("expected_artifacts", [])]
    return normalized


def build_bundle_fingerprint(bundle: dict[str, str]) -> str:
    hasher = hashlib.sha256()
    ordered_keys = [
        "plan_packet_path",
        "goal_tree_path",
        "spec_path",
        "rationale_path",
        "planning_summary_path",
    ]
    for key in ordered_keys:
        rel_path = bundle.get(key)
        if not rel_path:
            continue
        path = REPO_ROOT / rel_path
        hasher.update(key.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(rel_path.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return f"sha256:{hasher.hexdigest()}"


def derive_attempt_context(bundle_dir: Path) -> dict[str, Any]:
    request_path = bundle_dir / "ralph-executor.request.json"
    result_path = bundle_dir / "ralph-executor.result.json"
    existing_request = load_optional_json(request_path)
    existing_result = load_optional_json(result_path)

    observed: list[tuple[int, str]] = []
    for payload in [existing_request, existing_result]:
        if not isinstance(payload, dict):
            continue
        attempt_number = payload.get("attempt_number")
        attempt_id = payload.get("attempt_id")
        if isinstance(attempt_number, int) and attempt_number >= 1 and isinstance(attempt_id, str) and attempt_id:
            observed.append((attempt_number, attempt_id))

    if observed:
        latest_number, latest_id = max(observed, key=lambda item: item[0])
        next_number = latest_number + 1
        supersedes_attempt_id = latest_id
    else:
        next_number = 1
        supersedes_attempt_id = None

    return {
        "attempt_id": f"ralph-attempt-{next_number:03d}",
        "attempt_number": next_number,
        "supersedes_attempt_id": supersedes_attempt_id,
        "request_generated_at": now_utc_iso(),
        "request_status": "active",
    }


def build_follow_command(bundle_dir: Path) -> str:
    return f"$ralph follow {rel_repo(bundle_dir / 'ralph-next-step.md')}"


def build_next_step_options(bundle_dir: Path) -> tuple[str, dict[str, dict[str, str]], str]:
    follow_command = build_follow_command(bundle_dir)
    options = {
        "1": {
            "label": "Run now here",
            "description": "Continue in the current session by handing the generated Uigwe prompt to Ralph immediately.",
            "action_type": "run_now",
        },
        "3": {
            "label": "Run in another session or terminal",
            "description": "Use the copyable handoff command later after /clear or in a different terminal window.",
            "action_type": "show_command",
            "command": follow_command,
        },
    }
    message = "\n".join(
        [
            "## Next Step",
            "",
            "1. Run now here",
            "   Continue in the current session without typing a command.",
            "",
            "3. Run in another session or terminal",
            f"   `{follow_command}`",
            "",
            "Artifacts:",
            f"- `ralph-executor.request.json`: `{rel_repo(bundle_dir / 'ralph-executor.request.json')}`",
            f"- `ralph-next-step.md`: `{rel_repo(bundle_dir / 'ralph-next-step.md')}`",
        ]
    )
    return follow_command, options, message


def build_git_policy(mode: str) -> dict[str, Any]:
    policy = {
        "mode": mode,
        "verification_strategy": "tiered_changed_scope",
        "require_clean_start": False,
        "require_clean_finish": mode == "create_commits",
        "target_repo_paths": [rel_repo(REPO_ROOT)],
        "parent_gitlink_policy": "record_if_changed",
    }
    if mode == "no_commit":
        policy["verification_strategy"] = "record_only"
        policy["require_clean_finish"] = False
    return policy


def render_git_policy(git_policy: dict[str, Any]) -> list[str]:
    target_paths = ", ".join(f"`{item}`" for item in git_policy.get("target_repo_paths", [])) or "unspecified"
    parent_repo_path = git_policy.get("parent_repo_path") or "not specified"
    return [
        f"- Mode: `{git_policy['mode']}`",
        f"- Verification strategy: `{git_policy['verification_strategy']}`",
        f"- Require clean start: `{git_policy.get('require_clean_start', False)}`",
        f"- Require clean finish: `{git_policy.get('require_clean_finish', False)}`",
        f"- Target repo paths: {target_paths}",
        f"- Parent repo path: `{parent_repo_path}`",
        f"- Parent gitlink policy: `{git_policy.get('parent_gitlink_policy', 'none')}`",
        "- Clean finish means no unintended tracked changes in target scope. Do not run destructive ignored-file cleanup such as `git clean -xfd` just to satisfy this check.",
        "- When mode is `create_commits`, persist `git_evidence` in the executor result and link affected leaves to commit group ids in consumer feedback.",
    ]


def render_list(items: list[str], default: str = "None") -> list[str]:
    if not items:
        return [f"- {default}"]
    return [f"- {item}" for item in items]


def render_verification_items(items: list[dict[str, Any]]) -> list[str]:
    if not items:
        return ["- No explicit verification checks were provided."]
    rendered: list[str] = []
    for item in items:
        item_type = item.get("type", "check")
        description = item.get("description", "")
        rendered.append(f"- `{item_type}`: {description}")
    return rendered


def render_consumer_hints(consumer_hints: dict[str, Any]) -> list[str]:
    if not consumer_hints:
        return ["- No explicit consumer hints were provided."]

    expected_artifacts = ", ".join(f"`{item}`" for item in consumer_hints.get("expected_artifacts", [])) or "none"
    return [
        f"- preferred_role: `{consumer_hints.get('preferred_role', 'unspecified')}`",
        f"- needs_critic: `{consumer_hints.get('needs_critic', False)}`",
        f"- needs_verifier: `{consumer_hints.get('needs_verifier', True)}`",
        f"- can_run_parallel: `{consumer_hints.get('can_run_parallel', False)}`",
        f"- expected_artifacts: {expected_artifacts}",
    ]


def build_handoff_prompt(bundle_dir: Path, request: dict[str, Any], leaf_contracts: list[dict[str, Any]]) -> str:
    bundle = request["bundle"]
    planning_context = request["planning_context"]
    execution_scope = request["execution_scope"]

    lines = [
        "# Ralph Execution Handoff",
        "",
        "You are receiving a validated Uigwe planning bundle for execution through the Codex-native Ralph skill.",
        "Treat the Uigwe bundle as authoritative and do not reopen planning unless execution discovers a real contradiction.",
        "",
        "## Task Summary",
        "",
        f"- Bundle directory: `{rel_repo(bundle_dir)}`",
        f"- Attempt id: `{request['attempt_id']}`",
        f"- Attempt number: `{request['attempt_number']}`",
        f"- Resolved Uigwe mode: `{planning_context['resolved_mode']}`",
        f"- Resolved Uigwe profile: `{planning_context['resolved_profile']}`",
        f"- Selected plan id: `{planning_context['selected_plan_id']}`",
        f"- Selected plan title: `{planning_context['selected_plan_title']}`",
        f"- Selected plan summary: {planning_context['selected_plan_summary']}",
        f"- Bundle fingerprint: `{request['bundle_fingerprint']}`",
        "",
        "## Source Of Truth",
        "",
        f"1. `plan.packet.json`: `{bundle['plan_packet_path']}`",
        f"2. `goal-tree.json`: `{bundle['goal_tree_path']}`",
        f"3. `spec.md`: `{bundle['spec_path']}`",
        f"4. `rationale.md`: `{bundle['rationale_path']}`",
    ]
    if "planning_summary_path" in bundle:
        lines.append(f"5. `planning-summary.md`: `{bundle['planning_summary_path']}`")
    lines.extend(
        [
            "",
            "## Execution Scope",
            "",
            f"- Selection mode: `{execution_scope['selection_mode']}`",
            f"- Executable leaf ids: {', '.join(f'`{leaf_id}`' for leaf_id in execution_scope['executable_leaf_ids'])}",
            f"- Recommended dispatch order: {', '.join(f'`{leaf_id}`' for leaf_id in execution_scope['ordered_leaf_ids'])}",
            "",
            "## Execution Rules",
            "",
        ]
    )
    lines.extend(render_list(request["execution_rules"]))
    lines.extend(
        [
            "",
            "## Git Hygiene",
            "",
        ]
    )
    lines.extend(render_git_policy(request["git_policy"]))
    lines.extend(
        [
            "",
            "## Leaf Contracts",
            "",
        ]
    )

    for leaf in leaf_contracts:
        lines.extend(
            [
                f"### `{leaf['id']}` - {leaf['title']}",
                "",
                f"- Why: {leaf['why'] or 'No additional rationale provided.'}",
                f"- Description: {leaf['description'] or 'No additional description provided.'}",
                f"- Risk level: `{leaf['risk_level']}`",
                "",
                "Done criteria:",
            ]
        )
        lines.extend(render_list(leaf["done_criteria"], default="No explicit done criteria were provided."))
        lines.extend(
            [
                "",
                "Dependencies:",
            ]
        )
        lines.extend(render_list([f"`{item}`" for item in leaf["dependencies"]]))
        lines.extend(
            [
                "",
                "File scope:",
            ]
        )
        lines.extend(render_list([f"`{item}`" for item in leaf["file_scope"]], default="No explicit file scope was provided."))
        lines.extend(
            [
                "",
                "Verification:",
            ]
        )
        lines.extend(render_verification_items(leaf["verification"]))
        lines.extend(
            [
                "",
                "Consumer hints:",
            ]
        )
        lines.extend(render_consumer_hints(leaf["consumer_hints"]))
        lines.append("")

    lines.extend(
        [
            "## Output Expectations",
            "",
        ]
    )
    lines.extend(render_list(request["output_expectations"]))
    lines.extend(
        [
            "",
            "## Suggested Artifact Paths",
            "",
            f"- Attempt id: `{request['attempt_id']}`",
            f"- Consumer feedback: `{request['suggested_execution_feedback_path']}`",
            f"- Executor result: `{request['suggested_result_path']}`",
            "",
            "Persist the result and feedback at these root-level paths for this attempt unless your harness has an explicit alternate retention policy.",
            "",
            "## Re-entry Targets",
            "",
        ]
    )
    lines.extend(render_list([f"`{target}`" for target in request["allowed_reentry_targets"]]))
    return "\n".join(lines).rstrip() + "\n"


def build_request(bundle_dir: Path, git_policy_mode: str = "prepare_only") -> dict[str, Any]:
    wrapper_result, plan_packet, goal_tree, bundle = load_bundle(bundle_dir)
    leaf_contracts, ordered_leaf_ids, leaf_notes = collect_leaf_contracts(plan_packet, goal_tree)
    follow_command, next_step_options, next_step_message = build_next_step_options(bundle_dir)
    attempt_context = derive_attempt_context(bundle_dir)
    bundle_fingerprint = build_bundle_fingerprint(bundle)
    git_policy = build_git_policy(git_policy_mode)

    source_of_truth = ["plan_packet", "goal_tree", "spec", "rationale"]
    if "planning_summary_path" in bundle:
        source_of_truth.append("planning_summary")

    request: dict[str, Any] = {
        "format": REQUEST_FORMAT,
        "executor_type": "ralph",
        "backend": BACKEND,
        "bundle_root_path": rel_repo(bundle_dir),
        "bundle": bundle,
        "attempt_id": attempt_context["attempt_id"],
        "attempt_number": attempt_context["attempt_number"],
        "request_generated_at": attempt_context["request_generated_at"],
        "request_status": attempt_context["request_status"],
        "bundle_fingerprint": bundle_fingerprint,
        "planning_context": {
            "resolved_mode": wrapper_result["resolved_mode"],
            "resolved_profile": wrapper_result["resolved_profile"],
            "selected_plan_id": plan_packet["selected_plan"]["id"],
            "selected_plan_title": plan_packet["selected_plan"]["title"],
            "selected_plan_summary": plan_packet["selected_plan"]["summary"],
        },
        "execution_scope": {
            "selection_mode": "all_executable_leaves",
            "executable_leaf_ids": [leaf["id"] for leaf in leaf_contracts],
            "ordered_leaf_ids": ordered_leaf_ids,
        },
        "source_of_truth": source_of_truth,
        "allow_replanning": False,
        "git_policy": git_policy,
        "allowed_reentry_targets": ALLOWED_REENTRY_TARGETS,
        "execution_rules": EXECUTION_RULES,
        "output_expectations": OUTPUT_EXPECTATIONS,
        "recommended_next_command": follow_command,
        "next_step_options": next_step_options,
        "next_step_message": next_step_message,
        "suggested_handoff_prompt_path": rel_repo(bundle_dir / "ralph-next-step.md"),
        "suggested_execution_feedback_path": rel_repo(bundle_dir / "codex-consumer-feedback.json"),
        "suggested_result_path": rel_repo(bundle_dir / "ralph-executor.result.json"),
        "notes": [
            f"Resolved Uigwe mode: {wrapper_result['resolved_mode']}",
            f"Resolved Uigwe profile: {wrapper_result['resolved_profile']}",
            f"Attempt id: {attempt_context['attempt_id']}",
            f"Attempt number: {attempt_context['attempt_number']}",
            f"Prepared handoff for {len(leaf_contracts)} executable leaf nodes.",
            "Treat the Uigwe bundle as the execution source of truth.",
            "Do not reopen planning unless execution discovers a real contradiction.",
            f"Git policy mode: {git_policy['mode']}",
            "Root-level request and next-step files represent the latest active handoff for this bundle.",
            "Root-level result and feedback files are the durable persistence targets for this attempt unless an explicit harness policy overrides them.",
        ] + leaf_notes,
    }
    if attempt_context["supersedes_attempt_id"]:
        request["supersedes_attempt_id"] = attempt_context["supersedes_attempt_id"]
        request["notes"].append(
            f"Generating this handoff supersedes the previously recorded attempt `{attempt_context['supersedes_attempt_id']}` at the bundle root."
        )
    request["handoff_prompt"] = build_handoff_prompt(bundle_dir, request, leaf_contracts)
    return request


def main() -> int:
    args = parse_args()
    bundle_dir = resolve_bundle_path(Path(args.bundle_path))
    request = build_request(bundle_dir, git_policy_mode=args.git_policy)

    if args.write:
        (bundle_dir / "ralph-executor.request.json").write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
        (bundle_dir / "ralph-next-step.md").write_text(request["handoff_prompt"], encoding="utf-8")

    if args.json:
        print(json.dumps(request, indent=2))
    else:
        print(request["handoff_prompt"].rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
