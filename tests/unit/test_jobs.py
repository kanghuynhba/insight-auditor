import pytest

from src.domain.atomic_fact import AtomicFact
from src.domain.helpers import now
from src.domain.processing_job import ProcessingJob
from src.domain.text_chunk import TextChunk
from src.jobs import (
    JOB_EXTRACT_FACTS,
    JOB_PARSE_BOOK,
    QUEUE_FACT,
    QUEUE_PARSE,
    JobService,
)
from src.response.job import ProcessingJobResponse
from src.store import Store
from src.workers.fact_worker import FactWorker
from src.workers import handlers
from src.workers import runner


class FakeStore:
    def __init__(self):
        self.jobs = {}
        self.committed = False

    async def create_processing_job(self, **kwargs):
        job = ProcessingJob(**kwargs)
        self.jobs[job.id] = job
        return job

    async def get_processing_job(self, job_id: str):
        return self.jobs.get(job_id)

    async def list_processing_jobs(self, **kwargs):
        self.list_filters = kwargs
        return list(self.jobs.values())

    async def find_active_job(
        self, job_type: str, resource_type: str, resource_id: str
    ):
        for job in self.jobs.values():
            if (
                job.job_type == job_type
                and job.resource_type == resource_type
                and job.resource_id == resource_id
                and job.status in {"queued", "running"}
            ):
                return job
        return None

    async def commit(self):
        self.committed = True


@pytest.mark.asyncio
async def test_job_service_creates_extract_facts_job():
    store = FakeStore()
    service = JobService(store)

    job = await service.enqueue_extract_facts("section-1", force=True)

    assert job.job_type == JOB_EXTRACT_FACTS
    assert job.queue_name == QUEUE_FACT
    assert job.resource_type == "section"
    assert job.resource_id == "section-1"
    assert job.payload == {"force": True}
    assert job.status == "queued"
    assert store.committed is True


@pytest.mark.asyncio
async def test_enqueue_parse_book_returns_existing_active_job():
    store = FakeStore()
    service = JobService(store)
    existing = ProcessingJob(
        id="job-existing",
        job_type=JOB_PARSE_BOOK,
        queue_name=QUEUE_PARSE,
        resource_type="book",
        resource_id="book-1",
        status="running",
    )
    store.jobs[existing.id] = existing

    job = await service.enqueue_parse_book("book-1")

    assert job is existing
    assert len(store.jobs) == 1


@pytest.mark.asyncio
async def test_enqueue_extract_facts_returns_existing_active_job():
    store = FakeStore()
    service = JobService(store)
    existing = ProcessingJob(
        id="job-existing",
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        status="queued",
    )
    store.jobs[existing.id] = existing

    job = await service.enqueue_extract_facts("section-1")

    assert job is existing
    assert len(store.jobs) == 1


@pytest.mark.asyncio
async def test_force_extract_facts_creates_new_job_with_active_job_present():
    store = FakeStore()
    service = JobService(store)
    existing = ProcessingJob(
        id="job-existing",
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        status="running",
    )
    store.jobs[existing.id] = existing

    job = await service.enqueue_extract_facts("section-1", force=True)

    assert job is not existing
    assert job.payload == {"force": True}
    assert len(store.jobs) == 2


@pytest.mark.asyncio
async def test_job_service_lists_jobs_with_filters():
    store = FakeStore()
    service = JobService(store)
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        status="failed",
    )
    store.jobs[job.id] = job

    jobs = await service.list_jobs(
        status="failed",
        queue_name=QUEUE_FACT,
        job_type=JOB_EXTRACT_FACTS,
        resource_type="section",
        resource_id="section-1",
        limit=25,
    )

    assert jobs == [job]
    assert store.list_filters == {
        "status": "failed",
        "queue_name": QUEUE_FACT,
        "job_type": JOB_EXTRACT_FACTS,
        "resource_type": "section",
        "resource_id": "section-1",
        "limit": 25,
    }


def test_processing_job_response_maps_domain_model():
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        payload={"force": False},
    )

    response = ProcessingJobResponse.from_job(job)

    assert response.id == job.id
    assert response.job_type == JOB_EXTRACT_FACTS
    assert response.status == "queued"
    assert response.resource_id == "section-1"
    assert response.payload == {"force": False}


@pytest.mark.asyncio
async def test_worker_dispatch_calls_fact_handler(monkeypatch):
    calls = []

    class FakeFactWorker:
        def __init__(self, store, llm, settings):
            calls.append((store, llm, settings))

        async def handle(self, job):
            calls.append(job.id)
            return "ok"

    monkeypatch.setattr(handlers, "FactWorker", FakeFactWorker)
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
    )

    result = await handlers.dispatch_job(job, "store", "llm", "settings")

    assert result == "ok"
    assert calls == [("store", "llm", "settings"), job.id]


class FakeWorkerStore:
    def __init__(self, job):
        self.job = job
        self.actions = []

    async def mark_job_succeeded(self, job_id, message=None):
        self.actions.append(("succeeded", job_id, message))
        self.job.status = "succeeded"

    async def mark_job_failed(self, job_id, error):
        self.actions.append(("failed", job_id, error))
        self.job.status = "failed"

    async def update_processing_job_status(self, job_id, status, **kwargs):
        self.actions.append((status, job_id, kwargs))
        self.job.status = status

    async def get_processing_job(self, job_id):
        return self.job

    async def commit(self):
        self.actions.append(("commit",))

    async def rollback(self):
        self.actions.append(("rollback",))


