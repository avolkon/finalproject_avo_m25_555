"""
Пакет Parser Service для платформы ValutaTrade Hub.

Этот пакет отвечает за получение и обновление курсов валют
из внешних API источников (CoinGecko, ExchangeRate-API).
"""

# Экспорт BaseApiClient для использования в других модулях
from .api_clients import BaseApiClient

__all__ = [
    'BaseApiClient',  # Абстрактный базовый класс для API клиентов
]

__version__ = "1.0.0"
__author__ = "ValutaTrade Hub Development Team"

