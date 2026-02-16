"""Unit tests for src.rag.chunker module."""

import importlib.util

import pytest

# Load chunker directly from file to avoid src.rag.__init__.py
# which imports RAGPipeline and heavy ML models that hang in CI.
_spec = importlib.util.spec_from_file_location(
    "src.rag.chunker", "/mnt/projects/src/rag/chunker.py"
)
_chunker_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_chunker_mod)
DocumentChunker = _chunker_mod.DocumentChunker
DocumentChunk = _chunker_mod.DocumentChunk
ChunkingStrategy = _chunker_mod.ChunkingStrategy


class TestChunkingStrategy:
    """Tests for ChunkingStrategy enum."""

    def test_fixed_size_value(self):
        assert ChunkingStrategy.FIXED_SIZE.value == "fixed_size"

    def test_sentence_value(self):
        assert ChunkingStrategy.SENTENCE.value == "sentence"

    def test_paragraph_value(self):
        assert ChunkingStrategy.PARAGRAPH.value == "paragraph"

    def test_semantic_value(self):
        assert ChunkingStrategy.SEMANTIC.value == "semantic"

    def test_recursive_value(self):
        assert ChunkingStrategy.RECURSIVE.value == "recursive"

    def test_all_five_values_exist(self):
        members = list(ChunkingStrategy)
        assert len(members) == 5
        names = {m.name for m in members}
        assert names == {"FIXED_SIZE", "SENTENCE", "PARAGRAPH", "SEMANTIC", "RECURSIVE"}


class TestDocumentChunk:
    """Tests for DocumentChunk dataclass."""

    def test_default_overlap_is_zero(self):
        chunk = DocumentChunk(
            text="hello",
            chunk_id="doc1_chunk_0",
            document_id="doc1",
            start_index=0,
            end_index=5,
            metadata={},
        )
        assert chunk.overlap == 0

    def test_explicit_overlap(self):
        chunk = DocumentChunk(
            text="hello",
            chunk_id="doc1_chunk_0",
            document_id="doc1",
            start_index=0,
            end_index=5,
            metadata={},
            overlap=25,
        )
        assert chunk.overlap == 25

    def test_metadata_propagation(self):
        meta = {"source": "pdf", "page": 3}
        chunk = DocumentChunk(
            text="hello",
            chunk_id="doc1_chunk_0",
            document_id="doc1",
            start_index=0,
            end_index=5,
            metadata=meta,
        )
        assert chunk.metadata["source"] == "pdf"
        assert chunk.metadata["page"] == 3

    def test_all_fields_stored(self):
        chunk = DocumentChunk(
            text="content",
            chunk_id="d_chunk_0",
            document_id="d",
            start_index=10,
            end_index=17,
            metadata={"k": "v"},
            overlap=5,
        )
        assert chunk.text == "content"
        assert chunk.chunk_id == "d_chunk_0"
        assert chunk.document_id == "d"
        assert chunk.start_index == 10
        assert chunk.end_index == 17
        assert chunk.metadata == {"k": "v"}
        assert chunk.overlap == 5


class TestDocumentChunkerInit:
    """Tests for DocumentChunker initialisation and defaults."""

    def test_default_strategy_is_recursive(self):
        chunker = DocumentChunker()
        assert chunker.strategy == ChunkingStrategy.RECURSIVE

    def test_default_chunk_size(self):
        chunker = DocumentChunker()
        assert chunker.chunk_size == 512

    def test_default_chunk_overlap(self):
        chunker = DocumentChunker()
        assert chunker.chunk_overlap == 50

    def test_default_min_chunk_size(self):
        chunker = DocumentChunker()
        assert chunker.min_chunk_size == 100

    def test_custom_parameters(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=256,
            chunk_overlap=30,
            min_chunk_size=50,
        )
        assert chunker.strategy == ChunkingStrategy.SENTENCE
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 30
        assert chunker.min_chunk_size == 50


