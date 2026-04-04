# Directory Structure

## Top-Level Layout

```
/Users/Mehek1/
├── conca/                          # Content Creator Agent (Go + React full-stack)
├── kalshi-crypto-trader/           # Crypto trading bot (Python)
├── HiveMind/                        # Project workspace aggregator (submodules)
├── .planning/                       # Planning & documentation directory
├── .claude/                         # Claude Code configuration
├── .claude-flow/                    # Claude Flow configuration
├── .vscode/                         # VS Code settings
├── Desktop/                         # User desktop files
├── Documents/                       # User documents
├── Downloads/                       # User downloads
├── PycharmProjects/                 # PyCharm projects
├── Sites/                          # Web root
├── Tracker/                        # Time tracking tool
├── go/                             # Go package cache (go mod)
└── [other system directories]      # macOS system directories
```

---

## Key Directories

### **`/Users/Mehek1/conca/`** - Content Creator Agent

The primary full-stack application implementing autonomous AI content creation.

```
conca/
├── .git/                           # Git repository metadata
├── .gitignore                      # Git ignore rules
├── README.md                       # Project documentation
├── go.mod                          # Go module definition (v1.25.5)
├── go.sum                          # Dependency lock file
├── main                            # Compiled binary (executable)
├── server                          # Compiled binary (server)
├── logo.png                        # Brand logo
├── logo_black.png                  # Logo variant
│
├── cmd/                            # Command-line entry points
│   └── server/
│       └── main.go                 # Backend server entry point
│
├── api/                            # REST API layer (Go)
│   ├── server.go                   # HTTP server setup, route mounting, middleware
│   ├── handlers.go                 # Request handlers for brands, posts, calendar, analytics
│   ├── auth.go                     # JWT token generation/validation
│   └── [other API handlers]
│
├── agent/                          # Autonomous brain (Plan-Generate-Evaluate-Publish)
│   └── agent.go                    # Core agent logic with full workflow
│
├── models/                         # Data type definitions
│   └── types.go                    # BrandProfile, Post, ScheduledPost, Trend, Analytics, User, etc.
│
├── memory/                         # Persistence & semantic memory
│   ├── store.go                    # Store interface (abstract database)
│   ├── mongodb.go                  # MongoDB implementation
│   ├── vector.go                   # Vector embeddings for RAG
│   └── [other store implementations]
│
├── scheduler/                      # Background job scheduling
│   ├── scheduler.go                # Recurring job cycle manager
│   ├── queue.go                    # SQLite-backed job queue
│   ├── worker.go                   # Background job executor
│   └── [other scheduling logic]
│
├── tools/                          # External integrations & utilities
│   ├── llm.go                      # Google Gemini API client
│   ├── search.go                   # Search tool abstraction + implementations
│   ├── embeddings.go               # Semantic embedding generation
│   ├── twitter.go                  # X (Twitter) API integration
│   ├── linkedin.go                 # LinkedIn posting
│   ├── social.go                   # Unified social media interface
│   ├── analytics.go                # Engagement metrics aggregation
│   ├── logger/
│   │   └── logger.go               # Global logging buffer for dashboard
│   └── [other tools]
│
├── config/                         # Configuration templates
│   └── tech_startup.json           # Example brand profile template
│
├── web/                            # Frontend (React + TypeScript + Vite)
│   ├── .gitignore                  # Git ignore rules
│   ├── README.md                   # Frontend documentation
│   ├── package.json                # NPM dependencies
│   ├── package-lock.json           # Dependency lock
│   ├── bun.lockb                   # Bun package manager lock (alternative to npm)
│   ├── tsconfig.json               # TypeScript config
│   ├── vite.config.ts              # Vite bundler config
│   ├── tailwind.config.ts          # TailwindCSS config
│   ├── postcss.config.js           # PostCSS config (for Tailwind)
│   ├── eslint.config.js            # ESLint rules
│   ├── vitest.config.ts            # Vitest testing config
│   ├── components.json             # shadcn/ui component config
│   ├── index.html                  # HTML entry point
│   │
│   ├── public/                     # Static assets served as-is
│   │
│   ├── src/                        # TypeScript/React source
│   │   ├── main.tsx                # React app entry point
│   │   ├── App.tsx                 # Router setup, protected routes
│   │   ├── App.css                 # Global styles
│   │   ├── index.css               # Root stylesheet
│   │   ├── vite-env.d.ts           # Vite environment types
│   │   │
│   │   ├── pages/                  # Page components (routed)
│   │   │   ├── Index.tsx           # Dashboard (main page)
│   │   │   ├── Brands.tsx          # Brand management & creation
│   │   │   ├── Posts.tsx           # Post history & editing
│   │   │   ├── Calendar.tsx        # Content calendar & scheduling
│   │   │   ├── Analytics.tsx       # Engagement metrics & performance
│   │   │   ├── Settings.tsx        # User preferences
│   │   │   ├── Auth.tsx            # Login/register
│   │   │   └── NotFound.tsx        # 404 page
│   │   │
│   │   ├── components/             # Reusable React components
│   │   │   ├── Layout.tsx          # Main layout (sidebar, nav)
│   │   │   ├── NavLink.tsx         # Navigation link component
│   │   │   ├── StatCard.tsx        # Stat card display
│   │   │   ├── StatusBadge.tsx     # Status indicator badge
│   │   │   └── ui/                 # shadcn/ui primitive components (51 files)
│   │   │       ├── button.tsx
│   │   │       ├── card.tsx
│   │   │       ├── input.tsx
│   │   │       ├── dialog.tsx
│   │   │       ├── table.tsx
│   │   │       ├── tabs.tsx
│   │   │       ├── chart.tsx
│   │   │       └── [other UI primitives]
│   │   │
│   │   ├── hooks/                  # Custom React hooks
│   │   │
│   │   ├── lib/                    # Utility functions & helpers
│   │   │
│   │   ├── assets/                 # Images, fonts, icons
│   │   │
│   │   └── test/                   # Test files
│   │       ├── example.test.ts     # Example test
│   │       └── setup.ts            # Test setup
│   │
│   ├── dist/                       # Build output (generated)
│   │   └── assets/                 # Bundled JS/CSS
│   │
│   └── node_modules/               # NPM dependencies (large, ~350 packages)
│
└── [build artifacts and data]
```

