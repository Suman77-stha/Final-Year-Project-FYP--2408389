import os
import json
import joblib
import logging
import warnings
import optuna
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error

import xgboost as xgb
from statsmodels.tsa.arima.model import ARIMA
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping
import tensorflow as tf

from config import TICKER, get_model_path, get_result_path, get_plot_path
from config import TICKER, get_model_path, get_result_path, get_plot_path
from utils import (cleanup_files, download_data, calculate_indicators, feature_selection,
                   calculate_metrics, failure_analysis, plot_results, HybridEnsemble)

warnings.filterwarnings('ignore')
optuna.logging.set_verbosity(optuna.logging.WARNING)

class NaivePredictor:
    def fit(self, X, y=None): pass
    def predict(self, X): return np.zeros(X.shape[0])



def create_lstm_dataset(X, y, lookback=30):
    X_lstm, y_lstm = [], []
    for i in range(len(X) - lookback):
        X_lstm.append(X[i:(i + lookback)])
        y_lstm.append(y[i + lookback])
    return np.array(X_lstm), np.array(y_lstm)

def train_lstm(X_train, y_train, X_val, y_val, lookback=30):
    logging.info("Training LSTM...")
    X_train_lstm, y_train_lstm = create_lstm_dataset(X_train, y_train, lookback)
    X_val_lstm, y_val_lstm = create_lstm_dataset(X_val, y_val, lookback)
    
    if len(X_train_lstm) == 0 or len(X_val_lstm) == 0:
        return None # Not enough data for LSTM Window
        
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=(X_train_lstm.shape[1], X_train_lstm.shape[2])),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(1)
    ])
    
    model.compile(optimizer='adam', loss='mse')
    early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
    model.fit(X_train_lstm, y_train_lstm, validation_data=(X_val_lstm, y_val_lstm),
              epochs=50, batch_size=32, callbacks=[early_stop], verbose=0)
    
    return model

