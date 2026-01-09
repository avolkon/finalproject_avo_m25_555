"""
Модуль API клиентов для Parser Service.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import requests

from valutatrade_hub.core.exceptions import ApiRequestError


class BaseApiClient(ABC):
    """Абстрактный базовый класс для всех API клиентов валютных курсов."""
    
    def __init__(
        self, 
        name: str, 
        timeout: int = 10, 
        max_retries: int = 1
    ) -> None:
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
        self.logger = logging.getLogger(f'parser.{name.lower()}')
    
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
        self, 
        url: str, 
        params: Optional[Dict[str, Any]] = None
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
                    f"Попытка запроса {attempt + 1}: {url} "
                    f"с параметрами {params}"
                )
                
                # Выполнение HTTP GET запроса с таймаутом
                response = requests.get(
                    url, 
                    params=params, 
                    timeout=self.timeout,
                    headers={'User-Agent': 'ValutaTradeHub/1.0'}  # Заголовок идентификации
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
                    f"Таймаут, повторная попытка "
                    f"({attempt + 1}/{self.max_retries})"
                )
                
            except requests.exceptions.RequestException as e:
                # Обработка сетевых ошибок (connection error, SSL error и т.д.)
                raise ApiRequestError(
                    f"{self.name}: сетевая ошибка - {e}"
                ) from e
                
            except ValueError as e:
                # Ошибка декодирования JSON (некорректный ответ API)
                raise ApiRequestError(
                    f"{self.name}: некорректный JSON в ответе - {e}"
                ) from e
        
        # Защита от недостижимого кода (должно быть обработано в except блоке)
        raise ApiRequestError(
            f"{self.name}: неожиданная ошибка в _make_request()"
        )
    
    