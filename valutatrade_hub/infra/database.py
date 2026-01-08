"""Модуль DatabaseManager - синглтон для работы с JSON-хранилищем данных."""

import json
import shutil
from pathlib import Path
from typing import Any, Optional
import threading

from .settings import SettingsLoader


class DatabaseError(Exception):
    """Пользовательское исключение для ошибок работы с базой данных.
    
    Attributes:
        message: Описание ошибки работы с базой данных
    """
    
    def __init__(self, message: str):
        """Инициализация исключения с сообщением об ошибке.
        
        Args:
            message: Текстовое описание ошибки базы данных
        """
        super().__init__(message)


class DatabaseManager:
    """Синглтон для управления JSON-хранилищем данных платформы.
    
    Класс предоставляет абстракцию над файловым хранилищем данных
    с гарантией атомарности операций и поддержкой backup.
    
    Note:
        Реализация синглтона через __new__ выбрана для консистентности
        с SettingsLoader и простоты поддержки.
    """
    
    # Приватная переменная для хранения единственного экземпляра
    _instance: Optional['DatabaseManager'] = None
    
    # Блокировка для обеспечения потокобезопасности
    _lock = threading.Lock()
    
    # Константы имён файлов данных
    USERS_FILE = "users.json"
    PORTFOLIOS_FILE = "portfolios.json"
    RATES_FILE = "rates.json"
    
    def __new__(cls) -> 'DatabaseManager':
        """Реализация паттерна Singleton через переопределение __new__.
        
        Returns:
            Единственный экземпляр класса DatabaseManager
        """
        with cls._lock:
            # Проверка наличия уже созданного экземпляра
            if cls._instance is None:
                # Создание нового экземпляра
                cls._instance = super().__new__(cls)
                # Флаг инициализации для контроля однократного вызова __init__
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Приватный инициализатор синглтона (вызывается один раз).
        
        Raises:
            RuntimeError: Если SettingsLoader не доступен
        """
        # Проверка что инициализация выполняется только один раз
        if self._initialized:
            return
        
        # Получение экземпляра SettingsLoader для доступа к конфигурации
        self._settings = SettingsLoader()
        
        # Получение пути к директории данных из настроек
        data_dir = self._settings.get('data_dir', 'data')
        self._data_path = Path(data_dir)
        
        # Создание директории данных если она не существует
        self._data_path.mkdir(parents=True, exist_ok=True)
        
        # Установка флага инициализации
        self._initialized = True
    
    def load_users(self) -> list[dict]:
        """Загрузить данные всех пользователей из JSON файла.
        
        Returns:
            Список словарей с данными пользователей
            
        Raises:
            DatabaseError: При ошибках чтения или парсинга JSON
        """
        filepath = self._data_path / self.USERS_FILE
        return self._load_json(filepath, default=[])
    
    def save_users(self, users: list[dict]) -> None:
        """Сохранить данные пользователей в JSON файл.
        
        Args:
            users: Список словарей с данными пользователей
            
        Raises:
            DatabaseError: При ошибках записи в файл
        """
        filepath = self._data_path / self.USERS_FILE
        self._save_json(filepath, users)
    
    def load_portfolios(self) -> list[dict]:
        """Загрузить данные всех портфелей из JSON файла.
        
        Returns:
            Список словарей с данными портфелей
            
        Raises:
            DatabaseError: При ошибках чтения или парсинга JSON
        """
        filepath = self._data_path / self.PORTFOLIOS_FILE
        return self._load_json(filepath, default=[])
    
    def save_portfolios(self, portfolios: list[dict]) -> None:
        """Сохранить данные портфелей в JSON файл.
        
        Args:
            portfolios: Список словарей с данными портфелей
            
        Raises:
            DatabaseError: При ошибках записи в файл
        """
        filepath = self._data_path / self.PORTFOLIOS_FILE
        self._save_json(filepath, portfolios)
    
    def load_rates(self) -> dict:
        """Загрузить данные курсов валют из JSON файла.
        
        Returns:
            Словарь с данными курсов валют
            
        Raises:
            DatabaseError: При ошибках чтения или парсинга JSON
        """
        filepath = self._data_path / self.RATES_FILE
        return self._load_json(filepath, default={})
    
    def save_rates(self, rates: dict) -> None:
        """Сохранить данные курсов валют в JSON файл.
        
        Args:
            rates: Словарь с данными курсов валют
            
        Raises:
            DatabaseError: При ошибках записи в файл
        """
        filepath = self._data_path / self.RATES_FILE
        self._save_json(filepath, rates)
    
    def _load_json(self, filepath: Path, default: Any = None) -> Any:
        """Загрузить данные из JSON файла с обработкой ошибок.
        
        Args:
            filepath: Путь к JSON файлу для загрузки
            default: Значение по умолчанию если файл не существует
            
        Returns:
            Данные из JSON файла или значение по умолчанию
            
        Raises:
            DatabaseError: При ошибках чтения или парсинга JSON
        """
        # Проверка существования файла
        if not filepath.exists():
            return default if default is not None else {}
        
        try:
            # Открытие файла в режиме чтения с UTF-8 кодировкой
            with filepath.open('r', encoding='utf-8') as file:
                # Загрузка и парсинг JSON данных
                return json.load(file)
        except json.JSONDecodeError as e:
            # Ошибка парсинга JSON (некорректный формат)
            raise DatabaseError(f"Ошибка парсинга JSON файла {filepath}: {e}")
        except Exception as e:
            # Общая ошибка чтения файла
            raise DatabaseError(f"Ошибка чтения файла {filepath}: {e}")
    
    def _save_json(self, filepath: Path, data: Any) -> None:
        """Атомарное сохранение данных в JSON файл с backup механизмом.
        
        Args:
            filepath: Путь к JSON файлу для сохранения
            data: Данные для сохранения в JSON формате
            
        Raises:
            DatabaseError: При ошибках записи в файл
        """
        # Создание пути для backup файла (добавление .backup расширения)
        backup_file = filepath.with_suffix(filepath.suffix + '.backup')
        
        # Создание пути для временного файла
        temp_file = filepath.with_suffix(filepath.suffix + '.tmp')
        
        # Шаг 1: Создание backup существующего файла если он есть
        if filepath.exists():
            try:
                # Копирование существующего файла в backup
                shutil.copy2(filepath, backup_file)
            except Exception as e:
                raise DatabaseError(f"Ошибка создания backup файла: {e}")
        
        try:
            # Шаг 2: Сохранение данных во временный файл
            with temp_file.open('w', encoding='utf-8') as file:
                # Сериализация данных в JSON с форматированием
                json.dump(
                    data, 
                    file, 
                    indent=2, 
                    ensure_ascii=False,  # Поддержка Unicode символов
                    default=str          # Преобразование несериализуемых типов в строки
                )
            
            # Шаг 3: Атомарная замена основного файла временным
            temp_file.replace(filepath)
            
            # Шаг 4: Удаление временного файла (если замена прошла успешно)
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
                
        except Exception as e:
            # Шаг 5: Восстановление из backup при ошибке
            if backup_file.exists() and filepath.exists():
                try:
                    backup_file.replace(filepath)
                except Exception as restore_error:
                    raise DatabaseError(
                        f"Ошибка записи и восстановления: {e}, "
                        f"восстановление не удалось: {restore_error}"
                    )
            elif backup_file.exists():
                # Если основного файла не было, просто удаляем backup
                backup_file.unlink(missing_ok=True)
            
            raise DatabaseError(f"Ошибка сохранения данных в {filepath}: {e}")
        finally:
            # Шаг 6: Удаление backup файла если операция успешна
            if backup_file.exists():
                backup_file.unlink(missing_ok=True)

