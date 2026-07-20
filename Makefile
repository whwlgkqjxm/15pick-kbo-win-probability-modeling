.PHONY: install verify test lint check

install:
	python -m pip install -e ".[dev]"

verify:
	python scripts/verify_published_results.py

test:
	pytest -q

lint:
	ruff check src scripts tests

check: verify test lint
