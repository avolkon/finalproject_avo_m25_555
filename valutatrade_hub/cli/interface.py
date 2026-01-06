"""CLI: register, login."""

# Стандартные библиотеки для CLI
import argparse  # Парсер аргументов командной строки (--username, --password)
import sys  # sys.argv (аргументы), sys.exit() (завершение с кодом)

# Бизнес-логика регистрации/авторизации
from valutatrade_hub.core.usecases import (
    login_user,  # Авторизация: username, password → сессия
    register_user,  # Регистрация: username, password → user_id
)


def create_parser() -> argparse.ArgumentParser:
    """Парсер аргументов командной строки."""
    # Создаёт главный парсер с описанием CLI
    parser = argparse.ArgumentParser(description="Crypto CLI")
    # Добавляет подпарсеры для команд (register, login)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Подпарсер команды register
    reg = subparsers.add_parser("register")
    reg.add_argument("--username", required=True)  # Обязательный username
    reg.add_argument("--password", required=True)  # Обязательный password

    # Подпарсер команды login
    log = subparsers.add_parser("login")
    log.add_argument("--username", required=True)  # Обязательный username
    log.add_argument("--password", required=True)  # Обязательный password

    # Возвращает настроенный парсер
    return parser


def main(argv: list[str] | None = None) -> None:
    """Главная точка входа CLI."""
    # sys.argv если аргументы не переданы
    if argv is None:
        argv = sys.argv

    # Создаёт парсер и парсит аргументы (кроме argv[0] — имя скрипта)
    parser = create_parser()
    args = parser.parse_args(argv[1:])

    try:
        # Диспетчеризация по команде
        if args.command == "register":
            # Вызывает бизнес-логику регистрации
            uid = register_user(args.username, args.password)
            # Сообщение ТЗ: "Пользователь 'alice' зарегистрирован (id=1)"
            print(f"Пользователь '{args.username}' зарегистрирован (id={uid})")
        elif args.command == "login":
            # Вызывает бизнес-логику авторизации (print внутри login_user)
            login_user(args.username, args.password)
    except ValueError as e:
        # Обработка ошибок валидации (из usecases.py)
        print(f"Ошибка: {e}")
        sys.exit(1)  # Завершение с ошибкой (код 1)


if __name__ == "__main__":
    # Запуск CLI при прямом вызове модуля
    main()
