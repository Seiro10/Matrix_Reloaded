# File: services/content-router-agent/Makefile

.PHONY: help install test lint format clean docker-build docker-run deploy

# Default target
help:
	@echo "Available commands:"
	@echo "  install     - Install dependencies"
	@echo "  test        - Run tests"
	@echo "  lint        - Run linting"
	@echo "  format      - Format code"
	@echo "  clean       - Clean build artifacts"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run  - Run Docker container"
	@echo "  deploy      - Deploy to GCP"

# Install dependencies
install:
	pip install -r requirements.txt
	pip install pytest pytest-cov black flake8 mypy

# Run tests
test:
	python -m pytest tests/ -v --cov=src/

# Run linting
lint:
	flake8 src/ tests/
	mypy src/

# Format code
format:
	black src/ tests/
	isort src/ tests/

# Clean build artifacts
clean:
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Build Docker image
docker-build:
	docker build -t content-router-agent .

# Run Docker container
docker-run:
	docker run -p 8080:8080 \
		-e OPENAI_API_KEY=$(OPENAI_API_KEY) \
		-e ENVIRONMENT=development \
		content-router-agent

# Deploy to GCP (requires gcloud CLI)
deploy:
	gcloud run deploy content-router-agent \
		--source . \
		--region europe-west1 \
		--platform managed \
		--memory 1Gi \
		--cpu 1

# Development server
dev:
	python src/main.py

# Install pre-commit hooks
pre-commit:
	pip install pre-commit
	pre-commit install