.PHONY: help install test test-unit test-integration test-coverage lint format clean run

help:
	@echo "Grid Bot - Makefile Commands"
	@echo "=============================="
	@echo "install          Install dependencies"
	@echo "test             Run all tests"
	@echo "test-unit        Run unit tests only"
	@echo "test-integration Run integration tests only"
	@echo "test-coverage    Run tests with coverage report"
	@echo "lint             Run linters"
	@echo "format           Format code with black"
	@echo "clean            Clean generated files"
	@echo "run              Run the bot"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

test-unit:
	pytest tests/ -v -m "not integration"

test-integration:
	pytest tests/ -v -m "integration"

test-coverage:
	pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/index.html"

lint:
	flake8 *.py --exclude=venv,env,tests --max-line-length=127
	pylint *.py --disable=C0111,R0903,R0913,R0914 --max-line-length=127 || true

format:
	black *.py --exclude="venv|env|tests"

clean:
	rm -rf __pycache__
	rm -rf tests/__pycache__
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf *.pyc
	rm -rf logs/*.log
	rm -rf metrics/*.json
	rm -rf state/*.json

run:
	python grid_bot.py --config config.json

run-testnet:
	python grid_bot.py --config config.json

run-dryrun:
	python grid_bot.py --config config.json --dry-run
