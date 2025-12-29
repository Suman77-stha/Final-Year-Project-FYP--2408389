from django.db import models
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class New_Stock_Data(models.Model):
    symbol = models.CharField(max_length=10)
    nepal_dt = models.DateField()
    utc_dt = models.DateField()
    open_price = models.FloatField()
    high_price = models.FloatField()
    low_price = models.FloatField()
    close_price = models.FloatField()
    volume = models.BigIntegerField()
    change = models.FloatField()
    change_percent = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.symbol} - {self.nepal_dt}"
