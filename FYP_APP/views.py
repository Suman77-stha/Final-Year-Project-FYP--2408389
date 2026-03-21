from datetime import date
from django.contrib import messages
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from requests import request
from decimal import Decimal
from django.db.models.functions import TruncMonth
from .APS.lstm_model import predict_stock_price
from .models import CustomUserCreationForm, New_Stock_Data, Watchlist, Transaction, Wallet, Portfolio
from .APS.StockAPI import get_stock_data
from django.core.cache import cache
import datetime
import pytz
from django.db.models import Sum

# ---------------- FORGOT PASSWORD ----------------
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            reset_link = f"http://127.0.0.1:8000/FYP/password-reset-confirm/{user.username}/"
            send_mail(
                'Password Reset Request',
                f'Hi {user.username},\n\nClick the link below:\n{reset_link}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False
            )
            return redirect('password_reset_done')
        return render(request, 'forgetPassword.html', {'error': 'Email not found'})
    return render(request, 'forgetPassword.html')


# ---------------- PASSWORD RESET CONFIRM ----------------
def password_reset_confirm(request, user):
    try:
        userid = User.objects.get(username=user)
    except User.DoesNotExist:
        return redirect('Sign_In')

    if request.method == "POST":
        pass1 = request.POST.get("password1")
        pass2 = request.POST.get("password2")
        if pass1 == pass2:
            userid.set_password(pass1)
            userid.save()
            return redirect('password_reset_complete')
        return render(request, 'password_reset_confirm.html', {'error': 'Passwords do not match'})

    return render(request, 'password_reset_confirm.html', {'username': user})


# ---------------- PASSWORD RESET COMPLETE ----------------
def password_reset_complete_view(request):
    return render(request, 'password_reset_complete.html')


# ---------------- SIGN UP VIEW ----------------
def SignUp_View(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            username = request.POST.get("username")
            email = request.POST.get("email")

            if User.objects.filter(username=username).exists():
                return render(request, 'Sign_Up.html', {'form': form, 'error': 'Username already exists'})
            if User.objects.filter(email=email).exists():
                return render(request, 'Sign_Up.html', {'form': form, 'error': 'Email already exists'})

            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()

    return render(request, 'Sign_Up.html', {'form': form})

# ---------------- SIGN IN VIEW ----------------
def Sign_In_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'Sign_In.html', {'form': form})


def landing_page_view(request):
    return render(request, 'Landing_page.html')

def about_view(request):
    return render(request, 'About.html')

def wallet_view(request):
    return render(request, 'Wallet.html')
def AI_Assistance_view(request):
    return render(request, 'AI_Assistance.html')



