"""Canonical request/execution lifecycle and legal transitions."""


FINAL_STATES = frozenset({"APPROVED", "REJECTED", "MANUAL_REVIEW", "FAILED"})

LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "RECEIVED": frozenset({"PROCESSING"}),
    "PROCESSING": frozenset({
        "APPROVED", "REJECTED", "MANUAL_REVIEW", "RETRY_WAIT", "FAILED",
    }),
    "RETRY_WAIT": frozenset({"PROCESSING", "FAILED", "MANUAL_REVIEW"}),
    "APPROVED": frozenset(),
    "REJECTED": frozenset(),
    "MANUAL_REVIEW": frozenset({"APPROVED", "REJECTED"}),
    "FAILED": frozenset(),
}


def validate_transition(old_state: str, new_state: str) -> None:
    if new_state not in LEGAL_TRANSITIONS.get(old_state, frozenset()):
        raise ValueError(f"illegal lifecycle transition {old_state!r} -> {new_state!r}")
