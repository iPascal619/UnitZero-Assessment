"""Pytest configuration and fixtures for the test suite.

Uses an in-memory SQLite database for fast, isolated tests.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

# Override DATABASE_URL before importing the app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["TESTING"] = "1"

from app.database import Base, get_db
from app.main import app
from app.models import User
from app.auth import hash_password, create_access_token

# SQLite engine for tests
engine = create_engine(
    "sqlite:///./test.db",
    connect_args={"check_same_thread": False},
)

# Enable foreign key enforcement in SQLite
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    # Clean up test.db file
    if os.path.exists("./test.db"):
        try:
            os.remove("./test.db")
        except PermissionError:
            pass


@pytest.fixture
def db():
    """Yield a test database session."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    """FastAPI test client with overridden database dependency."""

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(db, username, role, password="testpass123"):
    """Helper to create a user in the test database."""
    user = User(
        username=username,
        email=f"{username}@test.com",
        password_hash=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_token(user):
    """Helper to create a JWT token for a user."""
    return create_access_token({"sub": str(user.id), "role": user.role})


@pytest.fixture
def admin_user(db):
    return _create_user(db, "admin", "admin")


@pytest.fixture
def operator_user(db):
    return _create_user(db, "operator", "operator")


@pytest.fixture
def client_user(db):
    return _create_user(db, "client1", "client")


@pytest.fixture
def client_user2(db):
    return _create_user(db, "client2", "client")


@pytest.fixture
def admin_headers(admin_user):
    return {"Authorization": f"Bearer {_get_token(admin_user)}"}


@pytest.fixture
def operator_headers(operator_user):
    return {"Authorization": f"Bearer {_get_token(operator_user)}"}


@pytest.fixture
def client_headers(client_user):
    return {"Authorization": f"Bearer {_get_token(client_user)}"}


@pytest.fixture
def client2_headers(client_user2):
    return {"Authorization": f"Bearer {_get_token(client_user2)}"}
