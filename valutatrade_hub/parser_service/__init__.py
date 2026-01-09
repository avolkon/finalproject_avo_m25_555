"""
Пакет Parser Service для платформы ValutaTrade Hub.
"""

# Импорт ApiRequestError из правильного места
from valutatrade_hub.core.exceptions import ApiRequestError  # ✅ Добавить эту строку!

# Экспорт классов API клиентов, хранилища, координатора обновления и кэша
from .api_clients import (
    BaseApiClient,  # Базовый абстрактный клиент
    CoinGeckoClient,  # Криптовалюты (реализовано)
    ExchangeRateApiClient,  # Фиатные валюты (новое)
)

from .storage import HistoryStorage, StorageError
from .updater import RatesUpdater, UpdateStatus, UpdateResult
from .rates_cache import RatesCache, CacheError, RateInfo
from .scheduler import SchedulerStatus, RatesScheduler  # Новые импорты

__all__ = [
    "ApiRequestError",  # Ошибки API
    "BaseApiClient",  # Базовый клиент API
    "CoinGeckoClient",  # CoinGecko крипто
    "ExchangeRateApiClient",  # ExchangeRate фиат
    "HistoryStorage",
    "StorageError",
    "RatesUpdater",
    "UpdateStatus",
    "UpdateResult",
    "RatesCache",
    "CacheError",
    "RateInfo",
    "SchedulerStatus",  # Статус планировщика (новая)
    "RatesScheduler",  # Планировщик обновлений (новая)
]

__version__ = "1.0.0"
__author__ = "ValutaTrade Hub Development Team"