@login_required(login_url='Sign_In')
def dashboard_view(request):

    # ---------------- SYMBOL & PERIOD ----------------
    search_symbol = request.GET.get('symbol', 'AAPL').upper()
    period = request.GET.get('period', '1y')

    nepal_tz = pytz.timezone("Asia/Kathmandu")
    today = datetime.datetime.now(nepal_tz).date()

    cache_key = f"stock_{search_symbol}_{today}"

    # ---------------- STOCK DATA (CACHED) ----------------
    stock_data = cache.get(cache_key)

    if not stock_data:
        stock_data = New_Stock_Data.objects.filter(
            symbol=search_symbol,
            nepal_dt=today
        ).first()

        if not stock_data:
            api_data = get_stock_data(search_symbol)

            if api_data:
                stock_data = New_Stock_Data.objects.create(
                    symbol=api_data['symbol'],
                    CompanyName=api_data['CompanyName'],
                    Currency=api_data['Currency'],
                    nepal_dt=api_data['nepal_dt'],
                    utc_dt=api_data['utc_dt'],
                    open_price=api_data['open_price'],
                    high_price=api_data['high_price'],
                    low_price=api_data['low_price'],
                    close_price=api_data['close_price'],
                    volume=api_data['volume'],
                    change=api_data['change'],
                )

        if stock_data:
            cache.set(cache_key, stock_data, timeout=60 * 60 * 6)

    # ---------------- WATCHLIST ----------------
    watchlist_cache_key = f"watchlist_{request.user}"

    Watchdata = cache.get(watchlist_cache_key)

    if not Watchdata:
        Watchdata = list(
            Watchlist.objects.filter(user=request.user)
            .order_by("-added_at")[:5]
        )

        cache.set(watchlist_cache_key, Watchdata, timeout=60 * 10)

    # ---------------- UPDATE WATCHLIST ----------------
    if stock_data:

        watchlist_entry, created = Watchlist.objects.update_or_create(
            user=request.user,
            symbol=stock_data.symbol,
            defaults={
                "nepal_dt": stock_data.nepal_dt,
                "CompanyName": stock_data.CompanyName,
                "Currency": stock_data.Currency,
                "close_price": stock_data.close_price,
                "volume": stock_data.volume,
                "change": stock_data.change,
            }
        )

        if watchlist_entry in Watchdata:
            Watchdata.remove(watchlist_entry)

        Watchdata.insert(0, watchlist_entry)

        if len(Watchdata) > 5:
            Watchdata.pop()

        cache.set(watchlist_cache_key, Watchdata, timeout=60 * 10)

    # ---------------- WALLET ----------------
    wallet, created = Wallet.objects.get_or_create(
        user=request.user,
        defaults={'balance': Decimal("100000")}
    )

    # ---------------- BUY / SELL LOGIC ----------------
    if request.method == "POST":

        symbol = request.POST.get("symbol")
        price = Decimal(request.POST.get("price"))
        quantity = int(request.POST.get("quantity"))
        action = request.POST.get("action")

        total = price * quantity

        if action == "buy":

            if wallet.balance >= total:

                wallet.balance -= total
                wallet.save()

                portfolio, created = Portfolio.objects.get_or_create(
                    user=request.user,
                    symbol=symbol,
                    defaults={'quantity': 0, 'avg_price': price}
                )

                portfolio.quantity += quantity
                portfolio.avg_price = price
                portfolio.save()

                Transaction.objects.create(
                    user=request.user,
                    symbol=symbol,
                    transaction_type="BUY",
                    price=price,
                    quantity=quantity,
                    total=total
                )

                messages.success(request, "Stock bought successfully")

            else:
                messages.error(request, "Insufficient balance")

        elif action == "sell":

            portfolio = Portfolio.objects.filter(
                user=request.user,
                symbol=symbol
            ).first()

            if portfolio and portfolio.quantity >= quantity:

                portfolio.quantity -= quantity
                portfolio.save()

                wallet.balance += total
                wallet.save()

                Transaction.objects.create(
                    user=request.user,
                    symbol=symbol,
                    transaction_type="SELL",
                    price=price,
                    quantity=quantity,
                    total=total
                )

                messages.success(request, "Stock sold successfully")

            else:
                messages.error(request, "Not enough shares to sell")

    # ---------------- PORTFOLIO ----------------
    portfolio = Portfolio.objects.filter(user=request.user)

    trades = Transaction.objects.filter(
        user=request.user
    ).order_by("-created_at")[:10]

    # ---------------- EXTRA DATA FOR TEMPLATE ----------------

    today_investment = Transaction.objects.filter(
        user=request.user,
        transaction_type="BUY",
        created_at__date=today
    ).aggregate(total=models.Sum("total"))["total"] or 0

    closing_balance = wallet.balance

    recent_symbols = Watchlist.objects.filter(
        user=request.user
    ).values_list("symbol", flat=True).distinct()[:10]
    # ---------------- PORTFOLIO CALCULATION (NEW) ---------------- #

    portfolio_data = []
    total_invested = 0
    total_current = 0
    total_profit = 0
    
    for p in portfolio:
    
        stock_info = get_stock_data(p.symbol)
    
        if stock_info:
            current_price = Decimal(str(stock_info["close_price"]))
        else:
            current_price = Decimal("0")
    
        invested = p.avg_price * p.quantity
        current_value = current_price * p.quantity
        profit = current_value - invested
    
        total_invested += invested
        total_current += current_value
        total_profit += profit
    
        portfolio_data.append({
            "symbol": p.symbol,
            "quantity": p.quantity,
            "avg_price": float(p.avg_price),
            "current_price": float(current_price),
            "invested": float(invested),
            "current_value": float(current_value),
            "profit": float(profit)
        })
    
    # ---------------- CONTEXT ----------------
    context = {
        "stock_data": stock_data,
        "Watchdata": Watchdata,
        "symbol": search_symbol,
        "period": period,
        "wallet": wallet,
        "portfolio": portfolio,
        "trades": trades,
        "today_investment": today_investment,
        "closing_balance": closing_balance,
        "recent_symbols": recent_symbols,
        "portfolio_data": portfolio_data,
    }

    return render(request, "dashboard.html", context)


