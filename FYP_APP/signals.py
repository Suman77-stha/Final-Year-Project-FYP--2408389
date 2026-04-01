# signals.py
from django.db.models.signals import post_save,post_delete
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Wallet

from .models import New_Stock_Data, Portfolio, Transaction
from .tasks import retrain_lora_async  # background task

@receiver(post_save, sender=User)
def create_wallet(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.create(user=instance, balance=100000.00)



@receiver([post_save, post_delete], sender=New_Stock_Data)
@receiver([post_save, post_delete], sender=Portfolio)
@receiver([post_save, post_delete], sender=Transaction)
def trigger_lora_retrain(sender, instance, **kwargs):
    retrain_lora_async()