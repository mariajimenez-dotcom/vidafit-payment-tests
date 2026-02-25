"""State machine for payment status transitions."""

from typing import Dict, List
from src.models import PaymentStatus


class InvalidStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


# Valid state transitions mapping
VALID_TRANSITIONS: Dict[PaymentStatus, List[PaymentStatus]] = {
    PaymentStatus.PENDING: [PaymentStatus.PROCESSING, PaymentStatus.FAILED],
    PaymentStatus.PROCESSING: [
        PaymentStatus.SUCCESS,
        PaymentStatus.FAILED,
        PaymentStatus.DECLINED_RETRIABLE,
    ],
    PaymentStatus.SUCCESS: [PaymentStatus.REFUNDED],
    PaymentStatus.DECLINED_RETRIABLE: [PaymentStatus.PROCESSING, PaymentStatus.FAILED],
    PaymentStatus.FAILED: [],  # Terminal state
    PaymentStatus.REFUNDED: [],  # Terminal state
}


def validate_transition(current_state: PaymentStatus, new_state: PaymentStatus) -> bool:
    """
    Validate if a state transition is allowed.

    Args:
        current_state: Current payment status
        new_state: Desired new status

    Returns:
        True if transition is valid

    Raises:
        InvalidStateTransitionError: If transition is not allowed
    """
    valid_next_states = VALID_TRANSITIONS.get(current_state, [])

    if new_state not in valid_next_states:
        raise InvalidStateTransitionError(
            f"Invalid transition from {current_state.value} to {new_state.value}. "
            f"Valid transitions: {[s.value for s in valid_next_states]}"
        )

    return True


def is_terminal_state(state: PaymentStatus) -> bool:
    """Check if a state is terminal (no further transitions allowed)."""
    return len(VALID_TRANSITIONS.get(state, [])) == 0


def is_retriable_state(state: PaymentStatus) -> bool:
    """Check if a payment in this state can be retried."""
    return state == PaymentStatus.DECLINED_RETRIABLE


def get_valid_next_states(current_state: PaymentStatus) -> List[PaymentStatus]:
    """Get list of valid next states from current state."""
    return VALID_TRANSITIONS.get(current_state, [])
