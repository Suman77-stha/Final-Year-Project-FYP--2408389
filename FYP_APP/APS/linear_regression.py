import time
import numpy as np
import pandas as pd
import yfinance as yf
import joblib

symbol = "TSLA"
model_path = f"models_from_regression/model_{symbol}.pkl"
future_days_n = 7   # match your sample output

start_time = time.time()

# -------------------------------
# LOAD MODEL
# -------------------------------
model = joblib.load(model_path)

# -------------------------------
# DOWNLOAD DATA
# -------------------------------
df = yf.download(symbol, period="10y", progress=False)
df = df.dropna()

current_price = df['Close'].iloc[-1].item()

# last 30 days for display (like your example)
recent_prices = df['Close'].tail(30).to_numpy().ravel().tolist()

# -------------------------------
# FUTURE PREDICTION
# -------------------------------
future_predictions = []
temp_df = df.copy()

for _ in range(future_days_n):

    X_input = temp_df[['Open', 'High', 'Low', 'Volume']].iloc[-1].values.reshape(1, -1)

    next_price = model.predict(X_input)[0]
    future_predictions.append(next_price)

    # append predicted row
    new_row = temp_df.iloc[-1].copy()
    new_row['Close'] = next_price
    temp_df = pd.concat([temp_df, pd.DataFrame([new_row])], ignore_index=True)

end_time = time.time()

# -------------------------------
# PRINT FORMATTED OUTPUT
# -------------------------------
print(f"\nPrediction done in {round(end_time - start_time, 4)} seconds\n")

print(f"Symbol: {symbol}")
print(f"Current Price: ${current_price:.2f}\n")

print("Recent Prices:")
for i, price in enumerate(recent_prices[-30:], 1):
    print(f"Day {i}: ${price:.2f}")

print("\nPredicted Next 7 Days:")
for i, price in enumerate(future_predictions, 1):
    print(f"Day {i}: ${price:.2f}")