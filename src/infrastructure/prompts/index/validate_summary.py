# src/infrastructure/llm/prompts/index/validate_summary.py

# FACT VALIDATION / ENTAILMENT

# Used by: AzureOpenAIClient.validate_facts()
# Classifies each AtomicFact as Found | Partial | Missing | Contradicted.
# Output: raw JSON array parallel to the input facts list.

VALIDATION_SYSTEM = (
    "You are a precise semantic entailment evaluator for an educational platform. "
    "You will be given a user's recall summary and a list of atomic facts from the "
    "source material. For each fact, determine whether the summary supports, partially "
    "supports, omits, or contradicts it. "
    "Base your judgment solely on what is written in the summary — do not infer "
    "knowledge the user did not express."
)

VALIDATION_USER = """\
-Goal-
Evaluate how well the user's summary covers each atomic fact listed below.
Return a classification for every fact. Base your judgment only on what the user
actually wrote — do not award credit for knowledge they did not express.

-Status Definitions-
  Found        — The summary clearly and correctly expresses this fact (accuracy 1.0).
  Partial      — The summary touches the concept but lacks precision or completeness (accuracy 0.5).
  Missing      — The summary does not address this fact at all (accuracy 0.0).
  Contradicted — The summary states something that directly conflicts with this fact
                 (accuracy 0.0, flagged as a Misconception in the report).

-Output Schema-
Return ONLY a JSON array, one object per fact, in the same order as the input list.
Each object must follow this exact shape:
{{"fact_id": "...", "status": "Found|Partial|Missing|Contradicted", "evidence": "...", "confidence": 0.0}}

  fact_id    — copy the id field from the fact verbatim
  evidence   — short quote or paraphrase from the summary supporting your classification;
               use "" if status is Missing
  confidence — float 0.0–1.0 representing your certainty in the classification

######################
-Examples-
######################

Example 1:
User summary:
"Binary search splits the array in half each time, which makes it very fast —
 much faster than going through every element. It does need the data to be in order first."

Facts:
[
  {{"id": "f-001", "point": "Binary search requires the input array to be sorted.", "rank": 1}},
  {{"id": "f-002", "point": "Binary search runs in O(log n) time.", "rank": 2}},
  {{"id": "f-003", "point": "The first bug-free version was published in 1962.", "rank": 3}}
]
######################
Output:
[
  {{"fact_id": "f-001", "status": "Found",   "evidence": "It does need the data to be in order first", "confidence": 0.97}},
  {{"fact_id": "f-002", "status": "Partial",  "evidence": "makes it very fast — much faster than going through every element", "confidence": 0.85}},
  {{"fact_id": "f-003", "status": "Missing",  "evidence": "", "confidence": 0.99}}
]

######################

Example 2:
User summary:
"TCP sends data without any handshake, which is why it's used for streaming video
 where speed matters more than reliability."

Facts:
[
  {{"id": "f-010", "point": "The TCP three-way handshake (SYN → SYN-ACK → ACK) must complete before any data is exchanged.", "rank": 1}},
  {{"id": "f-011", "point": "UDP, not TCP, is preferred for latency-sensitive applications like video streaming.", "rank": 3}}
]
######################
Output:
[
  {{"fact_id": "f-010", "status": "Contradicted", "evidence": "TCP sends data without any handshake", "confidence": 0.98}},
  {{"fact_id": "f-011", "status": "Contradicted", "evidence": "it's used for streaming video where speed matters more than reliability", "confidence": 0.95}}
]

######################
-Real Data-
######################
User summary:
{summary}

Facts:
{facts}
######################
Output:"""
