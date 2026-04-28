# import pandas as pd
import os
import time
# import yfinance as yf

# FAMOUS_STOCKS = [
#     "AAPL", "MSFT", "GOOGL", "AMZN", "META",
#     "TSLA", "NVDA", "NFLX", "AMD", "INTC",
#     "IBM", "ORCL", "ADBE", "CRM", "QCOM",
#     "BABA", "TSM", "SAP", "SONY", "UBER",
#     "DIS", "NKE", "PFE", "MRNA", "JPM",
#     "BAC", "GS", "C", "WFC", "V",
#     "MA", "AXP", "SPGI", "BLK", "COST",
#     "WMT", "HD", "MCD", "KO", "PEP",
#     "XOM", "CVX", "BP", "SHEL", "TTE",
#     "SHOP", "SQ", "PLTR", "SNOW", "TWTR"
# ]

# create folder for saving data
# SAVE_DIR = "data/stock_data"
# os.makedirs(SAVE_DIR, exist_ok=True)


# def download_stock_data(ticker, start, end):
#     """
#     Download stock price data from Yahoo Finance
#     and save as CSV per ticker
#     """
#     try:
#         df = yf.download(ticker, start=start, end=end)

#         if df.empty:
#             print(f"No data for {ticker}")
#             return

#         file_path = os.path.join(SAVE_DIR, f"{ticker}.csv")
#         df.to_csv(file_path)

#         print(f"Saved: {file_path}")

#     except Exception as e:
#         print(f"Error downloading {ticker}: {e}")


# # loop through stocks
# for ticker in FAMOUS_STOCKS:
#     download_stock_data(ticker, "2023-10-01", "2026-04-16")
#     time.sleep(1)  # avoid rate limiting

import pandas as pd
import os  # missing import

SAVE_DIR = "data"
os.makedirs(SAVE_DIR, exist_ok=True)

def download_stock_data(ticker, start, end):
    """
    download stock price data from Yahoo Finance
    """
    import yfinance as yf
    stock_data = yf.download(ticker, start=start, end=end)
    df = pd.DataFrame(stock_data)
    
    file_path = os.path.join(SAVE_DIR, "stock_price.csv")
    df.to_csv(file_path)  # save the data
    
    return df  # optional but useful

download_stock_data("AAPL", "2023-10-01", "2026-04-16")