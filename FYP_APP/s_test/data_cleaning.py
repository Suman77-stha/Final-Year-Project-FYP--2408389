import pandas as pd
import os

# Create directory if it doesn't exist
os.makedirs("data/processed", exist_ok=True)


# ===================== CLEAN STOCK DATA =====================
def clean_stock_data(symbol):
    df = pd.read_csv(f"data/raw/{symbol}_stock_data.csv", low_memory=False)

    df.drop_duplicates(inplace=True)

    # Convert Close to numeric safely
    df['Close'] = pd.to_numeric(df['Close'], errors='coerce')

    # Fill missing values
    df.ffill(inplace=True)

    # Remove invalid prices
    df = df[df['Close'] > 0]

    # Fix date
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date

    df.to_csv(f"data/processed/{symbol}_stock_cleaned.csv", index=False)
    print("Stock cleaned ✅")


# ===================== CLEAN NEWS DATA =====================
def clean_news_data(symbol):
    df = pd.read_csv(f"data/raw/{symbol}_news_data.csv")

    df.drop_duplicates(subset=['headline'], inplace=True)
    df.dropna(subset=['headline'], inplace=True)

    df = df[df['headline'].str.len() > 20]

    df['headline'] = df['headline'].str.replace(r'[^a-zA-Z0-9 ]', '', regex=True)

    df['date'] = pd.to_datetime(df['date']).dt.date

    df.to_csv(f"data/processed/{symbol}_news_cleaned.csv", index=False)

    print("News cleaned ✅")




# ===================== MAIN =====================
if __name__ == "__main__":
    clean_stock_data("AAPL")
    clean_news_data("AAPL")