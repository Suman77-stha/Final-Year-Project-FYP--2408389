"""
Rate Limiting Middleware for TradeVision AI

Implements Redis-backed rate limiting to prevent abuse and DoS attacks.
"""

import logging
import time
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import hashlib

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """
    Rate limiting middleware using Redis cache.
    
    Limits requests based on IP address and user ID.
    Different limits apply to different endpoint types.
    """
    
    # Rate limits (requests per minute)
    DEFAULT_LIMIT = 100
    AUTH_LIMIT = 10
    API_LIMIT = 60
    ML_PREDICTION_LIMIT = 30
    
    # Rate limit durations (in seconds)
    DURATION = 60  # 1 minute
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if (
            request.path.startswith('/static/')
            or request.path == '/health/'
            or request.path == '/favicon.ico'
        ):
            return self.get_response(request)

        # Get client identifier (IP or user ID)
        client_id = self.get_client_id(request)
        
        # Determine rate limit based on endpoint
        limit = self.get_rate_limit(request)
        
        # Check rate limit
        request_count = self.increment_and_get_request_count(client_id)
        if request_count > limit:
            logger.warning(f"Rate limit exceeded for {client_id} on {request.path}")
            return JsonResponse(
                {
                    'error': 'Rate limit exceeded',
                    'message': f'Maximum {limit} requests per minute allowed',
                    'retry_after': self.get_retry_after(client_id)
                },
                status=429
            )

        return self.get_response(request)
    
    def get_client_id(self, request):
        """
        Get client identifier from request.
        Uses user ID if authenticated, otherwise IP address.
        """
        if request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # Get IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        
        # Hash IP for privacy
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        return f"ip:{ip_hash}"
    
    def get_rate_limit(self, request):
        """
        Determine rate limit based on endpoint type.
        """
        path = request.path
        
        # Authentication endpoints - stricter limit
        if '/sign-in' in path or '/sign-up' in path or '/otp' in path:
            return self.AUTH_LIMIT
        
        # ML prediction endpoints - stricter limit
        if '/api/stock-prediction' in path or '/api/watchlist-ai' in path:
            return self.ML_PREDICTION_LIMIT
        
        # API endpoints
        if path.startswith('/api/'):
            return self.API_LIMIT
        
        # Default limit
        return self.DEFAULT_LIMIT
    
    def increment_and_get_request_count(self, client_id):
        """
        Increment request counter and return current count with minimal cache ops.
        """
        cache_key = f"rate_limit:{client_id}"

        if cache.add(cache_key, 1, self.DURATION):
            return 1

        try:
            return cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, self.DURATION)
            return 1
    
    def get_retry_after(self, client_id):
        """
        Get seconds until rate limit resets.
        """
        cache_key = f"rate_limit:{client_id}"
        # Some cache backends (e.g. LocMemCache) do not support ttl().
        ttl_func = getattr(cache, "ttl", None)
        if callable(ttl_func):
            ttl = ttl_func(cache_key)
            return max(0, ttl if ttl is not None else 0)
        return self.DURATION


class SlowRequestMiddleware:
    """
    Middleware to detect and block slow requests (potential DoS).
    """
    
    MAX_REQUEST_TIME = 30  # seconds
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        request_time = time.time() - start_time
        
        # Log slow requests
        if request_time > self.MAX_REQUEST_TIME:
            logger.warning(
                f"Slow request detected: {request.path} took {request_time:.2f}s "
                f"from {self.get_client_ip(request)}"
            )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')


class SecurityHeadersMiddleware:
    """
    Add security headers to all responses.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        response = self.get_response(request)
        
        # Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        # Content Security Policy (basic)
        if not settings.DEBUG:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
                "font-src 'self' https://fonts.gstatic.com https://unpkg.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.stockdata.org https://cdn.jsdelivr.net; "
            )
        
        return response


class RequestLoggingMiddleware:
    """
    Log all requests for security auditing.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        if (
            request.path.startswith('/static/')
            or request.path == '/health/'
            or request.path.startswith('/FYP/Sign_In/')
            or request.path.startswith('/FYP/Sign_Up/')
        ):
            return self.get_response(request)

        # Log request details
        logger.info(
            f"Request: {request.method} {request.path} | "
            f"IP: {self.get_client_ip(request)} | "
            f"User: {request.user.username if request.user.is_authenticated else 'anonymous'} | "
            f"User-Agent: {request.META.get('HTTP_USER_AGENT', 'unknown')[:100]}"
        )
        
        response = self.get_response(request)
        
        # Log response
        logger.info(
            f"Response: {response.status_code} for {request.method} {request.path}"
        )
        
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
