# Conventions

## Code Style

### Go
- **Formatting**: Standard `gofmt` conventions applied
- **Line length**: No strict limit enforced, typical functions 30-50 lines
- **Comments**: Package-level documentation precedes declarations
  - Example from `/Users/Mehek1/conca/agent/agent.go`: Package comment before type declarations
  - Method comments follow Go style: `// MethodName description`
- **Receiver naming**: Single letter convention (e.g., `func (a *Agent)`)
- **Imports**: Organized in blocks (standard library, then third-party, then internal)
- **Error handling**: Explicit error checking with `if err != nil` pattern
  - Example from agent.go: `if err != nil { return fmt.Errorf("context: %w", err) }`
  - Uses `fmt.Errorf` with `%w` verb for error wrapping

### Python
- **Formatting**: PEP 8 style observed in docstrings and structure
- **Module docstrings**: Present at file top with explicit purpose
  - Example from `/Users/Mehek1/HiveMind/kalshi-crypto-trader/main.py`: `"""Entry point. Polls news every 60s, runs signals, places trades."""`
  - Example from `/Users/Mehek1/HiveMind/kalshi-crypto-trader/trader.py`: Multi-line docstring explaining core logic
- **Type hints**: Used in function signatures (Python 3.10+)
  - Example: `def _majority_direction(directions: list[str]) -> Optional[str]:`
  - Example: `def analyze(text: str) -> SentimentSignal:`
- **Dataclasses**: Used for structured data (`@dataclass` from `dataclasses`)
  - Example from trader.py: `@dataclass class TradeDecision:` with 12 typed fields
  - Example from scraper.py: `@dataclass class Article:` with computed properties via `@property`

### TypeScript/React
- **Formatting**: ESLint enforced via strict config at `/Users/Mehek1/HiveMind/conca/web/eslint.config.js`
- **Unused variables**: Disabled (`@typescript-eslint/no-unused-vars: "off"`)
- **Component exports**: Warned against non-component default exports (`react-refresh/only-export-components: warn`)
- **Trailing imports**: Not enforced
- **Line length**: No explicit config, follows convention
- **TSX/React hooks**: Must follow rules of hooks (enforced via `reactHooks.configs.recommended.rules`)

## Naming Conventions

### Go
- **Types**: PascalCase
  - `BrandProfile`, `Trend`, `Post`, `Analytics`, `ScheduledPost`
- **Functions/Methods**: PascalCase (exported), camelCase (unexported)
  - Exported: `Run()`, `Plan()`, `Generate()`, `Evaluate()`, `Start()`
  - Unexported: `runAndSync()`, internal helper funcs
- **Constants**: SCREAMING_SNAKE_CASE for status values
  - `StatusDraft`, `StatusPending`, `StatusApproved`, `StatusScheduled`, `StatusPublished`
- **Variables**: camelCase
  - `brandID`, `postCount`, `finalPost`
- **Interfaces**: Commonly single method or simple name
  - `SearchTool`, `LLMTool`, `SocialClient`, `Store`, `VectorStore`, `EmbeddingTool`

### Python
- **Classes**: PascalCase
  - `KalshiClient`, `NewsScraper`, `Trader`, `Article`, `TradeDecision`, `SentimentSignal`
- **Functions**: snake_case
  - `_load_private_key()`, `_sign()`, `_parse_feed()`, `_majority_direction()`, `_position_size()`
  - Private functions prefixed with `_`
- **Constants**: SCREAMING_SNAKE_CASE
  - `KALSHI_API_KEY_ID`, `KALSHI_BASE_URL`, `MAX_PORTFOLIO_USD`, `DRY_RUN`, `SENTIMENT_THRESHOLD`
- **Module-level variables**: lowercase
  - `console`, `_analyzer`, `_client`

### TypeScript/React
- **Components**: PascalCase
  - `ProtectedRoute`, `App`, `Index`, `Brands`, `Posts`, `Analytics`
- **Functions/Hooks**: camelCase
  - `queryClient`, `defineConfig`
- **Types/Interfaces**: PascalCase (implicit from TypeScript conventions)
- **Constants**: camelCase or SCREAMING_SNAKE_CASE depending on scope
  - Local constants: `queryClient`

## Patterns

### Architectural Patterns

**Go - Agent Pattern**
- Central `Agent` struct acts as orchestrator
- Dependency injection via constructor: `NewAgent()` function
- File: `/Users/Mehek1/conca/agent/agent.go`
- Core methods follow a pipeline: `Plan() → Generate() → Evaluate() → Post()`
- Batch operations supported: `PlanBatch()` for scheduling multiple posts
- Analytics sync integrated: `SyncAnalytics()` runs post-execution

**Go - REST API Pattern**
- Chi router-based HTTP server at `/Users/Mehek1/conca/api/server.go`
- Middleware stacked: RequestID, RealIP, Logger, Recoverer, Timeout, CORS
- Routes grouped by protection level (public vs. protected routes)
- Protected routes use `AuthMiddleware`
- SPA fallback for static files: 404 routes served `index.html` for React routing

