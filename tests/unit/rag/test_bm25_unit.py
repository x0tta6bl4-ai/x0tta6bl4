"""
Unit tests for BM25 keyword search and RRF hybrid fusion.
"""

import pytest

from src.rag.bm25 import BM25Index, reciprocal_rank_fusion, tokenize


class TestTokenize:
    def test_basic_tokenization(self):
        tokens = tokenize("Hello World test")
        assert "hello" in tokens
        assert "world" in tokens
        assert "test" in tokens

    def test_stop_words_removed(self):
        tokens = tokenize("the quick brown fox is a very fast animal")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "a" not in tokens
        assert "very" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_single_char_removed(self):
        tokens = tokenize("I am a test x y z")
        assert "x" not in tokens
        assert "y" not in tokens
        assert "z" not in tokens

    def test_case_insensitive(self):
        tokens = tokenize("UPPERCASE lowercase MiXeD")
        assert "uppercase" in tokens
        assert "lowercase" in tokens
        assert "mixed" in tokens

    def test_cyrillic(self):
        tokens = tokenize("mesh сеть узел")
        assert "mesh" in tokens
        assert "сеть" in tokens
        assert "узел" in tokens


class TestBM25Index:
    def test_add_and_search(self):
        idx = BM25Index()
        idx.add("mesh network self healing nodes", "doc1")
        idx.add("post quantum cryptography encryption", "doc2")
        idx.add("federated learning machine training", "doc3")

        results = idx.search("mesh network", k=3)
        assert len(results) > 0
        assert results[0][0] == "doc1"  # doc1 should rank highest

    def test_search_empty_index(self):
        idx = BM25Index()
        results = idx.search("test query")
        assert results == []

    def test_search_no_match(self):
        idx = BM25Index()
        idx.add("hello world", "doc1")
        results = idx.search("zzzzzzzzzzz")
        assert results == []

    def test_search_returns_scores(self):
        idx = BM25Index()
        idx.add("mesh network nodes topology routing", "doc1")
        idx.add("database postgresql query optimizer", "doc2")
        results = idx.search("mesh network topology")
        assert len(results) > 0
        doc_id, score, meta = results[0]
        assert doc_id == "doc1"
        assert score > 0

    def test_search_ranking_order(self):
        idx = BM25Index()
        idx.add("mesh mesh mesh network", "doc_high")
        idx.add("mesh single mention", "doc_low")
        results = idx.search("mesh")
        # doc_high should score higher (more term frequency)
        assert results[0][0] == "doc_high"

    def test_metadata_preserved(self):
        idx = BM25Index()
        idx.add("test document", "doc1", metadata={"source": "file.md"})
        results = idx.search("test document")
        assert results[0][2]["source"] == "file.md"

    def test_num_documents(self):
        idx = BM25Index()
        assert idx.num_documents == 0
        idx.add("doc one", "d1")
        idx.add("doc two", "d2")
        assert idx.num_documents == 2

    def test_get_stats(self):
        idx = BM25Index()
        idx.add("hello world test", "d1")
        idx.add("world test again", "d2")
        stats = idx.get_stats()
        assert stats["num_documents"] == 2
        assert stats["vocabulary_size"] > 0
        assert stats["avg_document_length"] > 0

    def test_update_existing_document(self):
        idx = BM25Index()
        idx.add("old content here", "doc1")
        idx.add("new content replaced", "doc1")
        assert idx.num_documents == 1
        results = idx.search("new content replaced")
        assert len(results) > 0
        assert results[0][0] == "doc1"

    def test_top_k_limit(self):
        idx = BM25Index()
        for i in range(20):
            idx.add(f"document about mesh networking node {i}", f"doc{i}")
        results = idx.search("mesh networking", k=5)
        assert len(results) <= 5

    def test_idf_effect(self):
        """Rare terms should score higher than common terms."""
        idx = BM25Index()
        # 'mesh' appears in all docs, 'quantum' only in doc2
        idx.add("mesh network common", "doc1")
        idx.add("mesh quantum rare", "doc2")
        idx.add("mesh network common again", "doc3")
        results = idx.search("quantum")
        assert len(results) == 1
        assert results[0][0] == "doc2"


class TestReciprocalRankFusion:
    def test_basic_fusion(self):
        list1 = [("d1", 0.9, {}), ("d2", 0.8, {}), ("d3", 0.7, {})]
        list2 = [("d2", 0.95, {}), ("d1", 0.85, {}), ("d4", 0.75, {})]

        fused = reciprocal_rank_fusion([list1, list2], top_n=4)
        doc_ids = [r[0] for r in fused]
        # d1 and d2 appear in both lists -> should be top
        assert "d1" in doc_ids[:2]
        assert "d2" in doc_ids[:2]

    def test_empty_lists(self):
        fused = reciprocal_rank_fusion([[], []])
        assert fused == []

    def test_single_list(self):
        list1 = [("d1", 0.9, {"a": 1}), ("d2", 0.8, {"b": 2})]
        fused = reciprocal_rank_fusion([list1], top_n=2)
        assert len(fused) == 2
        assert fused[0][0] == "d1"

    def test_top_n_limit(self):
        list1 = [("d1", 0.9, {}), ("d2", 0.8, {}), ("d3", 0.7, {})]
        fused = reciprocal_rank_fusion([list1], top_n=2)
        assert len(fused) == 2

    def test_metadata_preserved(self):
        list1 = [("d1", 0.9, {"source": "vec"})]
        list2 = [("d2", 0.8, {"source": "bm25"})]
        fused = reciprocal_rank_fusion([list1, list2], top_n=2)
        meta_map = {r[0]: r[2] for r in fused}
        assert meta_map["d1"]["source"] == "vec"
        assert meta_map["d2"]["source"] == "bm25"

    def test_overlapping_results_boost(self):
        """Documents appearing in both lists should get higher RRF score."""
        list1 = [("shared", 0.5, {}), ("only_vec", 0.9, {})]
        list2 = [("shared", 0.5, {}), ("only_bm25", 0.9, {})]
        fused = reciprocal_rank_fusion([list1, list2], top_n=3)
        # 'shared' appears in both -> higher RRF score
        assert fused[0][0] == "shared"
