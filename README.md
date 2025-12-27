# StudyMate

A modern FastAPI application built with Poetry for dependency management, Uvicorn as the ASGI server, and Ruff for code formatting and linting.

## 📖 Project Description

**StudyMate** is an intelligent document-based question-answering system powered by Retrieval-Augmented Generation (RAG). The application enables users to upload PDF documents, which are automatically processed and indexed for semantic search. Users can then query their documents using natural language questions and receive accurate, context-aware answers based on the content of their uploaded documents.

### Key Capabilities

- **Document Management**: Upload and manage PDF documents with automatic text extraction and processing
- **Intelligent Search**: Semantic search across documents using vector embeddings stored in ChromaDB
- **RAG-Powered Q&A**: Ask questions about your documents and get answers generated using Google Gemini AI with relevant context from your documents
- **Chat Sessions**: Create persistent chat sessions with document context for extended conversations
- **User Authentication**: Secure authentication and authorization using Supabase with JWT tokens
- **Background Processing**: Asynchronous PDF processing using Celery for improved performance
- **Multi-User Support**: Each user has their own isolated document collection and vector store

### Technology Stack

The backend leverages modern technologies including:
- **FastAPI** for high-performance API endpoints
- **ChromaDB** for vector storage and semantic search
- **Google Gemini API** for embeddings and LLM-powered responses
- **Supabase** for authentication, user management, and file storage
- **Celery** with Redis for background task processing
- **Sentence Transformers** for local embedding generation (optional)

## 🚀 Features

- **FastAPI**: High-performance web framework for building APIs
- **Poetry**: Modern dependency management and packaging
- **Uvicorn**: Lightning-fast ASGI server
- **Ruff**: Ultra-fast Python linter and formatter
- **Pre-commit hooks**: Automated code quality checks
- **Pytest**: Comprehensive testing framework

## 📋 Prerequisites

Before running this project locally, make sure you have the following installed:

