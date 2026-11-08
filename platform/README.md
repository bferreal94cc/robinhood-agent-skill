# SPYBOT — signal notification platform

Automated execution means a notification to Dakota's phone/computer. This application has no order-placement or broker connection.

**Current status: local foundation, not an operating market scanner.** The API, mobile dashboard, SQLite development outbox and Pushover worker are implemented. Read-only Unusual Whales adapters, an opt-in SPY/QQQ GEX collector, raw replay archive, PostgreSQL outbox implementation, source-quality checks and XNYS session calendar are present but are not started or connected to signal generation. Strategy rules remain unconfigured and unapproved; real provider access, PostgreSQL integration, cloud deployment and device delivery remain unverified. The older `dashboard/` research page is preserved.

## Start locally

From this directory, use Python 3.12:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export DASHBOARD_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m uvicorn server.app:create_app --factory --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080`. Enter the local dashboard token in Settings to view protected API status. The browser keeps this dashboard access token only for the session. Never enter market-data, OpenAI or Pushover credentials in the frontend. The `.env.example` file documents environment names; files are not automatically loaded.

Start the worker in another terminal with the same environment and working directory:

```bash
python -m server.worker
```

The worker sends nothing with default configuration. Pushover delivery requires approved strategy configuration, notifications enabled, an app token and a recipient key. Configure secrets on the server only. Do not enable these flags as a substitute for implementing and validating real collectors and strategy rules.

## API

| Route | Access | Behavior |
|---|---|---|
| `GET /healthz` | Public | Process liveness only; not proof of data/notification health |
| `GET /api/status` | Bearer token | Honest setup/provider state and implementation blockers |
| `GET /api/signals` | Bearer token | Last 100 queued candidate records and delivery states |
| `POST /api/candidates` | Bearer token | Validate a trusted producer's candidate; block unapproved/non-live/stale/incomplete evidence, otherwise enqueue uniquely |

Candidate ingestion accepts producer assertions, not raw market evidence. It does not establish that a setup is profitable or compute strategy conditions. Source-quality helpers and the raw collectors are not yet wired into candidate ingestion; producer-provided evidence is still not independently verified. Browser demo values are synthetic and never sent as real signals.

The collector currently subscribes only to the documented `gex_strike:SPY` and `gex_strike:QQQ` channels. REST adapters are read-only and concurrency-capped at three requests. Stream recovery is bounded and calls an injected reconciliation callback; no provider credentials, live connection, or historical backfill has been exercised. The JSONL replay file is explicitly synthetic, not a captured provider response. Replayed raw events are archived with a content-derived ID and first-seen receive time; they are not normalized observations or strategy evidence.

Set `SPYBOT_DATABASE_URL` to select the PostgreSQL store and its initial migration. The API reports this as unverified until a real PostgreSQL integration test and operational recovery checks have passed. SQLite remains the default single-host development store.

## Verify

```bash
python -m unittest discover -s tests -v
node --check web/app.js
```

No external APIs or notification sends are needed by the tests. Provider credential validation and real device receipt remain separate activation checks.

## Structure

```text
platform/
  web/                  responsive dashboard, explicit demo isolation
  server/
    app.py              authenticated API and static UI
    models.py           typed candidate/evidence and deterministic gates
    config.py           server-only configuration, disabled defaults
    storage.py          SQLite development outbox and raw source-event archive
    postgres.py         PostgreSQL outbox with transactional SKIP LOCKED claims
    unusual_whales.py   Read-only REST adapter and bounded SPY/QQQ GEX collector
    market_data.py      Per-source freshness and entitlement gates
    exchange_calendar.py XNYS sessions, holidays and early closes
    strategy.py         Version-bound readiness gate; signal rules stay blocked
    notifications.py    Pushover transport and bounded processing
    worker.py           notification process, graceful shutdown
  tests/                API, delivery, collector replay and readiness checks
  docs/
    API_RESEARCH.md     official API/MCP routes, auth, caveats and links
    ARCHITECTURE.md     production structure and implementation milestones
  deploy/               production handoff; no resources provisioned
```

Recommended production: Cloud Run API + persistent worker pool + Cloud SQL PostgreSQL + Secret Manager. **Do not deploy the current SQLite database onto ephemeral Cloud Run storage or separate hosts.** Start with the [deployment handoff](deploy/README.md), [architecture](docs/ARCHITECTURE.md) and [API reference](docs/API_RESEARCH.md).
