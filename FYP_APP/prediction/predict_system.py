import os
import time
import json
import joblib
import logging
import datetime
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.metrics import mean_squared_error

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import (
    download_data, calculate_indicators, feature_selection, 
    evaluate_predictions, plot_forecast, HybridEnsemble
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def train_and_save_models(symbol, df_raw):
    logging.info(f"Training models for {symbol} as they do not exist...")
    
    data = calculate_indicators(df_raw)
    data['Target_Return'] = data['Close'].pct_change().shift(-1)
    
    # Drop rows with NaN or Inf in features or target
    data = data.replace([np.inf, -np.inf], np.nan)
    data = data.dropna()
    
    feature_names = [c for c in data.columns if c not in ['Target_Return']]
    
    X = data[feature_names].values
    y = data['Target_Return'].values
    
    # 80/20 chronological split
    split_idx = int(len(X) * 0.8)
    X_train, y_train = X[:split_idx], y[:split_idx]
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    # Feature Selection
    X_train_selected, selected_features = feature_selection(X_train_scaled, y_train, feature_names)
    
    # Cross-Validation & Hyperparameter Tuning for better model performance
    tscv = TimeSeriesSplit(n_splits=5)
    
    param_grid = {
        'max_depth': [3, 4, 5],
        'learning_rate': [0.01, 0.05, 0.1],
        'n_estimators': [100, 150, 200]
    }
    
    logging.info("Performing Time Series Cross-Validation to find best XGBoost parameters...")
    base_xgb = xgb.XGBRegressor(objective='reg:squarederror', random_state=42, n_jobs=-1)
    
    grid_search = GridSearchCV(
        estimator=base_xgb,
        param_grid=param_grid,
        cv=tscv,
        scoring='neg_root_mean_squared_error',
        n_jobs=-1
    )
    
    grid_search.fit(X_train_selected, y_train)
    
    logging.info(f"Best CV RMSE: {-grid_search.best_score_:.4f}")
    logging.info(f"Best Parameters: {grid_search.best_params_}")
    
    # Use the best model found by CV
    xgb_model = grid_search.best_estimator_
    
    lr_model = LinearRegression()
    lr_model.fit(X_train_selected, y_train)
    
    ensemble = HybridEnsemble(xgb_model, lr_model, xgb_weight=0.7)
    
    # Save Assets
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, 'models'), exist_ok=True)
    
    joblib.dump(xgb_model, os.path.join(base_dir, f'models/{symbol}_xgb_model.pkl'))
    joblib.dump(lr_model, os.path.join(base_dir, f'models/{symbol}_linear_model.pkl'))
    joblib.dump(ensemble, os.path.join(base_dir, f'models/{symbol}_ensemble_model.pkl'))
    joblib.dump(scaler, os.path.join(base_dir, f'models/{symbol}_scaler.pkl'))
    joblib.dump({'all_features': feature_names, 'selected_features': selected_features}, os.path.join(base_dir, f'models/{symbol}_features.pkl'))
    
    logging.info(f"Successfully trained and saved models for {symbol}.")
    return True

def get_latest_features(df, feature_names, selected_features, scaler):
    # Slice the dataframe to the last 200 rows for indicator calculation speedup
    df_slice = df.iloc[-200:]
    data = calculate_indicators(df_slice)
    
    # Forward fill then backward fill the entire slice to resolve NaNs cleanly
    data_filled = data.ffill().bfill()
    
    # Extract the last row containing features for the current "today"
    latest_row = data_filled.iloc[-1:]
        
    X_all = latest_row[feature_names].values
    X_scaled = scaler.transform(X_all)
    
    df_scaled = pd.DataFrame(X_scaled, columns=feature_names)
    X_selected = df_scaled[selected_features].values
    
    return X_selected


def _get_next_market_date(last_date, symbol):
    next_date = last_date + pd.Timedelta(days=1)
    if "-" not in symbol:
        while next_date.weekday() >= 5:
            next_date += pd.Timedelta(days=1)
    return next_date

