# Testing

## Framework

### TypeScript/React
- **Primary framework**: Vitest
  - Configuration: `/Users/Mehek1/HiveMind/conca/web/vitest.config.ts`
  - Environment: jsdom (browser DOM simulation)
  - Globals enabled (no imports needed for describe/it/expect)
  - Setup files: `./src/test/setup.ts`
- **Test file pattern**: `**/*.{test,spec}.{ts,tsx}`
- **Supporting libraries**:
  - `@testing-library/react` - Component testing utilities
  - `@testing-library/jest-dom` - DOM assertions
  - Assertion library: Vitest's `expect()` (Jest-compatible)
- **Run commands**:
  - `npm test` - Single run
  - `npm run test:watch` - Watch mode
  - File: `/Users/Mehek1/HiveMind/conca/web/package.json` lines 12-13

### Go
- **Standard library**: Uses Go's built-in `testing` package
- **Status**: No test files found in project (`*_test.go`)
- **Implication**: Testing strategy not yet implemented or tests in separate location

### Python
- **Standard library**: `unittest` or similar likely available
- **Status**: No test files found in `/Users/Mehek1/HiveMind/kalshi-crypto-trader/`
- **Dependencies**: No testing framework listed in `requirements.txt`
- **Implication**: Focus on manual testing or integration testing in live environment

## Structure

### TypeScript/React Test Organization
- **Location**: `/Users/Mehek1/HiveMind/conca/web/src/test/`
- **Setup file**: `setup.ts` - Initializes test environment
  - Imports `@testing-library/jest-dom` for DOM matchers
  - Polyfills `window.matchMedia()` for responsive UI testing
  - File: `/Users/Mehek1/HiveMind/conca/web/src/test/setup.ts`
- **Example test**: `/Users/Mehek1/HiveMind/conca/web/src/test/example.test.ts`
  - Basic structure: `describe("feature") → it("should ...") → expect()`
  - Vitest import: `import { describe, it, expect } from "vitest"`

### Test File Structure Example
```typescript
// From example.test.ts
import { describe, it, expect } from "vitest";

describe("example", () => {
  it("should pass", () => {
    expect(true).toBe(true);
  });
});
```

### Go Code Structure for Testability
- **Dependency injection**: Constructor pattern in `NewAgent()`, `NewServer()` enables mocking
  - File: `/Users/Mehek1/conca/agent/agent.go` line 25
  - File: `/Users/Mehek1/conca/api/server.go` line 24
- **Interface-based design**: Dependencies passed as interfaces
  - `tools.SearchTool`, `tools.LLMTool`, `tools.SocialClient`, `memory.Store`
  - Enables substitution with mock implementations
- **Functional separation**: Clear method boundaries facilitate unit testing
  - `Plan()`, `Generate()`, `Evaluate()` are independently testable
  - `SyncAnalytics()` isolated for analytics testing

### Python Code Structure for Testability
- **Separation of concerns**: Signal analyzers are independent modules
  - `/Users/Mehek1/HiveMind/kalshi-crypto-trader/signals/sentiment.py` - Pure function
  - `/Users/Mehek1/HiveMind/kalshi-crypto-trader/signals/keyword.py` - Pure function
  - `/Users/Mehek1/HiveMind/kalshi-crypto-trader/signals/llm.py` - Pure function with LLM call
- **Dataclass usage**: Strong typing aids test verification
  - `TradeDecision`, `Article`, `SentimentSignal` all dataclasses
  - Enables precise assertion on output fields
- **Configuration centralization**: `config.py` allows override for testing
  - `DRY_RUN=true` disables real trades
  - Thresholds configurable: `SENTIMENT_THRESHOLD`, `LLM_CONFIDENCE_THRESHOLD`

## Mocking

### TypeScript/React
- **Test setup provides mocks**:
  - `window.matchMedia()` polyfill for media query testing (setup.ts)
  - DOM environment via jsdom
- **Testing Library approach**: Component testing with user interactions
  - Expected pattern: render component, query DOM, assert results
  - No explicit mock examples in examined code, but supporting libs present:
    - `@testing-library/react` - Provides `render()`, `screen` utilities
    - `@testing-library/jest-dom` - Custom matchers like `.toBeInTheDocument()`
- **Browser APIs**: Mocked via jsdom and setup utilities

### Go
- **Interface mocking**: Since no test files exist, pattern is structural
- **Recommended approach** (based on architecture):
  - Create mock implementations of interfaces: `SearchTool`, `LLMTool`, `SocialClient`, `Store`, `VectorStore`
  - Pass mocks to `NewAgent()` constructor
  - Example constructor call from agent.go line 25:
    ```go
    func NewAgent(brand models.BrandProfile, search tools.SearchTool, llm tools.LLMTool, ...) *Agent
    ```
  - Tests would provide fake implementations of these interfaces

