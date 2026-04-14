**SOFTWARE REQUIREMENTS SPECIFICATION**

**Book Audit Platform**

AI-Powered Active Comprehension Engine

| **Document ID**    | BAP-SRS-v2.0                |
| ------------------ | --------------------------- |
| **Version**        | 2.1 - Source-Code Synced    |
| **Status**         | Draft for Review            |
| **Date**           | April 11, 2026              |
| **Classification** | Internal Technical Document |

# Table of Contents

# 1\. Introduction

## 1.1 Purpose

This Software Requirements Specification (SRS) defines the complete functional, architectural, behavioral, and non-functional requirements for the Book Audit Platform (BAP). It is the authoritative technical reference for all engineering, product, and QA stakeholders involved in the design, development, and testing of the system.

This document supersedes all prior informal architecture notes and establishes version 2.0 of the platform requirements, incorporating the Structured Knowledge Validation engine, the three-tier fact hierarchy, anti-passive-reading guardrails, and the hierarchical path-based retrieval strategy.

## 1.2 Scope

The Book Audit Platform is an AI-driven educational tool whose singular mission is to transition users from passive consumption of reading material to verified, active comprehension. The system targets technical and non-fiction books as its primary content type.

The platform achieves this through a two-phase pipeline:

- Content Ingestion Phase: Static documents (PDF/EPUB) are parsed, segmented into a hierarchical structure, chunked into semantic units, and stored in a local vector database alongside AI-generated Atomic Facts.
- Active Audit Phase: Users write chapter or section summaries from memory. The system validates these summaries against the stored Atomic Facts using a semantic entailment model, produces a weighted score, and surfaces granular, actionable gap reports.

## 1.3 Definitions & Acronyms

| **Term / Acronym**   | **Definition**                                                                                                                                                         |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Atomic Fact**      | A single, discrete, verifiable knowledge claim extracted from a chapter section during ingestion. Each fact carries a Criticality Rank (Tier 1-3).                     |
| **Audit Loop**       | The core user interaction cycle: read chapter → close book → write summary → receive AI evaluation.                                                                    |
| **Criticality Rank** | A 1-3 classification assigned to each Atomic Fact denoting its educational weight (Tier 1 = foundational, Tier 2 = precision, Tier 3 = nuance).                        |
| **Entailment Check** | An LLM-based logical inference task that determines whether a user's statement semantically implies or contradicts a given Atomic Fact.                                |
| **Path ID**          | A dot-notation hierarchical identifier (e.g., '001.002.004') that encodes the structural position of any text chunk within a book.                                     |
| **Structural Map**   | An AI-generated summary skeleton produced at ingestion time, containing one-sentence descriptions of every section and a list of 'Must-Know' facts for large chapters. |
| **AuditReport**      | The final output of the validation pipeline: a scored, tiered breakdown of mastered concepts, omissions, and misconceptions.                                           |
| **BAP**              | Book Audit Platform - this system.                                                                                                                                     |
| **LLM**              | Large Language Model (specifically OpenAI GPT-4o mini unless otherwise noted).                                                                                         |
| **RAG**              | Retrieval-Augmented Generation - a pattern where retrieved context is injected into an LLM prompt.                                                                     |
| **VectorDB**         | LanceDB local vector database instance used for semantic retrieval and chunk storage.                                                                                  |
| **FR**               | Functional Requirement.                                                                                                                                                |
| **NFR**              | Non-Functional Requirement.                                                                                                                                            |

# 2\. Product Overview

## 2.1 Product Vision & Anti-Patterns

The platform is built on a single, non-negotiable pedagogical principle: the user must engage in active recall before receiving any AI-generated insight about the material. The system must be architected to make passive consumption of AI-generated summaries structurally impossible.

| **⚠ CRITICAL CONSTRAINT** | The system MUST NOT allow users to view the AuditReport, Atomic Facts, or any AI-generated content analysis before they have submitted a minimum-length summary for the target section. This is a hard architectural gate, not a UI preference. |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |

The following behaviors are explicitly designated as anti-patterns and must be prevented at the API and service layer:

