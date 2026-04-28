# import pandas as pd
# import torch
# from transformers import AutoTokenizer, AutoModelForSequenceClassification

# def load_model():
#     tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
#     model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")
#     return tokenizer, model

# def get_sentiment(text, tokenizer, model):
#     inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
#     outputs = model(**inputs)

#     probs = torch.nn.functional.softmax(outputs.logits, dim=1)
#     return probs[0][2].item() - probs[0][0].item()

# def run_sentiment():
#     df = pd.read_csv("news_cleaned.csv")   # ✅ UPDATED

#     tokenizer, model = load_model()

#     df['sentiment'] = df['headline'].apply(
#         lambda x: get_sentiment(x, tokenizer, model)
#     )

#     daily = df.groupby('date')['sentiment'].mean().reset_index()
#     daily.to_csv("sentiment_data.csv", index=False)

#     print("Sentiment done ✅")

# if __name__ == "__main__":
#     run_sentiment()
import pandas as pd
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# ===================== LOAD FINBERT =====================
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")


def get_sentiment(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    outputs = model(**inputs)

    probs = torch.nn.functional.softmax(outputs.logits, dim=1)

    # positive - negative score
    return probs[0][2].item() - probs[0][0].item()


# ===================== SENTIMENT PER SYMBOL =====================
def run_sentiment(symbol="AAPL"):
    print("Loading file...")
    df = pd.read_csv(f"data/processed/{symbol}_news_cleaned.csv")
    print("File loaded ✅")

    df = df.dropna(subset=["headline"])
    df["headline"] = df["headline"].astype(str)
    df = df[df["headline"].str.strip() != ""]

    df["sentiment"] = df["headline"].apply(get_sentiment)

    daily = df.groupby("date")["sentiment"].mean().reset_index()

    daily.to_csv(f"data/processed/{symbol}_sentiment_data.csv", index=False)

    print("Sentiment computed ✅")


if __name__ == "__main__":
    run_sentiment()