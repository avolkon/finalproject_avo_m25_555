"""
Пакет Parser Service для платформы ValutaTrade Hub.
"""

# Импорт ApiRequestError из правильного места
from valutatrade_hub.core.exceptions import ApiRequestError  # ✅ Добавить эту строку!

# Экспорт классов API клиентов, хранилища, координатора обновления и кэша
from .api_clients import BaseApiClient, CoinGeckoClient
from .storage import HistoryStorage, StorageError
from .updater import RatesUpdater, UpdateStatus, UpdateResult
from .rates_cache import RatesCache, CacheError, RateInfo

__all__ = [
    'ApiRequestError',    # ✅ Добавить в экспорт (если используется в API)
    'BaseApiClient',    # Абстрактный базовый класс для API клиентов
    'CoinGeckoClient',  # Конкретная реализация для CoinGecko API
    'HistoryStorage',   # Хранилище исторических данных о курсах
    'StorageError',     # Исключение для ошибок работы хранилища
    'RatesUpdater',     # Координатор процесса обновления курсов
    'UpdateStatus',     # Перечисление статусов обновления
    'UpdateResult',     # Класс результата операции обновления
    'RatesCache',       # Класс для управления кэшем актуальных курсов
    'CacheError',       # Исключение для ошибок работы кэша
    'RateInfo',         # Структурированная информация о курсе
]

__version__ = "1.0.0"
__author__ = "ValutaTrade Hub Development Team"

