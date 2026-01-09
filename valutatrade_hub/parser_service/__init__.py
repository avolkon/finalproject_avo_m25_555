"""
Пакет Parser Service для платформы ValutaTrade Hub.

Этот пакет отвечает за получение и обновление курсов валют
из внешних API источников (CoinGecko, ExchangeRate-API).
"""

# Экспорт классов API клиентов, хранилища и координатора обновления
from .api_clients import BaseApiClient, CoinGeckoClient
from .storage import HistoryStorage, StorageError
from .updater import RatesUpdater, UpdateStatus, UpdateResult

__all__ = [
    'BaseApiClient',    # Абстрактный базовый класс для API клиентов
    'CoinGeckoClient',  # Конкретная реализация для CoinGecko API
    'HistoryStorage',   # Хранилище исторических данных о курсах
    'StorageError',     # Исключение для ошибок работы хранилища
    'RatesUpdater',     # Координатор процесса обновления курсов
    'UpdateStatus',     # Перечисление статусов обновления
    'UpdateResult',     # Класс результата операции обновления
]

__version__ = "1.0.0"
__author__ = "ValutaTrade Hub Development Team"

