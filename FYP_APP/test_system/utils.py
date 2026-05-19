import os
import glob
import logging
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator, EMAIndicator
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, mean_absolute_percentage_error, accuracy_score
from sklearn.linear_model import LinearRegression
import xgboost as xgb
from config import TICKER, PERIOD, get_plot_path, DIRS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HybridEnsemble:
    def __init__(self, xgb_model, lr_model):
        self.xgb_model = xgb_model
        self.lr_model = lr_model
        self.xgb_weight = 0.5
        
    def fit_weights(self, X_val, y_val):
        xgb_preds = self.xgb_model.predict(X_val)
        lr_preds = self.lr_model.predict(X_val)
        
        best_weight = 0.5
        best_rmse = float('inf')
        
        for w in [0.5, 0.6, 0.7, 0.8, 0.9]:
            combined = w * xgb_preds + (1 - w) * lr_preds
            rmse = np.sqrt(mean_squared_error(y_val, combined))
            if rmse < best_rmse:
                best_rmse = rmse
                best_weight = w
                
        self.xgb_weight = best_weight
        logging.info(f"Selected Ensemble Weights: XGBoost={self.xgb_weight}, LR={1-self.xgb_weight}")
        
    def predict(self, X):
        return self.xgb_weight * self.xgb_model.predict(X) + (1 - self.xgb_weight) * self.lr_model.predict(X)

def cleanup_files():
    logging.info("Cleaning up old files...")
    for d in DIRS.values():
        if os.path.exists(d):
            for file in glob.glob(os.path.join(d, '*.*')):
                try:
                    os.remove(file)
                except:
                    pass

def download_data():
    logging.info(f"Downloading {TICKER} and Market Indices...")
    df = yf.download(TICKER, period=PERIOD, progress=False)
    gspc = yf.download("^GSPC", period=PERIOD, progress=False)
    ixic = yf.download("^IXIC", period=PERIOD, progress=False)
    vix = yf.download("^VIX", period=PERIOD, progress=False)
    
    for x in [df, gspc, ixic, vix]:
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.droplevel(1)
            
    df['SP500_Ret'] = gspc['Close'].pct_change()
    df['NASDAQ_Ret'] = ixic['Close'].pct_change()
    df['VIX_Close'] = vix['Close']
    return df.dropna()

def calculate_indicators(df):
    logging.info("Engineering advanced features...")
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
    data['trend_strength'] = abs(close - data['SMA']) / data['Volatility'] if 'Volatility' in data.columns else 0
    data['Volatility'] = close.rolling(window=20).std()
    data['trend_strength'] = abs(close - data['SMA']) / data['Volatility']
    
    return data

def feature_selection(X, y, feature_names):
    logging.info("Filtering correlated features and selecting top features...")
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

def calculate_metrics(y_true_price, y_pred_price, y_prev_price):
    mae = mean_absolute_error(y_true_price, y_pred_price)
    rmse = np.sqrt(mean_squared_error(y_true_price, y_pred_price))
    r2 = r2_score(y_true_price, y_pred_price)
    mape = mean_absolute_percentage_error(y_true_price, y_pred_price)
    
    actual_dir = np.sign(y_true_price - y_prev_price)
    pred_dir = np.sign(y_pred_price - y_prev_price)
    actual_dir[actual_dir == 0] = 1
    pred_dir[pred_dir == 0] = 1
    dir_acc = accuracy_score(actual_dir, pred_dir)
    
    hit_ratio = sum(actual_dir == pred_dir) / len(actual_dir)
    
    returns = (y_true_price - y_prev_price) / y_prev_price
    strategy_returns = pred_dir * returns
    
    gross_profits = np.sum(strategy_returns[strategy_returns > 0])
    gross_losses = np.abs(np.sum(strategy_returns[strategy_returns < 0]))
    profit_factor = gross_profits / gross_losses if gross_losses != 0 else np.inf
    sharpe = np.sqrt(252) * np.mean(strategy_returns) / (np.std(strategy_returns) + 1e-9)
    
    return {
        'MAE': mae, 'RMSE': rmse, 'R2': r2, 'MAPE': mape, 
        'Dir_Acc': dir_acc, 'Hit_Ratio': hit_ratio, 
        'Sharpe': sharpe, 'Profit_Factor': profit_factor
    }

def failure_analysis():
    print("\n" + "="*80)
    print("FAILURE ANALYSIS & ROBUSTNESS")
    print("="*80)
    print("When do Time-Series Models Fail?")
    print("1. High Volatility / Crashes: Standard machine learning models map patterns from normal distributions. Black swan events invalidate historical distributions.")
    print("2. News Shocks: Unpredictable macroeconomic news overrides technical momentum instantly.")
    print("3. Trend Reversals: Lagging indicators (like SMA/MACD) cause models to overshoot during V-shaped market recoveries.")
    print("\nWhy is the Naive Baseline strong?")
    print("- Stock prices follow a near random-walk. 'Tomorrow's price is today's price' is mathematically difficult to beat due to high autocorrelation.")
    print("="*80 + "\n")

def plot_results(y_true, y_pred, dates, model_name):
    plt.figure(figsize=(14, 7))
    plt.plot(dates[-100:], y_true[-100:], label='Actual', color='blue')
    plt.plot(dates[-100:], y_pred[-100:], label='Predicted', color='orange')
    plt.title(f'{TICKER} - {model_name}: Actual vs Predicted (Last 100 days)')
    plt.legend()
    plt.savefig(get_plot_path(f'{model_name}_actual_vs_predicted.png'))
    plt.close()

    residuals = y_true - y_pred
    plt.figure(figsize=(10, 6))
    plt.scatter(y_pred, residuals, alpha=0.5)
    plt.axhline(0, color='red', linestyle='--')
    plt.title(f'{TICKER} - {model_name}: Residuals')
    plt.savefig(get_plot_path(f'{model_name}_residuals.png'))
    plt.close()

    plt.figure(figsize=(10, 6))
    sns.histplot(residuals, kde=True, bins=50)
    plt.title(f'{TICKER} - {model_name}: Error Distribution')
    plt.savefig(get_plot_path(f'{model_name}_error_dist.png'))
    plt.close()
