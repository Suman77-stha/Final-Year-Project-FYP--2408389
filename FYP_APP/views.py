from datetime import date, timedelta
from django.contrib import messages
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.db.models.functions import TruncMonth
from .models import CustomUserCreationForm, New_Stock_Data, Watchlist, Transaction, Wallet, Portfolio
import datetime
import pytz
import random
from django.db.models import Sum
from collections import defaultdict

# ---------------- FORGOT PASSWORD ----------------
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            reset_link = f"http://127.0.0.1:8000/FYP/password-reset-confirm/{user.username}/"
            try:
                if not settings.DEFAULT_FROM_EMAIL or not settings.EMAIL_HOST_PASSWORD:
                    raise ValueError("Email SMTP credentials are not configured.")

                send_mail(
                    'Password Reset Request',
                    f'Hi {user.username},\n\nClick the link below:\n{reset_link}',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False
                )
                return redirect('password_reset_done')
            except Exception as exc:
                return render(
                    request,
                    'forgetPassword.html',
                    {'error': f'Email could not be sent. SMTP error: {exc}'}
                )
        return render(request, 'forgetPassword.html', {'error': 'Email not found'})
    return render(request, 'forgetPassword.html')


# ---------------- PASSWORD RESET CONFIRM ----------------
def password_reset_confirm(request, user):
    try:
        userid = User.objects.get(username=user)
    except User.DoesNotExist:
        return redirect('Sign_In')

    if request.method == "POST":
        # Accept both custom field names and Django default names from templates.
        pass1 = request.POST.get("password1") or request.POST.get("new_password1")
        pass2 = request.POST.get("password2") or request.POST.get("new_password2")
        if pass1 == pass2:
            userid.set_password(pass1)
            userid.save()
            return redirect('password_reset_complete')
        return render(request, 'password_reset_confirm.html', {'error': 'Passwords do not match', 'username': user})

    return render(request, 'password_reset_confirm.html', {'username': user})


# ---------------- PASSWORD RESET COMPLETE ----------------
def password_reset_complete_view(request):
    return render(request, 'password_reset_complete.html')


# ---------------- SIGN UP VIEW ----------------
OTP_SESSION_KEY = "signup_otp_data"
OTP_VALIDITY_MINUTES = 10


def _generate_otp():
    return f"{random.SystemRandom().randint(100000, 999999)}"


def _send_signup_otp_email(username, email, otp):
    if not settings.DEFAULT_FROM_EMAIL or not settings.EMAIL_HOST_PASSWORD:
        raise ValueError("Email SMTP credentials are not configured.")

    send_mail(
        "Your Trade Vision AI OTP Code",
        (
            f"Hi {username},\n\n"
            f"Your OTP for account verification is: {otp}\n"
            f"This code is valid for {OTP_VALIDITY_MINUTES} minutes.\n\n"
            "If you did not request this, please ignore this email."
        ),
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )


def SignUp_View(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            email = form.cleaned_data.get("email")

            if User.objects.filter(username=username).exists():
                return render(request, 'Sign_Up.html', {'form': form, 'error': 'Username already exists'})
            if User.objects.filter(email=email).exists():
                return render(request, 'Sign_Up.html', {'form': form, 'error': 'Email already exists'})

            otp = _generate_otp()
            expires_at = timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)
            request.session[OTP_SESSION_KEY] = {
                "username": username,
                "email": email,
                "password": form.cleaned_data.get("password1"),
                "otp": otp,
                "expires_at": expires_at.isoformat(),
            }

            try:
                _send_signup_otp_email(username, email, otp)
            except Exception:
                request.session.pop(OTP_SESSION_KEY, None)
                return render(
                    request,
                    'Sign_Up.html',
                    {'form': form, 'error': 'OTP email could not be sent. Check email SMTP settings.'}
                )

            return redirect('verify_signup_otp')
    else:
        form = CustomUserCreationForm()

    return render(request, 'Sign_Up.html', {'form': form})


