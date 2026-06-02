#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SEJONG_ROOT = REPO_ROOT / "docs" / "sejong"
POLICY_DEFAULTS_PATH = SEJONG_ROOT / "policy.defaults.json"


INTENT_QUESTION_MAP = {
    "goal_clarity": "What is the concrete goal?",
    "why_now_clarity": "Why does this matter now?",
    "scope_clarity": "What is explicitly in scope?",
    "non_goal_clarity": "What is explicitly out of scope?",
    "decision_boundary_clarity": "Which decisions may Uigwe make without confirmation, and which require your approval?",
    "constraint_clarity": "What constraints must the plan respect?",
    "acceptance_clarity": "What does success look like in testable terms?",
    "open_question_resolution": "Which unresolved questions should be answered before planning advances?",
}

DESIGN_QUESTION_MAP = {
    "problem_frame_quality": "What problem framing should this design optimize for?",
    "selected_approach_quality": "Which approach is currently selected and why is it the right baseline?",
    "alternatives_quality": "What credible alternatives should remain in comparison?",
    "tradeoff_clarity": "What trade-offs matter most in this design?",
    "decision_coherence": "Which design decisions are already fixed?",
    "assumption_quality": "Which assumptions should stay visible during planning?",
    "risk_quality": "What risks need mitigation before decomposition?",
    "validation_plan_quality": "How should this design be validated before execution planning?",
}
STAGE_METADATA = {
    "deep-interview": {
        "stage_id": "intent_clarification",
        "stage_label": "기획 명확화",
        "score_key": "intent_readiness",
        "header": "Intent",
    },
    "brainstorming": {
        "stage_id": "design_clarification",
        "stage_label": "설계 명확화",
        "score_key": "design_readiness",
        "header": "Design",
    },
    "decomposition": {
        "stage_id": "executor_handoff_contract",
        "stage_label": "실행 계약화",
        "score_key": "handoff_readiness",
        "header": "Handoff",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Uigwe live-session readiness and next action.")
    parser.add_argument("input_path", help="Path to a JSON state file")
    parser.add_argument("--json", action="store_true", help="Print the result as JSON")
    parser.add_argument("--write-register", help="Write the generated ambiguity register to this path")
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy_defaults() -> dict[str, Any]:
    return load_json(POLICY_DEFAULTS_PATH)


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))


def text_score(value: Any) -> float:
    if not isinstance(value, str):
        return 0.0
    stripped = value.strip()
    if not stripped:
        return 0.0
    if len(stripped) >= 80 or len(stripped.split()) >= 12:
        return 1.0
    if len(stripped) >= 35 or len(stripped.split()) >= 6:
        return 0.8
    return 0.45


def list_score(items: Any, *, full_count: int = 2, partial_score: float = 0.55) -> float:
    if not isinstance(items, list) or not items:
        return 0.0
    if len(items) >= full_count:
        return 1.0
    return partial_score


def decision_boundary_score(items: Any) -> float:
    if not isinstance(items, list) or not items:
        return 0.0
    complete = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("decision") and "allowed_without_confirmation" in item:
            complete += 1
    if complete >= 1:
        return 1.0
    return 0.4


def acceptance_score(items: Any) -> float:
    if not isinstance(items, list) or not items:
        return 0.0
    complete = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("description") and item.get("verification"):
            complete += 1
    if complete >= 2:
        return 1.0
    if complete == 1:
        return 0.55
    return 0.0


def open_question_resolution_score(items: Any) -> float:
    if items is None:
        return 1.0
    if not isinstance(items, list):
        return 0.0
    unresolved = len([item for item in items if str(item).strip()])
    if unresolved == 0:
        return 1.0
    return clamp_score(1.0 - min(unresolved, 4) / 4.0)


def selected_approach_score(payload: Any) -> float:
    if not isinstance(payload, dict):
        return 0.0
    title = text_score(payload.get("title"))
    summary = text_score(payload.get("summary"))
    if title == 0.0 and summary == 0.0:
        return 0.0
    if title > 0.0 and summary > 0.0:
        return 1.0
    return 0.45


def risk_score(items: Any) -> float:
    if not isinstance(items, list) or not items:
        return 0.0
    complete = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("description") and item.get("mitigation"):
            complete += 1
    if complete >= 1:
        return 1.0
    return 0.4


def weighted_readiness_score(dimensions: dict[str, float], weights: dict[str, float]) -> float:
    return clamp_score(sum(dimensions[name] * weights[name] for name in weights))


