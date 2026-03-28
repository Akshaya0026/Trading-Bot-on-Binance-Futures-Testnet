"""
Input validation for CLI arguments before they reach the API layer.
All validators raise ValueError with a descriptive message on failure.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Optional

SUPPORTED_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP"}
SUPPORTED_SIDES = {"BUY", "SELL"}
MIN_QUANTITY = Decimal("0.001")


def validate_symbol(symbol: str) -> str:
    """Normalise and validate a trading pair symbol."""
    symbol = symbol.strip().upper()
    if not symbol.isalnum():
        raise ValueError(
            f"Invalid symbol '{symbol}'. Must contain only letters and digits "
            "(e.g. BTCUSDT)."
        )
    if len(symbol) < 3 or len(symbol) > 20:
        raise ValueError(
            f"Symbol '{symbol}' length is unusual. Expected 3-20 characters."
        )
    return symbol


def validate_side(side: str) -> str:
    """Validate and normalise order side."""
    side = side.strip().upper()
    if side not in SUPPORTED_SIDES:
        raise ValueError(
            f"Invalid side '{side}'. Must be one of: {', '.join(SUPPORTED_SIDES)}."
        )
    return side


def validate_order_type(order_type: str) -> str:
    """Validate and normalise order type."""
    order_type = order_type.strip().upper()
    if order_type not in SUPPORTED_ORDER_TYPES:
        raise ValueError(
            f"Invalid order type '{order_type}'. "
            f"Must be one of: {', '.join(sorted(SUPPORTED_ORDER_TYPES))}."
        )
    return order_type


def validate_quantity(quantity: str) -> Decimal:
    """Parse and validate quantity as a positive Decimal."""
    try:
        qty = Decimal(str(quantity))
    except InvalidOperation:
        raise ValueError(f"Invalid quantity '{quantity}'. Must be a numeric value.")

    if qty <= 0:
        raise ValueError(f"Quantity must be positive. Got: {qty}")
    if qty < MIN_QUANTITY:
        raise ValueError(f"Quantity {qty} is below minimum allowed ({MIN_QUANTITY}).")
    return qty


def validate_price(price: Optional[str], order_type: str) -> Optional[Decimal]:
    """
    Validate price.

    - MARKET orders: price is ignored (returns None).
    - LIMIT / STOP orders: price is required and must be positive.
    """
    order_type = order_type.strip().upper()

    if order_type == "MARKET":
        if price is not None:
            # Silently ignore — market orders don't use a price
            pass
        return None

    if price is None or str(price).strip() == "":
        raise ValueError(f"Price is required for {order_type} orders.")

    try:
        p = Decimal(str(price))
    except InvalidOperation:
        raise ValueError(f"Invalid price '{price}'. Must be a numeric value.")

    if p <= 0:
        raise ValueError(f"Price must be positive. Got: {p}")

    return p


def validate_stop_price(
    stop_price: Optional[str], order_type: str
) -> Optional[Decimal]:
    """Validate stop price for STOP / STOP_MARKET orders."""
    order_type = order_type.strip().upper()

    if order_type not in {"STOP", "STOP_MARKET"}:
        return None  # Not required for other types

    if stop_price is None or str(stop_price).strip() == "":
        raise ValueError(f"--stop-price is required for {order_type} orders.")

    try:
        sp = Decimal(str(stop_price))
    except InvalidOperation:
        raise ValueError(f"Invalid stop price '{stop_price}'. Must be numeric.")

    if sp <= 0:
        raise ValueError(f"Stop price must be positive. Got: {sp}")

    return sp
