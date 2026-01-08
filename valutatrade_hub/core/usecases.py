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
# Импорт функций работы с валютами из модуля currencies
from .currencies import get_currency, get_supported_currencies
# Импорт пользовательских исключений
from .exceptions import InsufficientFundsError, CurrencyNotFoundError, ApiRequestError


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
    
    # СОЗДАНИЕ НАЧАЛЬНОГО ПОРТФЕЛЯ С USD КОШЕЛЬКОМ
    portfolio = create_initial_portfolio(user_id)  # Создание портфеля через фабрику
    save_portfolio(portfolio)  # Явное сохранение портфеля в файл
    
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


def get_portfolio(user_id: int) -> Portfolio:
    """
    Получение портфеля пользователя с автоматическим созданием при отсутствии.
    Обновленная версия: использует фабрику create_empty_portfolio
    для устранения дублирования кода создания портфеля с USD.
    Args:
        user_id: Уникальный идентификатор пользователя
    Returns:
        Portfolio: Существующий или новый портфель с кошельком USD
    """
    # Попытка загрузить существующий портфель из хранилища
    portfolio = load_portfolio(user_id)
    
    if portfolio is None:  # Если портфель не найден
        # Использование фабрики для создания нового портфеля
        portfolio = create_empty_portfolio(user_id)
    
    return portfolio  # Возврат портфеля (нового или загруженного)

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

def create_empty_portfolio(user_id: int) -> Portfolio:
    """
    Фабрика для создания пустого портфеля с базовым USD кошельком.
    Args:
        user_id: Уникальный идентификатор пользователя
    Returns:
        Portfolio: Объект портфеля с кошельком USD
    Raises:
        TypeError: Если user_id не является целым числом
        ValueError: При ошибке добавления валюты (дубликат USD)
    """
    if not isinstance(user_id, int):  # Проверка типа user_id
        raise TypeError("user_id должен быть целым числом")
    
    portfolio = Portfolio(user_id)     # Создание объекта портфеля
    portfolio.add_currency('USD')      # Добавление базовой валюты USD
    
    return portfolio                   # Возврат готового портфеля

def create_initial_portfolio(user_id: int) -> Portfolio:
    """
    Создание начального портфеля для нового пользователя.
    Заменяет старую _initialize_user_portfolio, убирая side effects.
    Использует фабрику create_empty_portfolio для создания портфеля.
    Args:
        user_id: Уникальный идентификатор пользователя
    Returns:
        Portfolio: Объект портфеля с кошельком USD
    Raises:
        TypeError: Если user_id не является целым числом
        ValueError: При ошибке создания портфеля или добавления USD
    """
    # Использование фабричной функции для создания портфеля
    portfolio = create_empty_portfolio(user_id)
    
    return portfolio  # Возврат созданного портфеля без сохранения

def buy_currency(user_id: int, currency_code: str, amount: float) -> None:
    """Покупка валюты за USD.
    Args:
        user_id: Идентификатор пользователя
        currency_code: Код покупаемой валюты
        amount: Сумма покупки в целевой валюте
    Raises:
        ValueError: При некорректных параметрах
        CurrencyNotFoundError: Если валюта не поддерживается
        InsufficientFundsError: Если недостаточно USD на балансе
    """
    # Загрузка портфеля пользователя
    portfolio = get_portfolio(user_id)
    
    # Нормализация кода валюты в верхний регистр
    currency_code = currency_code.upper()
    
    # Проверка что сумма покупки положительная
    if amount <= 0:
        raise ValueError("""Некорректная сумма →
    'amount' должен быть положительным числом""")
    
    # Проверка что не пытаются купить USD за USD
    if currency_code == "USD":
        raise ValueError("Нельзя купить USD за USD")
    
    # Валидация валюты через get_currency() - автоматически выбросит CurrencyNotFoundError
    currency_obj = get_currency(currency_code)
    
    # Получение USD кошелька (гарантировано get_portfolio)
    usd_wallet = portfolio.get_wallet("USD")
    
    # Защита от None - USD кошелёк всегда должен существовать
    if usd_wallet is None:
        raise ValueError("Критическая ошибка: USD кошелёк отсутствует")
    
    # Получение или создание кошелька для целевой валюты
    target_wallet = portfolio.get_wallet(currency_code)
    if target_wallet is None:
        # Создание кошелька если отсутствует
        portfolio.add_currency(currency_code)
        target_wallet = portfolio.get_wallet(currency_code)
    
    # Защита от None после создания кошелька
    if target_wallet is None:
        raise ValueError(f"Критическая ошибка: не удалось создать кошелёк {currency_code}")
    
    # Расчёт стоимости покупки в USD (используем статический курс из Portfolio)
    usd_cost = amount * Portfolio.EXCHANGE_RATES[currency_code]
    
    # Проверка достаточности средств на USD кошельке
    if usd_wallet.balance < usd_cost:
        raise InsufficientFundsError(
            available=usd_wallet.balance,  # Доступный баланс USD
            required=usd_cost,             # Требуемая сумма USD
            code="USD"                     # Код валюты операции (USD)
        )
    
    # Списание USD с кошелька пользователя
    usd_wallet.withdraw(usd_cost)
    
    # Зачисление целевой валюты на кошелёк пользователя
    target_wallet.deposit(amount)
    
    # Сохранение обновлённого портфеля
    save_portfolio(portfolio)


