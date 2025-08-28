# Study Helper Pro

A modern FastAPI application built with Poetry for dependency management, Uvicorn as the ASGI server, and Ruff for code formatting and linting.

## 🚀 Features

- **FastAPI**: High-performance web framework for building APIs
- **Poetry**: Modern dependency management and packaging
- **Uvicorn**: Lightning-fast ASGI server
- **Ruff**: Ultra-fast Python linter and formatter
- **Pre-commit hooks**: Automated code quality checks
- **Pytest**: Comprehensive testing framework

## 📋 Prerequisites

Before running this project locally, make sure you have the following installed:

- **Python 3.8+** (recommended: Python 3.11)
- **Poetry** - [Installation Guide](https://python-poetry.org/docs/#installation)

### Installing Poetry

See [Poetry Official Docs](https://python-poetry.org/docs/)


## 🛠️ Local Setup

### 1. Clone the repository
```bash
gh repo clone Adha-KG/backend
```

### 2. Install dependencies
```bash
poetry install
```

### 3. Set up pre-commit hooks
```bash
poetry run pre-commit install
```

### 4. Run the application
```bash
poetry run uvicorn app.main:app --reload
```

The API will be available at:
- **Application**: http://localhost:8000
- **Interactive API docs (Swagger)**: http://localhost:8000/docs
- **Alternative API docs (ReDoc)**: http://localhost:8000/redoc


## 🔍 Code Quality


### Pre-commit Hooks


```bash
# Manually run pre-commit on all files
poetry run pre-commit run --all-files
```
This repo has a pre-commit that formats the files before committing. You may also want to have vscode extension for a better development experience, you can install the [Ruff extension for VS Code](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff) and enable "Format on Save" in your editor settings.

## 📁 Project Structure

```
my-fastapi-project/
├── app/                    # Application code
│   ├── __init__.py
│   └── main.py            # FastAPI application entry point
├── tests/                 # Test files
│   ├── __init__.py
│   └── test_main.py
├── .github/
│   └── workflows/
│       └── ci.yml         # GitHub Actions CI/CD
├── .pre-commit-config.yaml # Pre-commit configuration
├── pyproject.toml         # Poetry configuration and project metadata
├── README.md              # This file
└── .gitignore
```





## 🤝 Contributing

> **Note:** The `main` branch is protected. Always create a feature branch for your changes and submit a Pull Request for review and merging.  
> We use **rebase** for merging Pull Requests to keep the commit history clean.

1. Create a feature branch (`git checkout -b feature/amazing-feature`)
2. Make your changes
3. Run tests and linting (`poetry run test && poetry run lint`)
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request
7. **Rebase and Merge** your PR after review

## 📝 API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🐛 Troubleshooting

### Common Issues

**Poetry not found:**
```bash
# Make sure Poetry is in your PATH
export PATH="$HOME/.local/bin:$PATH"
```

**Port already in use:**
```bash
# Use a different port
poetry run uvicorn app.main:app --reload --port 8001
```

**Pre-commit hooks failing:**
```bash
# Update pre-commit hooks
poetry run pre-commit autoupdate
```

### Getting Help

- Check the [FastAPI documentation](https://fastapi.tiangolo.com/)
- Review [Poetry documentation](https://python-poetry.org/docs/)
- Check [Ruff documentation](https://docs.astral.sh/ruff/)

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.