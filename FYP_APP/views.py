from datetime import date
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings

from FYP_APP.models import CustomUserCreationForm, New_Stock_Data, Watchlist, Transaction, Wallet
import requests
import datetime
import pytz

# ---------------- FORGOT PASSWORD ----------------
# ---------------- FORGOT PASSWORD ----------------
def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get('email')
        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            # You can generate proper token later, for now use username in URL
            reset_link = f"http://127.0.0.1:8000/FYP/password-reset-confirm/{user.username}/"
            send_mail(
                'Password Reset Request',
                f'Hi {user.username},\n\nClick the link below to reset your password:\n{reset_link}',
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False
            )
            return redirect('password_reset_done')
        else:
            return render(request, 'forgetPassword.html', {'error': 'Email not found'})
    else:
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
        if pass1 and pass1 == pass2:
            userid.set_password(pass1)
            userid.save()
            return redirect('password_reset_complete')
        else:
            return render(request, 'password_reset_confirm.html', {'error': 'Passwords do not match'})

    return render(request, 'password_reset_confirm.html', {'username': user})


# ---------------- PASSWORD RESET COMPLETE ----------------
def password_reset_complete_view(request):
    # Simply render a "Password Reset Successful" page
    return render(request, 'password_reset_complete.html')


# ---------------- SIGN UP VIEW ----------------
def SignUp_View(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            username = request.POST.get("username")
            email = request.POST.get("email")
            pass1 = request.POST.get("password1")
            pass2 = request.POST.get("password2")

            if pass1 != pass2:
                return render(request, 'Sign_Up.html', {'form': form, 'error': 'Passwords do not match'})

            if User.objects.filter(username=username).exists():
                return render(request, 'Sign_Up.html', {'form': form, 'error': f'Username "{username}" already exists'})

            if User.objects.filter(email=email).exists():
                return render(request, 'Sign_Up.html', {'form': form, 'error': f'Email "{email}" already exists'})

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
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        initial_data = {'username': '', 'password': ''}
        form = AuthenticationForm(initial=initial_data)
    return render(request, 'Sign_In.html', {'form': form})


# ---------------- DASHBOARD VIEW ----------------
@login_required(login_url='Sign_In')
def dashboard_view(request):
    search_symbol = request.GET.get('symbol', 'BTC')
    api_data = None

    # Fetch real-time stock data
    try:
        response = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": search_symbol, "token": settings.FINNHUB_API_KEY}
        )
        response.raise_for_status()
        api_data = response.json()
    except Exception as e:
        print("Error fetching API:", e)

    nepal_dt = None
    if api_data and api_data.get('t'):
        timestamp = api_data['t']
        utc_dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=pytz.utc)
        nepal_dt = utc_dt.astimezone(pytz.timezone("Asia/Kathmandu"))

        # Save new stock data if today's data doesn't exist
        if not New_Stock_Data.objects.filter(symbol=search_symbol, nepal_dt=nepal_dt.date()).exists():
            stock = New_Stock_Data.objects.create(
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

    # ------------------- WATCHLIST -------------------
    stock_dict = {}
    user_watchlist = []

    if request.user.is_authenticated and nepal_dt:
        # Add/update searched symbol to watchlist
        watchlist_item, created = Watchlist.objects.update_or_create(
            user=request.user,
            symbol=search_symbol,
            defaults={
                'nepal_dt': nepal_dt.date(),
                'close_price': api_data.get('c', 0),
                'change': api_data.get('d', 0),
            }
        )

        # Limit to last 5 symbols
        all_watchlist = Watchlist.objects.filter(user=request.user).order_by('-added_at')
        if all_watchlist.count() > 5:
            for wl in all_watchlist[5:]:
                wl.delete()

        user_watchlist = Watchlist.objects.filter(user=request.user).order_by('-added_at')

        # Prepare stock_dict with latest nepal_dt for each symbol
        for wl in user_watchlist:
            latest_stock = New_Stock_Data.objects.filter(symbol=wl.symbol).order_by('-nepal_dt').first()
            if latest_stock:
                stock_dict[wl.symbol] = latest_stock

    # ------------------- Recent symbols -------------------
    recent_symbols = New_Stock_Data.objects.values_list('symbol', flat=True).distinct()[:10]

    # ------------------- Transactions -------------------
    user_transactions = Transaction.objects.filter(
        user=request.user,
        transaction_type='BUY'
    ).order_by('-created_at')

    # ------------------- Wallet -------------------
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    # ------------------- Buy/Sell Actions -------------------
    if request.method == "POST":
        action = request.POST.get('action')
        symbol = request.POST.get('symbol')
        quantity = int(request.POST.get('quantity', 1))
        latest_stock = New_Stock_Data.objects.filter(symbol=symbol).order_by('-nepal_dt').first()

        if latest_stock:
            price = latest_stock.close_price
            if action.lower() == "buy":
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

            elif action.lower() == "sell":
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

    # ------------------- Context -------------------
    context = {
        'data': stock_dict,
        'watchlist': user_watchlist,
        'transactions': user_transactions,
        'wallet': wallet,
        'recent_symbols': recent_symbols,
    }

    return render(request, 'dashboard.html', context)


# ---------------- LOGOUT ----------------
def logout_view(request):
    logout(request)
    return redirect('Sign_In')