- Anti-Pattern 1 - Report Browsing: A user requests an AuditReport for a section they have not yet submitted a summary for.
- Anti-Pattern 2 - Hint Dependency: A user uses the hint system as a substitute for reading the material, requesting hints before any genuine recall attempt.
- Anti-Pattern 3 - Fact Harvesting: A user directly queries the system to retrieve the stored Atomic Facts for a section.
- Anti-Pattern 4 - Reverse Lookup: A user submits a trivially short or non-substantive summary to unlock the report without genuine effort.

## 2.2 Core User Journey

The canonical, intended user flow is as follows:

| **Step** | **Action**                   | **System Behavior**                                                                                                        |
| -------- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **1**    | **Upload Book**              | User uploads a PDF or EPUB. System ingests, segments, and processes the document into the vector DB and Atomic Fact store. |
| **2**    | **Read Chapter**             | User reads the target chapter in their own medium (physical book, PDF, etc.). The platform plays no role at this stage.    |
| **3**    | **Close Book**               | User signals they are ready to audit. No content is shown.                                                                 |
| **4**    | **Write Summary**            | User writes a free-text recall summary from memory in the summary input field.                                             |
| **5**    | **Request Hints (Optional)** | User may optionally request contextual recall prompts. The system provides questions, not answers.                         |
| **6**    | **Submit for Audit**         | User submits the summary. The system validates it against Atomic Facts.                                                    |
| **7**    | **Receive Report**           | AuditReport is returned: weighted score, mastered facts, omissions by tier, misconceptions.                                |
| **8**    | **Targeted Re-Read**         | User re-reads flagged sub-sections based on report guidance.                                                               |
| **9**    | **Re-Audit (Optional)**      | User may submit a revised summary to improve their score.                                                                  |

# 3\. System Architecture

## 3.1 Architectural Overview

The application is structured as a strict 4-tier decoupled modular architecture. Each tier has a single responsibility and communicates only through defined interfaces. The tiers, from innermost to outermost, are: Domain → Infrastructure → Service → Interface.

## 3.2 Tier 1 - Domain Layer (src/core/)

| **CONSTRAINT** | This layer must have zero imports from any external library. No Azure OpenAI SDK, no LanceDB, no HTTP libraries. Pure Python only. |
| -------------- | ---------------------------------------------------------------------------------------------------------------------------------- |

### 3.2.1 models.py - Data Objects

Defines all core business objects as pure Python dataclasses or Pydantic models (internal only):

| **Model**          | **Key Fields**                                                                                           | **Description**                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **Book**           | id, title, author, file_path, created_at, chapters\[\]                                                   | Root aggregate. Holds all parsed chapters.                                          |
| **Chapter**        | id, book_id, title, path_id, parent_path_id, sections\[\], structural_map                                | Represents one logical chapter including its hierarchical path.                     |
| **Section**        | id, chapter_id, path_id, title, text, atomic_facts\[\]                                                   | A sub-unit of a chapter (e.g., Section 1.2.4). The atomic granularity of the audit. |
| **AtomicFact**     | id, section_id, point, rank (1\|2\|3), reason, embedding_id                                              | A single discrete knowledge claim with its criticality rank.                        |
| **UserSummary**    | id, user_id, section_id, text, word_count, submitted_at, attempt_number                                  | The user's free-text recall submission.                                             |
| **AuditReport**    | id, summary_id, section_id, score (0-100), mastered\[\], omissions\[\], misconceptions\[\], generated_at | The final evaluation output returned to the user.                                   |
| **FactValidation** | fact_id, status (Found\|Partial\|Missing\|Contradicted), evidence, confidence                            | Intermediate result of the LLM entailment check for one fact.                       |

### 3.2.2 interfaces.py - Service Contracts

Defines abstract base classes (ABCs) that the Infrastructure layer must implement:

- LLMInterface: generate_response(prompt: str, system: str) → str
- LLMInterface: generate_atomic_facts(text: str, path_id: str) → list\[AtomicFact\]
- LLMInterface: validate_facts(summary: str, facts: list\[AtomicFact\]) → list\[FactValidation\]
- LLMInterface: generate_hints(facts: list\[AtomicFact\], count: int) → list\[str\]
- VectorRepository: save_chunks(chunks: list\[TextChunk\]) → None
- VectorRepository: search_chunks(query: str, path_filter: str, top_k: int) → list\[TextChunk\]
- AtomicFactRepository: save_facts(facts: list\[AtomicFact\]) → None
- AtomicFactRepository: get_facts_by_path(path_id: str) → list\[AtomicFact\]
- SummaryRepository: save_summary(summary: UserSummary) → UserSummary
- SummaryRepository: get_summary_by_section(section_id: str) → UserSummary | None
- AuditRepository: save_report(report: AuditReport) → AuditReport

## 3.3 Tier 2 - Infrastructure Layer (src/infrastructure/)

Implements all contracts defined in the Domain Layer. Handles all I/O: file parsing, database reads/writes, and LLM API calls.

### 3.3.1 loaders/

- pdf_loader.py: Extracts text from .pdf files via PyMuPDF. Detects chapter and section boundaries using heading font-size heuristics and TOC metadata. Assigns path_id to each segment.
- epub_loader.py: Extracts text from .epub files. Uses the NCX/NAV document structure to derive the logical chapter/section hierarchy and assign path_id values.
- Both loaders return a list of Section objects with path_id, parent_path_id, title, and raw text populated.

### 3.3.2 databases/vectors/lancedb_repo.py

- Manages the connection to the local LanceDB instance at ./lancedb/ (configurable via lance_db_path). Table name is configurable via vector_index_name (default: "textbooks").
- Implements VectorStore. Converts text chunks to embeddings via Azure OpenAI (1536-dimension vectors) and persists them as rows in the LanceDB ChunkSchema table. Uses a threading.Lock to serialize writes while parallelizing embedding calls.
- All stored chunks include path_id as a filterable column to enable hierarchical path-prefix filtering. search_chunks() applies a WHERE filter of the form "book_id = 'X' AND path_id LIKE 'prefix%'" with prefilter=True before running vector similarity search.
- search_chunks() supports both semantic similarity search and \$filter=path.startswith(prefix) style filtering for parent-context retrieval.

### 3.3.3 repositories/fact_repo.py

- Implements AtomicFactRepository. Stores and retrieves AtomicFact objects from a relational SQLite database at data/facts.db.
- Facts are indexed on section_id and path_id for efficient lookup during audit validation.

### 3.3.4 llm/azure_openai_client.py

- Implements LLMInterface. Wraps the Azure OpenAI API using azure_openai_endpoint, azure_openai_api_key, and openai_api_version from Settings. The generative model and embedding model are both configurable via Settings.
- generate_atomic_facts(): Sends section text with the Atomic Fact extraction prompt (see §4.2.1). Parses the JSON response into AtomicFact objects.
- validate_facts(): Sends the user summary and the set of retrieved Atomic Facts with the entailment prompt (see §4.3.2). Parses FactValidation results.
- generate_hints(): Generates n contextual recall questions from the Tier 1 and Tier 2 facts of the target section. The prompt explicitly prohibits including answers.
- All API calls include retry logic (3 retries, exponential backoff) and structured error handling.

## 3.4 Tier 3 - Service Layer (src/services/)

### 3.4.1 ingestion.py

Orchestrates the full ingestion pipeline for a newly uploaded document:

- Receives the file path from the API layer.
- Dispatches to the appropriate loader (pdf_loader or epub_loader) based on file extension.
- Receives the parsed list of Section objects with path_id hierarchy populated.
- For each section, calls llm.generate_atomic_facts() to produce the ranked Atomic Fact list. Saves facts to fact_repo.
- Splits section text into semantic chunks (target: 256-512 tokens). Tags each chunk with path metadata.
- For sections exceeding a configurable threshold (default: 4,000 tokens), calls llm to generate a Structural Map summary. Stores on the Chapter model.
- Saves all chunks via lancedb_repo.save_chunks().
- Saves the Book and Chapter/Section metadata to the relational database.

### 3.4.2 audit.py

Orchestrates the validation pipeline for a user summary submission:

- Receives the UserSummary object and target path_id.
- Enforces the anti-passive-reading gate: confirms word count ≥ MIN_SUMMARY_WORDS (configurable, default: 50). Rejects submissions below threshold.
- Retrieves Atomic Facts for the target path_id from fact_repo.
- Executes the Three-Step Validation Flow (see §4.3).
- Applies the weighted scoring formula to produce a 0-100 score.
- Constructs the AuditReport with tiered feedback messages.
- Saves the report and returns it.