- **Python 3.12+** (required: see `pyproject.toml`)
- **Poetry** - [Installation Guide](https://python-poetry.org/docs/#installation)
- **Redis** - Required for Celery task queue
  - **Linux**: `sudo apt-get install redis-server` or `sudo systemctl start redis`
  - **macOS**: `brew install redis` and `brew services start redis`
  - **Windows**: Download from [Redis for Windows](https://redis.io/download) or use WSL

## 🛠️ Local Setup

### 1. Clone the repository
```bash
git clone https://github.com/username/repository-name.git
cd backend
```

### 2. Install dependencies
```bash
poetry install
```

### 3. Set up environment variables

Create a `.env` file in the project root with the following variables:

```bash
# ChromaDB configuration
CHROMA_API_KEY=your_chroma_api_key_here
CHROMA_HOST=localhost:8000  # or your ChromaDB host

# Redis configuration (for Celery)
REDIS_URL=redis://localhost:6379/0

# Google Gemini API (for embeddings/LLM)
GEMINI_API_KEY=your_gemini_api_key_here

# Supabase configuration (for authentication and storage)
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_STORAGE_BUCKET=your_storage_bucket_name  # Optional, if using Supabase storage
```

**Getting API Keys:**
- **Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- **ChromaDB**: Use local instance (no key needed) or get from [ChromaDB Cloud](https://www.trychroma.com/)
- **Supabase**: Create a project at [Supabase](https://supabase.com/) to get URL and keys

### 4. Set up pre-commit hooks (optional)
```bash
poetry run pre-commit install
```

### 5. Run the application

This project requires **three services** to run simultaneously:

#### Option A: Using the run script (Recommended)

```bash
chmod +x run.sh
./run.sh
```

This script will automatically:
- Start Redis server
- Start Celery worker
- Start FastAPI server

#### Option B: Manual setup (3 terminals)

**Terminal 1 - Start Redis server:**
```bash
redis-server
# Or if Redis is installed as a service:
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

**Terminal 2 - Start Celery Worker** (processes PDF uploads in background):
```bash
poetry run celery -A app.celery_app worker --loglevel=INFO --pool=solo
```

**Terminal 3 - Start FastAPI Server:**
```bash
poetry run uvicorn app.main:app --reload --port 8000
```

The API will be available at:
- **Application**: http://localhost:8000
- **Health Check**: http://localhost:8000/health
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
backend/
├── app/                           # Application code
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Environment configuration
│   ├── celery_app.py              # Celery configuration
│   ├── schemas.py                 # Pydantic schemas
│   ├── tasks.py                   # Celery tasks (PDF processing)
│   ├── auth/                      # Authentication module
│   │   ├── auth.py                # JWT authentication
│   │   └── supabase_client.py     # Supabase client
│   ├── routes/                    # API route handlers
│   │   ├── __init__.py
│   │   ├── auth.py                # Authentication routes
│   │   ├── users.py               # User management routes
│   │   ├── admin.py               # Admin routes
│   │   ├── documents.py           # Document upload/management
│   │   ├── query.py               # Query/RAG endpoints
│   │   ├── chat.py                # Chat endpoints
│   │   └── stats.py               # Statistics endpoints
│   └── services/                  # Service modules
│       ├── chunker.py             # Text chunking service
│       ├── embeddings.py          # Embedding generation
│       ├── pdf_loader.py          # PDF text extraction
│       ├── rag.py                 # RAG (Retrieval-Augmented Generation)
│       ├── retriever.py           # Semantic search/retrieval
│       ├── vectorstore.py         # ChromaDB vector store
│       ├── chat_service.py        # Chat service
│       ├── document_service.py    # Document service
│       ├── file_storage.py        # File storage (Supabase)
│       ├── storage_service.py     # Storage service
│       └── user_service.py        # User service
├── tests/                         # Test files
│   └── __init__.py
├── chroma_db/                     # Local ChromaDB storage
├── uploads/                       # Uploaded PDF files (created at runtime)
├── models_cache/                  # Cached ML models (sentence-transformers)
├── run.sh                         # Startup script
├── pyproject.toml                 # Poetry configuration and dependencies
├── poetry.lock                    # Locked dependencies
├── README.md                      # This file
└── .gitignore
```

## 🔧 Additional Setup

### Installing Sentence Transformers (if needed)

If you need to use sentence transformers for local embeddings:

```bash
# Install PyTorch (CPU version)
poetry add torch --source pytorch-cpu

# Install sentence-transformers
poetry add sentence-transformers
```

The models will be automatically downloaded and cached in `models_cache/` on first use.





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

**Redis connection error:**
```bash
# Check if Redis is running
redis-cli ping
# Should return: PONG

# Start Redis if not running
redis-server
# Or on Linux:
sudo systemctl start redis
```

**Celery worker not connecting:**
- Verify your `REDIS_URL` in `.env` file matches your Redis configuration
- Default: `redis://localhost:6379/0`
- Make sure Redis is running before starting Celery worker

**Port already in use:**
```bash
# Use a different port
poetry run uvicorn app.main:app --reload --port 8001
```

**Environment variables not loading:**
- Ensure `.env` file exists in the project root
- Verify all required variables are set
- Restart the application after changing `.env` file

**Supabase authentication errors:**
- Verify `SUPABASE_URL` and `SUPABASE_KEY` are correct
- Check that your Supabase project is active
- Ensure the Supabase service is accessible

**PDF processing fails:**
- Check Celery worker logs for errors
- Ensure ChromaDB is accessible (check `CHROMA_HOST` and `CHROMA_API_KEY`)
- Verify `GEMINI_API_KEY` is valid for embedding generation
- Make sure the Celery worker is running

**Pre-commit hooks failing:**
```bash
# Update pre-commit hooks
poetry run pre-commit autoupdate
```

### Getting Help

- Check the [FastAPI documentation](https://fastapi.tiangolo.com/)
- Review [Poetry documentation](https://python-poetry.org/docs/)
- Check [Ruff documentation](https://docs.astral.sh/ruff/)
- Review [Celery documentation](https://docs.celeryq.dev/)
- Check [Supabase documentation](https://supabase.com/docs)
## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.