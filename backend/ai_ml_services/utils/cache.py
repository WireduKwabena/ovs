# ai_service/utils/cache.py
import redis
import json
import hashlib
from functools import wraps
import logging
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

class AICache:
    """Redis-based caching for AI results"""

    def __init__(self, redis_url: str = 'redis://localhost:6379/0', default_ttl: int = 3600,
                 serializer: Callable[[Any], str] = json.dumps,
                 deserializer: Callable[[str], Any] = json.loads):
        self.redis_client = None
        try:
            self.redis_client = redis.from_url(redis_url)
            # Test connection
            self.redis_client.ping()
            logger.info("Redis cache connected successfully.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to Redis cache at {redis_url}: {e}. Caching will be disabled.", exc_info=True)
            self.redis_client = None # Disable caching if connection fails
        except Exception as e:
            logger.error(f"An unexpected error occurred while connecting to Redis: {e}. Caching will be disabled.", exc_info=True)
            self.redis_client = None

        self.default_ttl = default_ttl
        self.serializer = serializer
        self.deserializer = deserializer

    def generate_cache_key(self, *args, **kwargs) -> str:
        """Generate unique cache key from arguments"""
        # Ensure all arguments are JSON serializable for consistent hashing
        try:
            key_data = self.serializer({'args': args, 'kwargs': kwargs}, sort_keys=True)
            return hashlib.md5(key_data.encode()).hexdigest()
        except TypeError as e:
            logger.warning(f"Failed to serialize cache key arguments: {e}. Using a less specific key.", exc_info=True)
            # Fallback to a simpler key if complex args are not serializable
            return hashlib.md5(f"{str(args)}-{str(kwargs)}".encode()).hexdigest()


    def cache_result(self, ttl: Optional[int] = None):
        """Decorator to cache function results"""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                if not self.redis_client:
                    return func(*args, **kwargs) # Caching disabled or failed to connect

                cache_key = f"{func.__name__}:{self.generate_cache_key(*args, **kwargs)}"

                try:
                    # Try to get from cache
                    cached = self.redis_client.get(cache_key)
                    if cached:
                        logger.debug(f"Cache hit for {cache_key}")
                        return self.deserializer(cached)
                except redis.exceptions.RedisError as e:
                    logger.error(f"Redis error during cache retrieval for {cache_key}: {e}. Executing function without cache.", exc_info=True)
                except Exception as e:
                    logger.error(f"Error deserializing cached data for {cache_key}: {e}. Executing function without cache.", exc_info=True)

                # Execute function
                result = func(*args, **kwargs)

                try:
                    # Cache result
                    self.redis_client.setex(
                        cache_key,
                        ttl or self.default_ttl,
                        self.serializer(result) # Serialize the result
                    )
                    logger.debug(f"Cache set for {cache_key}")
                except redis.exceptions.RedisError as e:
                    logger.error(f"Redis error during cache set for {cache_key}: {e}. Result not cached.", exc_info=True)
                except TypeError as e:
                    logger.error(f"Result of {func.__name__} is not serializable: {e}. Result not cached.", exc_info=True)
                except Exception as e:
                    logger.error(f"Unexpected error during cache set for {cache_key}: {e}. Result not cached.", exc_info=True)

                return result

            return wrapper

        return decorator
