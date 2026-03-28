#!/usr/bin/env python3
"""
CLI entry point for the Binance Futures Testnet trading bot.

Usage examples:
  # Market BUY
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

  # Limit SELL
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.1 --price 2000

  # Stop-Market BUY (bonus order type)
  python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.01 --stop-price 85000

  # Use a custom .env file
  python cli.py --env-file /path/to/my.env --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── Optional dotenv support ───────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

from bot.client import BinanceClient, BinanceAPIError, BinanceNetworkError
from bot.orders import place_order
from bot.validators import (
    validate_symbol,
    validate_side,
    validate_order_type,
    validate_quantity,
    validate_price,
    validate_stop_price,
)
from bot.logging_config import setup_logger

logger = setup_logger("trading_bot.cli")


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description=(
            "Binance Futures Testnet – order placement CLI\n"
            "Supported order types: MARKET | LIMIT | STOP | STOP_MARKET"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # Market buy
  python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

  # Limit sell
  python cli.py --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.1 --price 2000

  # Stop-Market (bonus type)
  python cli.py --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.01 --stop-price 85000

  # Stop-Limit (bonus type)
  python cli.py --symbol BTCUSDT --side SELL --type STOP --quantity 0.01 --price 84500 --stop-price 85000
        """,
    )

    # ── Credentials / config ──────────────────────────────────────────────
    creds = parser.add_argument_group("credentials (override .env file)")
    creds.add_argument(
        "--api-key",
        default=None,
        help="Binance API key (or set BINANCE_API_KEY in .env)",
    )
    creds.add_argument(
        "--api-secret",
        default=None,
        help="Binance API secret (or set BINANCE_API_SECRET in .env)",
    )
    creds.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file with BINANCE_API_KEY / BINANCE_API_SECRET (default: .env)",
    )

    # ── Order parameters ──────────────────────────────────────────────────
    order = parser.add_argument_group("order parameters")
    order.add_argument(
        "--symbol", "-s",
        required=True,
        help="Trading pair symbol, e.g. BTCUSDT",
    )
    order.add_argument(
        "--side",
        required=True,
        choices=["BUY", "SELL", "buy", "sell"],
        help="Order side: BUY or SELL",
    )
    order.add_argument(
        "--type", "-t",
        dest="order_type",
        required=True,
        choices=["MARKET", "LIMIT", "STOP", "STOP_MARKET",
                 "market", "limit", "stop", "stop_market"],
        help="Order type: MARKET | LIMIT | STOP | STOP_MARKET",
    )
    order.add_argument(
        "--quantity", "-q",
        required=True,
        help="Order quantity, e.g. 0.01",
    )
    order.add_argument(
        "--price", "-p",
        default=None,
        help="Limit price (required for LIMIT / STOP orders)",
    )
    order.add_argument(
        "--stop-price",
        default=None,
        help="Stop trigger price (required for STOP / STOP_MARKET orders)",
    )
    order.add_argument(
        "--time-in-force", "-f",
        default="GTC",
        choices=["GTC", "IOC", "FOK"],
        help="Time-in-force for LIMIT orders (default: GTC)",
    )

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # ── Load .env credentials ─────────────────────────────────────────────
    env_path = Path(args.env_file)
    if _HAS_DOTENV and env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.debug("Loaded environment from %s", env_path)
    elif not _HAS_DOTENV and env_path.exists():
        # Manual .env parsing fallback (no python-dotenv)
        with env_path.open() as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip())

    api_key = args.api_key or os.environ.get("BINANCE_API_KEY", "")
    api_secret = args.api_secret or os.environ.get("BINANCE_API_SECRET", "")

    if not api_key or not api_secret:
        print(
            "\n  ✗ Missing credentials.\n"
            "    Set BINANCE_API_KEY and BINANCE_API_SECRET in your .env file,\n"
            "    or pass --api-key / --api-secret on the command line.\n"
        )
        return 1

    # ── Validate inputs ───────────────────────────────────────────────────
    try:
        symbol = validate_symbol(args.symbol)
        side = validate_side(args.side)
        order_type = validate_order_type(args.order_type)
        quantity = validate_quantity(args.quantity)
        price = validate_price(args.price, order_type)
        stop_price = validate_stop_price(args.stop_price, order_type)
    except ValueError as exc:
        print(f"\n  ✗ Validation error: {exc}\n")
        logger.error("Validation error: %s", exc)
        return 1

    logger.info(
        "CLI invoked | symbol=%s side=%s type=%s qty=%s price=%s stop=%s",
        symbol, side, order_type, quantity, price, stop_price,
    )

    # ── Initialise client ─────────────────────────────────────────────────
    try:
        client = BinanceClient(api_key=api_key, api_secret=api_secret)
    except ValueError as exc:
        print(f"\n  ✗ Configuration error: {exc}\n")
        return 1

    # ── Place order ───────────────────────────────────────────────────────
    try:
        place_order(
            client=client,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=args.time_in_force,
        )
    except (BinanceAPIError, BinanceNetworkError):
        # Errors already logged and printed inside place_order
        return 1
    except Exception as exc:
        print(f"\n  ✗ Unexpected error: {exc}\n")
        logger.exception("Unexpected error: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
