---
phase: 07-alpaca-execution-alerting
plan: "03"
subsystem: alerting
tags: [redis, sendgrid, slack, httpx, rate-limiting, pub-sub, fire-and-forget]

requires:
  - phase: 07-01
    provides: Alert ORM model, VALID_EVENT_TYPES, config settings (SENDGRID_API_KEY, SLACK_WEBHOOK_URL)
  - phase: 07-02
    provides: alerting test stubs (test_rate_limiter.py, test_dispatcher.py) as RED tests

provides:
  - Redis fixed-window rate limiter (is_rate_limited, max 3/hr per event_type)
  - Alert dispatcher (dispatch_alert) with fire-and-forget SendGrid and Slack delivery
  - Minimal HTML email templates and Slack text renderer for all 9 event types
  - Redis pub/sub publish on every alert dispatch (rate-limited and delivered)

affects: [07-04, 08-dashboard, alerting-wiring]

tech-stack:
  added: [sendgrid==6.12.5, httpx, redis-py]
  patterns:
    - "Redis INCR + conditional EXPIRE for fixed-window rate limiting"
    - "Fire-and-forget async delivery: exceptions caught/logged, never re-raised"
    - "Always-persist pattern: rate-limited alerts stored with rate_limited=True"
    - "Redis pub/sub publish on all alerts (for SSE dashboard in Phase 8)"

key-files:
  created:
    - backend/app/alerting/__init__.py
    - backend/app/alerting/rate_limiter.py
    - backend/app/alerting/dispatcher.py
    - backend/app/alerting/templates.py
  modified:
    - backend/tests/alerting/test_rate_limiter.py
    - backend/tests/alerting/test_dispatcher.py

key-decisions:
  - "Fire-and-forget: SendGrid and Slack calls never block or raise to caller"
  - "Rate-limited alerts are still persisted to DB with rate_limited=True (SC6)"
  - "Redis publish happens for ALL alerts including rate-limited ones (SSE dashboard needs full stream)"
  - "Email HTML uses <p> tags only per CLAUDE.md global rule — no CSS, no inline styles"
  - "Rate limiter key format: alert_rate:{event_type}:{epoch_hour} (fixed window)"

patterns-established:
  - "Fixed-window rate limiting: INCR key, EXPIRE on count==1 only"
  - "Async dispatcher with sync Redis client for rate limiting and pub/sub"
  - "Template functions return strings; dispatcher owns delivery logic"

requirements-completed: [FR-7.4, FR-7.5, FR-8.1, FR-8.3, FR-8.4]

duration: 15min
completed: 2026-05-13
---

# Phase 7 Plan 03: Alerting Module Summary

**Redis fixed-window rate limiter, fire-and-forget SendGrid+Slack dispatcher, and minimal HTML templates for all 9 PEAD alert event types — 8 stub tests turned GREEN**

## Performance

- **Duration:** 15 min
- **Started:** 2026-05-13T00:00:00Z
- **Completed:** 2026-05-13T00:15:00Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Implemented `is_rate_limited(r, event_type, max_per_hour=3)` with Redis INCR/EXPIRE fixed-window pattern, key format `alert_rate:{event_type}:{epoch_hour}`
- Implemented `dispatch_alert()` with full pipeline: validate event_type, rate check, DB persist (always), fire-and-forget SendGrid+Slack, Redis pub/sub publish
- Created minimal HTML email templates and Slack text renderer covering all 9 VALID_EVENT_TYPES
- Turned all 8 stub tests GREEN (3 rate limiter + 5 dispatcher)

## Task Commits

Each task was committed atomically:

1. **Task 1 + Task 2: Redis rate limiter, dispatcher, templates** - `e818671b` (feat)

## Files Created/Modified

- `backend/app/alerting/__init__.py` - Empty module marker
- `backend/app/alerting/rate_limiter.py` - Fixed-window rate limiter using Redis INCR/EXPIRE
- `backend/app/alerting/templates.py` - render_email_html() and render_slack_text() for all 9 event types
- `backend/app/alerting/dispatcher.py` - dispatch_alert() async function with full delivery pipeline
- `backend/tests/alerting/test_rate_limiter.py` - 3 real tests replacing stubs (all GREEN)
- `backend/tests/alerting/test_dispatcher.py` - 5 real tests replacing stubs (all GREEN)

## Decisions Made

- Used `str(call_args.subject)` in test assertion because sendgrid Mail wraps subject in a `Subject` object, not a plain string
- Slack text renderer uses `.upper()` for event labels; test assertions match the uppercased form
- `_send_sendgrid` and `_send_slack` are `async` helper functions even though SendGrid client is synchronous, for consistency with the async dispatcher signature

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Subject object type assertion in test_sendgrid_called_for_all_9_event_types**
- **Found during:** Task 2 (dispatcher tests)
- **Issue:** Plan's test template used `assert event_type in call_args.subject` but sendgrid's `Mail.subject` is a `Subject` object, not iterable as a string
- **Fix:** Changed to `assert event_type in str(call_args.subject)`
- **Files modified:** backend/tests/alerting/test_dispatcher.py
- **Verification:** Test passes after fix
- **Committed in:** e818671b (task commit)

**2. [Rule 1 - Bug] Fixed Slack text assertion to match uppercased event label**
- **Found during:** Task 2 (dispatcher tests)
- **Issue:** Plan's test template checked `assert event_type in call_kwargs["json"]["text"]` but render_slack_text() uppercases and replaces underscores with spaces, so `signal_generated` becomes `SIGNAL GENERATED`
- **Fix:** Changed assertion to `assert event_type.replace("_", " ").upper() in call_kwargs["json"]["text"]`
- **Files modified:** backend/tests/alerting/test_dispatcher.py
- **Verification:** Test passes for all 9 event types
- **Committed in:** e818671b (task commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes corrected mismatches between plan's test template and actual sendgrid/template behavior. No scope creep.

## Issues Encountered

- sendgrid package not installed in test environment; installed from requirements.txt (`sendgrid==6.12.5`) before running tests

## Known Stubs

None - all 9 event types produce real output from templates.py; no placeholder text.

## Threat Flags

None - no new network endpoints or auth paths introduced beyond what the plan's threat model covers.

## Next Phase Readiness

- `dispatch_alert()` is ready for wiring into the orders router (Plan 07-04)
- Rate limiter, templates, and dispatcher are fully tested and independently importable
- Redis pub/sub channel `alerts` is publishing; Phase 8 SSE dashboard can subscribe immediately

---
*Phase: 07-alpaca-execution-alerting*
*Completed: 2026-05-13*
