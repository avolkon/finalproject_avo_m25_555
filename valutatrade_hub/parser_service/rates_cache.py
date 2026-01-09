"""
Модуль RatesCache - управление кэшем актуальных курсов валют (rates.json).
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from valutatrade_hub.infra.settings import SettingsLoader


class CacheError(Exception):
    """Исключение для ошибок работы кэша курсов валют.

    Attributes:
        message: Текстовое описание ошибки
        operation: Название операции вызвавшей ошибку
    """

    def __init__(self, message: str, operation: str = "unknown") -> None:
        """Инициализация исключения кэша.

        Args:
            message: Текстовое описание ошибки
            operation: Название операции (например, "get_rate")
        """
        # Формирование полного сообщения об ошибке
        full_message: str = f"Ошибка кэша в операции {operation}: {message}"
        super().__init__(full_message)
        self.operation = operation  # Сохранение операции для отладки


@dataclass
class RateInfo:
    """Структурированная информация о курсе валюты."""

    rate: float  # Значение курса
    updated_at: str  # Время обновления в ISO формате
    source: str  # Источник данных
    is_fresh: bool  # Флаг свежести данных
    currency_pair: str  # Валютная пара (например, "BTC_USD")


class RatesCache:
    """Класс для управления кэшем актуальных курсов валют (rates.json)."""

    # Константа версии формата данных кэша
    CACHE_VERSION: str = "1.0"

    # Списки валют для классификации по типу
    FIAT_CURRENCIES: List[str] = ["USD", "EUR", "RUB"]
    CRYPTO_CURRENCIES: List[str] = ["BTC", "ETH"]

    def __init__(self, filepath: str = "data/rates.json") -> None:
        """Инициализация кэша курсов валют.

        Args:
            filepath: Путь к файлу кэша rates.json (по умолчанию data/rates.json)

        Raises:
            CacheError: При ошибках создания директории или инициализации

        Note:
            Автоматически создает файл кэша если он не существует.
            Загружает настройки TTL из SettingsLoader для проверки свежести.
        """
        self.filepath: Path = Path(filepath)  # Преобразование пути в объект Path
        # Инициализация логгера для операций кэша
        self.logger: logging.Logger = logging.getLogger("parser.cache")

        # Загрузка настроек TTL из SettingsLoader
        self.settings: SettingsLoader = SettingsLoader()

        # Создание директории если она не существует
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Директория создана/проверена: {self.filepath.parent}")
        except Exception as e:
            # Ошибка создания директории
            raise CacheError(
                f"Не удалось создать директорию: {e}", operation="init"
            ) from e

        # Инициализация данных кэша в памяти
        self._cache_data: Optional[Dict[str, Any]] = None
        self.logger.info(f"Кэш инициализирован: {self.filepath}")

    def get_rate(self, from_currency: str, to_currency: str) -> Optional[RateInfo]:
        """Получить информацию о курсе валюты из кэша.

        Args:
            from_currency: Исходная валюта (например, "BTC")
            to_currency: Целевая валюта (например, "USD")

        Returns:
            RateInfo с данными о курсе или None если пара не найдена

        Raises:
            CacheError: При ошибках загрузки или валидации данных кэша

        Note:
            Выполняет проверку свежести данных через is_fresh().
            Возвращает структурированную информацию о курсе.
        """
        # Нормализация кодов валют
        from_norm: str = from_currency.upper().strip()
        to_norm: str = to_currency.upper().strip()

        # Формирование ключа валютной пары
        pair_key: str = f"{from_norm}_{to_norm}"

        # Логирование запроса курса
        self.logger.debug(f"Запрос курса для пары: {pair_key}")

        # 1. Загрузка данных кэша если они еще не загружены
        if self._cache_data is None:
            self._load_cache()

        # Убедимся что данные кэша загружены
        if self._cache_data is None:
            raise CacheError("Не удалось загрузить данные кэша", operation="get_rate")

        # 2. Поиск пары в кэше
        pairs_data: Dict[str, Any] = self._cache_data.get("pairs", {})
        if pair_key not in pairs_data:
            # Пара не найдена в кэше
            self.logger.debug(f"Пара не найдена в кэше: {pair_key}")
            return None

        # 3. Получение данных пары из кэша
        pair_data: Dict[str, Any] = pairs_data[pair_key]

        # 4. Проверка свежести данных
        is_fresh: bool = self.is_fresh(pair_key, pair_data.get("updated_at", ""))

        # 5. Создание структурированной информации о курсе
        rate_info: RateInfo = RateInfo(
            rate=float(pair_data.get("rate", 0.0)),
            updated_at=pair_data.get("updated_at", ""),
            source=pair_data.get("source", "unknown"),
            is_fresh=is_fresh,
            currency_pair=pair_key,
        )

        # Логирование результата
        freshness_status: str = "свежий" if is_fresh else "устаревший"
        self.logger.debug(
            f"Найден курс для {pair_key}: {rate_info.rate}, "
            f"статус: {freshness_status}"
        )

        return rate_info  # Возврат структурированной информации о курсе

    def update_rate(
        self, pair: str, rate: float, source: str, timestamp: Optional[str] = None
    ) -> bool:
        """Обновить курс в кэше если данные свежее текущих.

        Args:
            pair: Валютная пара (например, "BTC_USD")
            rate: Значение курса
            source: Источник данных (например, "CoinGecko")
            timestamp: Время обновления (по умолчанию текущее время)

        Returns:
            True если курс был обновлен, False если данные устарели

        Raises:
            CacheError: При ошибках валидации данных или записи в кэш
            ValueError: При некорректных входных данных

        Note:
            Сравнивает timestamp с текущими данными и обновляет только если свежее.
            Выполняет атомарную запись обновленных данных в файл.
        """
        # Валидация входных параметров
        if not pair or "_" not in pair:
            raise ValueError(f"Некорректный формат валютной пары: {pair}")

        if rate <= 0:
            raise ValueError(f"Некорректное значение курса: {rate}")

        if not source or not source.strip():
            raise ValueError("Источник данных не может быть пустым")

        # Использование текущего времени если timestamp не указан
        update_time: str = timestamp or datetime.now().isoformat() + "Z"

        # Логирование операции обновления
        self.logger.debug(
            f"Обновление курса для {pair}: {rate} от {source} " f"в {update_time}"
        )

        # 1. Загрузка данных кэша если они еще не загружены
        if self._cache_data is None:
            self._load_cache()

        # Убедимся что данные кэша загружены
        if self._cache_data is None:
            raise CacheError(
                "Не удалось загрузить данные кэша", operation="update_rate"
            )

        # 2. Получение текущих данных пары (если есть)
        pairs_data: Dict[str, Any] = self._cache_data.get("pairs", {})
        current_pair_data: Optional[Dict[str, Any]] = pairs_data.get(pair)

        # 3. Проверка нужно ли обновлять данные
        should_update: bool = True  # По умолчанию обновляем

        if current_pair_data is not None:
            # Есть текущие данные - проверяем свежесть
            current_time_str: str = current_pair_data.get("updated_at", "")

            try:
                # Парсинг времени для сравнения
                current_time: datetime = datetime.fromisoformat(
                    current_time_str.replace("Z", "+00:00")
                )
                new_time: datetime = datetime.fromisoformat(
                    update_time.replace("Z", "+00:00")
                )

                # Обновляем только если новые данные свежее
                should_update = new_time > current_time

                if not should_update:
                    self.logger.debug(
                        f"Данные для {pair} не обновлены: "
                        f"новые данные устарели ({new_time} <= {current_time})"
                    )

            except (ValueError, TypeError):
                # Некорректный формат времени - обновляем в любом случае
                self.logger.warning(
                    f"Некорректный формат времени для пары {pair}, "
                    f"обновление выполняется"
                )
                should_update = True

        # 4. Обновление данных если нужно
        if should_update:
            # Создание новых данных пары
            new_pair_data: Dict[str, Any] = {
                "rate": float(rate),
                "updated_at": update_time,
                "source": source.strip(),
            }

            # Обновление данных в кэше
            pairs_data[pair] = new_pair_data
            self._cache_data["pairs"] = pairs_data
            self._cache_data["last_refresh"] = datetime.now().isoformat() + "Z"

            # 5. Атомарная запись обновленных данных в файл
            self._atomic_write(self._cache_data)

            self.logger.info(f"Курс обновлен: {pair} = {rate} от {source}")
            return True  # Данные обновлены

        return False  # Данные не обновлены (устарели)

    def bulk_update(self, rates: Dict[str, Dict[str, Any]]) -> int:
        """Массовое обновление курсов в кэше.

        Args:
            rates: Словарь с данными курсов {pair: {"rate": float, "source": str, "updated_at": str}}

        Returns:
            Количество обновленных курсов

        Raises:
            CacheError: При ошибках валидации данных или записи в кэш
            ValueError: При некорректных входных данных

        Note:
            Обновляет только те курсы, которые свежее текущих.
            Выполняет атомарное сохранение всех изменений.
        """
        # Логирование начала массового обновления
        self.logger.info(f"Массовое обновление {len(rates)} курсов")

        # Проверка что есть данные для обновления
        if not rates:
            self.logger.warning("Попытка массового обновления пустым словарем")
            return 0

        # 1. Загрузка данных кэша если они еще не загружены
        if self._cache_data is None:
            self._load_cache()

        # Убедимся что данные кэша загружены
        if self._cache_data is None:
            raise CacheError(
                "Не удалось загрузить данные кэша", operation="bulk_update"
            )

        pairs_data: Dict[str, Any] = self._cache_data.get("pairs", {})
        updated_count: int = 0  # Счетчик обновленных курсов

        # 2. Обработка каждого курса для обновления
        for pair, new_data in rates.items():
            try:
                # Валидация формата пары
                if "_" not in pair:
                    self.logger.warning(f"Некорректный формат пары: {pair}")
                    continue

                # Извлечение данных из словаря
                rate: Any = new_data.get("rate")
                source: Optional[str] = new_data.get("source")
                timestamp: Optional[str] = new_data.get("updated_at")

                # Валидация обязательных полей
                if rate is None or source is None:
                    self.logger.warning(
                        f"Отсутствуют обязательные поля для пары {pair}"
                    )
                    continue

                # Преобразование rate в float
                try:
                    rate_float: float = float(rate)
                    if rate_float <= 0:
                        self.logger.warning(
                            f"Неположительный курс для пары {pair}: {rate_float}"
                        )
                        continue
                except (ValueError, TypeError):
                    self.logger.warning(
                        f"Некорректный тип курса для пары {pair}: {rate}"
                    )
                    continue

                # Использование текущего времени если timestamp не указан
                update_time: str = timestamp or datetime.now().isoformat() + "Z"

                # 3. Проверка нужно ли обновлять данные
                should_update: bool = True
                current_pair_data: Optional[Dict[str, Any]] = pairs_data.get(pair)

                if current_pair_data is not None:
                    # Есть текущие данные - проверяем свежесть
                    current_time_str: str = current_pair_data.get("updated_at", "")

                    try:
                        # Парсинг времени для сравнения
                        current_time: datetime = datetime.fromisoformat(
                            current_time_str.replace("Z", "+00:00")
                        )
                        new_time: datetime = datetime.fromisoformat(
                            update_time.replace("Z", "+00:00")
                        )

                        # Обновляем только если новые данные свежее
                        should_update = new_time > current_time

                    except (ValueError, TypeError):
                        # Некорректный формат времени - обновляем
                        should_update = True

                # 4. Обновление данных если нужно
                if should_update:
                    # Создание новых данных пары
                    new_pair_data: Dict[str, Any] = {
                        "rate": rate_float,
                        "updated_at": update_time,
                        "source": source.strip(),
                    }

                    # Обновление в памяти
                    pairs_data[pair] = new_pair_data
                    updated_count += 1

                    self.logger.debug(f"Подготовлено обновление для пары: {pair}")

            except Exception as e:
                # Ошибка обработки конкретной пары - логируем и продолжаем
                self.logger.error(f"Ошибка обработки пары {pair}: {e}", exc_info=False)
                continue

        # 5. Сохранение обновлений если есть что сохранять
        if updated_count > 0:
            # Обновление структуры данных кэша
            self._cache_data["pairs"] = pairs_data
            self._cache_data["last_refresh"] = datetime.now().isoformat() + "Z"

            # Атомарная запись обновленных данных
            self._atomic_write(self._cache_data)

            self.logger.info(
                f"Массовое обновление завершено: {updated_count} курсов обновлено, "
                f"всего пар в кэше: {len(pairs_data)}"
            )
        else:
            self.logger.info("Массовое обновление: нет новых данных для обновления")

        return updated_count  # Возврат количества обновленных курсов

    def get_all_rates(self) -> Dict[str, Dict[str, Any]]:
        """Получить все актуальные курсы из кэша.

        Returns:
            Словарь со всеми курсами в формате {pair: {rate, updated_at, source}}

        Raises:
            CacheError: При ошибках загрузки данных кэша

        Note:
            Возвращает копию данных для защиты от модификации.
            Данные уже загружены и проверены.
        """
        # 1. Загрузка данных кэша если они еще не загружены
        if self._cache_data is None:
            self._load_cache()

        # Убедимся что данные кэша загружены
        if self._cache_data is None:
            raise CacheError(
                "Не удалось загрузить данные кэша", operation="get_all_rates"
            )

        # 2. Возврат копии данных пар (защита от модификации)
        pairs_data: Dict[str, Dict[str, Any]] = self._cache_data.get("pairs", {}).copy()

        # Логирование операции
        self.logger.debug(f"Получено {len(pairs_data)} курсов из кэша")

        return pairs_data  # Возврат копии данных

    def is_fresh(self, currency_pair: str, timestamp: str) -> bool:
        """Проверить свежесть курса по TTL из настроек.

        Args:
            currency_pair: Валютная пара (например, "BTC_USD")
            timestamp: Время обновления в ISO формате

        Returns:
            True если курс свежий, False если устарел

        Note:
            Использует TTL настройки из SettingsLoader для разных типов валют.
            Возвращает False при некорректном формате timestamp.
        """
        # Проверка на пустой timestamp
        if not timestamp or timestamp == "N/A":
            self.logger.debug(f"Пустой timestamp для пары {currency_pair}")
            return False

        try:
            # Парсинг timestamp из строки ISO формата
            update_time: datetime = datetime.fromisoformat(
                timestamp.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            # Некорректный формат timestamp
            self.logger.warning(
                f"Некорректный формат timestamp для пары {currency_pair}"
            )
            return False

        # Определение типа валюты для выбора TTL
        try:
            base_currency: str = currency_pair.split("_")[0].upper()
        except (IndexError, AttributeError):
            # Некорректный формат валютной пары
            self.logger.warning(f"Некорректный формат валютной пары: {currency_pair}")
            return False

        # Получение TTL из настроек в зависимости от типа валюты
        if base_currency in self.FIAT_CURRENCIES:
            # Фиатные валюты
            ttl_seconds: int = self.settings.get("rates_ttl_fiat_seconds", 3600)
        elif base_currency in self.CRYPTO_CURRENCIES:
            # Криптовалюты
            ttl_seconds = self.settings.get("rates_ttl_crypto_seconds", 300)
        else:
            # Другие валюты (по умолчанию)
            ttl_seconds = self.settings.get("rates_ttl_default_seconds", 1800)

        # Расчет времени, прошедшего с обновления
        current_time: datetime = datetime.now()
        time_since_update: float = (current_time - update_time).total_seconds()

        # Проверка свежести (прошло ли меньше времени чем TTL)
        is_fresh_result: bool = time_since_update <= ttl_seconds

        # Логирование результата проверки свежести
        freshness_status: str = "свежий" if is_fresh_result else "устаревший"
        self.logger.debug(
            f"Проверка свежести {currency_pair}: {freshness_status} "
            f"(прошло {time_since_update:.0f} сек, TTL: {ttl_seconds} сек)"
        )

        return is_fresh_result  # Возврат результата проверки свежести

    def get_stale_pairs(self) -> List[str]:
        """Получить список пар с устаревшими курсами.

        Returns:
            Список валютных пар с устаревшими данными

        Raises:
            CacheError: При ошибках загрузки данных кэша

        Note:
            Использует метод is_fresh() для проверки каждой пары.
            Возвращает только пары с устаревшими данными.
        """
        # 1. Получение всех курсов из кэша
        all_rates: Dict[str, Dict[str, Any]] = self.get_all_rates()

        # 2. Проверка свежести для каждой пары
        stale_pairs: List[str] = []

        for pair, pair_data in all_rates.items():
            timestamp: str = pair_data.get("updated_at", "")

            # Проверка свежести данных пары
            if not self.is_fresh(pair, timestamp):
                stale_pairs.append(pair)

        # Логирование результатов
        self.logger.info(f"Найдено {len(stale_pairs)} пар с устаревшими данными")

        return stale_pairs  # Возврат списка устаревших пар

    def get_cache_info(self) -> Dict[str, Any]:
        """Получить информацию о состоянии кэша.

        Returns:
            Словарь с информацией о кэше

        Raises:
            CacheError: При ошибках загрузки данных кэша
        """
        # 1. Загрузка данных кэша если они еще не загружены
        if self._cache_data is None:
            self._load_cache()

        # Убедимся что данные кэша загружены
        if self._cache_data is None:
            raise CacheError(
                "Не удалось загрузить данные кэша", operation="get_cache_info"
            )

        # 2. Сбор информации о кэше
        pairs_data: Dict[str, Any] = self._cache_data.get("pairs", {})
        total_pairs: int = len(pairs_data)

        # Подсчет пар по типам валют
        fiat_pairs: int = 0
        crypto_pairs: int = 0
        other_pairs: int = 0

        for pair in pairs_data.keys():
            try:
                base_currency: str = pair.split("_")[0].upper()
                if base_currency in self.FIAT_CURRENCIES:
                    fiat_pairs += 1
                elif base_currency in self.CRYPTO_CURRENCIES:
                    crypto_pairs += 1
                else:
                    other_pairs += 1
            except (IndexError, AttributeError):
                other_pairs += 1

        # Получение устаревших пар
        stale_pairs: List[str] = self.get_stale_pairs()

        # 3. Формирование информации о кэше
        cache_info: Dict[str, Any] = {
            "filepath": str(self.filepath),
            "version": self._cache_data.get("version", "unknown"),
            "last_refresh": self._cache_data.get("last_refresh", "unknown"),
            "total_pairs": total_pairs,
            "fiat_pairs": fiat_pairs,
            "crypto_pairs": crypto_pairs,
            "other_pairs": other_pairs,
            "stale_pairs_count": len(stale_pairs),
            "stale_pairs": stale_pairs[:10],  # Только первые 10 для краткости
            "is_loaded": self._cache_data is not None,
        }

        return cache_info  # Возврат информации о кэше

    def _load_cache(self) -> None:
        """Загрузить данные кэша из файла в память.

        Raises:
            CacheError: При ошибках чтения файла, парсинга JSON или валидации структуры

        Note:
            Если файл не существует, создает структуру данных по умолчанию.
            Кэширует загруженные данные в self._cache_data для последующего использования.
        """
        # Проверка существования файла
        if not self.filepath.exists():
            # Файл не существует - создание структуры по умолчанию
            self.logger.info(
                f"Файл кэша не существует, создается новый: {self.filepath}"
            )
            self._cache_data = self._create_default_cache_structure()
            return

        try:
            # Открытие файла для чтения в UTF-8 кодировке
            with open(self.filepath, "r", encoding="utf-8") as f:
                # Загрузка и парсинг JSON данных
                file_data: Dict[str, Any] = json.load(f)

            # Валидация структуры загруженных данных
            if not self._validate_cache_structure(file_data):
                self.logger.warning(
                    "Некорректная структура файла кэша, создается новая"
                )
                self._cache_data = self._create_default_cache_structure()
            else:
                # Данные валидны - сохранение в память
                self._cache_data = file_data
                pairs_count: int = len(self._cache_data.get("pairs", {}))
                self.logger.debug(f"Загружено {pairs_count} пар из файла кэша")

        except json.JSONDecodeError as e:
            # Ошибка парсинга JSON - создаем структуру по умолчанию
            self.logger.error(f"Ошибка парсинга JSON файла кэша: {e}")
            self._cache_data = self._create_default_cache_structure()

        except Exception as e:
            # Общая ошибка чтения файла - создаем структуру по умолчанию
            self.logger.error(f"Ошибка чтения файла кэша: {e}")
            self._cache_data = self._create_default_cache_structure()

        # Дополнительная проверка что self._cache_data установлен
        if self._cache_data is None:
            raise CacheError(
                "Критическая ошибка: не удалось создать структуру кэша",
                operation="_load_cache",
            )

    def _validate_cache_structure(self, data: Dict[str, Any]) -> bool:
        """Валидация структуры данных файла кэша.

        Args:
            data: Данные из файла для валидации

        Returns:
            True если структура валидна, False если нет
        """
        # Проверка обязательных полей верхнего уровня
        required_top_fields: List[str] = ["pairs", "last_refresh"]
        for field in required_top_fields:
            if field not in data:
                self.logger.warning(f"Отсутствует поле верхнего уровня: {field}")
                return False

        # Проверка что pairs является словарем
        if not isinstance(data["pairs"], dict):
            self.logger.warning("Поле 'pairs' должно быть словарем")
            return False

        # Проверка структуры каждой пары
        for pair_key, pair_data in data["pairs"].items():
            if not isinstance(pair_data, dict):
                self.logger.warning(
                    f"Некорректная структура данных для пары {pair_key}"
                )
                return False

            # Проверка обязательных полей пары
            pair_required_fields: List[str] = ["rate", "updated_at", "source"]
            for field in pair_required_fields:
                if field not in pair_data:
                    self.logger.warning(f"Отсутствует поле {field} для пары {pair_key}")
                    return False

        # Все проверки пройдены
        return True

    def _create_default_cache_structure(self) -> Dict[str, Any]:
        """Создать структуру данных кэша по умолчанию.

        Returns:
            Словарь со структурой данных кэша по умолчанию
        """
        current_time: str = datetime.now().isoformat() + "Z"

        default_structure: Dict[str, Any] = {
            "version": self.CACHE_VERSION,
            "last_refresh": current_time,
            "pairs": {},  # Пустой словарь пар
        }

        self.logger.debug("Создана структура данных кэша по умолчанию")
        return default_structure

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """Атомарная запись данных в файл кэша через временный файл.

        Args:
            data: Данные для записи в файл кэша

        Raises:
            CacheError: При ошибках записи, проверки целостности или переименования

        Note:
            Использует паттерн временный файл → проверка → атомарное переименование
            для гарантии целостности данных даже при сбоях системы.
        """
        # Создание путей к временному и основному файлам
        temp_filepath: Path = self.filepath.with_suffix(".tmp")
        backup_filepath: Path = self.filepath.with_suffix(".backup")

        try:
            # 1. Создание backup существующего файла (если он существует)
            if self.filepath.exists():
                try:
                    shutil.copy2(self.filepath, backup_filepath)
                    self.logger.debug(f"Создан backup кэша: {backup_filepath}")
                except Exception as backup_error:
                    self.logger.warning(
                        f"Не удалось создать backup кэша: {backup_error}"
                    )
                    # Продолжаем без backup

            # 2. Запись данных во временный файл
            with open(temp_filepath, "w", encoding="utf-8") as f:
                # Сериализация JSON с форматированием
                json.dump(
                    data,
                    f,
                    indent=2,
                    ensure_ascii=False,
                    default=str,  # Преобразование несериализуемых типов в строки
                )

            # 3. Проверка целостности записанных данных
            self._verify_cache_file_integrity(temp_filepath)

            # 4. Атомарное переименование временного файла в основной
            temp_filepath.replace(self.filepath)
            self.logger.debug(f"Файл кэша обновлен атомарно: {self.filepath}")

            # 5. Удаление временного файла (если он остался)
            if temp_filepath.exists():
                temp_filepath.unlink(missing_ok=True)

            # 6. Удаление backup файла (если операция успешна)
            if backup_filepath.exists():
                backup_filepath.unlink(missing_ok=True)

        except Exception as e:
            # 7. Восстановление из backup при ошибке
            self.logger.error(f"Ошибка атомарной записи кэша: {e}")

            if backup_filepath.exists() and self.filepath.exists():
                try:
                    backup_filepath.replace(self.filepath)
                    self.logger.info("Кэш восстановлен из backup")
                except Exception as restore_error:
                    raise CacheError(
                        f"Ошибка записи и восстановления кэша: {e}, "
                        f"восстановление не удалось: {restore_error}",
                        operation="_atomic_write",
                    ) from restore_error
            elif backup_filepath.exists():
                # Если основного файла не было, просто удаляем backup
                backup_filepath.unlink(missing_ok=True)

            # Удаление временного файла если он существует
            if temp_filepath.exists():
                temp_filepath.unlink(missing_ok=True)

            # Проброс исключения дальше
            raise CacheError(
                f"Ошибка атомарной записи кэша: {e}", operation="_atomic_write"
            ) from e

    def _verify_cache_file_integrity(self, filepath: Path) -> None:
        """Проверка целостности записанного файла кэша.

        Args:
            filepath: Путь к файлу для проверки

        Raises:
            CacheError: Если файл поврежден или имеет некорректную структуру

        Note:
            Проверяет что файл существует, содержит валидный JSON
            и имеет правильную структуру данных кэша.
        """
        # Проверка что файл существует и не пустой
        if not filepath.exists():
            raise CacheError(
                "Временный файл кэша не создан",
                operation="_verify_cache_file_integrity",
            )

        if filepath.stat().st_size == 0:
            raise CacheError(
                "Временный файл кэша пустой", operation="_verify_cache_file_integrity"
            )

        try:
            # Попытка загрузить и проверить JSON
            with open(filepath, "r", encoding="utf-8") as f:
                test_data: Dict[str, Any] = json.load(f)

            # Проверка структуры загруженных данных
            if not self._validate_cache_structure(test_data):
                raise CacheError(
                    "Некорректная структура данных во временном файле кэша",
                    operation="_verify_cache_file_integrity",
                )

        except json.JSONDecodeError as e:
            # Ошибка парсинга JSON
            raise CacheError(
                f"Некорректный JSON во временном файле кэша: {e}",
                operation="_verify_cache_file_integrity",
            ) from e
        except Exception as e:
            # Общая ошибка проверки
            raise CacheError(
                f"Ошибка проверки целостности кэша: {e}",
                operation="_verify_cache_file_integrity",
            ) from e


# Экспорт публичных классов модуля rates_cache
__all__ = [
    "CacheError",  # Исключение для ошибок работы кэша
    "RateInfo",  # Структурированная информация о курсе
    "RatesCache",  # Основной класс кэша курсов валют
]
