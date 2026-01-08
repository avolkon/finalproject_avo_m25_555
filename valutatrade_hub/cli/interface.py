"""
CLI интерфейс платформы.
"""

import argparse                           # Для парсинга аргументов командной строки
import sys                                # Для работы с системными аргументами
from prettytable import PrettyTable       # Для красивого вывода таблиц

from valutatrade_hub.core.usecases import (  # Импорт бизнес-логики
    register_user,                         # Функция регистрации пользователя
    login_user,                            # Функция входа пользователя
    CURRENT_USER_ID,                       # Глобальная переменная текущего пользователя
    get_portfolio,                         # Функция получения портфеля
    load_user,                             # Функция загрузки пользователя по ID
    buy_currency,
    sell_currency,
    get_rate
)
from valutatrade_hub.core.models import Portfolio  # Импорт модели портфеля


def create_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(description="Crypto Portfolio CLI")  # Создание парсера
    subparsers = parser.add_subparsers(dest="command", required=True)  # Создание подпарсеров

    # register
    reg = subparsers.add_parser("register")  # Подпарсер для регистрации
    reg.add_argument("--username", required=True)  # Обязательный аргумент имени
    reg.add_argument("--password", required=True)  # Обязательный аргумент пароля

    # login
    log = subparsers.add_parser("login")  # Подпарсер для входа
    log.add_argument("--username", required=True)  # Обязательный аргумент имени
    log.add_argument("--password", required=True)  # Обязательный аргумент пароля

    # show-portfolio
    show = subparsers.add_parser("show-portfolio")  # Подпарсер для показа портфеля
    show.add_argument("--base", default="USD")  # Опциональный аргумент базовой валюты

    # Сабпарсер для покупки валюты
    buy = subparsers.add_parser("buy")
    buy.add_argument("--currency", required=True)  # Код валюты (BTC, EUR)
    buy.add_argument("--amount", type=float, required=True)  # Сумма покупки
        
    # Сабпарсер для продажи валюты
    sell = subparsers.add_parser("sell")
    sell.add_argument("--currency", required=True)  # Код продаваемой валюты
    sell.add_argument("--amount", type=float, required=True)  # Сумма продажи

    # Подпарсер получения курса валют (не требует авторизации)
    rate = subparsers.add_parser("get-rate")
    rate.add_argument("--from", required=True)  # Исходная валюта (USD)
    rate.add_argument("--to", required=True)    # Целевая валюта (BTC)



    return parser  # Возврат готового парсера


def show_portfolio(base: str) -> None:
    """Показать портфель текущего пользователя."""
    if CURRENT_USER_ID is None:  # Проверка наличия активной сессии
        print("Сначала выполните login")  # Сообщение об отсутствии входа
        return  # Выход из функции
    
    user = load_user(CURRENT_USER_ID)  # Загрузка пользователя по ID
    if user is None:  # Проверка успешности загрузки
        print("Критическая ошибка: пользователь не найден")  # Сообщение об ошибке
        return  # Выход из функции
    
    portfolio = get_portfolio(CURRENT_USER_ID)  # Получение портфеля пользователя
    base_code = base.upper()  # Приведение базовой валюты к верхнему регистру
    
    if not portfolio.wallets:  # Проверка наличия кошельков в портфеле
        print("Портфель пуст. Добавьте валюту через buy.")  # Сообщение о пустом портфеле
        return  # Выход из функции
    
    table = PrettyTable(["Валюта", "Баланс", f"Стоимость ({base_code})"])  # Создание таблицы
    total = 0.0  # Инициализация общей суммы портфеля
    
    base_rate = Portfolio.EXCHANGE_RATES.get(base_code, 1.0)  # Получение курса базовой валюты
    
    for code, wallet in portfolio.wallets.items():  # Итерация по всем кошелькам
        asset_rate = Portfolio.EXCHANGE_RATES.get(code, 1.0)  # Получение курса валюты актива
        value_in_base = wallet.balance * (asset_rate / base_rate)  # Расчёт стоимости в базе
        table.add_row([code, f"{wallet.balance:.4f}", f"{value_in_base:.2f}"])  # Добавление строки
        total += value_in_base  # Добавление к общей сумме
    
    print(f"Портфель '{user.username}' (база: {base_code}):")  # Заголовок таблицы
    print(table)  # Вывод таблицы
    print("-" * 30)  # Разделительная линия
    print(f"ИТОГО: {total:.2f} {base_code}")  # Вывод общей суммы

