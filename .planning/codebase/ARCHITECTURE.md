# Architecture

## Pattern

The codebase consists of three main projects, each with distinct architecture patterns:

### 1. **Conca** - Content Creator Agent (Go + React)
A full-stack autonomous AI platform implementing a **layered microservice pattern** with a **Plan-Generate-Evaluate-Publish loop**.

### 2. **Kalshi Crypto Trader** (Python)
A polling-based trading bot implementing a **pipeline architecture** with **multi-layer signal aggregation**.

### 3. **HiveMind** (Git submodule)
A project workspace aggregator (contains conca and kalshi-crypto-trader as submodules).

---

## Layers

### **Conca Architecture**

#### **Layer 1: Frontend (React + TypeScript)**
- **Framework**: React 18 with Vite, TailwindCSS, shadcn/ui
- **Location**: `/Users/Mehek1/conca/web/`
- **Pages**: Dashboard (Index), Brands, Posts, Analytics, Calendar, Settings, Auth
- **Key Components**:
  - Layout (navigation, sidebar)
  - Data visualization (Recharts)
  - Forms (react-hook-form, Zod validation)
  - UI primitives (Radix UI, shadcn)
- **Client-side State**: TanStack React Query for async state
- **Authentication**: JWT token stored in localStorage

#### **Layer 2: API Server (Go + Chi)**
- **Framework**: Go 1.25.5, Chi router, JWT authentication
- **Location**: `/Users/Mehek1/conca/api/`
- **Core Files**:
  - `server.go`: HTTP server setup, route mounting, middleware (CORS, logging, timeouts)
  - `handlers.go`: HTTP request handlers for auth, brands, posts, analytics, calendar, scheduling
- **Authentication**: JWT token generation and validation
- **Database Layer**: Abstracted via `memory.Store` interface (pluggable: PostgreSQL or JSON)

#### **Layer 3: Agent Brain (Go)**
- **Location**: `/Users/Mehek1/conca/agent/agent.go`
- **Core Loop**: Research → Plan → Generate & Evaluate → Publish
- **Responsibilities**:
  - Research trends using SearchTool
  - Plan content strategy using LLM
  - Generate multiple content variations
  - Evaluate and rank by virality score
  - Schedule approved posts for publishing
- **Stateless**: Agent instance created per brand on-demand

#### **Layer 4: Job Scheduling & Queue (Go)**
- **Location**: `/Users/Mehek1/conca/scheduler/`
- **Components**:
  - `scheduler.go`: Recurring job cycle manager (15-min sync interval)
  - `queue.go`: SQLite-backed job queue with persistence
  - `worker.go`: Background job executor
- **Pattern**: Ensures every brand has scheduled jobs; pulls pending posts and publishes

#### **Layer 5: Memory & Storage (Go)**
- **Location**: `/Users/Mehek1/conca/memory/`
- **Interface-driven**:
  - `store.go`: Abstract Store interface (posts, brands, calendar, analytics, users)
  - `mongodb.go`: MongoDB implementation
  - `vector.go`: Vector embeddings for semantic memory (RAG)
- **Data Persistence**: Flexible (PostgreSQL or local JSON fallback)

#### **Layer 6: Tools & Integrations (Go)**
- **Location**: `/Users/Mehek1/conca/tools/`
- **Modules**:
  - `llm.go`: Gemini API client (text generation)
  - `search.go`: DuckDuckGo, NewsAPI, NewsData.io search aggregation
  - `embeddings.go`: Semantic embedding generation
  - `twitter.go`: X (Twitter) API integration
  - `linkedin.go`: LinkedIn posting
  - `analytics.go`: Engagement metrics aggregation
  - `social.go`: Unified social media client interface
  - `logger/logger.go`: Global buffer for agent logs

#### **Layer 7: Data Models (Go)**
- **Location**: `/Users/Mehek1/conca/models/types.go`
- **Core Types**:
  - `BrandProfile`: AI personality (name, industry, voice, topics)
  - `Post`: Generated content with analytics
  - `ScheduledPost`: Calendar entry with approval workflow
  - `Trend`: Research result
  - `Analytics`: Engagement metrics (views, likes, shares, comments)
  - `PostStatus`: Enum (draft, pending_review, approved, scheduled, published, failed)

#### **Layer 8: Configuration (Go)**
- **Location**: `/Users/Mehek1/conca/config/`
- **Files**: JSON brand templates (e.g., `tech_startup.json`)

---

### **Kalshi Crypto Trader Architecture**

#### **Layer 1: Entry Point (Python)**
- **File**: `/Users/Mehek1/kalshi-crypto-trader/main.py`
- **Responsibility**: Polling loop (60-sec interval), news scraping, signal evaluation, trade execution
- **Pattern**: Continuous loop with graceful shutdown

#### **Layer 2: Data Scraping (Python)**
- **File**: `/Users/Mehek1/kalshi-crypto-trader/scraper.py`
- **Responsibility**: Fetch crypto news from multiple sources
- **Output**: Article objects with title, source, timestamp

#### **Layer 3: Multi-Layer Signal Pipeline (Python)**
- **Location**: `/Users/Mehek1/kalshi-crypto-trader/signals/`
- **Three Independent Signals**:
  1. **Keyword Signal** (`keyword.py`): Pattern matching for crypto keywords
  2. **Sentiment Signal** (`sentiment.py`): Compound sentiment analysis
  3. **LLM Signal** (`llm.py`): Claude API for directional confidence and reasoning
- **Aggregation**: All three signals merged to make buy/sell decisions

