import threading
import logging
from datetime import datetime

class TradingBot:

    def __init__(self, lstm_model, broker_api):
        self.lstm_model = lstm_model
        self.broker_api = broker_api
        self.auto_mode = False
        self.lock = threading.Lock()

    # --------------------------------
    # Predict using existing LSTM
    # --------------------------------
    def predict_stock(self, stock_symbol):
        prediction = self.lstm_model.predict(stock_symbol)
        return f"Predicted price for {stock_symbol} is {prediction}"

    # --------------------------------
    # Detect Trend (Bullish/Bearish)
    # --------------------------------
    def get_trend(self, stock_symbol):
        trend = self.lstm_model.detect_trend(stock_symbol)
        return f"Market trend for {stock_symbol} is {trend}"

    # --------------------------------
    # Execute Trade (Atomic + Secure)
    # --------------------------------
    def execute_trade(self, stock_symbol, action):

        with self.lock:  # Atomic execution

            try:
                price = self.lstm_model.get_current_price(stock_symbol)

                order = self.broker_api.place_order(
                    symbol=stock_symbol,
                    side=action,
                    quantity=1
                )

                self.log_trade(stock_symbol, action, price)

                return f"{action} order executed for {stock_symbol} at {price}"

            except Exception as e:
                return f"Trade failed: {str(e)}"

    # --------------------------------
    # Auto Trading Mode
    # --------------------------------
    def auto_trade(self, stock_symbol):

        self.auto_mode = True

        trend = self.lstm_model.detect_trend(stock_symbol)

        if trend == "Bullish":
            return self.execute_trade(stock_symbol, "BUY")

        elif trend == "Bearish":
            return self.execute_trade(stock_symbol, "SELL")

        return "No trade executed."

    # --------------------------------
    # Trade Logging
    # --------------------------------
    def log_trade(self, symbol, action, price):

        logging.basicConfig(
            filename="trade_logs.txt",
            level=logging.INFO
        )

        logging.info(
            f"{datetime.now()} - {action} - {symbol} - {price}"
        )