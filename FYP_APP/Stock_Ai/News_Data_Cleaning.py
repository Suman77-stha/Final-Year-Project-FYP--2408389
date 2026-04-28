import pandas as pd
import os

BASE_DIR = "data"

news_path = os.path.join(BASE_DIR, "news_data.csv")
stock_path = os.path.join(BASE_DIR, "stock_price.csv")

    
news_df = pd.read_csv(news_path)
stock_df = pd.read_csv(stock_path)

for i in range(len(stock_df)):
    date = stock_df['Date'][i][:10]
    stock_df['Date'][i] = date

news_df = news_df[news_df['Date'].isin(stock_df['Date'].tolist())]

news_df.to_csv("cleaned_news_data.csv", index=False)