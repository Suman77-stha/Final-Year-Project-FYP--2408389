# AI PRICE PREDICTION MODULE
import datetime
import pytz
import os
import numpy as np
import pandas as pd
import yfinance as yf

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from tensorflow import keras


def load_stock_data(symbol):
    """
    Downloads historical stock data from Yahoo Finance
    """
    START = "2015-01-01"
    TODAY = datetime.datetime.now(
        pytz.timezone("Asia/Kathmandu")
    ).date()

    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

    data = yf.download(symbol, START, TODAY)
    data.reset_index(inplace=True)
    return data


def predict_stock_price(symbol="TSLA"):
    """
    Trains LSTM model and predicts future stock price
    Returns prediction and model accuracy
    """

    data = load_stock_data(symbol)

    close_prices = data["Close"].values.reshape(-1, 1)

    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(close_prices)

    train_len = int(len(scaled_data) * 0.95)
    train_data = scaled_data[:train_len]

    X_train, y_train = [], []

    for i in range(60, len(train_data)):
        X_train.append(train_data[i-60:i, 0])
        y_train.append(train_data[i, 0])

    X_train = np.array(X_train)
    y_train = np.array(y_train)
    X_train = X_train.reshape(
        X_train.shape[0], X_train.shape[1], 1
    )

    # LSTM Model
    model = keras.Sequential([
        keras.layers.LSTM(64, return_sequences=True,
                          input_shape=(X_train.shape[1], 1)),
        keras.layers.LSTM(64),
        keras.layers.Dense(128, activation="relu"),
        keras.layers.Dropout(0.5),
        keras.layers.Dense(1)
    ])

    model.compile(
        optimizer="adam",
        loss="mae"
    )

    model.fit(X_train, y_train, epochs=20, batch_size=32, verbose=0)

    # Testing
    test_data = scaled_data[train_len - 60:]
    X_test = []

    for i in range(60, len(test_data)):
        X_test.append(test_data[i-60:i, 0])

    X_test = np.array(X_test)
    X_test = X_test.reshape(
        X_test.shape[0], X_test.shape[1], 1
    )

    predictions = model.predict(X_test, verbose=0)
    predictions = scaler.inverse_transform(predictions)

    actual = close_prices[train_len:]
    r2 = r2_score(actual, predictions)

    return {
        "symbol": symbol,
        "current_price": float(data["Close"].iloc[-1]),
        "predicted_price": float(predictions[-1][0]),
        "accuracy": round(r2 * 100, 2),
        "close_prices": data["Close"]
    }
