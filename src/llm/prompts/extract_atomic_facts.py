ATOMIC_FACT_SYSTEM = (
    "You are a precision knowledge extraction engine for technical books. "
    "Your sole output is a valid JSON array of atomic knowledge claims extracted "
    "from the BODY TEXT of a provided chunk. "
    "Each claim must be independently true, testable, and non-redundant. "
    "Output ONLY a valid JSON array. No preamble, no markdown fences, no commentary."
)

ATOMIC_FACT_USER = """\
-Goal-
Extract high-value atomic knowledge claims from the BODY TEXT of the chunk below.
The chunk may include a breadcrumb header ([Book > Chapter > Section]) and overlap
text from the previous chunk — IGNORE these; extract only from the BODY TEXT
(the content after the header line).

Return AT MOST {max_facts} facts. Fewer is better — omit anything already implied
by a higher-ranked fact, trivially inferable by a competent reader, or that merely
restates the overlap/header context.

-Budget-
Rank 1 (CRITICAL):  2 facts maximum. Foundational logic and core definitions only.
Rank 2 (IMPORTANT): 2–3 facts maximum. Specific numbers, thresholds, named rules,
                     or formal distinctions with applied consequences.
Rank 3 (NUANCE):    0–1 facts maximum. Only if genuinely non-obvious to a domain expert.

Total cap: {max_facts} facts. If rank budgets sum to more than {max_facts},
drop the lowest-ranked facts first. Never pad to hit the budget.

-Ranking Rules-
Rank 1 (CRITICAL)  — If a reader misses this, the rest of the section is incoherent.
                      Core definitions, primary mechanisms, essential preconditions.
Rank 2 (IMPORTANT) — Required for applied or professional understanding.
                      Specific numbers, thresholds, contraindications, formal boundaries,
                      named rules, or distinctions that govern real decisions.
Rank 3 (NUANCE)    — Demonstrates mastery but not required for basic competency.
                      Historical context, secondary analogies, supporting examples.

-Claim Rules-
  • One discrete idea per claim — no conjunctions smuggling two facts into one sentence.
  • State the claim as a self-contained, universally true declarative sentence.
  • Do not reference the text, the author, or the chunk ("The text states…", "According to…").
  • Do not include definitional padding ("X is important because…") — state the fact directly.
  • If a claim is only true within a narrow scope, make that scope explicit in the claim.

-Question Rules-
  • 1–2 questions per fact, probing exactly and only that fact.
  • Open-ended only: "How…", "What…", "Under what conditions…". No yes/no questions.
  • Questions must be self-contained — answerable without re-reading the chunk.
  • Do not quote, closely paraphrase, or structurally mirror the claim inside the question.
  • The question must not contain the answer, nor any term that makes the answer
    immediately obvious (e.g., do not ask "What is the O(log n) complexity of…").
  • Each question must be answerable differently — do not write two questions that
    accept the same answer.

-Span Rules-
  • start_char and end_char are zero-based character indices into the BODY TEXT only
    (exclude the header line and overlap prefix when counting).
  • body_text[start_char:end_char] must reproduce the grounding passage verbatim.
  • Span the smallest contiguous substring that fully supports the claim.
  • When a claim is grounded by multiple non-contiguous sentences, span from the
    first character of the earliest to the last character of the latest
    (include intervening text rather than leaving a gap).
  • Never span the entire body text — keep spans as tight as possible.

-Deduplication-
  • The chunk may overlap with adjacent chunks. If a fact is near-identical to one
    that would clearly appear in a neighbouring chunk (e.g., it comes entirely from
    the overlap prefix), mark it with "from_overlap": true so downstream deduplication
    can filter it. Otherwise omit the field.

-Exclusions-
  • Filler and transitional sentences with no standalone knowledge value.
  • Claims that merely restate the section title or breadcrumb.
  • Hyper-specific minutiae unlikely to appear in any reasonable summary or exam.
  • Duplicate or near-duplicate claims within the same output array.

-Output Schema-
Each element must follow this exact shape (no extra fields unless noted):
{{
  "point":         "Declarative claim sentence.",
  "rank":          1,
  "reason":        "One sentence explaining why this rank was assigned.",
  "questions":     ["Primary question?", "Alternative question?"],
  "start_char":    0,
  "end_char":      42,
  "from_overlap":  true   // OPTIONAL — include only when true
}}

######################
-Examples-
######################

Example 1:
Section path: 001.002
Chunk token count: 312
Body text:
Binary search is an algorithm that finds the position of a target value within a sorted
array. It works by repeatedly halving the search space: compare the target to the middle
element, then discard the half where the target cannot lie. This continues until the target
is found or the search space is empty. The algorithm runs in O(log n) time, making it
dramatically faster than linear search for large datasets. John Mauchly described a
similar technique in 1946, though the first bug-free published version appeared in 1962.
######################
Output:
[
  {{"point": "Binary search requires the input array to be sorted before it can be applied.", "rank": 1, "reason": "Core precondition — applying binary search to unsorted data yields incorrect results, making this a prerequisite for all other algorithmic reasoning in this section.", "questions": ["What property must the input data possess before binary search can operate correctly?", "What is the consequence of applying binary search to data that violates its input requirement?"], "start_char": 0, "end_char": 88}},
  {{"point": "Binary search halves the search space at each step by discarding the half that cannot contain the target.", "rank": 1, "reason": "Primary mechanism — without understanding the halving logic, the O(log n) complexity and termination condition are both incoherent.", "questions": ["What decision is made at each step of binary search to reduce the remaining search space?", "How does the algorithm ensure the discarded half cannot contain the target value?"], "start_char": 90, "end_char": 262}},
  {{"point": "Binary search runs in O(log n) time.", "rank": 2, "reason": "Precision threshold — the specific complexity class is what makes binary search preferable to O(n) linear search at scale.", "questions": ["How does the time complexity of binary search scale relative to the size of the input?", "At what input sizes does the complexity advantage of binary search over linear search become significant?"], "start_char": 264, "end_char": 381}},
  {{"point": "The first correct published implementation of binary search appeared 16 years after the concept was first described.", "rank": 3, "reason": "Historical nuance illustrating the gap between algorithm description and correct implementation — non-obvious and memorable but not required for competency.", "questions": ["What does the publication history of binary search suggest about the relationship between describing and correctly implementing an algorithm?"], "start_char": 383, "end_char": 497}}
]

######################

Example 2:
Section path: 003.001
Chunk token count: 287
Body text:
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
  {{"point": "A TCP connection requires a three-step SYN → SYN-ACK → ACK exchange to complete before any application data can be transmitted.", "rank": 1, "reason": "Core mechanism — the handshake sequence is the defining characteristic of TCP connection establishment; all other TCP behaviour follows from it.", "questions": ["What sequence of messages must two hosts exchange before a TCP connection is ready to carry application data?", "Why must the handshake complete before data transmission begins, rather than allowing data to be piggybacked on the handshake itself?"], "start_char": 0, "end_char": 362}},
  {{"point": "TCP guarantees both delivery and ordering of segments; UDP provides neither guarantee.", "rank": 2, "reason": "Formal distinction — this difference is the basis for every TCP-vs-UDP protocol selection decision in practice.", "questions": ["How do TCP and UDP differ in what they promise about data arriving at the destination?", "What reliability properties does a protocol sacrifice when choosing UDP over TCP?"], "start_char": 364, "end_char": 434}},
  {{"point": "UDP is preferable over TCP for latency-sensitive applications because it eliminates handshake and retransmission overhead.", "rank": 3, "reason": "Applied nuance — a practical corollary of the TCP/UDP distinction; useful for engineering decisions but secondary to understanding the protocols.", "questions": ["Under what application requirements would UDP be chosen despite offering no delivery guarantees?", "What specific TCP mechanisms does UDP omit that make it better suited for real-time data streams?"], "start_char": 364, "end_char": 497}}
]

######################
-Real Data-
######################
Chunk token count: {chunk_token_count}
Body text:
{body_text}
######################
Output:"""
