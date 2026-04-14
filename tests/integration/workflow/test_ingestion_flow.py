# tests/integration/workflow/test_ingestion_flow.py

import json
from pathlib import Path
from typing import List

import pytest
from src.core.atomic_fact import AtomicFact
from src.core.config import get_settings
from src.index.operations.extract_atomic_facts import extract_atomic_facts
from src.infrastructure.chunking.natural_boundary_chunker import NaturalBoundaryChunker
from src.infrastructure.databases.vectors.lancedb_repo import LanceDBRepository
from src.infrastructure.llm.completion.lite_llm_completion import LiteLLMCompletion
from src.infrastructure.prompts.index.extract_atomic_facts import (
    ATOMIC_FACT_SYSTEM,
    ATOMIC_FACT_USER,
)
from src.infrastructure.storage.mariadb_storage import MariaDBStorage


@pytest.mark.slow
@pytest.mark.integration
class TestIngestionFlow:
    """End-to-end tests connecting all components."""

    @pytest.fixture
    def settings(self):
        return get_settings()

    @pytest.fixture
    def lancedb_repo(self, settings):
        return LanceDBRepository(settings)

    @pytest.fixture
    def mariadb_storage(self):
        import os

        connection_url = os.getenv(
            "TEST_MARIADB_URL", "mysql+aiomysql://root:password@localhost:3306/test_db"
        )
        return MariaDBStorage(connection_url, table_name="e2e_test_facts")

    @pytest.fixture
    def llm_completion(self, settings):
        config = settings.litellm_config
        return LiteLLMCompletion(
            model=config["model"],
            api_key=config["api_key"],
            api_base=config["base_url"],
            api_version=config["api_version"],
        )

    @pytest.fixture
    def chunker(self, settings):
        return NaturalBoundaryChunker(settings)

    async def test_chunk_to_facts_pipeline(
        self, lancedb_repo, mariadb_storage, llm_completion, chunker
    ):
        """
        Test complete pipeline:
        Text → Chunk → Extract Facts → Save to MariaDB → Retrieve
        """
        print("\n" + "=" * 60)
        print("Starting End-to-End Pipeline Test")
        print("=" * 60)

        # Step 1: Create test text (simulating a section)
        test_text = """
        ### Chapter 1: Introduction to Algorithms
        
        An algorithm is a finite sequence of well-defined instructions used to solve a class 
        of problems or perform a computation. Algorithms are fundamental to computer science 
        and programming.
        
        Binary search is a classic algorithm that finds the position of a target value within 
        a sorted array. It works by comparing the target to the middle element of the array. 
        If they are not equal, the half in which the target cannot lie is eliminated, and the 
        search continues on the remaining half. This process repeats until the target is found 
        or the search space is empty. Binary search runs in O(log n) time, making it much 
        faster than linear search for large datasets.
        
        The binary search algorithm requires the input array to be sorted. If the array is 
        unsorted, the algorithm will produce incorrect results. This precondition is essential 
        for the algorithm to function correctly.
        """

        section_id = "e2e-test-section-001"
        path_id = "999.001"

        print(f"\n1. Processing section: {section_id}")
        print(f"   Text length: {len(test_text)} characters")

        # Step 2: Chunk the text
        print("\n2. Chunking text...")
        chunks = chunker.chunk_section(
            section_id=section_id,
            book_id="e2e-test-book",
            path_id=path_id,
            text=test_text,
        )

        print(f"   Created {len(chunks)} chunks")
        for i, chunk in enumerate(chunks):
            print(f"   Chunk {i}: {chunk.chunk_level} - {len(chunk.text)} chars")

        # Step 3: Extract facts from each chunk
        print("\n3. Extracting atomic facts using LLM...")
        all_facts = []

        for i, chunk in enumerate(chunks):
            print(f"   Processing chunk {i+1}/{len(chunks)}...")

            facts = extract_atomic_facts(
                model=llm_completion,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
                text=chunk.text,
                path_id=path_id,
                section_id=section_id,
            )

            all_facts.extend(facts)
            print(f"      Extracted {len(facts)} facts")

        print(f"\n   Total facts extracted: {len(all_facts)}")

        # Step 4: Save facts to MariaDB
        print("\n4. Saving facts to MariaDB...")
        saved_keys = []

        for fact in all_facts:
            key = f"e2e_fact:{fact.section_id}:{fact.id}"
            await mariadb_storage.set(key, fact)
            saved_keys.append(key)
            print(f"   Saved: {fact.id} - {fact.point[:50]}...")

        # Step 5: Retrieve and verify facts
        print("\n5. Retrieving and verifying facts...")

        for fact, key in zip(all_facts, saved_keys):
            retrieved_data = await mariadb_storage.get(key)
            assert retrieved_data is not None

            retrieved_fact = AtomicFact(**retrieved_data)
            assert retrieved_fact.id == fact.id
            assert retrieved_fact.point == fact.point
            assert retrieved_fact.rank == fact.rank
            assert retrieved_fact.reason == fact.reason
            print(f"   Verified: {fact.id}")

        # Step 6: Cleanup
        print("\n6. Cleaning up test data...")
        for key in saved_keys:
            await mariadb_storage.delete(key)

        print("\n" + "=" * 60)
        print("✓ End-to-End Pipeline Test PASSED")
        print("=" * 60)

    async def test_retrieve_from_lancedb_and_extract(
        self, lancedb_repo, mariadb_storage, llm_completion
    ):
        """
        Test: Retrieve chunks from LanceDB → Extract facts → Save to MariaDB
        """
        print("\n" + "=" * 60)
        print("Testing LanceDB Retrieval + Fact Extraction")
        print("=" * 60)

        # Search for relevant chunks
        query = "algorithm binary search"
        book_id = "test-book-001"
        path_id = "001"

        print(f"\n1. Searching LanceDB for: '{query}'")
        results = lancedb_repo.search_chunks(
            query=query, book_id=book_id, path_id=path_id, top_k=3
        )

        if not results:
            print("   No results found - skipping test")
            pytest.skip("No data in LanceDB for this test")

        print(f"   Found {len(results)} chunks")

        # Extract facts from each chunk
        print("\n2. Extracting facts from retrieved chunks...")
        all_facts = []
        saved_keys = []

        for i, result in enumerate(results):
            print(f"   Processing chunk {i+1}:")
            print(f"     Path: {result.get('path_id')}")
            print(f"     Text preview: {result.get('text', '')[:100]}...")

            facts = extract_atomic_facts(
                model=llm_completion,
                system_prompt=ATOMIC_FACT_SYSTEM,
                user_prompt_template=ATOMIC_FACT_USER,
                text=result.get("text", ""),
                path_id=result.get("path_id", "unknown"),
                section_id=result.get("section_id", "unknown"),
            )

            all_facts.extend(facts)
            print(f"     Extracted {len(facts)} facts")

        print(f"\n   Total facts extracted: {len(all_facts)}")

        # Save to MariaDB
        if all_facts:
            print("\n3. Saving to MariaDB...")
            for fact in all_facts:
                key = f"lancedb_fact:{fact.section_id}:{fact.id}"
                await mariadb_storage.set(key, fact)
                saved_keys.append(key)
                print(f"   Saved: {fact.id}")

            # Verify
            print("\n4. Verifying saved facts...")
            for fact, key in zip(all_facts, saved_keys):
                retrieved = await mariadb_storage.get(key)
                assert retrieved is not None
                print(f"   Verified: {fact.id}")

            # Cleanup
            print("\n5. Cleaning up...")
            for key in saved_keys:
                await mariadb_storage.delete(key)

        print("\n" + "=" * 60)
        print("✓ LanceDB Retrieval Test PASSED")
        print("=" * 60)
