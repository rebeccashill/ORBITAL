# Contributing to ORBITAL

Thank you for your interest in contributing to ORBITAL.

ORBITAL is a domain-agnostic mission planning framework focused on
constraint discipline, robustness, and transparent feasibility reporting
across aerospace domains.

## Development Setup

1. Clone the repository
2. Create a virtual environment
3. Install dependencies:

   pip install -r requirements.txt
   pip install -r requirements-dev.txt

## Code Style

- Format code with `black`
- Lint with `ruff`
- Type check with `mypy`
- Keep functions small and modular
- Preserve separation between:
  - decision variables
  - constraints
  - objectives
  - simulation
  - planner

## Testing

- All new features should include tests in the `tests/` directory
- Run tests with:

  pytest

## Pull Requests

- Open a clear, descriptive PR
- Explain architectural impact if modifying core planner logic
- Ensure all tests pass before requesting review

Thank you for helping improve ORBITAL.