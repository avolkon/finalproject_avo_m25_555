"""Модель User с приватными атрибутами и геттерами/сеттерами."""

import hashlib  # Библиотека хеширования. Используется hashlib.sha256()

# для создания одностороннего псевдо-хеша пароля + salt
from datetime import datetime

# Класс datetime для хранения даты регистрации пользователя
# Требуется ТЗ: _registration_date: datetime
# Используется в JSON: .isoformat() → "2025-10-09T12:00:00"
from typing import NoReturn

# Аннотация типа для методов без возвращаемого значения
# Используется в change_password() → NoReturn (void)
# Указывает: метод изменяет состояние объекта, ничего не возвращает


class User:
    """Пользователь системы."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime
    ):
        """Конструктор принимает все параметры."""
        self._user_id = user_id
        self._username = username
        self._hashed_password = hashed_password
        self._salt = salt
        self._registration_date = registration_date

    # Геттеры для ВСЕХ атрибутов
    @property
    def user_id(self) -> int:
        """Уникальный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Сеттер username: не пустой."""
        if not value or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self) -> str:
        """Хешированный пароль."""
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Соль пользователя."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации."""
        return self._registration_date

    def get_user_info(self) -> str:
        """Информация без пароля."""
        return (f"ID: {self.user_id}, Имя: {self.username}, "
                f"Регистрация: {self.registration_date}")

    def change_password(self, new_password: str) -> NoReturn:
        """Смена пароля с хешированием."""
        if len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        
        # sha256(password + salt)
        data = new_password.encode('utf-8') + self.salt.encode('utf-8')
        self._hashed_password = hashlib.sha256(data).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Проверка пароля."""
        data = password.encode('utf-8') + self.salt.encode('utf-8')
        return hashlib.sha256(data).hexdigest() == self.hashed_password
