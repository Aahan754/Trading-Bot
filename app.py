from flask import Flask, render_template, request, jsonify
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest

app = Flask(__name__)

# 1. Paste your Alpaca Paper Trading API Keys here
API_KEY = "YOUR_ALPACA_PAPER_API_KEY"
SECRET_KEY = "YOUR_ALPACA_PAPER_SECRET_KEY"

# Initialize Alpaca Market Data Client for exact stock prices
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# 2. Simulated $1,000 Paper Wallet State
STARTING_BALANCE = 1000.00
portfolio = {
    "cash": STARTING_BALANCE,
    "positions": {}  # Format: {"AAPL": {"shares": 2.5, "avg_price": 190.00}}
}


def get_exact_price(symbol: str) -> float:
    """Fetches the exact latest trade price from Alpaca."""
    req = StockLatestTradeRequest(symbol_or_symbols=symbol.upper())
    trade = data_client.get_stock_latest_trade(req)
    return float(trade[symbol.upper()].price)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status", methods=["GET"])
def status():
    """Calculates live portfolio value, exact stock prices, and total gain/loss."""
    holdings_value = 0.0
    detailed_positions = []

    for symbol, data in portfolio["positions"].items():
        if data["shares"] > 0:
            live_price = get_exact_price(symbol)
            market_val = data["shares"] * live_price
            cost_basis = data["shares"] * data["avg_price"]
            pnl = market_val - cost_basis
            holdings_value += market_val

            detailed_positions.append({
                "symbol": symbol,
                "shares": round(data["shares"], 4),
                "avg_price": round(data["avg_price"], 2),
                "live_price": round(live_price, 2),
                "market_value": round(market_val, 2),
                "pnl": round(pnl, 2)
            })

    total_equity = portfolio["cash"] + holdings_value
    net_gain_loss = total_equity - STARTING_BALANCE
    pct_gain_loss = (net_gain_loss / STARTING_BALANCE) * 100

    return jsonify({
        "starting_balance": STARTING_BALANCE,
        "cash": round(portfolio["cash"], 2),
        "holdings_value": round(holdings_value, 2),
        "total_equity": round(total_equity, 2),
        "net_gain_loss": round(net_gain_loss, 2),
        "pct_gain_loss": round(pct_gain_loss, 2),
        "positions": detailed_positions
    })


@app.route("/api/quote/<symbol>", methods=["GET"])
def quote(symbol):
    """Returns exact live price for any searched ticker."""
    try:
        price = get_exact_price(symbol)
        return jsonify({"symbol": symbol.upper(), "price": round(price, 2)})
    except Exception as e:
        return jsonify({"error": f"Invalid ticker or API error: {str(e)}"}), 400


@app.route("/api/trade", methods=["POST"])
def trade():
    """Executes fractional Buy or Sell orders at exact market price."""
    data = request.json
    symbol = data.get("symbol", "").upper().strip()
    side = data.get("side")  # "buy" or "sell"
    dollar_amount = float(data.get("amount", 0))

    if not symbol or dollar_amount <= 0:
        return jsonify({"error": "Enter a valid ticker and dollar amount."}), 400

    try:
        exact_price = get_exact_price(symbol)
    except Exception:
        return jsonify({"error": f"Could not fetch exact market price for {symbol}."}), 400

    if side == "buy":
        if dollar_amount > portfolio["cash"]:
            return jsonify({"error": "Insufficient virtual cash balance."}), 400

        shares_bought = dollar_amount / exact_price
        portfolio["cash"] -= dollar_amount

        if symbol in portfolio["positions"]:
            old_shares = portfolio["positions"][symbol]["shares"]
            old_cost = old_shares * portfolio["positions"][symbol]["avg_price"]
            new_shares = old_shares + shares_bought
            portfolio["positions"][symbol] = {
                "shares": new_shares,
                "avg_price": (old_cost + dollar_amount) / new_shares
            }
        else:
            portfolio["positions"][symbol] = {
                "shares": shares_bought,
                "avg_price": exact_price
            }

        return jsonify({"message": f"Bought ${dollar_amount:.2f} of {symbol} @ ${exact_price:.2f}"})

    elif side == "sell":
        pos = portfolio["positions"].get(symbol)
        if not pos or pos["shares"] <= 0:
            return jsonify({"error": f"You do not own any shares of {symbol}."}), 400

        current_value = pos["shares"] * exact_price
        sell_value = min(dollar_amount, current_value)
        shares_sold = sell_value / exact_price

        pos["shares"] -= shares_sold
        portfolio["cash"] += sell_value

        if pos["shares"] < 0.00001:
            del portfolio["positions"][symbol]

        return jsonify({"message": f"Sold ${sell_value:.2f} of {symbol} @ ${exact_price:.2f}"})

    return jsonify({"error": "Invalid order side."}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5000)
