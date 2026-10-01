"""FastAPI application entry point with structured logging middleware."""

import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal, Base
from app.models import User
from app.auth import hash_password, decode_access_token
from app.routers import auth, users, episodes, requests, analytics, health

# ── Structured logging setup ─────────────────────────────────────────────────

logger = logging.getLogger("requestdesk")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)
logger.setLevel(logging.INFO)


def _seed_users(db):
    """Create default users if they don't exist."""
    defaults = [
        ("admin", "admin@requestdesk.local", "admin123", "admin"),
        ("operator1", "operator1@requestdesk.local", "operator123", "operator"),
        ("client1", "client1@requestdesk.local", "client123", "client"),
        ("client2", "client2@requestdesk.local", "client234", "client"),
    ]
    for username, email, password, role in defaults:
        exists = db.query(User).filter(User.username == username).first()
        if not exists:
            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                role=role,
            )
            db.add(user)
    db.commit()


import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks: seed default users."""
    if not os.environ.get("TESTING"):
        db = SessionLocal()
        try:
            _seed_users(db)
            logger.info(json.dumps({"event": "startup", "message": "Seed users created"}))
        finally:
            db.close()
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Dataset Request Desk",
    description="Internal platform for managing robotics dataset requests",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Structured logging middleware ─────────────────────────────────────────────

@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)

    # Extract user id from token if present
    user_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = decode_access_token(token)
        if payload:
            user_id = payload.get("sub")

    log_entry = {
        "method": request.method,
        "path": str(request.url.path),
        "status": response.status_code,
        "duration_ms": duration_ms,
        "user_id": user_id,
    }
    logger.info(json.dumps(log_entry))

    return response


# ── Include routers ──────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(episodes.router)
app.include_router(requests.router)
app.include_router(analytics.router)
app.include_router(health.router)
