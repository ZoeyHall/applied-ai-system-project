"""Retrieval over the PawPal+ care guide (the "R" in RAG).

The knowledge base is a folder of Markdown files in knowledge/. Each file
starts with a small header naming the species it applies to ("dog", "cat",
or "all"), and is split into one chunk per "## " section. That custom,
section-level index lets search return a focused paragraph with a citable
source ("cat_care.md > Litter box care") instead of a whole file.

Scoring is BM25, a standard keyword-ranking formula, implemented here with no
extra dependencies so the project stays easy to install.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does",
    "for", "from", "how", "i", "if", "in", "is", "it", "its", "my", "of", "on",
    "or", "should", "so", "that", "the", "their", "them", "there", "this", "to",
    "what", "when", "which", "who", "why", "will", "with", "you", "your", "me",
    "we", "our", "much", "many", "often", "get", "need", "needs",
}


def stem(word: str) -> str:
    """Very light suffix stripping so "feeding", "feeds" and "feed" all match.

    Good enough for this small corpus; a full stemmer (e.g. Porter) would be
    the next step for a larger one.
    """
    if len(word) > 5 and word.endswith("ing"):
        word = word[:-3]  # "feeding" -> "feed", "brushing" -> "brush"
    elif len(word) > 4 and word.endswith("ed") and not word.endswith("eed"):
        word = word[:-2]  # "trimmed" -> "trimm", "scooped" -> "scoop"
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]  # "walks" -> "walk"
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "ls":
        word = word[:-1]  # "trimm" -> "trim", "grooming" stays "groom"
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase, stemmed words with stopwords removed."""
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


@dataclass
class Chunk:
    """One "## " section of a care-guide document."""

    source: str  # file name, e.g. "cat_care.md"
    heading: str  # section heading, e.g. "Litter box care"
    species: str  # "dog", "cat", or "all"
    text: str

    @property
    def citation(self) -> str:
        return f"{self.source} > {self.heading}"


def parse_document(path: Path) -> list[Chunk]:
    """Split one Markdown file into section chunks, reading its species header."""
    raw = path.read_text(encoding="utf-8")
    species = "all"
    header = re.match(r"^---\n(.*?)\n---\n", raw, re.DOTALL)
    if header:
        for line in header.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "species":
                species = value.strip().lower()
        raw = raw[header.end():]

    chunks = []
    for section in re.split(r"^## ", raw, flags=re.MULTILINE)[1:]:
        heading, _, body = section.partition("\n")
        chunks.append(Chunk(path.name, heading.strip(), species, body.strip()))
    return chunks


class CareGuideRetriever:
    """BM25 search over section chunks, with optional species filtering."""

    def __init__(
        self,
        knowledge_dir: Path = KNOWLEDGE_DIR,
        chunks: list[Chunk] | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        """Index every section in knowledge_dir, or a ready-made list of chunks if given."""
        if chunks is not None:
            self.chunks = list(chunks)
        else:
            self.chunks = []
            for path in sorted(knowledge_dir.glob("*.md")):
                self.chunks.extend(parse_document(path))
        if not self.chunks:
            raise FileNotFoundError(f"No care-guide documents found in {knowledge_dir}")

        self.k1, self.b = k1, b
        # Index the heading twice so a heading match counts for more than a passing mention.
        self._docs = [tokenize(f"{c.heading} {c.heading} {c.text}") for c in self.chunks]
        self._tf = [Counter(doc) for doc in self._docs]
        self._avg_len = sum(len(d) for d in self._docs) / len(self._docs)
        df = Counter(term for doc in self._docs for term in set(doc))
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _score(self, query_terms: list[str], i: int) -> float:
        tf, length = self._tf[i], len(self._docs[i])
        score = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            freq = tf[term]
            norm = freq * (self.k1 + 1) / (freq + self.k1 * (1 - self.b + self.b * length / self._avg_len))
            score += self._idf.get(term, 0.0) * norm
        return score

    def search(self, query: str, species: str | None = None, k: int = 3) -> list[tuple[Chunk, float]]:
        """Return up to k (chunk, score) pairs that match the query, best first.

        Args:
            query: The question or keywords to look up.
            species: "dog" or "cat" to search only that species' guide plus the
                general ("all") guides. None or anything else searches everything.
            k: Maximum number of results.

        Returns:
            Matching chunks with a score above zero. An empty list means the
            guide has nothing relevant, which the agent must say rather than guess.
        """
        terms = tokenize(query)
        species = (species or "").lower()
        results = []
        for i, chunk in enumerate(self.chunks):
            if species in ("dog", "cat") and chunk.species not in (species, "all"):
                continue
            score = self._score(terms, i)
            if score > 0:
                results.append((chunk, score))
        results.sort(key=lambda item: item[1], reverse=True)
        return results[:k]

    def format_results(self, results: list[tuple[Chunk, float]]) -> str:
        """Render search results as text the model can read and cite."""
        if not results:
            return "No relevant care-guide sections found."
        return "\n\n".join(f"[{chunk.citation}]\n{chunk.text}" for chunk, _ in results)
