# Dialog ETL Backend

## Prerequisites
- Python 3.10+
- MySQL instance that hosts both `people_customer_dialog` (source) and `prepared_conversations` (target) tables.
- `.env` file located at the repository root (`/Users/yunshu/Documents/1208learn/.env`). The loader accepts both `KEY=value` and `key: value` forms. Required keys:

```
url=jdbc:mysql://<host>:<port>/<database>?serverTimezone=Asia/Shanghai
username=<db_user>
password=<db_password>
```

Optional overrides (if source/target DBs differ):

```
SRC_DB_HOST=...
SRC_DB_NAME=...
DST_DB_HOST=...
DST_DB_NAME=...
ETL_CRON=0 1 * * *
ETL_MAX_WORKERS=4
APP_TIMEZONE=Asia/Shanghai
LOG_LEVEL=INFO
```

### AICO 双环境（仅改 AICO_HOST 即切换 DB）

If you have both AICO test/prod environments and want the backend to automatically use different DB credentials when you switch `AICO_HOST`, define:

```
# Map AICO_HOST to a profile
AICO_HOST_TEST=20.17.x.x
AICO_HOST_PROD=20.17.y.y

# Profile-specific DB (applies to both source/target unless SRC_/DST_ are also provided)
TEST_URL=jdbc:mysql://<host>:<port>/<test_db>?serverTimezone=Asia/Shanghai
TEST_USERNAME=<db_user>
TEST_PASSWORD=<db_password>

PROD_URL=jdbc:mysql://<host>:<port>/<prod_db>?serverTimezone=Asia/Shanghai
PROD_USERNAME=<db_user>
PROD_PASSWORD=<db_password>
```

You can also override only the target DB (where `scenarios` live) via `TEST_DST_URL` / `PROD_DST_URL` (and username/password variants).

### AICO 双环境（同一个 DB 内切换 scenario 配置）

If you keep a single database but store different AICO credentials/kb mappings for test/prod, keep knowledge items bound to the user's `scenario_id` and store a second scenario row for test (common convention: `scenario_code` + `_test`). You can optionally bind each row to a specific AICO host via `scenarios.aico_host`.

```
ALTER TABLE scenarios ADD COLUMN aico_host VARCHAR(255) NULL;
```

When syncing, the backend will pick the AICO-config row in this order:

- If `AICO_HOST` matches `AICO_HOST_TEST`: prefer `<scenario_code>_test`
- If `AICO_HOST` matches `AICO_HOST_PROD`: prefer `<scenario_code>`
- If a candidate row has `aico_host == AICO_HOST`, it is preferred

The chosen row is used only for AICO calls (token/pid/kb_id/delete/upload/online). Knowledge items are still taken from the user's `scenario_id`.

## Local setup
```bash
cd /Users/yunshu/Documents/1208learn
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

## Run the service
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- `APScheduler` starts automatically when the FastAPI app boots. Default schedule is every day at `01:00` (Shanghai time) to process `(today - 1)` data.
- Health check: `GET http://localhost:8000/health`
- Manual ETL trigger: `POST http://localhost:8000/api/v1/etl/run`

Request body (optional date):

```json
{
  "target_date": "2024-06-01"
}
```

Response example:

```json
{
  "target_date": "2024-06-01",
  "groups_processed": 2,
  "conversations_total": 3400,
  "inserted": 3397,
  "skipped_existing": 3
}
```

## Notes
- `DialogETLService` enforces idempotency by checking `prepared_conversations.call_id` before insert.
- Concurrency is controlled by `ETL_MAX_WORKERS` (default `4`). Each worker handles one `group_code` at a time.
- Scheduler logs (success/failure counts) are written to stdout; hook them to your observability stack for production.
