"""Test data factories using Faker."""
from decimal import Decimal
from faker import Faker
import uuid

from src.models import Payment, Card, PaymentStatus, Transaction

fake = Faker()


class PaymentFactory:
    """Factory for creating test payments."""

    @staticmethod
    def create(
        amount: Decimal = None,
        currency: str = "USD",
        status: PaymentStatus = PaymentStatus.PENDING,
        idempotency_key: str = None,
        card: Card = None
    ) -> Payment:
        """Create a payment with sensible defaults."""
        return Payment(
            id=str(uuid.uuid4()),
            amount=amount or Decimal("100.00"),
            currency=currency,
            status=status,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
            card=card or CardFactory.create()
        )

    @staticmethod
    def create_batch(count: int, **kwargs) -> list:
        """Create multiple payments."""
        return [PaymentFactory.create(**kwargs) for _ in range(count)]


class CardFactory:
    """Factory for creating test cards."""

    @staticmethod
    def create(
        number: str = None,
        exp_month: int = None,
        exp_year: int = None,
        cvv: str = None,
        holder_name: str = None
    ) -> Card:
        """Create a card with sensible defaults."""
        return Card(
            number=number or "4532015112830366",  # Valid test Visa
            exp_month=exp_month or 12,
            exp_year=exp_year or 2025,
            cvv=cvv or "123",
            holder_name=holder_name or fake.name()
        )


class TransactionFactory:
    """Factory for creating test transactions."""

    @staticmethod
    def create(
        payment_id: str = None,
        amount: Decimal = None,
        currency: str = "USD",
        status: str = "pending",
        gateway: str = "primary",
        idempotency_key: str = None
    ) -> Transaction:
        """Create a transaction with sensible defaults."""
        return Transaction(
            id=str(uuid.uuid4()),
            payment_id=payment_id or str(uuid.uuid4()),
            amount=amount or Decimal("100.00"),
            currency=currency,
            status=status,
            gateway=gateway,
            idempotency_key=idempotency_key
        )
