# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Server-monitoring system ("Monitor Integral" / ServPulse) with three parts:
- **`server/`** — FastAPI backend (REST API + alert engine), serves the dashboard and ingests agent metrics. SQLite via SQLAlchemy.
- **`agent/python/`** — lightweight Python agent (`agent.py`) installed on monitored nodes; reads CPU/RAM/disk/network/Docker via `psutil` and POSTs to `/api/metrics`.
- **`frontend/`** — static SPA (vanilla JS + Chart.js in `assets/app.js`, **no build step**), served by the backend.

Code, comments, and commit messages are in Spanish — match that.

## Commands

```bash
# Dev backend (auto-reload). Run from repo root:
uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload

# Production backend (gunicorn, single worker — see warning below):
./scripts/run_prod.sh

# Tests (unittest-based; run from server/ so `app.*` imports resolve):
cd server && python -m pytest tests/            # or: python -m unittest discover tests
cd server && python -m pytest tests/test_alert_rules.py            # single file
cd server && python -m pytest tests/test_alert_rules.py -k test_alert_logic   # single test

# Agent (on a monitored node):
cd agent/python && python install.py     # interactive setup, writes agent.config.json
cd agent/python && python agent.py       # run

# Production deploy (git pull + deps + migrations + service restart):
./update_prod.sh        # Linux;  update_prod.ps1 for Windows
```

Python 3.12 (`.python-version`); deps in `server/requirements.txt` and `agent/python/requirements.txt`. There is no linter configured.

## Architecture & conventions

**Monolith.** Almost the entire backend lives in `server/app/main.py` (~2400 lines): all `@app.*` routes, auth, the alert engine, and the WhatsApp bot. `models.py` (SQLAlchemy), `schemas.py` (Pydantic), `email_utils.py` (Mailjet), `config.py` (env-backed settings). Ignore `*_backup.py` files.

**Two separate auth mechanisms — do not confuse them:**
- *Dashboard/web users*: opaque random session tokens stored in the `sessions` table, sent in the **`X-Dashboard-Token`** header. The dependency `get_current_user_from_token` (and `require_admin`) validates against that table. **This is the live mechanism.** Note: `create_jwt_for_user`/`verify_jwt_token` (PyJWT) also exist but the primary request auth path uses the session table, not JWT.
- *Agents*: authenticate per-server by `server_id` + `token` (a row in the `servers` table), created via `/api/register`.

**Schema migrations are manual — there is no Alembic.** At startup, `Base.metadata.create_all` creates *new tables only*; it never alters existing ones. Column additions to existing tables are applied two ways:
- `ensure_*_column()` / `ensure_*()` functions run in the `startup()` event (each does an idempotent `ALTER TABLE` / seed).
- Numbered `server/scripts/migrate_vN.py` scripts invoked by `update_prod.sh`.

➜ **When you add a column to an existing model, you must also add a matching `ensure_*` function** (and likely a `migrate_vN.py`), or it will silently not exist on already-deployed databases.

**Single-worker assumption (important).** Critical runtime state is in module-level dicts in `main.py`: the recent-metrics `_cache`, `_threshold_cache`, the alert-cooldown `_alert_state` (1-hour `ALERT_COOLDOWN`), and the in-memory WhatsApp `_wa_sessions`. These are **not shared across processes**, so `run_prod.sh` runs gunicorn with `WORKERS=1`. Running multiple workers would break alert de-duplication, the cache, and WhatsApp sessions.

**Alert engine.** Recipients are resolved by `get_alert_recipients` using `AlertRule` rows scoped `global` / `group` / `server`, plus per-server `ServerThreshold` overrides (falling back to `AlertConfig` / `DEFAULT_ALERTS`). Threshold checks run on every `POST /api/metrics`; an async `_offline_monitor_loop` (started in `startup()`) polls for servers that stopped reporting. Each alert type has a 1-hour cooldown per server.

**DB & data.** SQLite at `server/data/monitor.db` (gitignored, auto-created). Runs in **WAL mode** with `synchronous=NORMAL` + `busy_timeout` (applied via a `connect` event listener on the engine) so agent writes don't block dashboard reads — note this creates `monitor.db-wal`/`-shm` sidecar files (backups must account for them; see README). Performance indexes (incl. composite `ix_metrics_server_id_id`) are created by `ensure_performance_indexes()` at startup. JSON-heavy columns (`cpu_per_core`, `docker_containers`, `services`, `AlertRule.emails`, `sidebar_config`) are stored as serialized `Text` — serialize/deserialize manually. The `metrics` table has no retention/pruning — it grows unbounded (see README for a cron-based cleanup).

**Hot-path query rule.** When listing servers, get latest/first metric per server via `_bulk_server_first_last` (one aggregate query) + `_status_uptime_from`, never per-server in a loop — the old `_compute_server_status`/`_compute_uptime_for_server` pattern was 3 queries × N servers on every dashboard refresh.

**Frontend.** Single static SPA mounted by the backend: `GET /` returns `frontend/index.html`, assets served from `/assets`. Edit `frontend/assets/app.js` directly — no bundler, no transpile.

## Gotchas

- `config.py` currently contains **hardcoded default credentials and live email/API secrets** (`ALLOWED_USERS`, `EMAIL_API_KEY`, etc.) as fallbacks. Prefer `.env` (gitignored) overrides; don't add more secrets to source.
- `ALLOWED_ORIGINS = ["*"]` and `JWT_SECRET_KEY` defaults to `"change-me"` — set real values via env in production.
- The repo contains a nested `monitoreo-Server` git submodule that points back at this project; it commonly shows as modified in `git status`. Leave it alone unless intentionally bumping it.
- `agent/python/agent.config.json` is gitignored and per-install; don't commit node-specific config.
