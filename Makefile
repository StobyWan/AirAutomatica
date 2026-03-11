.PHONY: install format lint typecheck test check run setup-ollama pi-thermal pi-snapshot pi-diag

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

setup-ollama:
	@command -v ollama >/dev/null 2>&1 || { echo "Install Ollama: https://ollama.com (macOS: brew install ollama)"; exit 1; }
	ollama pull gemma3:1b || true
	@echo "Ollama ready. Start app with: python -m airautomatica.main  (ollama is default)"

pi-thermal:
	bash scripts/pi/watch_thermal.sh

pi-snapshot:
	bash scripts/pi/bench_snapshot.sh

pi-diag:
	bash scripts/pi/quick_diag.sh