def top_weak_dimensions(dimensions: dict[str, float], *, cutoff: float = 0.85) -> list[str]:
    weak = [name for name, score in dimensions.items() if score < cutoff]
    return sorted(weak, key=lambda name: (dimensions[name], name))


def dedupe_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def generate_intent_questions(intent: dict[str, Any], weak_dimensions: list[str]) -> list[str]:
    questions: list[str] = []
    for dimension in weak_dimensions:
        if dimension == "open_question_resolution":
            open_questions = intent.get("open_questions") or []
            if isinstance(open_questions, list):
                questions.extend(str(question).strip() for question in open_questions if str(question).strip())
            continue
        questions.append(INTENT_QUESTION_MAP[dimension])
    return dedupe_preserving_order(questions)[:6]


def generate_design_questions(design: dict[str, Any], weak_dimensions: list[str]) -> list[str]:
    questions = [DESIGN_QUESTION_MAP[dimension] for dimension in weak_dimensions]
    return dedupe_preserving_order(questions)[:6]


def resolve_profile(state: dict[str, Any]) -> str:
    profile = state.get("profile")
    if profile in {"greenfield", "brownfield"}:
        return profile
    if state.get("mode") == "decompose-only":
        return "brownfield"
    return "greenfield"


def intent_dimensions(intent: dict[str, Any]) -> dict[str, float]:
    return {
        "goal_clarity": text_score(intent.get("goal")),
        "why_now_clarity": text_score(intent.get("why_now")),
        "scope_clarity": list_score(intent.get("in_scope")),
        "non_goal_clarity": list_score(intent.get("non_goals")),
        "decision_boundary_clarity": decision_boundary_score(intent.get("decision_boundaries")),
        "constraint_clarity": list_score(intent.get("constraints")),
        "acceptance_clarity": acceptance_score(intent.get("acceptance_criteria")),
        "open_question_resolution": open_question_resolution_score(intent.get("open_questions")),
    }


def design_dimensions(design: dict[str, Any]) -> dict[str, float]:
    return {
        "problem_frame_quality": text_score(design.get("problem_frame")),
        "selected_approach_quality": selected_approach_score(design.get("selected_approach")),
        "alternatives_quality": list_score(design.get("alternatives"), full_count=2),
        "tradeoff_clarity": list_score(design.get("tradeoffs")),
        "decision_coherence": list_score(design.get("key_decisions")),
        "assumption_quality": list_score(design.get("assumptions"), full_count=1, partial_score=0.4),
        "risk_quality": risk_score(design.get("risks")),
        "validation_plan_quality": list_score(design.get("validation_plan"), full_count=1, partial_score=0.4),
    }


def approval_satisfied(payload: dict[str, Any], *, live_session: bool) -> bool:
    status = payload.get("approval_status")
    if status == "approved":
        return True
    if status == "waived":
        return not live_session or bool(payload.get("explicit_approval_waived"))
    return False


def build_score_block(name: str, score: float, threshold: float, dimensions: dict[str, float]) -> dict[str, Any]:
    return {
        "metric": name,
        "score": score,
        "threshold": threshold,
        "dimensions": dimensions,
        "weak_dimensions": top_weak_dimensions(dimensions),
    }


def missing_required_dimensions(dimensions: dict[str, float], required_names: list[str]) -> list[str]:
    return [name for name in required_names if dimensions.get(name, 0.0) <= 0.0]


def ask_action(stage: str, questions: list[str], score_block: dict[str, Any], *, action_type: str = "ask_questions") -> dict[str, Any]:
    return {
        "type": action_type,
        "stage": stage,
        "summary": f"{score_block['metric']} is below threshold and needs user clarification.",
        "questions": questions,
    }


def approval_action(stage: str, approval_target: str) -> dict[str, Any]:
    return {
        "type": "request_approval",
        "stage": stage,
        "approval_target": approval_target,
        "summary": f"{approval_target} is ready and waiting for user approval.",
    }


def ready_action(stage: str) -> dict[str, Any]:
    return {
        "type": "ready_for_decomposition",
        "stage": stage,
        "summary": "Readiness thresholds and approval gates are satisfied. Execution planning may begin.",
    }


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stage_metadata(stage: str) -> dict[str, str]:
    for metadata in STAGE_METADATA.values():
        if stage == metadata["stage_id"]:
            return metadata
    return STAGE_METADATA.get(stage, STAGE_METADATA["decomposition"])


