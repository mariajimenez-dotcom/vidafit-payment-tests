# VidaFit Payment Testing Strategy

## Executive Summary

This document outlines the comprehensive testing strategy for preventing the four critical payment bugs that affected 2,300+ VidaFit customers, resulting in duplicate charges.

## Testing Approach

### Test Pyramid Distribution

We follow a unit-heavy test pyramid optimized for rapid feedback and high coverage:

- **70% Unit Tests (20 tests)** - Fast, isolated, testing pure logic
- **20% Integration Tests (5 tests)** - Realistic, testing component interactions
- **10% E2E Tests (2 tests)** - System validation, demonstrating full flows

**Rationale:** Unit tests provide 85%+ bug detection at <30s runtime. Integration tests validate persistence and orchestration. E2E tests demonstrate system thinking.

### Target Metrics

- **Total Tests:** 27 (20 unit + 5 integration + 2 E2E)
- **Coverage:** >85% code coverage
- **Runtime:** <30 seconds (unit), <3 minutes (all tests)
- **Reliability:** 100% pass rate (no flaky tests)

## Bug Prevention Mapping

### Bug #1: Race Condition Duplicate Charges

**Root Cause:** Network timeout led to duplicate charges due to missing idempotency validation.

**Prevention Tests:**
- `test_duplicate_request_returns_cached_response` - Same idempotency key → same result
- `test_idempotency_key_expires_after_ttl` - Keys expire correctly (7-day TTL)
- `test_concurrent_requests_same_key_single_charge` - 50 threads → 1 charge
- `test_retry_with_same_key_after_failure` - Retries preserve idempotency
- `test_idempotency_preserved_across_retries` - Same key for all attempts

**Detection Method:** Thread-based concurrency tests with assertion on gateway call count.

### Bug #2: Incorrect State Transitions on Soft Declines

**Root Cause:** Soft declines (insufficient funds) marked as "failed" but still queued capture requests.

**Prevention Tests:**
- `test_soft_decline_maps_to_retriable_state` - Soft decline → DECLINED_RETRIABLE (not FAILED)
- `test_hard_decline_maps_to_terminal_failed_state` - Hard decline → FAILED (terminal)
- `test_valid_state_transition_pending_to_processing` - Business rules enforced
- `test_invalid_transition_rejected` - Invalid transitions blocked

**Detection Method:** State machine validation with explicit test for soft decline mapping.

### Bug #3: Payment Method Fallback Double Charge

**Root Cause:** Successful auth + failed capture triggered both retry AND fallback charge without voiding.

**Prevention Tests:**
- `test_primary_auth_success_capture_fail_void_before_fallback` - **KEY TEST** - Verifies void before fallback
- `test_primary_success_no_fallback_triggered` - No cascade on success
- `test_all_methods_fail_graceful_error` - Exhausted cascade handling

**Detection Method:** Mock gateway tracking with assertion on `void_called` flag.

### Bug #4: Currency Conversion Rounding

**Root Cause:** 0.01 BRL discrepancies in multi-currency transactions due to floating point.

**Prevention Tests:**
- `test_brl_to_usd_conversion_accurate` - Exchange rate correctness
- `test_decimal_precision_no_floating_point_errors` - Use Decimal type
- `test_roundtrip_conversion_within_tolerance` - BRL→USD→BRL ≤ 0.01 variance
- `test_proper_rounding_to_2_decimals` - Standard currency rounding

**Detection Method:** Decimal arithmetic with explicit tolerance checks.

## Technology Stack

### Core Testing Framework: pytest + Python 3.9

**Justification:**
- Python 3.9.6 already installed (no environment setup)
- Built-in `decimal.Decimal` for currency precision
- pytest's fixture system perfect for rapid development
- Rich ecosystem for mocking and time control

**Key Dependencies:**
```
pytest>=7.4.0          # Testing framework
pytest-cov>=4.1.0      # Coverage reporting
pytest-xdist>=3.3.1    # Parallel execution
pytest-mock>=3.11.1    # Mocking utilities
freezegun>=1.2.2       # Deterministic time control
tenacity>=8.2.3        # Retry logic
```

## Mock Architecture

### FakeGateway - Configurable Payment Gateway Mock

**Features:**
- Predefined scenarios (success, timeout, decline, rate limit)
- Idempotency cache simulation
- Call logging for assertions
- Transaction tracking (auth, capture, void)

**Scenarios:**
- `ALWAYS_SUCCESS` - Happy path testing
- `NETWORK_TIMEOUT` - Retry logic testing
- `SOFT_DECLINE` - Retriable error testing
- `HARD_DECLINE` - Terminal error testing
- `AUTH_SUCCESS_CAPTURE_FAIL` - Cascade bug testing
- `INTERMITTENT` - Flaky gateway simulation

### FakeDatabase - In-Memory Database Mock

**Features:**
- Row-level locking simulation (threading.Lock)
- Payment and transaction persistence
- Fast, isolated tests (no external dependencies)

