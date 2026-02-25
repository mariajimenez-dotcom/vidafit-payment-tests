"""
Unit tests for currency conversion with proper decimal handling.

These tests prevent Bug #4: Currency conversion rounding errors (0.01 BRL discrepancies).
"""

from decimal import Decimal

import pytest

from src.currency_converter import (CurrencyConversionError, convert_currency,
                                    get_conversion_variance,
                                    roundtrip_conversion)


@pytest.mark.unit
class TestCurrencyConversion:
    """Test suite for currency conversion logic."""

    def test_brl_to_usd_conversion_accurate(self):
        """
        Test that BRL to USD conversion is accurate using predefined rate.
        """
        amount = Decimal("100.00")  # 100 BRL
        from_currency = "BRL"
        to_currency = "USD"

        # Convert BRL to USD (rate: 0.1905)
        result = convert_currency(amount, from_currency, to_currency)

        # Expected: 100 * 0.1905 = 19.05
        expected = Decimal("19.05")
        assert result == expected

    def test_decimal_precision_no_floating_point_errors(self):
        """
        Test that Decimal type prevents floating point precision errors.

        Prevents: Bug #4 - Floating point rounding errors
        """
        # Test a value known to cause floating point issues
        amount = Decimal("0.1") + Decimal("0.2")

        # With Decimal, this should be exactly 0.3
        assert amount == Decimal("0.3")

        # Test conversion maintains precision
        result = convert_currency(
            Decimal("100.00"), "USD", "BRL", exchange_rate=Decimal("5.25")
        )

        # Should be exactly 525.00, not 524.9999999
        assert result == Decimal("525.00")
        assert isinstance(result, Decimal)

    def test_same_currency_passthrough_no_conversion(self):
        """
        Test that same currency conversion is optimized (no conversion occurs).
        """
        amount = Decimal("123.45")
        currency = "USD"

        result = convert_currency(amount, currency, currency)

        # Should return exact same amount
        assert result == amount
        assert result is amount or result == amount  # Same object or equal value

    def test_roundtrip_conversion_within_tolerance(self):
        """
        Test that roundtrip conversion (BRL→USD→BRL) has variance ≤ 0.01.

        Prevents: Bug #4 - Accumulating rounding errors in multi-currency transactions
        """
        original_amount = Decimal("100.00")
        from_currency = "BRL"
        to_currency = "USD"

        # Do roundtrip conversion
        result = roundtrip_conversion(original_amount, from_currency, to_currency)

        # Calculate variance
        variance = get_conversion_variance(original_amount, result)

        # Variance should be at most 0.01 (1 cent)
        assert variance <= Decimal("0.01"), f"Variance {variance} exceeds tolerance"

        # Result should be very close to original
        assert abs(result - original_amount) <= Decimal("0.01")

    def test_unsupported_currency_pair_raises_error(self):
        """
        Test that unsupported currency pairs raise appropriate error.
        """
        amount = Decimal("100.00")

        with pytest.raises(CurrencyConversionError) as exc_info:
            convert_currency(amount, "USD", "JPY")  # No JPY rate defined

        assert "No exchange rate found" in str(exc_info.value)

    def test_custom_exchange_rate(self):
        """
        Test that custom exchange rates can be provided.
        """
        amount = Decimal("100.00")
        custom_rate = Decimal("6.00")

        result = convert_currency(amount, "USD", "BRL", exchange_rate=custom_rate)

        # Should use custom rate: 100 * 6.00 = 600.00
        assert result == Decimal("600.00")

    def test_proper_rounding_to_2_decimals(self):
        """
        Test that amounts are properly rounded to 2 decimal places.
        """
        # Amount that would need rounding
        amount = Decimal("100.00")
        rate = Decimal("1.666666")  # Results in repeating decimal

        result = convert_currency(amount, "USD", "EUR", exchange_rate=rate)

        # Check result has exactly 2 decimal places
        assert result == result.quantize(Decimal("0.01"))

        # Convert to string and verify format
        result_str = str(result)
        decimal_places = len(result_str.split(".")[-1]) if "." in result_str else 0
        assert decimal_places == 2
