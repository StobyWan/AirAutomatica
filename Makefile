.PHONY: install format lint typecheck test check run

install:
	uv pip install -e ".[dev]"

format:
	black src tests
	isort src tests

lint:
	black --check src tests
	isort --check-only src tests

typecheck:
	mypy src tests

test:
	pytest

check: lint typecheck test

run:
	python -m airautomatica.main
