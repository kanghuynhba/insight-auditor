import os
from unittest.mock import MagicMock

import pytest
from sqlmodel import select
from src.core.atomic_fact import AtomicFact
from src.core.enums import Tier
from src.core.models import Book, Chapter, Section
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext
from src.infrastructure.loaders.file_type import FileType
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)


@pytest.fixture
def sample_text() -> str:
    """Sample section text for extraction."""
    return (
        "Python is a high-level, interpreted programming language. "
        "It emphasizes code readability with its notable use of significant whitespace. "
        "Python's dynamic typing and garbage collection make it suitable for rapid application development."
    )


@pytest.fixture
def sample_success_response() -> MagicMock:
    """
    Mock LLM response that returns a valid JSON array of atomic facts.
    The structure must match what extract_atomic_facts expects.
    """
    mock_response = MagicMock()
    mock_response.formatted_response = [
        {
            "point": "Python is a high-level, interpreted programming language.",
            "rank": 1,
            "reason": "Core definition of Python.",
            "questions": ["What type of programming language is Python?"],
        },
        {
            "point": "Python uses significant whitespace for code readability.",
            "rank": 2,
            "reason": "Key syntactical feature.",
            "questions": ["How does Python enforce code blocks?"],
        },
        {
            "point": "Dynamic typing and garbage collection make Python suitable for rapid development.",
            "rank": 2,
            "reason": "Important runtime characteristics.",
            "questions": [
                "What features of Python accelerate application development?"
            ],
        },
    ]
    return mock_response


@pytest.fixture
async def db_context():
    """Set up a clean MariaDB test database and tear down after test."""
    connection_url = os.getenv(
        "TEST_MARIADB_URL",
        "mysql+aiomysql://root:password@localhost:3306/insight_auditor_test",
    )
    ctx = DatabaseContext(connection_url)

    # Create all tables
    from sqlmodel import SQLModel

    async with ctx.engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    yield ctx

    # Cleanup
    await ctx.engine.dispose()


@pytest.fixture
async def setup_hierarchy(db_context):
    """Create a Book -> Chapter -> Section chain and return the Section."""
    async with db_context.get_session() as session:
        book = Book(
            title="LLM Test Book",
            source_format=FileType.Pdf,
            file_path="/tmp/test.pdf",
            source_filename="test.pdf",
        )
        session.add(book)
        await session.flush()

        chapter = Chapter(title="Chapter 1", path_id="001", book_id=book.id)
        session.add(chapter)
        await session.flush()

        section = Section(
            title="Introduction",
            chapter_id=chapter.id,
            path_id="001.001",
            level=1,
            raw_text="Python is a high-level, interpreted programming language.",
        )
        session.add(section)
        await session.commit()
        await session.refresh(section)
        return section


@pytest.mark.asyncio
class TestLLMFactExtraction:
    """Test LLM integration for atomic fact extraction using MariaDB."""

    async def test_extract_atomic_facts_success(
        self,
        db_context,
        setup_hierarchy,
        sample_success_response,
        sample_text,
    ):
        """Successful extraction: mock LLM, extract facts, persist, and verify."""
        section = setup_hierarchy

        # 1. Mock the LLM completion model
        mock_llm = MagicMock()
        mock_llm.completion.return_value = sample_success_response

        # 2. Run the synchronous extraction function (no need for await)
        facts = extract_atomic_facts(
            model=mock_llm,
            system_prompt=ATOMIC_FACT_SYSTEM,
            user_prompt_template=ATOMIC_FACT_USER,
            text=sample_text,
            path_id=section.path_id,
            section_id=section.id,
        )

        # 3. Persist the extracted facts to the test database
        async with db_context.get_session() as session:
            for fact in facts:
                session.add(fact)
            await session.commit()

            # 4. Retrieve facts from DB and verify
            stmt = (
                select(AtomicFact)
                .where(AtomicFact.section_id == section.id)
                .order_by(AtomicFact.rank)
            )
            result = await session.exec(stmt)
            saved_facts = result.all()

            # Assertions
            assert len(saved_facts) == len(sample_success_response.formatted_response)
            expected_facts = sample_success_response.formatted_response
            expected_by_point = {f["point"]: f for f in expected_facts}

            for fact in saved_facts:
                expected = expected_by_point.get(fact.point)
                assert expected is not None, f"Unexpected fact: {fact.point}"
                assert fact.rank == Tier.from_rank(expected["rank"])
                assert fact.reason == expected["reason"]
                # questions can be compared as sets if order doesn't matter
                assert set(fact.questions) == set(expected["questions"])
