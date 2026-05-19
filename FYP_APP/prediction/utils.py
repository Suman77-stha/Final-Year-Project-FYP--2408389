import os
import glob
import logging
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_percentage_error, accuracy_score

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HybridEnsemble:
    def __init__(self, xgb_model, lr_model, xgb_weight=0.7):
        self.xgb_model = xgb_model
        self.lr_model = lr_model
        self.xgb_weight = xgb_weight
        
    def predict(self, X):
        return self.xgb_weight * self.xgb_model.predict(X) + (1 - self.xgb_weight) * self.lr_model.predict(X)

def download_data(symbol, period="10y"):
    logging.info(f"Downloading {symbol} and Market Indices...")
    df = yf.download(symbol, period=period, progress=False)
    gspc = yf.download("^GSPC", period=period, progress=False)
    ixic = yf.download("^IXIC", period=period, progress=False)
    vix = yf.download("^VIX", period=period, progress=False)
    
    for x in [df, gspc, ixic, vix]:
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.droplevel(1)
            
    df['SP500_Ret'] = gspc['Close'].pct_change()
    df['NASDAQ_Ret'] = ixic['Close'].pct_change()
    df['VIX_Close'] = vix['Close']
    return df.dropna()

def calculate_indicators(df):
    data = df.copy()
    close = data['Close']
    
    # Base indicators
    data['RSI'] = RSIIndicator(close=close, window=14).rsi()
    macd = MACD(close=close)
    data['MACD'] = macd.macd()
    data['SMA'] = SMAIndicator(close=close, window=20).sma_indicator()
    data['EMA'] = EMAIndicator(close=close, window=20).ema_indicator()
    
    # Returns
    data['return'] = close.pct_change()
    data['log_return'] = np.log(close / close.shift(1))
    
    # Advanced Lags
    lags = [1, 2, 3, 5, 7, 14, 30]
    for lag in lags:
        data[f'lag_{lag}'] = close.shift(lag)
        data[f'return_lag_{lag}'] = data['return'].shift(lag)
        
    # Rolling Stats
    for w in [5, 10, 20]:
        data[f'rolling_mean_{w}'] = close.rolling(window=w).mean()
        data[f'rolling_std_{w}'] = close.rolling(window=w).std()
        
    # Spread & Price Action
    data['high_low_spread'] = data['High'] - data['Low']
    data['open_close_spread'] = data['Open'] - data['Close']
    data['price_change'] = close.diff()
    data['volume_change'] = data['Volume'].pct_change()
    data['momentum'] = close - data['lag_5']
    
    # Z-scores
    data['close_zscore'] = (close - data['rolling_mean_20']) / data['rolling_std_20']
    
    # Trend strength
    data['Volatility'] = close.rolling(window=20).std()
    data['trend_strength'] = abs(close - data['SMA']) / data['Volatility']
    
    # Drop rows with NA created by indicators
    return data

def feature_selection(X, y, feature_names):
    import xgboost as xgb
    df_X = pd.DataFrame(X, columns=feature_names)
    
    # 1. Correlation filtering
    corr_matrix = df_X.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
    to_drop = [column for column in upper.columns if any(upper[column] > 0.95)]
    df_X = df_X.drop(columns=to_drop)
    
    # 2. Importance based selection
    model = xgb.XGBRegressor(random_state=42, n_jobs=-1)
    model.fit(df_X.values, y)
    importances = model.feature_importances_
    
    # Keep top 20
    indices = np.argsort(importances)[::-1][:20]
    selected_features = df_X.columns[indices].tolist()
    
    return df_X[selected_features].values, selected_features

def evaluate_predictions(y_true, y_pred, y_prev):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    mape = mean_absolute_percentage_error(y_true, y_pred)
    
    actual_dir = np.sign(y_true - y_prev)
    pred_dir = np.sign(y_pred - y_prev)
    actual_dir[actual_dir == 0] = 1
    pred_dir[pred_dir == 0] = 1
    dir_acc = accuracy_score(actual_dir, pred_dir)
    
    return {
        'mape': mape * 100,
        'rmse': rmse,
        'r2': r2,
        'direction_accuracy': dir_acc
    }

def plot_forecast(symbol, dates_hist, prices_hist, dates_fut, prices_fut, actual_test_dates=None, actual_test_prices=None, pred_test_prices=None):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    plots_dir = os.path.join(base_dir, 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    # 1. Validation Plot
    if actual_test_dates is not None:
        plt.figure(figsize=(12, 6))
        plt.plot(actual_test_dates[-50:], actual_test_prices[-50:], label='Actual', marker='o')
        plt.plot(actual_test_dates[-50:], pred_test_prices[-50:], label='Predicted', marker='x')
        plt.title(f'{symbol} - Validation Set Evaluation (Last 50 days)')
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, f'{symbol}_validation_plot.png'))
        plt.close()
        
    # 2. Future Forecast Plot
    plt.figure(figsize=(12, 6))
    plt.plot(dates_hist[-60:], prices_hist.iloc[-60:], label='Historical Close', color='blue', marker='.')
    
    # Connect last historical to first future for visual continuity
    conn_dates = [dates_hist[-1]] + list(dates_fut)
    conn_prices = [prices_hist.iloc[-1]] + list(prices_fut)
    
    plt.plot(conn_dates, conn_prices, label='Forecasted Future', color='orange', linestyle='--', marker='o')
    plt.title(f'{symbol} - {len(dates_fut)}-Day Future Forecast')
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, f'{symbol}_prediction_plot.png'))
    plt.close()
