# NOTES.md — Design Decisions & Written Notes

## Stretch Item Chosen: Real-Time Updates (SSE)

Operators see request status changes and new requests live without refreshing, implemented via Server-Sent Events.

---

## 1. Design

### Data Model

```
┌──────────┐       ┌──────────────┐       ┌────────────┐
│  users   │       │   requests   │       │  episodes   │
├──────────┤       ├──────────────┤       ├────────────┤
│ id (PK)  │◄──┐   │ id (PK)      │   ┌──►│ id (PK)    │
│ username │   │   │ client_id(FK)│───┘   │ episode_id │ (unique, from CSV)
│ email    │   │   │ task_name    │       │ robot_id   │
│ password │   │   │ eps_requested│       │ task_name  │
│ role     │   │   │ deadline     │       │ recorded_at│
│ is_active│   │   │ notes        │       │ duration_s │
│ created  │   │   │ status       │       │ operator   │
└──────────┘   │   │ created_at   │       │ quality    │
               │   │ updated_at   │       └────────────┘
               │   └──────────────┘             ▲
               │          ▲                     │
               │          │                     │
               │   ┌──────┴───────┐      ┌─────┴──────┐
               │   │status_history│      │assignments │
               │   ├──────────────┤      ├────────────┤
               │   │ id (PK)      │      │ id (PK)    │
               └───┤ request_id   │      │ episode_id │ (unique constraint)
                   │ from_status  │      │ request_id │
                   │ to_status    │      │ assigned_by│
                   │ changed_by   │      │ assigned_at│
                   │ changed_at   │      └────────────┘
                   │ notes        │
                   └──────────────┘
```

**Where state lives:** All state is in PostgreSQL. The backend is stateless (no sessions, no in-memory caches) — every request reads/writes directly to the database. The only in-memory state is the SSE subscriber list for real-time events, which is ephemeral and rebuilt on reconnect. JWT tokens are the sole client-side state; they encode user ID and role for fast validation.

### Hardest Decisions

**1. Episode uniqueness — `episode_id` vs database `id`**

Episodes have a natural key (`episode_id` from the CSV, e.g. `EP-001`) and a surrogate key (auto-increment `id`). I chose to keep both: the surrogate key is the primary key and foreign key target (stable, compact, indexable), while `episode_id` has a unique constraint used for import idempotency. This avoids problems if the CSV format changes the `episode_id` scheme, and keeps joins fast.

**2. How to enforce "at most one assignment per episode"**

I used a unique constraint on `assignments.episode_id` at the database level. This means even if two operators try to assign the same episode simultaneously, only one will succeed (the other gets a constraint violation). The application also checks before insert for a better error message, but the constraint is the real safety net.

**3. Status transition logic — where to put it**

I centralized the valid transition map as a dictionary in `routers/requests.py`: `{(from, to): {allowed_roles}}`. This makes the rules visible in one place and easy to test. An alternative would be a state machine library, but for 5 transitions it felt like over-engineering. The database has a CHECK constraint on the `status` column to ensure only valid values are stored, but the transition *ordering* is enforced in application code.

---

## 2. What I Left Out / Simplified

- **Pagination on all list endpoints**: The episode list has `limit`/`offset`, but the requests list doesn't paginate. At scale, this would need cursor-based pagination.
- **Full-text search**: No search on task names or notes; just exact-match filters.
- **Audit trail for assignments**: Status changes are tracked in `status_history`, but assignment additions/removals are not independently audited (only the timestamp is recorded).
- **Password reset / email verification**: Not implemented. In production, we'd add email-based password reset and possibly SSO/OAuth2.
- **Frontend error boundaries**: Error handling is per-component, no global error boundary.
- **Rate limiting**: No rate limiting on login or API endpoints.

**What I'd do with two more days:**
1. Add proper pagination (cursor-based) to all list endpoints
2. Build an analytics dashboard in the frontend with charts
3. Add WebSocket-based notifications instead of SSE (better reconnection semantics)
4. Write integration tests that run against PostgreSQL in Docker
5. Add request-level audit logging (who assigned/removed which episode)

---

## 3. Something That Went Wrong

During development, the tests for status transitions were failing because SQLite (used in tests) doesn't enforce CHECK constraints by default the way PostgreSQL does. Specifically, the status column CHECK constraint `status IN ('submitted', ...)` was silently ignored in SQLite, allowing invalid values to be inserted.

**How I diagnosed it:** The transition test was passing when it shouldn't have — a request was transitioning from "submitted" directly to "accepted" without error. I added print statements to trace the SQL being executed and realized the CHECK constraint wasn't firing. After reading the SQLite docs, I confirmed that SQLite enforces CHECK constraints only from version 3.25+, and only when the table is created with the constraint (not altered to add it).

**How I fixed it:** I made the application logic the primary enforcer of valid transitions (the `TRANSITIONS` dictionary), not the database constraint. The CHECK constraint remains as a defense-in-depth measure in PostgreSQL production, but the application code is the authoritative source of truth. This is also better for error messages — instead of a generic constraint violation, users get "Invalid transition: submitted → accepted".

---

### 3.1 Test Suite & Setup Debugging

Later in the process, while verifying the full test suite with the company's updated seed logic, I encountered a cascade of issues that required deep debugging:

