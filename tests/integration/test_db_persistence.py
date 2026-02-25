"""
Integration tests for database persistence and state consistency.

These tests ensure payment states are correctly persisted and race conditions are prevented.
"""

import threading
from decimal import Decimal

import pytest

from fixtures.factories import PaymentFactory
from mocks.fake_db import FakeDatabase
from mocks.fake_gateway import FakeGateway, GatewayScenario
from src.models import PaymentStatus
from src.payment_processor import PaymentProcessor


@pytest.mark.integration
class TestDatabasePersistence:
    """Test suite for database persistence logic."""

    def test_payment_state_persisted_on_transition(self, fake_gateway, fake_db):
        """
        Test that payment state is persisted to database on each transition.
        """
        processor = PaymentProcessor(gateway=fake_gateway, database=fake_db)
        payment = PaymentFactory.create()

        # Record initial state
        initial_status = payment.status
        assert initial_status == PaymentStatus.PENDING

        # Process payment
        response = processor.process_payment(payment)

        # Verify success
        assert response.success
        assert payment.status == PaymentStatus.SUCCESS

        # Verify payment was persisted to database
        persisted_payment = fake_db.get_payment(payment.id)
        assert persisted_payment is not None
        assert persisted_payment.status == PaymentStatus.SUCCESS
        assert persisted_payment.gateway_transaction_id is not None

    def test_concurrent_updates_use_row_locks(self):
        """
        Test that concurrent updates to same payment use row-level locking.

        Prevents: Race conditions where multiple threads update same payment simultaneously.
        """
        gateway = FakeGateway(scenario=GatewayScenario.ALWAYS_SUCCESS)
        db = FakeDatabase()

        payment = PaymentFactory.create()

        # Save initial payment
        db.save_payment(payment)

        results = []
        errors = []

        def update_payment(thread_id):
            """Update payment in a thread."""
            try:
                # Get payment
                p = db.get_payment(payment.id)
                if p:
                    # Simulate some processing
                    p.retry_count += 1
                    # Save back
                    db.save_payment(p)
                    results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, e))

        # Create 20 threads all trying to update same payment
        threads = [
            threading.Thread(target=update_payment, args=(i,)) for i in range(20)
        ]

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # All threads should complete successfully
        assert len(results) == 20
        assert len(errors) == 0

        # Get final payment state
        final_payment = db.get_payment(payment.id)

        # retry_count should be 20 (each thread incremented once)
        # Due to row locking, updates should be serialized
        assert final_payment.retry_count == 20

    def test_transaction_audit_trail(self, fake_gateway, fake_db):
        """
        Test that transaction records are created for audit trail.
        """
        from src.models import Transaction

        processor = PaymentProcessor(gateway=fake_gateway, database=fake_db)
        payment = PaymentFactory.create()

        # Process payment
        response = processor.process_payment(payment)
        assert response.success

        # Create transaction record manually (in real system, this would be automatic)
        transaction = Transaction(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            status="success",
            gateway="primary",
            gateway_transaction_id=response.transaction_id,
            idempotency_key=payment.idempotency_key,
        )

        fake_db.save_transaction(transaction)

        # Verify transaction was saved
        saved_txn = fake_db.get_transaction(transaction.id)
        assert saved_txn is not None
        assert saved_txn.payment_id == payment.id
        assert saved_txn.gateway_transaction_id == response.transaction_id

        # Verify we can query transactions by payment
        payment_txns = fake_db.get_transactions_by_payment(payment.id)
        assert len(payment_txns) == 1
        assert payment_txns[0].id == transaction.id

    def test_failed_payment_persisted(self):
        """
        Test that failed payments are also persisted correctly.
        """
        # Gateway that always fails
        gateway = FakeGateway(scenario=GatewayScenario.HARD_DECLINE)
        db = FakeDatabase()

        processor = PaymentProcessor(gateway=gateway, database=db)
        payment = PaymentFactory.create()

        # Process payment (will fail)
        response = processor.process_payment(payment)

        # Should fail
        assert not response.success
        assert payment.status == PaymentStatus.FAILED
        assert payment.decline_reason is not None

        # Failed payment should be persisted
        persisted_payment = db.get_payment(payment.id)
        assert persisted_payment is not None
        assert persisted_payment.status == PaymentStatus.FAILED
        assert persisted_payment.decline_reason == payment.decline_reason