def predict(symbol="ETH-USD", future_days=7):
    start_time = time.time()
    logging.info(f"Starting Prediction Pipeline for {symbol}...")
    
    df_raw = download_data(symbol, period="10y")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, f'models/{symbol}_ensemble_model.pkl')
    if not os.path.exists(model_path):
        train_and_save_models(symbol, df_raw)
        
    # Load Models
    ensemble = joblib.load(model_path)
    scaler = joblib.load(os.path.join(base_dir, f'models/{symbol}_scaler.pkl'))
    features_dict = joblib.load(os.path.join(base_dir, f'models/{symbol}_features.pkl'))
    all_features = features_dict['all_features']
    selected_features = features_dict['selected_features']
    
    # Validate on recent test window (last 60 days of historical data)
    data = calculate_indicators(df_raw)
    data['Target_Return'] = data['Close'].pct_change().shift(-1)
    test_data = data.dropna().iloc[-60:].copy()
    
    X_test_all = test_data[all_features].values
    X_test_scaled = scaler.transform(X_test_all)
    df_test_scaled = pd.DataFrame(X_test_scaled, columns=all_features)
    X_test_selected = df_test_scaled[selected_features].values
    
    pred_test_returns = ensemble.predict(X_test_selected)
    prev_prices_test = test_data['Close'].values
    actual_returns_test = test_data['Target_Return'].values
    
    y_true_prices = prev_prices_test * (1 + actual_returns_test)
    y_pred_prices = prev_prices_test * (1 + pred_test_returns)
    test_dates = test_data.index
    
    metrics = evaluate_predictions(y_true_prices, y_pred_prices, prev_prices_test)
    
    # Recursive Future Forecasting
    logging.info(f"Generating recursive forecast for {future_days} days...")
    working_df = df_raw.copy()
    future_predictions = []
    future_dates = []
    
    last_date = working_df.index[-1]
    
    indicator_window = 200
    for i in range(future_days):
        # 1. Get features for the current end of working_df
        X_latest = get_latest_features(working_df, all_features, selected_features, scaler)
        
        # 2. Predict return for tomorrow
        pred_return = ensemble.predict(X_latest)[0]
        
        # 3. Calculate tomorrow's Close
        last_close = working_df['Close'].iloc[-1]
        next_close = last_close * (1 + pred_return)
        
        # 4. Create dummy row for tomorrow to allow recursive indicator calculation
        next_date = _get_next_market_date(last_date, symbol)
            
        future_predictions.append(next_close)
        future_dates.append(next_date)
        
        new_row = pd.DataFrame({
            'Open': [next_close],
            'High': [next_close],
            'Low': [next_close],
            'Close': [next_close],
            'Adj Close': [next_close],
            'Volume': [working_df['Volume'].iloc[-1]],
            'SP500_Ret': [working_df['SP500_Ret'].iloc[-1]],
            'NASDAQ_Ret': [working_df['NASDAQ_Ret'].iloc[-1]],
            'VIX_Close': [working_df['VIX_Close'].iloc[-1]]
        }, index=[next_date])
        
        working_df = pd.concat([working_df, new_row]).iloc[-indicator_window:]
        last_date = next_date
        
    # Generate Plots
    hist_dates = df_raw.index[-60:]
    hist_prices = df_raw['Close'].iloc[-60:]
    
    plot_forecast(
        symbol, hist_dates, hist_prices, future_dates, future_predictions,
        actual_test_dates=test_dates, actual_test_prices=y_true_prices, pred_test_prices=y_pred_prices
    )
    
    current_price = df_raw['Close'].iloc[-1]
    recent_prices = df_raw['Close'].iloc[-30:].tolist()
    
    # Save outputs
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, 'results'), exist_ok=True)
    pd.DataFrame({'Date': future_dates, 'Predicted_Price': future_predictions}).to_csv(os.path.join(base_dir, f'results/{symbol}_predictions.csv'), index=False)
    pd.DataFrame([metrics]).to_csv(os.path.join(base_dir, f'results/{symbol}_metrics.csv'), index=False)
    
    execution_time = time.time() - start_time
    
    result = {
        "symbol": symbol,
        "current_price": current_price,
        "close_prices": recent_prices,
        "future_days": future_predictions,
        "predicted_price": future_predictions[0],
        "mape": metrics['mape'],
        "rmse": metrics['rmse'],
        "r2": metrics['r2'],
        "direction_accuracy": metrics['direction_accuracy'],
        "execution_time": execution_time
    }
    
    return result

if __name__ == "__main__":
    import sys
    
    symbol = "ETH-USD"
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
        
    result = predict(symbol=symbol, future_days=7)
    
    print("\n" + "="*50)
    print(f"Prediction done in {result['execution_time']:.4f} seconds\n")
    print(f"Symbol: {result['symbol']}")
    print(f"Current Price: ${result['current_price']:.2f}\n")
    
    print(f"MAPE: {result['mape']:.2f}%")
    print(f"RMSE: {result['rmse']:.4f}")
    print(f"R²: {result['r2']:.4f}")
    print(f"Directional Accuracy: {result['direction_accuracy']:.4f}\n")
    
    print("Recent Prices:")
    for i, p in enumerate(result['close_prices'], 1):
        print(f"Day {i}: ${p:.2f}")
        
    print(f"\nPredicted Next {len(result['future_days'])} Days:")
    for i, p in enumerate(result['future_days'], 1):
        print(f"Day {i}: ${p:.2f}")
    print("="*50 + "\n")
