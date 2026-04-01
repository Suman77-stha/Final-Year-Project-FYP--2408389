# ==========================================
# ULTRA-FAST STOCK PRICE PREDICTION USING XGBOOST
# ==========================================
import os
import yfinance as yf
import numpy as np
import joblib
import json
import xgboost as xgb
import time

# CONFIG
SYMBOL = "AAPL"
RECENT_DAYS = 30
PREDICT_DAYS = 7
MODEL_FILE = f"{SYMBOL}_xgb_model.save"
CACHE_FILE = f"{SYMBOL}_xgb_cache.json"

# ==========================================
# LOAD STOCK DATA
# ==========================================
def load_stock_data(symbol):
    data = yf.download(symbol, start="2015-01-01", progress=False)
    if data.empty:
        raise ValueError(f"No data for {symbol}")
    # Ensure 1D numpy array
    prices = np.array(data["Close"].values, dtype=float).reshape(-1)
    return prices

# ==========================================
# CREATE FEATURES & LABELS
# ==========================================
def create_features(prices, seq_len=RECENT_DAYS):
    X, y = [], []
    for i in range(len(prices) - seq_len - PREDICT_DAYS + 1):
        X.append(prices[i:i+seq_len])
        y.append(prices[i+seq_len:i+seq_len+PREDICT_DAYS])
    return np.array(X), np.array(y)

# ==========================================
# TRAIN XGBOOST MODEL
# ==========================================
def train_model(prices):
    X, y = create_features(prices)
    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=5,
        objective='reg:squarederror',
        tree_method='hist',  # fast CPU training
        n_jobs=-1
    )
    model.fit(X, y)
    joblib.dump(model, MODEL_FILE)
    print("XGBoost model trained and saved.")
    return model

# ==========================================
# FAST PREDICTION WITH CACHE
# ==========================================
def predict(symbol="AAPL", future_days=7):
    prices = load_stock_data(symbol)
    last_close = float(prices[-1])

    # Load or train model
    if os.path.exists(MODEL_FILE):
        model = joblib.load(MODEL_FILE)
    else:
        model = train_model(prices)

    recent_prices = prices[-RECENT_DAYS:].tolist()

    # 🔥 RECURSIVE PREDICTION (KEY FIX)
    predictions = []
    temp_input = recent_prices.copy()

    for _ in range(future_days):
        x_input = np.array(temp_input[-RECENT_DAYS:]).reshape(1, -1)
        pred = model.predict(x_input).flatten()[0]

        predictions.append(float(pred))
        temp_input.append(pred)

    return {
        "symbol": symbol,
        "current_price": last_close,
        "close_prices": recent_prices,
        "future_days": predictions,
        "predicted_price": predictions[0]
    }
# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    start_time = time.time()
    
    result = predict()
    
    end_time = time.time()
    print(f"\nPrediction done in {end_time - start_time:.4f} seconds\n")
    
    print(f"Symbol: {result['symbol']}")
    print(f"Current Price: ${result['current_price']:.2f}\n")
    
    print("Recent Prices:")
    for i, p in enumerate(result["close_prices"], 1):
        print(f"Day {i}: ${p:.2f}")
    
    print("\nPredicted Next 7 Days:")
    for i, p in enumerate(result["future_days"], 1):
        print(f"Day {i}: ${p:.2f}")