---

### **`/Users/Mehek1/kalshi-crypto-trader/`** - Crypto Trading Bot

Autonomous trading system for Kalshi crypto markets using multi-layer signals.

```
kalshi-crypto-trader/
├── .env                            # Environment variables (API keys, config)
├── .env.example                    # Example config template
├── .DS_Store                       # macOS metadata
├── main.py                         # Entry point: polling loop + orchestration
├── config.py                       # Centralized configuration (env-based)
├── kalshi_client.py                # REST API client for Kalshi
├── scraper.py                      # News article fetching & parsing
├── trader.py                       # Trade decision aggregation & execution
│
├── signals/                        # Multi-layer signal pipeline
│   ├── __init__.py                 # Package marker
│   ├── keyword.py                  # Keyword pattern matching signal
│   ├── sentiment.py                # Sentiment analysis signal
│   ├── llm.py                      # Claude LLM-based signal with reasoning
│   └── __pycache__/                # Python cache (auto-generated)
│
├── kalshi_private_key.pem          # Kalshi authentication (private key)
├── requirements.txt                # Python dependencies
├── trader.log                      # Execution log (9.8 MB)
├── trades.jsonl                    # Executed trades ledger (61 MB)
├── __pycache__/                    # Python cache
└── [temporary files]
```

---

### **`/Users/Mehek1/HiveMind/`** - Workspace Aggregator

Top-level project orchestrator using Git submodules.

```
HiveMind/
├── .git/                           # Git repository with submodules
├── .gitignore                      # Ignore rules
├── README.md                       # Workspace documentation
│
├── conca/                          # Submodule → /Users/Mehek1/conca
├── kalshi-crypto-trader/           # Submodule → /Users/Mehek1/kalshi-crypto-trader
│
└── claude-config/                  # Claude Code workspace config
```

---

### **`/Users/Mehek1/.planning/`** - Planning & Docs

Architecture and planning documentation.

```
.planning/
└── codebase/
    ├── ARCHITECTURE.md             # System architecture (this file structure describes)
    └── STRUCTURE.md                # Directory layout & file organization (current)
```

---

## Naming Conventions

### **Go Files** (`conca/`)
- **Lowercase, underscore-separated**: `file_name.go`
- **Package structure**: Single package per directory (e.g., `api/`, `memory/`, `tools/`)
- **Interface names**: `FooTool`, `FooInterface` (PascalCase)
- **Implementation names**: `GeminiClient`, `MongoStore` (PascalCase)
- **Functions**: `NewFoo()` constructor pattern, `FuncName()` (PascalCase)

### **TypeScript Files** (`conca/web/src/`)
- **Components**: PascalCase (`Index.tsx`, `Brands.tsx`, `Layout.tsx`)
- **Utilities/Hooks**: camelCase (`useAuth.ts`, `utils.ts`)
- **UI Components**: PascalCase with `ui/` prefix (`ui/button.tsx`, `ui/card.tsx`)
- **Pages**: PascalCase (`pages/Index.tsx`, `pages/Auth.tsx`)

### **Python Files** (`kalshi-crypto-trader/`)
- **Lowercase, underscore-separated**: `file_name.py`
- **Modules**: `keyword.py`, `sentiment.py`, `llm.py` (single responsibility)
- **Functions**: `snake_case` (e.g., `fetch_new()`, `evaluate()`)
- **Classes**: PascalCase (e.g., `KalshiClient`, `NewsScraper`, `Trader`)

