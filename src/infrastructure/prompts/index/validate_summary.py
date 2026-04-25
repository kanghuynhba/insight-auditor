# validate_summary.py

VALIDATION_SYSTEM = (
    "You are a precise semantic entailment evaluator for an educational platform. "
    "You will be given a user's recall summary and a list of atomic facts from the "
    "source material. For each fact, determine whether the summary supports, partially "
    "supports, omits, or contradicts it. "
    "Base your judgment solely on what is written in the summary — do not infer "
    "knowledge the user did not express. "
    "When a previous attempt is provided, use it only to assess improvement or regression — "
    "never award credit based on what the user wrote previously."
)

# Rendered when a previous attempt exists
PREVIOUS_ATTEMPT_BLOCK = """\
-Previous Attempt (attempt #{attempt_number})-
Use this context to evaluate improvement or regression per fact.
Do NOT award credit based on anything written here — only the current summary counts.

Previous summary:
{previous_summary}

Previous report:
  Score: {score} | Misconceptions: {misconceptions} | Omissions: {omissions}

######################
"""

# Rendered when this is the user's first attempt
FIRST_ATTEMPT_BLOCK = """\
-Attempt Context-
This is the user's FIRST attempt. There is no previous summary or report.
Set "improved" to null for every fact.

######################
"""

VALIDATION_USER = """\
-Goal-
Evaluate how well the user's summary covers each atomic fact listed below.
Return a classification for every fact. Base your judgment only on what the user
actually wrote in the CURRENT summary — do not award credit for knowledge they did not express.

The summary must be at least 50 words. If it is shorter, return every fact as Missing
with evidence "" and confidence 1.0.

{attempt_context_block}\
-Status Definitions-
  Found        — The summary clearly and correctly expresses this fact (accuracy 1.0).
  Partial      — The summary touches the concept but lacks precision or completeness (accuracy 0.5).
  Missing      — The summary does not address this fact at all (accuracy 0.0).
  Contradicted — The summary states something that directly conflicts with this fact
                 (accuracy 0.0, flagged as a Misconception in the report).

-Output Schema-
Return ONLY a JSON array, one object per fact, in the same order as the input list.
Each object must follow this exact shape:
{{"fact_id": "...", "status": "Found|Partial|Missing|Contradicted", "evidence": "...", "confidence": 0.0, "improved": null}}

  fact_id    — copy the id field from the fact verbatim
  evidence   — short quote or paraphrase from the summary supporting your classification;
               use "" if status is Missing
  confidence — float 0.0–1.0 representing your certainty in the classification
  improved   — null if this is the first attempt; true if the user improved on this fact
               vs the previous attempt; false if they regressed or stayed the same

######################
-Examples-
######################
Example 1 (first attempt):
{first_attempt_block_example}\
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
  {{"fact_id": "f-001", "status": "Found",   "evidence": "It does need the data to be in order first", "confidence": 0.97, "improved": null}},
  {{"fact_id": "f-002", "status": "Partial",  "evidence": "makes it very fast — much faster than going through every element", "confidence": 0.85, "improved": null}},
  {{"fact_id": "f-003", "status": "Missing",  "evidence": "", "confidence": 0.99, "improved": null}}
]
######################
Example 2 (retry — previous attempt provided):
{previous_attempt_block_example}\
Current summary:
"TCP uses a three-way handshake before exchanging data. UDP is the better choice
 for video streaming since it's faster."
Facts:
[
  {{"id": "f-010", "point": "The TCP three-way handshake (SYN → SYN-ACK → ACK) must complete before any data is exchanged.", "rank": 1}},
  {{"id": "f-011", "point": "UDP, not TCP, is preferred for latency-sensitive applications like video streaming.", "rank": 3}}
]
######################
Output:
[
  {{"fact_id": "f-010", "status": "Found",  "evidence": "TCP uses a three-way handshake before exchanging data", "confidence": 0.96, "improved": true}},
  {{"fact_id": "f-011", "status": "Found",  "evidence": "UDP is the better choice for video streaming since it's faster", "confidence": 0.93, "improved": true}}
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

# Static example blocks rendered inside the examples section
_FIRST_ATTEMPT_BLOCK_EXAMPLE = """\
-Attempt Context-
This is the user's FIRST attempt. There is no previous summary or report.
Set "improved" to null for every fact.

"""

_PREVIOUS_ATTEMPT_BLOCK_EXAMPLE = """\
-Previous Attempt (attempt #1)-
Previous summary:
"TCP sends data without any handshake, which is why it's used for streaming video
 where speed matters more than reliability."
Previous report:
  Score: 0.0 | Misconceptions: f-010, f-011 | Omissions: (none)

"""