def main():
    cleanup_files()
    
    df = download_data()
    data = calculate_indicators(df)
    
    logging.info("Preprocessing data...")
    # Predict next day return
    data['Target_Return'] = data['Close'].pct_change().shift(-1)
    data = data.dropna()
    
    exclude_cols = ['Target_Return']
    feature_names = [c for c in data.columns if c not in exclude_cols]
    
    X = data[feature_names].values
    y = data['Target_Return'].values
    dates = data.index
    
    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Feature Selection
    X_selected, selected_features = feature_selection(X_scaled, y, feature_names)
    logging.info(f"Selected {len(selected_features)} features.")
    
    tscv = TimeSeriesSplit(n_splits=5)
    
    # XGBoost Optuna Tuning
    logging.info("Running Optuna Optimization for XGBoost...")
    def objective(trial):
        param = {
            'max_depth': trial.suggest_int('max_depth', 2, 8),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
            'n_estimators': trial.suggest_int('n_estimators', 50, 300),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_float('gamma', 1e-8, 1e-3, log=True),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 1e-2, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 1e-2, log=True),
            'objective': 'reg:squarederror',
            'random_state': 42
        }
        cv_scores = []
        for tr_idx, te_idx in tscv.split(X_selected):
            X_tr, X_te = X_selected[tr_idx], X_selected[te_idx]
            y_tr, y_te = y[tr_idx], y[te_idx]
            model = xgb.XGBRegressor(**param, n_jobs=-1)
            model.fit(X_tr, y_tr)
            preds = model.predict(X_te)
            cv_scores.append(mean_squared_error(y_te, preds))
        return np.mean(cv_scores)

    study = optuna.create_study(direction='minimize')
    study.optimize(objective, n_trials=15)
    
    best_xgb = xgb.XGBRegressor(**study.best_params, random_state=42, n_jobs=-1)
    lr_model = LinearRegression()
    
    # Final fold evaluation
    train_idx, test_idx = list(tscv.split(X_selected))[-1]
    X_train, X_test = X_selected[train_idx], X_selected[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]
    
    best_xgb.fit(X_train, y_train)
    lr_model.fit(X_train, y_train)
    
    # LSTM Training
    val_split = int(len(X_train) * 0.8)
    lstm_model = train_lstm(X_train[:val_split], y_train[:val_split], X_train[val_split:], y_train[val_split:])
    
    # ARIMA Baseline
    logging.info("Training ARIMA...")
    try:
        arima_model = ARIMA(y_train, order=(5,1,0)).fit()
        arima_preds_ret = arima_model.forecast(steps=len(y_test))
    except:
        arima_preds_ret = np.zeros(len(y_test))
    
    # Ensemble Weight Optimization
    xgb_val = xgb.XGBRegressor(**study.best_params, random_state=42, n_jobs=-1)
    xgb_val.fit(X_train[:val_split], y_train[:val_split])
    lr_val = LinearRegression()
    lr_val.fit(X_train[:val_split], y_train[:val_split])
    
    ensemble = HybridEnsemble(xgb_val, lr_val)
    ensemble.fit_weights(X_train[val_split:], y_train[val_split:])
    
    final_ensemble = HybridEnsemble(best_xgb, lr_model)
    final_ensemble.xgb_weight = ensemble.xgb_weight
    
    models = {
        'Naive': NaivePredictor(),
        'LinearRegression': lr_model,
        'XGBoost': best_xgb,
        'XGBoost_Linear_Ensemble': final_ensemble
    }
    
    prev_prices_test = data['Close'].values[test_idx]
    actual_prices_test = prev_prices_test * (1 + y_test)
    dates_test = dates[test_idx]
    
    all_metrics = []
    preds_dict = {'Date': dates_test, 'Actual': actual_prices_test}
    
    # Predict standard models
    for name, model in models.items():
        logging.info(f"Evaluating {name}...")
        pred_returns = model.predict(X_test)
        pred_prices = prev_prices_test * (1 + pred_returns)
        
        preds_dict[f'{name}_Predicted'] = pred_prices
        metrics = calculate_metrics(actual_prices_test, pred_prices, prev_prices_test)
        metrics['Model'] = name
        all_metrics.append(metrics)
        plot_results(actual_prices_test, pred_prices, dates_test, name)
        
    # Add ARIMA
    arima_pred_prices = prev_prices_test * (1 + arima_preds_ret)
    preds_dict['ARIMA_Predicted'] = arima_pred_prices
    arima_metrics = calculate_metrics(actual_prices_test, arima_pred_prices, prev_prices_test)
    arima_metrics['Model'] = 'ARIMA'
    all_metrics.append(arima_metrics)
    plot_results(actual_prices_test, arima_pred_prices, dates_test, 'ARIMA')
    
    # Add LSTM
    if lstm_model:
        # Generate predictions maintaining alignment
        lookback = 30
        X_test_lstm, _ = create_lstm_dataset(np.vstack((X_train[-lookback:], X_test)), np.zeros(len(X_test)+lookback), lookback)
        lstm_preds_ret = lstm_model.predict(X_test_lstm, verbose=0).flatten()
        lstm_pred_prices = prev_prices_test * (1 + lstm_preds_ret)
        preds_dict['LSTM_Predicted'] = lstm_pred_prices
        lstm_metrics = calculate_metrics(actual_prices_test, lstm_pred_prices, prev_prices_test)
        lstm_metrics['Model'] = 'LSTM'
        all_metrics.append(lstm_metrics)
        plot_results(actual_prices_test, lstm_pred_prices, dates_test, 'LSTM')

    metrics_df = pd.DataFrame(all_metrics).set_index('Model')
    metrics_df.to_csv(get_result_path('metrics.csv'))
    
    pd.DataFrame(preds_dict).to_csv(get_result_path('predictions.csv'), index=False)
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x=metrics_df.index, y=metrics_df['RMSE'], palette='viridis')
    plt.title(f'{TICKER} - Model Ranking by RMSE')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(get_plot_path('model_ranking.png'))
    plt.close()
    
    # Feature Importance Plot
    plt.figure(figsize=(10, 6))
    pd.Series(best_xgb.feature_importances_, index=selected_features).sort_values(ascending=True).plot(kind='barh')
    plt.title(f'{TICKER} - XGBoost Feature Importance')
    plt.tight_layout()
    plt.savefig(get_plot_path('feature_importance.png'), bbox_inches='tight')
    plt.close()
    
    # Correlation Heatmap
    plt.figure(figsize=(12, 10))
    sns.heatmap(pd.DataFrame(X_selected, columns=selected_features).corr(), cmap='coolwarm')
    plt.title(f'{TICKER} - Feature Correlation Heatmap')
    plt.tight_layout()
    plt.savefig(get_plot_path('correlation_heatmap.png'))
    plt.close()
    
    print("\n" + "="*80)
    print("FINAL MODEL COMPARISON RESULTS")
    print("="*80)
    print(metrics_df.round(4).to_string())
    print("="*80)
    
    failure_analysis()
    
    # Save assets
    joblib.dump(best_xgb, get_model_path('xgboost'))
    joblib.dump(lr_model, get_model_path('linear'))
    joblib.dump(final_ensemble, get_model_path('ensemble'))
    if lstm_model:
        lstm_model.save(get_model_path('lstm').replace('.pkl', '.h5'))
    joblib.dump(scaler, get_model_path('scaler'))
    joblib.dump(feature_names, get_model_path('all_features'))
    joblib.dump(selected_features, get_model_path('selected_features'))
    with open(get_model_path('ensemble_weights').replace('.pkl', '.json'), 'w') as f:
        json.dump({'xgb_weight': final_ensemble.xgb_weight, 'lr_weight': 1 - final_ensemble.xgb_weight}, f)

if __name__ == "__main__":
    main()
