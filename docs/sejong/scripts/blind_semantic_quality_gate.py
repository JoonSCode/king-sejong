#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKET_FORMAT = "sejong.blind-semantic-packet/v0.1-draft"
KEY_FORMAT = "sejong.blind-semantic-key/v0.1-draft"
JUDGMENT_FORMAT = "sejong.blind-semantic-judgment/v0.1-draft"
GATE_FORMAT = "sejong.blind-semantic-gate/v0.1-draft"
DEFAULT_RUBRIC = [
    "goal_fit",
    "evidence_grounding",
    "completeness",
    "actionability",
    "claim_safety",
    "artifact_fit",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def inferred_artifact_paths(task: dict[str, Any], explicit_paths: list[str]) -> list[str]:
    if explicit_paths:
        return explicit_paths
    contract = task.get("artifact_contract") if isinstance(task.get("artifact_contract"), dict) else {}
    return string_list(contract.get("required_paths"))


def read_artifacts(root: Path, paths: list[str], max_chars: int) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for path in paths:
        artifact_path = root / path
        if not artifact_path.exists():
            artifacts[path] = "<MISSING>"
            continue
        text = artifact_path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars:
            text = text[:max_chars] + "\n<TRUNCATED>"
        artifacts[path] = text
    return artifacts


def semantic_goal(task: dict[str, Any], override: str | None) -> str:
    if override and override.strip():
        return override.strip()
    explicit = task.get("semantic_goal")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    prompt = task.get("prompt")
    if isinstance(prompt, str) and prompt.strip():
        return prompt.strip()
    goal = task.get("goal")
    if isinstance(goal, str) and goal.strip():
        return goal.strip()
    return "Judge which output better satisfies the requested artifact."


def packet_id_for(task: dict[str, Any], baseline: dict[str, Any], candidate: dict[str, Any], seed: str) -> str:
    raw = "|".join(
        [
            str(task.get("task_id")),
            str(baseline.get("run_id")),
            str(candidate.get("run_id")),
            seed,
        ]
    )
    return "blind-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_packet(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    task = load_json(Path(args.task))
    baseline = load_json(Path(args.baseline_result))
    candidate = load_json(Path(args.candidate_result))
    artifact_paths = inferred_artifact_paths(task, args.include)
    if not artifact_paths:
        raise ValueError("No artifact paths provided and task.artifact_contract.required_paths is empty")

    seed = args.seed or f"{task.get('task_id')}:{baseline.get('run_id')}:{candidate.get('run_id')}"
    packet_id = packet_id_for(task, baseline, candidate, seed)
    sides = [
        (
            "baseline",
            {
                "artifacts": read_artifacts(Path(args.baseline_root), artifact_paths, args.max_chars),
            },
        ),
        (
            "candidate",
            {
                "artifacts": read_artifacts(Path(args.candidate_root), artifact_paths, args.max_chars),
            },
        ),
    ]
    random.Random(seed).shuffle(sides)
    blind_outputs = []
    mapping: dict[str, str] = {}
    for blind_id, (side, payload) in zip(("A", "B"), sides):
        blind_outputs.append({"id": blind_id, **payload})
        mapping[blind_id] = side

    packet = {
        "format": PACKET_FORMAT,
        "packet_id": packet_id,
        "generated_at": now_utc(),
        "task_id": task["task_id"],
        "prompt": task["prompt"],
        "goal": semantic_goal(task, args.judge_goal),
        "rubric": string_list(args.rubric) or DEFAULT_RUBRIC,
        "artifact_paths": artifact_paths,
        "outputs": blind_outputs,
        "judge_instructions": [
            "Judge only the artifact contents shown as A and B.",
            "Do not infer which output came from which run.",
            "Do not reward longer text unless it improves the user's stated goal.",
            "Prefer evidence-grounded, complete, actionable, claim-safe artifacts.",
            "Return a judgment with IDs A and B only.",
        ],
    }
    key = {
        "format": KEY_FORMAT,
        "packet_id": packet_id,
        "generated_at": now_utc(),
        "task_id": task["task_id"],
        "seed": seed,
        "mapping": mapping,
        "baseline_run_id": baseline["run_id"],
        "candidate_run_id": candidate["run_id"],
    }
    return packet, key


def score_for(judgment: dict[str, Any], blind_id: str) -> float:
    scores = judgment.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("judgment.scores must be an object")
    payload = scores.get(blind_id)
    if not isinstance(payload, dict):
        raise ValueError(f"judgment missing score for {blind_id}")
    score = payload.get("score")
    if not isinstance(score, (int, float)):
        raise ValueError(f"judgment score for {blind_id} must be numeric")
    return float(score)


def build_gate(args: argparse.Namespace) -> dict[str, Any]:
    packet = load_json(Path(args.packet))
    key = load_json(Path(args.key))
    judgment = load_json(Path(args.judgment))
    if packet.get("format") != PACKET_FORMAT:
        raise ValueError("packet has unexpected format")
    if key.get("format") != KEY_FORMAT:
        raise ValueError("key has unexpected format")
    if judgment.get("format") != JUDGMENT_FORMAT:
        raise ValueError("judgment has unexpected format")
    if packet.get("packet_id") != key.get("packet_id") or packet.get("packet_id") != judgment.get("packet_id"):
        raise ValueError("packet, key, and judgment packet_id must match")

    mapping = key.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("key.mapping must be an object")
    side_scores: dict[str, float] = {}
    for blind_id, side in mapping.items():
        side_scores[str(side)] = score_for(judgment, str(blind_id))

    baseline_score = side_scores.get("baseline")
    candidate_score = side_scores.get("candidate")
    if baseline_score is None or candidate_score is None:
        raise ValueError("mapping must include baseline and candidate")
    delta = round(candidate_score - baseline_score, 4)
    min_delta = float(args.min_delta)
    if delta >= min_delta:
        recommendation = "promote_candidate"
        winner_side = "candidate"
    elif delta <= -min_delta:
        recommendation = "reject_candidate"
        winner_side = "baseline"
    elif judgment.get("winner") == "tie":
        recommendation = "inconclusive"
        winner_side = "tie"
    else:
        recommendation = "keep_shadowing"
        winner_side = "candidate" if delta > 0 else "baseline" if delta < 0 else "tie"

    return {
        "format": GATE_FORMAT,
        "generated_at": now_utc(),
        "packet_id": packet["packet_id"],
        "task_id": packet["task_id"],
        "baseline_run_id": key["baseline_run_id"],
        "candidate_run_id": key["candidate_run_id"],
        "mapping": mapping,
        "blind_winner": judgment.get("winner"),
        "winner_side": winner_side,
        "baseline_score": baseline_score,
        "candidate_score": candidate_score,
        "score_delta": delta,
        "min_delta": min_delta,
        "recommendation": recommendation,
        "confidence": judgment.get("confidence"),
        "judge_notes": judgment.get("judge_notes"),
    }


def pack(args: argparse.Namespace) -> int:
    try:
        packet, key = build_packet(args)
    except Exception as exc:
        print(f"failure: {exc}", file=sys.stderr)
        return 1
    if args.write_packet:
        write_json(Path(args.write_packet), packet)
    if args.write_key:
        write_json(Path(args.write_key), key)
    print(json.dumps({"packet": packet, "key": key}, indent=2, sort_keys=True))
    return 0


def judge_result(args: argparse.Namespace) -> int:
    try:
        payload = build_gate(args)
    except Exception as exc:
        print(f"failure: {exc}", file=sys.stderr)
        return 1
    if args.write:
        write_json(Path(args.write), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.require_promotion and payload["recommendation"] != "promote_candidate":
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and unblind semantic quality judgments.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    pack_parser = subparsers.add_parser("pack", help="Create a blind A/B packet and private key.")
    pack_parser.add_argument("--task", required=True)
    pack_parser.add_argument("--baseline-result", required=True)
    pack_parser.add_argument("--candidate-result", required=True)
    pack_parser.add_argument("--baseline-root", required=True)
    pack_parser.add_argument("--candidate-root", required=True)
    pack_parser.add_argument("--include", action="append", default=[])
    pack_parser.add_argument("--rubric", action="append", default=[])
    pack_parser.add_argument("--seed")
    pack_parser.add_argument("--max-chars", type=int, default=30000)
    pack_parser.add_argument("--judge-goal")
    pack_parser.add_argument("--write-packet")
    pack_parser.add_argument("--write-key")
    pack_parser.set_defaults(func=pack)

    judge_parser = subparsers.add_parser("judge-result", help="Unblind a semantic judgment and map it to baseline/candidate.")
    judge_parser.add_argument("--packet", required=True)
    judge_parser.add_argument("--key", required=True)
    judge_parser.add_argument("--judgment", required=True)
    judge_parser.add_argument("--min-delta", type=float, default=0.5)
    judge_parser.add_argument("--write")
    judge_parser.add_argument("--require-promotion", action="store_true")
    judge_parser.set_defaults(func=judge_result)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
