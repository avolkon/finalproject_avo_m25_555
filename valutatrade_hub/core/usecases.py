"""Логика регистрации/входа."""

import json
import os
import secrets  # Стандартные библиотеки
from datetime import datetime        # Парсинг дат ISO
from typing import Dict, List, Optional, Any  # Типизация
from .models import User, Portfolio  # Импорт моделей
from .utils import (
    deserialize_user, serialize_user, load_users, load_rates, save_users, 
    ensure_data_dir
)



DATA_DIR = "data"                    # Директория данных
USERS_FILE = os.path.join(DATA_DIR, "users.json")  # Путь к пользователям
PORTFOLIOS_FILE = os.path.join(DATA_DIR, "portfolios.json")  # Путь к портфелям
# Константа пути к файлу курсов валют
RATES_FILE = os.path.join(DATA_DIR, "rates.json")
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
            wallet = portfolio.get_wallet(currency_code)
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

def buy_currency(user_id: int, currency_code: str, amount: float) -> None:
    """Покупка валюты за USD."""
    portfolio = get_portfolio(user_id)  # Загрузка портфеля пользователя
    currency_code = currency_code.upper()  # Нормализация кода валюты
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    if (currency_code not in Portfolio.EXCHANGE_RATES or
            currency_code == "USD"):
        raise ValueError("Неизвестная валюта или нельзя купить USD")
    usd_wallet = portfolio.get_wallet("USD")  # Гарантированно существует
    assert usd_wallet is not None
    target_wallet = portfolio.get_wallet(currency_code)
    if target_wallet is None:
        portfolio.add_currency(currency_code)  # Создание кошелька если отсутствует
        target_wallet = portfolio.get_wallet(currency_code)
    assert target_wallet is not None
    usd_cost = amount * Portfolio.EXCHANGE_RATES[currency_code]  # Стоимость в USD
    if usd_wallet.balance < usd_cost:
        raise ValueError("Недостаточно USD на балансе")
    usd_wallet.withdraw(usd_cost)  # Списание USD
    target_wallet.deposit(amount)  # Зачисление целевой валюты
    save_portfolio(portfolio)  # Сохранение обновленного портфеля


# def buy_currency(user_id: int, currency_code: str, amount: float) -> None:
#     """Покупка валюты: списать USD, начислить целевую валюту."""
#     # Загрузка портфеля текущего пользователя
#     portfolio = get_portfolio(user_id)
    
#     # Нормализация кода валюты в верхний регистр
#     currency_code = currency_code.upper()
    
#     # Валидация: сумма должна быть положительной
#     if amount <= 0:
#         raise ValueError("Сумма должна быть положительной")
    
#     # Валидация: валюта поддерживается и не USD
#     if (currency_code not in Portfolio.EXCHANGE_RATES or 
#         currency_code == 'USD'):
#         raise ValueError("Валюта не поддерживается")
    
#     # Получение USD кошелька (гарантировано get_portfolio)
#     usd_wallet = portfolio.get_wallet('USD')
#     # Защита от None (mypy strict)
#     # Вместо assert можно:
#     if usd_wallet is None:
#         raise ValueError("Критическая ошибка: USD кошелёк отсутствует")
#         # Создание целевого кошелька если не существует
    
#     if portfolio.get_wallet(currency_code) is None:
#         portfolio.add_currency(currency_code)
    
#     # Расчёт стоимости покупки в USD
#     usd_cost = amount * Portfolio.EXCHANGE_RATES[currency_code]
    
#     # Проверка достаточности USD баланса
#     if usd_wallet.balance < usd_cost:
#         raise ValueError("Недостаточно USD")
    
#     # Списание USD за покупку
#     usd_wallet.withdraw(usd_cost)
    
#     # Получение целевого кошелька ПОСЛЕ создания
#     target_wallet = portfolio.get_wallet(currency_code)
#     # Защита от None (логическая ошибка если add_currency не сработал)
#     if target_wallet is None:
#         raise ValueError("Критическая ошибка: создание кошелька")

#     # Начисление купленной валюты
#     target_wallet.deposit(amount)
    
#     # Сохранение обновлённого портфеля
#     save_portfolio(portfolio)

def sell_currency(user_id: int, currency_code: str, amount: float) -> None:
    """Продажа валюты: списать целевую, начислить USD."""
    # Загрузка портфеля текущего пользователя
    portfolio = get_portfolio(user_id)
    
    # Нормализация кода валюты в верхний регистр
    currency_code = currency_code.upper()
    
    # Валидация: сумма должна быть положительной
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    
    # Валидация: валюта поддерживается и не USD
    if (currency_code not in Portfolio.EXCHANGE_RATES or 
        currency_code == 'USD'):
        raise ValueError("Валюта не поддерживается")
    
    # Получение целевого кошелька для продажи
    target_wallet = portfolio.get_wallet(currency_code)
    # Защита от None: кошелёк должен существовать для продажи
    if target_wallet is None:
        raise ValueError("Критическая ошибка: целевой кошелёк отсутствует")
    
    # Получение USD кошелька (гарантировано get_portfolio)
    usd_wallet = portfolio.get_wallet('USD')
    # Защита от None для mypy
    if usd_wallet is None:
        raise ValueError("Критическая ошибка: USD кошелёк отсутствует")
    
    # Проверка достаточности баланса целевой валюты
    if target_wallet.balance < amount:
        raise ValueError("Недостаточно средств на кошельке")
    
    # Расчёт дохода в USD от продажи
    usd_income = amount * Portfolio.EXCHANGE_RATES[currency_code]
    
    # Списание валюты с целевого кошелька
    target_wallet.withdraw(amount)
    
    # Начисление USD на базовый кошелёк
    usd_wallet.deposit(usd_income)
    
    # Сохранение обновлённого портфеля
    save_portfolio(portfolio)

def get_rate(from_currency: str, to_currency: str) -> tuple[float, str, str]:
    """Получение курса валюты с приоритетом rates.json."""
    # Загрузка курсов из JSON или пустой словарь
    rates = load_rates()
    # Нормализация кодов валют в верхний регистр
    from_code = from_currency.upper()
    to_code = to_currency.upper()
    # Проверка поддержки обеих валют в EXCHANGE_RATES
    if (from_code not in Portfolio.EXCHANGE_RATES or
            to_code not in Portfolio.EXCHANGE_RATES):
        raise ValueError("Валюта не поддерживается")
    # Формирование ключа пары (EUR_USD)
    pair = f"{from_code}_{to_code}"
    # Поиск прямого курса в rates.json с fallback
    rate_data = rates.get(pair, {})
    direct_rate = (rate_data.get("rate", 
                Portfolio.EXCHANGE_RATES[from_code]))
    # Время обновления или заглушка
    timestamp = rate_data.get("updated_at", "N/A")
    # Источник: JSON или статический fallback
    source = "rates.json" if pair in rates else "Fallback"
    return (direct_rate, timestamp, source)  # Кортеж для CLI
