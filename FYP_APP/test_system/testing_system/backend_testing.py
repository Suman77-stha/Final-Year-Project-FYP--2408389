import os
import sys
import time
import joblib
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

# Append FYP_APP prediction to path to import utils
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRED_DIR = os.path.join(BASE_DIR, 'FYP_APP', 'prediction')
sys.path.append(PRED_DIR)

from utils import download_data, calculate_indicators
from predict_system import train_and_save_models

TICKERS = ["AAPL", "TSLA", "MSFT", "GOOGL", "NVDA", "005930.KS", "ETC-USD", "APG"]
INITIAL_BALANCE = 10000.0

def run_backtest():
    print("Starting AI Backtesting System...")
    
    all_trades = []
    portfolio_history = []
    price_history = {}
    profit_history = {}
    
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=365)
    
    for symbol in TICKERS:
        print(f"\n--- Processing {symbol} ---")
        
        # Load or train model
        model_path = os.path.join(PRED_DIR, f'models/{symbol}_ensemble_model.pkl')
        scaler_path = os.path.join(PRED_DIR, f'models/{symbol}_scaler.pkl')
        features_path = os.path.join(PRED_DIR, f'models/{symbol}_features.pkl')
        
        if not (os.path.exists(model_path) and os.path.exists(scaler_path) and os.path.exists(features_path)):
            print(f"Model missing for {symbol}. Training now...")
            df_raw = download_data(symbol, period="10y")
            train_and_save_models(symbol, df_raw)
            
        ensemble = joblib.load(model_path)
        scaler = joblib.load(scaler_path)
        features_dict = joblib.load(features_path)
        all_features = features_dict['all_features']
        selected_features = features_dict['selected_features']
        
        # Fetch 1.5 year data to cover backtest and indicator warmup
        df = download_data(symbol, period="2y")
        
        if df.empty:
            print(f"No data fetched for {symbol}. Skipping.")
            continue
            
        data = calculate_indicators(df)
        data = data.ffill().bfill()
        
        # Filter for the last 1 year for the backtest
        backtest_data = data[data.index >= pd.to_datetime(start_date)]
        price_history[symbol] = backtest_data['Close']
        
        balance = INITIAL_BALANCE
        shares = 0
        
        for idx, row in backtest_data.iterrows():
            current_price = row['Close']
            
            # Predict
            try:
                X_all = row[all_features].values.reshape(1, -1)
                X_scaled = scaler.transform(X_all)
                df_scaled = pd.DataFrame(X_scaled, columns=all_features)
                X_selected = df_scaled[selected_features].values
                
                pred_return = ensemble.predict(X_selected)[0]
                predicted_target = current_price * (1 + pred_return)
                trend_bullish = predicted_target > current_price
                accuracy = 80  # Mocked average accuracy since MAPE is calculated on test set
            except Exception as e:
                trend_bullish = False
                accuracy = 0
                
            rsi = row.get("RSI", 50)
            macd = row.get("MACD", 0)
            macd_bullish = macd > 0
            
            user_has_stock = shares > 0
            action = "HOLD"
            
            if not user_has_stock:
                if trend_bullish and rsi < 70 and macd_bullish:
                    action = "BUY"
                elif trend_bullish and accuracy > 50 and rsi < 70:
                    action = "BUY"
            else:
                if not trend_bullish and rsi > 70 and not macd_bullish:
                    action = "SELL"
                elif not trend_bullish and accuracy > 50 and not macd_bullish:
                    action = "SELL"
                    
            # Execute Trade
            if action == "BUY" and balance >= current_price:
                qty = balance // current_price
                if qty > 0:
                    shares += qty
                    balance -= qty * current_price
                    all_trades.append({
                        'Date': idx,
                        'Symbol': symbol,
                        'Action': 'BUY',
                        'Price': current_price,
                        'Shares': qty,
                        'Value': qty * current_price,
                        'Balance': balance
                    })
            elif action == "SELL" and shares > 0:
                value = shares * current_price
                balance += value
                all_trades.append({
                    'Date': idx,
                    'Symbol': symbol,
                    'Action': 'SELL',
                    'Price': current_price,
                    'Shares': shares,
                    'Value': value,
                    'Balance': balance
                })
                shares = 0
                
            portfolio_value = balance + (shares * current_price)
            portfolio_history.append({
                'Date': idx,
                'Symbol': symbol,
                'Portfolio_Value': portfolio_value
            })
            
        # Sell remaining shares at end of backtest
        if shares > 0:
            final_price = backtest_data.iloc[-1]['Close']
            value = shares * final_price
            balance += value
            all_trades.append({
                'Date': backtest_data.index[-1],
                'Symbol': symbol,
                'Action': 'SELL (End of Test)',
                'Price': final_price,
                'Shares': shares,
                'Value': value,
                'Balance': balance
            })
            shares = 0
            
        final_value = balance
        profit = final_value - INITIAL_BALANCE
        profit_history[symbol] = profit
        print(f"{symbol} Final Value: ${final_value:.2f} (Profit: ${profit:.2f})")

    if not all_trades:
        print("No trades were made.")
        return
        
    trades_df = pd.DataFrame(all_trades)
    
    # Save CSV
    output_csv = os.path.join(os.path.dirname(__file__), 'backtest_results.csv')
    trades_df.to_csv(output_csv, index=False)
    print(f"Trades saved to {output_csv}")
    
    # Process portfolio history
    history_df = pd.DataFrame(portfolio_history)
    pivot_df = history_df.pivot(index='Date', columns='Symbol', values='Portfolio_Value')
    pivot_df['Total_Portfolio_Value'] = pivot_df.sum(axis=1)
    
    # Plot
    plt.figure(figsize=(14, 7))
    for symbol in TICKERS:
        if symbol in pivot_df.columns:
            plt.plot(pivot_df.index, pivot_df[symbol], label=f'{symbol}')
            
    plt.plot(pivot_df.index, pivot_df['Total_Portfolio_Value'], label='Total Portfolio', linewidth=3, color='black', linestyle='--')
    
    plt.title('AI Backtesting 1-Year Portfolio Value')
    plt.xlabel('Date')
    plt.ylabel('Value ($)')
    plt.legend()
    plt.grid(True)
    
    output_png = os.path.join(os.path.dirname(__file__), 'pnl_chart.png')
    plt.savefig(output_png)
    plt.close()
    print(f"Chart saved to {output_png}")
    
    # 2. Plot individual stock prices with Buy/Sell markers
    fig, axes = plt.subplots(4, 2, figsize=(20, 24))
    axes = axes.flatten()
    
    for i, symbol in enumerate(TICKERS):
        ax = axes[i]
        if symbol in price_history:
            # Plot price line
            ax.plot(price_history[symbol].index, price_history[symbol].values, label='Price', color='blue', alpha=0.6)
            
            # Get trades for this symbol
            symbol_trades = trades_df[trades_df['Symbol'] == symbol]
            
            buys = symbol_trades[symbol_trades['Action'] == 'BUY']
            sells = symbol_trades[symbol_trades['Action'].str.contains('SELL')]
            
            # Overlay buy/sell markers
            if not buys.empty:
                ax.scatter(buys['Date'], buys['Price'], marker='^', color='green', s=150, label='Buy', zorder=5)
            if not sells.empty:
                ax.scatter(sells['Date'], sells['Price'], marker='v', color='red', s=150, label='Sell', zorder=5)
                
            prof = profit_history.get(symbol, 0)
            status = "Gain" if prof >= 0 else "Loss"
            color = "green" if prof >= 0 else "red"
            
            ax.set_title(f'{symbol} - 1 Year Activity\nInvested: ${INITIAL_BALANCE:,.2f} | {status}: ${abs(prof):,.2f} (Final: ${INITIAL_BALANCE+prof:,.2f})', fontsize=14)
            ax.set_ylabel('Price ($)')
            ax.grid(True, alpha=0.3)
            ax.legend()
            
    plt.tight_layout()
    output_trades_png = os.path.join(os.path.dirname(__file__), 'trades_activity_chart.png')
    plt.savefig(output_trades_png)
    plt.close()
    print(f"Trades activity chart saved to {output_trades_png}")

    
if __name__ == "__main__":
    run_backtest()
