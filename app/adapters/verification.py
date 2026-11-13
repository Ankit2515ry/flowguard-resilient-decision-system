"""External verification adapter contract and deterministic test/demo simulator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol


class DependencyCategory(str, Enum):
    NONE = "NONE"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    PERMANENT = "PERMANENT"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class Scenario(str, Enum):
    SUCCESS = "SUCCESS"
    TEMPORARY_FAILURE = "TEMPORARY_FAILURE"
    FAIL_THEN_RECOVER = "FAIL_THEN_RECOVER"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"


@dataclass(frozen=True, slots=True)
class VerificationResult:
    success: bool
    retryable: bool
    category: DependencyCategory
    message: str


class VerificationProvider(Protocol):
    def verify(
        self,
        *,
        operation: str,
        payload: dict[str, Any],
        operation_key: str,
        attempt_number: int,
    ) -> VerificationResult: ...


class SimulatedVerificationProvider:
    """A deterministic simulator configured by the server, never by request fields."""

    def __init__(self, scenario: Scenario = Scenario.SUCCESS, fail_attempts: int = 1):
        if fail_attempts < 0:
            raise ValueError("fail_attempts cannot be negative")
        self.scenario = scenario
        self.fail_attempts = fail_attempts

    def verify(
        self,
        *,
        operation: str,
        payload: dict[str, Any],
        operation_key: str,
        attempt_number: int,
    ) -> VerificationResult:
        del operation, payload, operation_key  # Identity/identity data are intentionally not inspected.
        if self.scenario is Scenario.SUCCESS:
            return VerificationResult(True, False, DependencyCategory.NONE, "verification succeeded")
        if self.scenario is Scenario.PERMANENT_FAILURE:
            return VerificationResult(False, False, DependencyCategory.PERMANENT,
                                      "simulated permanent verification failure")
        if self.scenario is Scenario.TEMPORARY_FAILURE:
            return VerificationResult(False, True, DependencyCategory.UNAVAILABLE,
                                      "simulated HTTP 503 / temporary outage")
        if attempt_number <= self.fail_attempts:
            return VerificationResult(False, True, DependencyCategory.TIMEOUT,
                                      "simulated transient timeout")
        return VerificationResult(True, False, DependencyCategory.NONE,
                                  "verification succeeded after recovery")


def provider_from_environment() -> SimulatedVerificationProvider:
    scenario_text = os.getenv("FLOWGUARD_SIMULATOR_SCENARIO", "SUCCESS").upper()
    try:
        scenario = Scenario(scenario_text)
    except ValueError as exc:
        raise ValueError(f"unsupported FLOWGUARD_SIMULATOR_SCENARIO {scenario_text!r}") from exc
    fail_attempts = int(os.getenv("FLOWGUARD_SIMULATOR_FAIL_ATTEMPTS", "1"))
    return SimulatedVerificationProvider(scenario, fail_attempts)
