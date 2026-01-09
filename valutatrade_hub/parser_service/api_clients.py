"""
Модуль API клиентов для Parser Service.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from .config import config  # ParserConfig с API-ключами и FIAT_CURRENCIES


class BaseApiClient(ABC):
    """Абстрактный базовый класс для всех API клиентов валютных курсов."""

    def __init__(self, name: str, timeout: int = 10, max_retries: int = 1) -> None:
        """Инициализация API клиента.

        Args:
            name: Название клиента для логирования (например, "CoinGecko")
            timeout: Таймаут запроса в секундах (по умолчанию 10)
            max_retries: Максимальное количество повторных попыток (по умолчанию 1)

        Note:
            Логгер создаётся с префиксом 'parser.' для интеграции в систему логирования.
        """
        self.name = name  # Название клиента для идентификации в логах
        self.timeout = timeout  # Таймаут запроса в секундах
        self.max_retries = max_retries  # Максимальное количество повторных попыток
        # Инициализация логгера с именем 'parser.{name}' для системного логирования
        self.logger = logging.getLogger(f"parser.{name.lower()}")

    @abstractmethod
    def fetch_rates(self) -> Dict[str, float]:
        """Получить курсы валют от API источника.

        Returns:
            Словарь с курсами в формате {"FROM_TO": rate}, например {"BTC_USD": 59337.21}

        Raises:
            ApiRequestError: При ошибках сети, таймаутах или некорректных ответах API
        """
        pass  # Абстрактный метод, требует реализации в дочерних классах

    def _make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Выполнить HTTP GET запрос с обработкой ошибок и повторными попытками.

        Args:
            url: URL адрес для выполнения запроса
            params: Словарь параметров запроса (опционально)

        Returns:
            Словарь с данными ответа API в формате JSON

        Raises:
            ApiRequestError: При ошибках сети, таймаутах или некорректном статусе ответа

        Note:
            Метод включает механизм повторных попыток при таймаутах (max_retries).
            Все ошибки преобразуются в единый тип исключения ApiRequestError.
        """
        # Итерация по количеству попыток (основная + retries)
        for attempt in range(self.max_retries + 1):
            try:
                # Логирование деталей запроса для отладки
                self.logger.debug(
                    f"Попытка запроса {attempt + 1}: {url} " f"с параметрами {params}"
                )

                # Выполнение HTTP GET запроса с таймаутом
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.timeout,
                    headers={
                        "User-Agent": "ValutaTradeHub/1.0"
                    },  # Заголовок идентификации
                )

                # Проверка HTTP статуса ответа (выбрасывает исключение при ошибке)
                response.raise_for_status()

                # Парсинг JSON ответа от API
                data = response.json()
                self.logger.debug(
                    f"Получен ответ от {self.name}: {len(str(data))} байт"
                )
                return data  # Успешный возврат данных

            except requests.exceptions.Timeout as e:
                # Обработка таймаута с логированием и повторной попыткой
                if attempt == self.max_retries:
                    # Исчерпаны все попытки - выбрасываем исключение
                    raise ApiRequestError(
                        f"{self.name}: таймаут запроса ({self.timeout} секунд)"
                    ) from e
                self.logger.warning(
                    f"Таймаут, повторная попытка " f"({attempt + 1}/{self.max_retries})"
                )

            except requests.exceptions.RequestException as e:
                # Обработка сетевых ошибок (connection error, SSL error и т.д.)
                raise ApiRequestError(f"{self.name}: сетевая ошибка - {e}") from e

            except ValueError as e:
                # Ошибка декодирования JSON (некорректный ответ API)
                raise ApiRequestError(
                    f"{self.name}: некорректный JSON в ответе - {e}"
                ) from e

        # Защита от недостижимого кода (должно быть обработано в except блоке)
        raise ApiRequestError(f"{self.name}: неожиданная ошибка в _make_request()")


