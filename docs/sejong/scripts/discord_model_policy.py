from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from enum import StrEnum

from discord_contract_types import ControlContractError, JsonObject, RiskClass


@dataclass(frozen=True, slots=True)
class ModelPolicy:
    luna_model: str
    sol_model: str
    antigravity_model: str


@dataclass(frozen=True, slots=True)
class RoutingRequest:
    task_class: str
    risk_class: RiskClass
    verification_class: str


class PromotionState(StrEnum):
    SHADOW = "shadow"
    PROMOTION_CANDIDATE = "promotion_candidate"


@dataclass(frozen=True, slots=True)
class ShadowMetrics:
    task_class: str
    comparable_runs: int
    independent_reviews: int
    quality_delta: float
    regressions: int
    approval_ref: str | None


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    state: PromotionState
    automatic_promotion: bool
    reasons: tuple[str, ...]


def evaluate_shadow_promotion(metrics: ShadowMetrics) -> PromotionDecision:
    reasons: list[str] = []
    if not math.isfinite(metrics.quality_delta):
        reasons.append("invalid_metrics")
    if not metrics.task_class:
        reasons.append("task_class_required")
    if metrics.comparable_runs < 3:
        reasons.append("insufficient_comparable_runs")
    if metrics.independent_reviews < 3:
        reasons.append("insufficient_independent_reviews")
    if metrics.quality_delta <= 0:
        reasons.append("no_quality_gain")
    if metrics.regressions != 0:
        reasons.append("regressions_present")
    if not metrics.approval_ref:
        reasons.append("explicit_approval_required")
    state = PromotionState.PROMOTION_CANDIDATE if not reasons else PromotionState.SHADOW
    return PromotionDecision(state, False, tuple(reasons))


def _decision_hash(payload: JsonObject) -> str:
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


def route_ticket(policy: ModelPolicy, request: RoutingRequest) -> JsonObject:
    if not request.task_class or not request.verification_class:
        raise ControlContractError("invalid_route", "task and verification classes are required")
    models = (policy.luna_model, policy.sol_model, policy.antigravity_model)
    if any(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model) is None for model in models):
        raise ControlContractError("unsafe_model", "every model slot must be one opaque argv-safe token")
    implementer_sandbox = "read-only" if request.task_class in {"analysis", "research", "review"} else "workspace-write"
    decision: JsonObject = {
        "format": "sejong.discord-model-route/v0.1-draft",
        "authority": "core_routing",
        "task_class": request.task_class,
        "risk_class": request.risk_class.value,
        "verification_class": request.verification_class,
        "requires_approval": request.risk_class is RiskClass.HIGH,
        "controller": {
            "slot": "terra",
            "function": "controller_router_only",
            "can_mutate": False,
        },
        "implementer": {
            "slot": "luna",
            "model": policy.luna_model,
            "sandbox": implementer_sandbox,
            "model_immutable_per_run": True,
        },
        "reviewer": {
            "slot": "sol",
            "model": policy.sol_model,
            "sandbox": "read-only",
            "fresh_run_required": True,
        },
        "shadow": {
            "slot": "antigravity",
            "model": policy.antigravity_model,
            "sandbox": "read-only",
            "state": "shadow",
            "canonical_authority": False,
        },
    }
    decision["decision_sha256"] = _decision_hash(decision)
    return decision
