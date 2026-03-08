import matplotlib.pyplot as plt
import os
import uuid
import pandas as pd

# from lstm_model import predict_stock_price
def plot_stock_prediction(prediction_result):
    """
    Plots historical stock prices and future 7-day predictions.

    Args:
        prediction_result (dict): Output from predict_stock_price()

    Returns:
        image_path (str): Path to the saved plot image
    """
    symbol = prediction_result["symbol"]
    actual_prices = prediction_result["close_prices"].tolist()
    future_prices = prediction_result["future_days"]

    # Generate dates for historical data
    actual_dates = pd.date_range(
        end=pd.Timestamp.today(), periods=len(actual_prices)
    ).tolist()

    # Generate dates for future predictions
    future_dates = pd.date_range(
        start=actual_dates[-1] + pd.Timedelta(days=1),
        periods=len(future_prices)
    ).tolist()

    # Plotting
    plt.figure(figsize=(12,6))
    plt.plot(actual_dates, actual_prices, label="Historical Prices", color="blue")
    plt.plot(future_dates, future_prices, label="Future 7-Day Prediction", color="red", linestyle="--", marker="o")
    
    plt.title(f"{symbol} Stock Price Prediction")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()

    # Save the plot
    filename = f"{symbol}_prediction_{uuid.uuid4().hex}.png"
    image_path = os.path.join("media", "plots", filename)
    os.makedirs(os.path.dirname(image_path), exist_ok=True)

    plt.tight_layout()
    plt.savefig(image_path)
    plt.close()
    print(image_path)

    return image_path