def ambiguity_options() -> list[dict[str, Any]]:
    return [
        {
            "id": "answer-now",
            "label": "Answer now (Recommended)",
            "description": "Provide the missing decision or detail before the next stage.",
            "recommended": True,
        },
        {
            "id": "waive-or-proceed",
            "label": "Waive / proceed",
            "description": "Explicitly skip this ambiguity and accept the risk.",
            "recommended": False,
        },
    ]


def action_questions(action: dict[str, Any]) -> list[str]:
    questions = action.get("questions")
    if isinstance(questions, list) and questions:
        return [str(question) for question in questions if str(question).strip()]
    if action.get("type") == "request_approval":
        return [f"Approve {action.get('approval_target', 'the current stage summary')} for the next stage?"]
    return []


def readiness_percent_for_stage(result: dict[str, Any], stage: str) -> int:
    metadata = stage_metadata(stage)
    score_key = metadata["score_key"]
    score_block = result.get("scores", {}).get(score_key)
    if isinstance(score_block, dict) and isinstance(score_block.get("score"), (int, float)):
        return max(0, min(100, int(round(float(score_block["score"]) * 100))))
    if result.get("action", {}).get("type") == "request_approval":
        return 100
    return 0


def build_ambiguity_register(result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any] | None:
    action = result.get("action") or {}
    questions = action_questions(action)
    if not questions:
        return None

    stage = str(action.get("stage") or "decomposition")
    metadata = stage_metadata(stage)
    now = str(state.get("last_updated_at") or now_utc_iso())
    ambiguities = []
    for index, question in enumerate(questions, start=1):
        ambiguities.append(
            {
                "id": f"{metadata['stage_id']}-q{index}",
                "question": question,
                "why_it_matters": "This unresolved decision can change the Uigwe stage contract or downstream execution boundary.",
                "options": ambiguity_options(),
                "free_response_allowed": True,
                "status": "pending",
                "blocking": True,
                "evidence_refs": [],
                "updated_at": now,
            }
        )

    return {
        "format": "sejong.ambiguity-register/v0.1-draft",
        "metadata": {
            "id": str(state.get("ambiguity_register_id") or f"ambiguity-{metadata['stage_id']}"),
            "active_context_id": str(state.get("active_context_id") or "unknown-active-context"),
            "route_id": str(state.get("route_id") or "unknown-route"),
            "created_at": str(state.get("created_at") or now),
        },
        "stage_id": metadata["stage_id"],
        "stage_label": metadata["stage_label"],
        "readiness_percent": readiness_percent_for_stage(result, stage),
        "blocking_count": len(ambiguities),
        "ambiguities": ambiguities,
        "next_required_user_action": (
            f"Answer the pending {metadata['stage_label']} question before the next stage, "
            "or explicitly waive it."
        ),
        "last_updated_at": now,
    }


