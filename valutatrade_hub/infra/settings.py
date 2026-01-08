"""Модуль SettingsLoader - синглтон для управления конфигурацией проекта."""

import tomllib
import threading
import copy
from pathlib import Path
from typing import Any, Optional

class ConfigError(Exception):
    """Пользовательское исключение для ошибок загрузки конфигурации.
    
    Attributes:
        message: Описание ошибки конфигурации
    """
    
    def __init__(self, message: str):
        """Инициализация исключения с сообщением об ошибке.
        
        Args:
            message: Текстовое описание ошибки конфигурации
        """
        super().__init__(message)


class SettingsLoader:
    """Синглтон для загрузки и управления конфигурацией из pyproject.toml.
    
    Класс реализует паттерн Singleton для гарантии единственного экземпляра
    в приложении. Конфигурация загружается из секции [tool.valutatrade]
    в файле pyproject.toml.
    
    Note:
        Реализация синглтона через __new__ выбрана как наиболее простая
        и читаемая для Python. Альтернатива через метакласс избыточна
        для данной задачи и сложнее для понимания.
    """
    
    # Приватная переменная для хранения единственного экземпляра
    _instance: Optional['SettingsLoader'] = None
    
    # Блокировка для обеспечения потокобезопасности при создании экземпляра
    _lock = threading.Lock()
    
    def __new__(cls) -> 'SettingsLoader':
        """Реализация паттерна Singleton через переопределение __new__.
        
        Returns:
            Единственный экземпляр класса SettingsLoader
            
        Note:
            Метод __new__ контролирует создание экземпляра класса.
            Гарантируется, что в приложении существует только один
            экземпляр SettingsLoader.
        """
        with cls._lock:
            # Проверка наличия уже созданного экземпляра
            if cls._instance is None:
                # Создание нового экземпляра через вызов родительского __new__
                cls._instance = super().__new__(cls)
                # Флаг инициализации для контроля однократного вызова __init__
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Приватный инициализатор синглтона (вызывается один раз).
        
        Raises:
            ConfigError: При ошибках загрузки или парсинга конфигурации
        """
        # Проверка что инициализация выполняется только один раз
        if self._initialized:
            return
        
        # Поиск и сохранение пути к файлу конфигурации
        self._config_path = self._find_config_file()
        
        # Приватный атрибут для хранения загруженной конфигурации
        self._config: Optional[dict] = None
        
        # Загрузка конфигурации из файла
        self._load_config()
        
        # Установка флага инициализации
        self._initialized = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение настройки по ключу с поддержкой вложенных ключей.
        
        Args:
            key: Ключ настройки (например, 'data_dir' или 'rates.ttl_fiat')
            default: Значение по умолчанию, возвращаемое если ключ не найден
            
        Returns:
            Значение настройки или переданное значение по умолчанию
        """
        # Разделение ключа на части для поддержки вложенных словарей
        keys = key.split('.')
        value = self._config
        
        # Поиск значения по вложенным ключам
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                # Ключ не найден - возвращаем значение по умолчанию
                return default
        
        return value
    
    def reload(self) -> None:
        """Перезагрузить конфигурацию из файла pyproject.toml.
        
        Raises:
            ConfigError: При ошибках загрузки или парсинга конфигурации
        """
        self._load_config()
    
    @property
    def all_settings(self) -> dict:
        """Получить глубокую копию всех настроек конфигурации.
        Returns:
            Словарь со всеми настройками из секции [tool.valutatrade]
        Raises:
            RuntimeError: Если конфигурация не была загружена
        """
        # Проверка что конфигурация была загружена
        if self._config is None:
            raise RuntimeError("Конфигурация не была загружена")
        
        # Возвращаем глубокую копию чтобы защитить оригинальные данные
        return copy.deepcopy(self._config)
    
    def _find_config_file(self) -> Path:
        """Найти файл конфигурации pyproject.toml в иерархии директорий.
        
        Returns:
            Объект Path указывающий на файл pyproject.toml
            
        Raises:
            ConfigError: Если файл pyproject.toml не найден
        """
        # Начинаем поиск с текущей рабочей директории
        current_dir = Path.cwd()
        
        # Поднимаемся вверх по иерархии директорий
        while current_dir != current_dir.parent:
            # Формирование пути к файлу конфигурации
            config_file = current_dir / "pyproject.toml"
            
            # Проверка существования файла
            if config_file.exists():
                return config_file
            
            # Переход на уровень выше
            current_dir = current_dir.parent
        
        # Файл не найден - выбрасываем исключение
        raise ConfigError("Файл конфигурации pyproject.toml не найден")
    
    def _load_config(self) -> None:
        """Загрузить и распарсить конфигурацию из файла pyproject.toml.
        
        Raises:
            ConfigError: При ошибках чтения файла или парсинга TOML
            ConfigError: Если секция [tool.valutatrade] отсутствует
        """
        try:
            # Открытие файла в бинарном режиме для tomllib
            with open(self._config_path, "rb") as file:
                # Парсинг TOML файла
                config = tomllib.load(file)
        except FileNotFoundError:
            raise ConfigError(f"Файл конфигурации не найден: {self._config_path}")
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"Ошибка парсинга TOML файла: {e}")
        
        # Проверка наличия необходимой секции конфигурации
        if 'tool' not in config or 'valutatrade' not in config['tool']:
            raise ConfigError("Секция [tool.valutatrade] не найдена в pyproject.toml")
        
        # Сохранение конфигурации из секции valutatrade
        self._config = config['tool']['valutatrade']