def sell_currency(user_id: int, currency_code: str, amount: float) -> None:
    """Продажа валюты: списать целевую, начислить USD.
    Args:
        user_id: Идентификатор пользователя
        currency_code: Код продаваемой валюты
        amount: Сумма продажи в целевой валюте
    Raises:
        ValueError: При некорректных параметрах
        CurrencyNotFoundError: Если валюта не поддерживается
        InsufficientFundsError: Если недостаточно средств для продажи
    """
    # Загрузка портфеля текущего пользователя
    portfolio = get_portfolio(user_id)
    
    # Нормализация кода валюты в верхний регистр
    currency_code = currency_code.upper()
    
    # Валидация: сумма должна быть положительной
    if amount <= 0:
        raise ValueError("Сумма должна быть положительной")
    
    # Валидация: нельзя продать USD (это базовая валюта)
    if currency_code == 'USD':
        raise ValueError("Нельзя продать USD (это базовая валюта)")
    
    # Валидация валюты через get_currency() - автоматически выбросит CurrencyNotFoundError
    currency_obj = get_currency(currency_code)
    
    # Получение целевого кошелька для продажи
    target_wallet = portfolio.get_wallet(currency_code)
    
    # Защита от None: кошелёк должен существовать для продажи
    if target_wallet is None:
        raise ValueError(f"У вас нет кошелька '{currency_code}'. "
                         f"Добавьте валюту: она создаётся автоматически при первой покупке.")
    
    # Получение USD кошелька (гарантировано get_portfolio)
    usd_wallet = portfolio.get_wallet('USD')
    
    # Защита от None для mypy (кошелёк USD всегда должен существовать)
    if usd_wallet is None:
        raise ValueError("Критическая ошибка: USD кошелёк отсутствует")
    
    # Проверка достаточности баланса целевой валюты
    if target_wallet.balance < amount:
        raise InsufficientFundsError(
            available=target_wallet.balance,  # Доступный баланс
            required=amount,                  # Требуемая сумма
            code=currency_code                # Код валюты
        )
    
    # Расчёт дохода в USD от продажи (используем статический курс)
    usd_income = amount * Portfolio.EXCHANGE_RATES[currency_code]
    
    # Списание валюты с целевого кошелька
    target_wallet.withdraw(amount)
    
    # Начисление USD на базовый кошелёк
    usd_wallet.deposit(usd_income)
    
    # Сохранение обновлённого портфеля
    save_portfolio(portfolio)


