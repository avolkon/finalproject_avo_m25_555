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
    sell_currency
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
            uid = register_user(args.username, args.password)  # Вызов регистрации
            print(f"Пользователь '{args.username}' зарегистрирован (id={uid})")  # Успешное сообщение
        
        elif args.command == "login":  # Обработка команды входа
            login_user(args.username, args.password)  # Вызов функции входа
            # login_user сам печатает сообщение об успешном входе
            # и выбрасывает ValueError при ошибке
        
        elif args.command == "show-portfolio":  # Обработка команды показа портфеля
            show_portfolio(args.base)  # Вызов функции показа портфеля
    
    except ValueError as e:  # Обработка ошибок валидации
        print(f"Ошибка ввода: {e}")  # Вывод сообщения об ошибке
        sys.exit(1)  # Завершение программы с кодом ошибки
    except Exception as e:  # Обработка всех остальных исключений
        print(f"Критическая ошибка: {e}")  # Вывод сообщения о критической ошибке
        sys.exit(1)  # Завершение программы с кодом ошибки


if __name__ == "__main__":  # Проверка запуска как основного модуля
    main()  # Запуск основной функции