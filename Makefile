.PHONY: install format lint typecheck test check run setup-ollama pi-thermal pi-ollama pi-log-thermal pi-snapshot pi-diag pi-download-deb pi-upgrade-deb pi-upgrade-latest

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

pi-ollama:
	bash scripts/pi/watch_ollama.sh

pi-log-thermal:
	bash scripts/pi/log_thermal_csv.sh

pi-snapshot:
	bash scripts/pi/bench_snapshot.sh

pi-diag:
	bash scripts/pi/quick_diag.sh

pi-verify-video:
	uv run python scripts/pi/verify_video_playback.py

pi-download-deb:
	REPO="$(REPO)" TAG="$(TAG)" bash scripts/pi/download_latest_deb.sh

pi-upgrade-deb:
	bash scripts/pi/upgrade_deb.sh $(DEB)

pi-upgrade-latest:
	@DEB=$$(REPO="$(REPO)" TAG="$(TAG)" bash scripts/pi/download_latest_deb.sh | tail -1) && \
	bash scripts/pi/upgrade_deb.sh "$$DEB"
