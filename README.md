# Binance Futures Testnet Trading Bot

A clean, well-structured Python CLI application for placing orders on the **Binance USDT-M Futures Testnet**.

---

## Features

| Feature | Details |
|---|---|
| Order types | `MARKET`, `LIMIT`, `STOP_MARKET`, `STOP` (stop-limit) |
| Sides | `BUY` and `SELL` |
| Input validation | Symbol, side, type, quantity, price, stop-price |
| Logging | Rotating file log + console (DEBUG to file, INFO to console) |
| Error handling | API errors, auth errors, network failures, bad input |
| Structure | Separate client / orders / validators / CLI layers |
| Credentials | `.env` file or CLI flags |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (signing, requests, error mapping)
│   ├── orders.py          # Order placement logic + formatted output
│   ├── validators.py      # Input validation helpers
│   └── logging_config.py  # Rotating file + console log setup
├── logs/
│   └── trading_bot.log    # Auto-created on first run
├── cli.py                 # Argparse CLI entry point
├── .env.example           # Credentials template
├── requirements.txt
└── README.md
```

---

## Setup

### 1 – Create a Binance Futures Testnet account

1. Visit <https://testnet.binancefuture.com>
2. Sign up / log in and navigate to **Account → API Key**
3. Generate a new API key + secret pair and copy them

### 2 – Clone and install dependencies

```bash
git clone https://github.com/your-username/trading_bot.git
cd trading_bot

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3 – Configure credentials

```bash
cp .env.example .env
```

Open `.env` and fill in your testnet credentials:

```
BINANCE_API_KEY=your_testnet_api_key_here
BINANCE_API_SECRET=your_testnet_api_secret_here
```

> **Security note:** Never commit your `.env` file. It is listed in `.gitignore`.

---

## How to Run

### General syntax

```bash
python cli.py --symbol SYMBOL --side BUY|SELL --type ORDER_TYPE --quantity QTY [--price PRICE] [--stop-price STOP_PRICE]
```

### Market order

```bash
# Buy 0.01 BTC at market price
python cli.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01

# Sell 0.1 ETH at market price
python cli.py --symbol ETHUSDT --side SELL --type MARKET --quantity 0.1
```

### Limit order

```bash
# Sell 0.01 BTC at $87,000 (GTC)
python cli.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.01 --price 87000

# Buy 0.01 BTC at $82,000 (IOC)
python cli.py --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.01 --price 82000 --time-in-force IOC
```

### Stop-Market order *(bonus)*

Triggers a market order when the stop price is reached.

```bash
# Protective stop: sell 0.01 BTC if price drops to $80,000
python cli.py --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.01 --stop-price 80000
```

### Stop-Limit order *(bonus)*

Triggers a limit order when the stop price is reached.

```bash
# Stop-limit: sell 0.01 BTC at $84,500 if price reaches $85,000
python cli.py --symbol BTCUSDT --side SELL --type STOP --quantity 0.01 --price 84500 --stop-price 85000
```

### Override credentials on the command line

```bash
python cli.py --api-key YOUR_KEY --api-secret YOUR_SECRET \
              --symbol BTCUSDT --side BUY --type MARKET --quantity 0.01
```

---

## Example Output

```
────────────────────────────────────────────────────────────
  ORDER REQUEST
────────────────────────────────────────────────────────────
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.01
────────────────────────────────────────────────────────────

  ORDER RESPONSE
────────────────────────────────────────────────────────────
  Order ID     : 4141237645
  Client OID   : aBcDeFgHiJkLmNo1
  Symbol       : BTCUSDT
  Side         : BUY
  Type         : MARKET
  Status       : FILLED
  Orig Qty     : 0.01
  Executed Qty : 0.01
  Avg Price    : 84321.50
────────────────────────────────────────────────────────────
  ✓ Order placed successfully  (id=4141237645, status=FILLED)
```

---

## Logging

All activity is written to `logs/trading_bot.log` (rotating, max 5 MB × 3 backups).

| Level | Destination | Content |
|---|---|---|
| `DEBUG` | File only | Full request params, raw response body |
| `INFO` | File + console | Order intent, success messages |
| `ERROR` | File + console | API errors, network failures, validation errors |

Log format:
```
2025-03-27 10:12:03 | INFO     | trading_bot.orders | Order placed successfully | id=4141237645 status=FILLED
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Missing credentials | Clear message, exit code 1 |
| Invalid symbol / side / type | Validation error printed, nothing sent to API |
| Quantity ≤ 0 | Rejected before API call |
| LIMIT order without `--price` | Rejected before API call |
| API auth failure (wrong key) | `BinanceAuthError` with actionable hint |
| API business error (e.g. bad qty) | `BinanceAPIError` with Binance error code |
| Network timeout / connection refused | `BinanceNetworkError` with clear message |

---

## Assumptions

1. **Testnet only** – The base URL is hardcoded to `https://testnet.binancefuture.com`. For production use, update `BASE_URL` in `bot/client.py`.
2. **USDT-M Futures** – All orders use the `/fapi/v1/order` endpoint (USDT-margined perpetuals).
3. **Hedge mode not supported** – The bot assumes one-way position mode (Binance default). For hedge mode, add a `positionSide` parameter.
4. **Quantity precision** – The bot passes the quantity as-is. If the testnet rejects an order due to precision, reduce decimal places (e.g. `0.001` → `0.01`).
5. **Time sync** – Uses `time.time()` for the request timestamp. If your system clock is more than 1 second off, set `recvWindow` higher in `bot/client.py`.

---

## Dependencies

```
requests>=2.31.0        # HTTP client
python-dotenv>=1.0.0    # .env file loading
```

> `python-dotenv` is optional — the bot includes a manual fallback parser if it is not installed.

---

## Running Tests (optional)

```bash
pip install pytest
pytest tests/   # if you add a tests/ directory
```
