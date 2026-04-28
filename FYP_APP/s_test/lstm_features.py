import pandas as pd
import numpy as np
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from sklearn.preprocessing import MinMaxScaler

def run_lstm(symbol="AAPL"):
    df = pd.read_csv(f"data/processed/{symbol}_stock_cleaned.csv")

    data = df[['Close']].values

    scaler = MinMaxScaler()
    scaled = scaler.fit_transform(data)

    X, y = [], []

    # sequence creation (IMPORTANT)
    for i in range(10, len(scaled)):
        X.append(scaled[i-10:i])
        y.append(scaled[i])

    X, y = np.array(X), np.array(y)

    model = Sequential([
        LSTM(50, input_shape=(X.shape[1], 1)),
        Dense(1)
    ])

    model.compile(optimizer='adam', loss='mse')
    model.fit(X, y, epochs=5, batch_size=16)

    preds = model.predict(X)

    df = df.iloc[10:].copy()
    df['lstm_feature'] = preds

    df.to_csv(f"data/processed/{symbol}_lstm_features.csv", index=False)

    print("LSTM features ready ✅")

if __name__ == "__main__":
    run_lstm()