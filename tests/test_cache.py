# tests/test_cache.py
import pytest
import json
from datetime import datetime
from app.routers.search import (
    get_search_popularity, 
    get_cache_ttl_minutes,
    get_cache_key,
    get_cached_results,
    save_cached_results,
    track_search_query
)


@pytest.mark.cache
class TestCacheIntelligence:
    """Tests for intelligent caching system"""
    
    def test_popularity_based_ttl(self, test_db, cache_test_data):
        """Test TTL calculation based on search popularity - optimized for production"""
        # Test different popularity levels according to optimized implementation
        assert get_cache_ttl_minutes(1) == 5      # 5 min cache for rare queries - optimized!
        assert get_cache_ttl_minutes(4) == 5      # Still 5 min  
        assert get_cache_ttl_minutes(5) == 15     # 15 min for medium popularity (5-19) - increased
        assert get_cache_ttl_minutes(10) == 15    # Still 15 min
        assert get_cache_ttl_minutes(20) == 30    # 30 min for popular (20-99) - increased
        assert get_cache_ttl_minutes(50) == 30    # Still 30 min
        assert get_cache_ttl_minutes(100) == 45   # 45 min for very popular (100-999) - increased
        assert get_cache_ttl_minutes(1000) == 60  # 1 hour for timeline (1000+) - new
    
    def test_search_popularity_tracking(self, test_db):
        """Test search query popularity tracking"""
        # Track new query
        track_search_query(test_db, "new query")
        popularity = get_search_popularity(test_db, "new query")
        assert popularity == 1
        
        # Track existing query
        track_search_query(test_db, "new query") 
        popularity = get_search_popularity(test_db, "new query")
        assert popularity == 2
        
        # Case insensitive and trimming
        track_search_query(test_db, "  NEW QUERY  ")
        popularity = get_search_popularity(test_db, "new query")
        assert popularity == 3
    
    def test_cache_key_generation(self):
        """Test cache key generation for different queries"""
        assert get_cache_key("test", "") == "search:test:"
        assert get_cache_key("test query", "cursor123") == "search:test query:cursor123"
        assert get_cache_key("", "") == "search::"
    
    def test_cache_save_and_retrieve(self, test_db):
        """Test cache save and retrieval with datetime serialization"""
        cache_key = "test:cache:key"
        test_data = {
            "answers": [
                {
                    "id": 1,
                    "text": "Test answer",
                    "created_at": datetime.now()  # This should be serialized to string
                }
            ],
            "has_next": False,
            "next_cursor": None
        }
        
        # Save to cache
        save_cached_results(test_db, cache_key, test_data, 10)
        
        # Retrieve from cache
        cached = get_cached_results(test_db, cache_key, 30)  # 30 min TTL
        assert cached is not None
        assert len(cached["answers"]) == 1
        assert cached["answers"][0]["text"] == "Test answer"
        assert isinstance(cached["answers"][0]["created_at"], str)  # Should be string now
    
    def test_cache_expiration(self, test_db):
        """Test cache expiration logic"""
        cache_key = "test:expired:cache"
        test_data = {"test": "data"}
        
        # Save to cache
        save_cached_results(test_db, cache_key, test_data, 10)
        
        # Should retrieve with high TTL
        cached = get_cached_results(test_db, cache_key, 60)
        assert cached is not None
        
        # Should not retrieve with 0 TTL (rare queries)
        cached = get_cached_results(test_db, cache_key, 0) 
        assert cached is None
    
    def test_cache_miss_handling(self, test_db):
        """Test cache miss scenarios"""
        # Non-existent cache key
        cached = get_cached_results(test_db, "nonexistent:key", 30)
        assert cached is None
        
        # Zero TTL (rare queries)
        cached = get_cached_results(test_db, "any:key", 0)
        assert cached is None


@pytest.mark.cache
@pytest.mark.integration
class TestCacheIntegration:
    """Integration tests for cache with search endpoints"""
    
    def test_search_cache_workflow(self, client, sample_data):
        """Test complete cache workflow in search"""
        # First search - should be slow (no cache)
        response1 = client.get("/search/answers?q=expérience")
        assert response1.status_code == 200
        
        # Second search - should hit cache (if popular enough after multiple calls)
        for _ in range(5):  # Make query popular enough to be cached
            client.get("/search/answers?q=expérience")
        
        response2 = client.get("/search/answers?q=expérience")
        assert response2.status_code == 200
        
        # Verify both responses have same structure
        assert "expérience" in response1.text.lower()
        assert "expérience" in response2.text.lower()
    
    def test_partial_requests_no_cache_save(self, client, sample_data):
        """Test that partial HTMX requests don't interfere with cache"""
        # Regular search
        response1 = client.get("/search/answers?q=service")
        assert response1.status_code == 200
        
        # Partial request (infinite scroll)
        response2 = client.get("/search/answers?q=service&partial=1")
        assert response2.status_code == 200
        
        # Should get different templates but same data
        assert "service" in response1.text.lower()
        assert "service" in response2.text.lower()


@pytest.mark.cache
class TestCacheRobustness:
    """Test cache error handling and edge cases"""
    
    def test_malformed_cache_data(self, test_db):
        """Test handling of corrupted cache data"""
        from app.models import SearchCache
        import uuid
        
        # Create cache entry with invalid JSON
        unique_key = f"bad:cache:{uuid.uuid4().hex[:8]}"
        bad_cache = SearchCache(
            cache_key=unique_key,
            results_json='{"incomplete": json',  # Invalid JSON
            search_count=5
        )
        test_db.add(bad_cache)
        test_db.commit()
        
        # Should handle gracefully (return None)
        cached = get_cached_results(test_db, unique_key, 30)
        assert cached is None
    
    def test_empty_query_handling(self, test_db):
        """Test cache behavior with empty queries"""
        # Empty queries (timeline) should not be tracked for stats
        track_search_query(test_db, "")
        track_search_query(test_db, "   ")
        
        # But timeline should be considered "popular" for caching purposes
        popularity = get_search_popularity(test_db, "")
        assert popularity == 1000  # Timeline is always "popular" for cache TTL
    
    def test_cache_transaction_handling(self, test_db):
        """Test cache operations handle transaction errors gracefully"""
        # This test ensures cache failures don't break search
        cache_key = "transaction:test"
        test_data = {"test": "data"}
        
        # Even if cache save fails, it shouldn't raise exception
        try:
            save_cached_results(test_db, cache_key, test_data, 10)
            # If we get here, cache save worked
            assert True
        except Exception:
            # If cache save fails, it should fail silently
            pytest.fail("Cache save should not raise exceptions")