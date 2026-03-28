"""
Flask web server — exposes the trading bot via a REST API for the UI.
"""

from __future__ import annotations

import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Load .env before importing bot modules
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from bot.client import BinanceClient, BinanceAPIError, BinanceAuthError, BinanceNetworkError

app = Flask(__name__, static_folder="ui", static_url_path="")
CORS(app)

LOG_FILE = Path(__file__).parent / "logs" / "trading_bot.log"


def _get_client():
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env")
    return BinanceClient(api_key=api_key, api_secret=api_secret)


@app.route("/")
def index():
    return send_from_directory("ui", "index.html")


@app.route("/api/order", methods=["POST"])
def place_order():
    data = request.get_json()

    symbol = (data.get("symbol") or "").strip().upper()
    side = (data.get("side") or "").strip().upper()
    order_type = (data.get("type") or "").strip().upper()
    quantity_raw = data.get("quantity", "")
    price_raw = data.get("price", "")
    stop_price_raw = data.get("stop_price", "")

    # Validate
    if not symbol:
        return jsonify({"error": "Symbol is required"}), 400
    if side not in ("BUY", "SELL"):
        return jsonify({"error": "Side must be BUY or SELL"}), 400
    if order_type not in ("MARKET", "LIMIT", "STOP", "STOP_MARKET"):
        return jsonify({"error": "Invalid order type"}), 400

    try:
        quantity = Decimal(str(quantity_raw))
    except InvalidOperation:
        return jsonify({"error": "Invalid quantity"}), 400

    price = None
    if price_raw:
        try:
            price = Decimal(str(price_raw))
        except InvalidOperation:
            return jsonify({"error": "Invalid price"}), 400

    stop_price = None
    if stop_price_raw:
        try:
            stop_price = Decimal(str(stop_price_raw))
        except InvalidOperation:
            return jsonify({"error": "Invalid stop price"}), 400

    if order_type in ("LIMIT", "STOP") and price is None:
        return jsonify({"error": f"Price is required for {order_type} orders"}), 400
    if order_type in ("STOP", "STOP_MARKET") and stop_price is None:
        return jsonify({"error": f"Stop price is required for {order_type} orders"}), 400

    try:
        client = _get_client()
        result = client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
        )
        return jsonify({"success": True, "data": result})
    except BinanceAuthError as e:
        return jsonify({"error": f"Auth error: {e.message}"}), 401
    except BinanceAPIError as e:
        return jsonify({"error": f"API error {e.code}: {e.message}"}), 400
    except BinanceNetworkError as e:
        return jsonify({"error": f"Network error: {e}"}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/logs", methods=["GET"])
def get_logs():
    try:
        if LOG_FILE.exists():
            lines = LOG_FILE.read_text().strip().splitlines()
            return jsonify({"logs": lines[-50:]})  # last 50 lines
        return jsonify({"logs": []})
    except Exception as e:
        return jsonify({"logs": [], "error": str(e)})


if __name__ == "__main__":
    app.run(debug=True, port=5050)
