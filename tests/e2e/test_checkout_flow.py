"""
End-to-end tests for complete checkout flows.

These tests demonstrate full system integration but are kept minimal
due to time constraints. In production, would expand to cover:
- Multiple payment methods
- Different currencies
- Various error scenarios
- Webhook processing
- Refund flows
"""

import pytest
import threading
from decimal import Decimal

from src.payment_processor import PaymentProcessor
from src.models import PaymentStatus
from mocks.fake_gateway import FakeGateway, GatewayScenario
from mocks.fake_db import FakeDatabase
from fixtures.factories import PaymentFactory


@pytest.mark.e2e
@pytest.mark.slow
class TestCheckoutFlow:
    """End-to-end test suite for checkout flows."""

    def test_full_checkout_card_authorization_capture(self):
        """
        Test complete checkout flow: authorization and capture.

        Flow:
        1. Customer initiates payment
        2. System authorizes card
        3. System captures funds
        4. Payment marked as successful
        5. State persisted to database
        """
        gateway = FakeGateway(scenario=GatewayScenario.ALWAYS_SUCCESS)
        db = FakeDatabase()
        processor = PaymentProcessor(gateway=gateway, database=db)

        # Create payment for customer purchase
        payment = PaymentFactory.create(amount=Decimal("149.99"), currency="USD")

        # Process payment
        response = processor.process_payment(payment)

        # Verify successful authorization
        assert response.success
        assert response.transaction_id is not None

        # Verify payment state
        assert payment.status == PaymentStatus.SUCCESS
        assert payment.gateway_transaction_id == response.transaction_id

        # Verify persistence
        persisted = db.get_payment(payment.id)
        assert persisted is not None
        assert persisted.status == PaymentStatus.SUCCESS

        # Verify gateway was called with correct idempotency
        assert len(gateway.call_log) >= 1
        auth_call = gateway.call_log[0]
        assert auth_call["operation"] == "authorize"
        assert auth_call["amount"] == Decimal("149.99")
        assert auth_call["idempotency_key"] == payment.idempotency_key

    def test_concurrent_payments_no_duplicate_charges(self):
        """
        Test that concurrent payments from multiple customers work correctly.

        Simulates 10 customers checking out simultaneously.

        Expected: All payments succeed independently without interference.
        """
        gateway = FakeGateway(scenario=GatewayScenario.ALWAYS_SUCCESS)
        db = FakeDatabase()

        results = []
        errors = []

        def process_customer_payment(customer_id):
            """Simulate a customer payment."""
            try:
                processor = PaymentProcessor(gateway=gateway, database=db)

                # Each customer has unique payment with unique idempotency key
                payment = PaymentFactory.create(amount=Decimal("99.99"), currency="USD")

                response = processor.process_payment(payment)
                results.append(
                    {
                        "customer_id": customer_id,
                        "payment_id": payment.id,
                        "success": response.success,
                        "transaction_id": response.transaction_id,
                    }
                )
            except Exception as e:
                errors.append({"customer_id": customer_id, "error": str(e)})

        # Simulate 10 concurrent customers
        threads = [
            threading.Thread(target=process_customer_payment, args=(i,))
            for i in range(10)
        ]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify results
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

        # All payments should succeed
        assert all(r["success"] for r in results)

        # All should have unique transaction IDs
        transaction_ids = [r["transaction_id"] for r in results]
        assert len(set(transaction_ids)) == 10, "Duplicate transaction IDs detected!"

        # All should have unique payment IDs
        payment_ids = [r["payment_id"] for r in results]
        assert len(set(payment_ids)) == 10

        # Gateway should be called exactly 10 times (once per customer)
        assert gateway.call_count == 10


# Additional E2E test ideas (documented for "with more time")
"""
Future E2E Tests to Implement:

1. test_multi_currency_checkout_flow
   - Customer pays in BRL, merchant receives USD
   - Verify currency conversion and proper rounding

2. test_payment_retry_after_soft_decline
   - Card declined due to insufficient funds
   - Customer updates card, retry succeeds

3. test_webhook_notification_flow
   - Payment succeeds
   - Webhook sent to merchant
   - Merchant acknowledges receipt

4. test_refund_flow
   - Original payment succeeds
   - Merchant issues refund
   - Funds returned to customer

5. test_partial_capture_flow
   - Authorize $100
   - Capture $75
   - Void remaining $25

6. test_checkout_timeout_recovery
   - Gateway times out during checkout
   - System retries automatically
   - Customer sees eventual success (not timeout error)

7. test_fraud_detection_decline
   - High-risk transaction flagged
   - Payment declined for security
   - Customer notified appropriately

8. test_3ds_authentication_flow
   - 3D Secure required for card
   - Customer completes authentication
   - Payment proceeds after verification
"""
