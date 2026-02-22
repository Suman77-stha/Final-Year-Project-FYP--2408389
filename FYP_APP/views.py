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
from django.shortcuts import render, redirect
from django.conf import settings

import json
import datetime
import pytz

from .models import CustomUserCreationForm, New_Stock_Data, Watchlist, Transaction, Wallet
from .StockAPI import get_stock_data
from django.core.cache import cache

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
        # Try DB
        stock_data = New_Stock_Data.objects.filter(
            symbol=search_symbol,
            nepal_dt=today
        ).first()

        # If not in DB → call API
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

        # Save in cache (even if from DB)
        if stock_data:
            cache.set(cache_key, stock_data, timeout=60 * 60 * 6)  # 6 hours

    # ---------------- WATCHLIST ----------------
    watchlist_cache_key = f"watchlist_{request.user}"

    Watchdata = cache.get(watchlist_cache_key)

    if not Watchdata:
        Watchdata = list(
            Watchlist.objects.filter(user=request.user)
            .order_by("-added_at")[:5]
        )

        cache.set(watchlist_cache_key, Watchdata, timeout=60 * 10)  # 10 min

    # ================= UPDATE WATCHLIST =================
    if stock_data:
        watchlist_entry, created = Watchlist.objects.update_or_create(
            user=request.user,
            symbol=stock_data.symbol,
            nepal_dt=stock_data.nepal_dt,
            defaults={
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
        if len(Watchdata)>5:
            Watchdata.pop()


        # IMPORTANT: refresh watchlist cache after modification
        cache.set(watchlist_cache_key, Watchdata, timeout=60 * 10)

    context = {
        "stock_data": stock_data,
        "Watchdata": Watchdata,
        "symbol": search_symbol,
        "period": period,
    }
    return render(request, "dashboard.html", context)

    # # ---------------- WALLET & TRANSACTIONS ----------------
    # wallet, _ = Wallet.objects.get_or_create(user=request.user)

    # user_transactions = Transaction.objects.filter(
    #     user=request.user
    # ).order_by("-created_at")

    # # ---------------- BUY / SELL ----------------
    # if request.method == "POST":
    #     action = request.POST.get("action")
    #     symbol = request.POST.get("symbol")
    #     quantity = int(request.POST.get("quantity", 1))

    #     latest_stock = New_Stock_Data.objects.filter(
    #         symbol=symbol
    #     ).order_by("-nepal_dt").first()

    #     if latest_stock:
    #         price = latest_stock.close_price

    #         if action == "buy" and wallet.balance >= price * quantity:
    #             Transaction.objects.create(
    #                 user=request.user,
    #                 symbol=symbol,
    #                 price=price,
    #                 quantity=quantity,
    #                 transaction_type="BUY",
    #             )
    #             wallet.balance -= price * quantity
    #             wallet.save()

    #         elif action == "sell":
    #             bought = Transaction.objects.filter(
    #                 user=request.user,
    #                 symbol=symbol,
    #                 transaction_type="BUY",
    #             ).aggregate(total=Sum("quantity"))["total"] or 0

    #             sold = Transaction.objects.filter(
    #                 user=request.user,
    #                 symbol=symbol,
    #                 transaction_type="SELL",
    #             ).aggregate(total=Sum("quantity"))["total"] or 0

    #             if bought - sold >= quantity:
    #                 Transaction.objects.create(
    #                     user=request.user,
    #                     symbol=symbol,
    #                     price=price,
    #                     quantity=quantity,
    #                     transaction_type="SELL",
    #                 )
    #                 wallet.balance += price * quantity
    #                 wallet.save()

    #     return redirect("dashboard")

    # # ---------------- LSTM GRAPH DATA ----------------
    # lstm_graph_data = {}

    # try:
    #     lstm_graph_data = get_lstm_graph(
    #         symbol=search_symbol,
    #         future_days=future_days
    #     )
    #     print("LSTM graph generated")
    # except Exception as e:
    #     print("LSTM Graph Error:", e)

    # # ---------------- CONTEXT ----------------
    # context = {
    #     "data": stock_dict,
    #     "wallet": wallet,
    #     "transactions": user_transactions,
    #     "recent_symbols": New_Stock_Data.objects.values_list(
    #         "symbol", flat=True
    #     ).distinct()[:10],
    #     "lstm_graph_data": json.dumps(lstm_graph_data or {}),
    #     "current_period": period,
    #     "current_symbol": search_symbol,
    # }

    




# ---------------- LOGOUT ----------------
def logout_view(request):
    logout(request)
    return redirect('Sign_In')
