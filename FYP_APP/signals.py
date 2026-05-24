# signals.py
from django.db.models.signals import post_save, post_delete
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Wallet
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_wallet(sender, instance, created, **kwargs):
    """
    Automatically create a wallet for new users with initial balance.
    """
    if created:
        Wallet.objects.create(user=instance, balance=100000.00)
        logger.info(f"Created wallet for new user: {instance.username}")


@receiver([post_save, post_delete], sender=Wallet)
def log_wallet_changes(sender, instance, **kwargs):
    """
    Log wallet balance changes for audit trail.
    """
    logger.info(
        f"Wallet changed for user {instance.user.username}: "
        f"Balance: ${instance.balance:.2f}"
    )