class CoinGeckoClient(BaseApiClient):
    """Клиент для работы с CoinGecko API для получения курсов криптовалют."""

    # Временные константы (будут перенесены в config.py в задаче 4.1.1)
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    CRYPTO_CURRENCIES: list[str] = ["BTC", "ETH"]  # Поддерживаемые криптовалюты
    CRYPTO_ID_MAP: Dict[str, str] = {"BTC": "bitcoin", "ETH": "ethereum"}

    def __init__(self, timeout: int = 10, max_retries: int = 1) -> None:
        """Инициализация CoinGecko клиента.

        Args:
            timeout: Таймаут запроса в секундах (по умолчанию 10)
            max_retries: Максимальное количество повторных попыток (по умолчанию 1)

        Note:
            Имя клиента фиксировано как "CoinGecko" для корректного логирования.
        """
        # Вызов конструктора родительского класса с фиксированным именем
        super().__init__(name="CoinGecko", timeout=timeout, max_retries=max_retries)

    def fetch_rates(self) -> Dict[str, float]:
        """Получить курсы криптовалют от CoinGecko API.

        Returns:
            Словарь в формате {"CRYPTO_USD": rate}, например {"BTC_USD": 59337.21}

        Raises:
            ApiRequestError: При ошибках API, сети или некорректных данных

        Note:
            Метод преобразует коды валют (BTC) в CoinGecko IDs (bitcoin)
            и парсит ответ API в стандартизированный формат.
        """
        # Логирование начала операции получения курсов
        self.logger.info(f"Запрос курсов для {len(self.CRYPTO_CURRENCIES)} криптовалют")

        # 1. Преобразование кодов валют в CoinGecko IDs
        coin_ids: list[str] = []
        for crypto_code in self.CRYPTO_CURRENCIES:
            if crypto_code not in self.CRYPTO_ID_MAP:
                # Ошибка если код валюты не найден в маппинге
                raise ApiRequestError(f"Неизвестный код криптовалюты: {crypto_code}")
            # Добавление соответствующего CoinGecko ID в список
            coin_ids.append(self.CRYPTO_ID_MAP[crypto_code])

        # 2. Подготовка параметров запроса
        params: Dict[str, str] = {
            "ids": ",".join(coin_ids),  # Объединение ID через запятую
            "vs_currencies": "usd",  # Базовая валюта - USD
        }

        # 3. Выполнение запроса через родительский метод
        response_data: Dict[str, Any] = self._make_request(self.COINGECKO_URL, params)

        # 4. Валидация и преобразование данных ответа
        return self._parse_response(response_data)

    def _parse_response(self, data: Dict[str, Any]) -> Dict[str, float]:
        """Парсинг ответа CoinGecko API в стандартизированный формат.

        Args:
            data: Ответ API в формате {"bitcoin": {"usd": 59337.21}}

        Returns:
            Словарь в формате {"BTC_USD": 59337.21}

        Raises:
            ApiRequestError: При некорректной структуре ответа или данных

        Note:
            Метод выполняет обратное преобразование: bitcoin -> BTC
            и создаёт пары валют в формате BTC_USD.
        """
        rates: Dict[str, float] = {}  # Инициализация словаря для результатов

        # Проверка что ответ не пустой
        if not data:
            raise ApiRequestError("CoinGecko вернул пустой ответ")

        # Создание обратного маппинга: ID -> код валюты (bitcoin -> BTC)
        id_to_code: Dict[str, str] = {v: k for k, v in self.CRYPTO_ID_MAP.items()}

        # Итерация по всем монетам в ответе API
        for coin_id, price_data in data.items():
            # Проверка структуры данных для каждой монеты
            if not isinstance(price_data, dict) or "usd" not in price_data:
                # Логирование предупреждения о некорректной структуре
                self.logger.warning(f"Некорректная структура данных для {coin_id}")
                continue  # Пропуск этой монеты, продолжение с следующей

            # Получение значения курса из ответа
            rate: Any = price_data["usd"]

            # Валидация числового значения курса
            if not self._validate_rate(rate, coin_id):
                continue  # Пропуск невалидного курса

            # Преобразование CoinGecko ID в код валюты и создание пары
            if coin_id in id_to_code:
                crypto_code: str = id_to_code[coin_id]  # Преобразование: bitcoin -> BTC
                pair_key: str = f"{crypto_code}_USD"  # Формирование ключа: BTC_USD
                rates[pair_key] = float(rate)  # Добавление курса в результаты
                self.logger.debug(f"Получен курс: {pair_key} = {rate}")
            else:
                # Логирование предупреждения о неизвестном ID
                self.logger.warning(f"Неизвестный CoinGecko ID: {coin_id}")

        # Проверка что получены хотя бы некоторые курсы
        if not rates:
            raise ApiRequestError("Не удалось получить ни одного курса из CoinGecko")

        # Логирование успешного завершения операции
        self.logger.info(f"Получено {len(rates)} курсов от CoinGecko")
        return rates  # Возврат словаря с курсами

    def _validate_rate(self, rate: Any, coin_id: str) -> bool:
        """Валидация числового значения курса.

        Args:
            rate: Значение курса для проверки (любой тип)
            coin_id: ID монеты для логирования в случае ошибки

        Returns:
            True если курс валиден, False если нет

        Note:
            Проверяет что курс является положительным числом
            в разумных пределах для криптовалют.
        """
        try:
            # Попытка преобразовать значение в float
            rate_float: float = float(rate)

            # Проверка что курс положительный
            if rate_float <= 0:
                self.logger.warning(f"Неположительный курс для {coin_id}: {rate}")
                return False

            # Проверка реалистичных пределов (курс не превышает 1 млн USD)
            if rate_float > 1_000_000:
                self.logger.warning(f"Слишком высокий курс для {coin_id}: {rate}")
                return False

            return True  # Курс прошел все проверки

        except (ValueError, TypeError):
            # Ошибка преобразования типа (не числовое значение)
            self.logger.warning(f"Некорректный тип курса для {coin_id}: {type(rate)}")
            return False


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API для фиатных курсов (ТЗ4 4.2.3)."""

    def __init__(self, timeout: int = 10, max_retries: int = 3) -> None:
        """Инициализация с параметрами таймаута и повторов."""
        super().__init__(name="ExchangeRate", timeout=timeout, max_retries=max_retries)

    def fetch_rates(self) -> Dict[str, float]:
        """
        Получить фиатные курсы к USD из ExchangeRate-API.

        Returns:
            {EUR_USD: 0.927, RUB_USD: 98.45} - только FIAT_CURRENCIES

        Raises:
            ApiRequestError при API/сетевых ошибках.
        """
        # 1. Проверка API-ключа из конфигурации
        api_key = config.EXCHANGERATE_API_KEY
        if not api_key:
            raise ApiRequestError("EXCHANGERATE_API_KEY не установлен в config")

        # 2. Формирование полного URL запроса
        base_url = config.EXCHANGERATE_API_URL
        url = f"{base_url}/{api_key}/latest/{config.BASE_CURRENCY}"

        # 3. HTTP запрос с retry логикой (наследуется)
        api_data = self._make_request(url=url)

        # 4. Валидация ответа API
        if api_data.get("result") != "success":
            err_msg = f"API failed: {api_data.get('error-type', 'unknown')}"
            raise ApiRequestError(err_msg)

        # 5. Парсинг rates поля
        raw_rates = api_data.get("rates", {})
        result_rates: Dict[str, float] = {}

        # 6. Фильтрация по FIAT_CURRENCIES + валидация
        for fiat_code in config.FIAT_CURRENCIES:
            if fiat_code in raw_rates:
                rate_raw = raw_rates[fiat_code]
                try:
                    rate_float = float(rate_raw)
                    if rate_float > 0:  # Только положительные курсы
                        pair = f"{fiat_code}_USD"
                        result_rates[pair] = rate_float
                    else:
                        self.logger.warning(
                            f"Отрицательный курс {fiat_code}: {rate_float}"
                        )
                except (ValueError, TypeError):
                    self.logger.warning(f"Не число для {fiat_code}: {rate_raw}")

        # 7. Логирование и проверка результата
        self.logger.info(f"ExchangeRate: {len(result_rates)} курсов")
        if not result_rates:
            raise ApiRequestError("Нет валидных фиатных курсов")

        return result_rates


# Экспорт всех клиентов для удобного импорта
__all__ = [
    "BaseApiClient",
    "CoinGeckoClient",
    "ExchangeRateApiClient",  # Новый клиент для ТЗ4
]
