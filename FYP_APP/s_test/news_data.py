# import requests
# import pandas as pd
# NEWS_API_KEY = "eeaa3ad47b384cb793bb0ca38185b181"
# STOCK_SYMBOL = "AAPL"
# START_DATE = "2023-01-01"
# END_DATE = "2024-01-01"
# import os

# # Create directory if it doesn't exist
# os.makedirs("data/raw", exist_ok=True)

# def fetch_news():
#     url = (
#         f"https://newsapi.org/v2/everything?"
#         f"q={STOCK_SYMBOL}"
#         f"&language=en"
#         f"&sortBy=publishedAt"
#         f"&from={START_DATE}"
#         f"&to={END_DATE}"
#         f"&apiKey={NEWS_API_KEY}"
#     )

#     response = requests.get(url)
#     data = response.json()

#     print(data)

#     if data.get("status") != "ok":
#         print("API ERROR:", data.get("message", data))
#         return

#     articles = data.get("articles", [])

#     if not articles:
#         print("No articles found")
#         return

#     news_list = []
#     for article in articles:
#         news_list.append({
#             "date": article["publishedAt"][:10],
#             "headline": article["title"]
#         })

#     df = pd.DataFrame(news_list)
#     df.to_csv("data/raw/news_data.csv", index=False)

#     print("News saved successfully ✅")

# if __name__ == "__main__":
#     fetch_news()

import requests
import pandas as pd

API_KEY = "KVUW4ESTNPBECL4Q"
SYMBOL = "AAPL"

url = (
    f"https://www.alphavantage.co/query?"
    f"function=NEWS_SENTIMENT"
    f"&tickers={SYMBOL}"
    f"&time_from=20240101T0000"
    f"&time_to=20260222T0000"
    f"&limit=1000"
    f"&apikey={API_KEY}"
)

response = requests.get(url)
data = response.json()

# DEBUG
print(data)

news_list = []

for article in data.get("feed", []):
    news_list.append({
        "date": article["time_published"][:8],  # YYYYMMDD
        "headline": article["title"],
        # "sentiment": article["overall_sentiment_score"]
    })

df = pd.DataFrame(news_list)

# Convert date format
df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.date

df.to_csv(f"data/raw/{SYMBOL}_news_data.csv", index=False)

print("Alpha Vantage news saved ✅")


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

# def fetch_news():
#     all_news = []

#     for symbol in symbols:

#         url = f"https://newsapi.org/v2/everything?q={symbol}&language=en&sortBy=publishedAt&apiKey={NEWS_API_KEY}"

#         response = requests.get(url)
#         data = response.json()

#         articles = data.get("articles", [])

#         for article in articles:
#             if article["title"]:
#                 all_news.append({
#                     "symbol": symbol,   # 🔥 IMPORTANT FIX
#                     "date": article["publishedAt"][:10],
#                     "headline": article["title"]
#                 })

#     df = pd.DataFrame(all_news)
#     df.to_csv("data/raw/news_data.csv", index=False)

#     print("News with symbols saved ✅")

# if __name__ == "__main__":
#     fetch_news()