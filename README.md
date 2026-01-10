# finalproject_avo_m25_555
Общая идея проекта
ValutaTrade Hub — Платформа валютного трейдинга

Это комплексная платформа, 
которая позволяет пользователям регистрироваться,
управлять своим виртуальным портфелем фиатных и криптовалют,
совершать сделки по покупке/продаже,
а также отслеживать актуальные курсы в реальном времени.
Система состоит из двух основных сервисов: 
Сервис Парсинга (Parser Service):
Отдельное приложение, которое по запросу или расписанию
обращается к публичным API, получает актуальные курсы,
сравнивает их с предыдущими значениями
и сохраняет историю в базу данных.
Основной Сервис (Core Service):
Главное приложение, которое предоставляет
пользовательский интерфейс (CLI),
управляет пользователями, их кошельками,
историей транзакций и взаимодействует
с сервисом парсинга для получения актуальных курсов.

ValutaTrade Hub — финтех платформа для управления крипто портфелем: покупка/продажа BTC/ETH/SOL/EUR/RUB, актуальные курсы с CoinGecko/ExchangeRate-API, CLI интерфейс, JSON хранение, планировщик обновлений.

Функции
- Курсы 24/7: CoinGecko (крипто каждые 5мин), ExchangeRate-API (фиат 1ч) → data/rates.json
- История: data/exchange_rates.json с уникальными ID (BTCUSD_20260110T150000Z)
- Портфель: data/portfolios.json, data/users.json — atomic JSON
- CLI: poetry run project {register|buy|sell|update-rates|show-history}
- TTL: Фиат 24ч, крипто 5мин (SettingsLoader)
- Логи: logs/parser.log с декоратором @log_action

Структура проекта
finalproject-avo-m25-555/
├── data/                    # JSON хранение
│   ├── users.json
│   ├── portfolios.json
│   ├── rates.json           # Текущие курсы
│   └── exchange_rates.json  # История
├── valutatrade_hub/
│   ├── core/                # Бизнес логика
│   │   ├── currencies.py    # FiatCurrency/CryptoCurrency
│   │   ├── models.py        # Portfolio/User/Wallet
│   │   └── usecases.py      # buy_currency/sell_currency
│   ├── parser_service/      # TZ4: Курсы API
│   │   ├── config.py
│   │   ├── apiclients.py    # CoinGecko/ExchangeRate
│   │   ├── ratescache.py
│   │   ├── updater.py
│   │   └── storage.py       # HistoryStorage
│   ├── cli/                 # CLI интерфейс
│   └── infra/               # Settings/Database
├── Makefile                 # CI/CD
├── pyproject.toml           # Poetry + ruff + [tool.valutatrade]
└── README.md

Быстрый старт

# 1. Клонировать/установить
git clone <repo>
cd finalproject-avo-m25-555
poetry install

# 2. Настроить API ключ (.env)
echo "EXCHANGERATE_API_KEY=your_key" > .env

ExchangeRate-API  
Перейдите на сайт https://www.exchangerate-api.com/.
Зарегистрируйтесь — это бесплатно.
После регистрации вы получите персональный API-ключ, который выглядит примерно так:
3b47a9b92e1b14c1f1234567

# 3. Запуск
make install    # Зависимости
make run        # CLI help
make lint test  # Проверки

CLI Команды

# Регистрация/логин
project register --username alice --password 1234
project login --username alice --password 1234

# Трейдинг
project buy --currency BTC --amount 0.01      # Купить BTC
project sell --currency BTC --amount 0.001    # Продать
project show-portfolio --base USD             # Портфель

# Курсы (TZ4)
project update-rates                          # Обновить все
project update-rates --source coingecko       # Только крипто
project show-rates --top 3                    # Топ 3 крипто
project show-rates --currency RUB             # RUB курс
project show-history --currency BTC --limit 5 # История BTC

# Dev
make format lint test clean

Разработка

# Форматирование/линтинг
make format fix lint

# Тесты
make test

# Сборка
make build package-install

# Публикация (dry-run)
make publish

Технические детали

Архитектура (Clean Architecture)
CLI → Usecases → Models → Infra (JSON atomic)
     ↓
ParserService (CoinGecko/ExchangeRate) → rates.json/history

Настройки [tool.valutatrade]
[tool.valutatrade]
rates_ttl_fiat_seconds = 86400     # 24ч
rates_ttl_crypto_seconds = 300     # 5мин
supported_currencies = ["USD","EUR","RUB","BTC","ETH"]
data_dir = "data"

Данные
- rates.json: {pairs: {BTC_USD: {rate, updated_at, source}}} TTL
- exchange_rates.json: История BTCUSD_20260110T150000Z + meta

Лицензия
MIT License — свободное использование/модификация.

Контакты
Анастасия Волконская <aavolkon@mail.ru>