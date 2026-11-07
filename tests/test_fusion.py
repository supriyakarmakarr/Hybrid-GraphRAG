"""Tests for RRF fusion."""
import pytest
from app.retrieval.fusion import rrf_fuse


class TestRRFFusion:
    def test_rrf_combines_lists(self):
        bm25 = [{"chunk_id": "c1"}, {"chunk_id": "c2"}, {"chunk_id": "c3"}]
        vec  = [{"chunk_id": "c2"}, {"chunk_id": "c1"}, {"chunk_id": "c4"}]
        fused = rrf_fuse([bm25, vec])
        # c1 and c2 appear in both — should rank highest
        assert fused[0] in ("c1", "c2")
        assert fused[1] in ("c1", "c2")

    def test_rrf_unique_results(self):
        bm25 = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
        vec  = [{"chunk_id": "c1"}, {"chunk_id": "c3"}]
        fused = rrf_fuse([bm25, vec])
        assert len(fused) == len(set(fused))

    def test_rrf_empty_lists(self):
        assert rrf_fuse([[], []]) == []

    def test_rrf_single_list(self):
        lst = [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
        fused = rrf_fuse([lst])
        assert fused == ["c1", "c2"]
