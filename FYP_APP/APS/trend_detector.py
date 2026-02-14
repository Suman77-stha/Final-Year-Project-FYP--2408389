# MARKET TREND + BASIC ACTION
from FYP_APP.APS.lstm_model import predict_stock_price
from FYP_APP.APS.indicators import get_technical_indicators

def detect_market_trend(predicted_price, current_price):
    """
    Determines market trend and basic action
    """

    if predicted_price > current_price:
        return {
            "trend": "Bullish",
            "action": "BUY",
            "confidence": "Low",
            "description": "Price expected to rise",
            "color": "green"
        }
    elif predicted_price < current_price:
        return {
            "trend": "Bearish",
            "action": "SELL",
            "confidence": "Low",
            "description": "Price expected to fall",
            "color": "red"
        }
    else:
        return {
            "trend": "Neutral",
            "action": "HOLD",
            "confidence": "Very Low",
            "description": "No clear direction",
            "color": "gray"
        }



data = predict_stock_price("TSLA")

trend = detect_market_trend(
    data["predicted_price"],
    data["current_price"]
)

indicators = get_technical_indicators(data["close_prices"])

print(trend)
print(indicators)
