"""Пакет инфраструктурных компонентов ValutaTrade Hub."""

# Импорт SettingsLoader для доступа из других модулей
from .settings import SettingsLoader, ConfigError

# Экспорт публичных классов и функций
__all__ = [
    'SettingsLoader',
    'ConfigError',
]

