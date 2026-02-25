"""Core payment processing logic."""

import hashlib
import time
from typing import Optional, Dict, Any
from decimal import Decimal

from src.models import (
    Payment,
    PaymentStatus,
    GatewayResponse,
    DeclineReason,
    Transaction,
)
from src.state_machine import validate_transition, is_retriable_state
from src.retry_handler import RetryHandler, NetworkTimeoutError


class IdempotencyValidator:
    """Validates and caches idempotent requests."""

    def __init__(self, cache_ttl_seconds: int = 604800):  # 7 days default
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = cache_ttl_seconds

    def check(self, key: str, payload: Dict[str, Any]) -> Optional[GatewayResponse]:
        """
        Check if request with this key has been processed before.

        Args:
            key: Idempotency key
            payload: Request payload for hash verification

        Returns:
            Cached response if found and valid, None otherwise
        """
        if key in self.cache:
            cached = self.cache[key]

            # Check if expired
            if cached["timestamp"] + self.ttl < time.time():
                del self.cache[key]
                return None

            # Verify payload matches (prevent key reuse with different data)
            payload_hash = self._hash_payload(payload)
            if cached["payload_hash"] != payload_hash:
                raise ValueError("Idempotency key reused with different payload")

            return cached["response"]

        return None

    def store(self, key: str, response: GatewayResponse, payload: Dict[str, Any]):
        """Store response in cache."""
        self.cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "payload_hash": self._hash_payload(payload),
        }

    def _hash_payload(self, payload: Dict[str, Any]) -> str:
        """Create hash of payload for verification."""
        payload_str = str(sorted(payload.items()))
        return hashlib.sha256(payload_str.encode()).hexdigest()


class PaymentProcessor:
    """Main payment processing orchestrator."""

    def __init__(
        self,
        gateway,
        database=None,
        idempotency_validator: Optional[IdempotencyValidator] = None,
        retry_handler: Optional[RetryHandler] = None,
    ):
        self.gateway = gateway
        self.database = database
        self.idempotency_validator = idempotency_validator or IdempotencyValidator()
        self.retry_handler = retry_handler or RetryHandler()

    def process_payment(self, payment: Payment) -> GatewayResponse:
        """
        Process a payment with full orchestration.

        Args:
            payment: Payment to process

        Returns:
            GatewayResponse with result
        """
        # Check idempotency
        if payment.idempotency_key:
            payload = self._payment_to_payload(payment)
            cached_response = self.idempotency_validator.check(
                payment.idempotency_key, payload
            )
            if cached_response:
                return cached_response

        # Transition to PROCESSING
        self._update_payment_status(payment, PaymentStatus.PROCESSING)

        try:
            # Execute with retry
            response = self.retry_handler.execute_with_retry(
                self._authorize_payment, payment
            )

            # Update status based on response
            if response.success:
                self._update_payment_status(payment, PaymentStatus.SUCCESS)
                payment.gateway_transaction_id = response.transaction_id
            elif response.is_retriable:
                self._update_payment_status(payment, PaymentStatus.DECLINED_RETRIABLE)
                payment.decline_reason = response.decline_reason
            else:
                self._update_payment_status(payment, PaymentStatus.FAILED)
                payment.decline_reason = response.decline_reason

            # Cache response if idempotent
            if payment.idempotency_key:
                self.idempotency_validator.store(
                    payment.idempotency_key, response, self._payment_to_payload(payment)
                )

            # Persist to database
            if self.database:
                self.database.save_payment(payment)

            return response

        except Exception as e:
            self._update_payment_status(payment, PaymentStatus.FAILED)
            if self.database:
                self.database.save_payment(payment)
            raise

    def _authorize_payment(self, payment: Payment) -> GatewayResponse:
        """Authorize payment through gateway."""
        return self.gateway.authorize(
            amount=payment.amount,
            currency=payment.currency,
            card=payment.card,
            idempotency_key=payment.idempotency_key,
        )

    def _update_payment_status(self, payment: Payment, new_status: PaymentStatus):
        """Update payment status with validation."""
        validate_transition(payment.status, new_status)
        payment.update_status(new_status)

    def _payment_to_payload(self, payment: Payment) -> Dict[str, Any]:
        """Convert payment to payload dict for hashing."""
        return {
            "amount": str(payment.amount),
            "currency": payment.currency,
            "card_last4": payment.card.number[-4:] if payment.card else None,
        }

    def process_with_cascade(self, payment: Payment, gateways: list) -> GatewayResponse:
        """
        Process payment with gateway cascade/fallback.

        Args:
            payment: Payment to process
            gateways: List of gateway instances to try in order

        Returns:
            GatewayResponse from successful gateway
        """
        last_response = None
        is_first_gateway = True

        for gateway_index, gateway in enumerate(gateways):
            # Reset payment status for retry on new gateway (except first)
            if not is_first_gateway:
                payment.status = PaymentStatus.PENDING
                payment.gateway_transaction_id = None
            is_first_gateway = False

            self.gateway = gateway

            try:
                # Try to authorize with this gateway (without full retry cascade to avoid complexity)
                payment.status = PaymentStatus.PROCESSING
                response = self._authorize_payment(payment)

                if response.success:
                    # Update payment status
                    payment.update_status(PaymentStatus.SUCCESS)
                    payment.gateway_transaction_id = response.transaction_id

                    # Persist to database
                    if self.database:
                        self.database.save_payment(payment)

                    return response
                else:
                    # Authorization failed
                    # If we had a partial authorization that needs voiding, do it
                    if payment.gateway_transaction_id:
                        try:
                            gateway.void(payment.gateway_transaction_id)
                            payment.gateway_transaction_id = None
                        except Exception:
                            pass  # Log but continue

                    last_response = response

            except Exception as e:
                # If we had a partial authorization that needs voiding, do it
                if payment.gateway_transaction_id:
                    try:
                        gateway.void(payment.gateway_transaction_id)
                        payment.gateway_transaction_id = None
                    except Exception:
                        pass  # Log but continue

                last_response = GatewayResponse(
                    success=False, error_message=str(e), is_retriable=False
                )

        # All gateways failed
        payment.update_status(PaymentStatus.FAILED)
        if self.database:
            self.database.save_payment(payment)

        return last_response or GatewayResponse(
            success=False, error_message="All gateways failed", is_retriable=False
        )