### 3.4.3 hint.py

Manages the hint generation sub-workflow:

- Validates that the user has NOT already submitted a summary for this section (hints are only for pre-submission recall practice).
- Retrieves Tier 1 and Tier 2 Atomic Facts for the target section.
- Calls llm.generate_hints() with a question-only constraint.
- Logs hint request count per session to enable anti-dependency rate limiting.

## 3.5 Tier 4 - Interface Layer (src/api/)

### 3.5.1 main.py

FastAPI application entry point. Configures CORS, middleware, exception handlers, and router registration.

### 3.5.2 routers/books.py

- POST /api/books/upload - Accepts multipart file upload. Validates file type. Enqueues ingestion job.
- GET /api/books/{book_id} - Returns book metadata and chapter/section hierarchy.
- GET /api/books/{book_id}/sections - Returns the full section tree with path_id values.

### 3.5.3 routers/audit.py

- POST /api/audit/submit - Accepts UserSummary payload. Returns AuditReport or 400 if gate conditions not met.
- GET /api/audit/report/{section_id} - Returns a previously generated report (gated: user must have a prior submission).
- POST /api/audit/hints - Accepts section path_id and desired hint count. Returns question list.

# 4\. Core Algorithms & Business Logic

## 4.1 Hierarchical Path System

Every text segment in the system is assigned a zero-padded three-digit path_id that encodes its structural position within the book. This enables parent-context retrieval and scoped audit validation.

| **Structural Level** | **Path ID Example** | **Description**                  |
| -------------------- | ------------------- | -------------------------------- |
| Chapter 1            | **001**             | Top-level chapter                |
| Section 1.2          | **001.002**         | Second section of chapter 1      |
| Subsection 1.2.4     | **001.002.004**     | Fourth subsection of section 1.2 |
| Subsection 1.2.4.1   | **001.002.004.001** | Nested sub-subsection            |

Context Injection Rule: When retrieving facts for a given path, the system also fetches the parent section's Structural Map summary to prevent the 'Inheritance Loss' problem - where an exception-focused subsection loses its foundational 'Base Case' context.

Retrieval Filter Pattern: To retrieve all content under Section 1.2, the system applies: filter(path_id.startswith('001.002')).

## 4.2 Atomic Fact Extraction (Ingestion-Time)

### 4.2.1 Three-Tier Fact Hierarchy

| **Rank**   | **Level Name**          | **Weight** | **Definition**                                                                                                                     |
| ---------- | ----------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Tier 1** | **Foundational Pillar** | **3×**     | The core 'Why' or defining mechanism. If missed, the rest of the summary is incoherent. Failure here heavily penalizes the score.  |
| **Tier 2** | **Critical Precision**  | **2×**     | Specific thresholds, contraindications, technical rules, or legal boundaries. Essential for professional or applied understanding. |
| **Tier 3** | **Contextual Nuance**   | **1×**     | Supporting examples, historical context, secondary analogies. Demonstrates mastery but not vital for basic competency.             |

### 4.2.2 Extraction Prompt Contract

The following LLM prompt structure must be used verbatim during ingestion to extract and rank Atomic Facts:

**SYSTEM PROMPT:**

You are an expert knowledge extraction engine for technical books. Extract discrete, atomic knowledge claims from the provided text. For each claim, assign a Criticality Rank (1-3) and output ONLY a valid JSON array. No preamble, no markdown fences.

**OUTPUT SCHEMA:**

\[{"point": "...", "rank": 1, "reason": "Core mechanism - understanding collapses without this"}\]

**RANKING RULES:**

Rank 1: Foundational logic, core definitions, primary mechanisms

Rank 2: Technical precision - numbers, thresholds, contraindications, rules

Rank 3: Supporting detail, examples, historical context

Exclude: Tier 4 - filler, repetitive phrasing, hyper-specific minutiae

## 4.3 Three-Step Validation Flow (Audit-Time)

The audit validation executes as a sequential three-step pipeline. Each step feeds into the next.

