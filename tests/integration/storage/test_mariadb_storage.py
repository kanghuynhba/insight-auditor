# tests/integration/storage/test_mariadb_storage.py

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import pytest
from sqlalchemy import text
from src.core.atomic_fact import AtomicFact
from src.core.audit import AuditReport, UserSummary
from src.core.enums import FactStatus, Tier
from src.infrastructure.storage.mariadb_storage import MariaDBStorage


# Helper to make datetime JSON serializable
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


@pytest.mark.asyncio
class TestMariaDBStorage:
    """Test MariaDB storage operations for atomic facts."""

    @pytest.fixture
    async def mariadb_storage(self):
        """Create MariaDB storage instance for testing with a unique table name."""
        connection_url = os.getenv(
            "TEST_MARIADB_URL",
            "mysql+aiomysql://root:131104@localhost:3306/insight_auditor_test",
        )
        # Use a unique table name to avoid conflicts between tests
        import uuid

        table_name = f"storage_{uuid.uuid4().hex[:8]}"
        storage = MariaDBStorage(connection_url, table_name=table_name)

        # Ensure table exists
        await storage._ensure_table()

        yield storage

        # Cleanup after tests
        async with storage._engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {storage._table_name}"))
        await storage._engine.dispose()

    @pytest.fixture
    def sample_fact(self):
        """Create a sample atomic fact."""
        return AtomicFact(
            section_id="section-001",
            path_id="001.001",
            point="Python lists are mutable sequences",
            rank=Tier.NUANCE,
            reason="Fundamental data structure property",
        )

    @pytest.fixture
    def multiple_facts(self):
        """Create multiple sample facts."""
        return [
            AtomicFact(
                section_id="section-001",
                path_id="001.001",
                point=f"Test point {i}",
                rank=Tier.IMPORTANT if i % 2 == 0 else Tier.NUANCE,
                reason=f"Test reason {i}",
            )
            for i in range(5)
        ]

    async def test_save_single_fact(self, mariadb_storage, sample_fact):
        """Test saving a single atomic fact to MariaDB."""
        key = f"fact:{sample_fact.section_id}:{sample_fact.id}"
        await mariadb_storage.set(key, sample_fact)

        retrieved = await mariadb_storage.get(key)
        assert retrieved is not None

        retrieved_fact = AtomicFact(**retrieved)
        assert retrieved_fact.id == sample_fact.id
        assert retrieved_fact.section_id == sample_fact.section_id
        assert retrieved_fact.point == sample_fact.point
        assert retrieved_fact.rank == sample_fact.rank
        assert retrieved_fact.reason == sample_fact.reason

    async def test_save_multiple_facts(self, mariadb_storage, multiple_facts):
        """Test saving multiple atomic facts to MariaDB."""
        keys = []
        for fact in multiple_facts:
            key = f"fact:{fact.section_id}:{fact.id}"
            keys.append(key)
            await mariadb_storage.set(key, fact)

        for fact, key in zip(multiple_facts, keys):
            retrieved = await mariadb_storage.get(key)
            assert retrieved is not None
            retrieved_fact = AtomicFact(**retrieved)
            assert retrieved_fact.id == fact.id

    async def test_update_existing_fact(self, mariadb_storage, sample_fact):
        """Test updating an existing fact (overwrite)."""
        key = f"fact:{sample_fact.section_id}:{sample_fact.id}"
        await mariadb_storage.set(key, sample_fact)

        updated_fact = AtomicFact(
            id=sample_fact.id,
            section_id=sample_fact.section_id,
            path_id=sample_fact.path_id,
            point="Updated point content",
            rank=Tier.IMPORTANT,
            reason="Updated reason",
        )
        await mariadb_storage.set(key, updated_fact)

        retrieved = await mariadb_storage.get(key)
        retrieved_fact = AtomicFact(**retrieved)
        assert retrieved_fact.point == "Updated point content"
        assert retrieved_fact.rank == Tier.IMPORTANT
        assert retrieved_fact.id == sample_fact.id

    async def test_get_nonexistent_key(self, mariadb_storage):
        """Test retrieving a non-existent key returns None."""
        result = await mariadb_storage.get("nonexistent_key_12345")
        assert result is None

    async def test_delete_fact(self, mariadb_storage, sample_fact):
        """Test deleting a fact from MariaDB."""
        key = f"fact:{sample_fact.section_id}:{sample_fact.id}"
        await mariadb_storage.set(key, sample_fact)
        await mariadb_storage.delete(key)

        result = await mariadb_storage.get(key)
        assert result is None

    async def test_save_fact_list(self, mariadb_storage, multiple_facts):
        """Test saving a list of facts using the storage's list handling."""
        key = "fact_list:section-001"
        await mariadb_storage.set(key, multiple_facts)

        retrieved = await mariadb_storage.get(key)
        assert retrieved is not None
        assert isinstance(retrieved, list)
        assert len(retrieved) == len(multiple_facts)

        for original, retrieved_dict in zip(multiple_facts, retrieved):
            retrieved_fact = AtomicFact(**retrieved_dict)
            assert retrieved_fact.id == original.id

    async def test_save_user_summary(self, mariadb_storage):
        """Test saving a UserSummary object (datetime is serialized as ISO string)."""
        summary = UserSummary(
            section_id="section-001",
            text="This is a test summary",
            word_count=5,
            attempt_number=1,
        )
        key = f"summary:{summary.section_id}:{summary.id}"
        await mariadb_storage.set(key, summary)

        retrieved = await mariadb_storage.get(key)
        assert retrieved is not None

        # The datetime field will come back as a string; Pydantic will parse it.
        retrieved_summary = UserSummary(**retrieved)
        assert retrieved_summary.id == summary.id
        assert retrieved_summary.text == summary.text
        assert retrieved_summary.attempt_number == 1

    async def test_save_audit_report(self, mariadb_storage):
        """Test saving an AuditReport object (datetime serialized)."""
        report = AuditReport(
            summary_id="summary-123",
            section_id="section-001",
            score=85.5,
            mastered=["fact-1", "fact-2"],
            omissions=["fact-3"],
            misconceptions=[],
        )
        key = f"report:{report.section_id}:{report.id}"
        await mariadb_storage.set(key, report)

        retrieved = await mariadb_storage.get(key)
        assert retrieved is not None

        retrieved_report = AuditReport(**retrieved)
        assert retrieved_report.id == report.id
        assert retrieved_report.score == 85.5
        assert len(retrieved_report.mastered) == 2

    async def test_get_as_bytes(self, mariadb_storage, sample_fact):
        """
        Test retrieving data as bytes with a prefix.
        Note: as_bytes=True with a single key (no wildcard) returns None
        because the method expects a prefix to match multiple keys.
        To test, use a prefix that matches the key.
        """
        key = f"fact:{sample_fact.section_id}:{sample_fact.id}"
        await mariadb_storage.set(key, sample_fact)

        # Use a prefix that matches the key (everything before the last colon)
        prefix = f"fact:{sample_fact.section_id}"
        result = await mariadb_storage.get(prefix, as_bytes=True)
        # The result should be a list containing the serialized fact dict
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["id"] == sample_fact.id
