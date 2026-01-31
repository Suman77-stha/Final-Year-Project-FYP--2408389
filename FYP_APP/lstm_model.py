# FYP_APP/lstm_model.py

import os
import numpy as np
import yfinance as yf
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_percentage_error
from tensorflow.keras.models import Sequential, load_model # type: ignore
from tensorflow.keras.layers import LSTM, Dense, Dropout # type: ignore
from django.conf import settings

LOOKBACK = 60

# ============================
# PATH SETUP (PRODUCTION SAFE)
# ============================
MODEL_DIR = os.path.join(settings.BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)


# ============================
# TRAIN LSTM MODEL
# ============================
def train_lstm(symbol):
    df = yf.download(symbol, period="5y")
    if df.empty:
        raise Exception("No data found")

    prices = df[['Close']].values

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(prices)

    X, y = [], []
    for i in range(LOOKBACK, len(scaled)):
        X.append(scaled[i - LOOKBACK:i])
        y.append(scaled[i])

    X, y = np.array(X), np.array(y)

    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(LOOKBACK, 1)),
        Dropout(0.2),
        LSTM(50),
        Dense(1)
    ])

    model.compile(optimizer="adam", loss="mse")
    model.fit(X_train, y_train, epochs=20, batch_size=32)

    preds = model.predict(X_test, verbose=0)
    accuracy = 100 - mean_absolute_percentage_error(y_test, preds) * 100

    model_path = os.path.join(MODEL_DIR, f"{symbol}_lstm.h5")
    scaler_path = os.path.join(MODEL_DIR, f"{symbol}_scaler.pkl")

    # IMPORTANT FIX
    model.save(model_path, include_optimizer=False)
    joblib.dump(scaler, scaler_path)

    print(f"\n LSTM Accuracy for {symbol}: {accuracy:.2f}%\n")

    return accuracy


# ============================
# PREDICT USING TRAINED MODEL
# ============================
def predict_lstm(symbol, days=7):
    model = load_model(
        f"models/{symbol}_lstm.h5",
        compile=False  # IMPORTANT
    )
    scaler = joblib.load(f"models/{symbol}_scaler.pkl")

    df = yf.download(symbol, period="6mo")
    prices = df[["Close"]].values

    scaled = scaler.transform(prices)
    seq = scaled[-LOOKBACK:]

    predictions = []

    for _ in range(days):
        pred = model.predict(
            seq.reshape(1, LOOKBACK, 1),
            verbose=0
        )[0][0]

        predictions.append(pred)
        seq = np.append(seq[1:], [[pred]], axis=0)

    predictions = scaler.inverse_transform(
        np.array(predictions).reshape(-1, 1)
    ).flatten()

    return predictions.tolist()