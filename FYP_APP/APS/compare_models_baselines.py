import warnings
import numpy as np
import pandas as pd
import yfinance as yf
import xgboost as xgb

from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, median_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import MinMaxScaler
from statsmodels.tsa.arima.model import ARIMA
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.models import Sequential

warnings.filterwarnings("ignore")

RECENT_DAYS = 30
PREDICT_DAYS = 7
TEST_WINDOWS = 25


def load_stock_data(symbol="AAPL", start="2023-01-01"):
    data = yf.download(symbol, start=start, progress=False)
    if data.empty:
        raise ValueError(f"No data for {symbol}")
    return np.asarray(data["Close"].values, dtype=float).reshape(-1)


def create_features(prices, seq_len=RECENT_DAYS, horizon=PREDICT_DAYS):
    X, y = [], []
    for i in range(len(prices) - seq_len - horizon + 1):
        X.append(prices[i : i + seq_len])
        y.append(prices[i + seq_len : i + seq_len + horizon])
    return np.asarray(X), np.asarray(y)


def _smape(y_true, y_pred):
    num = np.abs(y_pred - y_true)
    den = np.abs(y_true) + np.abs(y_pred) + 1e-8
    return float(np.mean(200.0 * num / den))


def _metrics(y_true, y_pred):
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(np.sqrt(mse))
    mape = float(np.mean(np.abs((y_true - y_pred) / np.clip(np.abs(y_true), 1e-8, None))) * 100)
    return {
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "MSE": mse,
        "RMSE": rmse,
        "R2": float(r2_score(y_true, y_pred)),
        "MAPE_%": mape,
        "sMAPE_%": _smape(y_true, y_pred),
        "MedianAE": float(median_absolute_error(y_true, y_pred)),
    }


def naive_predict_batch(X_test):
    return np.repeat(X_test[:, -1:], PREDICT_DAYS, axis=1)


def linear_regression_predict_batch(X_train, y_train, X_test):
    model = LinearRegression()
    model.fit(X_train, y_train)
    return model.predict(X_test)


def xgboost_predict_batch(X_train, y_train, X_test):
    # Keep XGBoost configuration aligned with lstm_model.py usage.
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
    return model.predict(X_test)


def arima_predict_from_sample_indices(prices, sample_indices, order=(5, 1, 0)):
    preds = []
    for idx in sample_indices:
        history_end = idx + RECENT_DAYS
        history = prices[:history_end]
        model = ARIMA(history, order=order)
        fit = model.fit()
        preds.append(np.asarray(fit.forecast(steps=PREDICT_DAYS), dtype=float))
    return np.asarray(preds)


def arima_predict_batch(prices, test_count=TEST_WINDOWS, order=(5, 1, 0)):
    preds = []
    total = len(prices) - RECENT_DAYS - PREDICT_DAYS + 1
    start_test_idx = max(0, total - test_count)

    for i in range(start_test_idx, total):
        history = prices[: i + RECENT_DAYS]
        model = ARIMA(history, order=order)
        fit = model.fit()
        preds.append(np.asarray(fit.forecast(steps=PREDICT_DAYS), dtype=float))

    return np.asarray(preds)


def _build_lstm(seq_len=RECENT_DAYS):
    model = Sequential([LSTM(32, input_shape=(seq_len, 1)), Dense(PREDICT_DAYS)])
    model.compile(optimizer="adam", loss="mse")
    return model


def lstm_predict_batch(X_train, y_train, X_test, epochs=12, batch_size=16):
    scaler = MinMaxScaler()
    X_train_s = scaler.fit_transform(X_train.reshape(-1, 1)).reshape(X_train.shape[0], X_train.shape[1], 1)
    X_test_s = scaler.transform(X_test.reshape(-1, 1)).reshape(X_test.shape[0], X_test.shape[1], 1)
    y_train_s = scaler.transform(y_train.reshape(-1, 1)).reshape(y_train.shape)

    model = _build_lstm(RECENT_DAYS)
    model.fit(X_train_s, y_train_s, epochs=epochs, batch_size=batch_size, verbose=0)

    pred_s = model.predict(X_test_s, verbose=0)
    pred = scaler.inverse_transform(pred_s.reshape(-1, 1)).reshape(pred_s.shape)
    return pred


