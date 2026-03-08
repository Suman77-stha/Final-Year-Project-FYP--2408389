import pandas as pd
def calculate_rsi(close_prices, period=14):
    """
    RELATIVE STRENGTH INDEX (RSI)

    Meaning:
    RSI measures how fast and how much a stock price is changing.
    It helps identify whether a stock is:
        - Overbought (too expensive)
        - Oversold (too cheap)

    RSI Value Interpretation:
        RSI > 70  → Overbought → Possible SELL signal
        RSI < 30  → Oversold  → Possible BUY signal
        RSI 30–70 → Neutral   → HOLD

    Parameters:
    close_prices (pd.Series): Stock closing prices
    period (int): Number of days used for RSI calculation (default = 14)

    Returns:
    float: Latest RSI value
    """

    # Step 1: Calculate price changes between consecutive days
    delta = close_prices.diff()

    # Step 2: Separate positive changes (gains)
    gain = delta.where(delta > 0, 0.0)

    # Step 3: Separate negative changes (losses)
    loss = -delta.where(delta < 0, 0.0)

    # Step 4: Calculate average gain over the period
    avg_gain = gain.rolling(period).mean()

    # Step 5: Calculate average loss over the period
    avg_loss = loss.rolling(period).mean()

    # Step 6: Calculate Relative Strength (RS)
    rs = avg_gain / avg_loss

    # Step 7: Convert RS into RSI using standard formula
    rsi = 100 - (100 / (1 + rs))

    # Step 8: Return latest RSI value
    return float(rsi.iloc[-1].item())


def calculate_macd(close_prices):
    """
    =========================
    MOVING AVERAGE CONVERGENCE DIVERGENCE (MACD)
    =========================

    Meaning:
    MACD identifies trend direction and momentum.
    It compares short-term price movement with long-term movement.

    MACD Interpretation:
        MACD > Signal → Bullish trend → BUY signal
        MACD < Signal → Bearish trend → SELL signal

    Components:
        - MACD Line   = 12-day EMA − 26-day EMA
        - Signal Line = 9-day EMA of MACD line

    Parameters:
    close_prices (pd.Series): Stock closing prices

    Returns:
    dict: Latest MACD and Signal values
    """

    # Step 1: Calculate short-term exponential moving average (12 days)
    short_ema = close_prices.ewm(span=100, adjust=False).mean()

    # Step 2: Calculate long-term exponential moving average (26 days)
    long_ema = close_prices.ewm(span=200, adjust=False).mean()

    # Step 3: MACD line calculation
    macd = short_ema - long_ema

    # Step 4: Signal line calculation (9-day EMA of MACD)
    signal = macd.ewm(span=9, adjust=False).mean()

    # Step 5: Return latest MACD and Signal values
    return {
        "macd": float(macd.iloc[-1].item()),
        "signal": float(signal.iloc[-1].item())
    }


def get_technical_indicators(close_prices):
    """
    =========================
    TECHNICAL INDICATORS WRAPPER
    =========================

    Purpose:
    Collects all technical indicators used in the system
    and returns them in a structured format.

    Used in:
    APS → DRS → TBS decision pipeline

    Returns:
    dict: RSI and MACD indicator values
    """

    return {
        "RSI": calculate_rsi(close_prices),
        "MACD": calculate_macd(close_prices)
    }
