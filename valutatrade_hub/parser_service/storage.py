"""
Модуль хранилища исторических данных о курсах валют.
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class StorageError(Exception):
    """Исключение для ошибок работы хранилища исторических данных.

    Attributes:
        message: Текстовое описание ошибки
        operation: Название операции вызвавшей ошибку
    """

    def __init__(self, message: str, operation: str = "unknown") -> None:
        """Инициализация исключения хранилища.

        Args:
            message: Текстовое описание ошибки
            operation: Название операции (например, "save_record")
        """
        # Формирование полного сообщения об ошибке
        full_message: str = f"Ошибка хранилища в операции {operation}: {message}"
        super().__init__(full_message)
        self.operation = operation  # Сохранение операции для отладки


class HistoryStorage:
    """Хранилище исторических данных о курсах валют.
    Класс управляет чтением и записью исторических данных о курсах валют
    в файл exchange_rates.json с поддержкой атомарных операций и уникальных ID.
    """

    # Константа версии формата данных
    DATA_VERSION: str = "1.0"

    def __init__(self, filepath: str = "data/exchange_rates.json") -> None:
        """Инициализация хранилища исторических данных.
        Args:
            filepath: Путь к файлу с историческими данными (по умолчанию data/exchange_rates.json)
        Raises:
            StorageError: Если не удается создать директорию для файла
        Note:
            Автоматически создает директорию если она не существует.
            Инициализирует логгер для операций хранилища.
        """
        self.filepath: Path = Path(filepath)  # Преобразование пути в объект Path
        # Инициализация логгера для операций хранилища
        self.logger: logging.Logger = logging.getLogger("parser.storage")

        # Создание директории если она не существует
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Директория создана/проверена: {self.filepath.parent}")
        except Exception as e:
            # Ошибка создания директории
            raise StorageError(
                f"Не удалось создать директорию: {e}", operation="init"
            ) from e

        # Инициализация данных в памяти
        self._data: Optional[Dict[str, Any]] = None
        self.logger.info(f"Хранилище инициализировано: {self.filepath}")

    def generate_id(self, from_currency: str, to_currency: str, timestamp: str) -> str:
        """ID = FROMTO_ISO (BTCUSD_20260110T143000Z)."""
        from_cur = from_currency.upper().strip()
        to_cur = to_currency.upper().strip()
        # "2025-10-10T12:00:00Z" -> "20251010T120000Z"
        ts_clean = timestamp.replace("-", "").replace(":", "").rpartition(".")[0] + "Z"
        record_id = f"{from_cur}{to_cur}_{ts_clean}"
        self.logger.debug(
            f"Generated ID: {record_id} from {from_currency}/{to_currency}/{timestamp}"
        )
        return record_id

    def validate_record(self, record: Dict[str, Any]) -> bool:
        """Валидация: required + формат + meta."""
        required = ["from_currency", "to_currency", "rate", "timestamp", "source"]
        for field in required:
            if field not in record:
                self.logger.warning(
                    f"Missing: {field} in {record.get('id', 'unknown')}"
                )
                return False

        # UPPER 2-5 символов
        if not (
            2 <= len(record["from_currency"]) <= 5 and record["from_currency"].isupper()
        ):
            return False
        if record["rate"] <= 0:
            self.logger.warning(f"Invalid rate {record['rate']}")
            return False
        if "meta" not in record or not isinstance(record["meta"], dict):
            self.logger.warning("Missing meta")
            return False
        # meta required
        meta_req = ["raw_id", "request_ms", "status_code"]
        for mfield in meta_req:
            if mfield not in record["meta"]:
                self.logger.warning(f"Missing meta.{mfield}")
                return False
        return True

    def save_record(self, record_data: Dict[str, Any]) -> str:
        """Сохранить одну запись о курсе валюты в историческое хранилище.
        Args:
            record_data: Данные записи в формате ТЗ4 (должны содержать обязательные поля)
        Returns:
            Уникальный идентификатор сохраненной записи
        Raises:
            StorageError: При ошибках валидации, генерации ID или записи данных
            ValueError: Если входные данные не содержат обязательных полей
        Note:
            Автоматически генерирует уникальный ID для записи на основе данных.
            Выполняет валидацию структуры данных перед сохранением.
        """
        # Логирование начала операции сохранения записи
        self.logger.debug(
            f"Сохранение записи: {record_data.get('from_currency', 'unknown')}_"
            f"{record_data.get('to_currency', 'unknown')}"
        )

        # 1. Валидация обязательных полей записи
        required_fields: List[str] = [
            "from_currency",
            "to_currency",
            "rate",
            "timestamp",
            "source",
        ]
        for field in required_fields:
            if field not in record_data:
                # Отсутствие обязательного поля
                raise ValueError(f"Отсутствует обязательное поле: {field}")

        # 2. Генерация уникального ID для записи
        record_id: str = self._generate_id(
            from_currency=record_data["from_currency"],
            to_currency=record_data["to_currency"],
            timestamp=record_data["timestamp"],
        )

        # 3. Добавление ID в данные записи
        record_data_with_id: Dict[str, Any] = record_data.copy()
        record_data_with_id["id"] = record_id

        # 4. Валидация полной структуры записи
        if not self._validate_record(record_data_with_id):
            raise StorageError("Невалидная структура записи", operation="save_record")

        # 5. Загрузка текущих данных (если еще не загружены)
        if self._data is None:
            self._load_data()

        # Убедимся что self._data не None после загрузки
        if self._data is None:
            raise StorageError(
                "Не удалось загрузить или создать структуру данных",
                operation="save_record",
            )

        # 6. Добавление записи в данные
        self._data["records"].append(record_data_with_id)
        self._data["total_records"] = len(self._data["records"])
        self._data["last_updated"] = datetime.now().isoformat() + "Z"

        # 7. Атомарная запись обновленных данных в файл
        self._atomic_write(self._data)

        # Логирование успешного сохранения
        self.logger.info(
            f"Сохранена запись {record_id}, всего записей: {self._data['total_records']}"
        )

        return record_id  # Возврат уникального ID сохраненной записи

    def save_batch(self, records: List[Dict[str, Any]]) -> List[str]:
        """Сохранить несколько записей о курсах валют атомарно.

        Args:
            records: Список записей для сохранения (каждая в формате ТЗ4)

        Returns:
            Список уникальных идентификаторов сохраненных записей

        Raises:
            StorageError: При ошибках валидации, генерации ID или записи данных
            ValueError: Если хотя бы одна запись не содержит обязательных полей

        Note:
            Все записи сохраняются одной атомарной операцией.
            При ошибке валидации одной записи вся операция отменяется.
        """
        # Логирование начала пакетного сохранения
        self.logger.info(f"Пакетное сохранение {len(records)} записей")

        # 1. Проверка что есть записи для сохранения
        if not records:
            self.logger.warning("Попытка сохранить пустой пакет записей")
            return []  # Возврат пустого списка ID

        saved_ids: List[str] = []  # Список для хранения ID сохраненных записей
        records_with_ids: List[Dict[str, Any]] = []  # Список записей с ID

        # 2. Обработка каждой записи в пакете
        for i, record in enumerate(records):
            try:
                # Валидация обязательных полей для каждой записи
                required_fields: List[str] = [
                    "from_currency",
                    "to_currency",
                    "rate",
                    "timestamp",
                    "source",
                ]
                for field in required_fields:
                    if field not in record:
                        raise ValueError(f"Запись {i}: отсутствует поле {field}")

                # Генерация уникального ID для записи
                record_id: str = self._generate_id(
                    from_currency=record["from_currency"],
                    to_currency=record["to_currency"],
                    timestamp=record["timestamp"],
                )

                # Создание копии записи с добавленным ID
                record_with_id: Dict[str, Any] = record.copy()
                record_with_id["id"] = record_id

                # Валидация полной структуры записи
                if not self._validate_record(record_with_id):
                    raise ValueError(f"Запись {i}: невалидная структура")

                # Добавление в списки для сохранения
                records_with_ids.append(record_with_id)
                saved_ids.append(record_id)

                self.logger.debug(
                    f"Подготовлена запись {i+1}/{len(records)}: {record_id}"
                )

            except Exception as e:
                # Ошибка обработки записи - отмена всей операции
                raise StorageError(
                    f"Ошибка в записи {i}: {e}", operation="save_batch"
                ) from e

        # 3. Загрузка текущих данных (если еще не загружены)
        if self._data is None:
            self._load_data()

        # Убедимся что self._data не None после загрузки
        if self._data is None:
            raise StorageError(
                "Не удалось загрузить или создать структуру данных",
                operation="save_batch",
            )

        # 4. Добавление всех записей в данные
        self._data["records"].extend(records_with_ids)
        self._data["total_records"] = len(self._data["records"])
        self._data["last_updated"] = datetime.now().isoformat() + "Z"

        # 5. Атомарная запись обновленных данных в файл
        self._atomic_write(self._data)

        # Логирование успешного пакетного сохранения
        self.logger.info(
            f"Сохранен пакет из {len(saved_ids)} записей, "
            f"всего записей: {self._data['total_records']}"
        )

        return saved_ids  # Возврат списка ID сохраненных записей

    def load_all(self) -> List[Dict[str, Any]]:
        """Загрузить все исторические записи о курсах валют.

        Returns:
            Список всех записей в хронологическом порядке (от старых к новым)

        Raises:
            StorageError: При ошибках чтения файла, парсинга JSON или валидации структуры

        Note:
            При первом вызове загружает данные из файла и кэширует в памяти.
            Последующие вызовы возвращают кэшированные данные.
        """
        # 1. Загрузка данных если они еще не загружены в память
        if self._data is None:
            self._load_data()

        # Убедимся что self._data не None после загрузки
        if self._data is None:
            raise StorageError(
                "Не удалось загрузить данные хранилища", operation="load_all"
            )

        # 2. Возврат копии списка записей (защита от модификации)
        records_copy: List[Dict[str, Any]] = self._data["records"].copy()

        # Логирование операции загрузки
        self.logger.debug(f"Загружено {len(records_copy)} записей")

        return records_copy  # Возврат копии списка записей

    def get_by_currency(
        self, currency_code: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Получить записи о курсах по коду валюты с ограничением количества.

        Args:
            currency_code: Код валюты для поиска (например, "BTC")
            limit: Максимальное количество возвращаемых записей (по умолчанию 100)

        Returns:
            Список записей содержащих указанную валюту (от новых к старым)

        Note:
            Поиск выполняется как по from_currency, так и по to_currency.
            Возвращаются записи отсортированные по времени (новые первые).
        """
        # Нормализация кода валюты для поиска
        search_code: str = currency_code.upper().strip()

        # 1. Загрузка всех записей если они еще не загружены
        if self._data is None:
            self._load_data()

        # Убедимся что self._data не None после загрузки
        if self._data is None:
            raise StorageError(
                "Не удалось загрузить данные хранилища", operation="get_by_currency"
            )

        # 2. Фильтрация записей по коду валюты
        matching_records: List[Dict[str, Any]] = []
        for record in self._data["records"]:
            # Проверка валюты в записи (исходная или целевая)
            if (
                record.get("from_currency", "").upper() == search_code
                or record.get("to_currency", "").upper() == search_code
            ):
                matching_records.append(record)

        # 3. Сортировка по времени (от новых к старым)
        matching_records.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # 4. Ограничение количества возвращаемых записей
        result: List[Dict[str, Any]] = matching_records[:limit]

        # Логирование операции поиска
        self.logger.debug(
            f"Найдено {len(result)} записей по валюте {search_code} "
            f"(всего совпадений: {len(matching_records)})"
        )

        return result  # Возврат отфильтрованных записей

    def get_by_period(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Получить записи о курсах за указанный временной период.

        Args:
            start_date: Начальная дата периода в ISO формате (например, "2025-10-01T00:00:00Z")
            end_date: Конечная дата периода в ISO формате (например, "2025-10-10T23:59:59Z")

        Returns:
            Список записей за указанный период в хронологическом порядке

        Raises:
            ValueError: При некорректном формате дат или если start_date > end_date

        Note:
            Включает записи с timestamp >= start_date и <= end_date.
        """
        try:
            # Парсинг дат для сравнения
            start_dt: datetime = datetime.fromisoformat(
                start_date.replace("Z", "+00:00")
            )
            end_dt: datetime = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError as e:
            # Некорректный формат даты
            raise ValueError(f"Некорректный формат даты: {e}") from e

        # Проверка что start_date <= end_date
        if start_dt > end_dt:
            raise ValueError(f"Начальная дата {start_date} позже конечной {end_date}")

        # 1. Загрузка всех записей если они еще не загружены
        if self._data is None:
            self._load_data()

        # Убедимся что self._data не None после загрузки
        if self._data is None:
            raise StorageError(
                "Не удалось загрузить данные хранилища", operation="get_by_period"
            )

        # 2. Фильтрация записей по периоду
        period_records: List[Dict[str, Any]] = []
        for record in self._data["records"]:
            try:
                # Парсинг timestamp записи
                record_timestamp: str = record.get("timestamp", "")
                if not record_timestamp:
                    continue  # Пропуск записей без timestamp

                record_dt: datetime = datetime.fromisoformat(
                    record_timestamp.replace("Z", "+00:00")
                )

                # Проверка что запись входит в период
                if start_dt <= record_dt <= end_dt:
                    period_records.append(record)

            except ValueError:
                # Некорректный формат timestamp в записи - пропуск
                self.logger.warning(
                    f"Некорректный формат timestamp в записи: {record.get('id', 'unknown')}"
                )
                continue

        # 3. Сортировка по времени (от старых к новым)
        period_records.sort(key=lambda x: x.get("timestamp", ""))

        # Логирование операции фильтрации по периоду
        self.logger.debug(
            f"Найдено {len(period_records)} записей за период "
            f"{start_date} - {end_date}"
        )

        return period_records  # Возврат записей за период

    def _generate_id(self, from_currency: str, to_currency: str, timestamp: str) -> str:
        """Сгенерировать уникальный идентификатор для записи о курсе.

        Args:
            from_currency: Исходная валюта (например, "BTC")
            to_currency: Целевая валюта (например, "USD")
            timestamp: Временная метка в ISO формате (например, "2025-10-10T12:00:00Z")

        Returns:
            Уникальный идентификатор в формате "FROM_TO_TIMESTAMP"

        Note:
            Формат ID: валюта1_валюта2_ISO_timestamp
            Пример: BTC_USD_2025-10-10T12:00:00Z
        """
        # Нормализация кодов валют (верхний регистр, без пробелов)
        from_norm: str = from_currency.upper().strip().replace(" ", "_")
        to_norm: str = to_currency.upper().strip().replace(" ", "_")

        # Нормализация timestamp (убедиться что есть Z в конце)
        ts_norm: str = timestamp.strip()
        if not ts_norm.endswith("Z"):
            ts_norm += "Z"

        # Генерация ID по шаблону FROM_TO_TIMESTAMP
        record_id: str = f"{from_norm}_{to_norm}_{ts_norm}"

        return record_id  # Возврат сгенерированного ID

    def _validate_record(self, record: Dict[str, Any]) -> bool:
        """Валидация структуры записи о курсе валюты.

        Args:
            record: Запись для валидации (должна содержать поле "id")

        Returns:
            True если запись валидна, False если нет

        Note:
            Проверяет обязательные поля, форматы данных и допустимые значения.
            Логирует предупреждения при обнаружении проблем.
        """
        # 1. Проверка наличия обязательных полей
        required_fields: List[str] = [
            "id",
            "from_currency",
            "to_currency",
            "rate",
            "timestamp",
            "source",
        ]
        for field in required_fields:
            if field not in record:
                self.logger.warning(f"Отсутствует обязательное поле: {field}")
                return False

        # 2. Проверка формата ID
        if not isinstance(record["id"], str) or not record["id"]:
            self.logger.warning("Некорректный формат ID")
            return False

        # 3. Проверка форматов кодов валют (2-5 символов, верхний регистр)
        for currency_field in ["from_currency", "to_currency"]:
            currency_code: str = record[currency_field]
            if not isinstance(currency_code, str):
                self.logger.warning(f"Некорректный тип {currency_field}")
                return False

            currency_norm: str = currency_code.upper().strip()
            if not (2 <= len(currency_norm) <= 5):
                self.logger.warning(
                    f"Некорректная длина кода валюты {currency_field}: {currency_norm}"
                )
                return False

        # 4. Проверка что rate является положительным числом
        try:
            rate_value: float = float(record["rate"])
            if rate_value <= 0:
                self.logger.warning(f"Неположительный курс: {rate_value}")
                return False
        except (ValueError, TypeError):
            self.logger.warning(f"Некорректный тип курса: {record['rate']}")
            return False

        # 5. Проверка формата timestamp (ISO 8601)
        try:
            ts: str = record["timestamp"]
            # Попытка парсинга ISO timestamp
            datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            self.logger.warning(f"Некорректный формат timestamp: {record['timestamp']}")
            return False

        # 6. Проверка что source является строкой
        if not isinstance(record["source"], str) or not record["source"].strip():
            self.logger.warning("Некорректный источник данных")
            return False

        # Все проверки пройдены - запись валидна
        return True

    def _load_data(self) -> None:
        """Загрузить данные из файла в память.

        Raises:
            StorageError: При ошибках чтения файла, парсинга JSON или валидации структуры

        Note:
            Если файл не существует, создает структуру данных по умолчанию.
            Кэширует загруженные данные в self._data для последующего использования.
        """
        # Проверка существования файла
        if not self.filepath.exists():
            # Файл не существует - создание структуры по умолчанию
            self.logger.info(f"Файл не существует, создается новый: {self.filepath}")
            self._data = self._create_default_structure()
            return

        try:
            # Открытие файла для чтения в UTF-8 кодировке
            with open(self.filepath, "r", encoding="utf-8") as f:
                # Загрузка и парсинг JSON данных
                file_data: Dict[str, Any] = json.load(f)

            # Валидация структуры загруженных данных
            if not self._validate_data_structure(file_data):
                self.logger.warning("Некорректная структура файла, создается новая")
                self._data = self._create_default_structure()
            else:
                # Данные валидны - сохранение в память
                self._data = file_data
                self.logger.debug(
                    f"Загружено {self._data['total_records']} записей из файла"
                )

        except json.JSONDecodeError as e:
            # Ошибка парсинга JSON - создаем структуру по умолчанию
            self.logger.error(f"Ошибка парсинга JSON файла: {e}")
            self._data = self._create_default_structure()

        except Exception as e:
            # Общая ошибка чтения файла - создаем структуру по умолчанию
            self.logger.error(f"Ошибка чтения файла: {e}")
            self._data = self._create_default_structure()

        # Дополнительная проверка что self._data установлен
        if self._data is None:
            raise StorageError(
                "Критическая ошибка: не удалось создать структуру данных",
                operation="_load_data",
            )

    def _validate_data_structure(self, data: Dict[str, Any]) -> bool:
        """Валидация структуры данных файла.

        Args:
            data: Данные из файла для валидации

        Returns:
            True если структура валидна, False если нет
        """
        # Проверка обязательных полей верхнего уровня
        required_top_fields: List[str] = [
            "version",
            "last_updated",
            "total_records",
            "records",
        ]
        for field in required_top_fields:
            if field not in data:
                self.logger.warning(f"Отсутствует поле верхнего уровня: {field}")
                return False

        # Проверка что records является списком
        if not isinstance(data["records"], list):
            self.logger.warning("Поле 'records' должно быть списком")
            return False

        # Проверка что total_records соответствует количеству записей
        if data["total_records"] != len(data["records"]):
            self.logger.warning(
                f"Несоответствие total_records ({data['total_records']}) "
                f"и количества записей ({len(data['records'])})"
            )
            return False

        # Все проверки пройдены
        return True

    def _create_default_structure(self) -> Dict[str, Any]:
        """Создать структуру данных по умолчанию.

        Returns:
            Словарь с структурой данных по умолчанию
        """
        current_time: str = datetime.now().isoformat() + "Z"

        default_structure: Dict[str, Any] = {
            "version": self.DATA_VERSION,
            "last_updated": current_time,
            "total_records": 0,
            "records": [],  # Пустой список записей
        }

        self.logger.debug("Создана структура данных по умолчанию")
        return default_structure

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """Атомарная запись данных в файл через временный файл.

        Args:
            data: Данные для записи в файл

        Raises:
            StorageError: При ошибках записи, проверки целостности или переименования

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
                    self.logger.debug(f"Создан backup: {backup_filepath}")
                except Exception as backup_error:
                    self.logger.warning(f"Не удалось создать backup: {backup_error}")
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
            self._verify_file_integrity(temp_filepath)

            # 4. Атомарное переименование временного файла в основной
            temp_filepath.replace(self.filepath)
            self.logger.debug(f"Файл обновлен атомарно: {self.filepath}")

            # 5. Удаление временного файла (если он остался)
            if temp_filepath.exists():
                temp_filepath.unlink(missing_ok=True)

            # 6. Удаление backup файла (если операция успешна)
            if backup_filepath.exists():
                backup_filepath.unlink(missing_ok=True)

        except Exception as e:
            # 7. Восстановление из backup при ошибке
            self.logger.error(f"Ошибка атомарной записи: {e}")

            if backup_filepath.exists() and self.filepath.exists():
                try:
                    backup_filepath.replace(self.filepath)
                    self.logger.info("Восстановлено из backup")
                except Exception as restore_error:
                    raise StorageError(
                        f"Ошибка записи и восстановления: {e}, "
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
            raise StorageError(
                f"Ошибка атомарной записи: {e}", operation="_atomic_write"
            ) from e

    def _verify_file_integrity(self, filepath: Path) -> None:
        """Проверка целостности записанного файла.

        Args:
            filepath: Путь к файлу для проверки

        Raises:
            StorageError: Если файл поврежден или имеет некорректную структуру

        Note:
            Проверяет что файл существует, содержит валидный JSON
            и имеет правильную структуру данных.
        """
        # Проверка что файл существует и не пустой
        if not filepath.exists():
            raise StorageError(
                "Временный файл не создан", operation="_verify_file_integrity"
            )

        if filepath.stat().st_size == 0:
            raise StorageError(
                "Временный файл пустой", operation="_verify_file_integrity"
            )

        try:
            # Попытка загрузить и проверить JSON
            with open(filepath, "r", encoding="utf-8") as f:
                test_data: Dict[str, Any] = json.load(f)

            # Проверка структуры загруженных данных
            if not self._validate_data_structure(test_data):
                raise StorageError(
                    "Некорректная структура данных во временном файле",
                    operation="_verify_file_integrity",
                )

        except json.JSONDecodeError as e:
            # Ошибка парсинга JSON
            raise StorageError(
                f"Некорректный JSON во временном файле: {e}",
                operation="_verify_file_integrity",
            ) from e
        except Exception as e:
            # Общая ошибка проверки
            raise StorageError(
                f"Ошибка проверки целостности: {e}", operation="_verify_file_integrity"
            ) from e


# Экспорт публичных классов модуля
__all__ = [
    "StorageError",  # Исключение для ошибок работы хранилища
    "HistoryStorage",  # Основной класс хранилища исторических данных
]