def verify_signup_otp(request):
    otp_data = request.session.get(OTP_SESSION_KEY)
    if not otp_data:
        return redirect('Sign_Up')

    if request.method == 'POST':
        action = request.POST.get("action")

        if action == "resend":
            otp = _generate_otp()
            expires_at = timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)
            otp_data["otp"] = otp
            otp_data["expires_at"] = expires_at.isoformat()
            request.session[OTP_SESSION_KEY] = otp_data

            try:
                _send_signup_otp_email(otp_data["username"], otp_data["email"], otp)
            except Exception:
                return render(
                    request,
                    'verify_signup_otp.html',
                    {'email': otp_data["email"], 'error': 'Failed to resend OTP email.'}
                )

            return render(
                request,
                'verify_signup_otp.html',
                {'email': otp_data["email"], 'success': 'A new OTP has been sent to your email.'}
            )

        entered_otp = request.POST.get("otp", "").strip()
        expires_at = timezone.datetime.fromisoformat(otp_data["expires_at"])

        if timezone.now() > expires_at:
            request.session.pop(OTP_SESSION_KEY, None)
            return render(
                request,
                'verify_signup_otp.html',
                {'email': otp_data["email"], 'error': 'OTP expired. Please sign up again.'}
            )

        if entered_otp != otp_data["otp"]:
            return render(
                request,
                'verify_signup_otp.html',
                {'email': otp_data["email"], 'error': 'Invalid OTP. Please try again.'}
            )

        if User.objects.filter(username=otp_data["username"]).exists():
            request.session.pop(OTP_SESSION_KEY, None)
            return redirect('Sign_Up')

        if User.objects.filter(email=otp_data["email"]).exists():
            request.session.pop(OTP_SESSION_KEY, None)
            return redirect('Sign_Up')

        user = User.objects.create_user(
            username=otp_data["username"],
            email=otp_data["email"],
            password=otp_data["password"],
        )
        request.session.pop(OTP_SESSION_KEY, None)
        login(request, user)
        return redirect('dashboard')

    return render(request, 'verify_signup_otp.html', {'email': otp_data["email"]})

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

def AI_Assistance_view(request):
    return render(request, 'AI_Assistance.html')



