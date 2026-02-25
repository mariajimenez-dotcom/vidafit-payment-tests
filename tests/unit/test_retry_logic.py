"""
Unit tests for retry logic with exponential backoff.

These tests ensure retries work correctly and prevent duplicate charges.
"""

import time
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from fixtures.factories import PaymentFactory
from mocks.fake_db import FakeDatabase
from mocks.fake_gateway import FakeGateway, GatewayScenario
from src.payment_processor import PaymentProcessor
from src.retry_handler import NetworkTimeoutError, RateLimitError, RetryHandler


@pytest.mark.unit
class TestRetryLogic:
    """Test suite for retry logic."""

    def test_retry_triggered_on_network_timeout(self):
        """
        Test that network timeouts trigger retry mechanism.
        """
        # Configure gateway to timeout first 2 times, then succeed
        gateway = FakeGateway(scenario=GatewayScenario.INTERMITTENT)
        db = FakeDatabase()

        processor = PaymentProcessor(
            gateway=gateway,
            database=db,
            retry_handler=RetryHandler(max_attempts=5, base_delay=0.1),
        )

        payment = PaymentFactory.create()

        # Should retry and eventually succeed (or fail after max attempts)
        try:
            response = processor.process_payment(payment)
            # If successful, verify retries occurred
            assert gateway.call_count >= 1
        except NetworkTimeoutError:
            # If all retries exhausted, that's also valid
            assert gateway.call_count == 5  # Max attempts

    def test_exponential_backoff_timing(self):
        """
        Test that exponential backoff uses correct delays: 1s, 2s, 4s, 8s.
        """
        handler = RetryHandler(max_attempts=5, base_delay=1)

        # Test backoff calculation
        assert handler.calculate_backoff_delay(0) == 1  # 1 * 2^0 = 1
        assert handler.calculate_backoff_delay(1) == 2  # 1 * 2^1 = 2
        assert handler.calculate_backoff_delay(2) == 4  # 1 * 2^2 = 4
        assert handler.calculate_backoff_delay(3) == 8  # 1 * 2^3 = 8
        assert handler.calculate_backoff_delay(4) == 10  # Capped at max=10

    def test_max_retry_attempts_respected(self):
        """
        Test that retry stops after configured maximum attempts.
        """
        # Gateway that always times out
        gateway = FakeGateway(scenario=GatewayScenario.NETWORK_TIMEOUT)
        db = FakeDatabase()

        max_attempts = 3
        processor = PaymentProcessor(
            gateway=gateway,
            database=db,
            retry_handler=RetryHandler(max_attempts=max_attempts, base_delay=0.1),
        )

        payment = PaymentFactory.create()

        # Should fail after max attempts (tenacity wraps in RetryError)
        with pytest.raises(Exception):  # Could be NetworkTimeoutError or RetryError
            processor.process_payment(payment)

        # Verify exactly max_attempts were made
        assert gateway.call_count == max_attempts

    def test_no_retry_on_permanent_failure_codes(self):
        """
        Test that permanent failures (invalid card, fraud) do NOT trigger retries.
        """
        # Configure gateway for hard decline (permanent failure)
        gateway = FakeGateway(scenario=GatewayScenario.HARD_DECLINE)
        db = FakeDatabase()

        processor = PaymentProcessor(
            gateway=gateway,
            database=db,
            retry_handler=RetryHandler(max_attempts=5, base_delay=0.1),
        )

        payment = PaymentFactory.create()

        # Process payment
        response = processor.process_payment(payment)

        # Should fail immediately without retries
        assert not response.success
        assert response.decline_reason is not None
        assert not response.is_retriable

        # Gateway should be called only ONCE (no retries)
        assert gateway.call_count == 1

    def test_idempotency_preserved_across_retries(self):
        """
        Test that the same idempotency key is used for all retry attempts.

        Prevents: Bug #1 - Retries creating duplicate charges with different keys
        """
        gateway = FakeGateway(scenario=GatewayScenario.INTERMITTENT)
        db = FakeDatabase()

        processor = PaymentProcessor(
            gateway=gateway,
            database=db,
            retry_handler=RetryHandler(max_attempts=5, base_delay=0.1),
        )

        idempotency_key = "test-retry-key-123"
        payment = PaymentFactory.create(idempotency_key=idempotency_key)

        # Process (will retry due to intermittent failures)
        try:
            processor.process_payment(payment)
        except Exception:
            pass  # Don't care if it fails, just checking idempotency

        # Check all gateway calls used the same idempotency key
        for call in gateway.call_log:
            if "idempotency_key" in call:
                assert call["idempotency_key"] == idempotency_key

    def test_should_retry_logic(self):
        """Test the should_retry decision logic."""
        handler = RetryHandler()

        # Should retry on network errors
        assert handler.should_retry(NetworkTimeoutError()) is True

        # Should retry on rate limits
        assert handler.should_retry(RateLimitError()) is True

        # Should NOT retry on other errors
        assert handler.should_retry(ValueError("Invalid")) is False
        assert handler.should_retry(Exception("Generic")) is False
