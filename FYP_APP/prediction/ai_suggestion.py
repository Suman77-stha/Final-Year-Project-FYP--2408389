import time
import yfinance as yf
import pandas as pd
from .predict_system import predict
from .utils import calculate_indicators

_suggestion_cache = {}
CACHE_TTL = 1800  # 30 minutes cache

def generate_ai_suggestion(symbol, user_has_stock):
    """
    Generates a BUY, SELL, or HOLD suggestion based on:
    - User's current portfolio (user_has_stock)
    - XGBoost model prediction accuracy and trend
    - Technical Indicators (RSI, MACD)
    """
    global _suggestion_cache
    cache_key = f"{symbol}_{user_has_stock}"
    if cache_key in _suggestion_cache:
        cached_time, cached_data = _suggestion_cache[cache_key]
        if time.time() - cached_time < CACHE_TTL:
            return cached_data

    # 1. Get Prediction from XGBoost Pipeline
    try:
        # Request a 7-day forecast. This will use cached models if they exist.
        pred_data = predict(symbol, future_days=7)
        mape = pred_data.get("mape", 100)
        accuracy = max(0, min(100, round(100 - mape, 2)))
        
        current_price = pred_data.get("current_price", 0)
        
        # Look at the 7-day forecast to determine direction
        future_prices = pred_data.get("future_days", [])
        if future_prices:
            predicted_target = future_prices[-1]
        else:
            predicted_target = pred_data.get("predicted_price", 0)
            
        trend_bullish = predicted_target > current_price
    except Exception as e:
        print(f"Error getting prediction for {symbol}: {e}")
        accuracy = 0
        trend_bullish = False

    # 2. Get Technical Indicators (RSI, MACD)
    rsi = 50
    macd = 0
    macd_bullish = False
    
    try:
        # Fetching enough data (e.g. 60 days) to ensure MACD (26-day EMA) can be calculated without NaNs, 
        # while fulfilling the requirement to look at recent 30-day window metrics.
        df = yf.download(symbol, period="60d", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        
        # Use existing utility to calculate indicators
        ind_df = calculate_indicators(df)
        last_row = ind_df.iloc[-1]
        
        rsi = float(last_row.get("RSI", 50))
        macd = float(last_row.get("MACD", 0))
        macd_bullish = macd > 0
        
    except Exception as e:
        print(f"Error calculating indicators for {symbol}: {e}")
        pass

    # 3. Formulate Action based on Context
    action = "HOLD"
    reasons = []
    
    if trend_bullish:
        reasons.append("Model predicts upward trend")
    else:
        reasons.append("Model predicts downward trend")
        
    if rsi < 30:
        reasons.append("RSI Oversold")
    elif rsi > 70:
        reasons.append("RSI Overbought")
        
    if macd_bullish:
        reasons.append("MACD Bullish")
    else:
        reasons.append("MACD Bearish")

    # The Core AI Logic:
    if not user_has_stock:
        # If the user doesn't own it, we can only BUY or HOLD
        if trend_bullish and rsi < 70 and macd_bullish:
            # We don't want to buy if it's overbought, but if trend is up and indicators agree -> BUY
            action = "BUY"
        elif trend_bullish and accuracy > 50 and rsi < 70:
            # If accuracy is very high and trend is up, BUY even if MACD is lagging
            action = "BUY"
        else:
            action = "HOLD"
    else:
        # If the user owns it, we can only SELL or HOLD
        if not trend_bullish and rsi > 70 and not macd_bullish:
            # Trend down, overbought, MACD bearish -> SELL
            action = "SELL"
        elif not trend_bullish and accuracy > 50 and not macd_bullish:
            # High accuracy downward trend with bearish MACD -> SELL
            action = "SELL"
        else:
            # Hold to ride out noise
            action = "HOLD"

    result = {
        "action": action,
        "confidence_score": accuracy, # Return the XGBoost accuracy directly
        "trend": "Bullish" if trend_bullish else "Bearish",
        "strength": "Strong" if accuracy > 60 else "Weak",
        "reason": " | ".join(reasons)
    }
    
    _suggestion_cache[cache_key] = (time.time(), result)
    return result
