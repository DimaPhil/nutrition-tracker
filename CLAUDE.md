# Claude Instructions

This file configures Claude's behavior for the Nutrition Tracker project.

## Project Overview

Nutrition Tracker is a Python application for tracking nutritional data.

## Tech Stack

- **Language**: Python 3.11+
- **Testing**: pytest with pytest-cov
- **Linting**: ruff (linting + formatting)
- **CI**: GitHub Actions
- **Containerization**: Docker

## Development Commands

```bash
# Install dependencies (dev)
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov --cov-report=term-missing

# Run linter
ruff check src tests

# Run formatter
ruff format src tests

# Fix linting issues
ruff check --fix src tests

# Run pre-commit hooks
pre-commit run --all-files

# Docker commands
docker-compose run test    # Run tests
docker-compose run lint    # Run linter
docker-compose up app      # Run production
```

## Code Standards

!.agents/principles.md

## Project Structure

```
nutrition-tracker/
├── src/
│   └── nutrition_tracker/   # Main application code
├── tests/                   # Test files
├── .github/workflows/       # CI configuration
├── .agents/                 # Agent configuration
├── pyproject.toml          # Project config (pytest, ruff, deps)
├── Dockerfile              # Container definition
└── docker-compose.yml      # Container orchestration
```

## Before Committing

1. Run `pytest` - all tests must pass
2. Run `ruff check src tests` - no linting errors
3. Run `ruff format src tests` - code is formatted
4. Update tests for new functionality
5. Follow principles in `.agents/principles.md`
