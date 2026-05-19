# FYP Advanced Stock Prediction System

This is a production-level, academic-grade stock price prediction system utilizing advanced machine learning (XGBoost), deep learning (LSTM), statistical models (ARIMA), and hybrid ensembles. 

## Project Architecture
- `config.py`: Centralized configuration variables (`TICKER`, `PERIOD`, etc.).
- `utils.py`: Modular helper functions containing data fetching, heavy feature engineering, metrics calculation, and evaluation plotting.
- `train_models.py`: The orchestrator that executes walk-forward TimeSeries splits, tuning, ensemble weight optimization, and model serialization.
- `predict.py`: Standalone inference script that dynamically fetches the latest live data and predicts the next day's price.

## Features Engineered
Over 30 technical indicators and statistical variables are computed, including:
- Momentum & Trend: RSI, MACD, SMA, EMA.
- Spreads: High-Low, Open-Close.
- Lags & Rolling Stats: Extensive memory via `lag_1` to `lag_30`, `rolling_mean`, and `z-scores`.
- Market Indices: Factoring in S&P500 (`^GSPC`), NASDAQ (`^IXIC`), and the Volatility Index (`^VIX`).
*A rigorous correlation filter and XGBoost-based feature selection step drop noisy data before training.*

## The Hybrid Ensemble Model
We introduce an `XGBoost_Linear_Ensemble` model. 
Why? Because time-series data is notoriously noisy. While XGBoost is exceptionally powerful at mapping complex non-linear signals, it is prone to overreacting. Linear Regression naturally maps the underlying market drift without overfitting. By combining both via automated weight optimization, we achieve significant variance reduction, improving overall robustness against market shocks.

## How to Run

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Train All Models**:
```bash
python train_models.py
```
This automatically deletes old models/plots, downloads 10 years of data, optimizes the models, and generates new assets dynamically named after the target stock (e.g., `AAPL_metrics.csv`).

3. **Predict Tomorrow's Price**:
```bash
python predict.py
```
