# Integrations

## External APIs

### AI & Language Models
- **Google Gemini API** — LLM for content generation and embeddings
  - Endpoint: `https://generativelanguage.googleapis.com/v1beta/`
  - Models: `gemini-1.5-flash`, `text-embedding-004`
  - Used in: `/Users/Mehek1/conca/tools/llm.go`, `/Users/Mehek1/conca/tools/embeddings.go`
  - Auth: API key via `GEMINI_API_KEY`

- **Anthropic Claude API** — LLM for signal analysis and tone detection
  - Client: `anthropic>=0.25.0` in Python projects
  - Used in: Kalshi trader signals, comment-tone-analyzer
  - Auth: API key via `ANTHROPIC_API_KEY`

- **OpenAI API** — ChatGPT integration for data analysis
  - Client: `openai==1.12.0`
  - Used in: Streamlit dashboard project

### News & Research
- **NewsAPI.org** — News aggregation and trending topic research
  - Endpoint: `https://newsapi.org/v2/`
  - Implementation: `/Users/Mehek1/conca/tools/search.go` (NewsAPISearch)
  - Auth: API key via `NEWSAPI_KEY`
  - Fallback: DuckDuckGo search when key unavailable

- **DuckDuckGo Search** — Secondary search tool for research
  - Implementation: `/Users/Mehek1/conca/tools/search.go` (DuckDuckGoSearch)
  - No authentication required

- **RSS Feeds** — Crypto news feeds for trading signals
  - Sources (in `/Users/Mehek1/kalshi-crypto-trader/config.py`):
    - CoinDesk: `https://www.coindesk.com/arc/outboundfeeds/rss/`
    - Cointelegraph: `https://cointelegraph.com/rss`
    - Decrypt: `https://decrypt.co/feed`
    - TheBlock: `https://www.theblock.co/rss.xml`
    - Bitcoin Magazine: `https://bitcoinmagazine.com/feed`
    - CryptoSlate: `https://cryptoslate.com/feed/`
    - AMBCrypto: `https://ambcrypto.com/feed/`

### Social Media

#### LinkedIn
- **LinkedIn API v2** — Post sharing and engagement metrics
  - Endpoint: `https://api.linkedin.com/v2/`
  - Operations: POST to `ugcPosts`, retrieve analytics
  - Implementation: `/Users/Mehek1/conca/tools/linkedin.go`
  - Auth: Bearer token (AccessToken), User URN required
  - Payload: UGC (User-Generated Content) posts with visibility controls

#### Twitter/X
- **X API v2** — Tweet posting and analytics
  - Endpoint: `https://api.twitter.com/2/`
  - Operations: POST `/tweets`, retrieve metrics
  - Implementation: `/Users/Mehek1/conca/tools/twitter.go`
  - Auth: OAuth 1.0a (API Key, Secret, Access Token, Token Secret)
  - Constraints: View counts only available on higher API tiers

#### Instagram, TikTok, Threads
- **Stubs present** in codebase (not yet integrated)
  - Placeholder implementation exists
  - Ready for credential and API setup

### Flight & Travel
- **Amadeus Flight API** — Real-time flight pricing
  - Client: `amadeus==8.1.0`
  - Used in: `/Users/Mehek1/Desktop/flight tracker/`
  - Features: Price checking, availability
  - Config: `/Users/Mehek1/Desktop/flight tracker/config.yaml`

- **Web Scraping (Fallback)** — Manual flight price scraping
  - Sources: Google Flights, Kayak
  - Tools: Selenium, BeautifulSoup4
  - Implementation: `/Users/Mehek1/Desktop/flight tracker/main.py`

### Trading & Financial
- **Kalshi Exchange API** — Crypto prediction market trading
  - Base URL: `https://trading-api.kalshi.com/trade-api/v2`
  - Client: Custom Python client at `/Users/Mehek1/kalshi-crypto-trader/kalshi_client.py`
  - Auth: RSA private key signing + API Key ID
  - Operations: Place trades, retrieve markets, check balance
  - Implementation: `/Users/Mehek1/kalshi-crypto-trader/trader.py`, `/Users/Mehek1/kalshi-crypto-trader/main.py`

### Communication & Scheduling
- **Google Calendar API** — Meeting scheduling
  - Client: `google-api-python-client>=2.120.0`
  - Auth: OAuth via `google-auth-oauthlib`
  - Used in: `/Users/Mehek1/Desktop/coffee chat scheduler/`
  - Files: `credentials.json`, `token.json` (OAuth tokens)

- **Slack Bolt** — Slack integration for notifications
  - Client: `slack-bolt>=1.18.0`
  - Used in: Coffee chat scheduler bot
  - Webhook support for notifications

