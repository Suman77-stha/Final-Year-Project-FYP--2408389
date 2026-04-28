# S_Test Folder System Analysis Report

**Generated on:** April 22, 2026  
**Folder Path:** `FYP/FYP_APP/s_test`  
**System Purpose:** Stock Price Prediction using Sentiment Analysis and Machine Learning

## 1. System Overview

The `s_test` folder contains a complete machine learning pipeline for stock price prediction. The system integrates multiple data sources and advanced AI techniques to forecast stock prices by combining:

- **Technical Analysis:** Stock price data and derived features
- **Sentiment Analysis:** News headline sentiment using FinBERT
- **Deep Learning:** LSTM for time-series feature extraction
- **Machine Learning:** XGBoost for final price prediction

The system is designed for single stock analysis (primarily AAPL) and follows a modular architecture where each Python file handles a specific stage of the data processing and modeling pipeline.


### Normal File Flow Sequence

1. **Data Acquisition Phase**
   - `stock_data.py` → Downloads historical stock data
   - `news_data.py` → Fetches financial news data

2. **Data Preprocessing Phase**
   - `data_cleaning.py` → Cleans and validates both datasets

3. **Feature Engineering Phase**
   - `sentiment.py` → Computes sentiment scores from news
   - `lstm_features.py` → Extracts temporal patterns via LSTM
   - `merge_features.py` → Combines all features into training dataset

4. **Model Training Phase**
   - `train_xgboost.py` → Trains the prediction model

5. **Inference & Evaluation Phase**
   - `xgboost_prediction.py` → Generates future price predictions
   - `evaluation.py` → Assesses model performance

## 3. Detailed Component Analysis

### 3.1 Data Acquisition Modules

#### `stock_data.py`
- **Purpose:** Downloads historical stock price data
- **API Used:** Yahoo Finance (yfinance library)
- **Parameters:** 
  - Symbol: AAPL (configurable)
  - Date Range: 2024-01-01 to 2026-04-22
- **Output:** `data/raw/{symbol}_stock_data.csv` with OHLCV data
- **Key Features:** Automatic date formatting, CSV export

#### `news_data.py`
- **Purpose:** Fetches financial news headlines
- **API Used:** Alpha Vantage News API
- **Parameters:** 
  - Symbol: AAPL
  - Date Range: 2024-01-01 to 2026-04-22
  - Limit: 1000 articles
- **Output:** `data/raw/{symbol}_news_data.csv` with date and headline
- **Key Features:** Sentiment-ready data extraction

### 3.2 Data Preprocessing Module

#### `data_cleaning.py`
- **Purpose:** Data quality assurance and standardization
- **Stock Data Cleaning:**
  - Removes duplicates
  - Converts 'Close' to numeric (handles errors)
  - Forward fills missing values
  - Filters out invalid prices (≤ 0)
  - Standardizes date format
- **News Data Cleaning:**
  - Removes duplicate headlines
  - Filters headlines > 20 characters
  - Cleans special characters from headlines
  - Standardizes date format
- **Output:** Cleaned versions in `data/processed/`

### 3.3 Feature Engineering Modules

#### `sentiment.py`
- **Purpose:** Quantifies market sentiment from news
- **Model Used:** FinBERT (ProsusAI/finbert)
- **Process:**
  - Loads pre-trained transformer model
  - Computes sentiment score per headline (positive - negative)
  - Aggregates daily average sentiment
- **Output:** `data/processed/{symbol}_sentiment_data.csv`
- **Key Features:** GPU-accelerated inference, daily aggregation

#### `lstm_features.py`
- **Purpose:** Extracts temporal patterns from price data
- **Architecture:** Simple LSTM network (50 units)
- **Process:**
  - Creates 10-day price sequences
  - Trains LSTM to predict next day's price
  - Uses predictions as features
- **Output:** `data/processed/{symbol}_lstm_features.csv`
- **Key Features:** Sequence-based feature extraction

#### `merge_features.py`
- **Purpose:** Creates unified training dataset
- **Merging Strategy:** Left join on date
- **Additional Features:**
  - `return`: Daily price change percentage
  - `ma7`: 7-day moving average
  - `volatility`: 7-day rolling standard deviation
  - `target`: Next day's closing price
- **Output:** `data/processed/{symbol}_final_dataset.csv`
- **Key Features:** Missing value handling, feature engineering

### 3.4 Model Training Module

#### `train_xgboost.py`
- **Purpose:** Trains the final prediction model
- **Algorithm:** XGBoost Regressor
- **Features Used:**
  - return, ma7, volatility (technical)
  - sentiment (fundamental)
  - lstm_feature (deep learning)
- **Hyperparameters:**
  - n_estimators: 300
  - learning_rate: 0.05
  - max_depth: 5
- **Output:** `data/processed/{symbol}_xgb_model.json`

### 3.5 Inference & Evaluation Modules

#### `xgboost_prediction.py`
- **Purpose:** Generates future price predictions
- **Method:** Iterative prediction with state updates
- **Features:** Live price integration, trading day calculation
- **Process:**
  - Starts from current live price
  - Predicts returns iteratively
  - Updates feature state for each prediction
- **Output:** Dictionary with predictions and dates

#### `evaluation.py`
- **Purpose:** Model performance assessment
- **Metrics:** MAE (Mean Absolute Error), RMSE (Root Mean Square Error)
- **Method:** Test set evaluation on historical data

## 4. System Dependencies & Requirements

### Python Libraries
- `pandas`, `numpy` - Data manipulation
- `yfinance` - Stock data download
- `requests` - API calls
- `transformers`, `torch` - Sentiment analysis
- `tensorflow` - LSTM features
- `xgboost` - Final model
- `sklearn` - Metrics and preprocessing

### External APIs
- **Yahoo Finance:** Stock price data
- **Alpha Vantage:** Financial news data
- **Hugging Face:** FinBERT model

### Data Directory Structure
```
data/
├── raw/
│   ├── {symbol}_stock_data.csv
│   └── {symbol}_news_data.csv
└── processed/
    ├── {symbol}_stock_cleaned.csv
    ├── {symbol}_news_cleaned.csv
    ├── {symbol}_sentiment_data.csv
    ├── {symbol}_lstm_features.csv
    ├── {symbol}_final_dataset.csv
    └── {symbol}_xgb_model.json
```

## 5. System Strengths & Limitations

### Strengths
- **Modular Design:** Each component can be updated independently
- **Multi-modal Features:** Combines technical, fundamental, and AI features
- **Automated Pipeline:** End-to-end processing from raw data to predictions
- **State-of-the-art Models:** Uses modern NLP and deep learning techniques

### Limitations
- **Single Stock Focus:** Currently designed for one symbol at a time
- **API Dependencies:** Relies on external data sources
- **Computational Intensity:** Sentiment analysis and LSTM training require significant resources
- **Short-term Focus:** LSTM sequences limited to 10 days

## 6. Usage Instructions

### Training Pipeline
```bash
# Run in sequence
python stock_data.py
python news_data.py
python data_cleaning.py
python sentiment.py
python lstm_features.py
python merge_features.py
python train_xgboost.py
```

### Prediction
```python
from xgboost_prediction import predict
result = predict("AAPL", future_days=5)
print(result)

## 4. Conclusion

Your `s_test` module already has a solid end-to-end ML workflow structure.  
The main reliability issues are import-time side effects, hardcoded keys, and inconsistent pipeline orchestration rules.  
With a strict controller and small refactors, this can become a stable production-style forecasting pipeline.
