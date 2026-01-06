#!/usr/bin/env python
"""Entry point CLI."""
from pathlib import Path

# Абсолютный импорт из пакета
from valutatrade_hub.cli.interface import main as cli_main


def main() -> None:
    """Запуск CLI."""
    cli_main()


if __name__ == "__main__":
    main()

