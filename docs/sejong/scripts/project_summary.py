#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project a human-readable summary from an Uigwe bundle.")
    parser.add_argument("bundle_path", help="Uigwe bundle directory or wrapper.result.json path")
    parser.add_argument("--write", action="store_true", help="Write planning-summary.json and planning-summary.md into the bundle directory")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    return parser.parse_args()


def resolve_bundle_path(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path.resolve()
    return input_path.resolve().parent


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def project_summary(bundle_dir: Path) -> dict[str, Any]:
    wrapper_result = load_json(bundle_dir / "wrapper.result.json")
    plan_packet = load_json(bundle_dir / "plan.packet.json")
    goal_tree = load_json(bundle_dir / "goal-tree.json")
    design_packet_path = bundle_dir / "design.packet.json"
    design_packet = load_json(design_packet_path) if design_packet_path.exists() else None

    selected_plan = plan_packet["selected_plan"]
    retained = [
        {
          "id": alt["id"],
          "title": alt["title"],
          "summary": alt["summary"],
        }
        for alt in plan_packet.get("retained_alternatives", [])
    ]
    risks = [
        {
          "id": risk["id"],
          "severity": risk["severity"],
          "description": risk["description"],
        }
        for risk in plan_packet.get("risk_summary", [])[:5]
    ]
    leaves = []
    for leaf in plan_packet.get("leaf_tasks", []):
        leaves.append(
            {
                "id": leaf["id"],
                "title": leaf["title"],
                "risk_level": leaf["risk_level"],
                "dependency_count": len(leaf.get("dependencies", [])),
                "file_scope_count": len(leaf.get("file_scope", [])),
                "needs_critic": bool(leaf.get("consumer_hints", {}).get("needs_critic", False)),
                "needs_verifier": bool(leaf.get("consumer_hints", {}).get("needs_verifier", False)),
            }
        )

    summary: dict[str, Any] = {
        "bundle_path": str(bundle_dir),
        "resolved_mode": wrapper_result["resolved_mode"],
        "resolved_profile": wrapper_result["resolved_profile"],
        "selected_plan": selected_plan,
        "selected_approach": None,
        "retained_alternatives": retained,
        "top_risks": risks,
        "leaf_summary": leaves,
        "goal_tree_stats": {
            "node_count": len(goal_tree.get("nodes", [])),
            "dependency_edge_count": len(goal_tree.get("dependency_edges", [])),
        },
    }
    if design_packet:
        selected_approach = design_packet.get("selected_approach")
        if selected_approach:
            summary["selected_approach"] = {
                "id": selected_approach["id"],
                "title": selected_approach["title"],
                "summary": selected_approach["summary"],
            }
    return summary


def markdown_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Planning Summary",
        "",
        f"- Mode: `{summary['resolved_mode']}`",
        f"- Profile: `{summary['resolved_profile']}`",
        f"- Plan: `{summary['selected_plan']['title']}`",
        f"- Summary: {summary['selected_plan']['summary']}",
        "",
    ]
    if summary.get("selected_approach"):
        lines.extend(
            [
                "## Selected Approach",
                "",
                f"- `{summary['selected_approach']['title']}`",
                f"- {summary['selected_approach']['summary']}",
                "",
            ]
        )
    if summary["retained_alternatives"]:
        lines.extend(["## Retained Alternatives", ""])
        for alt in summary["retained_alternatives"]:
            lines.append(f"- `{alt['title']}`: {alt['summary']}")
        lines.append("")
    if summary["top_risks"]:
        lines.extend(["## Top Risks", ""])
        for risk in summary["top_risks"]:
            lines.append(f"- `{risk['severity']}` `{risk['id']}`: {risk['description']}")
        lines.append("")
    lines.extend(["## Leaf Summary", ""])
    for leaf in summary["leaf_summary"]:
        lines.append(
            f"- `{leaf['title']}` | risk `{leaf['risk_level']}` | deps `{leaf['dependency_count']}` | files `{leaf['file_scope_count']}` | critic `{str(leaf['needs_critic']).lower()}` | verifier `{str(leaf['needs_verifier']).lower()}`"
        )
    lines.append("")
    lines.append(
        f"- Goal-tree stats: nodes `{summary['goal_tree_stats']['node_count']}`, edges `{summary['goal_tree_stats']['dependency_edge_count']}`"
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    bundle_dir = resolve_bundle_path(Path(args.bundle_path))
    summary = project_summary(bundle_dir)

    if args.write:
        (bundle_dir / "planning-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (bundle_dir / "planning-summary.md").write_text(markdown_summary(summary), encoding="utf-8")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(markdown_summary(summary).rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