### Step 1 - Retrieve (Semantic Similarity)

For each paragraph or meaningful clause in the user's summary, perform a vector similarity search against the section's stored chunks (filtered by path_id). Retrieve the top-5 most relevant Atomic Facts per paragraph. This step narrows the entailment check to the facts most likely touched by the user's writing.

### Step 2 - Verify (LLM Entailment)

The retrieved facts are bundled with the full user summary and sent to the LLM for semantic entailment checking. The LLM must classify each fact as one of four statuses:

| **Status**       | **Accuracy Score** | **Definition**                                                                                   |
| ---------------- | ------------------ | ------------------------------------------------------------------------------------------------ |
| **Found**        | 1.0                | The user's summary clearly and correctly expresses this fact.                                    |
| **Partial**      | 0.5                | The user touched on the concept but lacked precision or completeness.                            |
| **Missing**      | 0.0                | The user's summary did not address this fact at all.                                             |
| **Contradicted** | 0.0 + flag         | The user stated something that directly conflicts with this fact. Classified as a Misconception. |

### Step 3 - Score (Weighted Calculation)

Apply the weighted average formula to the FactValidation results:

**Score = ( Σ (Accuracy_i × Weight_i) / Σ Weight_i ) × 100**

Where: Accuracy ∈ {1.0 (Found), 0.5 (Partial), 0.0 (Missing/Contradicted)}

Weight ∈ {3 (Tier 1), 2 (Tier 2), 1 (Tier 3)}

## 4.4 AuditReport Feedback Generation

After scoring, the system constructs the AuditReport with tiered feedback messages. The rank of the missed or contradicted fact determines the tone and urgency of the feedback:

| **Rank**               | **Category**           | **Feedback Template**                                                                                                                                                                   |
| ---------------------- | ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Tier 1 - Missing**   | **CRITICAL GAP**       | CRITICAL GAP: You missed the core concept of \[concept\]. Understanding this is foundational - the rest of the chapter's logic depends on it. Return to this section before proceeding. |
| **Tier 2 - Missing**   | **TECHNICAL OMISSION** | TECHNICAL OMISSION: You captured the main idea, but missed the specific threshold/rule for \[detail\]. This precision is required for applied understanding.                            |
| **Tier 3 - Missing**   | **MINOR NUANCE**       | MINOR NUANCE: Solid recall overall. For 100% mastery, try to include the supporting context regarding \[detail\].                                                                       |
| **Any - Contradicted** | **MISCONCEPTION**      | MISCONCEPTION: Your statement '\[quote\]' conflicts with the source material. The correct understanding is \[fact\]. Review this carefully.                                             |
| **Any - Partial**      | **PARTIAL CREDIT**     | PARTIAL RECALL: You touched on \[concept\] but lacked the precision the source requires. Specifically: \[gap detail\].                                                                  |
# 5\. Functional Requirements

## 5.1 Document Ingestion

| **ID**      | **Priority** | **Requirement**                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-1.1**  | **MUST**     | The system must accept .pdf and .epub file uploads via the POST /api/books/upload endpoint.                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **FR-1.2**  | **MUST**     | The system must validate uploaded files against a MIME type allowlist before processing. Reject all other types with HTTP 415.                                                                                                                                                                                                                                                                                                                                                                                |
| **FR-1.3**  | **MUST**     | The system must parse uploaded PDFs using font-size heuristics and/or embedded TOC metadata to identify chapter and section boundaries.                                                                                                                                                                                                                                                                                                                                                                       |
| **FR-1.4**  | **MUST**     | The system must parse uploaded EPUBs using NCX/NAV document structure to identify and preserve the logical chapter hierarchy.                                                                                                                                                                                                                                                                                                                                                                                 |
| **FR-1.5**  | **MUST**     | The system must assign a unique, hierarchical path_id to every parsed segment, following the dot-notation zero-padded convention (e.g., '001.002.004').                                                                                                                                                                                                                                                                                                                                                       |
| **FR-1.6**  | **MUST**     | The system must extract Atomic Facts from each section's stored LanceDB chunks. For each section, the IngestionService retrieves all chunks by path_id, constructs the full section text from chunk text fields (using context_text where available for richer context), and calls LLMInterface.generate_atomic_facts(text, path_id). Each returned AtomicFact must carry a Criticality Rank of Tier.CRITICAL (3), Tier.IMPORTANT (2), or Tier.NUANCE (1), and must be persisted to the AtomicFactRepository. |
| **FR-1.7**  | **MUST**     | The system must generate a Structural Map for any section exceeding 4,000 tokens, comprising a one-sentence summary per sub-section and a 'Must-Know' fact list.                                                                                                                                                                                                                                                                                                                                              |
| **FR-1.8**  | **MUST**     | The system must save all text chunks to LanceDB with the full ChunkSchema (id, book_id, section_id, path_id, text, vector, start_char, end_char, chunk_index, chunk_level, word_count, context_text). The path_id column must be present on every row to enable prefix-filtered retrieval during Atomic Fact extraction and audit validation.                                                                                                                                                                 |
| **FR-1.9**  | **SHOULD**   | The system should provide an ingestion status endpoint so the client can poll for completion.                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **FR-1.10** | **MUST NOT** | The system must not make ingested Atomic Facts or Structural Maps queryable by end users via the public API.                                                                                                                                                                                                                                                                                                                                                                                                  |

