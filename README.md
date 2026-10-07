# 🔗 URL Shortener

A fast, simple URL shortening service built with FastAPI, React, PostgreSQL, and Redis.

## Tech Stack

- **Backend:** Python 3.12 + FastAPI (async)
- **Frontend:** React 18 + TypeScript + Vite
- **Database:** PostgreSQL 16
- **Cache:** Redis 7
- **Proxy:** Nginx
- **Deployment:** Docker Compose

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- Git

### Run

```bash
# Clone the repo
git clone <your-repo-url>
cd url-shortener

# Start all services
docker compose up --build
```

The app will be available at:
- **Frontend:** http://localhost (via nginx)
- **API docs:** http://localhost:8000/docs (Swagger UI)
- **Health check:** http://localhost:8000/health
- **URL:** http://localhost:3000/

### Local Development (without Docker)

**Backend:**
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
cp .env.example .env          # edit DATABASE_URL and REDIS_URL for local
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Requires PostgreSQL and Redis running locally.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/shorten` | Create a short URL |
| `GET` | `/api/urls` | List all URLs |
| `GET` | `/api/urls/{code}/stats` | Click analytics |
| `DELETE` | `/api/urls/{code}` | Delete a URL |
| `GET` | `/{short_code}` | Redirect to original URL |
| `GET` | `/health` | Health check |

### Shorten a URL

```bash
curl -X POST http://localhost/api/shorten \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/very/long/url"}'
```

Response:
```json
{
  "short_code": "abc123",
  "short_url": "http://localhost/abc123",
  "original_url": "https://example.com/very/long/url",
  "created_at": "2026-10-04T12:00:00",
  "click_count": 0
}
```

## URL Validation

The following URLs are rejected when shortening:

- **Self-referencing** — `localhost`, `127.0.0.1`, `::1`, and the app's own domain
- **Other shorteners** — `bit.ly`, `tinyurl.com`, `t.co`, `goo.gl`, etc.
- **Private IPs** — `10.x.x.x`, `192.168.x.x`, `172.x.x.x`
- **Duplicate detection** — if the same URL was already shortened, the existing short code is returned instead of creating a new one

## Project Structure

```
url-shortener/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app, lifespan, redirect handler
│   │   ├── routes.py         # API endpoints
│   │   ├── models.py         # SQLAlchemy models (URL, Click)
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── database.py       # Async DB session
│   │   ├── cache.py          # Redis cache + rate limiter
│   │   ├── config.py         # Settings from env
│   │   ├── validators.py     # Blocked domains, duplicate URL detection
│   │   └── utils.py          # Short code generation
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ShortenForm.tsx
│   │   │   └── URLList.tsx
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── Dockerfile
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── .gitignore
├── DEVELOPER.md
└── README.md
```

## Features

- ✅ Shorten URLs with random or custom codes
- ✅ 302 redirect with Redis caching
- ✅ Click tracking and analytics
- ✅ Rate limiting (30 req/min per IP)
- ✅ URL expiration support
- ✅ **Blocked domain validation** — prevents shortening of private IPs, other shorteners, and self-referencing URLs
- ✅ **Duplicate URL detection** — same URL returns the existing short code
- ✅ Responsive React UI with copy-to-clipboard
- ✅ Docker Compose for one-command setup

## License

MIT