**Trade-off:** Less realistic than real database, but 100x faster for unit tests.

## Test Organization

### Directory Structure

```
tests/
├── conftest.py              # Global fixtures
├── unit/                    # 20 unit tests
│   ├── test_idempotency.py (5 tests - HIGHEST PRIORITY)
│   ├── test_state_machine.py (6 tests - Core logic)
│   ├── test_retry_logic.py (5 tests - Bug prevention)
│   └── test_currency.py (4 tests - Financial accuracy)
├── integration/             # 5 integration tests
│   ├── test_gateway_cascade.py (3 tests - Bug #3 prevention)
│   └── test_db_persistence.py (2 tests - State consistency)
└── e2e/                     # 2 E2E tests
    └── test_checkout_flow.py (Full system validation)
```

### Fixture Strategy

**Global Fixtures (conftest.py):**
- `fake_gateway` - Configurable mock gateway
- `fake_db` - In-memory database
- `payment_processor` - Fully wired processor
- `sample_payment` - Test payment data
- `sample_card` - Test card data

**Fixture Benefits:**
- DRY principle (reusable test setup)
- Automatic cleanup (yield pattern)
- Fast test execution (shared setup)

## CI/CD Pipeline

### GitHub Actions Workflow

**Stages:**
1. **Setup** - Install Python 3.9, cache dependencies
2. **Unit Tests** - Parallel execution with pytest-xdist
3. **Integration Tests** - Sequential execution with coverage append
4. **Coverage Check** - Enforce >85% threshold
5. **E2E Tests** - Only on main branch push (slow tests)
6. **Artifacts** - Upload coverage reports

**Performance Optimizations:**
- Dependency caching (faster installs)
- Parallel unit test execution (`-n auto`)
- E2E tests only on main branch (reduce CI time)

## Coverage Strategy

### Coverage Targets

- **Overall:** >85% line coverage
- **Critical Paths:** 100% coverage
  - Idempotency validation
  - State machine transitions
  - Retry logic
  - Currency conversion

### Coverage Exclusions

- Mock implementations (fake_gateway.py, fake_db.py)
- Test data factories (factories.py)
- Type definitions (models.py dataclasses)

### Coverage Reporting

```bash
# Generate coverage report
pytest --cov=src --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html

# Check threshold
coverage report --fail-under=85
```

## Future Enhancements

### With Additional Time (Week 2-4)

**Week 2: Depth**
- Real Postgres with Testcontainers
- Webhook delivery and retry tests
- Full payment method cascade (5+ gateways)
- Transaction audit logging tests

**Week 3: Breadth**
- Additional E2E checkout flows (5 scenarios)
- Race condition stress tests (1000+ threads)
- Chaos engineering (Toxiproxy network faults)
- Performance benchmarks (Locust load tests)

**Week 4: Production Readiness**
- Security tests (SQL injection, XSS)
- PCI-DSS compliance checks
- Test data seeding scripts
- Production deployment pipeline

### Additional Test Scenarios

**Documented but not implemented (time constraint):**
- Multi-currency checkout flows
- 3D Secure authentication
- Partial capture/void flows
- Refund processing
- Fraud detection integration
- Rate limiting behavior
- Gateway timeout recovery
- Webhook retry logic

## Test Execution

### Local Development

```bash
# Run all tests
pytest

# Run only unit tests (fast feedback)
pytest tests/unit -v

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_idempotency.py -v

# Run parallel (faster)
pytest -n auto

# Run only marked tests
pytest -m unit
pytest -m integration
pytest -m e2e
```

### CI/CD

Tests run automatically on:
- Every push to main/develop
- Every pull request
- Manual workflow dispatch

## Best Practices

### Test Naming Convention

- **Format:** `test_<what>_<expected_behavior>`
- **Example:** `test_duplicate_request_returns_cached_response`
- **Benefits:** Self-documenting, clear intent

### Test Structure (Arrange-Act-Assert)

```python
def test_example():
    # Arrange: Set up test data
    payment = PaymentFactory.create()

    # Act: Execute system under test
    response = processor.process_payment(payment)

    # Assert: Verify expected behavior
    assert response.success
```

### Test Independence

- Each test runs in isolation
- No shared state between tests
- Fixtures handle cleanup automatically
- Tests can run in any order

### Deterministic Testing

- Use `freezegun` for time-based tests
- Seed random generators
- No network calls (use mocks)
- No flaky tests tolerated

## Conclusion

This testing strategy provides comprehensive coverage of the critical payment bugs that affected VidaFit customers. The unit-heavy pyramid ensures fast feedback, while integration and E2E tests validate system behavior. The test suite is designed for maintainability, extensibility, and production readiness.

**Key Success Factors:**
- Bug prevention through targeted test cases
- Fast execution for rapid development feedback
- High coverage with quality over quantity focus
- Clear documentation and organization
- CI/CD automation for continuous validation
