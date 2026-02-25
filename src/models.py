"""Data models for payment processing."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
import uuid


class PaymentStatus(str, Enum):
    """Payment status states."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    DECLINED_RETRIABLE = "DECLINED_RETRIABLE"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class DeclineReason(str, Enum):
    """Reason codes for declined payments."""

    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_CARD = "invalid_card"
    EXPIRED_CARD = "expired_card"
    FRAUD_SUSPECTED = "fraud_suspected"
    DO_NOT_HONOR = "do_not_honor"
    NETWORK_ERROR = "network_error"


@dataclass
class Card:
    """Payment card information."""

    number: str
    exp_month: int
    exp_year: int
    cvv: str
    holder_name: str


@dataclass
class Payment:
    """Payment entity."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    amount: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "USD"
    status: PaymentStatus = PaymentStatus.PENDING
    card: Optional[Card] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    gateway_transaction_id: Optional[str] = None
    decline_reason: Optional[DeclineReason] = None

    def update_status(self, new_status: PaymentStatus):
        """Update payment status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.utcnow()


@dataclass
class Transaction:
    """Transaction record for audit trail."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    payment_id: str = ""
    amount: Decimal = field(default_factory=lambda: Decimal("0"))
    currency: str = "USD"
    status: str = "pending"
    gateway: str = "primary"
    gateway_transaction_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    error_message: Optional[str] = None


@dataclass
class GatewayResponse:
    """Response from payment gateway."""

    success: bool
    transaction_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_retriable: bool = False
    decline_reason: Optional[DeclineReason] = None


@dataclass
class IdempotencyCacheEntry:
    """Cached response for idempotency."""

    key: str
    response: GatewayResponse
    timestamp: float
    payload_hash: str