def require_login() -> None:
    """Проверка активной сессии, sys.exit(1) если нет login."""
    # Проверка наличия залогиненного пользователя
    if CURRENT_USER_ID is None:
        # Сообщение об отсутствии сессии
        print("Сначала выполните login")
        # Завершение CLI с кодом ошибки 1
        sys.exit(1)   # Happy path: пользователь авторизован, продолжаем

def buy_cli(currency: str, amount: float) -> None:
    """CLI обработка покупки валюты с детализированным выводом по ТЗ УЗ 222."""
    
    require_login()  # Проверка сессии
    
    if CURRENT_USER_ID is None:
        print("Сначала выполните login")
        return
    
    try:
        # 1. Загружаем портфель ДЛЯ ПОЛУЧЕНИЯ БАЛАНСА "БЫЛО"
        portfolio_before = get_portfolio(CURRENT_USER_ID)
        wallet_before = portfolio_before.get_wallet(currency)
        balance_before = wallet_before.balance if wallet_before else 0.0
        
        # 2. Получаем курс для расчета стоимости
        rate_tuple = get_rate("USD", currency)
        rate = rate_tuple[0]  # курс USD→currency
        
        # 3. Выполняем покупку (основная бизнес-логика)
        buy_currency(CURRENT_USER_ID, currency, amount)
        
        # 4. Расчет стоимости покупки в USD
        cost_usd = amount * rate
        
        # 5. Вывод деталей операции по ТЗ (точный формат из примера)
        print(f"Покупка выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}")
        print("Изменения в портфеле:")
        print(f"- {currency}: было {balance_before:.4f} → стало {balance_before + amount:.4f}")
        print(f"Оценочная стоимость покупки: {cost_usd:,.2f} USD")
        
        # 6. Вывод обновленного портфеля (существующий функционал)
        show_portfolio('USD')
        
    except ValueError as e:
        print(f"Ошибка ввода: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

def sell_cli(currency: str, amount: float) -> None:
    """CLI обработка продажи валюты с детализированным выводом по ТЗ УЗ 222."""
    
    require_login()  # Проверка сессии
    
    if CURRENT_USER_ID is None:
        print("Сначала выполните login")
        return
    
    try:
        # 1. Загружаем портфель ДЛЯ ПРОВЕРКИ КОШЕЛЬКА И БАЛАНСА
        portfolio_before = get_portfolio(CURRENT_USER_ID)
        wallet_before = portfolio_before.get_wallet(currency)
        
        # 2. Проверка кошелька (новая валидация по ТЗ)
        if wallet_before is None:
            raise ValueError(
                f"У вас нет кошелька '{currency}'. "
                f"Добавьте валюту: она создаётся автоматически при первой покупке."
            )
        
        balance_before = wallet_before.balance
        
        # 3. Проверка достаточности средств (новая валидация по ТЗ)
        if balance_before < amount:
            raise ValueError(
                f"Недостаточно средств: доступно {balance_before:.4f} {currency}, "
                f"требуется {amount:.4f} {currency}"
            )
        
        # 4. Получаем курс для расчета выручки
        rate_tuple = get_rate(currency, "USD")
        rate = rate_tuple[0]  # курс currency→USD
        
        # 5. Выполняем продажу (основная бизнес-логика)
        sell_currency(CURRENT_USER_ID, currency, amount)
        
        # 6. Расчет выручки в USD
        revenue_usd = amount * rate
        
        # 7. Вывод деталей операции по ТЗ
        print(f"Продажа выполнена: {amount:.4f} {currency} по курсу {rate:.2f} USD/{currency}")
        print("Изменения в портфеле:")
        print(f"- {currency}: было {balance_before:.4f} → стало {balance_before - amount:.4f}")
        print(f"Оценочная выручка: {revenue_usd:,.2f} USD")
        
        # 8. Вывод обновленного портфеля (существующий функционал)
        show_portfolio('USD')
        
    except ValueError as e:
        print(f"Ошибка ввода: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

    # Выполнение продажи через бизнес-логику
    sell_currency(CURRENT_USER_ID, currency, amount)
    
    # Вывод обновлённого портфеля в USD
    show_portfolio('USD')

def get_rate_cli(from_currency: str, to_currency: str) -> None:
    """CLI команда получения курса валют с индикатором свежести."""
    # Получение курса через бизнес-логику (без проверки сессии)
    direct_rate, timestamp, source, is_fresh = get_rate(from_currency, 
                                                        to_currency)
    
    # Преобразование timestamp из ISO формата в человекочитаемый
    # ISO: "2025-10-09T00:03:22" → "2025-10-09 00:03:22"
    human_timestamp = timestamp
    if timestamp != "N/A":
        try:
            # Заменяем T на пробел
            human_timestamp = timestamp.replace("T", " ")
        except:
            human_timestamp = timestamp
    
    # Прямой курс с 8 знаками после запятой по формату ТЗ
    print(f"Курс {from_currency}→{to_currency}: {direct_rate:.8f} (обновлено: {human_timestamp})")
    
    # Обратный курс с 2 знаками после запятой по формату ТЗ
    print(f"Обратный курс {to_currency}→{from_currency}: {1/direct_rate:.2f}")    

def main(argv: list[str] | None = None) -> None:
    """Главная точка входа CLI."""
    if argv is None:  # Проверка переданных аргументов
        argv = sys.argv  # Использование системных аргументов по умолчанию
    
    if len(argv) == 1:  # Проверка количества аргументов
        print("Доступные команды: register, login, show-portfolio")  # Справка по командам
        return  # Выход из программы
    
    parser = create_parser()  # Создание парсера аргументов
    args = parser.parse_args(argv[1:])  # Парсинг аргументов командной строки
    
    try:  # Блок обработки исключений
        if args.command == "register":  # Обработка команды регистрации
            uid = register_user(args.username, args.password)  # Регистрация возвращает userid
            # Вывод сообщения об успешной регистрации
            print(f"Пользователь '{args.username}' зарегистрирован (id={uid}). "
                f"Войдите: login --username {args.username} --password ****")

        
        elif args.command == "login":  # Обработка команды входа
            login_user(args.username, args.password)  # Вызов функции входа
            # login_user сам печатает сообщение об успешном входе
            # и выбрасывает ValueError при ошибке
        
        elif args.command == "show-portfolio":  # Обработка команды показа портфеля
            show_portfolio(args.base)  # Вызов функции показа портфеля

        elif args.command == "buy": # Обработка команды покупки валюты
            buy_cli(args.currency, args.amount)
          
        elif args.command == "sell":  # Обработка команды продажи валюты
            sell_cli(args.currency, args.amount)
    
    except ValueError as e:  # Обработка ошибок валидации
        print(f"Ошибка ввода: {e}")  # Вывод сообщения об ошибке
        sys.exit(1)  # Завершение программы с кодом ошибки
    except Exception as e:  # Обработка всех остальных исключений
        print(f"Критическая ошибка: {e}")  # Вывод сообщения о критической ошибке
        sys.exit(1)  # Завершение программы с кодом ошибки


if __name__ == "__main__":  # Проверка запуска как основного модуля
    main()  # Запуск основной функции