def _cv_scores(prices, model_name="XGBoost", n_splits=3):
    X, y = create_features(prices)
    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_scores = []

    for train_idx, test_idx in tscv.split(X):
        X_train, y_train = X[train_idx], y[train_idx]
        X_test, y_test = X[test_idx], y[test_idx]

        if model_name == "Naive_Baseline":
            y_pred = naive_predict_batch(X_test)
        elif model_name == "Linear_Regression":
            y_pred = linear_regression_predict_batch(X_train, y_train, X_test)
        elif model_name == "XGBoost":
            y_pred = xgboost_predict_batch(X_train, y_train, X_test)
        elif model_name == "LSTM":
            y_pred = lstm_predict_batch(X_train, y_train, X_test, epochs=8)
        elif model_name == "ARIMA_Baseline":
            y_pred = arima_predict_from_sample_indices(prices, test_idx)
        else:
            continue

        fold_scores.append(_metrics(y_test, y_pred))

    if not fold_scores:
        return {}

    df = pd.DataFrame(fold_scores)
    return {f"CV_{c}_mean": float(df[c].mean()) for c in df.columns} | {
        f"CV_{c}_std": float(df[c].std(ddof=0)) for c in df.columns
    }


def compare_models(symbol="AAPL"):
    prices = load_stock_data(symbol)
    X, y = create_features(prices)

    if len(X) < TEST_WINDOWS + 5:
        raise ValueError("Not enough data to evaluate all models.")

    split = len(X) - TEST_WINDOWS
    X_train, y_train = X[:split], y[:split]
    X_test, y_test = X[split:], y[split:]

    preds = {
        "Naive_Baseline": naive_predict_batch(X_test),
        "Linear_Regression": linear_regression_predict_batch(X_train, y_train, X_test),
        "XGBoost": xgboost_predict_batch(X_train, y_train, X_test),
        "ARIMA_Baseline": arima_predict_batch(prices, test_count=len(X_test)),
        "LSTM": lstm_predict_batch(X_train, y_train, X_test),
    }

    min_len = min(len(y_test), *(len(v) for v in preds.values()))
    y_eval = y_test[-min_len:]

    results = {}
    for name, pred in preds.items():
        p = pred[-min_len:]
        model_metrics = _metrics(y_eval, p)
        model_metrics.update(_cv_scores(prices, model_name=name, n_splits=3))
        results[name] = model_metrics

    ranking = sorted(results.items(), key=lambda x: x[1]["RMSE"])
    return {
        "symbol": symbol,
        "recent_days": RECENT_DAYS,
        "predict_days": PREDICT_DAYS,
        "test_windows": min_len,
        "results": results,
        "ranking_by_rmse": [name for name, _ in ranking],
        "best_model": ranking[0][0],
    }


if __name__ == "__main__":
    output = compare_models("AAPL")
    print(f"Model comparison for {output['symbol']}:")
    print("=" * 95)
    print("Models: Naive_Baseline | Linear_Regression | ARIMA_Baseline | LSTM | XGBoost")
    print("=" * 95)
    for name, m in output["results"].items():
        print(
            f"{name}: MAE={m['MAE']:.4f}, MSE={m['MSE']:.4f}, RMSE={m['RMSE']:.4f}, "
            f"R2={m['R2']:.4f}, MAPE={m['MAPE_%']:.2f}%, sMAPE={m['sMAPE_%']:.2f}%"
        )
        print(
            f"  CV (TimeSeriesSplit): "
            f"MAE={m['CV_MAE_mean']:.4f}+/-{m['CV_MAE_std']:.4f}, "
            f"RMSE={m['CV_RMSE_mean']:.4f}+/-{m['CV_RMSE_std']:.4f}, "
            f"R2={m['CV_R2_mean']:.4f}+/-{m['CV_R2_std']:.4f}, "
            f"MAPE={m['CV_MAPE_%_mean']:.2f}%+/-{m['CV_MAPE_%_std']:.2f}%"
        )
        print("-" * 95)
    print("Best ->", output["best_model"])
