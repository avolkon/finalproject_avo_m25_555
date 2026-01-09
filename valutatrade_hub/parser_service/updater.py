"""
Модуль RatesUpdater - координатор процесса обновления курсов валют.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

from .api_clients import BaseApiClient
from .storage import HistoryStorage, StorageError
from valutatrade_hub.core.exceptions import ApiRequestError

from .api_clients import (
    CoinGeckoClient,  # Криптовалюты (есть)
    ExchangeRateApiClient,  # Фиат (новый из 5.1)
)


class UpdateStatus(Enum):
    """Статусы обновления курсов."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Частичный успех (не все источники)
    FAILED = "failed"  # Полный сбой


@dataclass
class UpdateResult:
    """Результат операции обновления курсов."""

    status: UpdateStatus
    total_rates: int  # Общее количество полученных курсов
    updated_sources: List[str]  # Источники которые успешно обновились
    failed_sources: List[str]  # Источники которые не удалось обновить
    error_messages: List[str]  # Сообщения об ошибках


class RatesUpdater:
    """Координатор процесса обновления курсов валют из всех источников."""

    def __init__(
        self,
        clients: List[BaseApiClient],
        history_storage: Optional[HistoryStorage] = None,
        cache_filepath: str = "data/rates.json",
    ) -> None:
        """Инициализация координатора обновления курсов.

        Args:
            clients: Список API клиентов для получения курсов
            history_storage: Хранилище исторических данных (опционально)
            cache_filepath: Путь к файлу кэша rates.json (по умолчанию data/rates.json)

        Note:
            Если history_storage не указан, исторические данные не сохраняются.
            Кэш rates.json обновляется всегда при успешном получении данных.
        """
        self.clients: List[BaseApiClient] = clients  # API клиенты для получения данных
        self.history_storage: Optional[HistoryStorage] = (
            history_storage  # Хранилище истории
        )
        self.cache_filepath: str = cache_filepath  # Путь к файлу кэша

        # Инициализация логгера для операций обновления
        self.logger: logging.Logger = logging.getLogger("parser.updater")

        self.logger.info(f"Инициализирован RatesUpdater с {len(clients)} клиентами")

    def get_clients(self) -> List[BaseApiClient]:
        """Создать и вернуть список всех API-клиентов.

        Returns:
            Список клиентов: CoinGecko + ExchangeRate для полного покрытия ТЗ4.
        """
        # Создание клиентов с едиными параметрами (timeout=10, retries=3)
        return [
            # Криптовалюты через CoinGecko API
            CoinGeckoClient(timeout=10, max_retries=3),
            # Фиатные валюты через ExchangeRate-API
            ExchangeRateApiClient(timeout=10, max_retries=3),
        ]

    def run_update(self) -> UpdateResult:
        """Выполнить полное обновление курсов из всех источников.

        Returns:
            Результат операции обновления со статусом и статистикой

        Raises:
            ApiRequestError: Если все клиенты завершились с ошибкой
            StorageError: При ошибках сохранения в историческое хранилище

        Note:
            Метод последовательно опрашивает всех клиентов, объединяет данные
            и сохраняет их в кэш rates.json и историческое хранилище.
        """
        self.logger.info("Начало полного обновления курсов")

        all_rates: Dict[str, Dict[str, Any]] = {}  # Словарь для объединенных данных
        updated_sources: List[str] = []  # Успешные источники
        failed_sources: List[str] = []  # Неудачные источники
        error_messages: List[str] = []  # Сообщения об ошибках

        # 1. Последовательный опрос всех клиентов
        for client in self.clients:
            try:
                self.logger.info(f"Опрос источника: {client.name}")

                # Получение курсов от клиента
                rates: Dict[str, float] = client.fetch_rates()

                # Преобразование формата данных
                formatted_rates: Dict[str, Dict[str, Any]] = (
                    self._format_rates_for_cache(rates, client.name)
                )

                # Объединение данных (новые данные перезаписывают старые)
                all_rates.update(formatted_rates)
                updated_sources.append(client.name)

                # Сохранение в историческое хранилище (если указано)
                if self.history_storage:
                    self._save_to_history(client.name, rates)

                self.logger.info(
                    f"Источник {client.name}: получено {len(rates)} курсов"
                )

            except ApiRequestError as e:
                # Ошибка API клиента - логируем и продолжаем с другими
                error_msg: str = f"{client.name}: {str(e)}"
                self.logger.error(error_msg)
                failed_sources.append(client.name)
                error_messages.append(error_msg)
                continue  # Продолжаем со следующим клиентом

            except Exception as e:
                # Неожиданная ошибка - логируем и продолжаем
                error_msg: str = f"{client.name}: неожиданная ошибка - {e}"
                self.logger.error(error_msg, exc_info=True)
                failed_sources.append(client.name)
                error_messages.append(error_msg)
                continue

        # 2. Проверка результатов опроса
        if not all_rates:
            # Не удалось получить ни одного курса от всех источников
            self.logger.error("Не удалось получить ни одного курса от всех источников")
            raise ApiRequestError(
                "Все источники завершились с ошибкой. Проверьте подключение к сети."
            )

        # 3. Обновление кэша rates.json
        updated_count: int = self._update_cache(all_rates)

        # 4. Определение статуса операции
        if not failed_sources:
            status: UpdateStatus = UpdateStatus.SUCCESS
            self.logger.info(
                f"Обновление успешно: {updated_count} курсов из {len(updated_sources)} источников"
            )
        elif updated_sources:
            status = UpdateStatus.PARTIAL
            self.logger.warning(
                f"Частичный успех: {updated_count} курсов из {len(updated_sources)} источников, "
                f"ошибок: {len(failed_sources)}"
            )
        else:
            # Этот случай не должен произойти из-за проверки выше, но на всякий случай
            status = UpdateStatus.FAILED
            self.logger.error("Все источники завершились с ошибкой")

        # 5. Возврат результата операции
        return UpdateResult(
            status=status,
            total_rates=updated_count,
            updated_sources=updated_sources,
            failed_sources=failed_sources,
            error_messages=error_messages,
        )

    def run_update_for_source(self, source_name: str) -> UpdateResult:
        """Выполнить обновление курсов только для указанного источника.

        Args:
            source_name: Название источника для обновления (например, "CoinGecko")

        Returns:
            Результат операции обновления

        Raises:
            ValueError: Если источник с указанным именем не найден
            ApiRequestError: Если источник завершился с ошибкой

        Note:
            Полезно для отладки или выборочного обновления конкретного источника.
        """
        self.logger.info(f"Выборочное обновление для источника: {source_name}")

        # Поиск клиента по имени
        target_client: Optional[BaseApiClient] = None
        for client in self.clients:
            if client.name.lower() == source_name.lower():
                target_client = client
                break

        if target_client is None:
            # Клиент с указанным именем не найден
            error_msg: str = f"Источник '{source_name}' не найден"
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        all_rates: Dict[str, Dict[str, Any]] = {}  # Словарь для данных
        updated_sources: List[str] = []  # Успешные источники
        failed_sources: List[str] = []  # Неудачные источники
        error_messages: List[str] = []  # Сообщения об ошибках

        try:
            # Получение курсов от выбранного клиента
            self.logger.info(f"Опрос источника: {target_client.name}")
            rates: Dict[str, float] = target_client.fetch_rates()

            # Преобразование формата данных
            formatted_rates: Dict[str, Dict[str, Any]] = self._format_rates_for_cache(
                rates, target_client.name
            )

            # Объединение данных
            all_rates.update(formatted_rates)
            updated_sources.append(target_client.name)

            # Сохранение в историческое хранилище (если указано)
            if self.history_storage:
                self._save_to_history(target_client.name, rates)

            self.logger.info(
                f"Источник {target_client.name}: получено {len(rates)} курсов"
            )

        except ApiRequestError as e:
            # Ошибка API клиента
            error_msg = f"{target_client.name}: {str(e)}"
            self.logger.error(error_msg)
            failed_sources.append(target_client.name)
            error_messages.append(error_msg)
            raise  # Пробрасываем исключение для выборочного обновления

        except Exception as e:
            # Неожиданная ошибка
            error_msg = f"{target_client.name}: неожиданная ошибка - {e}"
            self.logger.error(error_msg, exc_info=True)
            failed_sources.append(target_client.name)
            error_messages.append(error_msg)
            raise

        # Обновление кэша rates.json
        updated_count: int = self._update_cache(all_rates)

        # Определение статуса операции
        if not failed_sources:
            status: UpdateStatus = UpdateStatus.SUCCESS
            self.logger.info(
                f"Выборочное обновление успешно: {updated_count} курсов из {source_name}"
            )
        else:
            status = UpdateStatus.FAILED
            self.logger.error(f"Выборочное обновление не удалось: {source_name}")

        # Возврат результата операции
        return UpdateResult(
            status=status,
            total_rates=updated_count,
            updated_sources=updated_sources,
            failed_sources=failed_sources,
            error_messages=error_messages,
        )

    def _format_rates_for_cache(
        self, rates: Dict[str, float], source: str
    ) -> Dict[str, Dict[str, Any]]:
        """Преобразовать сырые курсы в формат для кэша rates.json.

        Args:
            rates: Сырые курсы в формате {"FROM_TO": rate}
            source: Источник данных (например, "CoinGecko")

        Returns:
            Словарь в формате для rates.json с метаданными
        """
        current_time: str = datetime.now().isoformat() + "Z"
        formatted_rates: Dict[str, Dict[str, Any]] = {}

        for pair, rate in rates.items():
            formatted_rates[pair] = {
                "rate": float(rate),  # Числовое значение курса
                "updated_at": current_time,  # Время обновления
                "source": source,  # Источник данных
            }

        return formatted_rates

    def _save_to_history(self, source: str, rates: Dict[str, float]) -> None:
        """Сохранить курсы в историческое хранилище.

        Args:
            source: Источник данных
            rates: Словарь курсов в формате {"FROM_TO": rate}

        Raises:
            StorageError: При ошибках сохранения в историческое хранилище

        Note:
            Создает записи для каждой валютной пары с метаданными.
            Используется только если history_storage был передан при инициализации.
        """
        if self.history_storage is None:
            return  # Историческое хранилище не указано

        try:
            current_time: str = datetime.now().isoformat() + "Z"
            records: List[Dict[str, Any]] = []

            for pair, rate in rates.items():
                # Парсинг пары валют (формат "FROM_TO")
                if "_" not in pair:
                    self.logger.warning(f"Некорректный формат пары: {pair}")
                    continue

                from_currency, to_currency = pair.split("_", 1)

                # Создание записи для исторического хранилища
                record: Dict[str, Any] = {
                    "from_currency": from_currency,
                    "to_currency": to_currency,
                    "rate": float(rate),
                    "timestamp": current_time,
                    "source": source,
                    "meta": {
                        "operation": "automatic_update",
                        "client_name": source,
                        "pair": pair,
                    },
                }
                records.append(record)

            # Пакетное сохранение записей
            if records:
                saved_ids: List[str] = self.history_storage.save_batch(records)
                self.logger.debug(
                    f"Сохранено {len(saved_ids)} записей в историческое хранилище"
                )

        except StorageError as e:
            # Ошибка сохранения в историческое хранилище
            self.logger.error(f"Ошибка сохранения истории: {e}")
            raise  # Пробрасываем исключение дальше

        except Exception as e:
            # Неожиданная ошибка при сохранении истории
            self.logger.error(
                f"Неожиданная ошибка при сохранении истории: {e}", exc_info=True
            )
            # Не пробрасываем исключение чтобы не прерывать основную операцию

    def _update_cache(self, rates: Dict[str, Dict[str, Any]]) -> int:
        """Обновить кэш rates.json с новыми данными.

        Args:
            rates: Словарь с курсами в формате для кэша

        Returns:
            Количество обновленных/добавленных курсов

        Raises:
            IOError: При ошибках чтения/записи файла кэша
            json.JSONDecodeError: При некорректном формате существующего файла

        Note:
            Обновляет только те курсы, которые свежее текущих или отсутствуют.
            Сохраняет данные в формате ТЗ4 с полями pairs и last_refresh.
        """
        try:
            import json
            from pathlib import Path

            cache_path: Path = Path(self.cache_filepath)
            current_time: str = datetime.now().isoformat() + "Z"

            # 1. Загрузка существующих данных или создание новой структуры
            existing_data: Dict[str, Any] = {}
            if cache_path.exists():
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)

                    # Проверка структуры существующих данных
                    if not isinstance(existing_data, dict):
                        existing_data = {}  # Некорректная структура - сбрасываем

                except (json.JSONDecodeError, IOError) as e:
                    self.logger.warning(f"Ошибка загрузки кэша, создается новый: {e}")
                    existing_data = {}

            # 2. Инициализация структуры данных если она пустая или некорректная
            if "pairs" not in existing_data or not isinstance(
                existing_data["pairs"], dict
            ):
                existing_data = {
                    "version": "1.0",
                    "last_refresh": current_time,
                    "pairs": {},
                }

            # 3. Обновление курсов (только если данные свежее или отсутствуют)
            updated_count: int = 0
            for pair, new_data in rates.items():
                existing_pair_data = existing_data["pairs"].get(pair)

                if existing_pair_data is None:
                    # Пара отсутствует - добавляем
                    existing_data["pairs"][pair] = new_data
                    updated_count += 1
                    self.logger.debug(f"Добавлена новая пара: {pair}")

                else:
                    # Пара существует - сравниваем время обновления
                    existing_time_str: str = existing_pair_data.get("updated_at", "")
                    new_time_str: str = new_data.get("updated_at", "")

                    try:
                        # Парсинг времени для сравнения
                        existing_time = datetime.fromisoformat(
                            existing_time_str.replace("Z", "+00:00")
                        )
                        new_time = datetime.fromisoformat(
                            new_time_str.replace("Z", "+00:00")
                        )

                        # Обновляем только если новые данные свежее
                        if new_time > existing_time:
                            existing_data["pairs"][pair] = new_data
                            updated_count += 1
                            self.logger.debug(f"Обновлена пара: {pair}")

                    except (ValueError, TypeError):
                        # Некорректный формат времени - обновляем в любом случае
                        existing_data["pairs"][pair] = new_data
                        updated_count += 1
                        self.logger.debug(
                            f"Обновлена пара (некорректное время): {pair}"
                        )

            # 4. Обновление времени последнего обновления
            existing_data["last_refresh"] = current_time

            # 5. Атомарная запись в файл через временный файл
            temp_path: Path = cache_path.with_suffix(".tmp")

            # Запись во временный файл
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False, default=str)

            # Проверка целостности записанных данных
            try:
                with open(temp_path, "r", encoding="utf-8") as f:
                    test_data = json.load(f)

                # Базовая проверка структуры
                if not isinstance(test_data, dict) or "pairs" not in test_data:
                    raise ValueError("Некорректная структура данных после записи")

                # Атомарное переименование временного файла
                temp_path.replace(cache_path)
                self.logger.debug(f"Кэш обновлен атомарно: {cache_path}")

            except (json.JSONDecodeError, ValueError) as e:
                # Ошибка проверки целостности - удаляем временный файл
                if temp_path.exists():
                    temp_path.unlink(missing_ok=True)
                raise IOError(f"Ошибка проверки целостности кэша: {e}") from e

            # 6. Логирование результатов обновления кэша
            self.logger.info(
                f"Кэш обновлен: {updated_count} курсов, "
                f"всего пар в кэше: {len(existing_data['pairs'])}"
            )

            return updated_count

        except Exception as e:
            self.logger.error(f"Критическая ошибка обновления кэша: {e}", exc_info=True)
            raise
