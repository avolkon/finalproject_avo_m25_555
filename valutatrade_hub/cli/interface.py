"""
CLI интерфейс платформы.
"""

import argparse  # Для парсинга аргументов командной строки
import os
import sys  # Для работы с системными аргументами
from pathlib import Path
from prettytable import PrettyTable  # Для красивого вывода таблиц

from valutatrade_hub.core.usecases import (  # Импорт бизнес-логики
    register_user,  # Функция регистрации пользователя
    login_user,  # Функция входа пользователя
    CURRENT_USER_ID,  # Глобальная переменная текущего пользователя
    get_portfolio,  # Функция получения портфеля
    load_user,  # Функция загрузки пользователя по ID
    buy_currency,
    sell_currency,
    get_rate,
)
from valutatrade_hub.core.currencies import (
    get_supported_currencies,
)  # Импорт списка валют
from valutatrade_hub.core.models import Portfolio  # Импорт модели портфеля

# Импорт пользовательских исключений для обработки в CLI
from valutatrade_hub.core.exceptions import (
    InsufficientFundsError,
    CurrencyNotFoundError,
    ApiRequestError,  # Исключение для ошибок API
)

BASE_DIR = Path(__file__).parent.parent
CACHE_PATH = BASE_DIR / "data" / "rates.json"

def safe_execute_command(command_func, *args, **kwargs):
    """Безопасное выполнение CLI команд с обработкой ошибок."""
    try:
        return command_func(*args, **kwargs)
    except KeyboardInterrupt:
        print("\nОперация прервана пользователем")
        sys.exit(0)
    except (ValueError, CurrencyNotFoundError, InsufficientFundsError, ApiRequestError) as e:
        # Ошибки бизнес-логики
        print(f"Ошибка: {e}")
        sys.exit(1)
    except Exception as e:
        # Непредвиденные ошибки
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

