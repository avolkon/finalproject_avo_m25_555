"""CLI entrypoint for finalproject_avo_m25_555."""

import sys
import shlex
import time
from typing import NoReturn

from prettytable import PrettyTable


def main() -> NoReturn:
    """Запуск CLI."""
    print("Finalproject_avo_m25_555 CLI v0.1.0")
    try:
        if len(sys.argv) > 1:
            args = shlex.split(' '.join(sys.argv[1:]))
            _handle_command(args)
        else:
            _print_help()
    except ValueError as e:
        print(f"Ошибка ввода: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)


def _handle_command(args: list[str]) -> None:
    """Обработка команды CLI."""
    # Место для декораторов: @log_action, @confirm_transaction
    pass


def _print_help() -> None:
    """Вывод справки."""
    table = PrettyTable(["Команда", "Описание"])
    table.add_row(["help", "Эта справка"])
    table.add_row(["register <name>", "Регистрация пользователя"])
    print(table)


if __name__ == "__main__":
    main()
