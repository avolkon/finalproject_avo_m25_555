"""Модуль иерархии валют для платформы ValutaTrade Hub."""

from typing import Optional
from abc import ABC, abstractmethod


class Currency(ABC):
    """Базовый абстрактный класс для всех типов валют."""

    def __init__(self, code: str, name: str):
        """Инициализация валюты с валидацией входных данных.

        Args:
            code: Код валюты (2-5 символов, без пробелов)
            name: Человекочитаемое название валюты

        Raises:
            ValueError: При некорректных параметрах code или name
        """
        # Нормализация кода валюты в верхний регистр
        code = code.upper().strip()

        # Валидация длины кода валюты (2-5 символов)
        if not (2 <= len(code) <= 5):
            raise ValueError(f"Код валюты должен быть 2-5 символов: {code}")

        # Валидация отсутствия пробелов в коде
        if " " in code:
            raise ValueError(f"Код валюты не должен содержать пробелы: {code}")

        # Валидация непустого названия валюты
        if not name or not name.strip():
            raise ValueError("Название валюты не может быть пустым")

        # Установка приватных атрибутов
        self._code = code
        self._name = name.strip()

    @property
    def code(self) -> str:
        """Получить код валюты в верхнем регистре.

        Returns:
            Код валюты (например, 'USD', 'BTC')
        """
        return self._code

    @property
    def name(self) -> str:
        """Получить человекочитаемое название валюты.

        Returns:
            Название валюты (например, 'US Dollar', 'Bitcoin')
        """
        return self._name

    @abstractmethod
    def get_display_info(self) -> str:
        """Получить строковое представление для UI/логов.
        Returns:
            Форматированная строка с информацией о валюте
        """
        pass

    def __repr__(self) -> str:
        """Официальное строковое представление для отладки.
        Returns:
            Строка в формате: ClassName(code='CODE', name='NAME')
        """
        return f"{self.__class__.__name__}(code='{self.code}', name='{self.name}')"

    def __str__(self) -> str:
        """Неформальное строковое представление для пользователя.
        Returns:
            Результат вызова get_display_info()
        """
        return self.get_display_info()