def create_parser() -> argparse.ArgumentParser:
    """Создать парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description="Crypto Portfolio CLI"
    )  # Создание парсера
    subparsers = parser.add_subparsers(
        dest="command", required=True
    )  # Создание подпарсеров

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
    rate.add_argument("--to", required=True)  # Целевая валюта (BTC)
        # Команда update-rates с фильтром по источнику (ТЗ4 4.6.1)
    update = subparsers.add_parser("update-rates", 
                                   help="Обновить курсы валют")
    update.add_argument(
        "--source",
        choices=["coingecko", "exchangerate", "all"],
        default="all",
        help="Источник для обновления (по умолчанию все)"
    )

    # Команда show-rates с фильтрацией (ТЗ4 4.6.2)
    show_r = subparsers.add_parser("show-rates", 
                                   help="Показать курсы из кэша")
    show_r.add_argument(
        "--currency",
        type=str,
        help="Фильтр по валюте (например, BTC)"
    )
    show_r.add_argument(
        "--top",
        type=int,
        help="Показать N самых дорогих криптовалют"
    )
    show_r.add_argument(
        "--base",
        type=str,
        default="USD",
        help="Базовая валюта для расчета (по умолчанию USD)"
    )

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
        print(
            "Портфель пуст. Добавьте валюту через buy."
        )  # Сообщение о пустом портфеле
        return  # Выход из функции

    table = PrettyTable(
        ["Валюта", "Баланс", f"Стоимость ({base_code})"]
    )  # Создание таблицы
    total = 0.0  # Инициализация общей суммы портфеля

    base_rate = Portfolio.EXCHANGE_RATES.get(
        base_code, 1.0
    )  # Получение курса базовой валюты

    for code, wallet in portfolio.wallets.items():  # Итерация по всем кошелькам
        asset_rate = Portfolio.EXCHANGE_RATES.get(
            code, 1.0
        )  # Получение курса валюты актива
        value_in_base = wallet.balance * (
            asset_rate / base_rate
        )  # Расчёт стоимости в базе
        table.add_row(
            [code, f"{wallet.balance:.4f}", f"{value_in_base:.2f}"]
        )  # Добавление строки
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
        sys.exit(1)  # Happy path: пользователь авторизован, продолжаем

def buy_cli(currency: str, amount: float) -> None:
    """CLI обработка покупки валюты с детализированным выводом по ТЗ УЗ 222."""

    require_login()  # Проверка активной сессии пользователя

    if CURRENT_USER_ID is None:
        # Защита от None после require_login (двойная проверка)
        print("Сначала выполните login")
        return

    # 1. Загружаем портфель ДЛЯ ПОЛУЧЕНИЯ БАЛАНСА "БЫЛО"
    portfolio_before = get_portfolio(CURRENT_USER_ID)
    wallet_before = portfolio_before.get_wallet(currency)
    # Если кошелька нет до покупки, баланс = 0.0
    balance_before = wallet_before.balance if wallet_before else 0.0

    # 2. Получаем курс для расчета стоимости
    rate_tuple = get_rate("USD", currency)
    rate = rate_tuple[0]  # курс USD→currency (первый элемент кортежа)

    # 3. Выполняем покупку (основная бизнес-логика)
    buy_currency(CURRENT_USER_ID, currency, amount)

    # 4. Расчет стоимости покупки в USD
    cost_usd = amount * rate

    # 5. Вывод деталей операции по ТЗ (точный формат из примера)
    print(
        f"Покупка выполнена: {amount:.4f} {currency} по курсу "
        f"{rate:.2f} USD/{currency}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {currency}: было {balance_before:.4f} → стало "
        f"{balance_before + amount:.4f}"
    )
    print(f"Оценочная стоимость покупки: {cost_usd:,.2f} USD")

    # 6. Вывод обновленного портфеля (существующий функционал)
    show_portfolio("USD")


def sell_cli(currency: str, amount: float) -> None:
    """CLI обработка продажи валюты с детализированным выводом по ТЗ УЗ 222."""

    require_login()  # Проверка активной сессии пользователя

    if CURRENT_USER_ID is None:
        # Защита от None после require_login (двойная проверка)
        print("Сначала выполните login")
        return

    # ВЕСЬ КОД БЕЗ try-except блока (строки 279-316 из оригинального try блока):
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
    rate = rate_tuple[0]  # курс currency→USD (первый элемент кортежа)

    # 5. Выполняем продажу (основная бизнес-логика)
    sell_currency(CURRENT_USER_ID, currency, amount)

    # 6. Расчет выручки в USD
    revenue_usd = amount * rate

    # 7. Вывод деталей операции по ТЗ
    print(
        f"Продажа выполнена: {amount:.4f} {currency} по курсу "
        f"{rate:.2f} USD/{currency}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {currency}: было {balance_before:.4f} → стало "
        f"{balance_before - amount:.4f}"
    )
    print(f"Оценочная выручка: {revenue_usd:,.2f} USD")

    # 8. Вывод обновленного портфеля (существующий функционал)
    show_portfolio("USD")

def get_rate_cli(from_currency: str, to_currency: str) -> None:
    """CLI команда получения курса валют с индикатором свежести и источником данных."""

    try:
        # Получение курса через бизнес-логику (без проверки сессии)
        # Возвращает кортеж: (курс, timestamp, источник, is_fresh)
        direct_rate, timestamp, source, is_fresh = get_rate(from_currency, to_currency)

        # Преобразование timestamp из ISO формата в человекочитаемый
        human_timestamp = timestamp  # Инициализация значением по умолчанию
        if timestamp != "N/A":
            # Заменяем T на пробел, если он есть в строке (ISO → читаемый)
            human_timestamp = (
                timestamp.replace("T", " ") if "T" in timestamp else timestamp
            )

        # Определение статуса свежести на основе источника и is_fresh
        if "Fallback" in source:
            # Для резервных (статических) курсов особый статус
            freshness_status = "статический (резервный)"
        elif is_fresh:
            # Данные свежие (обновлены в пределах TTL)
            freshness_status = "свежий"
        else:
            # Данные устарели (превышен TTL)
            freshness_status = "устаревший"

        # Прямой курс с 8 знаками после запятой по формату ТЗ
        print(f"Курс {from_currency}→{to_currency}: {direct_rate:.8f}")
        # Отдельные строки для каждой информации для лучшей читаемости
        print(f"Обновлено: {human_timestamp}")
        print(f"Источник: {source}")
        print(f"Статус: {freshness_status}")

        # Обратный курс с 2 знаками после запятой по формату ТЗ
        # Защита от деления на ноль (direct_rate никогда не должен быть 0)
        inverse_rate = 1 / direct_rate if direct_rate != 0 else 0.0
        print(f"Обратный курс {to_currency}→{from_currency}: {inverse_rate:.2f}")

    except CurrencyNotFoundError as e:
        # Обработка неизвестной валюты с выводом списка поддерживаемых
        supported = get_supported_currencies()
        print(f"Ошибка: {e}")
        print(f"Поддерживаемые валюты: {', '.join(supported)}")
        sys.exit(1)

    except ApiRequestError as e:
        # Обработка ошибки API с понятным сообщением для пользователя
        print(f"Ошибка: {e}")
        print("Пожалуйста, повторите попытку позже или проверьте подключение к сети.")
        sys.exit(1)

    except Exception as e:
        # Обработка всех остальных исключений
        print(f"Критическая ошибка: {e}")
        sys.exit(1)


def cli_update_rates(source: str = "all") -> None:
    """CLI-команда обновления курсов с фильтром по источнику."""
    try:
        # Ленивая загрузка модулей Parser Service
        from valutatrade_hub.parser_service import RatesUpdater
    except ImportError as e:
        print(f"Parser Service недоступен: {e}")
        print("Убедитесь, что модуль parser_service установлен.")
        sys.exit(1)

    try:
        # Создание RatesUpdater с автоматической инициализацией клиентов
        updater = RatesUpdater(clients=[], cache_filepath="data/rates.json")
        
        result = None
        if source in ["coingecko", "exchangerate"]:
            # Выборочное обновление для одного источника
            print(f"Обновление курсов из источника: {source}")
            result = updater.run_update_for_source(
                source_name="CoinGecko" if source == "coingecko" 
                else "ExchangeRate"
            )
        else:
            # Обновление из всех источников (по умолчанию)
            print("Обновление курсов из всех источников")
            result = updater.run_update()

        # Форматирование статуса для пользователя
        status_map = {
            "SUCCESS": "УСПЕХ",
            "PARTIAL": "ЧАСТИЧНО",
            "FAILED": "ОШИБКА",
        }
        status_display = status_map.get(str(result.status), "НЕИЗВЕСТНО")

        print(f"{status_display}: обновлено {result.total_rates} курсов")

        if result.updated_sources:
            print("Источники (успешные): " + 
                  ", ".join(sorted(result.updated_sources)))
        if result.failed_sources:
            print("Источники (с ошибками): " + 
                  ", ".join(sorted(result.failed_sources)))
        
        # Логирование ошибок если есть
        if result.error_messages:
            print("Ошибки:")
            for msg in result.error_messages:
                print(f"- {msg}")

    except ValueError as e:
        # Ошибка валидации источника
        print(f"Ошибка: {e}")
        print("Доступные источники: coingecko, exchangerate, all")
        sys.exit(1)
    except Exception as e:
        # Общая ошибка обновления
        print(f"Ошибка обновления курсов: {e}")
        sys.exit(1)


def cli_show_rates(
    currency: str | None = None,
    top: int | None = None,
    base: str = "USD",
) -> None:
    """CLI-команда показа курсов с фильтрацией и форматированием."""
    try:
        from valutatrade_hub.parser_service import RatesCache
    except ImportError as e:
        print(f"Parser Service недоступен: {e}")
        print("Убедитесь, что модуль parser_service установлен.")
        sys.exit(1)

    try:
        # Инициализация кэша курсов
        cache = RatesCache(filepath="data/rates.json")
        all_rates = cache.get_all_rates()

        # Проверка на пустой кэш
        if not all_rates:
            print("Локальный кэш курсов пуст.")
            print("Выполните: python main.py update-rates")
            return

        # Преобразование в список для фильтрации
        rows: list[tuple[str, dict]] = list(all_rates.items())

        # Фильтрация по валюте (нечеткий поиск)
        if currency:
            cur_upper = currency.upper()
            rows = [(pair, data) for pair, data in rows 
                    if cur_upper in pair.upper()]

        # Если нет результатов после фильтрации
        if not rows and currency:
            print(f"Курс для '{currency}' не найден в кеше.")
            return

        # Сортировка по курсу (по убыванию) для флага --top
        rows.sort(key=lambda x: x[1].get("rate", 0.0), reverse=True)
        
        # Ограничение количества результатов для --top
        if top is not None and top > 0:
            rows = rows[:top]

        # Создание форматированной таблицы с PrettyTable
        table = PrettyTable()
        table.field_names = ["Пара", "Курс", "Обновлено", "Источник", "Свежий"]
        
        # Выравнивание колонок для читаемости
        table.align["Пара"] = "l"
        table.align["Курс"] = "r"
        table.align["Обновлено"] = "c"
        table.align["Источник"] = "l"
        table.align["Свежий"] = "c"

        for pair, data in rows:
            rate_raw = data.get("rate")
            updated_at = data.get("updated_at", "N/A")
            source = data.get("source", "N/A")
            
            # Определение свежести данных через RatesCache
            is_fresh = cache.is_fresh(pair, updated_at)

            # Форматирование курса в зависимости от типа валюты
            rate_str: str
            if rate_raw is None:
                rate_str = "N/A"
            else:
                try:
                    rate_value = float(rate_raw)
                    # Разное количество знаков для крипто и фиата
                    if pair.startswith(("BTC_", "ETH_", "SOL_")):
                        rate_str = f"{rate_value:,.6f}"
                    else:
                        rate_str = f"{rate_value:,.4f}"
                except (TypeError, ValueError):
                    rate_str = "N/A"

            # Форматирование времени (только HH:MM:SS из ISO)
            updated_short = updated_at
            if "T" in updated_short:
                try:
                    # Извлечение только времени из ISO формата
                    time_part = updated_short.split("T")[1]
                    updated_short = time_part[:8]  # HH:MM:SS
                except (IndexError, TypeError):
                    updated_short = "N/A"

            # Маркер свежести
            fresh_mark = "да" if is_fresh else "нет"

            # Добавление строки в таблицу
            table.add_row([pair, rate_str, updated_short, source, fresh_mark])

        # Вывод заголовка и таблицы
        print(f"Курсы (база расчёта: {base.upper()}):")
        print(table)

        # Информация о количестве результатов
        if currency and len(rows) > 0:
            print(f"Найдено {len(rows)} курсов по фильтру '{currency}'.")
        elif top and len(rows) > 0:
            print(f"Показано {len(rows)} самых дорогих криптовалют.")

    except Exception as e:
        print(f"Ошибка чтения кэша курсов: {e}")
        sys.exit(1)

def main(argv: list[str] | None = None) -> None:
    """Главная точка входа CLI."""
    if argv is None:
        argv = sys.argv

    if len(argv) == 1:
        print("Доступные команды: register, login, show-portfolio, buy, sell, get-rate, update-rates, show-rates")
        return

    parser = create_parser()
    args = parser.parse_args(argv[1:])

    # Обработка команд с безопасным выполнением
    try:
        if args.command == "register":
            uid = register_user(args.username, args.password)
            print(f"Пользователь '{args.username}' зарегистрирован (id={uid}). "
                  f"Войдите: login --username {args.username} --password ****")

        elif args.command == "login":
            # login_user сам обрабатывает ошибки и выводит сообщения
            login_user(args.username, args.password)

        elif args.command == "show-portfolio":
            safe_execute_command(show_portfolio, args.base)

        elif args.command == "buy":
            safe_execute_command(buy_cli, args.currency, args.amount)

        elif args.command == "sell":
            safe_execute_command(sell_cli, args.currency, args.amount)

        elif args.command == "get-rate":
            safe_execute_command(get_rate_cli, args.__getattribute__("from"), args.to)

        elif args.command == "update-rates":
            safe_execute_command(cli_update_rates, args.source)

        elif args.command == "show-rates":
            safe_execute_command(cli_show_rates, args.currency, args.top, args.base)

    except KeyboardInterrupt:
        print("\nОперация прервана пользователем")
        sys.exit(0)
    except SystemExit:
        # Пропускаем системные выходы (уже обработаны в safe_execute_command)
        raise
    except Exception as e:
        # Обработка непредвиденных ошибок при выборе команды
        print(f"Критическая ошибка при обработке команды: {e}")
        sys.exit(1)

if __name__ == "__main__":  # Проверка запуска как основного модуля
    main()  # Запуск основной функции
