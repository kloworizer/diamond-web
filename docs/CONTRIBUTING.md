# Contributing to Diamond

> **Last Updated:** June 23, 2026

Thank you for considering contributing to the Diamond project! This document outlines the guidelines for contributing to the codebase.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Pull Request Process](#pull-request-process)
- [Git Commit Guidelines](#git-commit-guidelines)
- [Documentation](#documentation)

---

## Code of Conduct

By participating in this project, you agree to:

- Be respectful and inclusive
- Focus on constructive feedback
- Prioritize the project's goals
- Collaborate openly

---

## Getting Started

### Prerequisites

- Python 3.10+
- Git
- Basic understanding of Django 5.2

### Setup Development Environment

```bash
# 1. Fork and clone the repository
git clone https://github.com/<your-username>/diamond-web.git
cd diamond-web

# 2. Create virtual environment
python -m venv .venv

# 3. Activate it
# Windows (PowerShell):
Set-ExecutionPolicy Unrestricted -Scope Process; .\.venv\Scripts\Activate.ps1
# Linux/Mac:
# source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements/dev.txt

# 5. Setup environment
copy .env.example.dev .env  # Windows
# cp .env.example.dev .env  # Linux/Mac

# 6. Run migrations
python manage.py migrate

# 7. Load default templates (optional)
python manage.py load_default_templates

# 8. Create superuser
python manage.py createsuperuser

# 9. Run the server
python manage.py runserver
```

---

## Development Workflow

### Branch Naming Convention

Use the format: `{team-name}-{feature-description}`

```
esha-backend-fitur-login-logout
bimo-fitur-laporan-transfer
p3de-team-fix-tiket-workflow
```

### Development Process

1. **Create a branch** from `main`
2. **Make changes** following coding standards
3. **Write/update tests** for your changes
4. **Run tests** to ensure nothing is broken
5. **Commit** with meaningful commit messages
6. **Push** to your fork
7. **Create a Pull Request**

### Sync with Main Branch

```bash
git checkout main
git pull upstream main
git checkout your-feature-branch
git merge main
```

---

## Coding Standards

### Python / Django

- Follow **PEP 8** style guide
- Use **4 spaces** for indentation (no tabs)
- Maximum line length: **100 characters** (PEP 8 recommends 79, but 100 is acceptable for Django)
- Use **meaningful variable names** (Indonesian/English consistent with project)

### Django-Specific

- **Views**: Use class-based views where appropriate (ListView, CreateView, UpdateView, DeleteView)
- **Models**: Each model in its own file under `diamond_web/models/`
- **URLs**: Maintain the existing URL pattern structure
- **Forms**: Place forms in `diamond_web/forms/` with clear naming
- **Templates**: Use `diamond_web/templates/` with Bootstrap 5 classes
- **Queries**: Use Django ORM, avoid raw SQL unless absolutely necessary
- **Context processors**: For global template variables

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Models | PascalCase | `Tiket`, `JenisDataILAP` |
| Views | PascalCase (CBV) | `TiketListView`, `ILAPCreateView` |
| Forms | PascalCase | `TiketForm`, `BackupDataForm` |
| URL patterns | snake_case | `tiket_list`, `ilap_data` |
| Templates | snake_case | `tiket_list.html`, `ilap_form.html` |
| Variables | snake_case | `nama_ilap`, `jumlah_baris` |
| Functions | snake_case | `get_next_ilap_id()` |

### Imports Organization

```python
# 1. Standard library
import os
import sys

# 2. Third-party
from django.shortcuts import render
from django.views.generic import ListView

# 3. Local
from ..models import Tiket
from ..forms import TiketForm
```

---

## Testing Guidelines

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest diamond_web/tests/test_tiket_workflow.py

# Run with coverage
pytest --cov-report=html

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

### Writing Tests

- **Unit tests**: Test individual functions, forms, model methods
- **Integration tests**: Test views, workflows, and database interactions
- **Coverage target**: Minimum **80%** for new code
- Test files go in `diamond_web/tests/`
- Test classes: `Test*` pattern
- Test functions: `test_*` pattern

### What to Test

- ✅ Form validation (valid and invalid inputs)
- ✅ View responses (status codes, template used, context data)
- ✅ Model methods and properties
- ✅ Workflow transitions (tiket status changes)
- ✅ Permission checks (role-based access)
- ✅ Report generation and export
- ⚠️ Oracle sync (mock external dependencies)

---

## Pull Request Process

### Before Submitting

1. Ensure your code compiles without errors
2. Run the full test suite: `pytest`
3. Update documentation if needed
4. Review your own diff first

### PR Title Format

```
type(scope): brief description
```

Examples:
```
feat(tiket): add bulk select for kirim tiket
fix(report): correct SLA calculation for weekends
docs(readme): update setup instructions
test(forms): add validation tests for tiket form
refactor(views): simplify home view logic
```

### PR Description Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Refactoring

## Testing
- [ ] Unit tests pass
- [ ] Manual testing completed

## Screenshots (if applicable)

## Related Issues
Fixes #123
```

### Review Process

1. At least **one approval** required from a team lead
2. All automated checks must pass
3. Address all review comments before merging
4. Squash commits before merging (if requested)

---

## Git Commit Guidelines

### Commit Message Format

```
type(scope): subject

body (optional)
```

### Types

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation changes |
| `test` | Adding/updating tests |
| `refactor` | Code refactoring |
| `style` | Formatting, missing semicolons, etc. |
| `chore` | Build tasks, dependencies, etc. |

### Examples

```
feat(tiket): add ability to filter by date range in tiket list
fix(laporan): handle division by zero in SLA calculation
docs(oracle): update connection troubleshooting guide
test(forms): add validation for empty tiket form submission
```

---

## Documentation

### When to Update Documentation

- Adding new features → update relevant docs
- Changing workflows → update status flow docs
- Adding environment variables → update `.env.example.*`
- Adding database models → update `docs/models_erd.md`
- Changing API endpoints → update `docs/API_DOCUMENTATION.md`

### Documentation Location

| Document | Location | Description |
|----------|----------|-------------|
| Main README | `readme.md` | Project overview, setup, features |
| API Docs | `docs/API_DOCUMENTATION.md` | All API endpoints |
| Database Schema | `docs/models_erd.md` | ERD and model documentation |
| Deployment Guide | `docs/PRODUCTION_SETUP.md` | Production setup |
| Security Guide | `docs/SECURITY.md` | Security measures |
| Handover Doc | `docs/HANDOVER_DOCUMENT.md` | Project handover information |
| Oracle Setup | `docs/ORACLE_SETUP.md` | Oracle connection setup |
| Status Flow | `docs/status_tiket_flow.md` | Tiket workflow diagram |
| Templates Setup | `docs/TEMPLATES_SETUP.md` | DOCX template setup |
| Deployment Checklist | `docs/DEPLOYMENT_CHECKLIST.md` | Pre-deployment checklist |
| Changelog | `docs/CHANGELOG.md` | Release history |
| Contributing | `docs/CONTRIBUTING.md` | This file |

---

## Questions?

If you have questions about contributing, please open a discussion in the repository or contact the project lead.
