"""Публичный API CLI модуля ValutaTrade Hub (ТЗ4)."""

# Существующие функции CLI
from .interface import (
    create_parser,  # Основной парсер аргументов
    main,  # Точка входа CLI
)

# Новые команды Parser Service (5.2 ТЗ4 4.6)
from .interface import (
    cli_update_rates,  # update-rates команда ТЗ4
    cli_show_rates,  # show-rates с фильтрами ТЗ4
)

__all__ = [
    "create_parser",
    "main",
    "cli_update_rates",  # Экспорт для ТЗ4 4.6.1
    "cli_show_rates",  # Экспорт для ТЗ4 4.6.2
]
