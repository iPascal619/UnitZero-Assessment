# Dataset Request Desk

Internal platform for managing robotics dataset collection requests. Replaces the spreadsheet-based workflow with a structured web application.

## Quick Start

### Prerequisites
- Docker and Docker Compose

### One-command startup

```bash
docker compose up --build
```

This brings up:
- **PostgreSQL 16** on port 5432
- **Backend API** (FastAPI) on http://localhost:8000
- **Frontend** (React/Vite) on http://localhost:3000

The backend automatically runs database migrations and seeds default users on startup.

### Seed User Credentials

| Username   | Password      | Role     |
|-----------|---------------|----------|
| admin     | admin123      | admin    |
| operator1 | operator123   | operator |
| client1   | client123     | client   |
| client2   | client234     | client   |

### API Documentation

FastAPI auto-generates interactive docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Tests use an in-memory SQLite database — no external services needed.

### What the tests cover
- **Authorization rules**: login, role-based access, client data isolation
- **Status transitions**: valid/invalid transitions, role enforcement, delivery prerequisites
- **Assignment rules**: quality constraints, uniqueness, status restrictions
- **CSV import**: idempotency, data normalization, error reporting

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, middleware, startup
│   │   ├── config.py            # Environment-based configuration
│   │   ├── database.py          # SQLAlchemy engine & session
│   │   ├── models.py            # ORM models (User, Episode, Request, etc.)
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── auth.py              # JWT + bcrypt utilities
│   │   ├── dependencies.py      # FastAPI deps (auth, RBAC)
│   │   ├── events.py            # SSE event manager
│   │   ├── routers/             # API route handlers
│   │   └── services/            # Business logic (CSV import)
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Pytest test suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router & protected routes
│   │   ├── AuthContext.jsx      # Auth state management
│   │   ├── api.js               # API client
│   │   ├── components/          # Layout, shared components
│   │   └── pages/               # Login, Client, Operator, etc.
│   ├── Dockerfile
│   └── package.json
├── seed/
│   ├── episodes.csv             # Sample messy data for import testing
│   └── generate_episodes.py     # Generate large clean datasets
├── docker-compose.yml
├── NOTES.md                     # Design decisions & written notes
└── .github/workflows/ci.yml     # GitHub Actions CI
```

## Stretch Item: Real-Time Updates (SSE)

Operators see request status changes and new requests appear live without refreshing. The backend publishes Server-Sent Events via `/api/events`, and the operator dashboard subscribes to this stream using a fetch-based SSE client (to support Bearer token auth).

## Importing Episodes

Via the UI: Navigate to **Episodes** → **Import CSV** and select a CSV file.

Via API:
```bash
curl -X POST http://localhost:8000/api/episodes/import \
  -H "Authorization: Bearer <token>" \
  -F "file=@seed/episodes.csv"
```

The import is idempotent — running it multiple times on the same file will not create duplicates.
