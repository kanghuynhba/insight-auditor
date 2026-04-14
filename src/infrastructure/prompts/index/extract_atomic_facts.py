# src/infrastructure/prompts/index/extract_atomic_facts.py

# ATOMIC FACT EXTRACTION

# Used by: AzureOpenAIClient.generate_atomic_facts()
# Input:   full reconstructed section text + its path_id
# Output:  raw JSON array — no preamble, no markdown fences

# TODO: The prompt only works for technical books

ATOMIC_FACT_SYSTEM = (
    "You are an expert knowledge extraction engine for technical books. "
    "Extract discrete, atomic knowledge claims from the provided text. "
    "For each claim, assign a Criticality Rank (1-3) and output ONLY a valid "
    "JSON array. No preamble, no markdown fences."
)

ATOMIC_FACT_USER = """\
-Goal-
Extract every discrete, atomic knowledge claim from the section text below.
For each claim assign a Criticality Rank and return ONLY a valid JSON array.

-Ranking Rules-
Rank 1 (CRITICAL)  — Foundational logic, core definitions, primary mechanisms.
                     If a reader misses this, the rest of the section is incoherent.
Rank 2 (IMPORTANT) — Technical precision: specific numbers, thresholds,
                     contraindications, named rules, or legal/formal boundaries.
                     Essential for applied or professional understanding.
Rank 3 (NUANCE)    — Supporting detail: examples, historical context,
                     secondary analogies. Demonstrates mastery but not vital
                     for basic competency.

-Exclusions-
Exclude filler phrases, transitional sentences with no standalone knowledge value,
duplicate claims, and hyper-specific minutiae unlikely to appear in any reasonable summary.

-Output Schema-
Each element of the JSON array must follow this exact shape:
{{"point": "...", "rank": 1, "reason": "..."}}

######################
-Examples-
######################

Example 1:
Section path: 001.002
Text:
Binary search is an algorithm that finds the position of a target value within a sorted
array. It works by repeatedly halving the search space: compare the target to the middle
element, then discard the half where the target cannot lie. This continues until the target
is found or the search space is empty. The algorithm runs in O(log n) time, making it
dramatically faster than linear search for large datasets. John Mauchly described a
similar technique in 1946, though the first bug-free published version appeared in 1962.
######################
Output:
[
  {{"point": "Binary search requires the input array to be sorted before it can be applied.", "rank": 1, "reason": "Core precondition — the algorithm produces incorrect results on unsorted input."}},
  {{"point": "Binary search works by repeatedly halving the search space and discarding the half that cannot contain the target.", "rank": 1, "reason": "Primary mechanism — understanding this is required for the rest of the algorithm to make sense."}},
  {{"point": "Binary search runs in O(log n) time.", "rank": 2, "reason": "Precision threshold — the specific complexity distinguishes it from O(n) linear search."}},
  {{"point": "The first bug-free published version of binary search appeared in 1962, despite the concept being described by Mauchly in 1946.", "rank": 3, "reason": "Historical nuance — useful context but not required for algorithmic competency."}}
]

######################

Example 2:
Section path: 003.001
Text:
The TCP three-way handshake establishes a reliable connection between two hosts before
any data is exchanged. The initiating host sends a SYN segment. The responding host
replies with a SYN-ACK, simultaneously acknowledging the SYN and sending its own
synchronisation request. The initiating host completes the handshake with an ACK.
Only after this exchange do the hosts begin transmitting application data. TCP guarantees
delivery and ordering of segments; UDP does not, which makes UDP preferable for
latency-sensitive applications like video streaming.
######################
Output:
[
  {{"point": "The TCP three-way handshake (SYN → SYN-ACK → ACK) must complete before any application data is exchanged.", "rank": 1, "reason": "Core mechanism — the entire concept of TCP connection establishment depends on this sequence."}},
  {{"point": "TCP guarantees delivery and ordering of segments; UDP does not.", "rank": 2, "reason": "Critical distinction — this formal difference determines protocol selection in practice."}},
  {{"point": "UDP is preferable over TCP for latency-sensitive applications such as video streaming.", "rank": 3, "reason": "Applied nuance — a practical consequence of the TCP/UDP distinction, but secondary to understanding the protocols themselves."}}
]

######################
-Real Data-
######################
Section path: {path_id}
Text:
{text}
######################
Output:"""