### Email
- **SMTP** — Email notifications
  - Client: `smtplib2==0.96.0`, standard `smtplib`
  - Used in: Flight tracker price alerts, system notifications

## Databases

### MongoDB
- **Primary vector/semantic memory store** — Stores embeddings and RAG data
  - Connection: `mongodb://localhost:27017` (default local)
  - Collections: `posts`, `brands`, `scheduled_posts`, `users`, `vector_embeddings`
  - Implementation: `/Users/Mehek1/conca/memory/mongodb.go`
  - Driver: `go.mongodb.org/mongo-driver/v2`
  - Features: BSON encoding, automatic indexing

### SQLite
- **Fallback local storage** — JSON-based post and brand storage
  - Driver: `modernc.org/sqlite` (pure Go implementation)
  - Used when PostgreSQL unavailable
  - Implementation: `/Users/Mehek1/conca/memory/store.go`
  - Schema: Posts, brands, scheduled posts, users

### PostgreSQL
- **Optional production database** — Configurable via `DATABASE_URL`
  - Driver: `github.com/jackc/pgx/v5` (transitive dependency)
  - Used when `DATABASE_URL` environment variable is set
  - Supports full schema with migrations via Alembic
  - Not configured by default (falls back to MongoDB/SQLite)

### In-Memory & Cache
- **Redis** ≥5.0.0 — Task queue backend
  - Used with Celery for async job distribution
  - Connection configured via environment variables
  - Used in: Python async projects (coffee chat, flight tracker)

## Auth Providers

### JWT Authentication
- **Token-based auth** — Stateless session management
  - Secret: `JWT_SECRET` environment variable
  - Implementation: `/Users/Mehek1/conca/api/middleware.go`
  - Middleware: Context-based user ID extraction
  - Token generation: `/Users/Mehek1/conca/api/handlers.go` (login endpoint)

### OAuth 2.0
- **Google OAuth** — Gmail and Calendar integration
  - Scope: Calendar read/write
  - Files: `credentials.json`, `token.json` (in `/Users/Mehek1/Desktop/coffee chat scheduler/`)
  - Client: `google-auth-oauthlib>=1.2.0`
  - Used by: Calendar scheduler, event creation

- **LinkedIn OAuth** — Token generation for API access
  - AccessToken required in brand config
  - PersonURN required for posting

- **Twitter/X OAuth** — API credential authentication
  - OAuth 1.0a used (legacy, still valid for v2 API)
  - API Key, Secret, Access Token, Token Secret required

## Webhooks & Real-Time

### Slack Webhooks
- Incoming webhooks for event notifications
- Integrated via Slack Bolt framework

### Google Calendar Push Notifications
- Calendar event change notifications
- Webhook endpoints in FastAPI

## Vector Search & Embeddings

### Gemini Embeddings API
- **Semantic memory for content strategy**
  - Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent`
  - Implementation: `/Users/Mehek1/conca/tools/embeddings.go`
  - Used for: Semantic similarity in content library
  - Storage: MongoDB vector collections

## Other Integrations

### Environment & Config Management
- **python-dotenv** — .env file parsing across Python projects
- **.env files**:
  - `/Users/Mehek1/.env` (root)
  - `/Users/Mehek1/kalshi-crypto-trader/.env`
  - `/Users/Mehek1/Desktop/coffee chat scheduler/.env`

### Data Export & Logging
- **Trades JSONL** — Trading history in `/Users/Mehek1/kalshi-crypto-trader/trades.jsonl`
- **Trader Logs** — Activity log in `/Users/Mehek1/kalshi-crypto-trader/trader.log`

### Browser Automation
- **Selenium WebDriver** — Headless browser for flight tracking
  - Used in: `/Users/Mehek1/Desktop/flight tracker/main.py`
  - Targets: Google Flights, Kayak

### Sentiment Analysis
- **VADER (Valence Aware Dictionary and sEntiment Reasoner)** — Rule-based sentiment
  - Package: `vaderSentiment>=3.3.2`
  - Used in: Kalshi crypto trader signal layer

- **Hugging Face Transformers** — Neural sentiment classification
  - Models: BERT-based sentiment models
  - Used in: Comment tone analyzer

### Monitoring & Analytics
- **Streamlit** — Interactive dashboard for data analysis
  - Configuration: `/Users/Mehek1/.streamlit/credentials.toml`
  - Used in: Analytics dashboards, model training visualization

### Development & Testing
- **Vitest** — Unit testing framework
- **ESLint** — Code linting
- **Jest DOM** — DOM testing assertions
- **jsdom** — DOM simulation for tests