def get_rate(from_currency: str, to_currency: str) -> tuple[float, str, str, bool]:
    """
    Получение курса валюты с проверкой свежести данных.
    Args:
        from_currency: Исходная валюта (например, "USD")
        to_currency: Целевая валюта (например, "BTC")
    Returns:
        tuple: (курс, timestamp, источник, is_fresh)
        - float: Прямой курс обмена
        - str: Время обновления или "N/A"
        - str: Источник данных ("rates.json" или "Fallback")
        - bool: True если курс свежий, False если устарел
    """
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
    
    # Поиск данных в rates.json
    rate_data = rates.get(pair, {})
    timestamp = rate_data.get("updated_at", "N/A")
    
    # Проверка наличия и свежести курса в rates.json
    has_rate_in_json = pair in rates
    is_fresh = False
    direct_rate: float  # Явная аннотация типа для mypy
    
    if has_rate_in_json and timestamp != "N/A":
        # Проверка свежести курса через вспомогательную функцию
        is_fresh = is_rate_fresh(pair, timestamp)
    
    # Выбор курса: свежий из JSON или fallback
    if has_rate_in_json and is_fresh:
        # Явное приведение типа, получение курса из JSON
        rate_value = rate_data.get("rate")
        if rate_value is None:
            # Если в JSON нет rate, используем fallback
            direct_rate = (Portfolio.EXCHANGE_RATES[to_code] / 
                          Portfolio.EXCHANGE_RATES[from_code])
            source = "Fallback"
            timestamp = "N/A"
            is_fresh = False
        else:
            # Явное преобразование в float
            direct_rate = float(rate_value)
            source = "rates.json"
    else:
        # Fallback на статические курсы
        direct_rate = (Portfolio.EXCHANGE_RATES[to_code] / 
                      Portfolio.EXCHANGE_RATES[from_code])
        source = "Fallback"
        timestamp = "N/A"  # Для fallback нет timestamp
        is_fresh = False   # Fallback всегда считается устаревшим
    
    return (direct_rate, timestamp, source, is_fresh)

def generate_test_rates(test_scenario: str = "mixed") -> None:
    """
    Генератор тестовых данных для rates.json с разными временными метками.
    returns:
        None: Сохраняет данные в data/rates.json
    """
    from datetime import datetime, timedelta
    
    # Базовые валютные пары для тестирования
    currency_pairs = ["EUR_USD", "BTC_USD", "RUB_USD", "ETH_USD", "BTC_EUR"]
    
    # Инициализация словаря для rates.json
    test_rates = {}
    current_time = datetime.now()
    
    # Генерация timestamp для каждого сценария
    if test_scenario == "all_fresh":
        # Все курсы свежие (обновлены 1 минуту назад)
        timestamp = current_time - timedelta(minutes=1)
        for pair in currency_pairs:
            test_rates[pair] = {
                "rate": _generate_realistic_rate(pair),
                "updated_at": timestamp.isoformat()
            }
    
    elif test_scenario == "all_stale":
        # Все курсы устаревшие (обновлены 2 дня назад)
        timestamp = current_time - timedelta(days=2)
        for pair in currency_pairs:
            test_rates[pair] = {
                "rate": _generate_realistic_rate(pair),
                "updated_at": timestamp.isoformat()
            }
    
    elif test_scenario == "mixed":
        # Смешанные данные: 2 свежих, 3 устаревших
        fresh_time = current_time - timedelta(minutes=1)
        stale_time = current_time - timedelta(days=2)
        
        for i, pair in enumerate(currency_pairs):
            timestamp = fresh_time if i < 2 else stale_time
            test_rates[pair] = {
                "rate": _generate_realistic_rate(pair),
                "updated_at": timestamp.isoformat()
            }
    
    elif test_scenario == "invalid":
        # Некорректные форматы timestamp для тестирования обработки ошибок
        for pair in currency_pairs:
            test_rates[pair] = {
                "rate": _generate_realistic_rate(pair),
                "updated_at": "2025-13-45T99:99:99"  # Некорректный формат
            }
    
    elif test_scenario == "empty":
        # Пустой файл rates.json
        test_rates = {}
    
    else:
        raise ValueError(f"Неизвестный сценарий: {test_scenario}")
    
    # Добавление метаданных для идентификации тестовых данных
    if test_scenario != "empty":
        test_rates["source"] = "TestDataGenerator"
        test_rates["last_refresh"] = current_time.isoformat()
        test_rates["test_scenario"] = test_scenario
    
    # Сохранение данных в rates.json
    _save_rates_to_file(test_rates)