## 5.2 Anti-Passive-Reading Gates

| **ID**     | **Priority** | **Requirement**                                                                                                                                                                                       |
| ---------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-2.1** | **MUST**     | The system must reject any AuditReport request for a section where the requesting user has not yet submitted a summary. Return HTTP 403 with error code AUDIT_GATE_NO_SUBMISSION.                     |
| **FR-2.2** | **MUST**     | The system must reject summary submissions where the word count is less than the MIN_SUMMARY_WORDS threshold (configurable, default: 50 words). Return HTTP 400 with error code AUDIT_GATE_TOO_SHORT. |
| **FR-2.3** | **MUST**     | The hint generation endpoint must not be callable after a summary has already been submitted for that section. Return HTTP 409 with error code HINT_GATE_SUMMARY_EXISTS.                              |
| **FR-2.4** | **MUST**     | The system must not return Atomic Facts directly via any API endpoint, even to authenticated users.                                                                                                   |
| **FR-2.5** | **SHOULD**   | The system should apply a per-session rate limit on hint requests to discourage hint-dependency behavior (configurable via MAX_HINTS_PER_SESSION, default: 5 hint requests per section per session).  |

## 5.3 Audit & Validation

| **ID**     | **Priority** | **Requirement**                                                                                                                                                     |
| ---------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FR-3.1** | **MUST**     | The system must execute the full Three-Step Validation Flow (Retrieve → Verify → Score) for every submitted summary.                                                |
| **FR-3.2** | **MUST**     | The system must apply the weighted scoring formula using the Criticality Rank weights (Tier 1 = 3, Tier 2 = 2, Tier 3 = 1) to compute the final 0-100 score.        |
| **FR-3.3** | **MUST**     | The AuditReport must classify all unmatched facts as either Omissions (Missing) or Misconceptions (Contradicted).                                                   |
| **FR-3.4** | **MUST**     | Feedback messages in the AuditReport must use the tiered template language defined in §4.4, differentiating by Criticality Rank.                                    |
| **FR-3.5** | **MUST**     | The system must support re-audit: a user may submit a revised summary for the same section. Each submission generates a new AuditReport linked to the same section. |
| **FR-3.6** | **SHOULD**   | The system should include the score delta between the latest and previous attempt in the AuditReport for re-audits.                                                 |
| **FR-3.7** | **MUST**     | Hint generation must produce questions only, with no answers or source text excerpts included in the response.                                                      |
| **FR-3.8** | **SHOULD**   | The system should prefer Tier 1 and Tier 2 facts when generating hints, as these represent the most critical recall targets.                                        |

# 6\. Non-Functional Requirements

