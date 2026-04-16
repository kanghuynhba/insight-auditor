import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import selectinload
from sqlmodel import SQLModel, select
from src.core.atomic_fact import AtomicFact
from src.core.config import get_settings
from src.core.models import Book, Chapter, Section
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.persistence.chunk_repo import ChunkRepository
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.asyncio
class TestIngestionFlow:
    """Integration test for the full chunking + fact extraction + persistence pipeline."""

    @pytest.fixture
    def settings(self):
        return get_settings()

    @pytest.fixture
    async def db_context(self):
        """Setup a clean test database with all tables."""
        connection_url = os.getenv(
            "TEST_MARIADB_URL",
            "mysql+aiomysql://root:password@localhost:3306/insight_auditor_test",
        )
        ctx = DatabaseContext(connection_url)
        # Create all tables defined in SQLModel metadata
        async with ctx.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            await conn.run_sync(SQLModel.metadata.create_all)
        yield ctx
        # Cleanup
        async with ctx.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        await ctx.engine.dispose()

    @pytest.fixture
    async def sample_section(self, db_context):
        """Create a minimal Book → Chapter → Section for testing."""
        async with db_context.get_session() as session:
            book = Book(
                title="Integration Test Book",
                source_format=FileType.Pdf,
                file_path="/tmp/test.pdf",
                source_filename="test.pdf",
            )
            session.add(book)
            await session.flush()

            chapter = Chapter(
                title="Chapter 1", path_id="001", book_id=book.id, index=1
            )
            session.add(chapter)
            await session.flush()

            section = Section(
                title="Test Section",
                chapter_id=chapter.id,
                path_id="001.001",
                level=1,
                raw_text="An algorithm is a finite sequence of well-defined instructions. "
                "Binary search finds a target in a sorted array by repeatedly halving the search space.",
            )
            session.add(section)
            await session.commit()
            # Refresh and eagerly load the chapter relationship
            stmt = (
                select(Section)
                .where(Section.id == section.id)
                .options(selectinload(Section.chapter))
            )
            result = await session.execute(stmt)
            section = result.scalar_one()
            return section

    @pytest.fixture
    def chunker(self, settings):
        return NaturalBoundaryChunker(settings)

    @pytest.fixture
    def mock_llm_response(self):
        """Mock LLM response with a valid fact list."""
        mock = MagicMock()
        mock.formatted_response = [
            {
                "point": "Binary search requires a sorted array.",
                "rank": 1,
                "reason": "Core precondition",
                "questions": [
                    "What precondition must be satisfied before using binary search?"
                ],
            },
            {
                "point": "Binary search repeatedly halves the search space.",
                "rank": 1,
                "reason": "Core mechanism",
                "questions": ["How does binary search narrow down the search area?"],
            },
        ]
        return mock

    async def test_chunk_to_facts_pipeline(
        self, db_context, sample_section, chunker, mock_llm_response
    ):
        """Test that we can chunk a section, extract facts from a chunk, and persist them."""
        section = sample_section

        # 1. Chunk the section's raw text
        chunks = chunker.chunk_section(
            section_id=section.id,
            book_id=section.chapter.book_id,
            path_id=section.path_id,
            text=section.raw_text,
        )
        assert len(chunks) > 0, "Chunker produced no chunks"

        # 2. Use the first chunk for extraction (real extract_atomic_facts, but with mocked LLM)
        mock_llm = MagicMock()
        mock_llm.completion.return_value = mock_llm_response

        facts = extract_atomic_facts(
            model=mock_llm,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=chunks[0].text,
            path_id=section.path_id,
            section_id=section.id,
        )
        assert len(facts) > 0, "No facts extracted from chunk"

        # 3. Persist facts to MariaDB
        async with db_context.get_session() as session:
            for fact in facts:
                session.add(fact)
            await session.commit()

        # 4. Retrieve and verify facts are correctly linked to the section
        async with db_context.get_session() as session:
            stmt = select(AtomicFact).where(AtomicFact.section_id == section.id)
            result = await session.execute(stmt)
            saved_facts = result.scalars().all()

            assert len(saved_facts) == len(mock_llm_response.formatted_response)
            for fact in saved_facts:
                assert fact.section_id == section.id
                assert fact.path_id == section.path_id
                assert fact.point is not None
                assert fact.rank in (1, 2, 3)  # Will be coerced to Tier internally

        # 5. (Optional) Verify LanceDB chunks are also stored – if you want to test vector storage
        # vector_db = ChunkRepository(get_settings())
        # stored = await vector_db.get_chunks_by_book(section.chapter.book_id)
        # assert len(stored) > 0
