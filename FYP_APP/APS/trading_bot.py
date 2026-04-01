# trading_bot_functions.py
import time
from decimal import Decimal
from django.db import transaction as db_transaction
from FYP_APP.models import Wallet, Portfolio, Transaction, New_Stock_Data
from django.contrib.auth.models import User

# ---------------- Helper Functions ---------------- #

def get_latest_stock_price(symbol):
    """Fetch the latest close price from New_Stock_Data"""
    stock = New_Stock_Data.objects.filter(symbol=symbol).order_by('-nepal_dt').first()
    if not stock:
        raise ValueError(f"No stock data found for {symbol}")
    return stock.close_price

def buy_stock(user, symbol, quantity, condition_fn):
    """Buy stock if condition is met"""
    wallet = Wallet.objects.get(user=user)

    while True:
        price = get_latest_stock_price(symbol)
        if condition_fn(price):
            total_cost = Decimal(price) * quantity
            if wallet.balance >= total_cost:
                with db_transaction.atomic():
                    # Deduct from wallet
                    wallet.balance -= total_cost
                    wallet.save()

                    # Update portfolio
                    portfolio, created = Portfolio.objects.get_or_create(
                        user=user,
                        symbol=symbol,
                        defaults={'quantity': quantity, 'avg_price': Decimal(price)}
                    )
                    if not created:
                        total_quantity = portfolio.quantity + quantity
                        portfolio.avg_price = ((portfolio.avg_price * portfolio.quantity) + total_cost) / total_quantity
                        portfolio.quantity = total_quantity
                        portfolio.save()

                    # Record transaction
                    Transaction.objects.create(
                        user=user,
                        symbol=symbol,
                        price=Decimal(price),
                        quantity=quantity,
                        total=total_cost,
                        transaction_type=Transaction.BUY
                    )
                print(f"Bought {quantity} of {symbol} at {price} per unit. Total cost: {total_cost}")
                break
            else:
                print("Insufficient balance to buy the stock.")
                break
        else:
            print(f"Condition not met for buying {symbol} at price {price}. Waiting...")
            time.sleep(10)  # Wait before rechecking

def sell_stock(user, symbol, quantity):
    """Sell stock from user's portfolio"""
    wallet = Wallet.objects.get(user=user)
    try:
        portfolio = Portfolio.objects.get(user=user, symbol=symbol)
    except Portfolio.DoesNotExist:
        print("You do not own this stock.")
        return

    if portfolio.quantity < quantity:
        print(f"Insufficient quantity to sell. You have {portfolio.quantity}")
        return

    price = get_latest_stock_price(symbol)
    total_sale = Decimal(price) * quantity

    with db_transaction.atomic():
        # Add to wallet
        wallet.balance += total_sale
        wallet.save()

        # Update portfolio
        portfolio.quantity -= quantity
        if portfolio.quantity == 0:
            portfolio.delete()
        else:
            portfolio.save()

        # Record transaction
        Transaction.objects.create(
            user=user,
            symbol=symbol,
            price=Decimal(price),
            quantity=quantity,
            total=total_sale,
            transaction_type=Transaction.SELL
        )

    print(f"Sold {quantity} of {symbol} at {price} per unit. Total received: {total_sale}")

# ---------------- Example Usage ---------------- #

if __name__ == "__main__":
    import django
    import os
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yourproject.settings")
    django.setup()

    # Replace 'username' with your user
    user = User.objects.get(username="username")

    # Define your buy condition function
    def buy_condition(price):
        # Example: buy if price below 100
        return price < 100

    # Buy example
    buy_stock(user=user, symbol="AAPL", quantity=10, condition_fn=buy_condition)

    # Sell example
    sell_stock(user=user, symbol="AAPL", quantity=5)