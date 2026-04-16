import warnings
import yfinance as yf
import pandas as pd
import requests
import datetime
import pytz
import json
import os
from textblob import TextBlob  # for simple sentiment analysis

# ==========================================
# IGNORE FUTURE AND DEPRECATION WARNINGS
# ==========================================
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=DeprecationWarning)

# ==========================================
# CONFIG
# ==========================================
SYMBOL = "AAPL"
# FINNHUB_API_KEY = "d5925c9r01qvj8ijk49gd5925c9r01qvj8ijk4a0"  # optional
NEWSAPI_KEY = "eeaa3ad47b384cb793bb0ca38185b181"
# stock_data_key = "RH1cObRmVBGqK0a9SmEBdJfs6LT5TsAEvxKbswCB"  # optional
NEPAL_TZ = pytz.timezone("Asia/Kathmandu")
CACHE_FILE = "cache.json"


# ==========================================
# HELPER: LOAD/WRITE CACHE
# ==========================================
def load_cache(symbol):
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
            return cache.get(symbol)
    return None


def save_cache(symbol, data):
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
    cache[symbol] = data
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=4)


# ==========================================
# FETCH LIVE STOCK DATA
# ==========================================
# def get_stock_data(symbol):
#     try:
#         ticker = yf.Ticker(symbol)
#         info = ticker.info
#         df = ticker.history(period="1d", interval="1m")
#         if df.empty:
#             return None

#         last_row = df.iloc[-1]
#         prev_close = info.get("previousClose", last_row["Close"])
#         change = last_row["Close"] - prev_close

#         utc_dt = datetime.datetime.utcnow()
#         nepal_dt = utc_dt.astimezone(NEPAL_TZ)
#         if not symbol:
#             return None

#         symbol = symbol.strip().upper()

#         url = "https://api.stockdata.org/v1/data/quote"
#         params = {"symbols": symbol, "api_token": stock_data_key}
#         response = requests.get(url, params=params, timeout=10)
#         response.raise_for_status()
#         result = response.json()

#         stock = result["data"][0]
#         stock_data = {
#             "symbol": symbol,
#             "CompanyName": info.get("shortName", symbol),
#             "Currency": info.get("currency", "USD"),
#             "nepal_dt": str(nepal_dt),
#             "utc_dt": str(utc_dt),
#             "open_price": stock.get("day_open", 0),
#             "high_price": stock.get("day_high", 0),
#             "low_price": stock.get("day_low", 0),
#             "close_price": stock.get("price", 0),
#             "volume": stock.get("volume", 0),
#             "change": float(change)
#         }
#         return stock_data
#     except:
#         return None


# ==========================================
# CALCULATE TECHNICAL INDICATORS
# ==========================================
def calculate_indicators(symbol):
    try:
        df = yf.download(symbol, period="3mo", interval="1d")
        df["MA20"] = df["Close"].rolling(20).mean()
        df["MA50"] = df["Close"].rolling(50).mean()

        # RSI
        delta = df["Close"].diff()
        up, down = delta.clip(lower=0), -delta.clip(upper=0)
        roll_up = up.rolling(14).mean()
        roll_down = down.rolling(14).mean()
        df["RSI"] = 100 - (100 / (1 + roll_up / roll_down))

        # MACD
        exp1 = df["Close"].ewm(span=12, adjust=False).mean()
        exp2 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = exp1 - exp2
        df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()

        last_row = df.iloc[-1]
        return {
            "RSI": float(last_row["RSI"]),
            "MACD": {
                "macd": float(last_row["MACD"]),
                "signal": float(last_row["Signal"])
            }
        }
    except:
        return None


