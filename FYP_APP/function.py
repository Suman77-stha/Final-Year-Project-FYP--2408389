# FYP_APP/function.py

import yfinance as yf
from datetime import timedelta
from .lstm_model import predict_lstm

def get_lstm_graph(symbol, future_days=7):
    df = yf.download(symbol, period="1y")

    if df.empty:
        raise ValueError("No historical data found")

    predictions = predict_lstm(symbol, future_days)

    future_dates = [
        df.index[-1] + timedelta(days=i + 1)
        for i in range(future_days)
    ]

    return {
        "historical": {
            "dates": df.index.strftime("%Y-%m-%d").tolist(),
            "prices": df["Close"].tolist(),
        },
        "predicted": {
            "dates": [d.strftime("%Y-%m-%d") for d in future_dates],
            "prices": predictions,
        },
    }