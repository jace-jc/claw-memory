"""
tests/test_core.py - Test core imports and basic functionality
"""
import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestCoreImports:
    """Test that core modules can be imported without errors."""

    def test_import_core_module(self):
        """Test core module can be imported."""
        from core import LanceDBStore, SCHEMA
        assert LanceDBStore is not None
        assert SCHEMA is not None

    def test_import_core_memory_config(self):
        """Test core.memory_config can be imported."""
        from core.memory_config import CONFIG
        assert isinstance(CONFIG, dict)

    def test_import_memory_kg(self):
        """Test memory_kg can be imported."""
        from memory_kg import KnowledgeGraph, get_kg
        assert KnowledgeGraph is not None
        assert get_kg is not None

    def test_knowledge_graph_instantiation(self):
        """Test KnowledgeGraph can be instantiated."""
        from memory_kg import KnowledgeGraph
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            kg_path = os.path.join(tmpdir, "test_kg.json")
            kg = KnowledgeGraph(kg_path=kg_path)
            assert kg is not None
            assert kg.kg_path == kg_path

    def test_knowledge_graph_add_entity(self):
        """Test KnowledgeGraph.add_entity."""
        from memory_kg import KnowledgeGraph
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            kg = KnowledgeGraph(kg_path=os.path.join(tmpdir, "kg.json"))
            entity_id = kg.add_entity("Alice", "person", {"age": 30})
            assert entity_id is not None
            assert len(entity_id) > 0

    def test_knowledge_graph_get_stats(self):
        """Test KnowledgeGraph.get_stats."""
        from memory_kg import KnowledgeGraph
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            kg = KnowledgeGraph(kg_path=os.path.join(tmpdir, "kg.json"))
            stats = kg.get_stats()
            assert isinstance(stats, dict)
            assert "total_entities" in stats
            assert "total_relations" in stats

    def test_core_db_singleton(self):
        """Test core._db.get_db lazy singleton."""
        from core._db import get_db as get_db_core
        # Should return the same instance on repeated calls
        db1 = get_db_core()
        db2 = get_db_core()
        # Both should be the same object (singleton)
        assert db1 is db2
