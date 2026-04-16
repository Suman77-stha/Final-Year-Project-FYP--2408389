import numpy as np
import pandas as pd
import yfinance as yf
import joblib
import os

from sklearn.linear_model import LinearRegression

# -------------------------------
# CONFIG
# -------------------------------
os.makedirs("models_from_regression", exist_ok=True)
symbol = "TSLA"
model_path = f"models_from_regression/model_{symbol}.pkl"

# -------------------------------
# DOWNLOAD DATA (up to today)
# -------------------------------
df = yf.download(symbol, period="10y", progress=False)

df = df.dropna()

# Target = next day's close
df['Target'] = df['Close'].shift(-1)
df = df.dropna()

X = df[['Open', 'High', 'Low', 'Volume']]
y = df['Target']

# -------------------------------
# TRAIN MODEL
# -------------------------------
model = LinearRegression()
model.fit(X, y)

# -------------------------------
# SAVE MODEL
# -------------------------------
joblib.dump(model, model_path)

print(f"Model saved for {symbol} -> {model_path}")