**1. Hash Collision (bcrypt/passlib)**: The tests initially failed to start due to a `ValueError: password cannot be longer than 72 bytes` caused by an incompatibility between `passlib 1.7.4` and newer `bcrypt 4.0+` versions. I diagnosed this from the traceback and pinned `bcrypt==3.2.2` in `requirements.txt`.

**2. Test Database Isolation (IntegrityError)**: Tests started failing with a `UNIQUE constraint failed: users.username`. The root cause was a conflict between the FastAPI `lifespan` event (which called `_seed_users()`) and the `pytest` test fixtures. Both were attempting to create the same default users in the same in-memory `test.db`. I fixed this by setting a `TESTING=1` environment variable in `conftest.py` and disabling the `_seed_users()` call during test runs to give the test suite full control over database state.

**3. JWT Standards Compliance (Subject must be a string)**: Tests that authenticated successfully were getting `401 Unauthorized` responses on subsequent endpoints because `python-jose` threw a `JWTError`. The issue was that the `sub` (subject) claim in the JWT payload was being populated with `user.id` (an integer), but the JWT standard requires it to be a string. I wrapped `user.id` in `str()` during token generation and cast it back to an integer in the auth dependency.

**4. Async Event Loop in Worker Threads**: Finally, event publishing for SSE was throwing `RuntimeError: There is no current event loop in thread 'AnyIO worker thread'`. This happened because FastAPI runs synchronous (`def`) endpoint functions in a worker thread without an asyncio event loop, so `asyncio.get_event_loop().create_task()` failed. I refactored the endpoints to use FastAPI's native `BackgroundTasks` instead, which idiomatically handles async background execution from sync endpoints.

---

## 4. Security

### What I did
- **Passwords**: Hashed with bcrypt via passlib. Never stored or logged in plain text. The `password_hash` field is never returned in API responses (Pydantic schemas explicitly exclude it).
- **Tokens**: JWT with HS256, configurable expiry (default 8 hours). Secret key loaded from environment variable. In production, this would be rotated and stored in a secrets manager.
- **Input validation**: All inputs validated by Pydantic schemas with type checking, length limits, and regex patterns (e.g., role must match `^(client|operator|admin)$`). SQL injection prevented by SQLAlchemy's parameterized queries.
- **Authorization**: Enforced server-side via FastAPI dependencies (`require_role()`), not just UI hiding. Every endpoint checks the JWT and the user's role before executing.

### Two Vulnerabilities I'd Worry About Most

1. **JWT secret compromise**: If `SECRET_KEY` is leaked, an attacker can forge tokens for any user/role. Mitigation: use a strong random secret (not the dev default), rotate periodically, store in a secrets manager (AWS Secrets Manager, Vault). Consider moving to asymmetric signing (RS256) so the public key can be distributed without risk.

2. **IDOR on request endpoints**: A client could potentially guess or enumerate request IDs and try to access/modify other clients' requests. While I enforce `client_id` checks on every endpoint, a bug in any new endpoint could expose this. Mitigation: consider using UUIDs instead of sequential integer IDs for requests, add middleware-level tenant isolation, and add integration tests specifically for cross-tenant access.

---

## 5. Scale

### What breaks first at 10× users and 100× episodes (~5 million episodes)

1. **The `episodes_per_day_per_robot` analytics query** becomes expensive without a composite index on `(recorded_at, robot_id)`. The current individual indexes help, but a covering index would eliminate the need for index lookups. I'd also consider a **materialized view** refreshed on a schedule for the analytics dashboard.

2. **CSV import at 5M episodes**: The current import loads all existing `episode_id` values into a Python set for dedup checking. At 5M rows, this set consumes ~250MB of memory. I'd switch to **batch processing**: read the CSV in chunks, use `INSERT ... ON CONFLICT DO NOTHING` (PostgreSQL's upsert) to let the database handle dedup, and stream results rather than building a full set.

3. **Episode list endpoint** needs cursor-based pagination instead of offset/limit (offset-based pagination degrades at high offsets because PostgreSQL still scans to the offset point).

4. **Connection pooling**: The current setup creates a new SQLAlchemy session per request. At 10× concurrent users, we'd need proper connection pooling (PgBouncer) and possibly read replicas for analytics queries.

### What I'd change
- Add composite indexes: `(recorded_at, robot_id)`, `(task_name, quality)`
- Switch to `INSERT ON CONFLICT` for imports instead of application-level dedup
- Add read replicas for analytics; run heavy queries against the replica
- Consider partitioning the `episodes` table by `recorded_at` (monthly partitions)
- Add Redis for session caching and rate limiting
- Use background workers (Celery) for CSV import processing

---

## 6. AI Tooling

I used AI coding assistants during development for:
- **Boilerplate generation**: Initial FastAPI project structure, Pydantic schema definitions, Alembic migration templates
- **Test scaffolding**: Generating the test class structure and fixture setup
- **CSS design system**: The color palette and component styles
- **Documentation**: Drafting the README structure

All generated code was reviewed, modified, and understood before committing. The core domain logic (status transitions, assignment rules, import idempotency, authorization) was designed and implemented by me, with AI helping to translate the design into code faster.
