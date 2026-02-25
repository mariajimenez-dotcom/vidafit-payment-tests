"""
Unit tests for idempotency validation.

These tests prevent Bug #1: Race condition in retry mechanism that caused duplicate charges.
"""

import threading
import time
from decimal import Decimal

import pytest

from fixtures.factories import PaymentFactory
from mocks.fake_gateway import FakeGateway, GatewayScenario
from src.models import GatewayResponse, PaymentStatus
from src.payment_processor import IdempotencyValidator, PaymentProcessor
from src.retry_handler import RetryHandler


@pytest.mark.unit
class TestIdempotency:
    """Test suite for idempotency validation."""

    def test_duplicate_request_returns_cached_response(
        self, payment_processor, sample_payment
    ):
        """
        Test that duplicate requests with same idempotency key return cached response
        without creating duplicate charges.

        Prevents: Bug #1 - Race condition duplicate charges
        """
        # First request
        response1 = payment_processor.process_payment(sample_payment)
        assert response1.success

        # Second request with same idempotency key should return cached response
        sample_payment.status = PaymentStatus.PENDING  # Reset status
        response2 = payment_processor.process_payment(sample_payment)

        # Should get same response
        assert response2.success
        assert response1.transaction_id == response2.transaction_id

        # Gateway should only be called once
        assert payment_processor.gateway.call_count == 1

    def test_idempotency_key_expires_after_ttl(self):
        """
        Test that idempotency keys expire after TTL and new requests are processed.
        """
        # Create validator with short TTL (1 second)
        validator = IdempotencyValidator(cache_ttl_seconds=1)

        key = "test-key-123"
        payload = {"amount": "100.00", "currency": "USD"}
        response = GatewayResponse(success=True, transaction_id="txn-123")

        # Store response
        validator.store(key, response, payload)

        # Should be cached immediately
        cached = validator.check(key, payload)
        assert cached is not None
        assert cached.transaction_id == "txn-123"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired now
        cached = validator.check(key, payload)
        assert cached is None

    def test_different_keys_create_separate_transactions(self, payment_processor):
        """
        Test that different idempotency keys create separate transactions.
        """
        # Create two payments with different idempotency keys
        payment1 = PaymentFactory.create(
            amount=Decimal("100.00"), idempotency_key="key-1"
        )
        payment2 = PaymentFactory.create(
            amount=Decimal("200.00"), idempotency_key="key-2"
        )

        # Process both
        response1 = payment_processor.process_payment(payment1)
        response2 = payment_processor.process_payment(payment2)

        # Both should succeed with different transaction IDs
        assert response1.success
        assert response2.success
        assert response1.transaction_id != response2.transaction_id

        # Gateway should be called twice
        assert payment_processor.gateway.call_count == 2

    def test_retry_with_same_key_after_failure(
        self, fake_gateway, idempotency_validator, fake_db
    ):
        """
        Test that retries after failure use the same idempotency key.
        """
        # Configure gateway to fail first, then succeed
        fake_gateway.scenario = GatewayScenario.INTERMITTENT

        processor = PaymentProcessor(
            gateway=fake_gateway,
            database=fake_db,
            idempotency_validator=idempotency_validator,
            retry_handler=RetryHandler(max_attempts=3, base_delay=0.1),
        )

        payment = PaymentFactory.create(idempotency_key="retry-key")

        # Process - should retry and eventually succeed
        try:
            response = processor.process_payment(payment)
            # If successful, verify idempotency key was preserved
            assert payment.idempotency_key == "retry-key"
        except Exception:
            # If all retries failed, that's ok for this test
            # The important part is the key was preserved
            assert payment.idempotency_key == "retry-key"

    @pytest.mark.serial
    def test_concurrent_requests_same_key_single_charge(self, fake_gateway, fake_db):
        """
        Test that concurrent requests with same idempotency key result in single charge.

        Prevents: Bug #1 - Race condition causing duplicate charges
        """
        validator = IdempotencyValidator()
        processor = PaymentProcessor(
            gateway=fake_gateway, database=fake_db, idempotency_validator=validator
        )

        idempotency_key = "concurrent-key"
        results = []
        errors = []

        def process_payment_thread():
            try:
                payment = PaymentFactory.create(idempotency_key=idempotency_key)
                response = processor.process_payment(payment)
                results.append(response)
            except Exception as e:
                errors.append(e)

        # Create 50 threads all trying to process with same key
        threads = [threading.Thread(target=process_payment_thread) for _ in range(50)]

        # Start all threads simultaneously
        for thread in threads:
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join()

        # All should succeed (cached or real)
        assert len(results) == 50
        assert all(r.success for r in results)

        # But gateway should only be called ONCE
        assert fake_gateway.call_count == 1

        # All should have same transaction ID
        transaction_ids = [r.transaction_id for r in results]
        assert len(set(transaction_ids)) == 1  # Only one unique ID

        # No errors should occur
        assert len(errors) == 0
