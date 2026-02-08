"""
BM25 (Okapi BM25) keyword search for x0tta6bl4 RAG pipeline.

Implements BM25 ranking algorithm for sparse (lexical) retrieval to
complement dense (vector) search in hybrid retrieval.

Reference: Robertson & Zaragoza, "The Probabilistic Relevance Framework:
BM25 and Beyond" (2009).
"""
from __future__ import annotations

import math
import re
import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)

# Common English + Russian stop words for mesh/infra context
STOP_WORDS: Set[str] = {
    # English
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "and",
    "but", "or", "nor", "not", "no", "so", "if", "then", "than",
    "too", "very", "just", "about", "up", "out", "it", "its", "this",
    "that", "these", "those", "i", "we", "you", "he", "she", "they",
    "me", "us", "him", "her", "them", "my", "our", "your", "his",
    "their", "what", "which", "who", "when", "where", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same",
}

# Simple regex tokenizer: extract word tokens
_TOKEN_RE = re.compile(r"[a-zA-Z0-9\u0400-\u04FF]+")


def tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase word tokens, removing stop words."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


@dataclass
class BM25Document:
    """Indexed document metadata."""
    doc_id: str
    term_freqs: Dict[str, int]
    length: int
    metadata: Dict = field(default_factory=dict)


class BM25Index:
    """
    BM25 (Okapi BM25) index for keyword-based document retrieval.

    Parameters:
        k1: Term frequency saturation. Higher = more weight to term frequency.
            Typical range: 1.2 - 2.0
        b: Length normalization. 0 = no normalization, 1 = full normalization.
            Typical range: 0.5 - 0.8
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._documents: List[BM25Document] = []
        self._doc_id_to_idx: Dict[str, int] = {}
        # Inverted index: term -> set of doc indices
        self._inverted: Dict[str, Set[int]] = {}
        # Document frequency: term -> number of docs containing term
        self._df: Dict[str, int] = {}
        self._total_length: int = 0
        self._avg_dl: float = 0.0

    @property
    def num_documents(self) -> int:
        return len(self._documents)

    def add(self, text: str, doc_id: str, metadata: Optional[Dict] = None):
        """Add a document to the index."""
        tokens = tokenize(text)
        tf = Counter(tokens)

        if doc_id in self._doc_id_to_idx:
            # Update existing document
            idx = self._doc_id_to_idx[doc_id]
            old_doc = self._documents[idx]
            # Remove old term contributions
            for term in old_doc.term_freqs:
                if term in self._inverted:
                    self._inverted[term].discard(idx)
                    if not self._inverted[term]:
                        del self._inverted[term]
                self._df[term] = self._df.get(term, 1) - 1
                if self._df.get(term, 0) <= 0:
                    self._df.pop(term, None)
            self._total_length -= old_doc.length

            doc = BM25Document(
                doc_id=doc_id,
                term_freqs=dict(tf),
                length=len(tokens),
                metadata=metadata or {},
            )
            self._documents[idx] = doc
        else:
            idx = len(self._documents)
            doc = BM25Document(
                doc_id=doc_id,
                term_freqs=dict(tf),
                length=len(tokens),
                metadata=metadata or {},
            )
            self._documents.append(doc)
            self._doc_id_to_idx[doc_id] = idx

        # Update inverted index and df
        for term in tf:
            if term not in self._inverted:
                self._inverted[term] = set()
            self._inverted[term].add(idx)
            self._df[term] = len(self._inverted[term])

        self._total_length += doc.length
        self._avg_dl = self._total_length / len(self._documents) if self._documents else 0.0

    def search(self, query: str, k: int = 10) -> List[Tuple[str, float, Dict]]:
        """
        Search the index using BM25 scoring.

        Args:
            query: Search query string.
            k: Maximum number of results.

        Returns:
            List of (doc_id, score, metadata) tuples sorted by score descending.
        """
        query_tokens = tokenize(query)
        if not query_tokens or not self._documents:
            return []

        n = len(self._documents)
        scores: Dict[int, float] = {}

        for term in query_tokens:
            if term not in self._inverted:
                continue

            df = self._df.get(term, 0)
            # IDF with smoothing (Robertson-Walker variant)
            idf = math.log((n - df + 0.5) / (df + 0.5) + 1.0)

            for idx in self._inverted[term]:
                doc = self._documents[idx]
                tf = doc.term_freqs.get(term, 0)
                dl = doc.length

                # BM25 term score
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * dl / self._avg_dl)
                term_score = idf * numerator / denominator

                scores[idx] = scores.get(idx, 0.0) + term_score

        # Sort by score descending, take top k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]

        results = []
        for idx, score in ranked:
            doc = self._documents[idx]
            results.append((doc.doc_id, score, doc.metadata))

        return results

    def get_stats(self) -> Dict:
        return {
            "num_documents": self.num_documents,
            "vocabulary_size": len(self._df),
            "avg_document_length": round(self._avg_dl, 1),
            "k1": self.k1,
            "b": self.b,
        }


def reciprocal_rank_fusion(
    result_lists: List[List[Tuple[str, float, Dict]]],
    k: int = 60,
    top_n: int = 10,
) -> List[Tuple[str, float, Dict]]:
    """
    Reciprocal Rank Fusion (RRF) to combine multiple ranked lists.

    RRF score = sum over lists: 1 / (k + rank)

    Reference: Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion
    outperforms Condorcet and individual Rank Learning Methods" (SIGIR 2009).

    Args:
        result_lists: List of result lists, each is [(doc_id, score, metadata), ...]
        k: Smoothing constant (default 60, as in original paper).
        top_n: Number of results to return.

    Returns:
        Fused list of (doc_id, rrf_score, metadata) sorted by RRF score.
    """
    rrf_scores: Dict[str, float] = {}
    metadata_map: Dict[str, Dict] = {}

    for results in result_lists:
        for rank, (doc_id, _score, meta) in enumerate(results):
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            if doc_id not in metadata_map:
                metadata_map[doc_id] = meta

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [(doc_id, score, metadata_map.get(doc_id, {})) for doc_id, score in ranked]
