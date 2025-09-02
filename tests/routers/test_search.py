# tests/routers/test_search.py
import pytest
from fastapi.testclient import TestClient


@pytest.mark.scroll
class TestSearchAnswers:
    """Tests for search answers functionality"""
    
    def test_search_answers_basic(self, client, sample_data):
        """Test basic search functionality"""
        response = client.get("/search/answers?q=expérience")
        assert response.status_code == 200
        assert "expérience" in response.text.lower()
    
    def test_search_answers_empty_query(self, client, sample_data):
        """Test search with empty query (timeline mode)"""
        response = client.get("/search/answers")
        assert response.status_code == 200
        # Should show recent answers in timeline mode (author names or author IDs)
        assert ("Test User" in response.text or "Auteur #" in response.text)
    
    def test_search_fts_vs_timeline_mode(self, client, sample_data):
        """Test FTS mode vs timeline mode"""
        # FTS mode (with query)
        fts_response = client.get("/search/answers?q=service&mode=fts")
        assert fts_response.status_code == 200
        
        # Timeline mode (no query)
        timeline_response = client.get("/search/answers?mode=timeline")
        assert timeline_response.status_code == 200
        
        # Both should return valid responses but different content
        assert fts_response.text != timeline_response.text
    
    def test_infinite_scroll_pagination(self, client, sample_data):
        """Test infinite scroll pagination with cursors"""
        # First page
        response1 = client.get("/search/answers")
        assert response1.status_code == 200
        
        # Should contain pagination elements for next page if more results
        if "hx-get" in response1.text and "cursor=" in response1.text:
            # Extract cursor from response (simplified test)
            import re
            cursor_match = re.search(r'cursor=([^&"]+)', response1.text)
            if cursor_match:
                cursor = cursor_match.group(1)
                
                # Request next page
                response2 = client.get(f"/search/answers?cursor={cursor}")
                assert response2.status_code == 200


@pytest.mark.scroll
class TestInfiniteScrollTemplates:
    """Tests for infinite scroll template rendering"""
    
    def test_full_vs_partial_template(self, client, sample_data):
        """Test different templates for full vs partial requests"""
        # Full page request
        full_response = client.get("/search/answers?q=test")
        assert full_response.status_code == 200
        assert "Recherche dans les réponses" in full_response.text  # Page header
        
        # Partial HTMX request
        partial_response = client.get("/search/answers?q=test&partial=1")
        assert partial_response.status_code == 200
        # Should not contain full page header
        assert "Recherche dans les réponses" not in partial_response.text
    
    def test_infinite_scroll_with_cursor(self, client, sample_data):
        """Test infinite scroll uses append template"""
        # Request with cursor (infinite scroll)
        response = client.get("/search/answers?q=test&cursor=dummy&partial=1")
        assert response.status_code == 200
        
        # Should use append template (smaller response)
        assert len(response.text) < 25000  # Append template should be reasonable size
    
    def test_htmx_headers_detection(self, client, sample_data):
        """Test HTMX header detection"""
        # Request with HX-Request header
        response = client.get(
            "/search/answers?q=test",
            headers={"HX-Request": "true"}
        )
        assert response.status_code == 200
        # Should return partial template
        assert "Recherche dans les réponses" not in response.text


@pytest.mark.scroll
class TestSearchQuestions:
    """Tests for search questions functionality"""
    
    def test_search_questions_basic(self, client, sample_data):
        """Test basic question search"""
        response = client.get("/search/questions")
        assert response.status_code == 200
        
        # Should show forms and questions sections
        assert "formulaires" in response.text.lower() or "forms" in response.text.lower()
    
    def test_search_questions_sections(self, client, sample_data):
        """Test different sections in question search"""
        # Forms section
        forms_response = client.get("/search/questions?section=forms&partial=1")
        assert forms_response.status_code == 200
        
        # Questions section  
        questions_response = client.get("/search/questions?section=questions&partial=1")
        assert questions_response.status_code == 200
        
        # Should return different content
        assert forms_response.text != questions_response.text


@pytest.mark.cache
@pytest.mark.integration
class TestSearchCacheIntegration:
    """Test cache integration with search endpoints"""
    
    def test_cache_applied_to_popular_queries(self, client, sample_data):
        """Test that popular queries get cached"""
        query = "popular_test_query"
        
        # Make query popular by repeating it
        for i in range(6):  # Make it popular enough to cache
            response = client.get(f"/search/answers?q={query}")
            assert response.status_code == 200
        
        # Subsequent requests should potentially hit cache
        response = client.get(f"/search/answers?q={query}")
        assert response.status_code == 200
    
    def test_cache_not_applied_to_rare_queries(self, client, sample_data):
        """Test that rare queries are not cached"""
        # Single request - should not be cached
        response = client.get("/search/answers?q=very_rare_query_12345")
        assert response.status_code == 200
        
        # Second request - still should work (but not cached)
        response2 = client.get("/search/answers?q=very_rare_query_12345")
        assert response2.status_code == 200


@pytest.mark.integration
class TestSearchErrorHandling:
    """Test search error handling and edge cases"""
    
    def test_malformed_cursor(self, client, sample_data):
        """Test handling of malformed cursor parameters"""
        response = client.get("/search/answers?cursor=invalid_cursor_format")
        # Should handle gracefully, not crash
        assert response.status_code == 200
    
    def test_very_long_query(self, client, sample_data):
        """Test handling of very long search queries"""
        long_query = "a" * 1000
        response = client.get(f"/search/answers?q={long_query}")
        # Should handle gracefully
        assert response.status_code == 200
    
    def test_special_characters_query(self, client, sample_data):
        """Test search with special characters"""
        special_query = "test@#$%^&*()_+-=[]{}|;':\",./<>?"
        response = client.get(f"/search/answers?q={special_query}")
        assert response.status_code == 200
    
    def test_unicode_query(self, client, sample_data):
        """Test search with unicode characters"""
        unicode_query = "éàü测试🔍"
        response = client.get(f"/search/answers?q={unicode_query}")
        assert response.status_code == 200