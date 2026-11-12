"""
Build Job State Machine and Transition Rules
Phase 4 Implementation for Emergent Central Hub

Valid statuses:
- DRAFT
- QUEUED
- ASSIGNED
- STARTING
- RUNNING
- PAUSED
- COMPLETED
- FAILED
- CANCELLED
"""
from typing import Dict, Set


class InvalidTransitionError(ValueError):
    """Raised when an illegal status transition is attempted."""
    pass


# Strict status transition matrix
VALID_TRANSITIONS: Dict[str, Set[str]] = {
    "DRAFT": {"QUEUED", "CANCELLED"},
    "QUEUED": {"ASSIGNED", "STARTING", "CANCELLED"},
    "ASSIGNED": {"STARTING", "QUEUED", "CANCELLED"},
    "STARTING": {"RUNNING", "FAILED", "CANCELLED"},
    "RUNNING": {"PAUSED", "COMPLETED", "FAILED", "CANCELLED"},
    "PAUSED": {"RUNNING", "CANCELLED"},
    "FAILED": {"QUEUED"},  # Retry re-enqueues the job
    "CANCELLED": set(),    # Terminal state
    "COMPLETED": set(),    # Terminal state
}

# Terminal states
TERMINAL_STATUSES: Set[str] = {"COMPLETED", "CANCELLED"}

# Priority rank for scheduling (higher number = higher priority)
PRIORITY_ORDER: Dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}


def can_transition(current_status: str, target_status: str) -> bool:
    """Checks if a transition from current_status to target_status is permitted."""
    current = current_status.upper()
    target = target_status.upper()
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


def validate_transition(current_status: str, target_status: str, job_id: int = 0) -> None:
    """
    Validates that the status transition is permitted.
    Raises InvalidTransitionError if forbidden.
    """
    current = current_status.upper()
    target = target_status.upper()
    
    if current == target:
        return  # No-op transition
        
    if not can_transition(current, target):
        allowed_list = sorted(list(VALID_TRANSITIONS.get(current, set())))
        allowed_str = ", ".join(allowed_list) if allowed_list else "None (Terminal State)"
        raise InvalidTransitionError(
            f"Invalid build status transition for job #{job_id}: Cannot transition from '{current}' to '{target}'. "
            f"Permitted next statuses from '{current}': [{allowed_str}]."
        )

