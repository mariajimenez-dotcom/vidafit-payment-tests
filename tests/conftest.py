"""Global pytest fixtures."""
import pytest
from decimal import Decimal

from mocks.fake_gateway import FakeGateway, GatewayScenario
from mocks.fake_db import FakeDatabase
from fixtures.factories import PaymentFactory, CardFactory
from src.payment_processor import PaymentProcessor, IdempotencyValidator
from src.retry_handler import RetryHandler


@pytest.fixture
def fake_gateway():
    """Provide a fake payment gateway."""
    gateway = FakeGateway(scenario=GatewayScenario.ALWAYS_SUCCESS)
    yield gateway
    gateway.reset()


@pytest.fixture
def fake_db():
    """Provide a fake database."""
    db = FakeDatabase()
    yield db
    db.clear()


@pytest.fixture
def idempotency_validator():
    """Provide an idempotency validator."""
    return IdempotencyValidator(cache_ttl_seconds=300)


@pytest.fixture
def retry_handler():
    """Provide a retry handler."""
    return RetryHandler(max_attempts=5, base_delay=1)


@pytest.fixture
def payment_processor(fake_gateway, fake_db, idempotency_validator, retry_handler):
    """Provide a payment processor with all dependencies."""
    return PaymentProcessor(
        gateway=fake_gateway,
        database=fake_db,
        idempotency_validator=idempotency_validator,
        retry_handler=retry_handler
    )


@pytest.fixture
def sample_payment():
    """Provide a sample payment."""
    return PaymentFactory.create(
        amount=Decimal("100.00"),
        currency="USD"
    )


@pytest.fixture
def sample_card():
    """Provide a sample card."""
    return CardFactory.create()
