.PHONY: install run build publish package-install lint format fix test clean help

# === УСТАНОВКА И РАЗРАБОТКА ===
install:
	poetry install

run:
	poetry run project

build:
	poetry build

publish:
	poetry publish --dry-run

package-install:
	python -m pip install dist/*.whl

# === КОД КАЧЕСТВО ===
lint:
	poetry run ruff check .

format:
	poetry run ruff format .

fix:
	poetry run ruff check --fix .

test:
	poetry run pytest

clean:
	powershell -Command "Get-ChildItem -Path . -Directory -Filter '__pycache__', '.ruff_cache', '.pytest_cache', '.coverage', 'htmlcov' | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue"
	powershell -Command "Get-ChildItem -Path . -File -Filter '*.pyc' | Remove-Item -Force -ErrorAction SilentlyContinue"

# === ПОМОЩЬ ===
help:
	@echo "=============================================="
	@echo "  VALUTA TRADE HUB"
	@echo "=============================================="
	@echo ""
	@echo "DEV COMMANDS:"
	@echo "  make install      - install dependencies"
	@echo "  make lint         - review code by linter"
	@echo "  make format       - code formating"
	@echo "  make test         - run tests"
	@echo "  make clean        - clean cache"
	@echo ""
	@echo "APP COMMANDS (через poetry run):"
	@echo "  poetry run project register --username NAME --password PASSWORD"
	@echo "  poetry run project login --username NAME --password PASSWORD"
	@echo "  poetry run project show-portfolio --username NAME"
	@echo "  poetry run project buy --username NAME --currency BTC --amount 0.5"
	@echo "  poetry run project sell --username NAME --currency ETH --amount 2.0"
	@echo "  poetry run project get-rate --currency BTC"
	@echo "  poetry run project show-rates"
	@echo "  poetry run project update-rates"
	@echo ""
	@echo "EXAMPLES:"
	@echo "  poetry run project register --username alice --password 1234"
	@echo "  poetry run project login --username alice --password 1234"
	@echo "  poetry run project buy --username alice --currency BTC --amount 0.1"
	@echo ""
	@echo "COMMAND HELP:"
	@echo "  poetry run project --help"
	@echo "  poetry run project login --help"

# === АЛЬТЕРНАТИВА: Make с параметрами ===
# Использование: make register USER=alice PASS=1234
register:
ifndef USER
	$(error USER не указан. Используйте: make register USER=имя PASS=пароль)
endif
ifndef PASS
	$(error PASS не указан. Используйте: make register USER=имя PASS=пароль)
endif
	poetry run project register --username $(USER) --password $(PASS)

login:
ifndef USER
	$(error USER не указан. Используйте: make login USER=имя PASS=пароль)
endif
ifndef PASS
	$(error PASS не указан. Используйте: make login USER=имя PASS=пароль)
endif
	poetry run project login --username $(USER) --password $(PASS)

portfolio:
ifndef USER
	$(error USER не указан. Используйте: make portfolio USER=имя)
endif
	poetry run project show-portfolio --username $(USER)

# Использование: make buy USER=alice SYM=BTC AMT=0.5
buy:
ifndef USER
	$(error USER не указан. Используйте: make buy USER=имя SYM=символ AMT=сумма)
endif
ifndef SYM
	$(error SYM не указан. Используйте: make buy USER=имя SYM=символ AMT=сумма)
endif
ifndef AMT
	$(error AMT не указан. Используйте: make buy USER=имя SYM=символ AMT=сумма)
endif
	poetry run project buy --username $(USER) --symbol $(SYM) --amount $(AMT)

sell:
ifndef USER
	$(error USER не указан. Используйте: make sell USER=имя SYM=символ AMT=сумма)
endif
ifndef SYM
	$(error SYM не указан. Используйте: make sell USER=имя SYM=символ AMT=сумма)
endif
ifndef AMT
	$(error AMT не указан. Используйте: make sell USER=имя SYM=символ AMT=сумма)
endif
	poetry run project sell --username $(USER) --symbol $(SYM) --amount $(AMT)

rate:
ifndef SYM
	$(error SYM не указан. Используйте: make rate SYM=символ)
endif
	poetry run project get-rate --symbol $(SYM)

rates:
	poetry run project show-rates

update:
	poetry run project update-rates

