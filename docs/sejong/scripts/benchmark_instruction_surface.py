#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SEJONG_ROOT = SCRIPT_PATH.parents[1]
TASK_SET_PATH = SEJONG_ROOT / "examples" / "validation" / "uigwe-instruction-surface-task-set.json"
SCORECARD_PATH = SEJONG_ROOT / "examples" / "validation" / "runs" / "uigwe-instruction-surface.scorecard.json"
SUMMARY_PATH = SEJONG_ROOT / "examples" / "validation" / "runs" / "uigwe-instruction-surface.scorecard.md"

UIGWE_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "uigwe" / "SKILL.md"
SEJONG_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "sejong" / "SKILL.md"
JANGYEONGSIL_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "jangyeongsil" / "SKILL.md"
JIPHYEONJEON_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "jiphyeonjeon" / "SKILL.md"
SEUNGJEONGWON_SKILL_PATH = REPO_ROOT / ".agents" / "skills" / "seungjeongwon" / "SKILL.md"
JANGYEONGSIL_OPENAI_YAML_PATH = REPO_ROOT / ".agents" / "skills" / "jangyeongsil" / "agents" / "openai.yaml"
JIPHYEONJEON_OPENAI_YAML_PATH = REPO_ROOT / ".agents" / "skills" / "jiphyeonjeon" / "agents" / "openai.yaml"
README_PATH = SEJONG_ROOT / "README.md"
ROUTER_PATH = SEJONG_ROOT / "ROUTER.md"
REPO_CONTEXT_PATH = SEJONG_ROOT / "REPO_CONTEXT.md"
PROTOCOL_PATH = SEJONG_ROOT / "PROTOCOL.md"
SEUNGJEONGWON_EXECUTOR_PATH = SEJONG_ROOT / "SEUNGJEONGWON_EXECUTOR.md"
VALIDATION_PATH = SEJONG_ROOT / "VALIDATION.md"
ARTIFACT_STORAGE_PATH = SEJONG_ROOT / "ARTIFACT_STORAGE.md"
TEAM_EXECUTOR_PATH = SEJONG_ROOT / "TEAM_EXECUTOR.md"
HOOKS_PATH = SEJONG_ROOT / "HOOKS.md"
AMBIGUITY_REGISTER_PATH = SEJONG_ROOT / "AMBIGUITY_REGISTER.md"
AMBIGUITY_REGISTER_SCHEMA_PATH = SEJONG_ROOT / "ambiguity-register.schema.json"
SECURITY_PATH = SEJONG_ROOT / "SECURITY.md"
SILLOK_TRACE_PATH = SEJONG_ROOT / "SILLOK_TRACE.md"
CONTEXT_SCHEMA_PATH = SEJONG_ROOT / "king-sejong-context.schema.json"
CONTEXT_EXAMPLE_PATH = SEJONG_ROOT / "examples" / "king-sejong-context.example.json"
HOOK_SCRIPT_PATH = SEJONG_ROOT / "scripts" / "king_sejong_hooks.py"
SILLOK_TRACE_SCRIPT_PATH = SEJONG_ROOT / "scripts" / "sillok_trace.py"

UIGWE_SKILL_LINE_BUDGET = 320
SEJONG_SKILL_LINE_BUDGET = 90
COURT_HELPER_SKILL_LINE_BUDGET = 80

SCENARIO_IDS = (
    "instruction-routing-modes",
    "instruction-live-session-gates",
    "instruction-output-contract",
    "instruction-recursive-decomposition",
    "instruction-validation-benchmark",
    "instruction-sejong-boundary",
    "instruction-cross-stage-helper-calls",
    "instruction-research-to-uigwe-promotion",
    "instruction-court-skill-frontdoors",
    "instruction-bounded-parallelism",
    "instruction-king-sejong-hooks",
    "instruction-sejong-continuation",
    "instruction-ambiguity-register",
    "instruction-sejong-self-modification",
    "instruction-artifact-storage",
    "instruction-repo-context-refresh",
    "instruction-sillok-security-trace",
    "instruction-compression-budget",
)

