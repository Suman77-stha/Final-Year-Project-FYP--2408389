from lstm_model import predict_stock_price
from indicators import get_technical_indicators
from trend_detector import detect_market_trend

data = predict_stock_price("AAPL")

indicators = get_technical_indicators(data["close_prices"])

trend = detect_market_trend(
    data["predicted_price"],
    data["current_price"],
    indicators
)

print("Trend:", trend)
print("Indicators:", indicators)
