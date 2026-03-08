# AI STOCK PRICE PREDICTION MODULE

import os
import json
import datetime
import pytz
import numpy as np
import yfinance as yf
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
from tensorflow import keras  # type: ignore

# CONFIG

BASE_MODEL_DIR = "models"
os.makedirs(BASE_MODEL_DIR, exist_ok=True)

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

TIMEZONE = pytz.timezone("Asia/Kathmandu")

# DATA LOADING

def load_stock_data(symbol):
    START = "2015-01-01"
    TODAY = datetime.datetime.now(TIMEZONE).date()

    data = yf.download(symbol, START, TODAY, progress=False)

    if data.empty:
        raise ValueError(f"No data found for symbol: {symbol}")

    data.reset_index(inplace=True)
    return data


# MODEL SAVE / LOAD HELPERS

def save_model_bundle(symbol, model, scaler):
    symbol_dir = os.path.join(BASE_MODEL_DIR, symbol)
    os.makedirs(symbol_dir, exist_ok=True)

    model.save(os.path.join(symbol_dir, "model.h5"))
    joblib.dump(scaler, os.path.join(symbol_dir, "scaler.pkl"))

    meta = {
        "symbol": symbol,
        "trained_on": datetime.date.today().isoformat()
    }

    with open(os.path.join(symbol_dir, "meta.json"), "w") as f:
        json.dump(meta, f)


def load_model_and_scaler(symbol):
    symbol_dir = os.path.join(BASE_MODEL_DIR, symbol)

    model_path = os.path.join(symbol_dir, "model.h5")
    scaler_path = os.path.join(symbol_dir, "scaler.pkl")
    meta_path = os.path.join(symbol_dir, "meta.json")

    if not all(map(os.path.exists, [model_path, scaler_path, meta_path])):
        return None, None

    with open(meta_path, "r") as f:
        meta = json.load(f)

    today = datetime.date.today().isoformat()

    #  Strict validation
    if meta.get("symbol") != symbol or meta.get("trained_on") != today:
        print(" Old or mismatched model detected.")
        return None, None

    model = keras.models.load_model(model_path, compile=False)
    model.compile(
        optimizer="adam",
        loss=keras.losses.MeanAbsoluteError()
    )

    scaler = joblib.load(scaler_path)

    print("Loaded cached model for today.")
    return model, scaler


# MODEL TRAINING

def train_model(symbol):
    print(f"Training model for {symbol}...")

    data = load_stock_data(symbol)
    close_prices = data["Close"].values.reshape(-1, 1)

    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(close_prices)

    train_len = int(len(scaled_data) * 0.95)
    train_data = scaled_data[:train_len]

    X_train, y_train = [], []

    for i in range(60, len(train_data)):
        X_train.append(train_data[i - 60:i, 0])
        y_train.append(train_data[i, 0])

    X_train = np.array(X_train).reshape(-1, 60, 1)
    y_train = np.array(y_train)

    model = keras.Sequential([
        keras.layers.LSTM(64, return_sequences=True, input_shape=(60, 1)),
        keras.layers.LSTM(64),
        keras.layers.Dense(128, activation="relu"),
        keras.layers.Dropout(0.5),
        keras.layers.Dense(1)
    ])

    model.compile(
        optimizer="adam",
        loss=keras.losses.MeanAbsoluteError()
    )

    model.fit(
        X_train,
        y_train,
        epochs=20,
        batch_size=32,
        verbose=1
    )

    save_model_bundle(symbol, model, scaler)

    return model, scaler


# MAIN PREDICTION FUNCTION

def predict_stock_price(symbol="AAPL", period=7):
    print(f"\n Predicting stock price for: {symbol}")

    model, scaler = load_model_and_scaler(symbol)

    if model is None:
        model, scaler = train_model(symbol)
    else:
        print("Using cached model.")

    data = load_stock_data(symbol)
    close_prices = data["Close"].values.reshape(-1, 1)

    scaled_data = scaler.transform(close_prices)

    train_len = int(len(scaled_data) * 0.95)
    test_data = scaled_data[train_len - 60:]

    X_test = []

    for i in range(60, len(test_data)):
        X_test.append(test_data[i - 60:i, 0])

    if X_test:
        X_test = np.array(X_test).reshape(-1, 60, 1)
        predictions = model.predict(X_test, verbose=0)
        predictions = scaler.inverse_transform(predictions)

        actual = close_prices[train_len:]
        r2 = r2_score(actual, predictions)
    else:
        predictions = np.array([[close_prices[-1][0]]])
        r2 = 0.0

    #Future prediction
    last_60 = scaled_data[-60:]
    current_input = last_60.reshape(1, 60, 1)

    future_predictions = []

    for _ in range(period):
        next_price = model.predict(current_input, verbose=0)
        future_predictions.append(next_price[0, 0])

        current_input = np.append(
            current_input[:, 1:, :],
            [[[next_price[0, 0]]]],
            axis=1
        )

    future_predictions = scaler.inverse_transform(
        np.array(future_predictions).reshape(-1, 1)
    ).flatten()

    return {
        "symbol": symbol,
        "current_price": float(close_prices[-1][0]),
        "close_prices": data["Close"],
        "predicted_price": float(predictions[-1][0]),
        "accuracy": round(r2 * 100, 2),
        "future_days": future_predictions.tolist()
    }


# ================================
# TERMINAL EXECUTION
# ================================

if __name__ == "__main__":
    result = predict_stock_price(symbol="TSLA", period=7)

    print("\n AI STOCK PRICE PREDICTION")
    print("-" * 40)
    print(f"Symbol          : {result['symbol']}")
    print(f"Current Price  : ${result['current_price']:.2f}")
    print(f"Predicted Price: ${result['predicted_price']:.2f}")
    print(f"Accuracy       : {result['accuracy']}%")

    print("\n 7-Day Forecast:")
    for i, price in enumerate(result["future_days"], start=1):
        print(f"Day {i}: ${price:.2f}")