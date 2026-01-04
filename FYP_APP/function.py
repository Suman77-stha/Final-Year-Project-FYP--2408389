from django.http import JsonResponse
from FYP_APP.models import New_Stock_Data


# def stock_data_from_api(symbol):
#     """
#     Fetch stock data from Finnhub API and return JSON.
#     This function can be called directly from urls.py.
#     """
#     import requests
#     import datetime,pytz
#     from django.conf import settings
    

#     try:
#         # Call Finnhub API
#         response = requests.get("https://finnhub.io/api/v1/quote",params={"symbol": symbol, "token": settings.FINNHUB_API_KEY})
#         response.raise_for_status()
#         data = response.json()
#         print(data)
#         if data and data.get('t'):
#             timestamp = data['t']
#             # converting Unix timestamp to date
#             utc_dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
#             nepal_dt = utc_dt.astimezone(pytz.timezone("Asia/Kathmandu"))
#             if  not New_Stock_Data.objects.filter(symbol=symbol , nepal_dt=nepal_dt.date()).exists():
#                 stock = New_Stock_Data.objects.create(
#                     symbol = symbol,
#                     utc_dt = utc_dt.date(),
#                     nepal_dt = nepal_dt.date(),
#                     open_price=data['o'],
#                     high_price=data['h'],
#                     low_price=data['l'],
#                     close_price=data['c'],
#                     change=data['d'],
#                     volume = 0,
#                     change_percent=data['dp']
#                     )
#                 stock.save()
#                 # Print to terminal
#                 print(f"new data of Stock with different symbol or date for {symbol}: {data}")    
#             else:
#                 print("Data already exist in database")
#         else:
#             print("No valid data from API")
#             return None
#         return (nepal_dt.date())
#     except requests.RequestException as e:
#         print(f"Error fetching stock data: {e}")
#         return None
    
# def stock_data_from_database(nepal_dt,symbol):
#     """
#     Fetch stock data from database and return JSON.
#     This function can be called directly from urls.py.
#     """
#     stock_data = (
#         New_Stock_Data.objects.filter(symbol=symbol, nepal_dt=nepal_dt).order_by("-nepal_dt").first()
#     )
           
