import datetime
import pytz
import requests
from django.conf import settings


def get_stock_data(symbol):
    """
    Fetching new stock data.
    """
    symbol = symbol.upper()
    url = "https://api.stockdata.org/v1/data/quote"
    params = {
    "symbols": symbol,
    "api_token":"RH1cObRmVBGqK0a9SmEBdJfs6LT5TsAEvxKbswCB",
}

    # Data not found → fetch from Stock Data API
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
    except Exception as e:
        print("API error for AAPL:", e)
    # Check if data is available or not
    if not result.get("data"):
        print(f"No data returned for {symbol}")
        return None
    
    # Convert timestamp to UTC and Nepal time
    utc_dt = datetime.datetime.fromisoformat(
        result['data'][0]["last_trade_time"]
    ).replace(tzinfo=pytz.utc)

    nepal_tz = pytz.timezone("Asia/Kathmandu")
    nepal_dt = utc_dt.astimezone(nepal_tz).date()

    
    data = {
        'symbol': result['data'][0]['ticker'],
        'CompanyName': result['data'][0]['name'],
        'Currency': result['data'][0]['currency'],
        'nepal_dt': nepal_dt,
        'utc_dt': utc_dt.date(),
        'open_price': result['data'][0]['day_open'],
        'high_price': result['data'][0]['day_high'],
        'low_price': result['data'][0]['day_low'],
        'close_price': result['data'][0]['previous_close_price'],
        'volume': result['data'][0]['volume'],
        'change': result['data'][0]['day_change'],
        }
    return data
