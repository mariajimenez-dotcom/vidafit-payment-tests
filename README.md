# VidaFit Payment Testing Challenge

Comprehensive automated test suite to prevent duplicate payment charges that affected 2,300+ VidaFit customers.

## Challenge Overview

**Mission:** Build test suite that would have caught the four critical payment bugs:
1. Race condition in retry mechanism (missing idempotency validation)
2. Incorrect state transitions on soft declines
3. Payment method fallback bug (double charging)
4. Currency conversion rounding errors

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run only unit tests
pytest -m unit

# Run tests in parallel (faster)
pytest -n auto

# Run specific test file
pytest tests/unit/test_idempotency.py
```

## Project Structure

```
vidafit-payment-tests/
├── src/                    # Application code
│   ├── models.py          # Payment, Transaction models
│   ├── state_machine.py   # State transition rules
│   ├── payment_processor.py   # Core payment logic
│   ├── retry_handler.py   # Retry logic with idempotency
│   └── currency_converter.py # Multi-currency calculations
├── tests/
│   ├── unit/              # 20 unit tests (70% coverage)
│   ├── integration/       # 5 integration tests (20% coverage)
│   └── e2e/              # E2E test examples
├── mocks/                 # Test doubles
├── fixtures/              # Test data factories
└── docs/                  # Documentation
```

## Test Metrics

- **Total Tests:** 25+ (20 unit + 5 integration + 2 E2E examples)
- **Coverage Target:** >85%
- **Runtime Target:** <30 seconds (unit tests), <3 minutes (all tests)
- **Success Rate:** 100% (no flaky tests)

## CI/CD

Tests run automatically on push via GitHub Actions. See `.github/workflows/tests.yml`.

## Documentation

- [TEST_STRATEGY.md](docs/TEST_STRATEGY.md) - Testing approach and rationale
- [COVERAGE_REPORT.md](docs/COVERAGE_REPORT.md) - What's tested and gaps
- [TIME_DECISIONS.md](docs/TIME_DECISIONS.md) - 2-hour constraint trade-offs