@login_required(login_url='Sign_In')
def dashboard_view(request):
    from .APS.API_Data import calculate_indicators, get_news_sentiment, decision_engine
    from .APS.StockAPI import get_stock_data

    # ---------------- SYMBOL & PERIOD ----------------
    search_symbol = request.GET.get('symbol', 'AAPL').upper()
    period = request.GET.get('period', '1y')

    nepal_tz = pytz.timezone("Asia/Kathmandu")
    today = datetime.datetime.now(nepal_tz).date()

    # ---------------- STOCK DATA ----------------
    stock_data = New_Stock_Data.objects.filter(
        symbol=search_symbol,
        nepal_dt=today
    ).first()

    if not stock_data:
        api_data = get_stock_data(search_symbol)

        if api_data:
            stock_data = New_Stock_Data.objects.create(**api_data)

    # ---------------- WATCHLIST ----------------
    watchlist_items = list(
        Watchlist.objects.filter(user=request.user)
        .order_by("-added_at")[:5]
    )

    enhanced_watchdata = []

    for item in watchlist_items:

        try:
            # ---------------- DATA FETCH ----------------
            stock_info = get_stock_data(item.symbol)
            indicators = calculate_indicators(item.symbol)
            sentiment = get_news_sentiment(item.symbol)

            # ---------------- AI ENGINE ----------------
            ai_result = decision_engine(stock_info, indicators, sentiment)

        except Exception:
            # Fallback if any API fails
            ai_result = {
                "action": "HOLD",
                "confidence_score": 0,
                "trend": "Neutral",
                "strength": "Weak",
                "reason": "AI data unavailable"
            }

        # ---------------- FINAL OBJECT ----------------
        enhanced_watchdata.append({
            "symbol": item.symbol,
            "CompanyName": item.CompanyName,
            "close_price": float(item.close_price),
            "change": float(item.change),
            "volume": item.volume,

            # AI OUTPUT
            "ai_action": ai_result.get("action", "HOLD"),
            "confidence_score": ai_result.get("confidence_score", 0),
            "trend": ai_result.get("trend", "Neutral"),
            "strength": ai_result.get("strength", "Weak"),
            "reason": ai_result.get("reason", ""),
        })

    # Put searched symbol card first when it exists in watchlist cards.
    search_idx = next(
        (i for i, row in enumerate(enhanced_watchdata) if row.get("symbol", "").upper() == search_symbol),
        None
    )
    if search_idx is not None and search_idx != 0:
        enhanced_watchdata.insert(0, enhanced_watchdata.pop(search_idx))

    Watchdata = enhanced_watchdata

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

    # ---------------- WALLET ----------------
    wallet, created = Wallet.objects.get_or_create(
        user=request.user,
        defaults={'balance': Decimal("100000")}
    )

    # ---------------- BUY / SELL ----------------
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

                portfolio, _ = Portfolio.objects.get_or_create(
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
                messages.error(request, "Not enough shares")

    # ---------------- PORTFOLIO ----------------
    portfolio = Portfolio.objects.filter(user=request.user)

    trades = Transaction.objects.filter(
        user=request.user
    ).order_by("-created_at")[:10]

    # ---------------- EXTRA ----------------
    today_investment = Transaction.objects.filter(
        user=request.user,
        transaction_type="BUY",
        created_at__date=today
    ).aggregate(total=models.Sum("total"))["total"] or 0

    closing_balance = wallet.balance

    recent_symbols = Watchlist.objects.filter(
        user=request.user
    ).values_list("symbol", flat=True).distinct()[:10]

    # ---------------- PORTFOLIO CALC ----------------
    portfolio_data = []
    total_invested = total_current = total_profit = 0

    for p in portfolio:

        stock_info = get_stock_data(p.symbol)
        current_price = Decimal(str(stock_info["close_price"])) if stock_info else Decimal("0")

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
def _build_user_portfolio_donut_data(user, limit=5):
    palette = ["#22B8CF", "#4C4B8C", "#E39D5F", "#FF6B4A", "#5BC0BE"]

    positions = Portfolio.objects.filter(user=user, quantity__gt=0)
    rows = []
    for p in positions:
        # Portfolio is created from BUY flow; this reflects user buy holdings.
        value = float(p.avg_price * p.quantity)
        if value > 0:
            rows.append({"symbol": p.symbol, "value": value})

    rows.sort(key=lambda x: x["value"], reverse=True)
    rows = rows[:limit]

    labels, values, colors, legend = [], [], [], []
    total = 0.0
    for i, row in enumerate(rows):
        color = palette[i % len(palette)]
        val = round(row["value"], 2)
        labels.append(row["symbol"])
        values.append(val)
        colors.append(color)
        legend.append({"symbol": row["symbol"], "value": val, "color": color})
        total += val

    return {
        "labels": labels,
        "values": values,
        "colors": colors,
        "legend": legend,
        "total": round(total, 2),
    }


@login_required
def wallet_view(request):

    user = request.user

    # ---------------- WALLET ---------------- #

    wallet, created = Wallet.objects.get_or_create(user=user)

    balance = wallet.balance


    # ---------------- TODAY SUMMARY ---------------- #
    today = timezone.localdate()
    selected_date = today

    selected_transactions = Transaction.objects.filter(
        user=user,
        created_at__date=selected_date
    ).order_by("-created_at")

    selected_income = selected_transactions.filter(
        transaction_type="SELL"
    ).aggregate(total=Sum("total"))["total"] or 0

    selected_expense = selected_transactions.filter(
        transaction_type="BUY"
    ).aggregate(total=Sum("total"))["total"] or 0


    # ---------------- HISTORICAL TRANSACTIONS ---------------- #
    all_transactions = Transaction.objects.filter(
        user=user
    ).order_by("-created_at")[:100]

    grouped_map = defaultdict(list)
    for tx in all_transactions:
        grouped_map[tx.created_at.date()].append(tx)

    grouped_transactions = [
        {"date": tx_date, "items": items}
        for tx_date, items in sorted(grouped_map.items(), key=lambda x: x[0], reverse=True)
    ]


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

    donut_data = _build_user_portfolio_donut_data(user, limit=5)

    # ---------------- LAST 7 DAYS CHART DATA ---------------- #
    start_date = today - datetime.timedelta(days=6)
    seven_day_dates = [start_date + datetime.timedelta(days=i) for i in range(7)]

    range_transactions = Transaction.objects.filter(
        user=user,
        created_at__date__gte=start_date,
        created_at__date__lte=today
    ).order_by("created_at")

    chart_by_day = {
        d: {"income": 0.0, "expense": 0.0}
        for d in seven_day_dates
    }

    for tx in range_transactions:
        tx_day = tx.created_at.date()
        if tx_day not in chart_by_day:
            continue
        amount = float(tx.total)
        if tx.transaction_type == "SELL":
            chart_by_day[tx_day]["income"] += amount
        elif tx.transaction_type == "BUY":
            chart_by_day[tx_day]["expense"] += amount

    chart_labels = [d.strftime("%d %b") for d in seven_day_dates]
    chart_income = [round(chart_by_day[d]["income"], 2) for d in seven_day_dates]
    chart_expense = [round(chart_by_day[d]["expense"], 2) for d in seven_day_dates]
    chart_net = [round(chart_by_day[d]["income"] - chart_by_day[d]["expense"], 2) for d in seven_day_dates]


    # ---------------- CONTEXT ---------------- #

    context = {
        "balance": balance,
        "today_income": selected_income,
        "today_expense": selected_expense,
        "recent_transactions": selected_transactions,
        "grouped_transactions": grouped_transactions,
        "selected_date": selected_date,
        "recent_symbols": recent_symbols,
        "buy_total": buy_total,
        "sell_total": sell_total,
        "donut_labels": donut_data["labels"],
        "donut_values": donut_data["values"],
        "donut_colors": donut_data["colors"],
        "donut_legend": donut_data["legend"],
        "donut_total": donut_data["total"],
        "chart_labels": chart_labels,
        "chart_income": chart_income,
        "chart_expense": chart_expense,
        "chart_net": chart_net,
    }

    return render(request, "Wallet.html", context)


@login_required
def wallet_top5_donut_api(request):
    return JsonResponse(_build_user_portfolio_donut_data(request.user, limit=5))
    
@login_required(login_url='Sign_In')
def user_profile_view(request):
    user = request.user

    if request.method == "POST" and request.POST.get("action") == "profile":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()

        if not username or not email:
            messages.error(request, "Username and email are required.")
            return redirect("profile")

        username_exists = User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists()
        email_exists = User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists()

        if username_exists:
            messages.error(request, "This username is already taken.")
            return redirect("profile")

        if email_exists:
            messages.error(request, "This email is already in use.")
            return redirect("profile")

        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    holdings_count = Portfolio.objects.filter(user=user, quantity__gt=0).count()
    transactions_count = Transaction.objects.filter(user=user).count()
    joined_date = user.date_joined

    context = {
        "holdings_count": holdings_count,
        "transactions_count": transactions_count,
        "joined_date": joined_date,
    }
    return render(request, "user_profile.html", context)


@login_required(login_url='Sign_In')
def settings_view(request):
    user = request.user

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "preferences":
            request.session["settings_email_alerts"] = request.POST.get("email_alerts") == "on"
            request.session["settings_price_alerts"] = request.POST.get("price_alerts") == "on"
            request.session["settings_ai_tips"] = request.POST.get("ai_tips") == "on"
            request.session["settings_theme"] = request.POST.get("theme", "system")
            request.session.modified = True
            messages.success(request, "Settings saved successfully.")
            return redirect("settings")

        if action == "password":
            current_password = request.POST.get("current_password", "")
            new_password = request.POST.get("new_password", "")
            confirm_password = request.POST.get("confirm_password", "")

            if not user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
                return redirect("settings")

            if new_password != confirm_password:
                messages.error(request, "New passwords do not match.")
                return redirect("settings")

            if len(new_password) < 8:
                messages.error(request, "New password must be at least 8 characters long.")
                return redirect("settings")

            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            return redirect("settings")

    context = {
        "email_alerts": request.session.get("settings_email_alerts", True),
        "price_alerts": request.session.get("settings_price_alerts", True),
        "ai_tips": request.session.get("settings_ai_tips", True),
        "theme": request.session.get("settings_theme", "system"),
    }
    return render(request, "settings.html", context)


@login_required
def get_live_price(request):
    from .APS.StockAPI import get_stock_data

    symbol = request.GET.get("symbol")

    if not symbol:
        return JsonResponse({"price": None})

    data = get_stock_data(symbol.upper())

    if data:
        return JsonResponse({
            "price": data["close_price"]
        })

    return JsonResponse({"price": None})

@login_required
def stock_prediction_api(request):
    from .APS.lstm_model import predict

    symbol = request.GET.get("symbol", "AAPL")
    range_param = request.GET.get("range", "7D")

    range_map = {"7D": 7, "2W": 14, "7W": 49, "1M": 30, "5M": 150, "1Y": 365}
    period = range_map.get(range_param, 7)

    result = predict(symbol, period)

    # ---- Use real dates ----
    today = datetime.date.today()
    history_dates = [(today - datetime.timedelta(days=period - i)).strftime("%Y-%m-%d") 
                     for i in range(len(result["close_prices"]))]
    future_dates = [(today + datetime.timedelta(days=i+1)).strftime("%Y-%m-%d") 
                    for i in range(len(result["future_days"]))]

    # Ensure last historical price = current_price
    if result["close_prices"][-1] != result["current_price"]:
        result["close_prices"][-1] = result["current_price"]

    data = {
        "symbol": symbol,
        "history_labels": history_dates,
        "future_labels": future_dates,
        "close_prices": result["close_prices"],
        "future_days": result["future_days"],
        "accuracy": result.get("accuracy", 0),
        "current_price": result["current_price"]
    }

    return JsonResponse(data)
@login_required
# def profit_loss_api(request):

#     user = request.user

#     data = (
#         Transaction.objects.filter(user=user)
#         .annotate(month=TruncMonth("created_at"))
#         .values("month", "transaction_type")
#         .annotate(total=Sum("total"))
#         .order_by("month")
#     )

#     monthly = {}

#     for item in data:
#         month = item["month"].strftime("%b")

#         if month not in monthly:
#             monthly[month] = 0

#         if item["transaction_type"] == "BUY":
#             monthly[month] -= float(item["total"])
#         else:
#             monthly[month] += float(item["total"])

#     return JsonResponse({
#         "labels": list(monthly.keys())[-6:],  # last 6 months
#         "data": list(monthly.values())[-6:]
#     })

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
# from django.http import JsonResponse
# from FYP_APP.services.ai_engine import smart_ai

# def chatbot(request):
#     query = request.GET.get("q")

#     response = smart_ai(query)

#     return JsonResponse({"response": response})
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from decimal import Decimal
import json
from FYP_APP.models import Wallet, Portfolio, Transaction, New_Stock_Data

@login_required
def trading_bot_view(request):
    wallet = Wallet.objects.get(user=request.user)
    portfolio = Portfolio.objects.filter(user=request.user)
    market = New_Stock_Data.objects.order_by('-nepal_dt')[:20]  # Latest 20 stocks

    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        data = json.loads(request.body)
        symbol = data.get('symbol').upper()
        quantity = int(data.get('quantity'))
        action = data.get('action').upper()
        
        # Optional signals for conditional buy
        confidence = float(data.get('confidence_score', 0))
        trend = data.get('trend', '').lower()
        strength = data.get('strength', '').lower()
        conflict = data.get('conflict', False)
        reason = data.get('reason', '')

        # Get latest stock price
        stock = New_Stock_Data.objects.filter(symbol=symbol).order_by('-nepal_dt').first()
        if not stock:
            return JsonResponse({'message': 'Stock not found.'})
        price = Decimal(stock.close_price)
        total = price * quantity

        message = ""

        if action == 'BUY':
            # Condition logic
            if conflict:
                return JsonResponse({'message': f'Cannot buy {symbol}: conflict detected.'})
            if trend != 'bullish' or confidence < 35 or strength == 'weak':
                return JsonResponse({'message': f'Condition not met for {symbol}. Reason: {reason}'})
            if wallet.balance < total:
                return JsonResponse({'message': 'Insufficient balance.'})

            # Buy process
            wallet.balance -= total
            wallet.save()
            portfolio_item, created = Portfolio.objects.get_or_create(
                user=request.user,
                symbol=symbol,
                defaults={'quantity': quantity, 'avg_price': price}
            )
            if not created:
                total_quantity = portfolio_item.quantity + quantity
                portfolio_item.avg_price = ((portfolio_item.avg_price * portfolio_item.quantity) + total) / total_quantity
                portfolio_item.quantity = total_quantity
                portfolio_item.save()

            Transaction.objects.create(
                user=request.user,
                symbol=symbol,
                price=price,
                quantity=quantity,
                total=total,
                transaction_type='BUY'
            )
            message = f"Bought {quantity} of {symbol} at ${price} | Reason: {reason}"

        elif action == 'SELL':
            try:
                portfolio_item = Portfolio.objects.get(user=request.user, symbol=symbol)
            except Portfolio.DoesNotExist:
                return JsonResponse({'message': 'You do not own this stock.'})

            if portfolio_item.quantity < quantity:
                return JsonResponse({'message': 'Insufficient quantity to sell.'})

            portfolio_item.quantity -= quantity
            if portfolio_item.quantity == 0:
                portfolio_item.delete()
            else:
                portfolio_item.save()

            wallet.balance += total
            wallet.save()

            Transaction.objects.create(
                user=request.user,
                symbol=symbol,
                price=price,
                quantity=quantity,
                total=total,
                transaction_type='SELL'
            )
            message = f"Sold {quantity} of {symbol} at ${price}"

        # Prepare updated portfolio HTML
        portfolio_qs = Portfolio.objects.filter(user=request.user)
        portfolio_html = ''.join([
            f"<tr><td>{item.symbol}</td><td>{item.quantity}</td><td>{item.avg_price}</td></tr>"
            for item in portfolio_qs
        ])

        return JsonResponse({
            'message': message,
            'wallet_balance': wallet.balance,
            'portfolio_html': portfolio_html
        })

    # GET request → render dashboard
    return render(request, 'trading_dashboard.html', {
        'wallet': wallet,
        'portfolio': portfolio,
        'market': market
    })
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def Ai_Assistance_view(request):
    from .APS.nlp_voice_system import chatbot_logic

    # Initialize chat history in session if not present
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []

    if request.method == "POST":
        user_input = request.POST.get("message", "").strip()
        
        if user_input:
            # Call your existing logic from the APS folder
            ai_response = chatbot_logic(user_input, user=request.user)

            # Update the session history
            history = request.session['chat_history']
            history.append({
                'user': user_input, 
                'ai': ai_response
            })
            
            # Limit history to last 10 exchanges to keep session light
            if len(history) > 10:
                history.pop(0)
                
            request.session['chat_history'] = history
            request.session.modified = True
            
            # Redirect to the same page to prevent "Form Resubmission" on refresh
            return redirect('chatbot')

    return render(request, 'AI_Assistance.html', {
        'chat_history': request.session.get('chat_history', [])
    })

def clear_chat(request):
    if 'chat_history' in request.session:
        del request.session['chat_history']
    return redirect('chatbot')
