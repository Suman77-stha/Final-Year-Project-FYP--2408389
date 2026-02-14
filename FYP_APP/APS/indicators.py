# TECHNICAL INDICATORS MODULE

import pandas as pd


def calculate_rsi(close_prices, period=14):
    """
    Calculates Relative Strength Index (RSI)
    """
    delta = close_prices.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return round(rsi.iloc[-1], 2)


def calculate_macd(close_prices):
    """
    Calculates MACD and Signal Line
    """
    short_ema = close_prices.ewm(span=12, adjust=False).mean()
    long_ema = close_prices.ewm(span=26, adjust=False).mean()

    macd = short_ema - long_ema
    signal = macd.ewm(span=9, adjust=False).mean()

    return {
        "macd": round(macd.iloc[-1], 2),
        "signal": round(signal.iloc[-1], 2)
    }


def get_technical_indicators(close_prices):
    """
    Returns all indicators in one dictionary
    """
    return {
        "RSI": calculate_rsi(close_prices),
        "MACD": calculate_macd(close_prices)
    }