REQUIRED_GUARDRAIL_SCENARIOS = {
    "instruction-bounded-parallelism",
    "instruction-king-sejong-hooks",
    "instruction-sejong-continuation",
    "instruction-ambiguity-register",
    "instruction-research-to-uigwe-promotion",
    "instruction-sejong-self-modification",
    "instruction-artifact-storage",
    "instruction-repo-context-refresh",
    "instruction-sillok-security-trace",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark Uigwe and Sejong instruction-surface guardrails.")
    parser.add_argument("--task-set", default=str(TASK_SET_PATH), help="Frozen instruction-surface task set to load.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown scorecards.")
    parser.add_argument("--require-targets", action="store_true", help="Exit non-zero unless all guardrail targets pass.")
    return parser.parse_args()


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def line_count(path: Path) -> int:
    return len(load_text(path).splitlines())


def contains_all(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    missing = [needle for needle in needles if needle not in text]
    return not missing, missing


def check(name: str, passed: bool, detail: str, *, missing: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": name,
        "passed": passed,
        "detail": detail,
    }
    if missing:
        payload["missing"] = missing
    return payload


def evaluate_routing() -> list[dict[str, Any]]:
    skill = load_text(UIGWE_SKILL_PATH)
    required = [
        "Use when a user explicitly invokes `uigwe`",
        "## Do Not Use When",
        "`auto`",
        "`full`",
        "`design-to-plan`",
        "`decompose-only`",
        "Mode Resolution",
    ]
    passed, missing = contains_all(skill, required)
    return [
        check(
            "routing_terms_present",
            passed,
            "Uigwe trigger, non-trigger, and entry-mode terms remain visible in SKILL.md.",
            missing=missing,
        )
    ]


def evaluate_live_session() -> list[dict[str, Any]]:
    skill = load_text(UIGWE_SKILL_PATH)
    readme = load_text(README_PATH)
    required = [
        "Do not silently complete `deep-interview` or `brainstorming` from one ambiguous brief.",
        "Ask targeted clarification questions in small batches",
        "Do not mark an approval gate as `waived` in a live session unless the user explicitly says to skip approval.",
    ]
    passed, missing = contains_all(skill, required)
    readme_passed = "In live chat usage, Uigwe is supposed to do that interactively." in readme
    return [
        check("live_session_rules_present", passed, "Live-session clarification and approval rules remain in SKILL.md.", missing=missing),
        check("readme_live_session_summary_present", readme_passed, "README still summarizes interactive live-session behavior."),
    ]


def evaluate_output_contract() -> list[dict[str, Any]]:
    skill = load_text(UIGWE_SKILL_PATH)
    required = [
        "Intent Packet",
        "Design Packet",
        "Plan Packet",
        "spec.md",
        "rationale.md",
        "goal-tree.json",
        "Do not treat prose summaries alone as completion.",
    ]
    passed, missing = contains_all(skill, required)
    return [
        check("artifact_contract_present", passed, "Canonical Uigwe output artifacts remain explicit.", missing=missing)
    ]


def evaluate_recursive_decomposition() -> list[dict[str, Any]]:
    skill = load_text(UIGWE_SKILL_PATH)
    protocol = load_text(PROTOCOL_PATH)
    executor = load_text(SEUNGJEONGWON_EXECUTOR_PATH)
    seungjeongwon_skill = load_text(SEUNGJEONGWON_SKILL_PATH)
    combined = "\n".join([skill, protocol, executor, seungjeongwon_skill])
    required = [
        "select -> review -> reselect",
        "At each expandable node, Uigwe treats that node as a local objective.",
        "select candidate child objectives, review whether they satisfy the parent objective, reselect when they are weak or invalid",
        "fail to satisfy the parent node objective",
        "Stop descending only when the selected node satisfies handoff-leaf readiness.",
        "Seungjeongwon owns todo listup, todo verification, subtodo decomposition",
        "When Codex todo tooling is available, Seungjeongwon uses it as the user-visible execution board.",
        "append a redefinition event todo",
        "replacement todo as a new item",
        "Use the execution attempt ledger, not new visible todos, for small implementation hypotheses",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check(
            "recursive_decomposition_contract_present",
            passed,
            "Uigwe decomposition remains a recursive select-review-reselect loop down to Seungjeongwon handoff leaves.",
            missing=missing,
        )
    ]


def evaluate_validation_benchmark() -> list[dict[str, Any]]:
    skill = load_text(UIGWE_SKILL_PATH)
    validation = load_text(VALIDATION_PATH)
    readme = load_text(README_PATH)
    required_validation = [
        "Baseline first",
        "Task-specific scoring",
        "benchmark_instruction_surface.py --write --require-targets",
        "examples/validation/uigwe-seed-task-set.json",
        "Limited Executor/Consumer Dry Run",
    ]
    validation_passed, validation_missing = contains_all(validation, required_validation)
    skill_passed = "VALIDATION.md" in skill and "benchmark_instruction_surface.py --write --require-targets" in skill
    readme_passed = "benchmark_instruction_surface.py --write --require-targets" in readme
    return [
        check("validation_doc_contract_present", validation_passed, "VALIDATION.md defines baseline, scoring, benchmark, and dry-run expectations.", missing=validation_missing),
        check("skill_names_validation_benchmark", skill_passed, "Uigwe SKILL.md points improvement work at the validation benchmark."),
        check("readme_names_validation_benchmark", readme_passed, "docs/sejong README exposes the validation benchmark command."),
    ]


def evaluate_sejong_boundary() -> list[dict[str, Any]]:
    skill = load_text(SEJONG_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    required = [
        "It is not a shim over another skill.",
        "The router must call into the Uigwe skill or protocol surface rather than duplicating its packet rules.",
        "It does not weaken Uigwe live-session approval gates.",
        "Sejong keeps Uigwe focused on its strongest job",
    ]
    passed, missing = contains_all("\n".join([skill, router]), required)
    return [
        check("sejong_uigwe_boundary_present", passed, "Sejong remains a router/front door and does not duplicate Uigwe packet rules.", missing=missing)
    ]


def evaluate_cross_stage_helper_calls() -> list[dict[str, Any]]:
    sejong_skill = load_text(SEJONG_SKILL_PATH)
    jangyeongsil_skill = load_text(JANGYEONGSIL_SKILL_PATH)
    jiphyeonjeon_skill = load_text(JIPHYEONJEON_SKILL_PATH)
    uigwe_skill = load_text(UIGWE_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    protocol = load_text(PROTOCOL_PATH)
    readme = load_text(README_PATH)
    team = load_text(TEAM_EXECUTOR_PATH)
    combined = "\n".join([sejong_skill, jangyeongsil_skill, jiphyeonjeon_skill, uigwe_skill, router, protocol, readme, team])
    required = [
        "Court modes can be the primary route for a request or a bounded helper call inside another active court mode.",
        "`JangYeongsil` can be called as an evidence helper from Sejong, Uigwe, or Jiphyeonjeon",
        "`Jiphyeonjeon` can be called as a decision-support helper from Sejong, Uigwe, JangYeongsil, or Seungjeongwon",
        "A helper call produces bounded evidence or deliberation and then returns to the calling court mode.",
        "Helper calls return to Uigwe and do not approve gates or finalize canonical packets.",
        "`JangYeongsil` and `Jiphyeonjeon` also have thin installed skill front doors",
        "JangYeongsil research can run while Uigwe prepares artifact inventory, mode-readiness, or validation preflight",
        "Jiphyeonjeon option review may run while Uigwe inventories artifacts",
        "Host-native team or teammate messaging is preferred when the runtime officially supports direct worker messages",
        "with `current_surface` set to the helper mode",
        "Helper calls do not approve Uigwe gates, finalize `spec.md`, finalize `rationale.md`, finalize `goal-tree.json`, claim consensus, or override lead synthesis.",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check(
            "cross_stage_helper_calls_present",
            passed,
            "JangYeongsil and Jiphyeonjeon helper calls remain explicit, bounded, and non-authoritative.",
            missing=missing,
        )
    ]


def evaluate_research_to_uigwe_promotion() -> list[dict[str, Any]]:
    sejong_skill = load_text(SEJONG_SKILL_PATH)
    jangyeongsil_skill = load_text(JANGYEONGSIL_SKILL_PATH)
    jiphyeonjeon_skill = load_text(JIPHYEONJEON_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    hooks = load_text(HOOKS_PATH)
    context_schema = load_text(CONTEXT_SCHEMA_PATH)
    hook_script = load_text(HOOK_SCRIPT_PATH)
    combined = "\n".join(
        [sejong_skill, jangyeongsil_skill, jiphyeonjeon_skill, router, hooks, context_schema, hook_script]
    )
    required = [
        "Research-To-Uigwe Promotion Gate",
        "research result is not the conclusion",
        "Research-to-Uigwe rule",
        "research-only",
        "uigwe_promotion_required",
        "next_surface: uigwe",
        "write-like execution",
        "Research or council output must enter Uigwe before write-like execution",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check(
            "research_to_uigwe_promotion_present",
            passed,
            "Decision-prep research must promote to Uigwe instead of ending as a final conclusion.",
            missing=missing,
        )
    ]


def evaluate_court_skill_frontdoors() -> list[dict[str, Any]]:
    jangyeongsil_skill = load_text(JANGYEONGSIL_SKILL_PATH)
    jiphyeonjeon_skill = load_text(JIPHYEONJEON_SKILL_PATH)
    jangyeongsil_ui = load_text(JANGYEONGSIL_OPENAI_YAML_PATH)
    jiphyeonjeon_ui = load_text(JIPHYEONJEON_OPENAI_YAML_PATH)
    router = load_text(ROUTER_PATH)
    team = load_text(TEAM_EXECUTOR_PATH)
    installer = load_text(REPO_ROOT / "scripts" / "install-sejong.sh")
    combined = "\n".join([jangyeongsil_skill, jiphyeonjeon_skill, jangyeongsil_ui, jiphyeonjeon_ui, router, team, installer])
    required = [
        "`JangYeongsil` is the King Sejong evidence and experiment front door.",
        "`Jiphyeonjeon` is the King Sejong discussion and decision-support front door.",
        "source-of-truth routing contract is `../../../docs/sejong/ROUTER.md`",
        "display_name: \"JangYeongsil\"",
        "display_name: \"Jiphyeonjeon\"",
        ".agents/skills/jangyeongsil/",
        ".agents/skills/jiphyeonjeon/",
        "skills/jangyeongsil/",
        "skills/jiphyeonjeon/",
        "Peer messages are allowed only as bounded worker messages inside an open round.",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check(
            "court_skill_frontdoors_present",
            passed,
            "JangYeongsil and Jiphyeonjeon remain installed thin front doors with installer verification.",
            missing=missing,
        )
    ]


def evaluate_bounded_parallelism() -> list[dict[str, Any]]:
    skill = load_text(SEJONG_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    team = load_text(TEAM_EXECUTOR_PATH)
    combined = "\n".join([skill, router, team])
    required = [
        "workers are an optional execution tactic",
        "lead Sejong agent owns routing, synthesis, final decision, and final verification",
        "For parallel Jiphyeonjeon, use bounded briefs",
        "`$team` / `TeamExecutor` wrappers",
        "team_executor.py",
        "${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}/state/team/<run-id>/",
        "must use Sejong-owned state rooted at `${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`",
        "The lead Sejong agent opens and closes each challenge round",
        "sejong.team-mailbox-message/v0.1-draft",
        "send-message",
        "receive-messages",
        "`Uigwe` supports only preflight parallelism before gates",
        "do not use worker or subagent agreement as evidence or approval",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("bounded_parallelism_present", passed, "Parallelism remains optional, bounded, and lead-owned.", missing=missing)
    ]


def evaluate_king_sejong_hooks() -> list[dict[str, Any]]:
    hooks = load_text(HOOKS_PATH)
    context_schema = load_text(CONTEXT_SCHEMA_PATH)
    hook_script = load_text(HOOK_SCRIPT_PATH)
    combined = "\n".join([hooks, context_schema, hook_script])
    required = [
        "UserPromptSubmit",
        "PreToolUse",
        "PermissionRequest",
        "SubagentStop",
        "TaskCreated",
        "TaskCompleted",
        "TeammateIdle",
        "Stop",
        "PreCompact",
        "king-sejong.context/v0.1-draft",
        "protected_paths",
        "required_route_sequence",
        "pending_gates",
        "Hooks are deterministic guardrails, not a complete enforcement boundary.",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("king_sejong_hooks_contract_present", passed, "King Sejong hook guardrails and active context schema remain present.", missing=missing)
    ]


def evaluate_sejong_continuation() -> list[dict[str, Any]]:
    skill = load_text(SEJONG_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    readme = load_text(README_PATH)
    combined = "\n".join([skill, router, readme])
    required = [
        "when continuing an active Sejong workflow that the user has not explicitly ended",
        "follow-up user turns as Sejong turns even when they do not repeat the invocation token",
        "The user should not need to retype `$sejong`",
        "until the user explicitly exits Sejong or switches to another non-Sejong workflow",
        "This continuity is conversational state, not permanent memory.",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("sejong_continuation_present", passed, "Sejong invocation persists across follow-up turns until explicit exit or non-Sejong handoff.", missing=missing)
    ]


def evaluate_ambiguity_register() -> list[dict[str, Any]]:
    sejong_skill = load_text(SEJONG_SKILL_PATH)
    uigwe_skill = load_text(UIGWE_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    protocol = load_text(PROTOCOL_PATH)
    hooks = load_text(HOOKS_PATH)
    register = load_text(AMBIGUITY_REGISTER_PATH)
    register_schema = load_text(AMBIGUITY_REGISTER_SCHEMA_PATH)
    hook_script = load_text(HOOK_SCRIPT_PATH)
    combined = "\n".join([sejong_skill, uigwe_skill, router, protocol, hooks, register, register_schema, hook_script])
    required = [
        "sejong.ambiguity-register/v0.1-draft",
        "artifact_refs",
        "readiness_percent",
        "blocking_count",
        "open",
        "resolved",
        "waived",
        "readiness is `100%`",
        "free-response",
        "Stop` blocks completion when any referenced register has open ambiguities",
        "PreCompact` blocks compaction when an ambiguity-register reference is broken",
        "UserPromptSubmit` injects a compact register summary",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check(
            "ambiguity_register_contract_present",
            passed,
            "Ambiguity register remains external, readiness-gated, and hook-enforced.",
            missing=missing,
        )
    ]


def evaluate_sejong_self_modification() -> list[dict[str, Any]]:
    skill = load_text(SEJONG_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    readme = load_text(README_PATH)
    combined = "\n".join([skill, router, readme])
    required = [
        "Changes to Sejong itself need a higher routing bar than ordinary repository edits.",
        "Jiphyeonjeon decision -> Uigwe handoff-contract planning -> Seungjeongwon actionable decomposition, execution, and verification",
        "Material self-modification includes changes to:",
        "Use `Jiphyeonjeon` when the policy, behavior, naming, or boundary decision is not already settled.",
        "`Sejong direct` remains allowed for narrow non-behavioral maintenance",
        "material behavior changes should follow the full Sejong chain",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("sejong_self_modification_guard_present", passed, "Material Sejong self-modification requires Jiphyeonjeon, Uigwe, and Seungjeongwon.", missing=missing)
    ]


def evaluate_artifact_storage() -> list[dict[str, Any]]:
    storage = load_text(ARTIFACT_STORAGE_PATH)
    router = load_text(ROUTER_PATH)
    readme = load_text(README_PATH)
    combined = "\n".join([storage, router, readme])
    required = [
        "external nontracked",
        "`${SEJONG_HOME:-${CODEX_HOME:-~/.codex}/sejong}`",
        "tracked repository files are created only when the user explicitly asks",
        "Normal installation must not prompt for artifact tracking behavior.",
        "When artifacts are generated, report the external run directory and whether any tracked repository files were created.",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("artifact_storage_policy_present", passed, "Artifact storage remains external and nontracked by default with explicit promotion only.", missing=missing)
    ]


def evaluate_repo_context_refresh() -> list[dict[str, Any]]:
    skill = load_text(SEJONG_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    repo_context = load_text(REPO_CONTEXT_PATH)
    readme = load_text(README_PATH)
    combined = "\n".join([skill, router, repo_context, readme])
    required = [
        "guarded repo-context promotion workflow",
        "`init`",
        "`refresh`",
        "Produce a candidate diff before changing tracked files.",
        "explicit user approval",
        "always-on automatic updater",
        "Do not copy this source repository's `AGENTS.md` into target repositories.",
        "instruction pollution checks",
        "REPO_CONTEXT.md",
        "Use Sejong repo-context init/refresh",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("repo_context_refresh_contract_present", passed, "Repo-context init/refresh remains guarded, candidate-diff first, and approval-gated.", missing=missing)
    ]


def evaluate_sillok_security_trace() -> list[dict[str, Any]]:
    skill = load_text(SEJONG_SKILL_PATH)
    router = load_text(ROUTER_PATH)
    storage = load_text(ARTIFACT_STORAGE_PATH)
    security = load_text(SECURITY_PATH)
    sillok = load_text(SILLOK_TRACE_PATH)
    trace_script = load_text(SILLOK_TRACE_SCRIPT_PATH)
    combined = "\n".join([skill, router, storage, security, sillok, trace_script])
    required = [
        "Sillok trace",
        "sillok-trace-event.schema.json",
        "private_data",
        "untrusted_content",
        "external_action",
        "human_approval_ref",
        "LETHAL_TRIFECTA",
        "Record security-sensitive tool calls and decisions",
    ]
    passed, missing = contains_all(combined, required)
    return [
        check("sillok_security_trace_contract_present", passed, "Sillok trace and security guardrails remain visible and testable.", missing=missing)
    ]


def evaluate_compression() -> list[dict[str, Any]]:
    uigwe_lines = line_count(UIGWE_SKILL_PATH)
    sejong_lines = line_count(SEJONG_SKILL_PATH)
    jangyeongsil_lines = line_count(JANGYEONGSIL_SKILL_PATH)
    jiphyeonjeon_lines = line_count(JIPHYEONJEON_SKILL_PATH)
    skill = load_text(UIGWE_SKILL_PATH)
    return [
        check(
            "uigwe_skill_line_budget",
            uigwe_lines <= UIGWE_SKILL_LINE_BUDGET,
            f"Uigwe SKILL.md line count is {uigwe_lines}; budget is {UIGWE_SKILL_LINE_BUDGET}.",
        ),
        check(
            "sejong_skill_line_budget",
            sejong_lines <= SEJONG_SKILL_LINE_BUDGET,
            f"Sejong SKILL.md line count is {sejong_lines}; budget is {SEJONG_SKILL_LINE_BUDGET}.",
        ),
        check(
            "jangyeongsil_skill_line_budget",
            jangyeongsil_lines <= COURT_HELPER_SKILL_LINE_BUDGET,
            f"JangYeongsil SKILL.md line count is {jangyeongsil_lines}; budget is {COURT_HELPER_SKILL_LINE_BUDGET}.",
        ),
        check(
            "jiphyeonjeon_skill_line_budget",
            jiphyeonjeon_lines <= COURT_HELPER_SKILL_LINE_BUDGET,
            f"Jiphyeonjeon SKILL.md line count is {jiphyeonjeon_lines}; budget is {COURT_HELPER_SKILL_LINE_BUDGET}.",
        ),
        check(
            "validation_detail_lives_in_reference",
            "VALIDATION.md" in skill,
            "Validation detail is routed to a reference document rather than expanded inline.",
        ),
    ]


EVALUATORS: dict[str, Callable[[], list[dict[str, Any]]]] = {
    "instruction-routing-modes": evaluate_routing,
    "instruction-live-session-gates": evaluate_live_session,
    "instruction-output-contract": evaluate_output_contract,
    "instruction-recursive-decomposition": evaluate_recursive_decomposition,
    "instruction-validation-benchmark": evaluate_validation_benchmark,
    "instruction-sejong-boundary": evaluate_sejong_boundary,
    "instruction-cross-stage-helper-calls": evaluate_cross_stage_helper_calls,
    "instruction-research-to-uigwe-promotion": evaluate_research_to_uigwe_promotion,
    "instruction-court-skill-frontdoors": evaluate_court_skill_frontdoors,
    "instruction-bounded-parallelism": evaluate_bounded_parallelism,
    "instruction-king-sejong-hooks": evaluate_king_sejong_hooks,
    "instruction-sejong-continuation": evaluate_sejong_continuation,
    "instruction-ambiguity-register": evaluate_ambiguity_register,
    "instruction-sejong-self-modification": evaluate_sejong_self_modification,
    "instruction-artifact-storage": evaluate_artifact_storage,
    "instruction-repo-context-refresh": evaluate_repo_context_refresh,
    "instruction-sillok-security-trace": evaluate_sillok_security_trace,
    "instruction-compression-budget": evaluate_compression,
}


def expectation_text_for_scenario(scenario_id: str) -> str:
    base = [
        load_text(ROUTER_PATH),
        load_text(REPO_CONTEXT_PATH),
        load_text(ARTIFACT_STORAGE_PATH),
        load_text(TEAM_EXECUTOR_PATH),
        load_text(HOOKS_PATH),
        load_text(CONTEXT_SCHEMA_PATH),
        load_text(CONTEXT_EXAMPLE_PATH),
        load_text(HOOK_SCRIPT_PATH),
        load_text(SECURITY_PATH),
        load_text(SILLOK_TRACE_PATH),
        load_text(SILLOK_TRACE_SCRIPT_PATH),
    ]
    if scenario_id == "instruction-artifact-storage":
        return "\n".join([load_text(ARTIFACT_STORAGE_PATH), load_text(ROUTER_PATH), load_text(HOOKS_PATH)])
    if scenario_id == "instruction-bounded-parallelism":
        return "\n".join([load_text(TEAM_EXECUTOR_PATH), load_text(ROUTER_PATH), load_text(HOOKS_PATH)])
    if scenario_id == "instruction-ambiguity-register":
        return "\n".join(
            [
                load_text(AMBIGUITY_REGISTER_PATH),
                load_text(AMBIGUITY_REGISTER_SCHEMA_PATH),
                load_text(HOOKS_PATH),
                load_text(HOOK_SCRIPT_PATH),
                load_text(UIGWE_SKILL_PATH),
                load_text(ROUTER_PATH),
                load_text(ARTIFACT_STORAGE_PATH),
            ]
        )
    if scenario_id == "instruction-research-to-uigwe-promotion":
        return "\n".join(
            [
                load_text(ROUTER_PATH),
                load_text(SEJONG_SKILL_PATH),
                load_text(JANGYEONGSIL_SKILL_PATH),
                load_text(JIPHYEONJEON_SKILL_PATH),
                load_text(HOOKS_PATH),
                load_text(CONTEXT_SCHEMA_PATH),
                load_text(HOOK_SCRIPT_PATH),
            ]
        )
    return "\n".join(base)


def evaluate_guardrail_expectations(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    scenario_id = scenario["id"]
    expectations = scenario.get("guardrail_expectations")
    checks: list[dict[str, Any]] = []

    if scenario_id in REQUIRED_GUARDRAIL_SCENARIOS and not expectations:
        return [
            check(
                "typed_guardrail_expectations_present",
                False,
                "Scenario requires typed guardrail expectations.",
                missing=["guardrail_expectations"],
            )
        ]
    if not expectations:
        return checks

    target_text = expectation_text_for_scenario(scenario_id)
    for field_name, values in expectations.items():
        if not values:
            checks.append(check(f"guardrail_{field_name}", False, f"{field_name} must not be empty.", missing=[field_name]))
            continue
        passed, missing = contains_all(target_text, values)
        checks.append(
            check(
                f"guardrail_{field_name}",
                passed,
                f"Typed guardrail expectation {field_name} is represented in the instruction surface.",
                missing=missing,
            )
        )
    return checks


def validate_task_set(task_set: dict[str, Any]) -> None:
    scenario_ids = tuple(scenario["id"] for scenario in task_set.get("scenarios", []))
    if scenario_ids != SCENARIO_IDS:
        raise ValueError(f"Unexpected instruction-surface scenarios: {scenario_ids}")


def scenario_status(checks: list[dict[str, Any]]) -> str:
    return "pass" if all(item["passed"] for item in checks) else "fail"


def scenario_score(checks: list[dict[str, Any]]) -> float:
    if not checks:
        return 0.0
    return round(sum(1 for item in checks if item["passed"]) / len(checks), 4)


def build_scorecard(task_set: dict[str, Any]) -> dict[str, Any]:
    validate_task_set(task_set)

    results: list[dict[str, Any]] = []
    for scenario in task_set["scenarios"]:
        checks = EVALUATORS[scenario["id"]]()
        checks.extend(evaluate_guardrail_expectations(scenario))
        status = scenario_status(checks)
        results.append(
            {
                "scenario_id": scenario["id"],
                "title": scenario["title"],
                "status": status,
                "score": scenario_score(checks),
                "checks": checks,
                "blockers": [] if status == "pass" else [item["id"] for item in checks if not item["passed"]],
                "notes": ["Deterministic instruction-surface guardrail check."],
            }
        )

    pass_count = sum(1 for result in results if result["status"] == "pass")
    fail_count = len(results) - pass_count
    average_score = round(sum(result["score"] for result in results) / len(results), 4)
    meets_targets = pass_count == len(results)

    return {
        "format": "uigwe.validation-scorecard/v0.1-draft",
        "metadata": {
            "id": "uigwe-instruction-surface-scorecard",
            "task_set_id": task_set["metadata"]["id"],
            "generated_at": now_utc_iso(),
            "system_under_test": "sejong-uigwe",
            "runner": rel(SCRIPT_PATH),
        },
        "aggregate": {
            "scenario_count": len(results),
            "pass_count": pass_count,
            "partial_count": 0,
            "fail_count": fail_count,
            "average_score": average_score,
            "meets_targets": meets_targets,
        },
        "scenario_results": results,
        "notes": [
            "This scorecard checks instruction-surface guardrails only.",
            "It does not replace frozen planning benchmarks or consumer dry runs.",
        ],
    }


def preserve_generated_at_when_unchanged(scorecard: dict[str, Any], existing_path: Path) -> dict[str, Any]:
    if not existing_path.exists():
        return scorecard
    try:
        existing = load_json(existing_path)
    except Exception:
        return scorecard

    existing_generated_at = existing.get("metadata", {}).get("generated_at")
    candidate = json.loads(json.dumps(scorecard))
    if existing_generated_at:
        candidate.setdefault("metadata", {})["generated_at"] = existing_generated_at
    if candidate == existing:
        scorecard["metadata"]["generated_at"] = existing_generated_at
    return scorecard


def markdown_summary(scorecard: dict[str, Any]) -> str:
    aggregate = scorecard["aggregate"]
    lines = [
        "# Uigwe Instruction Surface Scorecard",
        "",
        f"- Task set: `{scorecard['metadata']['task_set_id']}`",
        f"- Generated at: `{scorecard['metadata']['generated_at']}`",
        f"- Status: `{'pass' if aggregate['meets_targets'] else 'fail'}`",
        f"- Average score: `{aggregate['average_score']}`",
        f"- Pass/fail: `{aggregate['pass_count']}/{aggregate['fail_count']}`",
        "",
        "## Scenarios",
    ]
    for result in scorecard["scenario_results"]:
        lines.append(f"- `{result['scenario_id']}`: `{result['status']}` ({result['score']})")
        for check_result in result["checks"]:
            if not check_result["passed"]:
                missing = f" Missing: {', '.join(check_result.get('missing', []))}" if check_result.get("missing") else ""
                lines.append(f"  - `{check_result['id']}` failed. {check_result['detail']}{missing}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    task_set = load_json(Path(args.task_set))
    scorecard = build_scorecard(task_set)

    if args.write:
        scorecard = preserve_generated_at_when_unchanged(scorecard, SCORECARD_PATH)
        SCORECARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCORECARD_PATH.write_text(json.dumps(scorecard, indent=2) + "\n", encoding="utf-8")
        SUMMARY_PATH.write_text(markdown_summary(scorecard), encoding="utf-8")

    print(markdown_summary(scorecard).rstrip())

    if args.require_targets and not scorecard["aggregate"]["meets_targets"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
