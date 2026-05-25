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
from django.urls import reverse
from decimal import Decimal
from django.db.models.functions import TruncMonth
from .models import CustomUserCreationForm, New_Stock_Data, Watchlist, Transaction, Wallet, Portfolio
import datetime
import pytz
import random
import requests
import numpy as np
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.db.models import Case, When, Value, DecimalField
from collections import defaultdict
import logging
import threading
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ---------------- FORGOT PASSWORD ----------------
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        user = User.objects.filter(email__iexact=email).first()

        if user:
            reset_path = reverse("password_reset_confirm", kwargs={"user": user.username})
            reset_link = request.build_absolute_uri(reset_path)
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


def _email_is_configured():
    return bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD and settings.DEFAULT_FROM_EMAIL)


def _send_signup_otp_email_async(username, email, otp):
    """
    Send OTP email in background so signup endpoint stays fast.
    """
    def _runner():
        try:
            _send_signup_otp_email(username, email, otp)
        except Exception:
            logger.exception("Async OTP email failed for user=%s email=%s", username, email)

    threading.Thread(target=_runner, daemon=True).start()


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

            if not _email_is_configured():
                request.session.pop(OTP_SESSION_KEY, None)
                return render(
                    request,
                    'Sign_Up.html',
                    {'form': form, 'error': 'OTP email service is not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD on Render.'}
                )

            try:
                _send_signup_otp_email(username, email, otp)
            except Exception as exc:
                request.session.pop(OTP_SESSION_KEY, None)
                logger.exception("Signup OTP send failed for user=%s email=%s", username, email)
                return render(
                    request,
                    'Sign_Up.html',
                    {'form': form, 'error': f'OTP email could not be sent. SMTP error: {exc}'}
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
            if not _email_is_configured():
                return render(
                    request,
                    'verify_signup_otp.html',
                    {'email': otp_data["email"], 'error': 'OTP email service is not configured. Please contact support.'}
                )

            otp = _generate_otp()
            expires_at = timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES)
            otp_data["otp"] = otp
            otp_data["expires_at"] = expires_at.isoformat()
            request.session[OTP_SESSION_KEY] = otp_data

            try:
                _send_signup_otp_email(otp_data["username"], otp_data["email"], otp)
            except Exception as exc:
                logger.exception("Resend OTP failed for user=%s email=%s", otp_data["username"], otp_data["email"])
                return render(
                    request,
                    'verify_signup_otp.html',
                    {'email': otp_data["email"], 'error': f'Failed to resend OTP email. SMTP error: {exc}'}
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

        try:
            with transaction.atomic():
                user, created = User.objects.get_or_create(
                    username=otp_data["username"],
                    defaults={
                        "email": otp_data["email"],
                    },
                )
                if not created:
                    request.session.pop(OTP_SESSION_KEY, None)
                    return render(
                        request,
                        'verify_signup_otp.html',
                        {'email': otp_data["email"], 'error': 'Username already exists. Please sign up again.'}
                    )
                if User.objects.filter(email=otp_data["email"]).exclude(pk=user.pk).exists():
                    request.session.pop(OTP_SESSION_KEY, None)
                    return render(
                        request,
                        'verify_signup_otp.html',
                        {'email': otp_data["email"], 'error': 'Email already exists. Please sign up again.'}
                    )
                user.set_password(otp_data["password"])
                user.save(update_fields=["password", "email"])
        except IntegrityError:
            request.session.pop(OTP_SESSION_KEY, None)
            return render(
                request,
                'verify_signup_otp.html',
                {'email': otp_data["email"], 'error': 'Account already exists. Please sign in or retry.'}
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

def AI_Assistance_view(request):
    return render(request, 'AI_Assistance.html')



@login_required(login_url='Sign_In')
def dashboard_view(request):
    from .APS.StockAPI import get_stock_data

    # ---------------- SYMBOL & PERIOD ----------------
    search_symbol = request.GET.get('symbol', 'AAPL').upper()
    period = request.GET.get('period', '1y')

    nepal_tz = pytz.timezone("Asia/Kathmandu")
    today = datetime.datetime.now(nepal_tz).date()

    def get_cached_or_fetch_quote(symbol):
        cached_qs = New_Stock_Data.objects.filter(symbol=symbol, nepal_dt=today).order_by("-utc_dt", "-id")
        cached = cached_qs.first()
        if cached:
            # If historical duplicate rows exist, use the most recent row to keep dashboard stable.
            return cached
        api_data = get_stock_data(symbol)
        if not api_data:
            return None
        existing_qs = New_Stock_Data.objects.filter(
            symbol=api_data["symbol"],
            nepal_dt=api_data["nepal_dt"],
        ).order_by("-utc_dt", "-id")
        existing = existing_qs.first()
        if existing:
            for field, value in api_data.items():
                setattr(existing, field, value)
            existing.save()
            return existing
        return New_Stock_Data.objects.create(**api_data)

    # ---------------- STOCK DATA ----------------
    stock_data = get_cached_or_fetch_quote(search_symbol)

    # ---------------- WATCHLIST ----------------
    watchlist_items = list(
        Watchlist.objects.filter(user=request.user)
        .order_by("-added_at")[:5]
    )

    enhanced_watchdata = []

    for item in watchlist_items:

        enhanced_watchdata.append({
            "symbol": item.symbol.strip(),
            "CompanyName": item.CompanyName,
            "close_price": float(item.close_price) if item.close_price else 0.0,
            "change": float(item.change) if item.change else 0.0,
            "volume": item.volume,

            # AI OUTPUT
            "ai_action": "LOADING",
            "confidence_score": 0,
            "trend": "Neutral",
            "strength": "Weak",
            "reason": "",
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
                cache.delete(f"wallet_top5_donut:{request.user.id}")
                cache.delete(f"portfolio_api:{request.user.id}")

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
                cache.delete(f"wallet_top5_donut:{request.user.id}")
                cache.delete(f"portfolio_api:{request.user.id}")

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

        stock_quote = get_cached_or_fetch_quote(p.symbol)
        current_price = Decimal(str(stock_quote.close_price)) if stock_quote else Decimal("0")

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
    cache_key = f"wallet_top5_donut:{request.user.id}"
    payload = cache.get(cache_key)
    if payload is None:
        payload = _build_user_portfolio_donut_data(request.user, limit=5)
        cache.set(cache_key, payload, 30)
    return JsonResponse(payload)


@login_required
def portfolio_api(request):
    cache_key = f"portfolio_api:{request.user.id}"
    payload = cache.get(cache_key)
    if payload is None:
        positions = Portfolio.objects.filter(user=request.user, quantity__gt=0).values("symbol", "quantity", "avg_price")
        positions_list = list(positions)
        tx_summary = Transaction.objects.filter(user=request.user).aggregate(
            buy_total=Sum(
                Case(
                    When(transaction_type="BUY", then="total"),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=3),
                )
            ),
            sell_total=Sum(
                Case(
                    When(transaction_type="SELL", then="total"),
                    default=Value(0),
                    output_field=DecimalField(max_digits=12, decimal_places=3),
                )
            ),
        )

        payload = {
            "positions": positions_list,
            "positions_count": len(positions_list),
            "buy_total": float(tx_summary["buy_total"] or 0),
            "sell_total": float(tx_summary["sell_total"] or 0),
        }
        cache.set(cache_key, payload, 30)

    return JsonResponse(payload)
    
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
    allowed_themes = {"system", "light", "dark", "midnight", "graphite"}

    def as_bool(value):
        return str(value).lower() in {"1", "true", "on", "yes"}

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "preferences":
            request.session["settings_email_alerts"] = as_bool(request.POST.get("email_alerts"))
            request.session["settings_price_alerts"] = as_bool(request.POST.get("price_alerts"))
            request.session["settings_ai_tips"] = as_bool(request.POST.get("ai_tips"))

            selected_theme = (request.POST.get("theme", "system") or "system").strip().lower()
            if selected_theme not in allowed_themes:
                selected_theme = "system"
                messages.error(request, "Invalid theme selected. Reverted to System.")
            request.session["settings_theme"] = selected_theme

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


def landing_market_snapshot_api(request):
    from .APS.StockAPI import get_stock_data

    def to_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def pct_change(price, change):
        prev = price - change
        if prev == 0:
            return 0.0
        return (change / prev) * 100

    def fetch_quote(symbol):
        data = get_stock_data(symbol) or {}
        price = to_float(data.get("close_price"), 0.0)
        change = to_float(data.get("change"), 0.0)
        return {
            "symbol": (data.get("symbol") or symbol).upper(),
            "price": price,
            "change": change,
            "change_pct": round(pct_change(price, change), 2),
            "currency": data.get("Currency", "USD"),
        }

    quotes = {
        "NASDAQ": fetch_quote("^IXIC"),
        "S&P500": fetch_quote("^GSPC"),
        "AAPL": fetch_quote("AAPL"),
        "TSLA": fetch_quote("TSLA"),
        "BTC": fetch_quote("BTC-USD"),
        "MSFT": fetch_quote("MSFT"),
        "NVDA": fetch_quote("NVDA"),
    }

    aapl = quotes["AAPL"]
    tsla = quotes["TSLA"]
    btc = quotes["BTC"]

    prediction_trend = "Bullish" if aapl["change_pct"] > 0.2 else "Bearish" if aapl["change_pct"] < -0.2 else "Neutral"
    confidence = int(max(55, min(94, 62 + abs(aapl["change_pct"]) * 6)))

    signal = "BUY" if tsla["change_pct"] > 1 else "SELL" if tsla["change_pct"] < -1 else "HOLD"
    risk_level = "High" if abs(tsla["change_pct"]) >= 2.5 else "Medium" if abs(tsla["change_pct"]) >= 1 else "Low"
    signal_reason = (
        "Momentum remains positive with improving day trend."
        if signal == "BUY"
        else "Downside pressure is increasing; protect capital."
        if signal == "SELL"
        else "Sideways movement detected; wait for stronger confirmation."
    )

    proxy_assets = [quotes["AAPL"], quotes["MSFT"], quotes["NVDA"], quotes["TSLA"], quotes["BTC"]]
    total_value = round(sum(x["price"] for x in proxy_assets), 2)
    avg_change = round(sum(x["change_pct"] for x in proxy_assets) / len(proxy_assets), 2) if proxy_assets else 0.0

    return JsonResponse({
        "ticker": [
            {"label": "NASDAQ", **quotes["NASDAQ"]},
            {"label": "S&P 500", **quotes["S&P500"]},
            {"label": "AAPL", **quotes["AAPL"]},
            {"label": "TSLA", **quotes["TSLA"]},
            {"label": "BTC", **quotes["BTC"]},
        ],
        "cards": {
            "live_market": {
                "nasdaq": quotes["NASDAQ"],
                "sp500": quotes["S&P500"],
                "btc": quotes["BTC"],
            },
            "ai_prediction": {
                "symbol": "AAPL",
                "trend": prediction_trend,
                "confidence": confidence,
                "next_day_hint": round(aapl["price"] * (1 + (aapl["change_pct"] / 100) * 0.4), 2),
            },
            "recommendation": {
                "symbol": "TSLA",
                "signal": signal,
                "risk_level": risk_level,
                "reason": signal_reason,
            },
            "portfolio_proxy": {
                "total_value": total_value,
                "profit_pct": avg_change,
                "active_assets": len(proxy_assets),
            },
        },
        "updated_symbol_time": timezone.now().isoformat(),
    })

@login_required
def watchlist_ai_api(request):
    from .prediction.ai_suggestion import generate_ai_suggestion
    
    watchlist_items = list(
        Watchlist.objects.filter(user=request.user)
        .order_by("-added_at")[:5]
    )
    
    owned_symbols = set(
        Portfolio.objects.filter(user=request.user, quantity__gt=0)
        .values_list("symbol", flat=True)
    )

    ai_predictions = {}
    for item in watchlist_items:
        sym = item.symbol.strip()
        user_has_stock = sym in owned_symbols
        ai_result = generate_ai_suggestion(sym, user_has_stock)
        ai_predictions[sym] = {
            "ai_action": ai_result.get("action", "HOLD"),
            "confidence_score": ai_result.get("confidence_score", 0),
            "trend": ai_result.get("trend", "Neutral")
        }
        
    return JsonResponse({"status": "success", "data": ai_predictions})

@login_required
def stock_prediction_api(request):
    from .prediction.predict_system import predict

    symbol = request.GET.get("symbol", "AAPL")
    range_param = request.GET.get("range", "7D")

    range_map = {"7D": 7, "2W": 14, "7W": 49, "1M": 30, "5M": 150, "1Y": 365}
    period = range_map.get(range_param, 7)

    result = predict(symbol, period)

    # ---- Use real dates ----
    today = datetime.date.today()
    history_dates = [(today - datetime.timedelta(days=len(result["close_prices"]) - 1 - i)).strftime("%Y-%m-%d") 
                     for i in range(len(result["close_prices"]))]
    future_dates = [(today + datetime.timedelta(days=i+1)).strftime("%Y-%m-%d") 
                    for i in range(len(result["future_days"]))]

    # Ensure last historical price = current_price
    close_prices = result.get("close_prices") or []
    if close_prices and result.get("current_price") is not None:
        if close_prices[-1] != result["current_price"]:
            close_prices[-1] = result["current_price"]

    data = {
        "symbol": symbol,
        "history_labels": history_dates,
        "future_labels": future_dates,
        "close_prices": close_prices,
        "future_days": result["future_days"],
        "accuracy": round(100 - result.get("mape", 0), 2),
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

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def Ai_Assistance_view(request):
    from .APS.nlp_voice_system import chatbot_logic

    # Initialize chat history in session if not present
    if 'chat_history' not in request.session:
        request.session['chat_history'] = []
    if 'chatbot_memory_state' not in request.session:
        request.session['chatbot_memory_state'] = {}

    if request.method == "POST":
        user_input = request.POST.get("message", "").strip()
        
        if user_input:
            # Call chatbot with persisted memory state for contextual follow-ups.
            ai_response, new_memory_state = chatbot_logic(
                user_input,
                user=request.user,
                memory_state=request.session.get('chatbot_memory_state', {}),
                return_state=True
            )

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
            request.session['chatbot_memory_state'] = new_memory_state
            request.session.modified = True
            
            # Redirect to the same page to prevent "Form Resubmission" on refresh
            return redirect('chatbot')

    return render(request, 'AI_Assistance.html', {
        'chat_history': request.session.get('chat_history', [])
    })

def clear_chat(request):
    if 'chat_history' in request.session:
        del request.session['chat_history']
    if 'chatbot_memory_state' in request.session:
        del request.session['chatbot_memory_state']
    return redirect('chatbot')
