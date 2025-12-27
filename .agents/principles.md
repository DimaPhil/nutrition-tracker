# Code Principles & Standards

This document defines the core principles and standards for all code in this project. All contributors (human and AI) must adhere to these guidelines.

---

## SOLID Principles

### Single Responsibility Principle (SRP)
- Each class/module should have one reason to change
- Functions should do one thing and do it well
- Split large modules into focused, cohesive units

### Open/Closed Principle (OCP)
- Open for extension, closed for modification
- Use abstractions and interfaces to allow behavior extension
- Favor composition over inheritance

### Liskov Substitution Principle (LSP)
- Subtypes must be substitutable for their base types
- Don't break behavioral contracts in derived classes
- Ensure method signatures and semantics are preserved

### Interface Segregation Principle (ISP)
- Prefer small, focused interfaces over large monolithic ones
- Clients should not depend on methods they don't use
- Split interfaces by client needs

### Dependency Inversion Principle (DIP)
- Depend on abstractions, not concretions
- High-level modules should not depend on low-level modules
- Use dependency injection for flexibility and testability

---

## Core Design Principles

### DRY (Don't Repeat Yourself)
- Extract common logic into reusable functions/classes
- Use constants for magic values
- Centralize configuration and shared behavior
- Exception: Prefer duplication over wrong abstraction (Rule of Three)

### KISS (Keep It Simple, Stupid)
- Choose the simplest solution that works
- Avoid premature optimization
- Write code that is easy to understand and maintain
- Complex solutions require justification

### YAGNI (You Aren't Gonna Need It)
- Don't implement features until they're actually needed
- Avoid speculative generalization
- Focus on current requirements, not hypothetical futures

### WAGMI (We're All Gonna Make It)
- Write code that helps the team succeed
- Prioritize collaboration and knowledge sharing
- Leave code better than you found it
- Document decisions for future contributors

---

## Clean Code Standards

### Naming Conventions
- Use descriptive, intention-revealing names
- Functions: verb phrases (`calculate_total`, `validate_input`)
- Classes: noun phrases (`UserRepository`, `NutritionCalculator`)
- Variables: descriptive nouns (`user_count`, `daily_calories`)
- Constants: SCREAMING_SNAKE_CASE (`MAX_RETRIES`, `DEFAULT_TIMEOUT`)
- Avoid abbreviations unless universally understood

### Functions
- Keep functions small (ideally < 20 lines)
- Single level of abstraction per function
- Maximum 3-4 parameters; use objects for more
- Avoid side effects; prefer pure functions
- Return early to reduce nesting

### Classes
- Keep classes focused and cohesive
- Prefer composition over inheritance
- Use dataclasses for data containers
- Keep public interface minimal

### Comments
- Code should be self-documenting
- Use comments for "why", not "what"
- Keep comments updated with code changes
- Use docstrings for public APIs (Google style)

### Error Handling
- Use exceptions for exceptional conditions
- Catch specific exceptions, not bare `except:`
- Provide meaningful error messages
- Don't use exceptions for control flow
- Fail fast, fail loud

---

## Python-Specific Standards

### Type Hints
- Use type hints for all public APIs
- Use `typing` module for complex types
- Prefer `|` union syntax over `Union[]` (Python 3.10+)
- Use `TypeAlias` for complex type definitions

### Imports
- Group imports: stdlib, third-party, local
- Use absolute imports
- Avoid `from module import *`
- Sort imports with isort/ruff

### Code Style
- Follow PEP 8 (enforced by ruff)
- Maximum line length: 88 characters
- Use Google-style docstrings
- Prefer f-strings over `.format()` or `%`

### Testing
- Aim for 80%+ code coverage
- Use pytest fixtures for shared setup
- Test behavior, not implementation
- One assertion per test concept
- Use descriptive test names: `test_<function>_<scenario>_<expected>`

---

## Architecture Guidelines

### Layered Architecture
```
src/
├── nutrition_tracker/
│   ├── domain/      # Business logic, entities
│   ├── services/    # Application services
│   ├── adapters/    # External integrations
│   └── api/         # Entry points (CLI, web)
```

### Dependency Direction
- Dependencies flow inward (adapters -> services -> domain)
- Domain layer has no external dependencies
- Use dependency injection for external services

### Configuration
- Use environment variables for deployment config
- Use `.env` files for local development (never commit)
- Validate configuration at startup

---

## Code Review Checklist

Before submitting code, verify:

- [ ] All tests pass
- [ ] Linter passes with no warnings
- [ ] New code has appropriate test coverage
- [ ] Public APIs have docstrings
- [ ] No hardcoded secrets or credentials
- [ ] Error handling is appropriate
- [ ] Code follows naming conventions
- [ ] Complex logic is documented
- [ ] No unnecessary dependencies added
- [ ] Changes are backward compatible (or documented)

---

## Anti-Patterns to Avoid

- **God Objects**: Classes that do too much
- **Spaghetti Code**: Tangled, hard-to-follow logic
- **Magic Numbers**: Unexplained numeric literals
- **Deep Nesting**: More than 3 levels of indentation
- **Long Parameter Lists**: More than 4 parameters
- **Feature Envy**: Methods using other objects' data excessively
- **Primitive Obsession**: Using primitives instead of small objects
- **Speculative Generality**: Building for hypothetical future needs
