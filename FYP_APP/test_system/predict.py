import os
import json
import joblib
import yfinance as yf
import pandas as pd
import numpy as np
import logging

from config import TICKER, get_model_path
from utils import calculate_indicators, HybridEnsemble

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info(f"Starting Prediction Pipeline for {TICKER}...")
    
    xgb_path = get_model_path('xgboost')
    if not os.path.exists(xgb_path):
        logging.error(f"Models for {TICKER} not found. Please run train_models.py first.")
        return
        
    ensemble = joblib.load(get_model_path('ensemble'))
    scaler = joblib.load(get_model_path('scaler'))
    all_features = joblib.load(get_model_path('all_features'))
    selected_features = joblib.load(get_model_path('selected_features'))
    
    logging.info("Downloading latest data to compute lags...")
    df = yf.download(TICKER, period="1y", progress=False)
    gspc = yf.download("^GSPC", period="1y", progress=False)
    ixic = yf.download("^IXIC", period="1y", progress=False)
    vix = yf.download("^VIX", period="1y", progress=False)
    
    for x in [df, gspc, ixic, vix]:
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.droplevel(1)
            
    df['SP500_Ret'] = gspc['Close'].pct_change()
    df['NASDAQ_Ret'] = ixic['Close'].pct_change()
    df['VIX_Close'] = vix['Close']
    
    data = calculate_indicators(df.dropna())
    latest_data = data.iloc[-1:].copy()
    
    # The current dataframe has index aligned, no forward fill needed if latest is clean
    if latest_data.isna().sum().sum() > 0:
        latest_data = latest_data.fillna(method='ffill')
        
    X_latest = latest_data[all_features].values
    X_scaled = scaler.transform(X_latest)
    
    df_scaled = pd.DataFrame(X_scaled, columns=all_features)
    X_scaled_selected = df_scaled[selected_features].values
    
    ensemble_pred_return = ensemble.predict(X_scaled_selected)[0]
    
    today_price = latest_data['Close'].values[0]
    pred_price = today_price * (1 + ensemble_pred_return)
    
    print("\n" + "="*50)
    print(f"{TICKER} - NEXT-DAY ENSEMBLE PREDICTION")
    print("="*50)
    print(f"Today's Close:     ${today_price:.2f}")
    print(f"Predicted Return:  {ensemble_pred_return*100:.2f}%")
    print(f"Predicted Close:   ${pred_price:.2f}")
    print(f"Using Weights:     XGBoost={ensemble.xgb_weight:.2f}, LR={(1-ensemble.xgb_weight):.2f}")
    print("="*50 + "\n")

if __name__ == "__main__":
    main()