# ==========================================
# FETCH NEWS SENTIMENT (Finnhub + NewsAPI)
# ==========================================
def get_news_sentiment(symbol):
    sentiment = {"bullish_percent": 0, "bearish_percent": 0, "sentiment_score": 0, "articles": []}
    try:
        # --- Finnhub sentiment ---
        url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={FINNHUB_API_KEY}"
        resp = requests.get(url).json()
        sentiment["bullish_percent"] = resp.get("bullishPercent", 0)
        sentiment["bearish_percent"] = resp.get("bearishPercent", 0)
        sentiment["sentiment_score"] = resp.get("sentiment", 0)
    except:
        pass

    try:
        # --- NewsAPI sentiment ---
        url = f"https://newsapi.org/v2/everything?q={symbol}&sortBy=publishedAt&language=en&apiKey={NEWSAPI_KEY}"
        resp = requests.get(url).json()
        articles = [a for a in resp.get("articles", []) if a.get("description")]  # remove null descriptions
        articles = articles[:5]
        sentiment["articles"] = [{"title": a["title"], "description": a["description"]} for a in articles]

        # Calculate simple sentiment score using TextBlob
        scores = []
        for a in articles:
            text = (a["title"] or "") + " " + (a["description"] or "")
            if text.strip():
                blob = TextBlob(text)
                scores.append(blob.sentiment.polarity)
        sentiment["sentiment_score_newsapi"] = sum(scores)/len(scores) if scores else 0
    except:
        sentiment["sentiment_score_newsapi"] = 0

    # Fallback if Finnhub returns 0
    if sentiment["bullish_percent"] == 0 and sentiment["bearish_percent"] == 0:
        score = sentiment.get("sentiment_score_newsapi", 0)
        if abs(score) < 0.05:
            sentiment["bullish_percent"] = 50
            sentiment["bearish_percent"] = 50
        else:
            shift = min(abs(score)*50, 25)
            if score > 0:
                sentiment["bullish_percent"] = 50 + shift
                sentiment["bearish_percent"] = 50 - shift
            else:
                sentiment["bullish_percent"] = 50 - shift
                sentiment["bearish_percent"] = 50 + shift

    return sentiment


# ==========================================
# GENERATE BUY/SELL/HOLD DECISION
# ==========================================
def decision_engine(stock, indicators, sentiment):
    if not stock or not indicators:
        return {"action": "HOLD", "confidence_score": 0, "reason": "Insufficient data"}

    rsi = indicators["RSI"]
    macd = indicators["MACD"]["macd"]
    signal = indicators["MACD"]["signal"]
    bull = sentiment.get("bullish_percent", 50)
    bear = sentiment.get("bearish_percent", 50)

    score = 0
    reasons = []

    # RSI
    if rsi < 30:
        score += 25
        reasons.append("RSI Oversold → Bullish")
    elif rsi > 70:
        score -= 25
        reasons.append("RSI Overbought → Bearish")
    else:
        reasons.append("RSI Neutral")

    # MACD
    if macd > signal:
        score += 30
        reasons.append("MACD Bullish Crossover")
    else:
        score -= 30
        reasons.append("MACD Bearish")

    # Sentiment
    sentiment_diff = bull - bear
    sentiment_score = sentiment_diff * 0.4
    score += sentiment_score
    reasons.append(f"Sentiment Impact: {sentiment_score:.1f}")

    # Final action
    if score > 25:
        action = "BUY"
    elif score < -25:
        action = "SELL"
    else:
        action = "HOLD"

    confidence = min(max(abs(score), 0), 100)

    # Conflict detection
    conflict = False
    if (macd > signal and bear > bull) or (macd < signal and bull > bear):
        conflict = True
        confidence *= 0.7

    return {
        "action": action,
        "confidence_score": round(confidence, 2),
        "trend": "Bullish" if score > 25 else ("Bearish" if score < -25 else "Neutral"),
        "strength": "Strong" if abs(score) > 50 else "Weak",
        "conflict": conflict,
        "reason": " | ".join(reasons)
    }


# # ==========================================
# # MAIN
# # ==========================================
# if __name__ == "__main__":
#     # Try cached data first
#     cached = load_cache(SYMBOL)

#     stock_data = get_stock_data(SYMBOL) or (cached.get("stock_data") if cached else None)
#     indicators = calculate_indicators(SYMBOL) or (cached.get("indicators") if cached else None)
#     sentiment = get_news_sentiment(SYMBOL) or (cached.get("sentiment") if cached else None)
#     decision = decision_engine(stock_data, indicators, sentiment)

#     result = {
#         "stock_data": stock_data,
#         "indicators": indicators,
#         "sentiment": sentiment,
#         "decision": decision
#     }

#     # Save cache if new output differs
#     if cached != result:
#         save_cache(SYMBOL, result)

#     print(json.dumps(result, indent=4))