### Python
- **No mocking framework present**: Not listed in `requirements.txt`
- **Recommended approach** (based on signal architecture):
  - Each signal analyzer is a pure function: `analyze(text: str) → SignalType`
  - Testable with deterministic inputs (no external state needed)
  - Example from sentiment.py: Pure VADER analysis, no external calls
  - LLM signal (llm.py) requires Claude API - would need mocking for unit tests
- **Configuration override**: `DRY_RUN=true` for safe integration testing
- **Manual testing pattern**: Print-based logging visible via `console.print()` for verification

## Coverage

### TypeScript/React
- **Status**: No coverage configuration found in vitest.config.ts
- **Framework capability**: Vitest supports coverage via `@vitest/coverage-*` plugins (not installed)
- **Current state**: No explicit coverage measurement
- **Dependencies available for coverage**:
  - `@testing-library/jest-dom` (v6.6.0) - Supports assertion coverage
  - `jsdom` (v20.0.3) - DOM simulation for coverage

### Go
- **Status**: No test files, therefore no coverage
- **Framework capability**: Go's `go test -cover` and coverage tools available
- **Recommended setup**: Create `*_test.go` files alongside implementation

### Python
- **Status**: No test files, no coverage measurement
- **Framework capability**: `pytest` and `coverage` tools available (not installed)
- **Testing approach appears to be**: Live trading with `DRY_RUN=true` mode
  - Logs all trades to `trades.jsonl` file (trader.py line 45)
  - Each decision logged regardless of execution (line 59-61)
  - Observable via file inspection rather than test assertions

### Live Testing & Verification Patterns

**Python - Trade Decision Logging**
- File: `/Users/Mehek1/HiveMind/kalshi-crypto-trader/trades.jsonl`
- Format: JSON Lines (one JSON object per line)
- Content: `TradeDecision` dataclass fields (timestamp, article, market, direction, signals, execution status)
- Verification: Analyze logs post-execution rather than unit tests
- Example from trader.py lines 120-138: Decision structure captured before execution

**Python - Signal Verification**
- Signals can be individually tested by calling `analyze()` directly:
  - `signals.sentiment.analyze(text)` → `SentimentSignal`
  - `signals.keyword.analyze(text)` → `KeywordSignal`
  - `signals.llm.analyze(title, summary, market)` → `LLMSignal`
- No test framework, but functions are pure and deterministic (except LLM call)
- Could be tested with sample crypto news snippets

**Go - Agent Loop Testing Approach**
- Would require mocking: Search tool, LLM tool, Social client, Memory store
- Key methods to test:
  - `Run()` - Full cycle orchestration
  - `Plan()` - Trend analysis and topic selection
  - `Generate()` - Content creation
  - `Evaluate()` - Quality scoring
  - `PlanBatch()` - Batch scheduling logic
  - `SyncAnalytics()` - Performance tracking
- Logger captures state: `logger.GlobalBuffer` tracks all steps
- Verification would be checking logger output and store updates

### Test Isolation & Test Doubles

**Go - Constructor-based DI**
- Clean test setup possible:
  ```go
  mockSearch := NewMockSearchTool()
  mockLLM := NewMockLLMTool()
  // ...
  agent := NewAgent(brand, mockSearch, mockLLM, ...)
  result := agent.Run()
  ```

**Python - Pure Functions**
- Signal analyzers need no setup:
  ```python
  signal = sentiment.analyze("very positive text")
  assert signal.direction == "yes"
  ```

**TypeScript/React - Setup File Pattern**
- setup.ts runs before all tests (vitest.config.ts line 10)
- Provides global `matchMedia` mock for all tests
- Components can be rendered and tested in isolation:
  ```typescript
  import { render, screen } from "@testing-library/react";
  render(<MyComponent />);
  expect(screen.getByText("expected")).toBeInTheDocument();
  ```

### Test Execution Environment

**TypeScript/React**
- Browser-like environment (jsdom)
- No network mocking configured (would need manual setup)
- File system unavailable in browser tests
- Component lifecycle: Full React lifecycle in test environment

**Go**
- Would run in standard Go test environment (no special setup needed)
- Can use `testing.T` for parallel test execution
- Can mock network calls via interface injection

**Python**
- Runs in standard Python environment
- Network calls to Kalshi API and RSS feeds are real
- LLM calls to Claude are real (costs money)
- `DRY_RUN=true` prevents actual trade placement
- No test isolation - relies on configuration flags

