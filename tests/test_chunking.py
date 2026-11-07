"""Tests for text chunking logic."""
import pytest
from app.ingestion.chunker import chunk_text, make_chunks


class TestChunking:
    def test_basic_chunking(self):
        words = ["word"] * 1200
        text = " ".join(words)
        chunks = chunk_text(text, size=500, overlap=50)
        assert len(chunks) == 3  # 1200 / (500-50) ≈ 3

    def test_overlap_exists(self):
        text = " ".join([f"w{i}" for i in range(600)])
        chunks = chunk_text(text, size=500, overlap=50)
        # Second chunk should start 450 words in
        second_start = chunks[1].split()[0]
        assert second_start == "w450"

    def test_empty_text(self):
        assert chunk_text("") == []

    def test_short_text_one_chunk(self):
        text = "Short text here."
        chunks = chunk_text(text)
        assert len(chunks) == 1

    def test_make_chunks_deterministic(self):
        """Same input → same chunk IDs."""
        chunks1 = make_chunks("doc_001", "tenant-test", "Hello world " * 100, ["admin"])
        chunks2 = make_chunks("doc_001", "tenant-test", "Hello world " * 100, ["admin"])
        ids1 = [c["chunk_id"] for c in chunks1]
        ids2 = [c["chunk_id"] for c in chunks2]
        assert ids1 == ids2

    def test_chunks_inherit_roles(self):
        chunks = make_chunks("doc_001", "tenant-test", "Some text " * 200, ["admin", "analyst"])
        for chunk in chunks:
            assert "admin" in chunk["allowed_roles"]
            assert "analyst" in chunk["allowed_roles"]

    def test_chunk_ids_unique(self):
        chunks = make_chunks("doc_001", "tenant-test", "word " * 2000, ["admin"])
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))
