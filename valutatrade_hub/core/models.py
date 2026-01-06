# """Модель User с приватными атрибутами и геттерами/сеттерами."""

# import hashlib  # Библиотека хеширования. Используется hashlib.sha256()

# # для создания одностороннего псевдо-хеша пароля + salt
# from datetime import datetime

# # Класс datetime для хранения даты регистрации пользователя
# # Требуется ТЗ: _registration_date: datetime
# # Используется в JSON: .isoformat() → "2025-10-09T12:00:00"
# from typing import NoReturn

# # Аннотация типа для методов без возвращаемого значения
# # Используется в change_password() → NoReturn (void)
# # Указывает: метод изменяет состояние объекта, ничего не возвращает


# class User:
#     """Пользователь системы."""

#     def __init__(
#         self,
#         user_id: int,
#         username: str,
#         hashed_password: str,
#         salt: str,
#         registration_date: datetime,
#     ):
#         """Конструктор принимает все параметры."""
#         self._user_id = user_id
#         self._username = username
#         self._hashed_password = hashed_password
#         self._salt = salt
#         self._registration_date = registration_date

#     # Геттеры для ВСЕХ атрибутов
#     @property
#     def user_id(self) -> int:
#         """Уникальный идентификатор пользователя."""
#         return self._user_id

#     @property
#     def username(self) -> str:
#         """Имя пользователя."""
#         return self._username

#     @username.setter
#     def username(self, value: str) -> None:
#         """Сеттер username: не пустой."""
#         if not value or not value.strip():
#             raise ValueError("Имя пользователя не может быть пустым")
#         self._username = value.strip()

#     @property
#     def hashed_password(self) -> str:
#         """Хешированный пароль."""
#         return self._hashed_password

#     @property
#     def salt(self) -> str:
#         """Соль пользователя."""
#         return self._salt

#     @property
#     def registration_date(self) -> datetime:
#         """Дата регистрации."""
#         return self._registration_date

#     def get_user_info(self) -> str:
#         """Информация без пароля."""
#         return (
#             f"ID: {self.user_id}, Имя: {self.username}, "
#             f"Регистрация: {self.registration_date}"
#         )

#     def change_password(self, new_password: str) -> NoReturn:
#         """Смена пароля с хешированием."""
#         if len(new_password) < 4:
#             raise ValueError("Пароль должен быть не короче 4 символов")

#         # sha256(password + salt)
#         data = new_password.encode("utf-8") + self.salt.encode("utf-8")
#         self._hashed_password = hashlib.sha256(data).hexdigest()

#     def verify_password(self, password: str) -> bool:
#         """Проверка пароля."""
#         data = password.encode("utf-8") + self.salt.encode("utf-8")
#         return hashlib.sha256(data).hexdigest() == self.hashed_password


"""
Модели домена: User, Wallet, Portfolio.
"""

import hashlib                       # Для хеширования паролей
from datetime import datetime        # Для дат регистрации
from typing import Dict, Optional  # Аннотации типов
from .utils import load_users


