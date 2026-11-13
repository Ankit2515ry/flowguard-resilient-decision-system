"""Bounded retry timing settings; first external attempt counts toward max_attempts."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    lease_seconds: int = 120

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one (including the initial attempt)")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")
        if self.lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")

    def delay_after(self, failed_attempt: int) -> float:
        """Exponential delay after a failed attempt, capped at configured maximum."""
        exponent = max(0, failed_attempt - 1)
        return min(self.max_delay_seconds, self.base_delay_seconds * (2 ** exponent))

    @classmethod
    def from_environment(cls) -> RetryPolicy:
        return cls(
            max_attempts=int(os.getenv("FLOWGUARD_RETRY_MAX_ATTEMPTS", "3")),
            base_delay_seconds=float(os.getenv("FLOWGUARD_RETRY_BASE_DELAY_SECONDS", "1")),
            max_delay_seconds=float(os.getenv("FLOWGUARD_RETRY_MAX_DELAY_SECONDS", "60")),
            lease_seconds=int(os.getenv("FLOWGUARD_EXECUTION_LEASE_SECONDS", "120")),
        )
