"""
Base API client with caching and rate limiting
"""
import os
import time
import json
import hashlib
from pathlib import Path
from typing import Optional, Any
from datetime import datetime, timedelta
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class APICache:
    """Simple file-based cache for API responses"""

    def __init__(self, cache_dir: str = "data/cache", default_ttl: int = 900):
        """
        Args:
            cache_dir: Directory to store cache files
            default_ttl: Default time-to-live in seconds (default 15 minutes)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl
        self.enabled = os.getenv("CACHE_ENABLED", "True").lower() == "true"

    def _get_cache_key(self, key: str) -> str:
        """Generate cache file path from key"""
        hash_key = hashlib.md5(key.encode()).hexdigest()
        return str(self.cache_dir / f"{hash_key}.json")

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Get value from cache if not expired"""
        if not self.enabled:
            return None

        cache_file = self._get_cache_key(key)
        if not os.path.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Check expiration
            cached_time = datetime.fromisoformat(data['timestamp'])
            ttl = ttl or self.default_ttl
            if datetime.utcnow() - cached_time > timedelta(seconds=ttl):
                os.remove(cache_file)
                return None

            logger.debug(f"Cache hit for key: {key}")
            return data['value']

        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    def set(self, key: str, value: Any):
        """Store value in cache"""
        if not self.enabled:
            return

        cache_file = self._get_cache_key(key)
        try:
            data = {
                'timestamp': datetime.utcnow().isoformat(),
                'value': value
            }
            with open(cache_file, 'w') as f:
                json.dump(data, f)
            logger.debug(f"Cached value for key: {key}")
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def clear(self):
        """Clear all cache files"""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                os.remove(cache_file)
            except Exception as e:
                logger.error(f"Error clearing cache file {cache_file}: {e}")


class RateLimiter:
    """Simple rate limiter"""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.call_times = []

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove calls older than 1 minute
        self.call_times = [t for t in self.call_times if now - t < 60]

        if len(self.call_times) >= self.calls_per_minute:
            # Calculate wait time
            oldest_call = min(self.call_times)
            wait_time = 60 - (now - oldest_call)
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)

        self.call_times.append(time.time())


def cached(ttl: Optional[int] = None):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Generate cache key from function name and arguments
            key_parts = [func.__name__] + [str(arg) for arg in args]
            key_parts += [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = ":".join(key_parts)

            # Try cache first
            if hasattr(self, 'cache'):
                cached_value = self.cache.get(cache_key, ttl)
                if cached_value is not None:
                    return cached_value

            # Call function
            result = func(self, *args, **kwargs)

            # Cache result
            if hasattr(self, 'cache') and result is not None:
                self.cache.set(cache_key, result)

            return result
        return wrapper
    return decorator


class BaseAPIClient:
    """Base class for API clients"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 900,
        rate_limit: int = 60
    ):
        self.api_key = api_key
        self.cache = APICache(default_ttl=cache_ttl) if cache_enabled else None
        self.rate_limiter = RateLimiter(calls_per_minute=rate_limit)
        self.session = None

    def _make_request(self, url: str, params: Optional[dict] = None) -> dict:
        """Make HTTP request with rate limiting"""
        import requests

        self.rate_limiter.wait_if_needed()

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def health_check(self) -> bool:
        """Check if API is accessible"""
        raise NotImplementedError
