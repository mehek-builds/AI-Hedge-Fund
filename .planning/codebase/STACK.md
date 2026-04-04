# Tech Stack

## Languages
- **Go** 1.25.5 — Primary backend language for the `conca` content creator agent
- **TypeScript** — Frontend and web configuration
- **Python** 3.x — Machine learning and data science projects (flight tracker, crypto trader, coffee chat scheduler, comment analyzer)
- **JavaScript/Node.js** — Build tooling and frontend dependencies

## Runtime
- **Go runtime** — Server and daemon processes
- **Node.js 18+** — Frontend build and development
- **Python runtime** — Async task execution and ML inference

## Frameworks

### Backend (Go)
- **Chi v5** (`github.com/go-chi/chi/v5`) — HTTP router and middleware
- **JWT Authentication** (`github.com/golang-jwt/jwt/v5`) — Token-based auth
- **GoQuery** (`github.com/PuerkitoBio/goquery`) — HTML parsing and web scraping
- **Environment Management** (`github.com/joho/godotenv`) — .env file loading

### Frontend (React)
- **React** 18.3.1 — UI framework
- **Vite** 5.4.19 — Build tooling and dev server
- **TailwindCSS** 3.4.17 — Utility-first CSS
- **shadcn/ui** — Radix UI component library with TailwindCSS
- **React Hook Form** 7.61.1 — Form state management
- **React Query** (@tanstack/react-query) 5.83.0 — Server state management
- **React Router** 6.30.1 — Client-side routing
- **Recharts** 2.15.4 — Data visualization
- **Zod** 3.25.76 — Schema validation

### Python (Async/Task Processing)
- **FastAPI** ≥0.110.0 — Modern async web framework
- **Uvicorn** ≥0.29.0 — ASGI server
- **Celery** ≥5.3.0 — Distributed task queue
- **APScheduler** 3.10.4 — Advanced scheduling
- **SQLAlchemy** 2.0+ — ORM and database abstraction
- **Alembic** 1.13+ — Database migrations
- **Pydantic** ≥2.0.0 — Data validation

### Data & ML (Python)
- **Pandas** 2.1.4+ — Data manipulation and analysis
- **NumPy** (implicit via Pandas/Torch) — Numerical computing
- **Torch** ≥2.0.0 — Deep learning framework
- **Transformers** ≥4.40.0 — Hugging Face transformer models
- **Streamlit** 1.31.0 — Interactive dashboards
- **Plotly** 5.18.0 — Interactive visualization

### Utilities & Integrations
- **httpx** ≥0.27.0 — Async HTTP client
- **requests** 2.31.0 — HTTP client
- **BeautifulSoup4** ≥4.12.0 — HTML/XML parsing
- **Selenium** 4.16.0 — Browser automation
- **Cryptography** ≥42.0.0 — Encryption and key management
- **python-dotenv** ≥1.0.0 — Environment variable management
- **PyYAML** 6.0.1 — YAML parsing
- **Rich** 13.7.0+ — Terminal output formatting
- **VADER Sentiment** 3.3.2 — Sentiment analysis
- **Anthropic** ≥0.25.0 — Claude API client
- **OpenAI** 1.12.0 — OpenAI API client
- **FeedParser** 6.0.11 — RSS/Atom feed parsing

## Key Dependencies

### Database Drivers
- **MongoDB** — `go.mongodb.org/mongo-driver/v2` for Go; SQLAlchemy support for Python
- **SQLite** — `modernc.org/sqlite` for pure Go SQLite support
- **PostgreSQL** — `github.com/jackc/pgx/v5` (transitive via SQLAlchemy)

### Cryptography & Security
- **Golang.org/x/crypto** v0.44.0 — Cryptographic operations
- **RSA Key Support** — For signing (Kalshi trading auth)
- **JWT** — Token-based authentication

### UUID & Utilities
- **Google UUID** (`github.com/google/uuid`) — UUID generation

### Frontend UI Components
- Radix UI components (27 different component types)
- Embla Carousel — Image carousel
- Sonner — Toast notifications
- date-fns — Date manipulation
- cmdk — Command palette

## Configuration

### Environment Variables (Primary)
- `GEMINI_API_KEY` — Google Gemini LLM API key
- `NEWSAPI_KEY` — NewsAPI.org key for research
- `KALSHI_API_KEY_ID` — Kalshi trading platform API key
- `KALSHI_PRIVATE_KEY_PATH` — Path to RSA private key for Kalshi
- `ANTHROPIC_API_KEY` — Claude API key for sentiment analysis
- `JWT_SECRET` — Secret for JWT token signing
- `DATABASE_URL` — PostgreSQL connection string (optional, defaults to local JSON/SQLite)

### Configuration Files
- **`/Users/Mehek1/conca/config/`** — Brand profile JSON configs
- **`/Users/Mehek1/Desktop/flight tracker/config.yaml`** — Flight tracking configuration
- **`/Users/Mehek1/.streamlit/credentials.toml`** — Streamlit configuration
- **`/Users/Mehek1/.env`** — Root environment file
- **`/Users/Mehek1/kalshi-crypto-trader/.env`** — Kalshi trader environment
- **`/Users/Mehek1/kalshi-crypto-trader/config.py`** — Python trading configuration

### Build Configuration
- **`/Users/Mehek1/conca/web/vite.config.ts`** — Vite bundler configuration
- **`/Users/Mehek1/conca/web/tailwind.config.ts`** — TailwindCSS configuration
- **`/Users/Mehek1/conca/web/tsconfig.json`** — TypeScript compiler configuration
- **`/Users/Mehek1/conca/web/components.json`** — shadcn/ui component configuration

### Project Structure
- **`/Users/Mehek1/conca/`** — Main content creator platform (Go + React)
  - `/cmd/` — CLI entry points
  - `/api/` — HTTP API handlers
  - `/agent/` — Autonomous agent logic
  - `/tools/` — External integrations (LLM, social, search)
  - `/memory/` — Persistence layer (MongoDB, vector store)
  - `/scheduler/` — Job scheduling
  - `/web/` — React frontend (Vite + TypeScript)
  - `/models/` — Data models

- **`/Users/Mehek1/kalshi-crypto-trader/`** — Crypto trading bot (Python)
  - `main.py`, `trader.py`, `kalshi_client.py` — Core trading logic
  - `scraper.py` — News aggregation
  - `signals/` — Signal generation

- **`/Users/Mehek1/Desktop/flight tracker/`** — Flight price monitoring (Python + Flask)
- **`/Users/Mehek1/Desktop/coffee chat scheduler/`** — Meeting scheduling bot (Python + FastAPI)
- **`/Users/Mehek1/Downloads/comment-tone-analyzer/`** — Sentiment analysis tool (Python + Transformers)

## Package Managers
- **Go Modules** — `go.mod` and `go.sum`
- **npm** — Node.js dependency management
- **pip** — Python package management
