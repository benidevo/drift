# 🌊 Drift

[![CI](https://github.com/benidevo/drift/actions/workflows/ci.yml/badge.svg)](https://github.com/benidevo/drift/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/benidevo/drift/branch/master/graph/badge.svg)](https://codecov.io/gh/benidevo/drift)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

Catch architectural violations before they become technical debt. Drift analyzes your code changes to ensure they follow established patterns.

## 🎯 The Problem

As codebases grow, they often drift away from their intended architecture:

- Direct database calls bypass the repository layer
- Services become tightly coupled instead of maintaining clean boundaries
- API contracts change without considering downstream impacts
- Established patterns get violated in the rush to ship features

Traditional code reviews catch syntax issues but often miss these architectural concerns.

## 💡 How Drift Helps

Drift integrates into your GitHub or GitLab pipeline to automatically review code changes:

1. **Detects Violations**: Identifies when code breaks architectural patterns
2. **Provides Context**: Understands why changes are being made from PR descriptions
3. **Shows Impact**: Visualizes how changes affect your system architecture
4. **Suggests Fixes**: Offers specific recommendations to maintain consistency

## ✨ Key Features

- **Pattern Detection**: Recognizes repository patterns, service boundaries, and API contracts
- **LLM Agnostic**: Use OpenAI, Gemini, Claude, or any LLM provider
- **Visual Diagrams**: See architectural impact with generated diagrams
- **Non-Blocking**: Advisory feedback that doesn't stop your deployment
- **Context Aware**: Incorporates business requirements from PR descriptions

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- Docker (optional, for containerized development)

### Development Setup

1. **Clone the repository**

   ```bash
   git clone https://github.com/benidevo/drift.git
   cd drift
   ```

2. **Install dependencies**

   ```bash
   poetry install
   ```

3. **Configure environment variables**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

4. **Set up pre-commit hooks**

   ```bash
   make setup-pre-commit
   ```

5. **Run the application**

   ```bash
   poetry run python -m drift
   ```

### Docker Development

For a consistent development environment, use Docker:

```bash
# Build the development image
make build

# Run the application
make run

# Run tests
make test

# Run linting
make lint

# Type check with mypy
make type-check

# Format code
make format
```

### Available Commands

Run `make help` to see all available commands:

- `make build`: Build Docker image
- `make run`: Run development container
- `make test`: Run tests in Docker
- `make lint`: Run linting in Docker
- `make format`: Format code in Docker
- `make type-check`: Run type checking with mypy
- `make clean`: Clean Docker images and containers
- `make setup-pre-commit`: Install pre-commit hooks

## 🧪 Testing

Run tests with coverage:

```bash
poetry run pytest
```

Or using Docker:

```bash
make test
```

## ⚙️ Configuration

Drift uses environment variables for configuration. See `.env.example` for all available options:

- **LLM Configuration**: Choose your LLM provider (OpenAI, Anthropic, etc.) and API key
- **Platform Tokens**: GitHub or GitLab tokens for API access
- **JIRA Integration**: Optional integration for pulling context from JIRA tickets
- **Custom Endpoints**: Support for enterprise LLM gateways

Example configuration:

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-...
GITHUB_TOKEN=ghp_...
```

## 🔧 Development

### Code Quality

This project uses:

- **Ruff** for linting and formatting
- **Mypy** for type checking
- **Pytest** for testing
- **Pre-commit** for git hooks

Pre-commit hooks automatically run on every commit to ensure code quality. They will:

- Format code with Ruff
- Check for linting issues
- Run type checking with Mypy
- Validate commit message format
- Fix common issues (trailing whitespace, file endings)

### Commit Messages

Follow conventional commits format:

- `feat:` New features
- `fix:` Bug fixes
- `docs:` Documentation changes
- `chore:` Maintenance tasks
- `test:` Test improvements
- `refactor:` Code refactoring

## 📊 Status

This project is under active development.

## 🛠️ Built With

- Python for broad compatibility
- LiteLLM for flexible LLM integration
- Docker for consistent deployment
- Native CI/CD integration for GitHub Actions and GitLab CI

## 📚 Documentation

- [Project Specification](docs/Project-Specification.md)
- [Technical Design](docs/Technical-Design-Document.md)
