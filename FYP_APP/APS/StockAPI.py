import datetime
import pytz
import requests


def get_stock_data(symbol):
    """
    Fetch stock data from stockdata.org API.
    Returns dictionary or None.
    """

    # ---------------- INPUT VALIDATION ----------------
    if not symbol:
        return None

    symbol = symbol.strip().upper()

    url = "https://api.stockdata.org/v1/data/quote"

    params = {
        "symbols": symbol,
        "api_token": "RH1cObRmVBGqK0a9SmEBdJfs6LT5TsAEvxKbswCB",  # move to settings later
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()

    except requests.RequestException as e:
        print(f"API error for {symbol}: {e}")
        return None

    # ---------------- CHECK DATA EXISTS ----------------
    if not result.get("data"):
        print(f"No data returned for {symbol}")
        return None

    stock = result["data"][0]

    # ---------------- TIME CONVERSION ----------------
    try:
        utc_dt = datetime.datetime.fromisoformat(
            stock["last_trade_time"]
        ).replace(tzinfo=pytz.utc)

        nepal_tz = pytz.timezone("Asia/Kathmandu")
        nepal_dt = utc_dt.astimezone(nepal_tz).date()

    except Exception as e:
        print(f"Date conversion error for {symbol}: {e}")
        return None

    # ---------------- CLEAN DATA ----------------
    data = {
        "symbol": stock.get("ticker"),
        "CompanyName": stock.get("name"),
        "Currency": stock.get("currency"),
        "nepal_dt": nepal_dt,
        "utc_dt": utc_dt,   # keep full datetime
        "open_price": stock.get("day_open", 0),
        "high_price": stock.get("day_high", 0),
        "low_price": stock.get("day_low", 0),
        "close_price": stock.get("price", 0),  # use current price instead of previous_close
        "volume": stock.get("volume", 0),
        "change": stock.get("day_change", 0),
    }

    return data

if __name__ == "__main__":
    print(get_stock_data("AAPL"))