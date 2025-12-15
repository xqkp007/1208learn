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
