from django.conf import settings
from django.http import JsonResponse
from FYP_app.models import StockData
from datetime import datetime
import requests
import logging

logger = logging.getLogger(__name__)

def get_stock_data(symbol="AAPL"):
    api_key = settings.ALPHA_VANTAGE_KEY
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return JsonResponse({"success": False, "error": str(e)})

    data = response.json().get("Global Quote", {})

    if not data:
        return JsonResponse({"success": False, "message": f"No data returned for {symbol}"})

    trading_day_str = data.get("07. latest trading day")
    if not trading_day_str:
        return JsonResponse({"success": False, "message": f"Latest trading day not found for {symbol}"})

    try:
        trading_day = datetime.strptime(trading_day_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"success": False, "message": f"Invalid date format for {symbol}: {trading_day_str}"})

    # Avoid duplicates
    if StockData.objects.filter(symbol=symbol, date=trading_day).exists():
        message = f"Data for {symbol} on {trading_day} already exists."
        logger.info(message)
        return JsonResponse({"success": True, "message": message, "date": str(trading_day)})

    # Safely parse numeric values
    def safe_float(val):
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    def safe_int(val):
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    stock = StockData(
        symbol=data.get("01. symbol", symbol),
        date=trading_day,
        open_price=safe_float(data.get("02. open")),
        high_price=safe_float(data.get("03. high")),
        low_price=safe_float(data.get("04. low")),
        close_price=safe_float(data.get("05. price")),
        volume=safe_int(data.get("06. volume")),
        change=safe_float(data.get("09. change")),
        change_percent=data.get("10. change percent", "0%")
    )
    stock.save()
    logger.info(f"Saved {symbol} data for {trading_day}")

    return JsonResponse({
        "success": True,
        "symbol": symbol,
        "date": str(trading_day),
        "data": {
            "open": stock.open_price,
            "high": stock.high_price,
            "low": stock.low_price,
            "close": stock.close_price,
            "volume": stock.volume,
            "change": stock.change,
            "change_percent": stock.change_percent
        }
    })
