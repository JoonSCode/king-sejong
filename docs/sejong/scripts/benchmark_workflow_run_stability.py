#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from typing import Any

from benchmark_workflow_run_comparison import performance_comparison


DEFAULT_SAMPLES = 9
DEFAULT_WARMUPS = 1
DEFAULT_MAX_P95_SECONDS = 1.0
DEFAULT_MAX_FAILURE_RATE = 0.0


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[index]


def summarize(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "min": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "max": 0.0,
            "stdev": 0.0,
        }
    return {
        "min": round(min(values), 6),
        "median": round(statistics.median(values), 6),
        "p95": round(percentile(values, 0.95), 6),
        "max": round(max(values), 6),
        "stdev": round(statistics.pstdev(values), 6),
    }


def run_samples(args: argparse.Namespace) -> dict[str, Any]:
    for _ in range(args.warmups):
        performance_comparison(args.worker_count, args.evidence_count, args.max_large_ledger_seconds)

    samples = [
        performance_comparison(args.worker_count, args.evidence_count, args.max_large_ledger_seconds)
        for _ in range(args.samples)
    ]
    candidate_values = [float(sample["candidate_elapsed_seconds"]) for sample in samples]
    baseline_values = [float(sample["baseline_elapsed_seconds"]) for sample in samples]
    failure_count = sum(1 for sample in samples if not sample["passed"] or sample["candidate_failures"])
    failure_rate = failure_count / args.samples if args.samples else 1.0
    candidate_summary = summarize(candidate_values)
    baseline_summary = summarize(baseline_values)
    passed = (
        args.samples > 0
        and failure_rate <= args.max_failure_rate
        and candidate_summary["p95"] <= args.max_p95_seconds
        and candidate_summary["max"] <= args.max_large_ledger_seconds
    )
    return {
        "format": "sejong.workflow-run-stability-benchmark/v0.1-draft",
        "passed": passed,
        "sample_count": args.samples,
        "warmup_count": args.warmups,
        "worker_count": args.worker_count,
        "evidence_count": args.evidence_count,
        "max_large_ledger_seconds": args.max_large_ledger_seconds,
        "max_p95_seconds": args.max_p95_seconds,
        "max_failure_rate": args.max_failure_rate,
        "failure_count": failure_count,
        "failure_rate": round(failure_rate, 4),
        "candidate_elapsed_seconds": candidate_summary,
        "baseline_elapsed_seconds": baseline_summary,
        "samples": samples,
        "notes": [
            "This benchmark verifies timing stability of the workflow-run validator over repeated large-ledger checks.",
            "It does not prove real-world productivity; pair it with workflow-run artifact audits over real task corpora.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repeat workflow-run large-ledger validation to detect timing flake risk.")
    parser.add_argument("--samples", type=int, default=DEFAULT_SAMPLES)
    parser.add_argument("--warmups", type=int, default=DEFAULT_WARMUPS)
    parser.add_argument("--worker-count", type=int, default=1000)
    parser.add_argument("--evidence-count", type=int, default=2000)
    parser.add_argument("--max-large-ledger-seconds", type=float, default=DEFAULT_MAX_P95_SECONDS)
    parser.add_argument("--max-p95-seconds", type=float, default=DEFAULT_MAX_P95_SECONDS)
    parser.add_argument("--max-failure-rate", type=float, default=DEFAULT_MAX_FAILURE_RATE)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_samples(args)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        candidate = payload["candidate_elapsed_seconds"]
        print(
            "workflow_run_stability "
            f"{'ok' if payload['passed'] else 'failed'}: "
            f"samples={payload['sample_count']} failures={payload['failure_count']} "
            f"candidate_p95={candidate['p95']}s candidate_max={candidate['max']}s"
        )
        if not payload["passed"]:
            print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
