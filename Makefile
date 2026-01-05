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

lint:
	poetry run ruff check .

format:
	poetry run ruff format .

fix:
	poetry run ruff check --fix .

test:
	poetry run pytest

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .ruff_cache .pytest_cache .coverage htmlcov
