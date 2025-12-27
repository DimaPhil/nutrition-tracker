# Agent Instructions

Configuration for AI agents working on the Nutrition Tracker project.

## Core Principles

!.agents/principles.md

## Agent-Specific Guidelines

### Code Generation

- Always follow the principles defined above
- Generate type-annotated Python code
- Include docstrings for all public functions/classes
- Write tests alongside implementation code
- Use dependency injection for external services

### Code Review

- Verify SOLID principles are followed
- Check for proper error handling
- Ensure adequate test coverage
- Validate naming conventions
- Look for security vulnerabilities

### Refactoring

- Apply the Rule of Three before abstracting
- Preserve existing behavior (verify with tests)
- Make small, incremental changes
- Update tests to match changes

### Testing Strategy

- Unit tests for business logic
- Integration tests for external services
- Use fixtures for test setup
- Mock external dependencies
- Aim for deterministic tests

## File Conventions

| Directory | Purpose |
|-----------|---------|
| `src/nutrition_tracker/` | Application source code |
| `tests/` | All test files |
| `tests/conftest.py` | Shared fixtures |

## Quality Gates

All changes must pass:

1. `pytest` - All tests pass
2. `ruff check` - No linting errors
3. `ruff format --check` - Code is formatted
4. Coverage >= 80%