def _generate_realistic_rate(currency_pair: str) -> float:
    """
    Генерация реалистичного курса валюты на основе Portfolio.EXCHANGE_RATES.
    
    Args:
        currency_pair: Валютная пара в формате "EUR_USD"
        
    Returns:
        float: Реалистичный курс обмена
    """
    from .models import Portfolio  # Отложенный импорт
    
    try:
        # Парсинг валютной пары
        from_curr, to_curr = currency_pair.split("_")
        
        # Получение курсов из статических данных
        from_rate = Portfolio.EXCHANGE_RATES.get(from_curr, 1.0)
        to_rate = Portfolio.EXCHANGE_RATES.get(to_curr, 1.0)
        
        # Расчет курса: to_currency / from_currency
        if from_rate == 0:
            return 0.0  # Защита от деления на ноль
        return to_rate / from_rate
    
    except (ValueError, KeyError):
        # Fallback: случайный реалистичный курс
        import random
        return round(random.uniform(0.5, 2.5), 4)


def _save_rates_to_file(rates_data: dict) -> None:
    """
    Сохранение данных курсов в rates.json.
    
    Args:
        rates_data: Словарь с данными курсов
    """
    import json
    from pathlib import Path
    
    # Создание директории data если не существует
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)
    
    # Полный путь к файлу rates.json
    rates_file = data_dir / "rates.json"
    
    try:
        # Сохранение данных в JSON с форматированием
        with open(rates_file, 'w', encoding='utf-8') as f:
            json.dump(rates_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Тестовые данные сохранены в {rates_file}")
        print(f"   Сценарий: {rates_data.get('test_scenario', 'N/A')}")
        print(f"   Записей курсов: {len([k for k in rates_data.keys() 
                                      if not k.startswith('_')])}")
    
    except Exception as e:
        print(f"❌ Ошибка сохранения rates.json: {e}")
        raise

def is_rate_fresh(currency_pair: str, timestamp: str) -> bool:
    """
    Проверка актуальности курса валюты по времени обновления.
    
    Args:
        currency_pair: Валютная пара в формате "EUR_USD"
        timestamp: Время обновления в ISO формате "2025-10-09T10:30:00"
        
    Returns:
        bool: True если курс свежий, False если устарел
    """
    from datetime import datetime, timedelta
    
    # ВНУТРЕННИЕ ПРОВЕРКИ КОРРЕКТНОСТИ ЛОГИКИ
    # Эти assert'ы работают только в режиме разработки (python -O отключает)
    if "_" not in currency_pair:  # Проверка формата валютной пары
        # Assert для разработки + безопасный return для production
        assert False, f"Неверный формат валютной пары: {currency_pair}"
        return False  # Защита на случай отключенных assert
    
    try:
        # Парсинг timestamp из строки ISO формата
        update_time = datetime.fromisoformat(timestamp)
    except (ValueError, TypeError):
        # Некорректный timestamp
        assert False, f"Некорректный формат timestamp: {timestamp}"
        return False  # Защита на случай отключенных assert
    
    # Определение валюты из пары (первая часть до "_")
    base_currency = currency_pair.split("_")[0].upper()
    
    # Константы времени свежести для разных типов валют
    FIAT_CURRENCIES = {"USD", "EUR", "RUB"}  # Фиатные валюты
    CRYPTO_CURRENCIES = {"BTC", "ETH"}       # Криптовалюты
    
    FIAT_FRESHNESS = timedelta(hours=24)     # 24 часа для фиата
    CRYPTO_FRESHNESS = timedelta(minutes=5)  # 5 минут для крипто
    DEFAULT_FRESHNESS = timedelta(minutes=30)  # 30 минут по умолчанию
    
    # ВАЛИДАЦИЯ ПОЛИТИКИ СВЕЖЕСТИ (assert для разработки)
    assert "USD" in FIAT_CURRENCIES, "USD должен быть в фиатных валютах"
    assert "BTC" in CRYPTO_CURRENCIES, "BTC должен быть в криптовалютах"
    assert CRYPTO_FRESHNESS < FIAT_FRESHNESS, \
        "Крипто должен быть строже фиата (5 мин < 24 часа)"
    
    # Выбор лимита свежести в зависимости от типа валюты
    if base_currency in FIAT_CURRENCIES:
        freshness_limit = FIAT_FRESHNESS
    elif base_currency in CRYPTO_CURRENCIES:
        freshness_limit = CRYPTO_FRESHNESS
    else:
        freshness_limit = DEFAULT_FRESHNESS
    
    # Расчет времени, прошедшего с обновления
    time_since_update = datetime.now() - update_time
    
    # Проверка, не устарел ли курс
    return time_since_update <= freshness_limit
