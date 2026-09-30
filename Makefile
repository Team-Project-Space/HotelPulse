# HotelPulse
# NOTE (Windows): this machine's WDAC policy blocks `.venv\Scripts\python.exe`
# (error 4551), so every target uses the system `py` launcher. If `make` is not
# installed, run the equivalent `py -m ...` commands directly.

PY ?= py

.PHONY: help install install-dev run test eval db-init fmt-check clean

help:
	@echo "install      install runtime dependencies"
	@echo "install-dev  install runtime + dev dependencies"
	@echo "run          start the Streamlit dashboard"
	@echo "test         run the offline test suite (no network, no API keys)"
	@echo "eval         run the tagging accuracy eval, writes eval/results.md"
	@echo "db-init      create the SQLite database and schema"
	@echo "clean        remove caches and the local database"

install:
	$(PY) -m pip install -r requirements.txt

install-dev:
	$(PY) -m pip install -r requirements.txt pytest
	$(PY) -m pip install -e .

run:
	$(PY) -m streamlit run src/hotelpulse/app/streamlit_app.py

test:
	$(PY) -m pytest

eval:
	$(PY) eval/run_eval.py

db-init:
	$(PY) -c "import sys; sys.path.insert(0, 'src'); from hotelpulse.db.connection import init_db; init_db(); print('database ready')"

fmt-check:
	$(PY) -m compileall -q src tests eval

clean:
	rm -rf .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -f data/hotelpulse.db