class TestFixedSizeStrategy:
    """Tests for _chunk_fixed_size via FIXED_SIZE strategy."""

    def test_short_text_below_min_returns_empty(self):
        """Text shorter than min_chunk_size should yield no chunks."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        short_text = "a" * 50  # 50 chars < 100 min
        chunks = chunker.chunk(short_text, "doc1")
        assert chunks == []

    def test_text_exactly_chunk_size_returns_one_chunk(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        text = "x" * 200
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_long_text_produces_multiple_chunks(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        text = "a" * 500
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 2

    def test_overlap_between_adjacent_chunks(self):
        """Adjacent chunks should share overlapping characters."""
        overlap = 20
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=overlap,
            # min_chunk_size must be small enough that the last chunk
            # (after overlap) doesn't get skipped, avoiding an infinite loop
            # in _chunk_fixed_size where start = end - overlap goes backwards.
            min_chunk_size=1,
        )
        # Unique chars so we can verify overlap content
        text = "".join(chr(ord("a") + (i % 26)) for i in range(500))
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 2

        # The first chunk's overlap should be 0 (no previous chunk)
        assert chunks[0].overlap == 0

        # Subsequent chunks should report the overlap value
        for c in chunks[1:]:
            assert c.overlap == overlap

        # Verify the actual text overlaps: end of chunk N overlaps start of chunk N+1
        for i in range(len(chunks) - 1):
            tail = chunks[i].text[-overlap:]
            head = chunks[i + 1].text[:overlap]
            assert tail == head

    def test_chunk_id_format(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        text = "b" * 500
        chunks = chunker.chunk(text, "mydoc")
        for idx, c in enumerate(chunks):
            assert c.chunk_id == f"mydoc_chunk_{idx}"

    def test_document_id_propagated(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        text = "c" * 200
        chunks = chunker.chunk(text, "doc42")
        assert all(c.document_id == "doc42" for c in chunks)

    def test_chunk_index_in_metadata(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        text = "d" * 500
        chunks = chunker.chunk(text, "doc1")
        for idx, c in enumerate(chunks):
            assert c.metadata["chunk_index"] == idx

    def test_trailing_piece_below_min_is_skipped(self):
        """When the last piece is below min_chunk_size it should be dropped."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        # 250 chars: first chunk=200 (kept), remainder=50 (dropped)
        text = "e" * 250
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) == 1
        assert len(chunks[0].text) == 200


class TestSentenceStrategy:
    """Tests for _chunk_sentence via SENTENCE strategy."""

    def test_single_sentence_returns_one_chunk(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=500,
            chunk_overlap=0,
        )
        text = "This is a single sentence."
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) == 1
        assert "This is a single sentence" in chunks[0].text

    def test_multiple_sentences_fitting_one_chunk(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=500,
            chunk_overlap=0,
        )
        text = "First sentence. Second sentence. Third sentence."
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) == 1

    def test_sentences_exceeding_chunk_size_split(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=50,
            chunk_overlap=0,
        )
        text = "First sentence is here. Second sentence is here. Third sentence is here. Fourth sentence is here."
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 2

    def test_exclamation_and_question_marks_split(self):
        """! and ? should also work as sentence delimiters."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=500,
            chunk_overlap=0,
        )
        text = "Hello world! How are you? Fine."
        chunks = chunker.chunk(text, "doc1")
        # All sentences should appear in the chunks
        combined = " ".join(c.text for c in chunks)
        assert "Hello world" in combined
        assert "How are you" in combined
        assert "Fine" in combined

    def test_chunk_id_format_sentence(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=50,
            chunk_overlap=0,
        )
        text = "Sentence one is here. Sentence two is here. Sentence three is here. Sentence four is here."
        chunks = chunker.chunk(text, "sdoc")
        for idx, c in enumerate(chunks):
            assert c.chunk_id == f"sdoc_chunk_{idx}"

    def test_empty_sentences_stripped(self):
        """Consecutive delimiters should not produce empty chunks."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=500,
            chunk_overlap=0,
        )
        text = "First... Second."
        chunks = chunker.chunk(text, "doc1")
        for c in chunks:
            assert c.text.strip() != ""


