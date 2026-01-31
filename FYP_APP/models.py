# ==============================
# Django core imports
# ==============================

# Used to create database tables (models)
from django.db import models

# Django built-in User model (handles login, username, password, etc.)
from django.contrib.auth.models import User

# Used to extend Django's default signup form
from django.contrib.auth.forms import UserCreationForm

# Django form utilities
from django import forms


# ==============================
# Custom User Registration Form
# ==============================

class CustomUserCreationForm(UserCreationForm):
    # Adds email field to default Django signup form
    email = forms.EmailField(required=True)

    class Meta:
        # Tell Django to use built-in User model
        model = User

        # Fields that will appear in the signup form
        fields = ('username', 'email', 'password1', 'password2')


# ==============================
# STOCK MARKET DATA MODEL
# (Shared by all users)
# ==============================

class New_Stock_Data(models.Model):
    # Stock ticker symbol (AAPL, TSLA, NABIL, etc.)
    symbol = models.CharField(max_length=10)

    # Date in Nepal time (for local market display)
    nepal_dt = models.DateField()

    # Date in UTC time (for API reference)
    utc_dt = models.DateField()

    # Opening price of the stock
    open_price = models.FloatField()

    # Highest price of the day
    high_price = models.FloatField()

    # Lowest price of the day
    low_price = models.FloatField()

    # Closing price of the stock
    close_price = models.FloatField()

    # Total traded volume
    volume = models.BigIntegerField()

    # Price difference (today - previous close)
    change = models.FloatField()

    # Percentage change
    change_percent = models.FloatField()

    def __str__(self):
        # Human-readable display in admin panel
        return f"{self.symbol} - {self.nepal_dt}"


# ==============================
# WALLET MODEL
# (One wallet per user)
# ==============================

class Wallet(models.Model):
    # OneToOneField means:
    # One user → One wallet only
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,     # Delete wallet if user is deleted
        related_name="wallet"         # Access wallet using user.wallet
    )

    # User's current balance
    # DecimalField is used for money to avoid precision errors
    balance = models.DecimalField(
        max_digits=12,                # Total digits
        decimal_places=2,             # Digits after decimal
        default=100000.00             # Default starting balance
    )

    # Automatically updates when wallet changes
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Wallet - $ {self.balance}"


# ==============================
# TRANSACTION MODEL
# (Buy & Sell records)
# ==============================

class Transaction(models.Model):
    # Constants to avoid spelling mistakes
    BUY = 'BUY'
    SELL = 'SELL'

    # Choices shown in admin and forms
    TRANSACTION_TYPES = [
        (BUY, 'Buy'),
        (SELL, 'Sell'),
    ]

    # Many transactions can belong to one user
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,        # Delete transactions if user deleted
        related_name="transactions"      # Access via user.transactions.all()
    )

    # Stock symbol being traded
    symbol = models.CharField(max_length=10)

    # Price per stock at the time of transaction
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # Number of stocks bought or sold
    quantity = models.PositiveIntegerField()  # Prevents negative quantity

    # BUY or SELL
    transaction_type = models.CharField(
        max_length=4,
        choices=TRANSACTION_TYPES
    )

    # Automatically stores transaction date & time
    created_at = models.DateTimeField(auto_now_add=True)

    def total_value(self):
        # Calculates total transaction value
        return self.price * self.quantity

    def __str__(self):
        return f"{self.user.username} {self.transaction_type} {self.symbol}"


# ==============================
# WATCHLIST MODEL
# (User saved stocks)
# ==============================

class Watchlist(models.Model):
    # One user can watch many stocks
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="watchlist"      # Access via user.watchlist.all()
    )

    # Stock symbol added to watchlist
    symbol = models.CharField(max_length=10)

    # Time when stock was added
    added_at = models.DateTimeField(auto_now_add=True)

    # Date in Nepal time (for local market display)
    nepal_dt = models.DateField()

    # Closing price of the stock
    close_price = models.FloatField()
    
    # Closing price of the stock
    change = models.FloatField()

    class Meta:
        # Prevent same user from adding same stock twice
        unique_together = ('user', 'symbol')

        # Latest added stock appears first
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} → {self.symbol}"


