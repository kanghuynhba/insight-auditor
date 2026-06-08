# insight-auditor

## Running the API

Start the FastAPI application from the backend repository root:

```bash
uvicorn src.main:app --reload
```

The API creates SQLModel tables on startup when the configured MariaDB database
is reachable.

## Running workers

Slow processing is handled by durable `ProcessingJob` rows. The current worker
MVP supports book parsing and fact extraction:

```bash
python -m src.workers.runner --queues fact_queue,parse_queue
```

The runner accepts multiple queues in priority order:

```bash
python -m src.workers.runner --queues audit_queue,fact_queue,parse_queue
```

`parse_book` and `extract_facts` jobs are implemented. `audit_summary` is
intentionally left for the next migration phase.

Worker operational settings can be configured with environment variables:

```text
JOB_STALE_TIMEOUT_SECONDS=900
JOB_RETRY_BASE_DELAY_SECONDS=0
```

`JOB_STALE_TIMEOUT_SECONDS` controls when a `running` job is considered stuck.
If the worker finds a stale running job with attempts remaining, it moves it
back to `queued`; otherwise it marks it `failed`.

## Job status

List jobs:

```text
GET /jobs
GET /jobs?status=running
GET /jobs?queue_name=parse_queue&status=queued
GET /jobs?job_type=extract_facts&resource_type=section&resource_id=<section_id>
```

Generic job status:

```text
GET /jobs/{job_id}
```

Fact-extraction compatibility status:

```text
GET /facts/extraction/{job_id}
```

## Worker runbook

Start the API in one terminal:

```bash
uvicorn src.main:app --reload
```

Start a worker for the implemented queues in another terminal:

```bash
python -m src.workers.runner --queues fact_queue,parse_queue
```

Upload/parse/fact-extract smoke test against a running API and worker:

```bash
python scripts/manual_durable_flow.py path/to/textbook.pdf
python scripts/manual_durable_flow.py path/to/textbook.epub --api http://127.0.0.1:8000
```

Inspect queued/running/failed jobs:

```bash
curl 'http://localhost:8000/jobs'
curl 'http://localhost:8000/jobs?status=queued'
curl 'http://localhost:8000/jobs?status=running'
curl 'http://localhost:8000/jobs?status=failed'
curl 'http://localhost:8000/jobs/<job_id>'
```

If jobs look stuck:

1. Check whether the worker process is running.
2. Inspect `GET /jobs?status=running` and compare `updated_at` with
   `JOB_STALE_TIMEOUT_SECONDS`.
3. Restart the worker. On startup/poll, it recovers stale `running` jobs by
   requeueing them if attempts remain or failing them when attempts are
   exhausted.
4. For repeated failures, inspect `error`, `message`, `attempts`, and
   `resource_id` from `GET /jobs/{job_id}`.

Common failure cases:

- API returns upload success but parsing never starts: worker is not running, or
  it was started without `parse_queue`.
- Parse job fails quickly: check `Book.file_path`, source file permissions, and
  whether the file extension is supported by the PDF/EPUB loaders.
- Fact job stays queued: worker is not running, or it was started without
  `fact_queue`.
- Fact job fails: check that the section has chunks and the configured LLM
  completion credentials are valid.
- Job remains `running` after a worker crash: restart the worker and let stale
  recovery requeue or fail it based on `JOB_STALE_TIMEOUT_SECONDS` and attempts.

## Manual migration notes

Fresh databases are initialized from SQLModel metadata on API startup. Existing
MariaDB databases need the durable job table and book upload status column
added before running the queued upload/extraction flow:

```sql
ALTER TABLE book
  ADD COLUMN upload_status VARCHAR(32) NOT NULL DEFAULT 'uploaded';

CREATE TABLE processing_job (
  id VARCHAR(255) NOT NULL PRIMARY KEY,
  job_type VARCHAR(255) NOT NULL,
  queue_name VARCHAR(255) NOT NULL,
  status VARCHAR(255) NOT NULL DEFAULT 'queued',
  resource_type VARCHAR(255) NOT NULL,
  resource_id VARCHAR(255) NOT NULL,
  payload JSON NULL,
  progress DOUBLE NULL,
  message TEXT NULL,
  error TEXT NULL,
  attempts INT NOT NULL DEFAULT 0,
  max_attempts INT NOT NULL DEFAULT 3,
  created_at DATETIME NOT NULL,
  started_at DATETIME NULL,
  completed_at DATETIME NULL,
  updated_at DATETIME NOT NULL
);

CREATE INDEX ix_processing_job_job_type ON processing_job (job_type);
CREATE INDEX ix_processing_job_queue_name ON processing_job (queue_name);
CREATE INDEX ix_processing_job_status ON processing_job (status);
CREATE INDEX ix_processing_job_resource_type ON processing_job (resource_type);
CREATE INDEX ix_processing_job_resource_id ON processing_job (resource_id);
```
