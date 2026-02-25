"""
Unit tests for payment state machine.

These tests prevent Bug #2: Incorrect state transitions on soft declines.
"""

import pytest

from src.state_machine import (
    validate_transition,
    InvalidStateTransitionError,
    is_terminal_state,
    is_retriable_state,
    get_valid_next_states,
)
from src.models import PaymentStatus
from fixtures.factories import PaymentFactory


@pytest.mark.unit
class TestStateMachine:
    """Test suite for payment state machine logic."""

    def test_valid_state_transition_pending_to_processing(self):
        """Test valid transition from PENDING to PROCESSING."""
        current = PaymentStatus.PENDING
        new = PaymentStatus.PROCESSING

        # Should not raise exception
        assert validate_transition(current, new) is True

    def test_processing_to_success_on_gateway_success(self):
        """Test valid transition from PROCESSING to SUCCESS (happy path)."""
        current = PaymentStatus.PROCESSING
        new = PaymentStatus.SUCCESS

        assert validate_transition(current, new) is True

    def test_processing_to_failed_on_gateway_error(self):
        """Test valid transition from PROCESSING to FAILED (error handling)."""
        current = PaymentStatus.PROCESSING
        new = PaymentStatus.FAILED

        assert validate_transition(current, new) is True

    def test_invalid_transition_rejected(self):
        """
        Test that invalid transitions are rejected.

        For example, cannot go from SUCCESS back to PENDING.
        """
        current = PaymentStatus.SUCCESS
        new = PaymentStatus.PENDING

        with pytest.raises(InvalidStateTransitionError) as exc_info:
            validate_transition(current, new)

        assert "Invalid transition" in str(exc_info.value)
        assert "SUCCESS" in str(exc_info.value)
        assert "PENDING" in str(exc_info.value)

    def test_soft_decline_maps_to_retriable_state(self):
        """
        Test that soft declines map to DECLINED_RETRIABLE state, not FAILED.

        Prevents: Bug #2 - Soft declines incorrectly marked as FAILED
        """
        # Should be able to transition from PROCESSING to DECLINED_RETRIABLE
        current = PaymentStatus.PROCESSING
        new = PaymentStatus.DECLINED_RETRIABLE

        assert validate_transition(current, new) is True

        # DECLINED_RETRIABLE should be recognized as retriable
        assert is_retriable_state(PaymentStatus.DECLINED_RETRIABLE) is True

        # Should be able to retry (go back to PROCESSING)
        assert (
            validate_transition(
                PaymentStatus.DECLINED_RETRIABLE, PaymentStatus.PROCESSING
            )
            is True
        )

    def test_hard_decline_maps_to_terminal_failed_state(self):
        """
        Test that hard declines (invalid card, fraud) map to terminal FAILED state.

        Hard declines should NOT be retried.
        """
        # Should be able to transition to FAILED
        assert (
            validate_transition(PaymentStatus.PROCESSING, PaymentStatus.FAILED) is True
        )

        # FAILED should be terminal (no further transitions)
        assert is_terminal_state(PaymentStatus.FAILED) is True

        # Should not be retriable
        assert is_retriable_state(PaymentStatus.FAILED) is False

        # Cannot transition from FAILED
        valid_next = get_valid_next_states(PaymentStatus.FAILED)
        assert len(valid_next) == 0

        # Trying to transition from FAILED should fail
        with pytest.raises(InvalidStateTransitionError):
            validate_transition(PaymentStatus.FAILED, PaymentStatus.PROCESSING)

    def test_terminal_states_identified(self):
        """Test that terminal states are correctly identified."""
        assert is_terminal_state(PaymentStatus.FAILED) is True
        assert is_terminal_state(PaymentStatus.REFUNDED) is True
        assert is_terminal_state(PaymentStatus.SUCCESS) is False  # Can refund
        assert is_terminal_state(PaymentStatus.PENDING) is False
        assert is_terminal_state(PaymentStatus.PROCESSING) is False

    def test_get_valid_next_states(self):
        """Test retrieval of valid next states."""
        # From PENDING
        pending_next = get_valid_next_states(PaymentStatus.PENDING)
        assert PaymentStatus.PROCESSING in pending_next
        assert PaymentStatus.FAILED in pending_next

        # From PROCESSING
        processing_next = get_valid_next_states(PaymentStatus.PROCESSING)
        assert PaymentStatus.SUCCESS in processing_next
        assert PaymentStatus.FAILED in processing_next
        assert PaymentStatus.DECLINED_RETRIABLE in processing_next

        # From terminal state
        failed_next = get_valid_next_states(PaymentStatus.FAILED)
        assert len(failed_next) == 0