class TestParagraphStrategy:
    """Tests for _chunk_paragraph via PARAGRAPH strategy."""

    def test_single_paragraph_returns_one_chunk(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=500,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        text = "This is a single paragraph with some content."
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_multiple_small_paragraphs_grouped(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=500,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunker.chunk(text, "doc1")
        # Total text is well under 500, so should be grouped into 1 chunk
        assert len(chunks) == 1
        assert "Paragraph one." in chunks[0].text
        assert "Paragraph two." in chunks[0].text
        assert "Paragraph three." in chunks[0].text

    def test_paragraphs_exceeding_chunk_size_split(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=100,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        para1 = "A" * 60
        para2 = "B" * 60
        para3 = "C" * 60
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunker.chunk(text, "doc1")
        # 60+60 = 120 > 100, so cannot all fit in one chunk
        assert len(chunks) >= 2

    def test_oversized_paragraph_split_with_fixed_size(self):
        """A single paragraph larger than chunk_size is split via fixed_size."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=100,
            chunk_overlap=0,
            min_chunk_size=50,
        )
        big_paragraph = "Z" * 250
        text = big_paragraph  # Single paragraph, no \n\n
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 2
        # All text should be covered
        combined = "".join(c.text for c in chunks)
        assert len(combined) >= 200  # At least most of the text

    def test_oversized_paragraph_among_normal(self):
        """Mix of normal and oversized paragraphs."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=100,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        normal = "Small paragraph."
        big = "X" * 250
        text = f"{normal}\n\n{big}\n\n{normal}"
        chunks = chunker.chunk(text, "doc1")
        # The big paragraph should be split, so we expect at least 3 chunks
        assert len(chunks) >= 3

    def test_chunk_id_sequential(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=100,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        para1 = "P" * 60
        para2 = "Q" * 60
        para3 = "R" * 60
        text = f"{para1}\n\n{para2}\n\n{para3}"
        chunks = chunker.chunk(text, "pdoc")
        for idx, c in enumerate(chunks):
            assert c.chunk_id == f"pdoc_chunk_{idx}"


class TestRecursiveStrategy:
    """Tests for _chunk_recursive via RECURSIVE (default) strategy."""

    def test_text_with_paragraphs_uses_paragraph_splitting(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=500,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        text = "Paragraph one content.\n\nParagraph two content.\n\nParagraph three content."
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 1
        combined = "\n\n".join(c.text for c in chunks)
        assert "Paragraph one content." in combined

    def test_text_with_sentences_only_uses_sentence_splitting(self):
        """No double-newlines, but has periods -- should use sentence strategy."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=500,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        text = "Sentence one. Sentence two. Sentence three."
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 1
        combined = " ".join(c.text for c in chunks)
        assert "Sentence one" in combined

    def test_text_without_punctuation_falls_back_to_fixed_size(self):
        """No paragraphs, no sentence-ending punctuation, uses fixed_size."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=100,
            chunk_overlap=0,
            min_chunk_size=50,
        )
        text = "a" * 300  # No periods, no newlines
        chunks = chunker.chunk(text, "doc1")
        assert len(chunks) >= 2
        # Fixed size chunks should be exactly chunk_size (except possibly last)
        assert len(chunks[0].text) == 100

    def test_recursive_prefers_paragraph_over_sentence(self):
        """When text has both paragraphs and sentences, paragraph splitting wins."""
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=500,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        text = "First sentence. Second sentence.\n\nThird sentence. Fourth sentence."
        chunks = chunker.chunk(text, "doc1")
        # With paragraph strategy at chunk_size=500, everything fits in 1 chunk
        assert len(chunks) >= 1

    def test_recursive_falls_to_sentence_if_paragraph_chunks_too_large(self):
        """If paragraph chunks exceed 1.5x chunk_size, try sentence splitting."""
        chunk_size = 100
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=chunk_size,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        # One giant "paragraph" with sentences
        big_para = ". ".join(["Sentence " + str(i) for i in range(30)])
        # Add \n\n so paragraph path is tried, but the single paragraph is too large
        text = "Small intro.\n\n" + big_para
        chunks = chunker.chunk(text, "doc1")
        # Should produce multiple chunks regardless of path
        assert len(chunks) >= 2


class TestMetadataPropagation:
    """Tests for metadata passing through to chunks."""

    def test_metadata_included_in_fixed_size_chunks(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        meta = {"source": "web", "author": "tester"}
        text = "f" * 200
        chunks = chunker.chunk(text, "doc1", metadata=meta)
        assert len(chunks) == 1
        assert chunks[0].metadata["source"] == "web"
        assert chunks[0].metadata["author"] == "tester"
        # chunk_index is also added
        assert chunks[0].metadata["chunk_index"] == 0

    def test_metadata_included_in_sentence_chunks(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=500,
            chunk_overlap=0,
        )
        meta = {"lang": "en"}
        text = "A sentence here."
        chunks = chunker.chunk(text, "doc1", metadata=meta)
        assert chunks[0].metadata["lang"] == "en"
        assert "chunk_index" in chunks[0].metadata

    def test_metadata_included_in_paragraph_chunks(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=500,
            chunk_overlap=0,
            min_chunk_size=10,
        )
        meta = {"category": "tech"}
        text = "A paragraph."
        chunks = chunker.chunk(text, "doc1", metadata=meta)
        assert chunks[0].metadata["category"] == "tech"

    def test_none_metadata_defaults_to_empty_dict(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        text = "g" * 200
        chunks = chunker.chunk(text, "doc1", metadata=None)
        assert len(chunks) == 1
        # Only chunk_index should be present
        assert chunks[0].metadata == {"chunk_index": 0}


class TestEmptyText:
    """Tests for empty or whitespace-only text input."""

    def test_empty_string_returns_empty_list_fixed(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.FIXED_SIZE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        chunks = chunker.chunk("", "doc1")
        assert chunks == []

    def test_empty_string_returns_empty_list_sentence(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=200,
            chunk_overlap=0,
        )
        chunks = chunker.chunk("", "doc1")
        assert chunks == []

    def test_empty_string_returns_empty_list_paragraph(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=200,
            chunk_overlap=0,
        )
        chunks = chunker.chunk("", "doc1")
        assert chunks == []

    def test_empty_string_returns_empty_list_recursive(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=200,
            chunk_overlap=0,
            min_chunk_size=100,
        )
        chunks = chunker.chunk("", "doc1")
        assert chunks == []

    def test_whitespace_only_sentence(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.SENTENCE,
            chunk_size=200,
            chunk_overlap=0,
        )
        chunks = chunker.chunk("   ", "doc1")
        assert chunks == []

    def test_whitespace_only_paragraph(self):
        chunker = DocumentChunker(
            strategy=ChunkingStrategy.PARAGRAPH,
            chunk_size=200,
            chunk_overlap=0,
        )
        chunks = chunker.chunk("   \n\n   ", "doc1")
        assert chunks == []
