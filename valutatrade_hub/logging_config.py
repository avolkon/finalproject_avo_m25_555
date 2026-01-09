"""Модуль конфигурации системы логирования ValutaTrade Hub."""

import logging
import logging.handlers
import json
from pathlib import Path
from typing import Dict, Any

from .infra.settings import SettingsLoader, ConfigError


class JSONFormatter(logging.Formatter):
    """Пользовательский форматтер для логирования в формате JSON.

    Наследуется от стандартного logging.Formatter и преобразует
    записи логов в структурированный JSON формат.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Форматирование записи лога в строку JSON.

        Args:
            record: Объект записи лога из модуля logging

        Returns:
            Строка в формате JSON с данными лога
        """
        # Базовые поля лога
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),  # Временная метка
            "level": record.levelname,  # Уровень логирования
            "logger": record.name,  # Имя логгера
            "message": record.getMessage(),  # Основное сообщение
        }

        # Добавление дополнительных полей из атрибутов записи
        # Исключаем стандартные атрибуты LogRecord
        standard_attrs = {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }

        # Добавление пользовательских атрибутов
        for attr_name in dir(record):
            if not attr_name.startswith("_") and attr_name not in standard_attrs:
                try:
                    attr_value = getattr(record, attr_name)
                    # Проверка что значение сериализуемо в JSON
                    if isinstance(attr_value, (str, int, float, bool, type(None))):
                        log_data[attr_name] = attr_value
                except (AttributeError, TypeError):
                    # Пропускаем атрибуты которые нельзя получить или сериализовать
                    continue

        # Сериализация в JSON строку
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging() -> None:
    """Основная функция настройки системы логирования.

    Raises:
        ConfigError: При ошибках загрузки конфигурации
        RuntimeError: При критических ошибках настройки логирования
    """
    try:
        # Получение экземпляра SettingsLoader для доступа к конфигурации
        settings = SettingsLoader()

        # Получение параметров логирования из настроек
        log_format = settings.get("log_format", "detailed")  # Формат логов
        log_level_name = settings.get("log_level", "INFO")  # Уровень логирования
        log_max_size_mb = settings.get("log_max_size_mb", 10)  # Макс. размер файла (МБ)
        log_backup_count = settings.get(
            "log_backup_count", 5
        )  # Количество backup файлов
        logs_dir_name = settings.get("logs_dir", "logs")  # Директория логов
        log_console = settings.get("log_console", False)  # Вывод в консоль

        # Преобразование строкового уровня логирования в числовой
        log_level = getattr(logging, log_level_name.upper(), logging.INFO)

        # Создание объекта Path для директории логов
        logs_dir = Path(logs_dir_name)

        # Создание директории логов если она не существует
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Настройка корневого логгера (базовый уровень)
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Очистка существующих handlers для избежания дублирования
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Создание основного файлового handler с ротацией по размеру
        main_log_file = logs_dir / "valutatrade.log"
        main_file_handler = logging.handlers.RotatingFileHandler(
            filename=main_log_file,  # Путь к основному файлу логов
            maxBytes=log_max_size_mb * 1024 * 1024,  # Макс. размер в байтах
            backupCount=log_backup_count,  # Количество backup файлов
            encoding="utf-8",  # Кодировка UTF-8 для Unicode
        )

        # Выбор формата логов на основе конфигурации
        if log_format == "json":
            formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
        else:
            # Строковый формат (detailed)
            formatter = logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )

        # Применение форматтера к handler
        main_file_handler.setFormatter(formatter)

        # Добавление handler к корневому логгеру
        root_logger.addHandler(main_file_handler)

        # Настройка вывода логов в консоль (опционально, для разработки)
        if log_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)

        # Настройка специализированных логгеров для разных типов операций
        _setup_specialized_loggers(logs_dir, formatter, log_level)

        # Логирование успешной настройки
        root_logger.info(
            f"Система логирования настроена: формат={log_format}, "
            f"уровень={log_level_name}, директория={logs_dir}"
        )

    except ConfigError as e:
        # Ошибка конфигурации - используем базовую настройку
        logging.basicConfig(level=logging.INFO)
        logging.error(
            f"Ошибка конфигурации логирования, используется базовый режим: {e}"
        )
        raise
    except Exception as e:
        # Критическая ошибка - используем базовую настройку
        logging.basicConfig(level=logging.INFO)
        logging.error(f"Критическая ошибка настройки логирования: {e}")
        raise RuntimeError(f"Не удалось настроить логирование: {e}")


def _setup_specialized_loggers(
    logs_dir: Path, formatter: logging.Formatter, log_level: int
) -> None:
    """Настройка специализированных логгеров для разных типов операций.

    Args:
        logs_dir: Директория для хранения файлов логов
        formatter: Форматтер для записи логов
        log_level: Числовой уровень логирования
    """
    # Логгер для доменных операций (buy, sell, register, login)
    actions_logger = logging.getLogger("actions")
    actions_logger.setLevel(log_level)
    actions_logger.propagate = False  # Отключаем propagation в root логгер

    actions_file = logs_dir / "actions.log"
    actions_handler = logging.handlers.RotatingFileHandler(
        filename=actions_file,
        maxBytes=10 * 1024 * 1024,  # 10 МБ для файла действий
        backupCount=5,  # 5 backup файлов
        encoding="utf-8",
    )
    actions_handler.setFormatter(formatter)
    actions_logger.addHandler(actions_handler)

    # Логгер для ошибок (только ERROR и выше)
    errors_logger = logging.getLogger("errors")
    errors_logger.setLevel(logging.ERROR)  # Только ошибки
    errors_logger.propagate = False

    errors_file = logs_dir / "errors.log"
    errors_handler = logging.handlers.RotatingFileHandler(
        filename=errors_file,
        maxBytes=5 * 1024 * 1024,  # 5 МБ для файла ошибок
        backupCount=3,  # 3 backup файла
        encoding="utf-8",
    )
    errors_handler.setFormatter(formatter)
    errors_logger.addHandler(errors_handler)

    # Логгер для операций с базой данных
    database_logger = logging.getLogger("database")
    database_logger.setLevel(log_level)
    database_logger.propagate = False

    database_file = logs_dir / "database.log"
    database_handler = logging.handlers.RotatingFileHandler(
        filename=database_file,
        maxBytes=5 * 1024 * 1024,  # 5 МБ для файла БД
        backupCount=3,
        encoding="utf-8",
    )
    database_handler.setFormatter(formatter)
    database_logger.addHandler(database_handler)

    # Логгер для API операций (будущее использование)
    api_logger = logging.getLogger("api")
    api_logger.setLevel(log_level)
    api_logger.propagate = False

    api_file = logs_dir / "api.log"
    api_handler = logging.handlers.RotatingFileHandler(
        filename=api_file,
        maxBytes=5 * 1024 * 1024,  # 5 МБ для файла API
        backupCount=3,
        encoding="utf-8",
    )
    api_handler.setFormatter(formatter)
    api_logger.addHandler(api_handler)
