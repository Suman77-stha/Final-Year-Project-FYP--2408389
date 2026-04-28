import pandas as pd

def merge_all(symbol="AAPL"):
    stock = pd.read_csv(f"data/processed/{symbol}_stock_cleaned.csv")
    sentiment = pd.read_csv(f"data/processed/{symbol}_sentiment_data.csv")
    lstm = pd.read_csv(f"data/processed/{symbol}_lstm_features.csv")

    stock['Date'] = pd.to_datetime(stock['Date']).dt.date
    sentiment['date'] = pd.to_datetime(sentiment['date']).dt.date
    lstm['Date'] = pd.to_datetime(lstm['Date']).dt.date

    df = pd.merge(stock, sentiment, left_on="Date", right_on="date", how="left")
    df = pd.merge(df, lstm[['Date','lstm_feature']], on="Date", how="left")
    if "Date" in df.columns and "date" in df.columns:
        df.drop(columns=["date"], inplace=True)
        df.rename(columns={"Date": "date"}, inplace=True)

    df['sentiment'].fillna(0, inplace=True)

    # features
    df['return'] = df['Close'].pct_change()
    df['ma7'] = df['Close'].rolling(7).mean()
    df['volatility'] = df['Close'].rolling(7).std()

    df['target'] = df['Close'].shift(-1)

    df.dropna(inplace=True)

    df.to_csv(f"data/processed/{symbol}_final_dataset.csv", index=False)

    print("Merged dataset ready ✅")

if __name__ == "__main__":
    merge_all()