"""
tests/test_search.py - Test search functionality
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestSearchImports:
    """Test that retrieval/search modules can be imported."""

    def test_import_retrieval_modules(self):
        """Test retrieval modules can be imported."""
        from retrieval import search_cache
        assert search_cache is not None

    def test_import_bm25(self):
        """Test BM25 search module exists."""
        from retrieval.bm25_search import BM25Search
        assert BM25Search is not None

    def test_import_intent_classifier(self):
        """Test intent classifier can be imported."""
        from retrieval.intent_classifier import IntentClassifier
        assert IntentClassifier is not None

    def test_import_search_cache(self):
        """Test search cache can be imported."""
        from retrieval.search_cache import SearchCache
        assert SearchCache is not None


class TestSearchCache:
    """Test search cache basic functionality."""

    def test_search_cache_instantiation(self):
        """Test SearchCache can be instantiated."""
        from retrieval.search_cache import SearchCache
        cache = SearchCache()
        assert cache is not None

    def test_search_cache_stats(self):
        """Test SearchCache.get_stats returns dict."""
        from retrieval.search_cache import SearchCache
        cache = SearchCache()
        stats = cache.get_stats()
        assert isinstance(stats, dict)


class TestIntentClassifier:
    """Test intent classifier."""

    def test_intent_classifier_instantiation(self):
        """Test IntentClassifier can be instantiated."""
        from retrieval.intent_classifier import IntentClassifier
        classifier = IntentClassifier()
        assert classifier is not None

    def test_intent_classifier_classify(self):
        """Test IntentClassifier.classify returns expected types."""
        from retrieval.intent_classifier import IntentClassifier
        classifier = IntentClassifier()
        result = classifier.classify("用户的名字叫什么")
        # Result is a tuple (intent, confidence)
        assert isinstance(result, tuple)
        assert len(result) == 2
