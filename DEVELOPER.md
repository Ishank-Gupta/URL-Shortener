# Developer Guide — URL Shortener

This document covers the architecture, conventions, data flow, and development workflow for the URL Shortener project. Read this before contributing or extending the codebase.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Map](#service-map)
3. [Request Flow](#request-flow)
4. [Backend Deep Dive](#backend-deep-dive)
5. [Frontend Deep Dive](#frontend-deep-dive)
6. [Database Schema](#database-schema)
7. [Caching Strategy](#caching-strategy)
8. [Rate Limiting](#rate-limiting)
9. [Configuration](#configuration)
10. [Docker Setup](#docker-setup)
11. [Local Development](#local-development)
12. [API Reference](#api-reference)
13. [Error Handling](#error-handling)
14. [Adding New Features](#adding-new-features)
15. [Known Limitations & Future Work](#known-limitations--future-work)

---

## Architecture Overview

```
┌─────────────┐     ┌─────────┐     ┌───────────┐     ┌────────────┐
│   Browser   │────▶│  Nginx  │────▶│  FastAPI │────▶│ PostgreSQL │
│  (React UI) │     │  :80    │     │  :8000    │     │  :5432     │
└─────────────┘     └─────────┘     └─────┬─────┘     └────────────┘
                                          │
                                          ▼
                                    ┌───────────┐
                                    │   Redis   │
                                    │   :6379   │
                                    └───────────┘
```

**Pattern:** Reverse-proxy architecture with async backend, read-through cache, and relational storage.

Nginx sits at the edge and routes traffic:
- `/api/*` and `/{short_code}` → FastAPI backend
- Everything else → React dev server (Vite)

The backend is fully async (asyncpg + redis.asyncio), so a single process handles many concurrent connections without blocking on I/O.

---

## Service Map

| Service | Image / Build      | Port  | Role                              |
|---------|--------------------|-------|-----------------------------------|
| `nginx` | `nginx:alpine`     | 80    | Reverse proxy, TLS termination    |
| `api`   | `./backend`        | 8000  | FastAPI application server        |
| `web`   | `./frontend`       | 5173  | Vite React dev server             |
| `db`    | `postgres:16-alpine` | 5432 | Primary data store                |
| `redis` | `redis:7-alpine`   | 6379  | Cache + rate limiter              |

**Dependency chain:** `nginx` → `api` + `web` → `db` + `redis`

Docker Compose health checks on `db` and `redis` ensure the API doesn't start until storage is ready.

---

## Request Flow

### Shortening a URL (`POST /api/shorten`)

```
Client
  │
  ▼
Nginx ──▶ FastAPI (routes.py :: shorten_url)
              │
              ├─ Validate input (Pydantic schema)
              ├─ If custom_alias: check uniqueness in DB
              ├─ Generate short_code via secrets.token_urlsafe()
              ├─ INSERT into `urls` table
              ├─ SET key in Redis cache
              └─ Return URLResponse with short_url
```

### Redirecting (`GET /{short_code}`)

```
Client
  │
  ▼
Nginx ──▶ FastAPI (main.py :: redirect_to_url)
              │
              ├─ Rate limit check (Redis INCR + EXPIRE)
              ├─ Cache HIT? → redirect immediately
              │     └─ Also: UPDATE click_count, INSERT into clicks
              │
              ├─ Cache MISS? → SELECT from `urls` table
              │     ├─ Not found → 404
              │     ├─ Expired → 410
              │     └─ Found → SET cache, UPDATE click_count, INSERT click, 302 redirect
              │
              └─ Return RedirectResponse(url=original_url, status_code=302)
```

**Why 302 (temporary) instead of 301 (permanent)?**
A 301 is cached by the browser permanently. If the user deletes or updates the short URL, browsers with a cached 301 would never hit the server again. 302 ensures every click is tracked and the mapping can be changed.

---

## Backend Deep Dive

### Directory Structure

```
backend/
├── app/
│   ├── __init__.py      # Package marker
│   ├── main.py          # FastAPI app, lifespan events, redirect handler
│   ├── routes.py        # /api/* CRUD endpoints
│   ├── models.py        # SQLAlchemy ORM models (URL, Click)
│   ├── schemas.py       # Pydantic request/response schemas
│   ├── database.py      # Async engine + session factory
│   ├── cache.py         # Redis get/set/delete + rate limiter
│   ├── config.py        # Settings loaded from environment
│   └── utils.py         # Short code generation + uniqueness check
├── Dockerfile
├── requirements.txt
└── .env.example
```

### Key Design Decisions

**Async everywhere.** `asyncpg` for PostgreSQL, `redis.asyncio` for Redis, and FastAPI's native async support. This means no thread pool overhead for I/O — a single uvicorn worker can handle hundreds of concurrent connections.

**Lifespan events** (`main.py`). Tables are created via `Base.metadata.create_all` on startup. This is intentional for development simplicity. For production, replace with Alembic migrations.

**Session-per-request** (`database.py`). Each request gets its own `AsyncSession` via FastAPI's dependency injection. The session auto-commits on success and rolls back on exception.

**Short code generation** (`utils.py`). Uses Python's `secrets` module (cryptographically secure). The `get_unique_short_code()` function retries up to 10 times on collision, which is overkill at any realistic scale — at 6 chars with base64url alphabet, you have ~56 billion possible codes.

### Adding a New Endpoint

1. Define request/response schemas in `schemas.py`
2. Add the route function in `routes.py` (it's already mounted on `/api`)
3. If it needs a new model, add it to `models.py` and restart (or run Alembic)

---

## Frontend Deep Dive

### Directory Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ShortenForm.tsx   # URL input + custom alias form
│   │   └── URLList.tsx       # Table with copy/delete actions
│   ├── api.ts                # Typed fetch wrappers for all endpoints
│   ├── App.tsx               # Root component, state management
│   ├── main.tsx              # React entry point
│   └── index.css             # Global styles
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── Dockerfile
```

### State Management

Plain React `useState` — no external state library. The URL list lives in `App.tsx` and flows down:
- `ShortenForm` calls `onShortened(entry)` → prepends to list
- `URLList` calls `onDeleted(shortCode)` → filters from list

This is sufficient for the current feature set. If you add auth or complex state, consider Zustand or React Context.

### API Layer (`api.ts`)

All backend calls go through typed functions:
- `shortenUrl(url, customAlias?)` → `POST /api/shorten`
- `listUrls(skip, limit)` → `GET /api/urls`
- `getUrlStats(shortCode)` → `GET /api/urls/{code}/stats`
- `deleteUrl(shortCode)` → `DELETE /api/urls/{code}`

The Vite dev server proxies `/api` to `http://localhost:8000` (see `vite.config.ts`), so no CORS issues during development.

### Styling

Plain CSS in `index.css`. No framework (Tailwind, MUI, etc.) to keep the dependency surface small. The layout is responsive down to 600px.

---

## Database Schema

### `urls` table

| Column        | Type         | Constraints              | Notes                        |
|---------------|--------------|--------------------------|------------------------------|
| `id`          | `INTEGER`    | PK, autoincrement        |                              |
| `short_code`  | `VARCHAR(20)`| UNIQUE, NOT NULL, indexed | The lookup key               |
| `original_url`| `TEXT`       | NOT NULL                 | The destination              |
| `custom_alias`| `VARCHAR(50)`| UNIQUE, nullable         | User-chosen alias            |
| `created_at`  | `DATETIME`   | NOT NULL, default now    |                              |
| `expires_at`  | `DATETIME`   | nullable                 | NULL = never expires         |
| `click_count` | `INTEGER`    | NOT NULL, default 0      | Denormalized for fast reads  |

### `clicks` table

| Column       | Type         | Constraints              | Notes                        |
|--------------|--------------|--------------------------|------------------------------|
| `id`         | `INTEGER`    | PK, autoincrement        |                              |
| `url_id`     | `INTEGER`    | FK → urls.id, CASCADE    |                              |
| `clicked_at` | `DATETIME`   | NOT NULL, default now    | Indexed for time queries     |
| `referrer`   | `TEXT`       | nullable                 | HTTP Referer header          |
| `user_agent` | `TEXT`       | nullable                 | Browser/bot identification   |
| `ip_address` | `VARCHAR(45)`| nullable                 | Supports IPv6                |

**Why denormalize `click_count`?** Reading `SELECT COUNT(*) FROM clicks WHERE url_id = ?` on every list/stats call is expensive. The counter on `urls` gives O(1) reads at the cost of an extra UPDATE on each redirect.

### Indexes

- `ix_urls_short_code` — the primary lookup path
- `ix_clicks_url_id` — join clicks to their URL
- `ix_clicks_clicked_at` — time-range analytics queries

---

## Caching Strategy

**Pattern:** Read-through cache with explicit invalidation.

```
GET /{short_code}
  └─ Redis GET url:{short_code}
       ├─ HIT  → use cached original_url
       └─ MISS → query PostgreSQL → Redis SET with 1h TTL
```

**Cache key format:** `url:{short_code}` → `original_url` (plain string, not JSON)

**TTL:** 3600 seconds (1 hour). Configurable in `cache.py :: CACHE_TTL`.

**Invalidation:** On `DELETE /api/urls/{code}`, the cache key is explicitly deleted. No invalidation on click (the cached value doesn't change).

**Why not cache forever?** URL expiration. A URL that expires at T+30min must not be served from a cache that outlives it. The 1h TTL is a balance between hit rate and staleness.

---

## Rate Limiting

**Implementation:** Sliding window counter in Redis.

```python
key = f"rate:{client_ip}"
# INCR key (creates at 0 if missing, then increments)
# EXPIRE key 60 (resets the window every 60 seconds)
```

**Default limit:** 30 requests per minute per IP address.

**Scope:** Only the redirect endpoint (`GET /{short_code}`) is rate-limited. API endpoints (`/api/*`) are not — add middleware if needed.

**Response on limit exceeded:** HTTP 429 with `{"detail": "Rate limit exceeded"}`.

---

## Configuration

All config is via environment variables, loaded by Pydantic Settings (`config.py`):

| Variable               | Default                                             | Description              |
|------------------------|-----------------------------------------------------|--------------------------|
| `DATABASE_URL`         | `postgresql+asyncpg://postgres:postgres@db:5432/urlshortener` | Async PG connection string |
| `REDIS_URL`            | `redis://redis:6379/0`                              | Redis connection string  |
| `BASE_URL`             | `http://localhost:8000`                              | Prefix for short URLs    |
| `SHORT_CODE_LENGTH`    | `6`                                                 | Generated code length    |
| `RATE_LIMIT_PER_MINUTE`| `30`                                                | Redirects per IP per min |

In Docker, these are set in `docker-compose.yml`. For local dev, copy `.env.example` to `.env` and edit.

---

## Docker Setup

### Build & Run

```bash
docker compose up --build        # first time or after code changes
docker compose up                # subsequent runs
docker compose down              # stop all services
docker compose down -v           # stop and delete volumes (wipes DB)
```

### Volumes

- `postgres_data` — persists database across restarts
- `./backend:/app` — live reload for backend code
- `./frontend:/app` + anonymous `/app/node_modules` — live reload for frontend without overwriting container's node_modules

### Logs

```bash
docker compose logs api          # backend logs
docker compose logs web          # frontend logs
docker compose logs db           # PostgreSQL logs
docker compose logs -f           # tail all services
```

---

## Local Development

For faster iteration without Docker:

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate                   # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env: point DATABASE_URL and REDIS_URL to localhost
uvicorn app.main:app --reload --port 8000
```

Requires PostgreSQL and Redis running locally (or in Docker):
```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=urlshortener -p 5432:5432 postgres:16-alpine
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://localhost:8000` automatically.

---

## API Reference

### `POST /api/shorten`

Create a short URL.

**Request:**
```json
{
  "url": "https://example.com/long/path",
  "custom_alias": "my-link",       // optional, 3-50 chars, [a-zA-Z0-9_-]
  "expires_at": "2026-12-31T23:59:59"  // optional, ISO 8601
}
```

**Response (201):**
```json
{
  "short_code": "my-link",
  "short_url": "http://localhost/my-link",
  "original_url": "https://example.com/long/path",
  "created_at": "2026-10-04T12:00:00",
  "expires_at": "2026-12-31T23:59:59",
  "click_count": 0
}
```

**Errors:** 409 (alias taken), 422 (invalid input)

### `GET /api/urls?skip=0&limit=50`

List all shortened URLs, newest first.

### `GET /api/urls/{short_code}/stats`

Returns URL metadata + last 100 clicks with timestamps, referrer, and user agent.

### `DELETE /api/urls/{short_code}`

Deletes the URL and all its click history. Returns 204 on success.

### `GET /{short_code}`

Redirects to the original URL (302). Records a click. Rate-limited.

**Errors:** 404 (not found), 410 (expired), 429 (rate limited)

### `GET /health`

Returns `{"status": "ok", "timestamp": "..."}`. Use for Docker health checks and uptime monitoring.

---

## Error Handling

All error responses follow the format:
```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning              | When                                  |
|--------|----------------------|---------------------------------------|
| 404    | Not Found            | Short code doesn't exist              |
| 409    | Conflict             | Custom alias already taken            |
| 410    | Gone                 | Short URL has expired                 |
| 422    | Unprocessable Entity | Invalid input (Pydantic validation)   |
| 429    | Too Many Requests    | Rate limit exceeded                   |
| 500    | Internal Server Error| Unhandled exception (check logs)      |

---

## Adding New Features

### Example: Adding user authentication

1. Add `users` table to `models.py` (id, email, password_hash, created_at)
2. Add auth schemas to `schemas.py` (UserCreate, UserLogin, TokenResponse)
3. Create `auth.py` with JWT token generation/verification
4. Add `/api/auth/register` and `/api/auth/login` to a new `auth_routes.py`
5. Add `user_id` FK to `urls` table
6. Create a `get_current_user` dependency for protected routes
7. Update frontend: add login/register pages, store JWT in localStorage, send in Authorization header

### Example: Adding QR code generation

1. `pip install qrcode[pil]` → add to `requirements.txt`
2. Add `GET /api/urls/{short_code}/qr` endpoint in `routes.py`
3. Generate QR with `qrcode.make(short_url)`, return as PNG via `StreamingResponse`
4. Add a "QR" button in `URLList.tsx` that opens the image

---

## Known Limitations & Future Work

| Limitation | Impact | Fix |
|-----------|--------|-----|
| No authentication | Anyone can see/delete all URLs | Add JWT auth (see above) |
| `create_all` for schema | Can't do incremental migrations | Add Alembic |
| No tests | Regressions go unnoticed | Add pytest + httpx async tests |
| Single-process uvicorn | Limited throughput | Add gunicorn with uvicorn workers |
| No HTTPS | Insecure in production | Add TLS cert to nginx config |
| No duplicate URL detection | Same URL can be shortened multiple times | Add optional dedup lookup |
| `click_count` race condition | Concurrent redirects may lose counts | Use `UPDATE ... SET click_count = click_count + 1` (already does this via ORM, but under very high concurrency consider raw SQL with `FOR UPDATE`) |
| No geo-IP | Can't show click locations | Add `geoip2` library + MaxMind DB |

---

*Last updated: 2026-10-04*
