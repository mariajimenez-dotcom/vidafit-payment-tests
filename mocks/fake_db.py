"""In-memory database mock for testing."""

import threading
from typing import Dict, Optional, List
from src.models import Payment, Transaction


class FakeDatabase:
    """In-memory database with transaction support and row locking."""

    def __init__(self):
        self.payments: Dict[str, Payment] = {}
        self.transactions: Dict[str, Transaction] = {}
        self.locks: Dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()

    def save_payment(self, payment: Payment) -> Payment:
        """
        Save payment to database.

        Args:
            payment: Payment to save

        Returns:
            Saved payment
        """
        # Get or create lock for this payment
        with self._global_lock:
            if payment.id not in self.locks:
                self.locks[payment.id] = threading.Lock()
            lock = self.locks[payment.id]

        # Acquire row lock
        with lock:
            # Simulate row-level locking for concurrent updates
            self.payments[payment.id] = payment

        return payment

    def get_payment(self, payment_id: str) -> Optional[Payment]:
        """Get payment by ID."""
        return self.payments.get(payment_id)

    def save_transaction(self, transaction: Transaction) -> Transaction:
        """Save transaction to database."""
        self.transactions[transaction.id] = transaction
        return transaction

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        return self.transactions.get(transaction_id)

    def get_transactions_by_payment(self, payment_id: str) -> List[Transaction]:
        """Get all transactions for a payment."""
        return [
            txn for txn in self.transactions.values() if txn.payment_id == payment_id
        ]

    def begin_transaction(self):
        """Begin database transaction (no-op for in-memory)."""
        pass

    def commit(self):
        """Commit transaction (no-op for in-memory)."""
        pass

    def rollback(self):
        """Rollback transaction (no-op for in-memory)."""
        pass

    def clear(self):
        """Clear all data (for test cleanup)."""
        self.payments.clear()
        self.transactions.clear()
        self.locks.clear()
