"""Configurable mock payment gateway for testing."""
import uuid
import time
from typing import Optional, List, Dict, Any
from decimal import Decimal

from src.models import GatewayResponse, DeclineReason, Card
from src.retry_handler import NetworkTimeoutError, RateLimitError


class GatewayScenario:
    """Predefined gateway behavior scenarios."""
    ALWAYS_SUCCESS = "ALWAYS_SUCCESS"
    NETWORK_TIMEOUT = "NETWORK_TIMEOUT"
    SOFT_DECLINE = "SOFT_DECLINE"
    HARD_DECLINE = "HARD_DECLINE"
    RATE_LIMITED = "RATE_LIMITED"
    INTERMITTENT = "INTERMITTENT"
    AUTH_SUCCESS_CAPTURE_FAIL = "AUTH_SUCCESS_CAPTURE_FAIL"


class FakeGateway:
    """Mock payment gateway with configurable behavior."""

    def __init__(self, scenario: str = GatewayScenario.ALWAYS_SUCCESS):
        self.scenario = scenario
        self.call_log: List[Dict[str, Any]] = []
        self.idempotency_cache: Dict[str, GatewayResponse] = {}
        self.authorized_transactions: Dict[str, bool] = {}
        self.void_called = False
        self.call_count = 0
        self.intermittent_counter = 0

    def authorize(
        self,
        amount: Decimal,
        currency: str,
        card: Optional[Card] = None,
        idempotency_key: Optional[str] = None
    ) -> GatewayResponse:
        """
        Authorize a payment.

        Args:
            amount: Payment amount
            currency: Currency code
            card: Card information
            idempotency_key: Idempotency key for duplicate prevention

        Returns:
            GatewayResponse with result
        """
        self.call_count += 1

        # Log the call
        self.call_log.append({
            'operation': 'authorize',
            'amount': amount,
            'currency': currency,
            'idempotency_key': idempotency_key,
            'timestamp': time.time()
        })

        # Check idempotency cache
        if idempotency_key and idempotency_key in self.idempotency_cache:
            return self.idempotency_cache[idempotency_key]

        # Execute scenario
        response = self._execute_scenario()

        # Cache response if idempotent
        if idempotency_key and response:
            self.idempotency_cache[idempotency_key] = response

        # Track authorized transactions
        if response.success and response.transaction_id:
            self.authorized_transactions[response.transaction_id] = True

        return response

    def capture(self, transaction_id: str, amount: Optional[Decimal] = None) -> GatewayResponse:
        """Capture a previously authorized transaction."""
        self.call_log.append({
            'operation': 'capture',
            'transaction_id': transaction_id,
            'amount': amount,
            'timestamp': time.time()
        })

        # Check if this scenario should fail capture
        if self.scenario == GatewayScenario.AUTH_SUCCESS_CAPTURE_FAIL:
            return GatewayResponse(
                success=False,
                error_code="capture_failed",
                error_message="Capture failed",
                is_retriable=False
            )

        # Normal capture success
        if transaction_id in self.authorized_transactions:
            return GatewayResponse(
                success=True,
                transaction_id=transaction_id
            )

        return GatewayResponse(
            success=False,
            error_code="transaction_not_found",
            error_message="Transaction not found",
            is_retriable=False
        )

    def void(self, transaction_id: str) -> GatewayResponse:
        """Void a previously authorized transaction."""
        self.void_called = True
        self.call_log.append({
            'operation': 'void',
            'transaction_id': transaction_id,
            'timestamp': time.time()
        })

        if transaction_id in self.authorized_transactions:
            del self.authorized_transactions[transaction_id]
            return GatewayResponse(success=True)

        return GatewayResponse(
            success=False,
            error_code="transaction_not_found",
            error_message="Transaction not found"
        )

    def _execute_scenario(self) -> GatewayResponse:
        """Execute the configured scenario."""
        if self.scenario == GatewayScenario.ALWAYS_SUCCESS:
            return GatewayResponse(
                success=True,
                transaction_id=str(uuid.uuid4())
            )

        elif self.scenario == GatewayScenario.NETWORK_TIMEOUT:
            raise NetworkTimeoutError("Gateway connection timeout")

        elif self.scenario == GatewayScenario.SOFT_DECLINE:
            return GatewayResponse(
                success=False,
                error_code="insufficient_funds",
                error_message="Insufficient funds",
                is_retriable=True,
                decline_reason=DeclineReason.INSUFFICIENT_FUNDS
            )

        elif self.scenario == GatewayScenario.HARD_DECLINE:
            return GatewayResponse(
                success=False,
                error_code="invalid_card",
                error_message="Invalid card number",
                is_retriable=False,
                decline_reason=DeclineReason.INVALID_CARD
            )

        elif self.scenario == GatewayScenario.RATE_LIMITED:
            raise RateLimitError("Rate limit exceeded")

        elif self.scenario == GatewayScenario.INTERMITTENT:
            # Alternate between success and failure
            self.intermittent_counter += 1
            if self.intermittent_counter % 2 == 0:
                return GatewayResponse(
                    success=True,
                    transaction_id=str(uuid.uuid4())
                )
            else:
                raise NetworkTimeoutError("Intermittent failure")

        elif self.scenario == GatewayScenario.AUTH_SUCCESS_CAPTURE_FAIL:
            return GatewayResponse(
                success=True,
                transaction_id=str(uuid.uuid4())
            )

        # Default success
        return GatewayResponse(
            success=True,
            transaction_id=str(uuid.uuid4())
        )

    def reset(self):
        """Reset gateway state for new test."""
        self.call_log.clear()
        self.idempotency_cache.clear()
        self.authorized_transactions.clear()
        self.void_called = False
        self.call_count = 0
        self.intermittent_counter = 0
