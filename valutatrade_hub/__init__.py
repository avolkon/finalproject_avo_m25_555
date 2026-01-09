"""Основной пакет ValutaTrade Hub - платформа для валютного трейдинга."""

# Импорт и инициализация системы логирования при загрузке пакета
try:
    from .logging_config import setup_logging

    setup_logging()
except Exception as e:
    # Fallback: базовая настройка логирования если основная не сработала
    import logging

    logging.basicConfig(level=logging.INFO)
    logging.error(f"Не удалось инициализировать систему логирования: {e}")

# Экспорт версии пакета
__version__ = "3.0.0"
__author__ = "Анастасия Волконская"
__email__ = "aavolkon@mail.ru"

# Экспорт основных компонентов для удобного импорта
__all__ = [
    "__version__",
    "__author__",
    "__email__",
]
