"""Core services: users, wallets, transactions."""

import functools
import time
from typing import Any


def log_action(func):
    """Декоратор логирования."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        print(f"{func.__name__} took {time.time() - start:.2f}s")
        return result
    return wrapper


def confirm_user(func):
    """Декоратор подтверждения рискованных операций."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        confirm = input("Подтвердить операцию? (y/n): ")
        if confirm.lower() == 'y':
            return func(*args, **kwargs)
        return None
    return wrapper


# Замыкание для кэширования курсов (в Parser)
def create_rate_cache(ttl: int = 60):
    """Фабрика кэша для курсов."""
    cache: dict[str, dict[str, Any]] = {}
    
    def get_rate(symbol: str) -> float | None:
        now = time.time()
        if symbol in cache and now - cache[symbol]["ts"] < ttl:
            return cache[symbol]["rate"]
        # TODO: запрос API
        return None
    
    def set_rate(symbol: str, rate: float):
        cache[symbol] = {"rate": rate, "ts": now}
    
    return get_rate, set_rate