#     if stock_data:
#         print("Data exist")
#         return ({
#             "symbol": stock_data.symbol,
#             "date": stock_data.nepal_dt,
#             "open": stock_data.open_price,
#             "high": stock_data.high_price,
#             "low": stock_data.low_price,
#             "close": stock_data.close_price,
#             "change": stock_data.change,
#             "change_percent": float(stock_data.change_percent),
#             "source": "database"
#         })
#     return None
from django.shortcuts import render, redirect
from django.conf import settings
import requests
import datetime
import pytz
from FYP_APP.models import New_Stock_Data, Watchlist, Transaction, Wallet
def view(request):
    search_symbol = request.GET.get('symbol', 'BTC')

    # ------------------------------
    # 2️⃣ Fetch real-time stock data from Finnhub API
    # ------------------------------
    try:
        response = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": search_symbol, "token": settings.FINNHUB_API_KEY}
        )
        response.raise_for_status()
        api_data = response.json()
    except Exception as e:
        api_data = None
        print("Error fetching API:", e)

    # ------------------------------
    # 3️⃣ Convert timestamp to UTC & Nepal time
    # ------------------------------
    nepal_dt = None
    if api_data and api_data.get('t'):
        timestamp = api_data['t']
        utc_dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
        nepal_dt = utc_dt.astimezone(pytz.timezone("Asia/Kathmandu"))

        # ------------------------------
        # 4️⃣ Save new stock data if today's data doesn't exist
        # ------------------------------
        if not New_Stock_Data.objects.filter(symbol=search_symbol, nepal_dt=nepal_dt.date()).exists():
            stock=New_Stock_Data.objects.create(
                symbol=search_symbol,
                utc_dt=utc_dt.date(),
                nepal_dt=nepal_dt.date(),
                open_price=api_data.get('o', 0),
                high_price=api_data.get('h', 0),
                low_price=api_data.get('l', 0),
                close_price=api_data.get('c', 0),
                change=api_data.get('d', 0),
                volume=0,
                change_percent=api_data.get('dp', 0)
            )
            stock.save()
            print(stock)

    # ------------------------------
    # 5️⃣ User Watchlist & stock_dict
    # ------------------------------
    stock_dict = {}
    user_watchlist = []

    if request.user.is_authenticated:
        # Auto-add searched symbol to watchlist if not exists
        if nepal_dt:  # Only if API returned valid data
            watch_list=Watchlist.objects.create(
                user=request.user,
                symbol=search_symbol,
                defaults={
                    'nepal_dt': nepal_dt.date(),
                    'close_price': api_data.get('c', 0),
                    'change': api_data.get('d', 0),
                }
            )
            watch_list.save()

        # Fetch full watchlist
        user_watchlist_qs = Watchlist.objects.filter(user=request.user).order_by('-nepal_dt')
        user_watchlist = user_watchlist_qs

        # Fetch all historical stock data for watchlist symbols
        for symbol in user_watchlist:
            all_stocks = New_Stock_Data.objects.filter(symbol=symbol).order_by('-nepal_dt')
            stock_dict[symbol] = list(all_stocks)

    # ------------------------------
    # 6️⃣ Recent search symbols for autocomplete
    # ------------------------------
    recent_symbols = New_Stock_Data.objects.values_list('symbol', flat=True).distinct()[:10]

    # ------------------------------
    # 7️⃣ User transactions (only BUY for dashboard cards)
    # ------------------------------
    user_transactions = []
    if request.user.is_authenticated:
        user_transactions = Transaction.objects.filter(
            user=request.user,
            transaction_type='BUY'
        ).order_by('-created_at')

    # ------------------------------
    # 8️⃣ User wallet (create if not exists)
    # ------------------------------
    wallet = None
    if request.user.is_authenticated:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)

    # ------------------------------
    # 9️⃣ Handle Buy/Sell POST actions
    # ------------------------------
    if request.method == "POST" and request.user.is_authenticated:
        action = request.POST.get('action')
        symbol = request.POST.get('symbol')
        quantity = int(request.POST.get('quantity', 1))

        latest_stock = New_Stock_Data.objects.filter(symbol=symbol).order_by('-nepal_dt').first()
        if latest_stock:
            price = latest_stock.close_price

            if action == "buy":
                total_cost = price * quantity
                if wallet.balance >= total_cost:
                    Transaction.objects.create(
                        user=request.user,
                        symbol=symbol,
                        price=price,
                        quantity=quantity,
                        transaction_type="BUY"
                    )
                    wallet.balance -= total_cost
                    wallet.save()

            elif action == "sell":
                buy_transactions = Transaction.objects.filter(
                    user=request.user,
                    symbol=symbol,
                    transaction_type="BUY"
                )
                total_bought_qty = sum(t.quantity for t in buy_transactions)
                total_sold_qty = sum(t.quantity for t in Transaction.objects.filter(
                    user=request.user,
                    symbol=symbol,
                    transaction_type="SELL"
                ))
                available_qty = total_bought_qty - total_sold_qty

                if available_qty >= quantity:
                    Transaction.objects.create(
                        user=request.user,
                        symbol=symbol,
                        price=price,
                        quantity=quantity,
                        transaction_type="SELL"
                    )
                    wallet.balance += price * quantity
                    wallet.save()

        return redirect("dashboard")

    # ------------------------------
    # 10️⃣ Prepare context for template
    # ------------------------------
    context = {
        'data': stock_dict,
        'recent_symbols': recent_symbols,
        'watchlist': user_watchlist,
        'transactions': user_transactions,
        'wallet': wallet,
    }
 