| **ID**      | **Category**    | **Target** | **Requirement**                                                                                                                                                                                                                                                                                                         |
| ----------- | --------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **NFR-1.1** | Performance     | < 30s      | Full ingestion pipeline for a single chapter (≤ 10,000 tokens) must complete within 30 seconds under standard load.                                                                                                                                                                                                     |
| **NFR-1.2** | Performance     | < 15s      | AuditReport generation must complete within 15 seconds of summary submission under standard load.                                                                                                                                                                                                                       |
| **NFR-1.3** | Performance     | < 5s       | Hint generation must complete within 5 seconds.                                                                                                                                                                                                                                                                         |
| **NFR-2.1** | Reliability     | ≥ 99%      | LLM API calls must implement retry logic (3 retries, exponential backoff). System must not fail permanently on transient API errors.                                                                                                                                                                                    |
| **NFR-2.2** | Reliability     | -          | LanceDB and SQLite databases must be persisted to disk. Data must survive application restarts.                                                                                                                                                                                                                         |
| **NFR-3.1** | Scalability     | -          | The path_id column in LanceDB must be used as a prefilter in all search_chunks() calls (prefilter=True) to enable efficient prefix-filtered retrieval without full-table scans.                                                                                                                                         |
| **NFR-4.1** | Security        | -          | Uploaded files must be scanned for path traversal attacks. File names must be sanitized before storage.                                                                                                                                                                                                                 |
| **NFR-4.2** | Security        | -          | Azure OpenAI credentials (azure_openai_api_key, azure_openai_endpoint, openai_api_version) must be loaded from environment variables only via the Settings class (pydantic-settings). Credentials must never be hardcoded or logged. The api_key is stored as a SecretStr to prevent accidental exposure in tracebacks. |
| **NFR-5.1** | Maintainability | -          | Domain Layer (src/core/) must remain free of all external library imports. This is enforced via CI linting rule.                                                                                                                                                                                                        |
| **NFR-5.2** | Maintainability | -          | All LLM prompts must be defined as versioned constants in a dedicated prompts.py file, not inline in service or infrastructure code.                                                                                                                                                                                    |
| **NFR-6.1** | Configurability | -          | MIN_SUMMARY_WORDS, MAX_HINTS_PER_SESSION, and LARGE_SECTION_TOKEN_THRESHOLD must be environment-variable-configurable.                                                                                                                                                                                                  |

# 7\. Technology Stack & Data Storage

## 7.1 Technology Decisions

| **Component**           | **Technology**               | **Justification**                                                                                                                                                                                                         |
| ----------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **API Framework**       | FastAPI (Python)             | Async-capable, auto-generates OpenAPI docs, Pydantic integration for request validation.                                                                                                                                  |
| **LLM Provider**        | Azure OpenAI API             | Enterprise-grade deployment via Azure. Model and API version are fully configurable via Settings (generative_model, openai_api_version). Supports JSON mode for structured extraction.                                    |
| **Embedding Model**     | Azure OpenAI Embedding Model | Configurable via embedding_model in Settings. Produces 1536-dimension vectors stored natively in LanceDB's Vector(1536) column type.                                                                                      |
| **Vector Database**     | LanceDB (local)              | Zero-infrastructure local deployment. Native columnar storage with Arrow/PyArrow backend. Supports SQL-style prefiltering on path_id and book_id before ANN vector search. Thread-safe writes via application-level lock. |
| **Relational Database** | SQLite                       | Zero-infrastructure, sufficient for Atomic Fact storage and session state. Migrate to PostgreSQL at scale.                                                                                                                |
| **PDF Parser**          | PyMuPDF (fitz)               | Preserves font metadata needed for heading detection heuristics.                                                                                                                                                          |
| **EPUB Parser**         | ebooklib                     | Standard Python EPUB parsing with NCX/NAV access.                                                                                                                                                                         |
| **File Formats**        | .pdf, .epub                  | Primary target formats for technical and non-fiction books.                                                                                                                                                               |
| **Language**            | Python 3.11+                 | Type hint support, match statements, strong ML/AI ecosystem.                                                                                                                                                              |

## 7.2 Data Storage Schema

### 7.2.1 SQLite - facts.db

- Table: atomic_facts - (id, section_id, path_id, point TEXT, rank INT, reason TEXT, created_at DATETIME). Index on (section_id, path_id).
- Table: books - (id, title, author, file_path, status, created_at).
- Table: sections - (id, book_id, path_id, parent_path_id, title, structural_map TEXT, created_at).
- Table: user_summaries - (id, user_id, section_id, text TEXT, word_count INT, attempt_number INT, submitted_at DATETIME).
- Table: audit_reports - (id, summary_id, section_id, score REAL, mastered JSON, omissions JSON, misconceptions JSON, generated_at DATETIME).

