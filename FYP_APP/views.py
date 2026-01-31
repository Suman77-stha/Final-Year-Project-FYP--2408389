from datetime import date
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone



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

# views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Sum
from django.conf import settings

import json
import datetime
import pytz
import requests

from .models import New_Stock_Data, Watchlist, Transaction, Wallet
from .function import get_lstm_graph


@login_required(login_url='Sign_In')
def dashboard_view(request):

    # ---------------- SYMBOL & PERIOD ----------------
    search_symbol = request.GET.get('symbol', 'BTC').upper()
    period = request.GET.get('period', '1y')

    PERIOD_MAP = {
        "1w": 7,
        "2w": 14,
        "3w": 21,
        "1m": 30,
        "3m": 90,
        "5m": 150,
        "1y": 365,
    }

    future_days = PERIOD_MAP.get(period, 30)

    api_data = {}
    nepal_dt = None

    # ---------------- FETCH LIVE PRICE ----------------
    try:
        response = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={
                "symbol": search_symbol,
                "token": settings.FINNHUB_API_KEY
            },
            timeout=10
        )
        response.raise_for_status()
        api_data = response.json()
    except Exception as e:
        print("API error:", e)

    # ---------------- SAVE STOCK DATA ----------------
    if api_data.get("t"):
        utc_dt = datetime.datetime.utcfromtimestamp(
            api_data["t"]
        ).replace(tzinfo=pytz.utc)

        nepal_dt = utc_dt.astimezone(
            pytz.timezone("Asia/Kathmandu")
        )

        New_Stock_Data.objects.update_or_create(
            symbol=search_symbol,
            nepal_dt=nepal_dt.date(),
            defaults={
                "utc_dt": utc_dt.date(),
                "open_price": api_data.get("o", 0),
                "high_price": api_data.get("h", 0),
                "low_price": api_data.get("l", 0),
                "close_price": api_data.get("c", 0),
                "change": api_data.get("d", 0),
                "change_percent": api_data.get("dp", 0),
                "volume": 0,
            }
        )

    # ---------------- WATCHLIST ----------------
    stock_dict = {}

    if nepal_dt:
        Watchlist.objects.update_or_create(
            user=request.user,
            symbol=search_symbol,
            defaults={
                "nepal_dt": nepal_dt.date(),
                "close_price": api_data.get("c", 0),
                "change": api_data.get("d", 0),
            }
        )

        watchlist = Watchlist.objects.filter(
            user=request.user
        ).order_by("-added_at")[:5]

        for wl in watchlist:
            latest = New_Stock_Data.objects.filter(
                symbol=wl.symbol
            ).order_by("-nepal_dt").first()

            if latest:
                stock_dict[wl.symbol] = latest

    # ---------------- WALLET & TRANSACTIONS ----------------
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    user_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by("-created_at")

    # ---------------- BUY / SELL ----------------
    if request.method == "POST":
        action = request.POST.get("action")
        symbol = request.POST.get("symbol")
        quantity = int(request.POST.get("quantity", 1))

        latest_stock = New_Stock_Data.objects.filter(
            symbol=symbol
        ).order_by("-nepal_dt").first()

        if latest_stock:
            price = latest_stock.close_price

            if action == "buy" and wallet.balance >= price * quantity:
                Transaction.objects.create(
                    user=request.user,
                    symbol=symbol,
                    price=price,
                    quantity=quantity,
                    transaction_type="BUY",
                )
                wallet.balance -= price * quantity
                wallet.save()

            elif action == "sell":
                bought = Transaction.objects.filter(
                    user=request.user,
                    symbol=symbol,
                    transaction_type="BUY",
                ).aggregate(total=Sum("quantity"))["total"] or 0

                sold = Transaction.objects.filter(
                    user=request.user,
                    symbol=symbol,
                    transaction_type="SELL",
                ).aggregate(total=Sum("quantity"))["total"] or 0

                if bought - sold >= quantity:
                    Transaction.objects.create(
                        user=request.user,
                        symbol=symbol,
                        price=price,
                        quantity=quantity,
                        transaction_type="SELL",
                    )
                    wallet.balance += price * quantity
                    wallet.save()

        return redirect("dashboard")

    # ---------------- LSTM GRAPH DATA ----------------
    lstm_graph_data = {}

    try:
        lstm_graph_data = get_lstm_graph(
            symbol=search_symbol,
            future_days=future_days
        )
        print("LSTM graph generated")
    except Exception as e:
        print("LSTM Graph Error:", e)

    # ---------------- CONTEXT ----------------
    context = {
        "data": stock_dict,
        "wallet": wallet,
        "transactions": user_transactions,
        "recent_symbols": New_Stock_Data.objects.values_list(
            "symbol", flat=True
        ).distinct()[:10],
        "lstm_graph_data": json.dumps(lstm_graph_data or {}),
        "current_period": period,
        "current_symbol": search_symbol,
    }

    return render(request, "dashboard.html", context)




# ---------------- LOGOUT ----------------
def logout_view(request):
    logout(request)
    return redirect('Sign_In')
