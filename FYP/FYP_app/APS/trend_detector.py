def detect_market_trend(predicted_price, current_price, indicators):
    rsi = indicators["RSI"]
    macd = indicators["MACD"]["macd"]
    signal = indicators["MACD"]["signal"]

    confidence = "Low"

    if (macd > signal and rsi < 70) or (macd < signal and rsi > 30):
        confidence = "High"

    if predicted_price > current_price:
        return {
            "trend": "Bullish",
            "action": "BUY",
            "confidence": confidence,
            "color": "green"
        }

    elif predicted_price < current_price:
        return {
            "trend": "Bearish",
            "action": "SELL",
            "confidence": confidence,
            "color": "red"
        }

    return {
        "trend": "Neutral",
        "action": "HOLD",
        "confidence": "Very Low",
        "color": "gray"
    }
