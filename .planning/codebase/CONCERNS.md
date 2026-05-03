# Concerns

## Technical Debt

### Go Projects (conca, kalshi-crypto-trader)
1. **String-based UUID Generation** (`/Users/Mehek1/conca/agent/agent.go`)
   - Uses `fmt.Sprintf("post-%d", time.Now().Unix())` for post IDs, which is not collision-resistant
   - Should use proper UUID (uuid.NewV4()) for distributed systems

2. **Hard-coded Default Values**
   - MongoDB connection defaults to `mongodb://localhost:27017` if env var missing (`/Users/Mehek1/conca/cmd/main.go:96`)
   - No validation that required API keys are set before using them
   - API timeout fixed at 60 seconds globally (`/Users/Mehek1/conca/api/server.go:41`)

3. **Error Handling**
   - Silent failures in notification system (`/Users/Mehek1/kalshi-crypto-trader/trader.py:55`) - catches all exceptions without logging
   - Generic error responses that don't distinguish between user errors and system errors
   - Database context operations use `context.Background()` everywhere, no timeout controls

4. **Memory/Vector Store Integration** (`/Users/Mehek1/conca/memory/vector.go`)
   - Vector store implementation requires review - collection management not fully visible in reviewed code
   - Potential N+1 queries in brand listing with vector lookups

5. **Middleware Issues** (`/Users/Mehek1/conca/api/middleware.go`)
   - No request validation before JWT parsing
   - Context value assertion on line 73 could silently return empty string

### Python Projects
1. **File I/O Without Validation** (`/Users/Mehek1/kalshi-crypto-trader/trader.py:60`)
   - Opens trades.jsonl without checking write permissions or disk space
   - No rotation or size limits on growing log files

2. **Subprocess Execution** (`/Users/Mehek1/kalshi-crypto-trader/trader.py:51-54`)
   - Dangerous use of `osascript` with user input (article title, message)
   - Could be vulnerable to injection if article data is not sanitized

## Known Bugs / Issues

### Critical

1. **Exposed API Keys in Configuration File** - **SEVERITY: CRITICAL**
   - `/Users/Mehek1/kalshi-crypto-trader/config.py` contains hardcoded API credentials:
     - Line 7: Kalshi API Key ID hardcoded as fallback
     - Line 8: Full Kalshi RSA private key embedded in source code (lines 8-34)
     - Line 39: Anthropic API key (redacted — rotate immediately)
   - **Impact**: Anyone with code access has credentials to trading systems and LLM API
   - **Recommendation**: Immediately rotate all exposed credentials, move to environment variables only

2. **Plain-text Password Hashing** (`/Users/Mehek1/conca/api/handlers.go:346-349`)
   - Uses SHA256 for password hashing instead of bcrypt/argon2
   - No salt - identical passwords produce identical hashes
   - Allows rainbow table attacks
   - **Fix**: Use `golang.org/x/crypto/bcrypt`

### High

3. **Weak CORS Policy** (`/Users/Mehek1/conca/api/server.go:151`)
   - `Access-Control-Allow-Origin: "*"` allows any origin to make requests
   - No credential protection - should be restricted to specific domains

4. **JWT Secret Management** (`/Users/Mehek1/conca/api/middleware.go`)
   - Secret is passed as string parameter, likely from environment
   - No validation of minimum secret length (should be 256+ bits)
   - No secret rotation mechanism

5. **Hardcoded MongoDB User ID Prefix** (`/Users/Mehek1/conca/api/handlers.go:123`)
   - Uses `fmt.Sprintf("%s_%s", userID[:8], brand.ID)` which assumes userID is at least 8 chars
   - Could panic on short IDs; no bounds checking

6. **No Input Validation**
   - `/Users/Mehek1/conca/api/handlers.go:40-48`: Email/password fields accepted without validation (length, format, special chars)
   - No SQL injection protection in MongoDB queries (though MongoDB driver handles this, queries should still validate)
   - Brand ID and Name validation only checks empty strings (line 115-118)

### Medium

7. **Silent Fallbacks in Search Configuration** (`/Users/Mehek1/conca/cmd/main.go:44-58`)
   - If NEWSAPI_KEY missing, silently falls back to DuckDuckGo
   - User may not realize their desired API isn't working
   - Should warn or fail explicitly

8. **Missing Request ID Logging**
   - Middleware creates request IDs but handlers don't seem to use them in logs
   - Makes debugging difficult in async operations

9. **Database Disconnect Not Enforced** (`/Users/Mehek1/conca/cmd/main.go:103`)
   - `defer mStore.Close()` will close on normal exit, but not guaranteed in panic scenarios
   - Should use context cancellation for graceful shutdown

10. **Unvalidated URL Construction** (`/Users/Mehek1/conca/tools/llm.go:67`)
    - Builds URL with unsanitized model parameter: `fmt.Sprintf("...%s:generateContent?key=%s", g.Model, g.APIKey)`
    - API key exposed in URL (should be in header)

11. **File Server Path Traversal Risk** (`/Users/Mehek1/conca/api/server.go:92-127`)
    - Custom FileServer implementation with fallback to index.html
    - Path traversal could be possible if not handled by http.FileServer properly
    - Should add explicit path validation

## Security Concerns

1. **Cryptographic Issues**
   - SHA256 password hashing (non-standard, weak)
   - API key exposed in URL instead of Authorization header (`/Users/Mehek1/conca/tools/llm.go:67`)
   - No HTTPS enforcement (development OK, but production risk)

