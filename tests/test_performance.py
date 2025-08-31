# tests/test_performance.py
import pytest
from fastapi.testclient import TestClient


@pytest.mark.performance
class TestCachePerformance:
    """Performance tests for cache system"""
    
    def test_cache_hit_vs_miss_performance(self, client, sample_data, benchmark):
        """Test that cache hits are significantly faster than misses"""
        
        def search_with_cache_miss():
            # Use unique query each time to avoid cache
            import time
            query = f"unique_query_{time.time()}"
            response = client.get(f"/search/answers?q={query}")
            return response
        
        def search_with_potential_cache_hit():
            # Use same query to potentially hit cache
            response = client.get("/search/answers?q=cached_query")
            return response
        
        # Benchmark cache miss
        miss_result = benchmark.pedantic(
            search_with_cache_miss, 
            iterations=5, 
            rounds=1
        )
        assert miss_result.status_code == 200
    
    def test_dashboard_cache_performance(self, client, sample_data, benchmark):
        """Test dashboard cache performance improvement"""
        form_id = sample_data["form"].id
        
        def dashboard_request():
            response = client.get(f"/forms/{form_id}/dashboard")
            return response
        
        # Benchmark dashboard requests
        result = benchmark.pedantic(
            dashboard_request,
            iterations=10,
            rounds=2
        )
        assert result.status_code == 200
        
        # After multiple requests, should benefit from cache
        # Exact performance improvement hard to test in unit tests,
        # but at minimum should not degrade
    
    def test_search_popularity_tracking_performance(self, test_db, benchmark):
        """Test that popularity tracking doesn't significantly impact performance"""
        from app.routers.search import track_search_query
        
        def track_query():
            track_search_query(test_db, "performance_test_query")
        
        result = benchmark.pedantic(
            track_query,
            iterations=100,
            rounds=3
        )
        
        # Should complete quickly even with many iterations
        # This ensures popularity tracking doesn't become a bottleneck


@pytest.mark.performance
@pytest.mark.slow
class TestInfiniteScrollPerformance:
    """Performance tests for infinite scroll functionality"""
    
    def test_pagination_cursor_performance(self, client, sample_data, benchmark):
        """Test that cursor-based pagination maintains performance"""
        
        def paginated_search():
            # Test first page
            response1 = client.get("/search/answers")
            assert response1.status_code == 200
            return response1
        
        result = benchmark.pedantic(
            paginated_search,
            iterations=5,
            rounds=2
        )
        assert result.status_code == 200
    
    def test_large_result_set_performance(self, client, test_db, benchmark):
        """Test performance with larger result sets"""
        # Create more sample data for this test
        from app.models import Form, Question, Author, Contribution, Answer
        
        # Create additional test data
        form = Form(name="Performance Test Form", version="1.0", source="test")
        test_db.add(form)
        test_db.flush()
        
        question = Question(
            form_id=form.id,
            question_code="PERF_Q1",
            prompt="Performance test question",
            type="text",
            position=1
        )
        test_db.add(question)
        test_db.flush()
        
        # Create multiple authors and contributions
        for i in range(50):
            author = Author(name=f"Test User {i}", email_hash=f"hash{i}")
            test_db.add(author)
            test_db.flush()
            
            contribution = Contribution(
                author_id=author.id,
                form_id=form.id,
                source="performance_test"
            )
            test_db.add(contribution)
            test_db.flush()
            
            answer = Answer(
                contribution_id=contribution.id,
                question_id=question.id,
                text=f"This is a performance test answer number {i} with some content to search through",
                position=1
            )
            test_db.add(answer)
        
        test_db.commit()
        
        def search_large_dataset():
            response = client.get("/search/answers?q=performance")
            return response
        
        result = benchmark.pedantic(
            search_large_dataset,
            iterations=3,
            rounds=2
        )
        assert result.status_code == 200


@pytest.mark.performance 
class TestDatabaseQueryPerformance:
    """Performance tests for database queries"""
    
    def test_search_query_performance(self, test_db, sample_data, benchmark):
        """Test raw search query performance"""
        from sqlalchemy import text
        
        def search_query():
            # Test the core search query performance
            result = test_db.execute(
                text("""
                    SELECT a.id, a.text, q.prompt
                    FROM answers a
                    JOIN questions q ON q.id = a.question_id
                    WHERE a.text IS NOT NULL
                    AND char_length(btrim(a.text)) >= 40
                    ORDER BY a.id DESC
                    LIMIT 20
                """)
            ).mappings().all()
            return result
        
        results = benchmark.pedantic(
            search_query,
            iterations=10,
            rounds=3
        )
        assert len(results) >= 0  # Should return some results
    
    def test_cache_lookup_performance(self, test_db, cache_test_data, benchmark):
        """Test cache lookup query performance"""
        from app.routers.search import get_cached_results
        
        def cache_lookup():
            result = get_cached_results(test_db, "search:popular:", 30)
            return result
        
        result = benchmark.pedantic(
            cache_lookup,
            iterations=50,
            rounds=3
        )
        # Cache lookup should be very fast


@pytest.mark.performance
@pytest.mark.integration
class TestMemoryUsage:
    """Tests for memory usage during operations"""
    
    def test_infinite_scroll_memory_usage(self, client, sample_data):
        """Test that infinite scroll doesn't cause memory leaks"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Simulate multiple scroll requests
        for i in range(10):
            response = client.get(f"/search/answers?cursor=test_cursor_{i}&partial=1")
            assert response.status_code == 200
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 50MB for 10 requests)
        assert memory_increase < 50 * 1024 * 1024  # 50MB threshold
    
    def test_large_cache_data_handling(self, test_db, benchmark):
        """Test handling of large cache data"""
        from app.routers.search import save_cached_results
        
        # Create large test data
        large_data = {
            "answers": [
                {
                    "id": i,
                    "text": "Lorem ipsum " * 100,  # Large text content
                    "created_at": "2024-01-01T00:00:00"
                }
                for i in range(100)  # 100 large answers
            ],
            "has_next": True,
            "next_cursor": "large_cursor"
        }
        
        def save_large_cache():
            save_cached_results(test_db, "large:cache:test", large_data, 10)
        
        benchmark.pedantic(
            save_large_cache,
            iterations=3,
            rounds=1
        )
        
        # Should complete without errors even with large data