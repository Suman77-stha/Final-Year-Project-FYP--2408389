import pandas as pd
import numpy as np
import time
import requests
NEWSAPI_KEY = "eeaa3ad47b384cb793bb0ca38185b181"


def get_news(date):
    """
    Get top 10 finance-related news headlines for a given date
    """
    url = f"https://newsapi.org/v2/everything?q=finance OR stock market OR economy&from={date}&to={date}&language=en&sortBy=publishedAt&apiKey={NEWSAPI_KEY}"

    try:
        response = requests.get(url)
        data = response.json()

        articles = data.get("articles", [])
        headlines = []

        for article in articles:
            title = article.get("title", "").replace(",", "")
            headlines.append(title)

        # ensure exactly 10 columns
        while len(headlines) < 10:
            headlines.append(None)

        return headlines[:10]

    except Exception as e:
        print(f"Error on {date}: {e}")
        return [None] * 10


def generate_news_file():
    """
    Store daily news headlines into CSV
    """
    start = "2025-03-16"
    end = "2026-04-17"

    dates = pd.date_range(start=start, end=end)

    all_data = []

    for date in dates:
        date_str = date.strftime("%Y-%m-%d")
        print(f"Fetching news for {date_str}...")

        headlines = get_news(date_str)

        row = [date_str] + headlines
        all_data.append(row)

        time.sleep(1)  # avoid rate limits

    columns = ["Date"] + [f"News {i+1}" for i in range(10)]
    df = pd.DataFrame(all_data, columns=columns)

    df.to_csv("data/news.csv", index=False)
    print("Saved data/news.csv")


# run
generate_news_file()