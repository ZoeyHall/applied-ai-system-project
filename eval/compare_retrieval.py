"""Before/after comparison of the care-guide index.

    python eval/compare_retrieval.py

"Before": a naive index with one chunk per file, no species filter. The top
result is a whole document, so the model receives every section in it.
"After": the custom section-level index with species metadata (retriever.py).

For each question, both indexes return their top result. We measure whether
that result contains the answer's section and how many words of context the
model has to read. Less irrelevant context means fewer tokens and less room
for the model to mix up facts (e.g. dog vs cat grooming intervals).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from retriever import CareGuideRetriever, Chunk  # noqa: E402
from run_eval import RETRIEVAL_CASES  # noqa: E402


def build_file_level(section_index: CareGuideRetriever) -> CareGuideRetriever:
    """Rebuild the same BM25 index with one chunk per file instead of per section."""
    by_file: dict[str, list[Chunk]] = {}
    for chunk in section_index.chunks:
        by_file.setdefault(chunk.source, []).append(chunk)
    merged = [
        Chunk(source, "(whole file)", "all", "\n".join(f"{c.heading}. {c.text}" for c in chunks))
        for source, chunks in by_file.items()
    ]
    return CareGuideRetriever(chunks=merged)


def main() -> None:
    after = CareGuideRetriever()
    before = build_file_level(after)

    print(f"{'QUESTION':<46} {'BEFORE (file-level)':<28} {'AFTER (section-level)':<28}")
    print("-" * 102)
    totals = {"before_hit": 0, "after_hit": 0, "before_words": 0, "after_words": 0}
    for query, species, citation in RETRIEVAL_CASES:
        source = citation.split(">")[0].strip()

        b_chunk = before.search(query, k=1)[0][0]
        b_hit = b_chunk.source == source  # the right file contains the section
        b_words = len(b_chunk.text.split())

        a_chunk = after.search(query, species=species, k=1)[0][0]
        a_hit = a_chunk.citation == citation
        a_words = len(a_chunk.text.split())

        totals["before_hit"] += b_hit
        totals["after_hit"] += a_hit
        totals["before_words"] += b_words
        totals["after_words"] += a_words
        print(
            f"{query[:45]:<46} {('hit' if b_hit else 'MISS') + f', {b_words} words':<28} "
            f"{('hit' if a_hit else 'MISS') + f', {a_words} words':<28}"
        )

    n = len(RETRIEVAL_CASES)
    print("-" * 102)
    print(f"Top result contains the answer: before {totals['before_hit']}/{n}, after {totals['after_hit']}/{n}")
    print(
        f"Average context per question:   before {totals['before_words'] / n:.0f} words, "
        f"after {totals['after_words'] / n:.0f} words "
        f"({1 - totals['after_words'] / totals['before_words']:.0%} less)"
    )


if __name__ == "__main__":
    main()