@login_required
def wallet_view(request):

    user = request.user

    # ---------------- WALLET ---------------- #

    wallet, created = Wallet.objects.get_or_create(user=user)

    balance = wallet.balance


    # ---------------- TODAY TRANSACTIONS ---------------- #

    today = timezone.now().date()

    today_transactions = Transaction.objects.filter(
        user=user,
        created_at__date=today
    )

    today_income = today_transactions.filter(
        transaction_type="SELL"
    ).aggregate(total=Sum("total"))["total"] or 0

    today_expense = today_transactions.filter(
        transaction_type="BUY"
    ).aggregate(total=Sum("total"))["total"] or 0


    # ---------------- RECENT TRANSACTIONS ---------------- #

    recent_transactions = Transaction.objects.filter(
        user=user
    ).order_by("-created_at")[:10]


    # ---------------- RECENT SEARCH SYMBOLS ---------------- #

    recent_symbols = Watchlist.objects.filter(
        user=user
    ).values_list("symbol", flat=True)[:10]


    # ---------------- DONUT CHART DATA ---------------- #

    buy_total = Transaction.objects.filter(
        user=user,
        transaction_type="BUY"
    ).aggregate(total=Sum("total"))["total"] or 0

    sell_total = Transaction.objects.filter(
        user=user,
        transaction_type="SELL"
    ).aggregate(total=Sum("total"))["total"] or 0


    # ---------------- CONTEXT ---------------- #

    context = {
        "balance": balance,
        "today_income": today_income,
        "today_expense": today_expense,
        "recent_transactions": recent_transactions,
        "recent_symbols": recent_symbols,
        "buy_total": buy_total,
        "sell_total": sell_total,
    }

    return render(request, "Wallet.html", context)
    
@login_required
def get_live_price(request):

    symbol = request.GET.get("symbol")

    if not symbol:
        return JsonResponse({"price": None})

    data = get_stock_data(symbol.upper())

    if data:
        return JsonResponse({
            "price": data["close_price"]
        })

    return JsonResponse({"price": None})

def stock_prediction_api(request):

    symbol = request.GET.get("symbol", "TSLA")
    range_param = request.GET.get("range", "7D")

    # Map UI ranges → days
    range_map = {
        "7D": 7,
        "1W": 7,
        "7W": 49,
        "1M": 30,
        "5M": 150,
        "1Y": 365
    }

    period = range_map.get(range_param, 7)

    result = predict_stock_price(symbol, period)

    #  IMPORTANT CHANGE (dynamic history)
    history_length = min(len(result["close_prices"]), 60)

    close_prices = result["close_prices"][-history_length:]
    future_prices = result["future_days"]

    history_labels = [f"D{i}" for i in range(len(close_prices))]
    future_labels = [f"F{i+1}" for i in range(len(future_prices))]

    data = {
        "symbol": symbol,
        "history_labels": history_labels,
        "future_labels": future_labels,
        "close_prices": close_prices,
        "future_prices": future_prices,
        "accuracy": result["accuracy"],
        "current_price": result["current_price"]
    }

    return JsonResponse(data)


@login_required
def profit_loss_api(request):

    user = request.user

    data = (
        Transaction.objects.filter(user=user)
        .annotate(month=TruncMonth("created_at"))
        .values("month", "transaction_type")
        .annotate(total=Sum("total"))
        .order_by("month")
    )

    monthly = {}

    for item in data:
        month = item["month"].strftime("%b")

        if month not in monthly:
            monthly[month] = 0

        if item["transaction_type"] == "BUY":
            monthly[month] -= float(item["total"])
        else:
            monthly[month] += float(item["total"])

    return JsonResponse({
        "labels": list(monthly.keys())[-6:],  # last 6 months
        "data": list(monthly.values())[-6:]
    })

# ---------------- LOGOUT ----------------
def logout_view(request):
    logout(request)
    return redirect('Sign_In')

@login_required
def stock_6month_api(request):

    import yfinance as yf

    symbol = request.GET.get("symbol", "AAPL")

    stock = yf.Ticker(symbol)
    hist = stock.history(period="6mo")

    labels = [d.strftime("%b") for d in hist.index]
    prices = hist["Close"].fillna(0).tolist()

    return JsonResponse({
        "labels": labels,
        "data": prices
    })