@pytest.mark.asyncio
async def test_process_job_marks_success(monkeypatch):
    async def fake_dispatch(job, store, llm, settings):
        return "done"

    monkeypatch.setattr(runner, "dispatch_job", fake_dispatch)
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        attempts=1,
    )
    store = FakeWorkerStore(job)

    await runner.process_job(job, store, "llm", "settings")

    assert job.status == "succeeded"
    assert ("succeeded", job.id, "done") in store.actions
    assert ("commit",) in store.actions


@pytest.mark.asyncio
async def test_process_job_requeues_failed_job_before_max_attempts(monkeypatch):
    async def fake_dispatch(job, store, llm, settings):
        raise RuntimeError("temporary")

    monkeypatch.setattr(runner, "dispatch_job", fake_dispatch)
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        attempts=1,
        max_attempts=3,
    )
    store = FakeWorkerStore(job)

    await runner.process_job(job, store, "llm", "settings")

    assert job.status == "queued"
    assert any(action[0] == "queued" for action in store.actions)


@pytest.mark.asyncio
async def test_process_job_marks_failed_at_max_attempts(monkeypatch):
    async def fake_dispatch(job, store, llm, settings):
        raise RuntimeError("permanent")

    monkeypatch.setattr(runner, "dispatch_job", fake_dispatch)
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        attempts=3,
        max_attempts=3,
    )
    store = FakeWorkerStore(job)

    await runner.process_job(job, store, "llm", "settings")

    assert job.status == "failed"
    assert any(action[0] == "failed" for action in store.actions)


class FakeJobsRepository:
    def __init__(self, jobs):
        self.jobs = {job.id: job for job in jobs}
        self.stale_before = None
        self.queue_name = None

    async def list_stale_running(self, queue_name, stale_before, limit=10):
        self.queue_name = queue_name
        self.stale_before = stale_before
        return list(self.jobs.values())[:limit]

    async def update_status(
        self,
        job_id,
        status,
        *,
        message=None,
        error=None,
        progress=None,
    ):
        job = self.jobs[job_id]
        job.status = status
        if message is not None:
            job.message = message
        if error is not None:
            job.error = error
        if progress is not None:
            job.progress = progress
        return job


@pytest.mark.asyncio
async def test_recover_stale_running_jobs_requeues_when_attempts_remain():
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        status="running",
        attempts=1,
        max_attempts=3,
        updated_at=now(),
    )
    store = Store.__new__(Store)
    store.jobs = FakeJobsRepository([job])

    recovered = await store.recover_stale_running_jobs(QUEUE_FACT, timeout_seconds=60)

    assert recovered == [job]
    assert job.status == "queued"
    assert job.message == "Recovered stale running job"
    assert store.jobs.queue_name == QUEUE_FACT


@pytest.mark.asyncio
async def test_recover_stale_running_jobs_fails_when_attempts_exhausted():
    job = ProcessingJob(
        job_type=JOB_EXTRACT_FACTS,
        queue_name=QUEUE_FACT,
        resource_type="section",
        resource_id="section-1",
        status="running",
        attempts=3,
        max_attempts=3,
        updated_at=now(),
    )
    store = Store.__new__(Store)
    store.jobs = FakeJobsRepository([job])

    recovered = await store.recover_stale_running_jobs(QUEUE_FACT, timeout_seconds=60)

    assert recovered == [job]
    assert job.status == "failed"
    assert job.message == "Stale running job exceeded max attempts"
    assert job.error == "Job exceeded stale running timeout"


class FakeFactStore:
    def __init__(self, facts):
        self.facts = facts
        self.saved_facts = []
        self.deleted_chunks = []

    async def get_facts_by_chunk(self, chunk_id):
        return self.facts

    async def delete_facts_by_chunk(self, chunk_id):
        self.deleted_chunks.append(chunk_id)

    async def save_facts(self, facts):
        self.saved_facts.extend(facts)
        return facts


class FakeChunkSettings:
    chunk_size = 400
    chunk_overlap = 40


@pytest.mark.asyncio
async def test_fact_worker_retry_skips_chunks_with_existing_facts(monkeypatch):
    async def fail_if_called(**kwargs):
        raise AssertionError("extract_facts should not run for existing chunk facts")

    monkeypatch.setattr("src.workers.fact_worker.extract_facts", fail_if_called)
    fact = AtomicFact(section_id="section-1", chunk_id="chunk-1", point="Known fact")
    chunk = TextChunk(
        id="chunk-1",
        book_id="book-1",
        section_id="section-1",
        text="Known fact.",
        chunk_index=0,
        chunk_level="sentence_group",
        start_char=0,
        end_char=11,
    )
    store = FakeFactStore([fact])
    worker = FactWorker(store, llm=None, settings=FakeChunkSettings())

    facts = await worker._process_chunk(chunk, force=False)

    assert facts == [fact]
    assert store.saved_facts == []
    assert store.deleted_chunks == []
