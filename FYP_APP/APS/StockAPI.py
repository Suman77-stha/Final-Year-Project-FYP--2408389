import datetime
import os
import pytz
import requests
import yfinance as yf

try:
    from django.conf import settings
except Exception:
    settings = None


SYMBOL_ALIASES = {
    "TESLA": "TSLA",
    "GOOGLE": "GOOGL",
}


def _normalize_symbol(symbol):
    normalized = symbol.strip().upper()
    return SYMBOL_ALIASES.get(normalized, normalized)


def _build_response_data(symbol, company, currency, utc_dt, open_price, high_price, low_price, close_price, volume, change):
    nepal_tz = pytz.timezone("Asia/Kathmandu")
    nepal_dt = utc_dt.astimezone(nepal_tz).date()
    return {
        "symbol": symbol,
        "CompanyName": company,
        "Currency": currency,
        "nepal_dt": nepal_dt,
        "utc_dt": utc_dt,
        "open_price": open_price or 0,
        "high_price": high_price or 0,
        "low_price": low_price or 0,
        "close_price": close_price or 0,
        "volume": volume or 0,
        "change": change or 0,
    }


def _get_stock_data_from_yfinance(symbol):
    """
    Free fallback provider when stockdata.org quota/plan fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")

        if hist is None or hist.empty:
            print(f"Fallback error for {symbol}: no history from yfinance")
            return None

        latest = hist.iloc[-1]
        previous_close = hist.iloc[-2]["Close"] if len(hist) > 1 else latest["Close"]
        change = float(latest["Close"] - previous_close)
        info = ticker.fast_info if hasattr(ticker, "fast_info") else {}
        company = ""

        try:
            company = ticker.info.get("shortName", "")
        except Exception:
            company = ""

        currency = info.get("currency", "USD") if info else "USD"
        ts = hist.index[-1]
        if hasattr(ts, "to_pydatetime"):
            utc_dt = ts.to_pydatetime()
        else:
            utc_dt = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)

        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=pytz.utc)
        else:
            utc_dt = utc_dt.astimezone(pytz.utc)

        return _build_response_data(
            symbol=symbol,
            company=company or symbol,
            currency=currency,
            utc_dt=utc_dt,
            open_price=float(latest.get("Open", 0)),
            high_price=float(latest.get("High", 0)),
            low_price=float(latest.get("Low", 0)),
            close_price=float(latest.get("Close", 0)),
            volume=int(latest.get("Volume", 0)),
            change=change,
        )
    except Exception as e:
        print(f"Fallback error for {symbol}: {e}")
        return None


def get_stock_data(symbol):
    """
    Fetch stock data from stockdata.org API.
    Returns dictionary or None.
    """

    # ---------------- INPUT VALIDATION ----------------
    if not symbol:
        return None

    symbol = _normalize_symbol(symbol)

    url = "https://api.stockdata.org/v1/data/quote"
    api_key = (
        getattr(settings, "STOCKDATA_API_KEY", None)
        if settings is not None
        else None
    ) or os.environ.get("STOCKDATA_API_KEY", "")

    params = {
        "symbols": symbol,
        "api_token": api_key,
    }

    result = None
    if api_key:
        try:
            response = requests.get(url, params=params, timeout=10)

            # 402 = quota/plan issue on stockdata.org
            if response.status_code == 402:
                print(f"Primary API quota/plan issue for {symbol} (HTTP 402). Falling back to yfinance.")
                return _get_stock_data_from_yfinance(symbol)

            response.raise_for_status()
            result = response.json()

        except requests.RequestException as e:
            print(f"API error for {symbol}: {e}. Falling back to yfinance.")
            return _get_stock_data_from_yfinance(symbol)
    else:
        print(f"Primary API key missing for {symbol}. Falling back to yfinance.")
        return _get_stock_data_from_yfinance(symbol)

    # ---------------- CHECK DATA EXISTS ----------------
    if not result.get("data"):
        print(f"No data returned for {symbol}. Falling back to yfinance.")
        return _get_stock_data_from_yfinance(symbol)

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
    return _build_response_data(
        symbol=stock.get("ticker") or symbol,
        company=stock.get("name") or symbol,
        currency=stock.get("currency") or "USD",
        utc_dt=utc_dt,
        open_price=stock.get("day_open", 0),
        high_price=stock.get("day_high", 0),
        low_price=stock.get("day_low", 0),
        close_price=stock.get("price", 0),
        volume=stock.get("volume", 0),
        change=stock.get("day_change", 0),
    )

if __name__ == "__main__":
    print(get_stock_data("AAPL"))
