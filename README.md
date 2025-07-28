# 🌊 Drift

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
