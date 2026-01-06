"""Логика регистрации/входа."""

import json
import os
import secrets  # Стандартные библиотеки
from datetime import datetime        # Парсинг дат ISO
from typing import Dict, List, Optional, Any  # Типизация
from .models import User, Portfolio, Wallet  # Импорт моделей
from .utils import (
    deserialize_user, serialize_user, load_users, save_users, 
    ensure_data_dir
)



DATA_DIR = "data"                    # Директория данных
USERS_FILE = os.path.join(DATA_DIR, "users.json")  # Путь к пользователям
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")  # Путь к портфелям

CURRENT_USER_ID: Optional[int] = None  # Глобальная сессия пользователя

def serialize_portfolio(portfolio: Portfolio) -> Dict:  # Сериализация → JSON
    """Сериализация портфеля."""
    return {
        'user_id': portfolio.user_id,  # ID владельца
        'wallets': {
            code: {                  # Каждый кошелёк
                'currency_code': wallet.currency_code,  # Код валюты
                'balance': wallet.balance  # Баланс
            }
            for code, wallet in portfolio.wallets.items()  # Перебор
        }
    }


def deserialize_portfolio(data: Dict[str, Any], user_id: int) -> Portfolio:
    """Десериализация портфеля из JSON в объект Portfolio."""
    portfolio = Portfolio(user_id)  # type: Portfolio  # Создание объекта портфеля
    
    wallets_data = data.get('wallets', {})  # type: Dict[str, Dict[str, Any]]
    # Безопасное извлечение данных о кошельках
    
    for currency_code, wallet_data in wallets_data.items():  # Итерация по всем валютам
        try:
            # ВАЛИДАЦИЯ И ПРИВЕДЕНИЕ ТИПА БАЛАНСА
            balance = float(wallet_data['balance'])  # Преобразование строки/числа в float
            
            # СОЗДАНИЕ КОШЕЛЬКА С БАЛАНСОМ
            portfolio.add_currency(currency_code)  # Создаёт кошелёк с balance=0.0
            
            # ПОЛУЧЕНИЕ И ПРОВЕРКА КОШЕЛЬКА
            wallet = portfolio.get_wallet(currency_code)  # type: Optional[Wallet]
            if wallet is None:
                # ЛОГИРОВАНИЕ КРИТИЧЕСКОЙ ОШИБКИ (невозможное состояние)
                print(f"🚨 Критическая ошибка: кошелёк {currency_code} создан, но не найден")
                continue  # Пропуск этого кошелька
            
            # УСТАНОВКА РЕАЛЬНОГО БАЛАНСА
            wallet.balance = balance  # type: ignore  # Игнор для mypy (Optional[Wallet])
            
        except KeyError as e:
            # ОТСУТСТВИЕ ОБЯЗАТЕЛЬНОГО ПОЛЯ 'balance'
            print(f"⚠️ Отсутствует поле 'balance' для кошелька {currency_code}: {e}")
            continue  # Пропуск проблемного кошелька
            
        except ValueError as e:
            # НЕВОЗМОЖНОСТЬ ПРЕОБРАЗОВАТЬ balance В float
            print(f"⚠️ Некорректный баланс для кошелька {currency_code}: {e}")
            continue  # Пропуск проблемного кошелька
            
        except TypeError as e:
            # НЕПРАВИЛЬНЫЙ ТИП ДАННЫХ
            print(f"⚠️ Ошибка типа данных для кошелька {currency_code}: {e}")
            continue  # Пропуск проблемного кошелька
    
    return portfolio  # Возврат полностью десериализованного объекта

def _initialize_user_portfolio(user_id: int) -> None:
    """Инициализация портфеля нового пользователя с USD кошельком."""
    portfolio = Portfolio(user_id)       # Создание объекта Portfolio
    portfolio.add_currency('USD')        # Добавление базовой валюты
    
    portfolios = load_portfolios()       # Текущие портфели из JSON
    portfolio_data = serialize_portfolio(portfolio)  # OOP → Dict для JSON
    
    # Проверка дублей (race condition safe)
    if not any(p['user_id'] == user_id for p in portfolios):
        portfolios.append(portfolio_data)  # ✅ Теперь portfolio_data существует!
        save_portfolios(portfolios)        # Атомарное сохранение

