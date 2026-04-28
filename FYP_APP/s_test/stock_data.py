import yfinance as yf
import pandas as pd
STOCK_SYMBOL = "AAPL"
START_DATE = "2024-01-01"
END_DATE = "2026-04-22"

def download_stock_data():
    df = yf.download(STOCK_SYMBOL, start=START_DATE, end=END_DATE)
    
    df.reset_index(inplace=True)
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    
    df.to_csv(f"data/raw/{STOCK_SYMBOL}_stock_data.csv", index=False)
    print("Stock data saved ✅")

if __name__ == "__main__":
    download_stock_data()
# import yfinance as yf
# import pandas as pd
# import os

# # Create directory if it doesn't exist
# os.makedirs("data/raw", exist_ok=True)

# symbols = [
#     "AAPL", "TSLA", "MSFT", "AMZN", "GOOGL",
#     "META", "NVDA", "NFLX", "AMD", "INTC",
#     "ORCL", "IBM", "ADBE", "CRM", "QCOM",
#     "AVGO", "TXN", "CSCO", "MU", "ASML",
#     "TSM", "SAP", "SONY", "BABA", "JD",
#     "PDD", "UBER", "LYFT", "SHOP", "SPOT",
#     "PYPL", "SQ", "ROKU", "SNAP", "ZM",
#     "DIS", "WMT", "COST", "MCD", "NKE",
#     "SBUX", "KO", "PEP", "PG", "JNJ",
#     "XOM", "CVX", "BAC", "JPM", "GS"
# ]

# START_DATE = "2023-01-01"
# END_DATE = "2024-01-01"

# def download_stock_data():

#     all_data = []

#     for symbol in symbols:
#         df = yf.download(symbol, start=START_DATE, end=END_DATE)

#         df.reset_index(inplace=True)

#         df['Date'] = pd.to_datetime(df['Date']).dt.date

#         df['symbol'] = symbol   # 🔥 IMPORTANT FIX

#         all_data.append(df)

#     final_df = pd.concat(all_data)

#     final_df.to_csv("data/raw/stock_data.csv", index=False)

#     print("Multi-stock data saved ✅")

# if __name__ == "__main__":
#     download_stock_data()