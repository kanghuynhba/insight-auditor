from src.jobs import JOB_EXTRACT_FACTS, JOB_PARSE_BOOK
from src.workers.fact_worker import FactWorker
from src.workers.parse_worker import ParseWorker


async def dispatch_job(job, store, llm, settings) -> str:
    if job.job_type == JOB_EXTRACT_FACTS:
        return await FactWorker(store, llm, settings).handle(job)
    if job.job_type == JOB_PARSE_BOOK:
        return await ParseWorker(store, llm, settings).handle(job)
    raise ValueError(f"Unsupported job type: {job.job_type}")
