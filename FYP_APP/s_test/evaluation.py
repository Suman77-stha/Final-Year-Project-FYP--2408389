# import pandas as pd
# import xgboost as xgb
# from sklearn.metrics import mean_absolute_error, mean_squared_error
# import numpy as np

# def evaluate():
#     df = pd.read_csv("data/processed/final_dataset.csv")

#     features = [
#         'return', 'ma7', 'volatility',
#         'sentiment', 'lstm_feature'
#     ]

#     X = df[features]
#     y = df['target']

#     split = int(len(df) * 0.8)

#     X_test = X[split:]
#     y_test = y[split:]

#     model = xgb.XGBRegressor()
#     model.load_model("data/processed/xgb_model.json")

#     preds = model.predict(X_test)

#     mae = mean_absolute_error(y_test, preds)
#     rmse = np.sqrt(mean_squared_error(y_test, preds))

#     print("Evaluation Results:")
#     print(f"MAE  : {mae}")
#     print(f"RMSE : {rmse}")

# if __name__ == "__main__":
#     evaluate()

# import pandas as pd
# import xgboost as xgb
# from sklearn.metrics import mean_absolute_error, mean_squared_error
# import numpy as np
# from FYP_APP.APS.StockAPI import get_stock_data
# def evaluate(symbol="AAPL"):
#     df = pd.read_csv("data/processed/final_dataset.csv")

#     features = [
#         'return', 'ma7', 'volatility',
#         'sentiment', 'lstm_feature'
#     ]

#     # Ensure proper date column
#     df["date"] = pd.to_datetime(df["date"])

#     X = df[features]
#     y = df["target"]

#     split = int(len(df) * 0.8)

#     X_test = X[split:]
#     y_test = y[split:]
#     test_dates = df["date"].iloc[split:]

#     model = xgb.XGBRegressor()
#     model.load_model("data/processed/xgb_model.json")

#     preds = model.predict(X_test)

#     mae = mean_absolute_error(y_test, preds)
#     rmse = np.sqrt(mean_squared_error(y_test, preds))

#     # Date-wise mapping (no system date used)
#     predictions = []
#     for i in range(len(preds)):
#         predictions.append({
#             "date": str(test_dates.iloc[i]),
#             "actual": float(y_test.iloc[i]),
#             "predicted": float(preds[i]),
#             "error": float(abs(y_test.iloc[i] - preds[i]))
#         })

#     return {
#         "symbol": symbol,

#         "metrics": {
#             "mae": float(mae),
#             "rmse": float(rmse)
#         },

#         "predictions": predictions,

#         "summary": {
#             "test_start_date": str(test_dates.iloc[0]),
#             "test_end_date": str(test_dates.iloc[-1]),
#             "total_samples": len(preds),
#             "last_prediction": float(preds[-1])
#         }
#     }

# if __name__ == "__main__":
#     result = evaluate("AAPL")
#     print(result)


import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import numpy as np
import requests
from datetime import datetime, timedelta


# ==============================
# 1. STOCK API (LIVE DATA)
# ==============================
def get_stock_data(symbol, api_key):
    url = "https://api.stockdata.org/v1/data/quote"

    params = {
        "symbols": symbol,
        "api_token": api_key
    }

    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    stock = data["data"][0]

    return {
        "symbol": stock.get("ticker"),
        "company": stock.get("name"),
        "currency": stock.get("currency"),
        "utc_dt": stock.get("last_updated"),
        "open_price": float(stock.get("day_open", 0)),
        "high_price": float(stock.get("day_high", 0)),
        "low_price": float(stock.get("day_low", 0)),
        "close_price": float(stock.get("price", 0)),
        "volume": float(stock.get("volume", 0)),
        "change": float(stock.get("day_change", 0)),
    }


# ==============================
# 2. NEXT TRADING DAY LOGIC
# ==============================
def get_next_trading_day(start_date=None):
    if start_date is None:
        start_date = datetime.utcnow().date()

    next_day = start_date + timedelta(days=1)

    # skip weekends
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)

    return next_day


def generate_future_trading_days(days=7):
    dates = []
    current = get_next_trading_day()

    while len(dates) < days:
        dates.append(current)
        current += timedelta(days=1)

        while current.weekday() >= 5:
            current += timedelta(days=1)

    return dates


# ==============================
# 3. MAIN EVALUATION FUNCTION
# ==============================
def evaluate(symbol="AAPL", api_key="YOUR_API_KEY"):
    # ------------------------
    # LIVE STOCK DATA
    # ------------------------
    stock = get_stock_data(symbol, api_key)

    # ------------------------
    # LOAD DATASET
    # ------------------------
    df = pd.read_csv(f"data/processed/{symbol}_final_dataset.csv")

    features = [
        'return', 'ma7', 'volatility',
        'sentiment', 'lstm_feature'
    ]

    df["date"] = pd.to_datetime(df["date"])

    X = df[features]
    y = df["target"]

    split = int(len(df) * 0.8)

    X_test = X[split:]
    y_test = y[split:]
    test_dates = df["date"].iloc[split:]

    # ------------------------
    # LOAD MODEL
    # ------------------------
    model = xgb.XGBRegressor()
    model.load_model(f"data/processed/{symbol}_xgb_model.json")

    preds = model.predict(X_test)

    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))

    # ------------------------
    # CLEAN TEST PREDICTIONS
    # ------------------------
    predictions = []
    for i in range(len(preds)):
        predictions.append({
            "date": str(test_dates.iloc[i].date()),
            "actual": round(float(y_test.iloc[i]), 2),
            "predicted": round(float(preds[i]), 2),
            "error": round(abs(float(y_test.iloc[i]) - float(preds[i])), 2)
        })

    # ------------------------
    # FUTURE PREDICTIONS (7 DAYS)
    # ------------------------
    future_dates = generate_future_trading_days(7)

    future_predictions = []
    last_price = stock["close_price"]

    temp_input = [last_price] * len(features)

    for i in range(7):
        x_input = np.array(temp_input[-len(features):]).reshape(1, -1)
        pred = model.predict(x_input)[0]

        future_predictions.append({
            "date": future_dates[i].strftime("%Y-%m-%d"),
            "predicted_price": round(float(pred), 2),
            "change_from_last": round(float(pred - last_price), 2)
        })

        temp_input.append(pred)

    # ------------------------
    # FINAL RESPONSE
    # ------------------------
    return {
        "live_stock": stock,

        "metrics": {
            "mae": round(float(mae), 2),
            "rmse": round(float(rmse), 2)
        },

        "evaluation_predictions": predictions,

        "future_predictions": {
            "start_date": future_dates[0].strftime("%Y-%m-%d"),
            "end_date": future_dates[-1].strftime("%Y-%m-%d"),
            "data": future_predictions
        },

        "summary": {
            "test_start_date": str(test_dates.iloc[0].date()),
            "test_end_date": str(test_dates.iloc[-1].date()),
            "total_test_samples": len(preds),
            "last_evaluation_prediction": round(float(preds[-1]), 2)
        }
    }


# ==============================
# 4. RUN
# ==============================
if __name__ == "__main__":
    result = evaluate("AAPL", api_key="RH1cObRmVBGqK0a9SmEBdJfs6LT5TsAEvxKbswCB")
    print(result)