def build_structured_choice_requests(register: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not register:
        return []
    header = stage_metadata(str(register.get("stage_id", ""))).get("header", "Uigwe")
    requests = []
    for ambiguity in register.get("ambiguities", []):
        if not isinstance(ambiguity, dict):
            continue
        requests.append(
            {
                "adapter": "codex_structured_choice",
                "id": ambiguity.get("id"),
                "header": header,
                "question": ambiguity.get("question"),
                "options": ambiguity.get("options", []),
                "free_response_allowed": bool(ambiguity.get("free_response_allowed", True)),
            }
        )
    return requests


def attach_live_runtime_outputs(result: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    register = build_ambiguity_register(result, state)
    if register:
        result["ambiguity_register"] = register
        result["structured_choice_requests"] = build_structured_choice_requests(register)
    return result


def evaluate_live_session(state: dict[str, Any]) -> dict[str, Any]:
    policy_defaults = load_policy_defaults()
    live_session = bool(state.get("live_session", True))
    mode = state.get("mode")
    if mode not in {"full", "design-to-plan", "decompose-only"}:
        raise ValueError(f"Unsupported mode: {mode}")

    profile = resolve_profile(state)
    profile_defaults = policy_defaults["profiles"][profile]

    intent = state.get("intent") or {}
    design = state.get("design") or {}

    intent_weights = policy_defaults["derived_metrics"]["intent_readiness"]["dimensions"]
    design_weights = policy_defaults["derived_metrics"]["design_readiness"]["dimensions"]
    thresholds = profile_defaults["readiness_thresholds"]

    intent_block = build_score_block(
        "intent_readiness",
        weighted_readiness_score(intent_dimensions(intent), intent_weights),
        thresholds["intent_to_brainstorming"],
        intent_dimensions(intent),
    )
    design_block = build_score_block(
        "design_readiness",
        weighted_readiness_score(design_dimensions(design), design_weights),
        thresholds["design_to_decomposition"],
        design_dimensions(design),
    )

    result = {
        "mode": mode,
        "resolved_profile": profile,
        "live_session": live_session,
        "scores": {
            "intent_readiness": intent_block,
            "design_readiness": design_block,
        },
    }

    intent_required = [
        "goal_clarity",
        "why_now_clarity",
        "scope_clarity",
        "non_goal_clarity",
        "decision_boundary_clarity",
        "constraint_clarity",
        "acceptance_clarity",
    ]
    design_required = [
        "problem_frame_quality",
        "selected_approach_quality",
        "alternatives_quality",
        "tradeoff_clarity",
        "decision_coherence",
        "validation_plan_quality",
    ]
    intent_contract_gaps = missing_required_dimensions(intent_block["dimensions"], intent_required)
    design_contract_gaps = missing_required_dimensions(design_block["dimensions"], design_required)
    result["scores"]["intent_readiness"]["contract_gaps"] = intent_contract_gaps
    result["scores"]["design_readiness"]["contract_gaps"] = design_contract_gaps

    if mode == "full":
        if intent_block["score"] < intent_block["threshold"] or intent_contract_gaps:
            result["action"] = ask_action(
                "deep-interview",
                generate_intent_questions(intent, dedupe_preserving_order(intent_contract_gaps + intent_block["weak_dimensions"])),
                intent_block,
            )
            return attach_live_runtime_outputs(result, state)
        if not approval_satisfied(intent, live_session=live_session):
            result["action"] = approval_action("deep-interview", "intent_summary")
            return attach_live_runtime_outputs(result, state)
        if design_block["score"] < design_block["threshold"] or design_contract_gaps:
            result["action"] = ask_action(
                "brainstorming",
                generate_design_questions(design, dedupe_preserving_order(design_contract_gaps + design_block["weak_dimensions"])),
                design_block,
            )
            return attach_live_runtime_outputs(result, state)
        if not approval_satisfied(design, live_session=live_session):
            result["action"] = approval_action("brainstorming", "design_summary")
            return attach_live_runtime_outputs(result, state)
        result["action"] = ready_action("decomposition")
        return attach_live_runtime_outputs(result, state)

    if mode == "design-to-plan":
        if intent_block["score"] < intent_block["threshold"] or intent_contract_gaps:
            result["action"] = ask_action(
                "deep-interview",
                generate_intent_questions(intent, dedupe_preserving_order(intent_contract_gaps + intent_block["weak_dimensions"])),
                intent_block,
                action_type="reenter_deep_interview",
            )
            return attach_live_runtime_outputs(result, state)
        if "approval_status" in intent and not approval_satisfied(intent, live_session=live_session):
            result["action"] = approval_action("deep-interview", "intent_summary")
            return attach_live_runtime_outputs(result, state)
        if design_block["score"] < design_block["threshold"] or design_contract_gaps:
            result["action"] = ask_action(
                "brainstorming",
                generate_design_questions(design, dedupe_preserving_order(design_contract_gaps + design_block["weak_dimensions"])),
                design_block,
            )
            return attach_live_runtime_outputs(result, state)
        if not approval_satisfied(design, live_session=live_session):
            result["action"] = approval_action("brainstorming", "design_summary")
            return attach_live_runtime_outputs(result, state)
        result["action"] = ready_action("decomposition")
        return attach_live_runtime_outputs(result, state)

    if design_block["score"] < design_block["threshold"] or design_contract_gaps:
        result["action"] = ask_action(
            "brainstorming",
            generate_design_questions(design, dedupe_preserving_order(design_contract_gaps + design_block["weak_dimensions"])),
            design_block,
            action_type="reenter_brainstorming",
        )
        return attach_live_runtime_outputs(result, state)
    if not approval_satisfied(design, live_session=live_session):
        result["action"] = approval_action("brainstorming", "design_summary")
        return attach_live_runtime_outputs(result, state)
    result["action"] = ready_action("decomposition")
    return attach_live_runtime_outputs(result, state)


def main() -> int:
    args = parse_args()
    state = load_json(Path(args.input_path))
    result = evaluate_live_session(state)
    if args.write_register:
        register = result.get("ambiguity_register")
        if register:
            register_path = Path(args.write_register).expanduser()
            register_path.parent.mkdir(parents=True, exist_ok=True)
            register_path.write_text(json.dumps(register, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            result["ambiguity_register_path"] = str(register_path)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["action"]["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