#### **Layer 4: Core Trading Logic (Python)**
- **File**: `/Users/Mehek1/kalshi-crypto-trader/trader.py`
- **Responsibilities**:
  - Enforce $100 hard cap per position
  - Position sizing (conservative)
  - Market matching (article ticker → Kalshi market)
  - Trade execution logging (JSONL format)
  - macOS notifications

#### **Layer 5: Client & API (Python)**
- **File**: `/Users/Mehek1/kalshi-crypto-trader/kalshi_client.py`
- **Responsibility**: REST client for Kalshi API (markets, balance, trading)

#### **Layer 6: Configuration (Python)**
- **File**: `/Users/Mehek1/kalshi-crypto-trader/config.py`
- **Responsibility**: Centralized env-based config (API keys, portfolio limits, poll intervals)

---

## Data Flow

### **Conca Content Creation Loop**

```
User (Web UI)
  ↓
[Frontend] React SPA
  ↓ (HTTP/JWT)
[API Server] Go Chi Router
  ↓
[Handlers] Brand/Post/Calendar/Analytics endpoints
  ↓
[Store Interface] Abstract persistence
  ↓
[Database] PostgreSQL or JSON
  ↓
[Queue] SQLite job queue
  ↓
[Worker] Background executor
  ↓
[Agent Brain] Plan → Generate → Evaluate
  ├→ SearchTool: Query trends
  ├→ LLMTool: Generate variations
  ├→ VectorStore: Semantic evaluation
  └→ SocialClient: Publish to X/LinkedIn
  ↓
[Memory] Vector embeddings (semantic RAG)
  ↓
Published Post + Analytics
```

### **Kalshi Trading Loop**

```
News Sources
  ↓
[Scraper] Fetch articles every 60s
  ↓
[Article] Parsed title, source, timestamp
  ↓
[Signal Pipeline] Parallel evaluation:
  ├→ KeywordSignal: Pattern match crypto
  ├→ SentimentSignal: Compound score
  └→ LLMSignal: Claude confidence
  ↓
[Trade Decision] Aggregate signals → direction & size
  ↓
[Trader] Size position, enforce cap
  ↓
[KalshiClient] Place trade via REST API
  ↓
[Logging] JSONL trades file + macOS notification
```

---

## Key Abstractions

### **Conca**

| Abstraction | Location | Purpose |
|---|---|---|
| `Store` | `memory/store.go` | Database abstraction (posts, brands, users, calendar) |
| `SearchTool` | `tools/search.go` | News/trend source interface |
| `LLMTool` | `tools/llm.go` | Text generation interface |
| `SocialClient` | `tools/social.go` | Social media posting interface |
| `EmbeddingTool` | `tools/embeddings.go` | Semantic embedding interface |
| `AnalyticsFetcher` | `tools/analytics.go` | Engagement metrics interface |
| `Queue` | `scheduler/queue.go` | Job queue persistence interface |
| `VectorStore` | `memory/vector.go` | Semantic memory (RAG) interface |
| `Agent` | `agent/agent.go` | Autonomous content brain (stateless, per-brand) |

### **Kalshi**

| Abstraction | Location | Purpose |
|---|---|---|
| `KalshiClient` | `kalshi_client.py` | REST API client |
| `NewsScraper` | `scraper.py` | Article fetching |
| `Trader` | `trader.py` | Decision aggregation & position sizing |
| `Signal` | `signals/*.py` | Individual signal evaluators (keyword, sentiment, LLM) |

---

## Entry Points

### **Conca**

1. **Backend Server**
   - **File**: `/Users/Mehek1/conca/cmd/server/main.go`
   - **Command**: `go run cmd/server/main.go`
   - **Port**: Default 8000
   - **Starts**:
     - API server (HTTP)
     - Job scheduler (background)
     - Worker pool (background)

2. **Frontend**
   - **File**: `/Users/Mehek1/conca/web/src/main.tsx`
   - **Build**: `npm run build` → `/dist`
   - **URL**: `http://localhost:8080` (served by backend)

### **Kalshi Crypto Trader**

1. **Main Entry**
   - **File**: `/Users/Mehek1/kalshi-crypto-trader/main.py`
   - **Command**: `python main.py`
   - **Starts**:
     - News polling loop (60-sec interval)
     - Continuous signal evaluation
     - Trade execution on signals

---

## Cross-Cutting Concerns

### **Logging**
- **Conca**: Global buffer in `tools/logger/logger.go` streamed to dashboard
- **Kalshi**: Rich console output + JSONL trade logs

### **Authentication & Authorization**
- **Conca**: JWT tokens (HS256) in Authorization header; `auth.go` middleware validates
- **Kalshi**: API key authentication via environment variables

### **Error Handling**
- **Conca**: Structured error responses with HTTP status codes
- **Kalshi**: Try-catch with graceful recovery; logs errors and continues polling

### **Configuration**
- **Conca**: Environment variables (`.env` file)
- **Kalshi**: Environment variables via `config.py`

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, TailwindCSS, shadcn/ui, Recharts, React Router, React Query |
| **Backend** | Go 1.25.5, Chi router, JWT, PostgreSQL/JSON, SQLite queue |
| **LLM** | Google Gemini API, Claude API (Kalshi) |
| **Search** | DuckDuckGo, NewsAPI, NewsData.io |
| **Social APIs** | X (Twitter), LinkedIn |
| **Database** | PostgreSQL, MongoDB, SQLite (queue), JSON (local) |
| **Python Stack** | Python 3.x, Rich (logging), dataclasses |
| **Testing** | Vitest (frontend), Go testing (backend) |

