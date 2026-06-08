"""Deep-module dependency wiring.

These dependencies expose the new public module contracts while the existing
router/service dependencies continue to work during migration.
"""

from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.dependencies.storages import get_session
from src.api.dependencies.vector import get_vector_repo
from src.audit import AuditGateway
from src.domain import Settings, get_settings
from src.extraction import FactExtraction
from src.ingestion import BookIngestion
from src.jobs import JobService
from src.llm import LLMGateway
from src.store import Store


def get_store(
    session: AsyncSession = Depends(get_session),
    vector_repo=Depends(get_vector_repo),
) -> Store:
    return Store(session, vector_repo)


def get_llm_gateway(settings: Settings = Depends(get_settings)) -> LLMGateway:
    return LLMGateway(settings)


def get_ingestion(
    store: Store = Depends(get_store),
    llm: LLMGateway = Depends(get_llm_gateway),
    settings: Settings = Depends(get_settings),
) -> BookIngestion:
    return BookIngestion(store, llm, settings)


def get_job_service(store: Store = Depends(get_store)) -> JobService:
    return JobService(store)


def get_extraction(
    store: Store = Depends(get_store),
    llm: LLMGateway = Depends(get_llm_gateway),
    settings: Settings = Depends(get_settings),
) -> FactExtraction:
    return FactExtraction(store, llm, settings)


def get_audit_gateway(
    store: Store = Depends(get_store),
    llm: LLMGateway = Depends(get_llm_gateway),
    settings: Settings = Depends(get_settings),
) -> AuditGateway:
    return AuditGateway(store, llm, settings)
