.PHONY: reproduce verify figures test lint check manifest clean

reproduce:
	python scripts/reproduce_core_results.py

manifest:
	python scripts/build_manifest.py

verify:
	python scripts/verify_research_artifacts.py

figures: reproduce
	python scripts/generate_figures.py

test:
	pytest -q --cov=fifteenpick_prediction --cov-report=term-missing

lint:
	ruff check src scripts tests

check: lint test verify

clean:
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov build dist *.egg-info src/*.egg-info
