# src/infrastructure/prompts/index/generate_structural_map.py

# STRUCTURAL MAP GENERATION

# Used by: AzureOpenAIClient.generate_structural_map()
# Triggered only for sections exceeding large_section_token_threshold (default 4 000 tokens).
# Output stored as plain text on the Chapter/Section structural_map field.

# TODO: The prompt only works for technical books

STRUCTURAL_MAP_SYSTEM = (
    "You are a technical curriculum designer. "
    "Your job is to produce concise structural maps of book sections to help "
    "readers understand the landscape of a chapter before diving in. "
    "Be precise and factual. Do not editorialize."
)

STRUCTURAL_MAP_USER = """\
-Goal-
Produce a structural map for the section below.
The map has two parts: sub-section summaries and a must-know fact list.

-Output Format-
PART 1 — SUB-SECTION SUMMARIES
One sentence per identifiable sub-section or major topic shift.
  • <sub-section title or topic>: <one-sentence summary>

PART 2 — MUST-KNOW FACTS
The 3–7 facts a reader absolutely must retain. State each precisely.
  ✦ <the fact>

Keep the entire output under 300 words. No other commentary.

######################
-Example-
######################

Example 1:
Section path: 002.001
Text: [a long chapter on sorting algorithms covering bubble sort, merge sort, and quicksort]
######################
Output:
PART 1 — SUB-SECTION SUMMARIES
  • Bubble sort: Repeatedly swaps adjacent elements until the array is sorted; simple but O(n²) in the worst case.
  • Merge sort: Recursively divides the array in half, sorts each half, then merges; guarantees O(n log n) time.
  • Quicksort: Partitions around a pivot element and recursively sorts partitions; O(n log n) average but O(n²) worst case.

PART 2 — MUST-KNOW FACTS
  ✦ Merge sort is stable and guarantees O(n log n) time regardless of input order.
  ✦ Quicksort is O(n log n) on average but degrades to O(n²) on already-sorted input with a naive pivot strategy.
  ✦ Bubble sort is O(n²) in the average and worst case and is rarely used in production.
  ✦ A stable sort preserves the relative order of equal elements; merge sort is stable, quicksort (in-place) is not.

######################
-Real Data-
######################
Text:
{text}
######################
Output:"""
