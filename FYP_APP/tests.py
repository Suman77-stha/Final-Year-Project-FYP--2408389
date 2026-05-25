"""
Tests for FYP_APP

This module contains unit tests for the TradeVision AI application.
"""

from django.test import TestCase
from django.contrib.auth.models import User
from .models import Wallet, Portfolio, Transaction, Watchlist


class WalletModelTest(TestCase):
    """Test cases for Wallet model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_wallet_creation_on_user_creation(self):
        """Test that wallet is automatically created when user is created."""
        self.assertTrue(hasattr(self.user, 'wallet'))
        self.assertEqual(self.user.wallet.balance, 100000.00)


class PortfolioModelTest(TestCase):
    """Test cases for Portfolio model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_portfolio_creation(self):
        """Test portfolio creation."""
        portfolio = Portfolio.objects.create(
            user=self.user,
            symbol='AAPL',
            quantity=10,
            average_price=150.00
        )
        self.assertEqual(portfolio.symbol, 'AAPL')
        self.assertEqual(portfolio.quantity, 10)


class TransactionModelTest(TestCase):
    """Test cases for Transaction model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_transaction_creation(self):
        """Test transaction creation."""
        transaction = Transaction.objects.create(
            user=self.user,
            symbol='AAPL',
            transaction_type='BUY',
            quantity=10,
            price=150.00
        )
        self.assertEqual(transaction.transaction_type, 'BUY')
        self.assertEqual(transaction.quantity, 10)


class WatchlistModelTest(TestCase):
    """Test cases for Watchlist model."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_watchlist_creation(self):
        """Test watchlist creation."""
        watchlist = Watchlist.objects.create(
            user=self.user,
            symbol='AAPL'
        )
        self.assertEqual(watchlist.symbol, 'AAPL')