### 7.2.2 LanceDB - ./lancedb/

- Table: textbooks (configurable via vector_index_name) - Schema (ChunkSchema / LanceModel): id: str, book_id: str, section_id: str, path_id: str, text: str, vector: Vector(1536), start_char: int, end_char: int, chunk_index: int, chunk_level: str ("paragraph" | "sentence" | "word_window"), word_count: int, context_text: str | None. Filtering is applied on book_id and path_id (LIKE prefix%) as a prefilter before ANN search.

# 8\. API Reference

## 8.1 Endpoint Specification

| **Method** | **Endpoint**                    | **Auth Gate**              | **Description**                                      |
| ---------- | ------------------------------- | -------------------------- | ---------------------------------------------------- |
| **POST**   | /api/books/upload               | None                       | Upload PDF or EPUB. Initiates async ingestion.       |
| **GET**    | /api/books/{book_id}            | None                       | Retrieve book metadata and section hierarchy.        |
| **GET**    | /api/books/{book_id}/sections   | None                       | Return full section tree with path_id values.        |
| **GET**    | /api/books/ingestion/{job_id}   | None                       | Poll ingestion job status.                           |
| **POST**   | /api/audit/hints                | No prior submission        | Generate recall questions for a section.             |
| **POST**   | /api/audit/submit               | None → triggers gate check | Submit user summary. Returns AuditReport on success. |
| **GET**    | /api/audit/report/{section_id}  | Prior submission required  | Retrieve a previously generated AuditReport.         |
| **GET**    | /api/audit/history/{section_id} | None                       | List all audit attempts for a section.               |

## 8.2 Error Code Registry

| **HTTP** | **Error Code**               | **Trigger Condition**                                                               |
| -------- | ---------------------------- | ----------------------------------------------------------------------------------- |
| **400**  | **AUDIT_GATE_TOO_SHORT**     | Summary word count is below MIN_SUMMARY_WORDS threshold.                            |
| **400**  | **INVALID_FILE_TYPE**        | Uploaded file is not .pdf or .epub.                                                 |
| **403**  | **AUDIT_GATE_NO_SUBMISSION** | AuditReport requested but no prior summary submission exists for this user/section. |
| **409**  | **HINT_GATE_SUMMARY_EXISTS** | Hint requested after a summary has already been submitted for this section.         |
| **422**  | **INGESTION_FAILED**         | Document parsing failed (corrupt file, unrecognized format).                        |
| **429**  | **HINT_RATE_LIMIT_EXCEEDED** | User has exceeded MAX_HINTS_PER_SESSION for this section.                           |
| **500**  | **LLM_UNAVAILABLE**          | OpenAI API returned a non-retryable error after maximum retries exhausted.          |

# 9\. Revision History

| **Version** | **Date**       | **Author**  | **Summary of Changes**                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------- | -------------- | ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1.0         | March 27, 2026 | Khang Huynh | Initial architecture notes and high-level overview.                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **2.0**     | Apr 2, 2026    | Khang Huynh | Full SRS rewrite: Added Atomic Fact system, 3-tier hierarchy, anti-passive-reading gates, path_id system, three-step validation flow, weighted scoring formula, tiered feedback templates, full FR/NFR tables, API error registry.                                                                                                                                                                                                                                      |
| **2.1**     | Apr 11, 2026   | Claude      | Source-code sync: VectorDB updated from ChromaDB to LanceDB throughout (§1.3, §3.3.2, §7.1, §7.2.2, NFR-2.2, NFR-3.1). LLM provider updated to Azure OpenAI (§3.3.4, §7.1, NFR-4.2). ChunkSchema expanded to full 11-field definition. FR-1.6 updated to Atomic Fact extraction from LanceDB chunks. FR-1.8 updated with full schema. FR-2.5 hint limit corrected to 5 (matches config). Next step: Atomic Fact extraction pipeline from stored LanceDB chunk metadata. |