class User:
    """Пользователь системы."""
    
    def __init__(                # Конструктор пользователя
        self,
        user_id: int,            # Уникальный ID
        username: str,           # Имя пользователя
        hashed_password: str,    # Захешированный пароль
        salt: str,               # Соль для хеша
        registration_date: datetime  # Дата регистрации
    ):
        self._user_id = user_id              # Приватный ID
        self._username = username            # Приватное имя
        self._hashed_password = hashed_password  # Приватный хеш
        self._salt = salt                    # Приватная соль
        self._registration_date = registration_date  # Приватная дата

    @property
    def user_id(self) -> int:           # Геттер ID
        """ID пользователя."""
        return self._user_id             # Возврат приватного значения

    @property
    def username(self) -> str:          # Геттер имени
        """Имя пользователя."""
        return self._username            # Возврат приватного значения
    
    @property
    def hashed_password(self) -> str:
        """Захешированный пароль пользователя."""
        # Возврат приватного хеша для сериализации
        return self._hashed_password

    @property
    def salt(self) -> str:
        """Уникальная соль для хеширования пароля."""
        # Соль нужна для verify_password()
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата и время регистрации пользователя."""
        # ISO формат для JSON: 2025-10-09T12:00:00
        return self._registration_date

    def get_user_info(self) -> str:     # Метод информации
        """Информация без пароля."""
        return (f"ID: {self._user_id}, Username: {self._username}, "  # Формирование строки
                f"Дата: {self._registration_date}")  # Добавление даты

    def change_password(self, new_password: str) -> None:  # Смена пароля
        """Изменение пароля с хешем."""
        if len(new_password) < 4:       # Проверка длины пароля
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._hashed_password = hashlib.sha256(  # Создание нового хеша
            new_password.encode() + self._salt.encode()  # Пароль + соль в байты
        ).hexdigest()                       # Получение hex строки

    def verify_password(self, password: str) -> bool:  # Верификация
        """Проверка пароля."""
        check_hash = hashlib.sha256(     # Вычисление тестового хеша
            password.encode() + self._salt.encode()  # Входной пароль + соль
        ).hexdigest()                       # В hex формате
        return check_hash == self._hashed_password  # Сравнение хешей


class Wallet:
    """Кошелёк одной валюты."""

    def __init__(self, currency_code: str, balance: float = 0.0):  # Конструктор
        if not isinstance(balance, (int, float)) or balance < 0:  # Валидация баланса
            raise ValueError("Баланс не может быть отрицательным")
        self.currency_code = currency_code.upper()  # Код в верхний регистр
        self._balance = float(balance)              # Приведение к float

    @property
    def balance(self) -> float:         # Геттер баланса
        """Текущий баланс."""
        return self._balance             # Возврат приватного значения

    @balance.setter
    def balance(self, value: float) -> None:  # Сеттер баланса
        """Установка баланса с проверкой."""
        if not isinstance(value, (int, float)) or value < 0:  # Валидация
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)        # Приведение и установка

    def deposit(self, amount: float) -> None:  # Пополнение
        """Пополнение."""
        if amount <= 0:                     # Проверка суммы
            raise ValueError("'amount' должен быть положительным числом")
        self._balance += amount              # Добавление к балансу

    def withdraw(self, amount: float) -> None:  # Снятие
        """Снятие."""
        if amount <= 0:                     # Проверка суммы
            raise ValueError("'amount' должен быть положительным числом")
        if amount > self._balance:          # Проверка достаточности
            raise ValueError("Недостаточно средств")
        self._balance -= amount              # Вычитание из баланса

    def get_balance_info(self) -> str:  # Информация
        """Информация о балансе."""
        return f"{self.currency_code}: {self._balance:.4f}"  # Форматированная строка


class Portfolio:
    """Портфель пользователя."""

    EXCHANGE_RATES = {                  # Фиксированные курсы
        'BTC': 59337.21,                # Биткоин к USD
        'EUR': 1.0786,                  # Евро к USD
        'USD': 1.0,                     # Доллар базовый
        'RUB': 0.01016,                 # Рубль к USD
        'ETH': 3720.00                  # Эфир к USD
    }

    def __init__(self, user_id: int):   # Конструктор портфеля
        self._user_id = user_id          # ID владельца
        self._wallets: Dict[str, Wallet] = {}  # Словарь кошельков

    @property
    def user_id(self) -> int:           # Геттер ID
        """ID пользователя."""
        return self._user_id             # Возврат приватного значения

    @property
    def user(self) -> Optional['User']:            # Свойство пользователя
        """Связанный пользователь (stub)."""
        from .usecases import load_user  # Импорт функции загрузки
        return load_user(self._user_id)  # Загрузка по ID # Возвращает User | None

    @property
    def wallets(self) -> Dict[str, Wallet]:  # Копия кошельков
        """Копия кошельков."""
        import copy                      # Импорт модуля копирования
        return copy.deepcopy(self._wallets)  # Глубокая копия словаря

    def add_currency(self, currency_code: str) -> None:  # Добавление валюты
        """Добавить кошелёк."""
        code = currency_code.upper()     # Нормализация кода
        if code in self._wallets:        # Проверка существования
            raise ValueError(f"Кошелёк {code} уже существует")
        self._wallets[code] = Wallet(code)  # Создание и добавление

    def get_wallet(self, currency_code: str) -> Optional[Wallet]:  # Получение
        """Получить кошелёк."""
        return self._wallets.get(currency_code.upper())  # По коду из словаря

    def get_total_value(self, base_currency: str = 'USD') -> float:  # Стоимость
        """Общая стоимость в базовой валюте."""
        base_rate = self.EXCHANGE_RATES.get(base_currency.upper(), 1.0)  # Курс базы
        total = 0.0                         # Инициализация суммы
        for wallet in self._wallets.values():  # Перебор кошельков
            rate = self.EXCHANGE_RATES.get(wallet.currency_code, 1.0)  # Курс актива
            total += wallet.balance * (rate / base_rate)  # Добавление стоимости
        return total                        # Возврат итога