**Python - Signal Aggregation Pattern**
- Three-layer signal evaluation system at `/Users/Mehek1/HiveMind/kalshi-crypto-trader/`
- Layer 1: Keyword analysis (`signals/keyword.py`)
- Layer 2: Sentiment analysis via VADER (`signals/sentiment.py`)
- Layer 3: LLM analysis via Claude (`signals/llm.py`)
- Majority voting: 2 of 3 signals must agree for trade execution
- Files: `trader.py` orchestrates evaluation, `main.py` polls feeds

**Python - Configuration Management**
- Environment variables loaded via `dotenv` in `config.py`
- All settings centralized with defaults
- Hard caps enforced: `MAX_PORTFOLIO_USD`, `MAX_SINGLE_TRADE_USD`
- Feature flags: `DRY_RUN` mode for safe testing

**React - Query Client Pattern**
- Centralized `QueryClient` in App root at `/Users/Mehek1/HiveMind/conca/web/src/App.tsx`
- TanStack React Query for data fetching
- Route protection via `ProtectedRoute` HOC checking `localStorage.conca_token`
- Provider composition: QueryClientProvider → TooltipProvider → Toaster layers

### Code Organization Patterns

**Go - Package Structure**
- Packages by domain: `agent/`, `api/`, `config/`, `memory/`, `models/`, `scheduler/`, `tools/`
- Interface definitions near usage points
- Tool interfaces defined in `tools/` package
- Memory stores abstracted as interfaces

**Python - Modular Signals**
- Signal modules are independent: `signals/keyword.py`, `signals/sentiment.py`, `signals/llm.py`
- Each returns consistent signal type with `direction`, `score/confidence`, `triggered` fields
- Trader aggregates signals via `_majority_direction()` utility

**TypeScript/React - Component Hierarchy**
- UI components in `/Users/Mehek1/HiveMind/conca/web/src/components/ui/`
- Pages in `/src/pages/`
- Shared utilities and context at root
- Test files colocated in `/src/test/`

## Error Handling

### Go
- **Standard error wrapping**: Uses `fmt.Errorf("context: %w", err)` for error chain preservation
  - Example from `/Users/Mehek1/conca/agent/agent.go` line 47: `return fmt.Errorf("research failed: %w", err)`
  - Example from line 54: `return fmt.Errorf("planning failed: %w", err)`
- **Early return pattern**: Errors checked immediately, function returns early
- **Logging integration**: Errors logged before returning
  - Example line 85: `logger.GlobalBuffer.Warn("Feedback: %s", critique)`
  - Example line 119: `logger.GlobalBuffer.Error("Warning: Failed to create embedding: %v", err)`
- **Graceful degradation**: Some errors are warnings, not fatal
  - Vector embedding failures don't stop post execution (line 108-120)
  - Analytics fetch failures log but continue (line 318-320)
- **Default values on error**: Some operations have safe defaults
  - Example line 291: Score defaults to 7 if parsing fails

### Python
- **Try-catch with logging**: Generic broad exception handling with print fallback
  - Example from `/Users/Mehek1/HiveMind/kalshi-crypto-trader/scraper.py` lines 39-61: `try/except` with `print()` to stderr
  - Example from `main.py` lines 89-91: Catches generic `Exception`, logs to console, sleeps
- **Validation at boundaries**: Credential checks in main (lines 43-48)
- **Graceful service degradation**: RSS feed failures don't crash (line 60)
- **Hard cap enforcement**: Budget checks before actions (trader.py lines 146, 164-167)
- **Rich console output**: Error messages formatted with color/styling
  - Example: `console.print(f"[red]Error in main loop: {e}[/]")`

### TypeScript/React
- **Token-based auth validation**: ProtectedRoute checks token existence
  - Example from `/Users/Mehek1/HiveMind/conca/web/src/App.tsx` lines 19-23
  - Returns redirect to `/auth` if missing
- **No explicit error handling in example code**: Basic test file shows no error scenarios
- **Dependency setup**: Error handling deferred to testing/mocking layers

### Logging Strategy

**Go**: Centralized buffer logger
- Usage: `logger.GlobalBuffer.Info()`, `Warn()`, `Error()`
- Example from agent.go: Line 40 starts cycle, line 123 marks completion
- Structured logging of agent loop stages

**Python**: Print-based with Rich formatting
- Console output with styled markup: `console.print("[green]...[/]")`
- Desktop notifications for trade events: `_notify()` function
- Trade decisions logged to JSONL: `_log(decision)` appends JSON lines
- File: `/Users/Mehek1/HiveMind/kalshi-crypto-trader/trader.py` line 61

**TypeScript/React**: Error boundary and console (implicit)
- No explicit logging patterns in examined code
- Relies on browser DevTools console

