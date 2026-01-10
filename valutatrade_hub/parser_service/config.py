"""Конфигурация Parser Service для ТЗ4."""

from dataclasses import dataclass  # dataclass для конфига
import os  # os.getenv для API-ключа


@dataclass(frozen=True)  # Неизменяемый конфиг
class ParserConfig:
    """Конфигурация парсера курсов валют."""

    # API ключ из ENV (по умолчанию из ТЗ4)
    EXCHANGERATE_API_KEY: str = os.getenv("d27515639de97f22e18f53d9", "")
    if not EXCHANGERATE_API_KEY:
        raise ValueError("""
                Ошибка: переменная окружения EXCHANGERATE_API_KEY не установлена.
                Добавьте её в .env файл или установите командой:
                set EXCHANGERATE_API_KEY=ваш_ключ_сюда""")

    # Базовые URL эндпоинтов API
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"

    # Настройки валют
    BASE_CURRENCY: str = "USD"  # Базовая валюта USD
    FIAT_CURRENCIES: tuple = (  # Фиатные валюты для парсинга
        "EUR",
        "GBP",
        "RUB",
    )
    CRYPTO_CURRENCIES: tuple = (  # Криптовалюты для CoinGecko
        "BTC",
        "ETH",
        "SOL",
    )

    # Маппинг тикеров -> CoinGecko ID
    CRYPTO_ID_MAP: dict = {
        "BTC": "bitcoin",  # BTC -> bitcoin
        "ETH": "ethereum",  # ETH -> ethereum
        "SOL": "solana",  # SOL -> solana
    }

    # Пути к файлам данных
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Настройки планировщика (из pyproject.toml)
    FIAT_UPDATE_INTERVAL_MINUTES: int = 60
    CRYPTO_UPDATE_INTERVAL_MINUTES: int = 5
    ENABLE_AUTO_START: bool = True
    LOG_SCHEDULER_EVENTS: bool = True
    UPDATE_TIMEOUT_SECONDS: int = 300
    ALLOW_CONCURRENT_UPDATES: bool = False


# Глобальный экземпляр конфигурации
config: ParserConfig = ParserConfig()


def __post_init__(self) -> None:
    if not self.EXCHANGERATE_API_KEY:
        raise ValueError(
            "❌ Не удалось загрузить API-ключ ExchangeRate.\n\n"
            "Для работы с курсами валют необходимо:\n"
            "1. Получите бесплатный ключ на https://www.exchangerate-api.com/\n"
            "2. Установите его одним из способов:\n"
            "   • Создайте файл '.env' в корне проекта и добавьте:\n"
            "     EXCHANGERATE_API_KEY=ваш_ключ\n"
            "   • Или установите через командную строку:\n"
            "     Windows: set EXCHANGERATE_API_KEY=ваш_ключ\n"
            "     Linux/Mac: export EXCHANGERATE_API_KEY=ваш_ключ\n\n"
            "После установки перезапустите программу."
        )
