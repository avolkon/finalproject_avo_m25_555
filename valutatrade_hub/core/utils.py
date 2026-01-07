"""Утилиты JSON: атомарное сохранение."""

import json  # Стандартная библиотека для сериализации/десериализации
import os

# JSON. Преобразует list[dict] ↔ data/users.json
# Требуется ТЗ: хранение в users.json формате
# DATA_DIR = Path("data"), USERS_FILE = DATA_DIR / "users.json"
# .exists(), .mkdir(), .open() — кроссплатформенные операции
from datetime import datetime

# Используется: salt = secrets.token_hex(4) для уникальной
# соли каждого пользователя (безопаснее random)
from pathlib import Path  # Объектно-ориентированный путь к файлам

# Класс datetime для парсинга/сериализации дат регистрации
# JSON ↔ datetime.fromisoformat(), .isoformat()
from typing import Any

# Type hints для функций JSON utils:
# load_users() → List[Dict[str, Any]]
# serialize_user() → Dict[str, Any]
from .models import User  # Относительный импорт класса User из соседнего модуля

# Требуется для сериализации/десериализации:
# User → serialize_user() → dict → JSON
# JSON → dict → deserialize_user() → User

DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"


def ensure_data_dir() -> None:
    """Создать папку data."""
    DATA_DIR.mkdir(exist_ok=True)


def load_users() -> list[dict[str, Any]]:
    """Загрузить пользователей."""
    # Гарантирует наличие папки data перед чтением
    ensure_data_dir()
    # Проверяет существование файла users.json
    if not USERS_FILE.exists():
        return []  # Возвращает пустой список если файла нет
    # Открывает файл для чтения в UTF-8 кодировке
    with USERS_FILE.open("r", encoding="utf-8") as f:
        # Парсит JSON → List[Dict] для работы с пользователями
        return json.load(f)


def save_users(users: list[dict[str, Any]]) -> None:
    """Сохранить с backup."""
    # Гарантирует наличие папки data
    ensure_data_dir()
    # Создаёт имя backup файла: users.json.backup
    backup = USERS_FILE.with_suffix(".backup")
    # Если файл существует — перемещает в backup (атомарно)
    if USERS_FILE.exists():
        USERS_FILE.replace(backup)

    try:
        # Открывает файл для записи UTF-8
        with USERS_FILE.open("w", encoding="utf-8") as f:
            # Сохраняет список словарей в JSON с отступами
            # ensure_ascii=False — поддержка русских символов
            json.dump(users, f, indent=2, ensure_ascii=False)
    except Exception:
        # При ошибке записи восстанавливает backup
        if backup.exists():
            backup.replace(USERS_FILE)
        raise  # Перебрасывает исключение дальше


def serialize_user(user: User) -> dict[str, Any]:
    """User → dict.
    Преобразует объект User в словарь ТЗ-формата для JSON
    # ID пользователя из геттера user_id
    # Имя пользователя из геттера username
    # Хешированный пароль из геттера hashed_password
    # Уникальная соль пользователя из геттера salt
    # Дата регистрации в ISO формате для JSON
        # .isoformat() → "2025-10-09T12:00:00"
    """
    return {
        "user_id": user.user_id,
        "username": user.username,
        "hashed_password": user.hashed_password,
        "salt": user.salt,
        "registration_date": user.registration_date.isoformat(),
    }

def deserialize_user(data: dict[str, Any]) -> User:
    """dict → User.
    Восстанавливает объект User из словаря ТЗ-формата из JSON
    # user_id из JSON → параметр конструктора User
    # username из JSON → параметр конструктора User
    # hashed_password из JSON → параметр конструктора User
    # salt из JSON → параметр конструктора User
    # registration_date парсится из ISO → datetime.fromisoformat()
    """
    return User(
        data["user_id"],
        data["username"],
        data["hashed_password"],
        data["salt"],
        datetime.fromisoformat(data["registration_date"]),
    )

def load_rates() -> dict[str, dict[str, Any]]:
    """Загрузка курсов валют из rates.json."""
    # Гарантия наличия директории data
    ensure_data_dir()
    # Константа пути к rates.json (аналогично USERS_FILE)
    rates_file = os.path.join("data", "rates.json")
    # Проверка существования файла курсов
    if not os.path.exists(rates_file):
        return {}  # Пустой словарь при отсутствии файла
    try:
        # Открытие файла rates.json в режиме чтения
        with open(rates_file, "r", encoding="utf-8") as f:
            # Парсинг JSON → dict пар типа "EUR_USD": {"rate": float, "updated_at": str}
            return json.load(f)
    except (json.JSONDecodeError, KeyError) as e:
        # Некорректный JSON или структура → пустой fallback
        print(f"Предупреждение: повреждён rates.json: {e}")
        return {}  # Безопасный fallback без EXCHANGE_RATES