### **Configuration Files**
- **Go**: `.env` (environment variables), JSON templates in `config/`
- **React/Web**: `.env`, `tsconfig.json`, `tailwind.config.ts`, `vite.config.ts`
- **Python**: `.env`, `config.py`, `requirements.txt`

---

## Important Files

| File | Location | Purpose | Lines |
|---|---|---|---|
| **Server Entry** | `conca/cmd/server/main.go` | Go backend bootstrap | 129 |
| **Agent Brain** | `conca/agent/agent.go` | Core Plan-Generate-Evaluate loop | 363 |
| **API Handlers** | `conca/api/handlers.go` | HTTP request handlers | 349 |
| **Data Models** | `conca/models/types.go` | Core domain types | 102 |
| **Store Interface** | `conca/memory/store.go` | Database abstraction | ~80 |
| **Scheduler** | `conca/scheduler/scheduler.go` | Job management | 104 |
| **LLM Tool** | `conca/tools/llm.go` | Gemini API client | 172 |
| **Search Tool** | `conca/tools/search.go` | News/trend search | 233 |
| **Web Router** | `conca/web/src/App.tsx` | React routing & auth | ~40 |
| **Web Dashboard** | `conca/web/src/pages/Index.tsx` | Main dashboard page | ~300 |
| **Trader Entry** | `kalshi-crypto-trader/main.py` | Trading bot main loop | 95 |
| **Trader Logic** | `kalshi-crypto-trader/trader.py` | Trade aggregation & execution | 197 |
| **Kalshi Client** | `kalshi-crypto-trader/kalshi_client.py` | API client | 141 |
| **LLM Signal** | `kalshi-crypto-trader/signals/llm.py` | Claude-based signal | 87 |

---

## Build Artifacts & Generated Files

| Location | Generated By | Purpose |
|---|---|---|
| `conca/main` | `go build` | Compiled backend binary |
| `conca/server` | `go build` | Compiled server binary |
| `conca/web/dist/` | `npm run build` or `bun build` | Bundled frontend (HTML, JS, CSS) |
| `conca/web/dist/assets/` | Vite/Rollup | Bundled JavaScript & CSS modules |
| `kalshi-crypto-trader/__pycache__/` | Python interpreter | Bytecode cache |
| `kalshi-crypto-trader/trader.log` | Runtime execution | Audit log (appended) |
| `kalshi-crypto-trader/trades.jsonl` | Runtime execution | Executed trades ledger (appended) |

---

## Database & Data Files

| Path | Type | Purpose | Size |
|---|---|---|---|
| `.env` (conca) | Configuration | API keys, JWT secret, database URL | ~500B |
| `.env.example` | Template | Example configuration | ~400B |
| `conca/config/*.json` | JSON | Brand profile templates | ~5KB |
| **PostgreSQL** (if configured) | Database | Primary data store (posts, brands, users) | Variable |
| **SQLite** (local queue) | Database | Job queue persistence | ~1-10MB |
| **MongoDB** (if configured) | Database | Alternative document store | Variable |
| `kalshi-crypto-trader/trader.log` | Text log | Execution audit trail | 9.8 MB |
| `kalshi-crypto-trader/trades.jsonl` | JSONL | Structured trade records (one per line) | 61 MB |

---

## Development Workflow Directories

| Path | Purpose |
|---|---|
| `conca/web/src/test/` | Frontend test files (Vitest) |
| `conca/web/node_modules/` | NPM dependencies (~350 packages) |
| `conca/web/dist/` | Built frontend output |
| `.claude/` | Claude Code workspace files |
| `.vscode/` | VS Code settings |
| `Desktop/` | Development shortcuts & projects |

---

## Key Configuration Files

### Go (conca)
- **`go.mod`**: Defines module `content-creator-agent`, requires 6 external packages
- **`go.sum`**: Lock file for reproducible builds
- **`.env`**: Runtime configuration (GEMINI_API_KEY, JWT_SECRET, DATABASE_URL)

### React (conca/web)
- **`package.json`**: 40+ dependencies (React, Vite, TypeScript, TailwindCSS, etc.)
- **`tsconfig.json`**: TypeScript compiler settings
- **`vite.config.ts`**: Vite bundler & build config
- **`tailwind.config.ts`**: TailwindCSS customization
- **`components.json`**: shadcn/ui component registry

### Python (kalshi-crypto-trader)
- **`requirements.txt`**: Dependencies (anthropic, requests, rich, etc.)
- **`config.py`**: Centralized config from env variables
- **`.env`**: Runtime secrets (KALSHI_API_KEY_ID, ANTHROPIC_API_KEY, etc.)

