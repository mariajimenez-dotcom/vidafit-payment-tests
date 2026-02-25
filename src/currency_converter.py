"""Currency conversion with proper decimal handling."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, Optional

# Sample exchange rates (in production, fetch from external API)
EXCHANGE_RATES: Dict[tuple, Decimal] = {
    ("USD", "BRL"): Decimal("5.25"),
    ("BRL", "USD"): Decimal("0.1905"),
    ("USD", "EUR"): Decimal("0.92"),
    ("EUR", "USD"): Decimal("1.087"),
}


class CurrencyConversionError(Exception):
    """Raised when currency conversion fails."""

    pass


def convert_currency(
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    exchange_rate: Optional[Decimal] = None,
) -> Decimal:
    """
    Convert amount from one currency to another using Decimal for precision.

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "USD")
        to_currency: Target currency code (e.g., "BRL")
        exchange_rate: Optional specific rate to use

    Returns:
        Converted amount as Decimal with proper rounding

    Raises:
        CurrencyConversionError: If conversion fails or rate not found
    """
    # Same currency - no conversion needed
    if from_currency == to_currency:
        return amount

    # Get exchange rate
    if exchange_rate is None:
        rate_key = (from_currency, to_currency)
        if rate_key not in EXCHANGE_RATES:
            raise CurrencyConversionError(
                f"No exchange rate found for {from_currency} to {to_currency}"
            )
        exchange_rate = EXCHANGE_RATES[rate_key]

    # Ensure we're working with Decimal types
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    rate_decimal = (
        Decimal(str(exchange_rate))
        if not isinstance(exchange_rate, Decimal)
        else exchange_rate
    )

    # Perform conversion
    converted = amount_decimal * rate_decimal

    # Round to 2 decimal places (standard for most currencies)
    return converted.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def roundtrip_conversion(
    amount: Decimal, from_currency: str, to_currency: str
) -> Decimal:
    """
    Convert currency and convert back to verify precision.

    Returns:
        Amount after roundtrip conversion
    """
    converted = convert_currency(amount, from_currency, to_currency)
    return convert_currency(converted, to_currency, from_currency)


def get_conversion_variance(original: Decimal, roundtrip: Decimal) -> Decimal:
    """Calculate variance between original and roundtrip amount."""
    return abs(original - roundtrip)
