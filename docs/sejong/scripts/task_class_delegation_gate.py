#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from delegation_route_contract import (
    ARTIFACT_POLICIES,
    CODE_COUPLINGS,
    COURT_MODE_POLICIES,
    EVIDENCE_BREADTHS,
    FORMAT as POLICY_FORMAT,
    HOST_NATIVE_STATES,
    NATIVE_MESSAGING_STATES,
    NATIVE_WRITE_ISOLATIONS,
    OVERHEAD_ROIS,
    SEUNGJEONGWON_GUARDRAIL_STATES,
    TASK_CLASSES,
    UIGWE_STATES,
    WORKER_AUTHORITY_POLICIES,
    WORKER_SCOPE_STATES,
    WRITE_MODES,
    WRITE_RISKS,
    DelegationInput,
)
from delegation_route_policy import evaluate


FORMAT = POLICY_FORMAT


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select a King Sejong execution/delegation route for a task class."
    )
    parser.add_argument(
        "--from-json", help="Read decision factors from a JSON file, or '-' for stdin."
    )
    parser.add_argument("--task-class", choices=sorted(TASK_CLASSES))
    parser.add_argument("--write-risk", choices=sorted(WRITE_RISKS), default="low")
    parser.add_argument(
        "--evidence-breadth", choices=sorted(EVIDENCE_BREADTHS), default="narrow"
    )
    parser.add_argument(
        "--code-coupling", choices=sorted(CODE_COUPLINGS), default="isolated"
    )
    parser.add_argument("--overhead-roi", choices=sorted(OVERHEAD_ROIS), default="low")
    parser.add_argument(
        "--uigwe-contract-state", choices=sorted(UIGWE_STATES), default="none"
    )
    parser.add_argument(
        "--seungjeongwon-guardrail-state",
        choices=sorted(SEUNGJEONGWON_GUARDRAIL_STATES),
        default="clear",
    )
    parser.add_argument(
        "--artifact-policy",
        choices=sorted(ARTIFACT_POLICIES),
        default="sejong_home_or_promoted_refs",
    )
    parser.add_argument(
        "--worker-authority-policy",
        choices=sorted(WORKER_AUTHORITY_POLICIES),
        default="evidence_only",
    )
    parser.add_argument(
        "--court-mode-policy",
        choices=sorted(COURT_MODE_POLICIES),
        default="existing_surfaces_only",
    )
    parser.add_argument(
        "--worker-scope-state", choices=sorted(WORKER_SCOPE_STATES), default="none"
    )
    parser.add_argument("--write-mode", choices=sorted(WRITE_MODES), default="allowed")
    parser.add_argument(
        "--host-native-state", choices=sorted(HOST_NATIVE_STATES), default="unknown"
    )
    parser.add_argument(
        "--host-native-direct-messaging",
        choices=sorted(NATIVE_MESSAGING_STATES),
        default="unknown",
    )
    parser.add_argument(
        "--host-native-write-isolation",
        choices=sorted(NATIVE_WRITE_ISOLATIONS),
        default="unknown",
    )
    parser.add_argument("--requires-independent-process", action="store_true")
    parser.add_argument("--requires-cross-session-recovery", action="store_true")
    parser.add_argument("--requires-write-isolation", action="store_true")
    parser.add_argument("--requires-peer-messaging", action="store_true")
    return parser.parse_args(argv)


def input_from_args(args: argparse.Namespace) -> DelegationInput:
    if args.from_json:
        raw = (
            sys.stdin.read()
            if args.from_json == "-"
            else Path(args.from_json).read_text(encoding="utf-8")
        )
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("--from-json payload must be an object")
        return DelegationInput(**payload)
    if not args.task_class:
        raise ValueError("--task-class is required unless --from-json is used")
    return DelegationInput(
        task_class=args.task_class,
        write_risk=args.write_risk,
        evidence_breadth=args.evidence_breadth,
        code_coupling=args.code_coupling,
        overhead_roi=args.overhead_roi,
        uigwe_contract_state=args.uigwe_contract_state,
        seungjeongwon_guardrail_state=args.seungjeongwon_guardrail_state,
        artifact_policy=args.artifact_policy,
        worker_authority_policy=args.worker_authority_policy,
        court_mode_policy=args.court_mode_policy,
        worker_scope_state=args.worker_scope_state,
        write_mode=args.write_mode,
        host_native_state=args.host_native_state,
        host_native_direct_messaging=args.host_native_direct_messaging,
        host_native_write_isolation=args.host_native_write_isolation,
        requires_independent_process=args.requires_independent_process,
        requires_cross_session_recovery=args.requires_cross_session_recovery,
        requires_write_isolation=args.requires_write_isolation,
        requires_peer_messaging=args.requires_peer_messaging,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        case = input_from_args(parse_args(argv))
        print(json.dumps(evaluate(case), indent=2, sort_keys=True))
        return 0
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
