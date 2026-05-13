# Operations Runbook: PEAD Trading System

This runbook documents manual UAT procedures for Railway operations. It covers volume
persistence verification (NFR-5), production smoke tests, RL trainer manual deploys,
and rollback procedures.

---

## Section 1: Railway Volume Persistence Verification (NFR-5)

Run this checklist after any forced Railway service restart or re-deploy to confirm that
persisted data (rows in PostgreSQL) survived the restart.

### Prerequisites

- Railway CLI installed: `npm install -g @railway/cli`
- Authenticated: `railway login`
- Access to the Railway project's PostgreSQL service

### Checklist

**Step 1: Record pre-restart row counts**

Before restarting, capture baseline counts. Connect to the Railway PostgreSQL service
(via Railway's database console or `railway connect <postgres-service-name>`) and run:

```sql
SELECT 'earnings_events' AS table_name, COUNT(*) AS row_count FROM earnings_events
UNION ALL
SELECT 'signals', COUNT(*) FROM signals
UNION ALL
SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL
SELECT 'portfolio_positions', COUNT(*) FROM portfolio_positions;
```

Save this output. You will compare it against post-restart counts.

**Step 2: Trigger a service restart**

In the Railway dashboard:
1. Navigate to your project.
2. Select the `fastapi` service.
3. Click "Redeploy" (or "Restart" if using the three-dot menu).

Alternatively, via CLI:
```bash
railway redeploy --service fastapi
```

**Step 3: Watch startup logs for Alembic migration output**

In the Railway dashboard, open the `fastapi` service logs. After the container starts,
confirm that the following line (or similar) appears:

```
INFO  [alembic.runtime.migration] Running upgrade ...
```

If no Alembic output appears, check that the container startup command runs
`alembic upgrade head` before starting uvicorn, or that the application lifespan
event triggers migrations.

Pass criteria: Alembic migration line visible in logs within 60 seconds of container start.

**Step 4: Confirm the health check returns 200**

Wait for the service to reach healthy state. In the Railway dashboard the service
indicator turns green. Then verify:

```bash
curl -f https://<RAILWAY_DOMAIN>/health
# Expected response: {"status": "ok"}
# Expected HTTP status: 200
```

Replace `<RAILWAY_DOMAIN>` with the Railway-assigned domain for your fastapi service
(visible in the service settings under "Domains").

**Step 5: Verify row counts survived**

Reconnect to the Railway PostgreSQL service and re-run the same query from Step 1:

```sql
SELECT 'earnings_events' AS table_name, COUNT(*) AS row_count FROM earnings_events
UNION ALL
SELECT 'signals', COUNT(*) FROM signals
UNION ALL
SELECT 'alerts', COUNT(*) FROM alerts
UNION ALL
SELECT 'portfolio_positions', COUNT(*) FROM portfolio_positions;
```

Compare against pre-restart counts. All counts must match.

**Step 6: Verify volume mount configuration (if counts do not match)**

If row counts differ after restart, the PostgreSQL volume may be unmounted or the
service may be pointing to a different database instance. In the Railway dashboard:

1. Navigate to the PostgreSQL service settings.
2. Confirm that a persistent volume is attached (visible under "Volumes" in service settings).
3. Confirm that the `DATABASE_URL` environment variable in the `fastapi` service points
   to the Railway PostgreSQL service, not to a local or external database.

### Pass Criteria

- All row counts match pre-restart counts.
- `/health` returns HTTP 200.
- Alembic migration output appears in startup logs.

### Fail Actions

- Counts do not match: check volume attachment in Railway service settings.
- Health check fails: check `fastapi` service logs for startup errors.
- Alembic not running: check that the Docker entrypoint or startup command includes
  `alembic upgrade head` before starting the application server.

---

## Section 2: Production Smoke Test (Post-Deploy Verification)

Run these checks after every deployment to main to confirm all services are operational.

### Step 1: Health Check

```bash
curl -f https://<RAILWAY_DOMAIN>/health
```

Expected response body:
```json
{"status": "ok"}
```

Expected: HTTP 200.

### Step 2: Dashboard Endpoint

```bash
curl -f https://<RAILWAY_DOMAIN>/api/v1/dashboard
```

Expected response: JSON object containing keys including `nav`, `daily_pnl`,
`active_positions`, `macro_gate_status`, and `recent_alerts`.

Expected: HTTP 200.

### Step 3: SSE Stream Connection

```bash
curl -N --max-time 30 https://<RAILWAY_DOMAIN>/api/v1/events
```

Expected: The connection opens immediately with:
```
Content-Type: text/event-stream
```

And emits one or more lines matching `: heartbeat` within 30 seconds.

Expected: HTTP 200 with streaming response.

Note: Use `--max-time 30` to cap the wait. The stream is long-lived; end it manually
with Ctrl-C after confirming the heartbeat lines appear.

### Step 4: Signal Feed

```bash
curl -f "https://<RAILWAY_DOMAIN>/api/v1/signals?limit=5"
```

Expected response: JSON array (may be empty if no signals have been computed yet).

Expected: HTTP 200.

### Step 5: Alerts Endpoint

```bash
curl -f "https://<RAILWAY_DOMAIN>/api/v1/alerts?limit=5"
```

Expected response: JSON array (may be empty if no alerts have fired yet).

Expected: HTTP 200.

### Pass Criteria

All five checks return HTTP 200. The SSE stream opens and emits at least one
`: heartbeat` line within 30 seconds.

### Fail Actions

- Any endpoint returns 4xx or 5xx: check the `fastapi` service logs in Railway.
- SSE stream does not emit heartbeat: check that the Celery worker and Redis services
  are running (visible in Railway dashboard service list).
- Dashboard returns empty data: this is acceptable immediately after a fresh deploy
  if no earnings events have been loaded yet.

---

## Section 3: RL Trainer Manual Deploy

The `rl_trainer` service is intentionally excluded from the auto-deploy step in
`.github/workflows/cd.yml`. This prevents a push to main from killing an in-progress
training job.

The CI test `backend/tests/test_deploy_gate.py` asserts that `rl_trainer` does not
appear in any `railway up` command in `cd.yml`. Do NOT add `rl_trainer` to `cd.yml`.

### To deploy rl_trainer manually

**Via Railway CLI:**

```bash
railway up --service rl_trainer
```

**Via Railway dashboard:**

1. Navigate to your Railway project.
2. Select the `rl_trainer` service.
3. Click the three-dot menu next to the service name.
4. Select "Deploy" or "Manual Deploy".

### Verify rl_trainer is running

In the Railway dashboard, the `rl_trainer` service will show status "Running" when
the training loop is active. Check logs for output from `app.rl.trainer` to confirm
training is in progress.

---

## Section 4: Rollback Procedure

If a deployment causes errors, use one of the following methods to roll back.

### Option A: Railway Dashboard Rollback (Recommended)

1. In the Railway dashboard, navigate to the affected service.
2. Click "Deployments" in the left panel.
3. Find the last known-good deployment in the list.
4. Click the three-dot menu next to that deployment.
5. Click "Rollback" (or "Redeploy this version").

The service will revert to the selected deployment without any code changes needed.

### Option B: Git Revert and Redeploy

```bash
git revert HEAD
git push origin main
```

This creates a new commit that undoes the last change and pushes it to main, triggering
a fresh auto-deploy via the CD workflow.

### Option C: Database Migration Rollback

If the deployment included a schema migration that needs to be reverted:

```bash
railway run --service fastapi -- alembic downgrade -1
```

This rolls back the most recent Alembic migration by one step. To roll back multiple
steps, replace `-1` with the number of migrations or a specific revision identifier.

Warning: Always back up your data before running a downgrade migration. Downgrade
operations may be destructive depending on the migration content.

### Pass Criteria for Rollback

After rollback:
- `/health` returns HTTP 200.
- Row counts match pre-rollback counts (verify using the query from Section 1, Step 1).
- No error-level log lines appear in the Railway service logs.
