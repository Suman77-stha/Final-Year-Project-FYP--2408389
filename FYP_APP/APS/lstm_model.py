# ==========================================
# AI STOCK PRICE PREDICTION (LLM Qwen3.5-35B)
# ==========================================

import datetime
import pytz
import yfinance as yf
import torch
import re
import json

from transformers import AutoTokenizer, AutoModelForCausalLM

# ==========================================
# CONFIG
# ==========================================
TIMEZONE = pytz.timezone("Asia/Kathmandu")
PREDICT_DAYS = 7  # Number of days to forecast
RECENT_DAYS = 30  # Last N days of closing prices

# ==========================================
# DATA LOADING
# ==========================================
def load_stock_data(symbol):
    START = "2015-01-01"
    TODAY = datetime.datetime.now(TIMEZONE).date()

    data = yf.download(symbol, START, TODAY, progress=False)

    if data.empty:
        raise ValueError(f"No data found for symbol: {symbol}")

    if "Close" not in data.columns:
        raise ValueError(f"'Close' column not found in data for {symbol}")

    data.reset_index(inplace=True)
    return data

# ==========================================
# LOAD QWEN MODEL
# ==========================================
def load_qwen_model():
    print("Loading Qwen3.5-35B-A3B model...")
    model_name = "Qwen/Qwen3.5-7B"

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype=torch.float16
    )
    model.eval()
    return tokenizer, model

# ==========================================
# CREATE PROMPT FOR LLM
# ==========================================
def create_prompt(symbol, recent_prices, predict_days=PREDICT_DAYS):
    """
    Formats recent prices into a prompt for Qwen3.5
    """
    prompt = f"""
You are a financial expert. Given the recent closing prices for {symbol}:

{recent_prices}

Predict the next {predict_days} days of closing prices as a JSON array of numbers only. 
Do not include explanations or text, only output a JSON array.
"""
    return prompt

# ==========================================
# PREDICTION FUNCTION
# ==========================================
def predict_stock_price(symbol="AAPL", recent_days=RECENT_DAYS, predict_days=PREDICT_DAYS):
    print(f"\nPredicting stock price for {symbol} using Qwen3.5-35B...")

    # Load stock data
    data = load_stock_data(symbol)
    # Safe conversion to list
    if "Close" in data.columns:
        close_prices = data["Close"].values.flatten().tolist()
    else:
        raise ValueError(f"'Close' column not found in data for {symbol}")      # Convert Series to list
    recent_prices = close_prices[-recent_days:]  # Last 30 days

    # Load model
    tokenizer, model = load_qwen_model()

    # Create prompt
    prompt = create_prompt(symbol, recent_prices, predict_days)

    # Tokenize and move to GPU
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

    # Generate predictions
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=50,
            temperature=0.0,
            do_sample=False
        )

    # Decode output
    prediction_text = tokenizer.decode(outputs[0], skip_special_tokens=True)

    # Extract JSON array from text
    match = re.search(r"\[.*\]", prediction_text)
    if match:
        future_predictions = json.loads(match.group())
    else:
        future_predictions = []

    # Safe fallback
    predicted_price = future_predictions[-1] if future_predictions else None

    return {
        "symbol": symbol,
        "current_price": close_prices[-1],
        "close_prices": recent_prices,
        "predicted_price": predicted_price,
        "future_days": future_predictions
    }

# ==========================================
# TERMINAL TEST
# ==========================================
if __name__ == "__main__":
    result = predict_stock_price("TSLA")

    print("\nAI STOCK PRICE PREDICTION (Qwen3.5)")
    print("--------------------------------")
    print("Symbol:", result["symbol"])
    print("Current Price:", result["current_price"])
    print("Predicted Price (Day 7):", result["predicted_price"])

    print("\nLast 30 Days Closing Prices:")
    for i, price in enumerate(result["close_prices"], 1):
        print(f"Day {i}: ${price:.2f}")

    print("\n7 Day Forecast:")
    for i, price in enumerate(result["future_days"], 1):
        print(f"Day {i}: ${price:.2f}")