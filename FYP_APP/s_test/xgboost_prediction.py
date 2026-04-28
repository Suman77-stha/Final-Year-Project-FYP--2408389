import xgboost as xgb
from FYP_APP.APS.StockAPI import get_stock_data
from datetime import datetime, timedelta

# ==============================
# CONFIG
# ==============================
FEATURES = ['sentiment', 'lstm_feature', 'return', 'ma7', 'volatility']

# ==============================
# MODEL LOAD
# ==============================
def load_model(symbol):
    model = xgb.XGBRegressor()
    model.load_model(f"data/processed/{symbol}_xgb_model.json")
    return model

# ==============================
# LIVE PRICE
# ==============================
def get_live_price(symbol):
    stock = get_stock_data(symbol.upper())

    if not stock or stock.get("price") is None:
        raise ValueError("Live price missing")

    price = stock.get("price")

    if price == 0:
        raise ValueError("Live price is zero")

    return float(price)

# ==============================
# TRADING DAY
# ==============================
def get_next_trading_day(date):
    next_day = date + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day

# ==============================
# PREDICT (NO CSV VERSION)
# ==============================
def predict(symbol="AAPL", future_days=5):

    model = load_model(symbol)

    # LIVE anchor price
    current_price = get_live_price(symbol)

    # 🔥 IMPORTANT: initialize feature state manually (NO CSV)
    state = {
        "sentiment": 0.0,
        "lstm_feature": 0.0,
        "return": 0.0,
        "ma7": current_price,
        "volatility": 0.0
    }

    predictions = []
    dates = []

    last_price = current_price
    current_date = datetime.utcnow().date()

    for _ in range(future_days):

        X = [[state[f] for f in FEATURES]]

        predicted_return = float(model.predict(X)[0])

        next_price = last_price * (1 + predicted_return)

        predictions.append(next_price)

        # update date
        current_date = get_next_trading_day(current_date)
        dates.append(str(current_date))

        # update state (self-learning loop)
        state["return"] = predicted_return
        state["ma7"] = (state["ma7"] * 6 + next_price) / 7
        state["volatility"] = abs(predicted_return)
        state["lstm_feature"] = state["lstm_feature"]
        state["sentiment"] = state["sentiment"]

        last_price = next_price

    return {
        "symbol": symbol,
        "current_price": current_price,
        "future_days": predictions,
        "predicted_price": predictions[0]
    }

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    print(predict("AAPL", 7))