def register_user(username: str, password: str) -> int:
    """Регистрация нового пользователя."""
    users = load_users()  # Загрузка текущих пользователей
    
    # Проверка уникальности username (case-insensitive по ТЗ)
    username_lower = username.lower()  # Приведение к нижнему регистру для проверки
    if any(u["username"].lower() == username_lower for u in users):
        raise ValueError(f"Имя '{username}' уже занято")  # Точное сообщение из ТЗ
    
    # Валидация пароля по ТЗ (≥4 символа)
    if len(password) < 4:
        raise ValueError("Пароль ≥4 символа")  # Точная формулировка ТЗ
    
    # Генерация нового user_id: максимум существующих + 1 (или 1 если пусто)
    user_id = max([u["user_id"] for u in users], default=0) + 1  # Инкремент ID
    salt = secrets.token_hex(4)  # Криптографически стойкая соль (8 байт в hex)
    
    # Создание объекта User с временным пустым хешем
    user = User(user_id, username, "", salt, datetime.now())  # OOP-first подход
    user.change_password(password)  # Хеширование пароля: sha256(password + salt)
    
    # Сериализация User → Dict и добавление в список
    users.append(serialize_user(user))  # Стандартный сериализатор
    save_users(users)  # Атомарное сохранение в users.json
    
    # Создание начального портфеля с USD кошельком
    _initialize_user_portfolio(user_id)  # Заменяет _stub_portfolio
    
    return user_id  # Возврат ID нового пользователя для CLI

def login_user(username: str, password: str) -> None:
    """Авторизация пользователя."""
    users = load_users()  # Все пользователи из JSON
    
    for user_data in users:  # Перебор всех записей пользователей
        if user_data["username"].lower() == username.lower():  # Case-insensitive поиск
            user = deserialize_user(user_data)  # Dict → User объект (OOP паттерн)
            
            if user.verify_password(password):  # Проверка хеша пароля
                global CURRENT_USER_ID  # Модификация глобальной сессии
                CURRENT_USER_ID = user.user_id  # Установка текущего пользователя
                print(f"Вы вошли как '{username}'")  # Точный формат вывода ТЗ
                # Из объекта (consistent)
                return  # Успешный ранний возврат
            
            raise ValueError("Неверный пароль")  # Точное сообщение ТЗ
    
    raise ValueError("Пользователь не найден")  # Точное сообщение ТЗ


def get_current_user() -> User | None:
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



"""
Бизнес-логика: работа с пользователями и портфелями.
"""

def load_portfolios() -> List[Dict]: # Загрузка портфелей
    """Загрузка портфелей."""
    ensure_data_dir()                # Проверка директории
    try:
        with open(PORTFOLIOS_FILE, 'r', encoding='utf-8') as f:  # Чтение
            return json.load(f)      # Парсинг в список
    except FileNotFoundError:        # Файл не найден
        return []                    # Пустой список


def save_portfolios(portfolios: List[Dict]) -> None:  # Сохранение
    """Сохранение портфелей."""
    with open(PORTFOLIOS_FILE, 'w', encoding='utf-8') as f:  # Запись
        json.dump(portfolios, f, indent=2, ensure_ascii=False)  # Форматированный JSON


def load_user(user_id: int) -> Optional[User]:  # Загрузка по ID
    """Загрузка пользователя."""
    users = load_users()             # Список из JSON
    for u in users:                  # Перебор записей. Поиск совпадения
        if u['user_id'] == user_id:
            return deserialize_user(u)  # Стандартный десериализатор
    return None                      # Пользователь не найден


def load_portfolio(user_id: int) -> Optional[Portfolio]:  # Полная десериализация
    """Загрузка портфеля."""
    portfolios = load_portfolios()   # Список портфелей
    for p in portfolios:             # Поиск по user_id
        if p['user_id'] == user_id:
            return deserialize_portfolio(p, user_id)  # ✅ OOP-first
    return None                      # Отсутствует


def get_portfolio(user_id: int) -> Portfolio:  # Автоматическое создание
    """Получить/создать портфель."""
    portfolio = load_portfolio(user_id)  # Попытка загрузки
    if portfolio is None:            # Новый портфель
        portfolio = Portfolio(user_id)  # Создание
        portfolio.add_currency('USD')  # Базовый кошелёк. USD по умолчанию
    return portfolio                 # Объект готов


def save_portfolio(portfolio: Portfolio) -> None:  # Объект → JSON
    """Сохранение портфеля."""
    portfolios = load_portfolios()   # Текущий список
    portfolio_data = serialize_portfolio(portfolio)  # ✅ Сериализация
    
    for i, p in enumerate(portfolios):  # Поиск позиции
        if p['user_id'] == portfolio.user_id:  # Замена существующего
            portfolios[i] = portfolio_data  # Обновление
            save_portfolios(portfolios)  # Атомарное сохранение
            return                   # Готово
            
    portfolios.append(portfolio_data)  # Новый портфель
    save_portfolios(portfolios)      # Финальное сохранение
