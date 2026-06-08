from __future__ import annotations

import argparse
import asyncio
import logging

from src.domain.config import get_settings
from src.llm import LLMGateway
from src.store import Store
from src.store._sql import DatabaseContext
from src.store._vector import ChunkRepository, VectorDatabaseContext
from src.workers.handlers import dispatch_job

logger = logging.getLogger(__name__)


def job_log_context(job) -> dict:
    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "queue_name": job.queue_name,
        "resource_type": job.resource_type,
        "resource_id": job.resource_id,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
    }


async def process_job(job, store: Store, llm: LLMGateway, settings) -> None:
    context = job_log_context(job)
    try:
        logger.info("Starting job %s", context)
        message = await dispatch_job(job, store, llm, settings)
        await store.mark_job_succeeded(job.id, message=message)
        await store.commit()
        logger.info("Succeeded job %s", context)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed job %s: %s", context, exc)
        await store.rollback()
        current_job = await store.get_processing_job(job.id)
        if current_job and current_job.attempts < current_job.max_attempts:
            retry_delay = getattr(settings, "job_retry_base_delay_seconds", 0.0)
            if retry_delay > 0:
                await asyncio.sleep(retry_delay * max(current_job.attempts, 1))
            await store.update_processing_job_status(
                job.id,
                "queued",
                error=str(exc),
                message="Retry queued",
                progress=0.0,
            )
            logger.info("Requeued failed job %s", job_log_context(current_job))
        else:
            await store.mark_job_failed(job.id, str(exc))
            logger.info("Marked failed job %s", context)
        await store.commit()


async def run_worker(queues: list[str], sleep_seconds: float) -> None:
    settings = get_settings()
    db = DatabaseContext(str(settings.mariadb_url))
    vector_ctx = VectorDatabaseContext(settings)
    vector_repo = await ChunkRepository.create(settings, vector_ctx)
    llm = LLMGateway(settings)

    while True:
        did_work = False
        for queue_name in queues:
            async with db.get_session() as session:
                store = Store(session, vector_repo)
                recovered_jobs = await store.recover_stale_running_jobs(
                    queue_name,
                    settings.job_stale_timeout_seconds,
                )
                if recovered_jobs:
                    await store.commit()
                    for recovered_job in recovered_jobs:
                        logger.info("Recovered stale job %s", job_log_context(recovered_job))

                job = await store.claim_next_job(queue_name)
                if not job:
                    continue

                did_work = True
                logger.info("Claimed job %s", job_log_context(job))
                await process_job(job, store, llm, settings)

        if not did_work:
            await asyncio.sleep(sleep_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Insight Auditor worker")
    parser.add_argument(
        "--queues",
        default="audit_queue,fact_queue,parse_queue",
        help="Comma-separated queue names in priority order.",
    )
    parser.add_argument("--sleep", type=float, default=2.0)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    args = parse_args()
    queues = [queue.strip() for queue in args.queues.split(",") if queue.strip()]
    asyncio.run(run_worker(queues, args.sleep))


if __name__ == "__main__":
    main()
