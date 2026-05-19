# ==========================================
# ULTRA-FAST STOCK PRICE PREDICTION USING XGBOOST
# ==========================================
import os
import yfinance as yf
import numpy as np
import joblib
import xgboost as xgb
import time
from sklearn.metrics import mean_absolute_percentage_error

# CONFIG
SYMBOL = "AAPL"
RECENT_DAYS = 30
PREDICT_DAYS = 7
TEST_WINDOWS = 25
MODEL_FILE = f"{SYMBOL}_xgb_model.save"

# ==========================================
# LOAD STOCK DATA
# ==========================================
def load_stock_data(symbol):
    data = yf.download(symbol, start="2023-01-01", progress=False)
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

def train_model(prices, symbol):
    X, y = create_features(prices)
    model_file = f"{symbol}_xgb_model.save"
    if len(X) < TEST_WINDOWS + 5:
        raise ValueError("Not enough data to evaluate model.")

    split = len(X) - TEST_WINDOWS
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        objective="reg:squarederror",
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred_test = model.predict(X_test)
    mape = float(mean_absolute_percentage_error(y_test, y_pred_test) * 100)

    joblib.dump(model, model_file)
    print(f"Model Accuracy (MAPE %): {mape:.4f}")
    print("XGBoost model trained and saved.")
    return model, mape

# ==========================================
# FAST PREDICTION WITH CACHE
# ==========================================
def predict(symbol="ETH", future_days=7):
    prices = load_stock_data(symbol)
    last_close = float(prices[-1])
    model_file = f"{symbol}_xgb_model.save"

    # Load or train model
    if os.path.exists(model_file):
        model = joblib.load(model_file)
        X_all, y_all = create_features(prices)
        if len(X_all) < TEST_WINDOWS + 1:
            raise ValueError("Not enough data to evaluate model.")
        split = len(X_all) - TEST_WINDOWS
        X_eval, y_eval = X_all[split:], y_all[split:]
        y_pred_eval = model.predict(X_eval)
        accuracy = float(mean_absolute_percentage_error(y_eval, y_pred_eval) * 100)
    else:
        model, accuracy = train_model(prices, symbol)

    recent_prices = prices[-RECENT_DAYS:].tolist()

    # Direct multi-step prediction (same structure as training target)
    x_input = np.array(recent_prices).reshape(1, -1)
    pred_vector = model.predict(x_input).flatten().tolist()
    predictions = [float(p) for p in pred_vector[:future_days]]

    return {
        "symbol": symbol,
        "current_price": last_close,
        "close_prices": recent_prices,
        "future_days": predictions,
        "predicted_price": predictions[0],
        "accuracy": accuracy
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
    if result["accuracy"] is not None:
        print(f"Model Accuracy (MAPE %): {result['accuracy']:.4f}\n")
    
    print("Recent Prices:")
    for i, p in enumerate(result["close_prices"], 1):
        print(f"Day {i}: ${p:.2f}")
    
    print("\nPredicted Next 7 Days:")
    for i, p in enumerate(result["future_days"], 1):
        print(f"Day {i}: ${p:.2f}")
