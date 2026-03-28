"""
Low-level Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - Timestamp synchronisation
  - HTTP request/response lifecycle
  - Structured logging of every outgoing request and incoming response
  - Granular exception mapping (network, API, auth errors)
"""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests

from .logging_config import setup_logger

BASE_URL = "https://testnet.binancefuture.com"
RECV_WINDOW = 5000  # ms – how long the server accepts the request

logger = setup_logger("trading_bot.client")


class BinanceAPIError(Exception):
    """Raised when the Binance API returns a non-2xx response."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Binance API error {code}: {message}")


class BinanceAuthError(BinanceAPIError):
    """Raised for authentication / signature errors (codes -2014, -1022, etc.)."""


class BinanceNetworkError(Exception):
    """Raised on transport-level failures (timeout, connection refused, etc.)."""


AUTH_ERROR_CODES = {-2014, -1022, -2015}


class BinanceClient:
    """
    Thin wrapper around the Binance Futures Testnet REST API.

    Usage::

        client = BinanceClient(api_key="...", api_secret="...")
        response = client.place_order(
            symbol="BTCUSDT",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0.01"),
        )
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = BASE_URL,
        timeout: int = 10,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("api_key and api_secret must not be empty.")

        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        logger.debug("BinanceClient initialised (base_url=%s)", self._base_url)

    # ──────────────────────────────────────────────────────────────────────
    # Public methods
    # ──────────────────────────────────────────────────────────────────────

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """
        Place a new order on Binance Futures Testnet.

        Args:
            symbol:        Trading pair, e.g. "BTCUSDT".
            side:          "BUY" or "SELL".
            order_type:    "MARKET", "LIMIT", "STOP", or "STOP_MARKET".
            quantity:      Order quantity.
            price:         Limit price (required for LIMIT / STOP).
            stop_price:    Trigger price (required for STOP / STOP_MARKET).
            time_in_force: "GTC" | "IOC" | "FOK" (ignored for MARKET orders).

        Returns:
            Parsed JSON response from the Binance API.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": str(quantity),
        }

        if order_type != "MARKET":
            params["timeInForce"] = time_in_force

        if price is not None:
            params["price"] = str(price)

        if stop_price is not None:
            params["stopPrice"] = str(stop_price)

        logger.info(
            "Placing %s %s order | symbol=%s qty=%s price=%s",
            side,
            order_type,
            symbol,
            quantity,
            price or "MARKET",
        )

        return self._signed_post("/fapi/v1/order", params)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Fetch details of an existing order."""
        return self._signed_get(
            "/fapi/v1/order", {"symbol": symbol, "orderId": order_id}
        )

    def get_account_info(self) -> Dict[str, Any]:
        """Return futures account information (balances, positions)."""
        return self._signed_get("/fapi/v2/account", {})

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _sign(self, params: Dict[str, Any]) -> str:
        """Append timestamp + recvWindow and return the HMAC-SHA256 signature."""
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = RECV_WINDOW
        query = urlencode(params)
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _signed_post(
        self, path: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        signature = self._sign(params)
        params["signature"] = signature
        url = f"{self._base_url}{path}"
        logger.debug("POST %s | params=%s", url, {k: v for k, v in params.items() if k != "signature"})
        return self._request("POST", url, data=params)

    def _signed_get(
        self, path: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        signature = self._sign(params)
        params["signature"] = signature
        url = f"{self._base_url}{path}"
        logger.debug("GET %s | params=%s", url, {k: v for k, v in params.items() if k != "signature"})
        return self._request("GET", url, params=params)

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Execute the HTTP request, log the result, and raise on errors."""
        try:
            response = self._session.request(
                method,
                url,
                params=params,
                data=data,
                timeout=self._timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("Request timed out: %s %s", method, url)
            raise BinanceNetworkError(f"Request timed out ({self._timeout}s).") from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s %s | %s", method, url, exc)
            raise BinanceNetworkError(f"Connection error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            logger.error("Request exception: %s", exc)
            raise BinanceNetworkError(f"Request failed: {exc}") from exc

        logger.debug(
            "Response | status=%s | body=%s",
            response.status_code,
            response.text[:500],
        )

        # Parse JSON; fall back to raw text on parse failure
        try:
            payload = response.json()
        except ValueError:
            logger.error("Non-JSON response (status=%s): %s", response.status_code, response.text)
            raise BinanceAPIError(response.status_code, response.text)

        if not response.ok:
            code = payload.get("code", response.status_code)
            msg = payload.get("msg", "Unknown error")
            logger.error("API error | code=%s | msg=%s", code, msg)
            if code in AUTH_ERROR_CODES:
                raise BinanceAuthError(code, msg)
            raise BinanceAPIError(code, msg)

        return payload
