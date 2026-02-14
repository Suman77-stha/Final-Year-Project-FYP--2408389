from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django import forms


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class New_Stock_Data(models.Model):
    symbol = models.CharField(max_length=10)
    CompanyName = models.CharField(max_length=255)
    Currency = models.CharField(max_length=10)
    nepal_dt = models.DateField()
    utc_dt = models.DateField()
    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    volume = models.BigIntegerField()
    change = models.FloatField()

    def __str__(self):
        return f"{self.symbol} - {self.nepal_dt}"


class Wallet(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=100000.00
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Wallet - $ {self.balance}"


class Transaction(models.Model):
    BUY = 'BUY'
    SELL = 'SELL'

    TRANSACTION_TYPES = [
        (BUY, 'Buy'),
        (SELL, 'Sell'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    symbol = models.CharField(max_length=10)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    quantity = models.PositiveIntegerField()
    transaction_type = models.CharField(
        max_length=4,
        choices=TRANSACTION_TYPES
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def total_value(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.user.username} {self.transaction_type} {self.symbol}"


class Watchlist(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="watchlist"
    )
    symbol = models.CharField(max_length=10)
    CompanyName = models.CharField(max_length=255)
    Currency = models.CharField(max_length=10)
    added_at = models.DateTimeField(auto_now_add=True)
    nepal_dt = models.DateField()
    close_price = models.FloatField()
    change = models.FloatField()
    volume = models.FloatField()

    class Meta:
        unique_together = ('user', 'symbol')
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} → {self.symbol}"