2. **Authentication & Authorization**
   - No rate limiting on auth endpoints - brute force attacks possible
   - No account lockout after failed login attempts
   - JWT doesn't validate user still exists (could have been deleted)
   - No way to revoke tokens (logout doesn't invalidate server-side)

3. **Data Exposure**
   - System status endpoint returns environment variable names even when disconnected (`/Users/Mehek1/conca/api/system.go:25`)
   - MongoDB database name exposed via status endpoint
   - Error messages may leak internal details

4. **API Key Handling**
   - Multiple API keys passed to handlers but only one JWTSecret validated
   - No key rotation strategy
   - Credentials logged in trade decisions (`/Users/Mehek1/kalshi-crypto-trader/trader.py` - though actual keys not logged, reasoning fields contain error details)

5. **Subprocess/Shell Injection Risk**
   - macOS notification via osascript in trader (`/Users/Mehek1/kalshi-crypto-trader/trader.py:51-54`)
   - Article title/message not quoted properly, could execute arbitrary commands if title contains special chars

6. **Deserialization Risk**
   - `json.NewDecoder(r.Body).Decode()` used throughout without size limits
   - Large request bodies could cause DoS or memory exhaustion

## Performance

1. **Query Performance Issues**
   - `GetGlobalHistory()` loads ALL brands then queries posts - should use single aggregation query
   - No pagination on history endpoints - could load millions of records
   - MongoDB Find operations don't set batch size

2. **Memory Usage**
   - Trades log file (`/Users/Mehek1/kalshi-crypto-trader/trades.jsonl`) is 61MB and growing unbounded
   - No compression or archival strategy
   - Reading entire file into memory for pagination would be problematic

3. **HTTP Client Reuse**
   - GeminiClient creates new http.Client each request - should reuse connection pool
   - 60-second timeout may be too long for user-facing requests

4. **Vector Store Inefficiency**
   - Not visible in code review, but typical pattern: full table scans on similarity search
   - No indexing strategy for embedding queries

5. **Logging**
   - Global logger buffer with no size limit (`/Users/Mehek1/conca/tools/logger/logger.go`)
   - All log entries kept in memory indefinitely
   - Could leak memory over time

## Fragile Areas

1. **Authentication Flow** (`/Users/Mehek1/conca/api/handlers.go`, `/Users/Mehek1/conca/api/middleware.go`)
   - Multiple places assume userID is non-empty and well-formed
   - No validation that user ID from JWT matches requesting user
   - Could allow accessing other users' data if ID not validated per-resource

2. **Brand ID Uniqueness**
   - Brand IDs are user-scoped with prefix (`/Users/Mehek1/conca/api/handlers.go:123`)
   - But database doesn't enforce uniqueness constraint
   - Race condition: two simultaneous requests could create duplicate IDs

3. **Scheduled Posts Calendar**
   - PostStatus enum depends on exact string matching
   - No validation that transition is to valid state (e.g., can't go from "published" back to "scheduled")
   - Race condition if post updated while being published

4. **Signal Aggregation in Trader** (`/Users/Mehek1/kalshi-crypto-trader/trader.py:64-72`)
   - Majority voting with 3 signals: returns None if split 1-1-1 or 2-1 mixed
   - Behavior on new signals unclear - hardcoded for exactly 3
   - Sentiment=neutral might not be counted as signal direction for majority

5. **Market Relevance Check** (`/Users/Mehek1/kalshi-crypto-trader/trader.py:106-109`)
   - Simple word overlap (>= 2 words) is brittle
   - "Bitcoin" article won't match "BTC" market
   - No semantic similarity, false negatives common

6. **Config Loading**
   - Hard defaults in code override environment in some cases
   - No validation that config file exists before reading (`/Users/Mehek1/conca/cmd/main.go:29`)
   - Fatal error terminates whole service on bad config

## Recommendations

### Immediate (Security Critical)
1. **Rotate all exposed credentials** in `config.py` (Kalshi keys, Anthropic API key)
2. **Remove hardcoded keys** from source - implement env-only loading with validation
3. **Replace SHA256 password hashing** with bcrypt (golang.org/x/crypto/bcrypt)
4. **Fix CORS policy** - restrict to specific origins instead of "*"
5. **Add request size limits** to prevent DoS on JSON endpoints

### Short Term (High Priority)
6. **Implement proper authentication**:
   - Rate limiting on /register and /login
   - Token revocation/logout
   - Password validation rules (length, complexity)
7. **Add input validation** for email format, password strength, brand names
8. **Secure API key usage**:
   - Remove API key from URL (use Authorization header)
   - Validate minimum key length before use
9. **Fix subprocess execution** - properly quote/escape osascript arguments
10. **Add index constraints** - enforce unique brand IDs per user at database level

### Medium Term
11. **Implement proper logging**:
    - Use structured logging (logrus, zap)
    - Implement log rotation for trader.log
    - Set log buffer size limits
12. **Database optimization**:
    - Add indexes on frequently queried fields (brand_id, user_id)
    - Implement pagination on all list endpoints (limit 50-100 default)
    - Aggregate global queries with MongoDB aggregation pipeline
13. **Add proper shutdown handling**:
    - Context-aware server shutdown
    - Graceful connection draining
14. **Implement vector store optimization**:
    - Index embeddings with HNSW or similar
    - Set query limits to prevent full scans
15. **Add monitoring/alerting**:
    - Track failed auth attempts
    - Alert on unusual trading volumes
    - Monitor API latencies and errors

### Long Term
16. **Architecture improvements**:
    - Separate auth service from business logic
    - Implement circuit breakers for external APIs
    - Add cache layer (Redis) for frequently accessed data
17. **Testing**:
    - Add security-focused unit tests (auth, input validation)
    - Load testing for database queries
    - Integration tests for full auth flow
18. **Documentation**:
    - Security model documentation
    - API authentication/authorization guide
    - Incident response playbook