class FiatCurrency(Currency):
    """Класс фиатной валюты (государственные деньги)."""

    def __init__(self, code: str, name: str, issuing_country: str):
        """Инициализация фиатной валюты.
        Args:
            code: Код валюты (например, 'USD', 'EUR', 'RUB')
            name: Название валюты (например, 'US Dollar')
            issuing_country: Страна или зона эмиссии (например, 'United States')
        Raises:
            ValueError: Если issuing_country пустое
        """
        # Вызов конструктора родительского класса
        super().__init__(code, name)

        # Валидация непустой страны эмиссии
        if not issuing_country or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")

        # Установка приватного атрибута страны эмиссии
        self._issuing_country = issuing_country.strip()

    @property
    def issuing_country(self) -> str:
        """Получить страну или зону эмиссии валюты.
        Returns:
            Название страны эмиссии
        """
        return self._issuing_country

    def get_display_info(self) -> str:
        """Получить строковое представление фиатной валюты.
        Returns:
            Строка формата: "[FIAT] USD — US Dollar (Issuing: United States)"
        """
        # Форматирование строки согласно требованиям ТЗ
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Класс криптовалюты (цифровые активы)."""

    def __init__(
        self, code: str, name: str, algorithm: str, market_cap: Optional[float] = None
    ):
        """Инициализация криптовалюты.
        Args:
            code: Код валюты (например, 'BTC', 'ETH')
            name: Название валюты (например, 'Bitcoin')
            algorithm: Алгоритм консенсуса (например, 'SHA-256')
            market_cap: Рыночная капитализация (опционально)
        Raises:
            ValueError: Если algorithm пустой
        """
        # Вызов конструктора родительского класса
        super().__init__(code, name)

        # Валидация непустого алгоритма
        if not algorithm or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")

        # Установка приватных атрибутов
        self._algorithm = algorithm.strip()
        self._market_cap = market_cap

    @property
    def algorithm(self) -> str:
        """Получить алгоритм консенсуса криптовалюты.
        Returns:
            Название алгоритма
        """
        return self._algorithm

    @property
    def market_cap(self) -> Optional[float]:
        """Получить рыночную капитализацию криптовалюты.
        Returns:
            Рыночная капитализация или None, если неизвестна
        """
        return self._market_cap

    def get_display_info(self) -> str:
        """Получить строковое представление криптовалюты.
        Returns:
            Строка формата: "[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)"
        """
        # Базовая часть строки с кодом, названием и алгоритмом
        base_info = f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}"

        # Добавление информации о рыночной капитализации, если известна
        if self.market_cap is not None:
            # Форматирование большой капитализации в научной нотации
            if self.market_cap >= 1e6:
                mcap_str = f"{self.market_cap:.2e}"
            else:
                mcap_str = f"{self.market_cap:,.2f}"

            return f"{base_info}, MCAP: {mcap_str})"

        # Возврат строки без информации о капитализации
        return f"{base_info})"

    # Приватный реестр данных поддерживаемых валют


_CURRENCY_REGISTRY = {
    "USD": {
        "type": "fiat",  # Тип валюты: фиатная
        "name": "US Dollar",  # Название валюты
        "issuing_country": "United States",  # Страна эмиссии
    },
    "EUR": {
        "type": "fiat",  # Тип валюты: фиатная
        "name": "Euro",  # Название валюты
        "issuing_country": "Eurozone",  # Зона эмиссии
    },
    "RUB": {
        "type": "fiat",  # Тип валюты: фиатная
        "name": "Russian Ruble",  # Название валюты
        "issuing_country": "Russia",  # Страна эмиссии
    },
    "BTC": {
        "type": "crypto",  # Тип валюты: криптовалюта
        "name": "Bitcoin",  # Название валюты
        "algorithm": "SHA-256",  # Алгоритм консенсуса
        "market_cap": 1.12e12,  # Рыночная капитализация
    },
    "ETH": {
        "type": "crypto",  # Тип валюты: криптовалюта
        "name": "Ethereum",  # Название валюты
        "algorithm": "Ethash",  # Алгоритм консенсуса
        "market_cap": 4.5e11,  # Рыночная капитализация
    },
}

# Кеш созданных объектов валют для избежания повторного создания
_CURRENCY_CACHE = {}


def get_currency(code: str) -> Currency:
    """Фабричный метод для получения объекта валюты по коду.

    Args:
        code: Код валюты в любом регистре (например, 'usd', 'BTC')

    Returns:
        Объект Currency (FiatCurrency или CryptoCurrency)

    Raises:
        CurrencyNotFoundError: Если код валюты не поддерживается системой
    """
    # Нормализация кода валюты: верхний регистр, удаление пробелов
    normalized_code = code.upper().strip()

    # Проверка наличия валюты в реестре поддерживаемых
    if normalized_code not in _CURRENCY_REGISTRY:
        # Ленивый импорт для избежания циклических зависимостей
        from .exceptions import CurrencyNotFoundError

        raise CurrencyNotFoundError(normalized_code)

    # Проверка наличия валюты в кеше созданных объектов
    if normalized_code in _CURRENCY_CACHE:
        return _CURRENCY_CACHE[normalized_code]

    # Получение данных валюты из реестра
    currency_data = _CURRENCY_REGISTRY[normalized_code]

    # Создание объекта в зависимости от типа валюты
    if currency_data["type"] == "fiat":
        # Создание объекта фиатной валюты
        currency = FiatCurrency(
            code=normalized_code,
            name=currency_data["name"],
            issuing_country=currency_data["issuing_country"],
        )
    else:
        # Создание объекта криптовалюты (тип 'crypto')
        currency = CryptoCurrency(
            code=normalized_code,
            name=currency_data["name"],
            algorithm=currency_data["algorithm"],
            market_cap=currency_data.get("market_cap"),  # Опциональный параметр
        )

    # Сохранение созданного объекта в кеше для повторного использования
    _CURRENCY_CACHE[normalized_code] = currency

    # Возврат созданного объекта валюты
    return currency


def get_supported_currencies() -> list[str]:
    """Получить список кодов всех поддерживаемых валют.

    Returns:
        Список строк с кодами валют в верхнем регистре
    """
    # Возврат ключей реестра в виде списка
    return list(_CURRENCY_REGISTRY.keys())
