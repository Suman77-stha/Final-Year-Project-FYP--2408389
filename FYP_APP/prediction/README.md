# FYP Stock Forecasting System

A robust, production-level system capable of predicting future N-day trajectories for any cryptocurrency or stock.

## Architecture
- `predict_system.py`: The entry point. Handles dynamic loading, automatic model training on missing files, and recursive future predictions.
- `utils.py`: Modular utilities containing exact feature engineering mirrors of the test system, evaluation logic, and dynamic plot generation.

## Features
- **Dynamic Training**: Need to predict `ETH-USD`? Just run the script. It will automatically download 10 years of data, extract 40+ lagging technical indicators, train XGBoost and Linear Regression, build an ensemble, and save everything for instant use next time.
- **Recursive Forecasting**: The script uses a dynamic lag-forwarding methodology to iteratively compute unknown future indicators to drive multi-step XGBoost predictions.
