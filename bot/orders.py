"""
Order placement logic and result formatting.

Sits between the CLI layer and the raw BinanceClient.
Responsible for:
  - Calling the client with validated parameters
  - Extracting and normalising the fields we care about
  - Printing a human-readable order summary and result
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, Optional

from .client import BinanceClient, BinanceAPIError, BinanceAuthError, BinanceNetworkError
from .logging_config import setup_logger

logger = setup_logger("trading_bot.orders")


# ── Pretty-print helpers ───────────────────────────────────────────────────────

_DIVIDER = "─" * 60


def _print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal],
    stop_price: Optional[Decimal],
) -> None:
    print(f"\n{_DIVIDER}")
    print("  ORDER REQUEST")
    print(_DIVIDER)
    print(f"  Symbol     : {symbol}")
    print(f"  Side       : {side}")
    print(f"  Type       : {order_type}")
    print(f"  Quantity   : {quantity}")
    if price is not None:
        print(f"  Price      : {price}")
    if stop_price is not None:
        print(f"  Stop Price : {stop_price}")
    print(_DIVIDER)


def _print_order_result(response: Dict[str, Any]) -> None:
    print("\n  ORDER RESPONSE")
    print(_DIVIDER)
    print(f"  Order ID     : {response.get('orderId', 'N/A')}")
    print(f"  Client OID   : {response.get('clientOrderId', 'N/A')}")
    print(f"  Symbol       : {response.get('symbol', 'N/A')}")
    print(f"  Side         : {response.get('side', 'N/A')}")
    print(f"  Type         : {response.get('type', 'N/A')}")
    print(f"  Status       : {response.get('status', 'N/A')}")
    print(f"  Orig Qty     : {response.get('origQty', 'N/A')}")
    print(f"  Executed Qty : {response.get('executedQty', 'N/A')}")

    avg_price = response.get("avgPrice") or response.get("price")
    print(f"  Avg Price    : {avg_price or 'N/A'}")

    time_in_force = response.get("timeInForce")
    if time_in_force:
        print(f"  Time-in-Force: {time_in_force}")

    print(_DIVIDER)


# ── Core function ──────────────────────────────────────────────────────────────

def place_order(
    client: BinanceClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: Decimal,
    price: Optional[Decimal] = None,
    stop_price: Optional[Decimal] = None,
    time_in_force: str = "GTC",
) -> Dict[str, Any]:
    """
    Place an order via the Binance client and print a formatted summary.

    Args:
        client:        Initialised BinanceClient.
        symbol:        Trading pair (validated, upper-cased).
        side:          "BUY" or "SELL".
        order_type:    "MARKET", "LIMIT", "STOP", or "STOP_MARKET".
        quantity:      Order quantity (Decimal).
        price:         Limit price (Decimal | None).
        stop_price:    Stop trigger price (Decimal | None).
        time_in_force: Time-in-force policy (default "GTC").

    Returns:
        Raw API response dict.

    Raises:
        BinanceAPIError, BinanceAuthError, BinanceNetworkError on failure.
    """
    _print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    try:
        response = client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
        )
    except BinanceAuthError as exc:
        logger.error("Authentication failure: %s", exc)
        print(f"\n  ✗ Authentication error: {exc.message}")
        print("    → Check your API key and secret in the .env file.\n")
        raise
    except BinanceAPIError as exc:
        logger.error("Order placement failed: %s", exc)
        print(f"\n  ✗ API error ({exc.code}): {exc.message}\n")
        raise
    except BinanceNetworkError as exc:
        logger.error("Network error during order placement: %s", exc)
        print(f"\n  ✗ Network error: {exc}\n")
        raise

    _print_order_result(response)

    status = response.get("status", "UNKNOWN")
    order_id = response.get("orderId", "N/A")
    if status in {"NEW", "FILLED", "PARTIALLY_FILLED"}:
        print(f"  ✓ Order placed successfully  (id={order_id}, status={status})\n")
        logger.info("Order placed successfully | id=%s status=%s", order_id, status)
    else:
        print(f"  ⚠ Order submitted but status is '{status}'  (id={order_id})\n")
        logger.warning("Unexpected order status | id=%s status=%s", order_id, status)

    return response
