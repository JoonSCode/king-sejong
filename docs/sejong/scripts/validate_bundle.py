#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[3]
SCHEMA_DIR = REPO_ROOT / "docs" / "sejong"


@dataclass
class Issue:
    level: str
    code: str
    message: str
    artifact: str | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
        }
        if self.artifact:
            payload["artifact"] = self.artifact
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationReport:
    def __init__(self, bundle_path: Path) -> None:
        self.bundle_path = bundle_path
        self.resolved_mode: str | None = None
        self.resolved_profile: str | None = None
        self.checks: list[dict[str, Any]] = []
        self.errors: list[Issue] = []
        self.warnings: list[Issue] = []

    def add_check(self, name: str, status: str, summary: str, details: dict[str, Any] | None = None) -> None:
        check: dict[str, Any] = {"name": name, "status": status, "summary": summary}
        if details:
            check["details"] = details
        self.checks.append(check)

    def error(self, code: str, message: str, artifact: Path | None = None, details: dict[str, Any] | None = None) -> None:
        self.errors.append(Issue("error", code, message, str(artifact) if artifact else None, details))

    def warn(self, code: str, message: str, artifact: Path | None = None, details: dict[str, Any] | None = None) -> None:
        self.warnings.append(Issue("warning", code, message, str(artifact) if artifact else None, details))

    def status(self, strict: bool = False) -> str:
        if self.errors:
            return "fail"
        if strict and self.warnings:
            return "fail"
        return "pass"

    def to_dict(self, strict: bool = False) -> dict[str, Any]:
        return {
            "bundle_path": str(self.bundle_path),
            "status": self.status(strict=strict),
            "resolved_mode": self.resolved_mode,
            "resolved_profile": self.resolved_profile,
            "checks": self.checks,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate an Uigwe bundle directory or wrapper.result.json")
    parser.add_argument("input_path", help="Bundle directory or wrapper.result.json path")
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    parser.add_argument("--write-report", action="store_true", help="Write bundle-validation.result.json and bundle-validation.md")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    return parser.parse_args()


def resolve_bundle_path(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path.resolve()
    if input_path.is_file():
        return input_path.resolve().parent
    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_ref(path_str: str, bundle_dir: Path) -> Path:
    candidate = Path(path_str)
    if candidate.is_absolute():
        return candidate
    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return (bundle_dir / candidate).resolve()


def run_schema_validation(schema_path: Path, data_path: Path) -> tuple[bool, str]:
    command = [
        "npx",
        "-y",
        "-p",
        "ajv-cli",
        "-p",
        "ajv-formats",
        "ajv",
        "validate",
        "-c",
        "ajv-formats",
        "-s",
        str(schema_path),
        "-d",
        str(data_path),
        "--spec=draft2020",
    ]
    result = subprocess.run(command, capture_output=True, text=True, cwd=str(REPO_ROOT))
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def artifact_contract_for_mode(mode: str) -> tuple[set[str], set[str]]:
    required = {
        "wrapper.request.json",
        "wrapper.result.json",
        "plan.packet.json",
        "goal-tree.json",
        "spec.md",
        "rationale.md",
    }
    forbidden: set[str] = set()
    if mode == "full":
        required.update({"intent.packet.json", "design.packet.json"})
    elif mode == "design-to-plan":
        required.add("design.packet.json")
        forbidden.add("intent.packet.json")
    elif mode == "decompose-only":
        forbidden.add("intent.packet.json")
    return required, forbidden


def stronger_task_statuses() -> set[str]:
    return {"executable_leaf", "dispatched", "completed", "blocked"}


def validate_bundle(bundle_dir: Path, strict: bool = False) -> ValidationReport:
    report = ValidationReport(bundle_dir)

    wrapper_result_path = bundle_dir / "wrapper.result.json"
    if not wrapper_result_path.exists():
        report.error("missing_required_artifact", "wrapper.result.json is required", wrapper_result_path)
        return report

    wrapper_result = load_json(wrapper_result_path)
    report.resolved_mode = wrapper_result.get("resolved_mode")
    report.resolved_profile = wrapper_result.get("resolved_profile")

    mode = report.resolved_mode
    profile = report.resolved_profile
    if mode not in {"full", "design-to-plan", "decompose-only"}:
        report.error("mode_mismatch", f"Unsupported or missing resolved_mode: {mode}", wrapper_result_path)
        return report

    required, forbidden = artifact_contract_for_mode(mode)
    present = {path.name for path in bundle_dir.iterdir() if path.is_file()}

    missing = sorted(name for name in required if name not in present)
    unexpected = sorted(name for name in forbidden if name in present)

    if missing:
        for name in missing:
            report.error("missing_required_artifact", f"Missing required artifact for mode '{mode}': {name}", bundle_dir / name)
        report.add_check("artifact_presence", "fail", "Missing required artifacts", {"missing": missing})
    elif unexpected:
        for name in unexpected:
            report.error("unexpected_artifact_for_mode", f"Unexpected artifact for mode '{mode}': {name}", bundle_dir / name)
        report.add_check("artifact_presence", "fail", "Unexpected artifacts for resolved mode", {"unexpected": unexpected})
    else:
        report.add_check("artifact_presence", "pass", "Required artifacts present for resolved mode", {"mode": mode})

    schema_map = {
        "wrapper.request.json": SCHEMA_DIR / "wrapper.schema.json",
        "wrapper.result.json": SCHEMA_DIR / "wrapper.schema.json",
        "plan.packet.json": SCHEMA_DIR / "packets.schema.json",
        "intent.packet.json": SCHEMA_DIR / "packets.schema.json",
        "design.packet.json": SCHEMA_DIR / "packets.schema.json",
        "goal-tree.json": SCHEMA_DIR / "goal-tree.schema.json",
    }
    schema_failures = []
    for name, schema_path in schema_map.items():
        artifact_path = bundle_dir / name
        if not artifact_path.exists():
            continue
        ok, output = run_schema_validation(schema_path, artifact_path)
        if not ok:
            schema_failures.append(name)
            kind = "wrapper" if "wrapper" in name else "packet" if "packet" in name or "intent" in name or "design" in name else "goal_tree"
            report.error(f"schema_invalid_{kind}", output or f"Schema validation failed for {name}", artifact_path)
    if schema_failures:
        report.add_check("schema_validation", "fail", "One or more schema validations failed", {"artifacts": schema_failures})
    else:
        report.add_check("schema_validation", "pass", "All present JSON artifacts passed schema validation")

    artifact_refs = wrapper_result.get("artifacts", {})
    missing_refs = []
    for key, path_str in artifact_refs.items():
        resolved = resolve_ref(path_str, bundle_dir)
        if not resolved.exists():
            missing_refs.append((key, path_str))
            report.error("artifact_path_missing", f"wrapper.result references a missing path for {key}: {path_str}", wrapper_result_path)
    if missing_refs:
        report.add_check("wrapper_result_paths", "fail", "wrapper.result contains missing paths", {"missing": missing_refs})
    else:
        report.add_check("wrapper_result_paths", "pass", "wrapper.result artifact paths resolve")

    plan_packet_path = bundle_dir / "plan.packet.json"
    goal_tree_path = bundle_dir / "goal-tree.json"
    if plan_packet_path.exists() and goal_tree_path.exists():
        plan_packet = load_json(plan_packet_path)
        goal_tree = load_json(goal_tree_path)

        if profile and plan_packet.get("profile") != profile:
            report.error(
                "profile_mismatch",
                f"wrapper.result profile '{profile}' does not match plan.packet profile '{plan_packet.get('profile')}'",
                plan_packet_path,
            )
        if plan_packet.get("profile") != goal_tree.get("metadata", {}).get("profile"):
            report.error(
                "profile_mismatch",
                "plan.packet profile does not match goal-tree metadata.profile",
                goal_tree_path,
            )

        expected_paths = {
            "spec_path": bundle_dir / "spec.md",
            "rationale_path": bundle_dir / "rationale.md",
            "goal_tree_path": goal_tree_path,
        }
        for field_name, expected_path in expected_paths.items():
            actual = resolve_ref(plan_packet.get(field_name, ""), bundle_dir) if plan_packet.get(field_name) else None
            if actual is None or actual != expected_path.resolve():
                report.error(
                    "bundle_path_mismatch",
                    f"plan.packet {field_name} does not match the produced artifact path",
                    plan_packet_path,
                    {"field": field_name, "expected": str(expected_path.resolve()), "actual": str(actual) if actual else None},
                )

        task_nodes = {
            node["id"]: node
            for node in goal_tree.get("nodes", [])
            if node.get("type") == "task"
        }
        missing_leaf_nodes = []
        for leaf in plan_packet.get("leaf_tasks", []):
            node = task_nodes.get(leaf.get("id"))
            if not node or node.get("status") not in stronger_task_statuses():
                missing_leaf_nodes.append(leaf.get("id"))
                report.error(
                    "leaf_missing_goal_tree_node",
                    f"Leaf task '{leaf.get('id')}' is missing from goal-tree as an executable task node",
                    goal_tree_path,
                )
        if missing_leaf_nodes:
            report.add_check("leaf_cross_reference", "fail", "Some plan leaves are missing in goal-tree task nodes", {"missing_leaf_ids": missing_leaf_nodes})
        else:
            report.add_check("leaf_cross_reference", "pass", "Every plan leaf appears in goal-tree executable task nodes")

        field_drift = []
        if "ready_for_consumer" in goal_tree:
            field_drift.append("ready_for_consumer")
            report.error(
                "packet_field_in_goal_tree",
                "goal-tree.json contains packet-only field 'ready_for_consumer'",
                goal_tree_path,
            )
        if field_drift:
            report.add_check("field_placement", "fail", "Packet-only fields found in goal-tree", {"fields": field_drift})
        else:
            report.add_check("field_placement", "pass", "No packet-only fields found in goal-tree")

        task_field_failures = []
        for node in task_nodes.values():
            missing_fields = [
                field_name
                for field_name in ("done_criteria", "file_scope", "verification", "risk_level")
                if not node.get(field_name)
            ]
            if missing_fields:
                task_field_failures.append({"id": node.get("id"), "missing_fields": missing_fields})
                report.error(
                    "task_node_missing_execution_fields",
                    f"Task node '{node.get('id')}' is missing execution fields",
                    goal_tree_path,
                    {"missing_fields": missing_fields},
                )
        if task_field_failures:
            report.add_check("task_node_execution_fields", "fail", "Some task nodes are missing execution fields", {"nodes": task_field_failures})
        else:
            report.add_check("task_node_execution_fields", "pass", "All task nodes include execution fields")

        if wrapper_result.get("status") == "completed" and wrapper_result.get("blockers"):
            report.error(
                "completed_status_with_blockers",
                "wrapper.result reports completed status with non-empty blockers",
                wrapper_result_path,
            )

    if not report.errors:
        report.add_check("overall", "pass", "Bundle passed validation")
    else:
        report.add_check("overall", "fail", "Bundle validation failed", {"error_count": len(report.errors), "warning_count": len(report.warnings)})

    return report


def markdown_report(report: ValidationReport, strict: bool = False) -> str:
    lines = [
        "# Bundle Validation",
        "",
        f"- Bundle: `{report.bundle_path}`",
        f"- Status: `{report.status(strict=strict)}`",
        f"- Resolved mode: `{report.resolved_mode}`",
        f"- Resolved profile: `{report.resolved_profile}`",
        "",
        "## Checks",
    ]
    for check in report.checks:
        lines.append(f"- `{check['name']}`: `{check['status']}` - {check['summary']}")
    if report.errors:
        lines.extend(["", "## Errors"])
        for issue in report.errors:
            location = f" (`{issue.artifact}`)" if issue.artifact else ""
            lines.append(f"- `{issue.code}`{location}: {issue.message}")
    if report.warnings:
        lines.extend(["", "## Warnings"])
        for issue in report.warnings:
            location = f" (`{issue.artifact}`)" if issue.artifact else ""
            lines.append(f"- `{issue.code}`{location}: {issue.message}")
    return "\n".join(lines) + "\n"


def write_reports(bundle_dir: Path, report: ValidationReport, strict: bool = False) -> None:
    json_path = bundle_dir / "bundle-validation.result.json"
    md_path = bundle_dir / "bundle-validation.md"
    json_path.write_text(json.dumps(report.to_dict(strict=strict), indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown_report(report, strict=strict), encoding="utf-8")


def main() -> int:
    args = parse_args()
    bundle_dir = resolve_bundle_path(Path(args.input_path))
    report = validate_bundle(bundle_dir, strict=args.strict)

    if args.write_report:
        write_reports(bundle_dir, report, strict=args.strict)

    if args.json:
        print(json.dumps(report.to_dict(strict=args.strict), indent=2))
    else:
        print(markdown_report(report, strict=args.strict).rstrip())

    return 1 if report.status(strict=args.strict) == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
