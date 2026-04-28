import pandas as pd
import xgboost as xgb

def train(symbol="AAPL"):
    df = pd.read_csv(f"data/processed/{symbol}_final_dataset.csv")

    features = [
        'return', 'ma7', 'volatility',
        'sentiment', 'lstm_feature'
    ]

    X = df[features]
    y = df['target']

    split = int(len(df) * 0.8)

    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = xgb.XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5
    )

    model.fit(X_train, y_train)

    model.save_model(f"data/processed/{symbol}_xgb_model.json")

    print("XGBoost trained ✅")

if __name__ == "__main__":
    train()