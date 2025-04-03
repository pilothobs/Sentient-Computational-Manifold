# Contributing to Sentient Computational Manifold (SCM)

Thank you for your interest in contributing to SCM! We welcome contributions from everyone who wishes to improve this project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Issue Reporting](#issue-reporting)
- [Feature Requests](#feature-requests)

## Code of Conduct

We are committed to providing a friendly, safe, and welcoming environment for all contributors. By participating in this project, you agree to abide by the following guidelines:

- Be respectful and inclusive of all participants regardless of background.
- Exercise empathy and kindness in all interactions.
- Use welcoming and inclusive language.
- Be constructive and collaborate with other contributors.
- Gracefully accept constructive criticism.
- Focus on what is best for the community.

Unacceptable behavior includes harassment, offensive comments, unwelcome sexual attention, and other conduct that creates a hostile environment.

## Getting Started

1. **Fork the repository** on GitHub.
2. **Clone your fork** to your local machine:
   ```bash
   git clone https://github.com/YOUR_USERNAME/Sentient-Computational-Manifold.git
   cd Sentient-Computational-Manifold
   ```
3. **Set up the development environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install jsonschema rich semver graphviz
   pip install pytest pytest-cov flake8  # For testing and linting
   ```
4. **Create a new branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

1. **Branch Naming Conventions**:
   - `feature/` - For new features or enhancements
   - `bugfix/` - For bug fixes
   - `docs/` - For documentation updates
   - `refactor/` - For code refactoring
   - `test/` - For adding or updating tests

2. **Commit Guidelines**:
   - Write clear, concise commit messages.
   - Begin with a verb in the present tense (e.g., "Add feature" not "Added feature").
   - Reference issue numbers when relevant (e.g., "Fix #123: Resolve memory leak").
   - Keep commits focused on a single task or fix.

3. **Pull Requests**:
   - Update your fork to include the latest changes from the main repository before submitting a PR.
   - Provide a clear title and description for your PR.
   - Link to any related issues.
   - Include screenshots or examples if applicable.

## Submitting Changes

1. **Create a pull request** from your fork to the main repository.
2. Wait for a maintainer to review your PR.
3. Address any feedback or requested changes.
4. Once approved, a maintainer will merge your PR.

## Coding Standards

We follow PEP 8 standards for Python code. Additionally:

1. **Python Style Guidelines**:
   - Use 4 spaces for indentation (no tabs).
   - Maximum line length of 100 characters.
   - Use docstrings for all functions, classes, and modules.
   - Use type hints where appropriate.
   - Follow consistent naming conventions:
     - `snake_case` for variables and functions
     - `PascalCase` for classes
     - `UPPER_CASE` for constants

2. **Documentation**:
   - Document all public APIs with clear docstrings.
   - Include examples in docstrings where helpful.
   - Keep documentation updated when code changes.

3. **Linting**:
   - Run `flake8` to check for style issues before submitting.

## Testing Guidelines

1. **Write tests** for all new features and bug fixes.
2. **Maintain test coverage** at or above current levels.
3. **Run the test suite** before submitting changes:
   ```bash
   pytest --cov=scm tests/
   ```
4. **Include both unit tests and integration tests** where appropriate.

## Issue Reporting

When reporting bugs or issues, please include:

1. **Steps to reproduce** the issue.
2. **Expected behavior** and what actually happened.
3. **Environment details**:
   - Operating system
   - Python version
   - SCM version (or commit hash)
   - Any relevant configuration
4. **Screenshots or logs** if applicable.
5. **Potential solutions** if you have any ideas.

## Feature Requests

For feature requests, please include:

1. **Clear description** of the desired feature.
2. **Use case** explaining why this feature would be valuable.
3. **Potential implementation approaches** if you have suggestions.
4. **Examples** of similar features in other projects, if relevant.

Thank you for contributing to the Sentient Computational Manifold project! 