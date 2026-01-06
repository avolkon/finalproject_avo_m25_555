"""Логика регистрации/входа."""

from typing import Optional
                    # Аннотация для Optional[int|User]: значение или None
                    # CURRENT_USER_ID: Optional[int] = None

from datetime import datetime  
                    # Класс datetime.now() для даты регистрации
                    # User(user_id, ..., datetime.now())

import secrets         # Криптографически стойкий генератор
                    # salt = secrets.token_hex(4) — уникальная соль пароля

from .models import User
                    # Относительный импорт класса User из models.py
                    # user = User(...), user.change_password(), user.verify_password()

from .utils import (
    load_users,         # users.json → List[Dict]  
    save_users,         # List[Dict] → users.json (атомарно)
    serialize_user,     # User → Dict для JSON
    deserialize_user    # Dict → User из JSON
)
                    # Все утилиты JSON-хранилища для работы с пользователями



CURRENT_USER_ID: Optional[int] = None
"""Глобальная переменная: ID текущего залогиненного пользователя."""


def register_user(username: str, password: str) -> int:
    """Регистрация нового пользователя."""
    # Загружает текущий список пользователей из users.json
    users = load_users()
    
    # Проверяет уникальность username среди всех пользователей
    if any(u["username"] == username for u in users):
        raise ValueError(f"Имя '{username}' уже занято")
    
    # Валидация длины пароля по ТЗ (≥4 символа)
    if len(password) < 4:
        raise ValueError("Пароль ≥4 символа")
    
    # Генерирует новый user_id: максимум + 1 (или 1 если список пуст)
    user_id = max([u["user_id"] for u in users], default=0) + 1
    # Генерирует уникальную соль (8 случайных байт в hex)
    salt = secrets.token_hex(4)  
    
    # Создаёт объект User с пустым хешем пароля (заполнится change_password)
    user = User(user_id, username, "", salt, datetime.now())
    # Хеширует пароль: sha256(password + salt)
    user.change_password(password)
    
    # Сериализует User → dict и добавляет в список
    users.append(serialize_user(user))
    # Атомарно сохраняет в users.json
    save_users(users)
    
    # Заглушка для portfolios.json (реализуется на следующем шаге)
    _stub_portfolio(user_id)
    
    # Возвращает ID нового пользователя
    return user_id


def login_user(username: str, password: str) -> None:
    """Авторизация пользователя."""
    # Загружает всех пользователей
    users = load_users()
    
    # Ищет пользователя по username
    for data in users:
        if data["username"] == username:
            # Десериализует dict → объект User
            user = deserialize_user(data)
            # Проверяет пароль через хеш
            if user.verify_password(password):
                # Устанавливает глобальную сессию
                global CURRENT_USER_ID
                CURRENT_USER_ID = user.user_id
                # Сообщение ТЗ: "Вы вошли как 'alice'"
                print(f"Вы вошли как '{username}'")
                return  # Успешный выход
    
    # Если не найден или пароль неверный
    raise ValueError("Пользователь/пароль неверны")


def get_current_user() -> Optional[User]:
    """Получить текущего залогиненного пользователя."""
    # Нет активной сессии
    if CURRENT_USER_ID is None:
        return None
    # Загружает список пользователей
    users = load_users()
    # Ищет по user_id
    for data in users:
        if data["user_id"] == CURRENT_USER_ID:
            return deserialize_user(data)
    return None  # Не найден (редкий случай)


def _stub_portfolio(user_id: int) -> None:
    """Заглушка: создание пустого портфеля."""
    # portfolios.json реализуется на следующем шаге ТЗ (Wallet/Portfolio)
    pass
