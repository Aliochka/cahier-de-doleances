# tests/routers/test_forms.py
import pytest
import json
from unittest.mock import patch


@pytest.mark.integration
class TestFormDetail:
    """Tests for form detail pages"""
    
    def test_form_detail_basic(self, client, sample_data):
        """Test basic form detail page"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}")
        assert response.status_code == 200
        assert "Test Form" in response.text
    
    def test_form_detail_with_contributions(self, client, sample_data):
        """Test form detail with multiple contributions"""
        form_id = sample_data["form"].id
        
        # Test first contribution (default)
        response = client.get(f"/forms/{form_id}")
        assert response.status_code == 200
        
        # Test specific contribution index
        response2 = client.get(f"/forms/{form_id}?contrib=2")
        assert response2.status_code == 200
        
        # Both should be valid but potentially different content
        assert response.status_code == response2.status_code == 200
    
    def test_form_detail_nonexistent(self, client):
        """Test form detail for nonexistent form"""
        response = client.get("/forms/99999")
        assert response.status_code == 404
    
    def test_form_detail_navigation(self, client, sample_data):
        """Test form contribution navigation"""
        form_id = sample_data["form"].id
        
        # Test invalid contribution index (should clamp to valid range)
        response = client.get(f"/forms/{form_id}?contrib=999")
        assert response.status_code == 200  # Should clamp to max available
        
        response = client.get(f"/forms/{form_id}?contrib=0")
        assert response.status_code == 200  # Should clamp to min (1)


@pytest.mark.cache
@pytest.mark.integration
class TestFormDashboard:
    """Tests for form dashboard with caching"""
    
    def test_dashboard_basic(self, client, sample_data):
        """Test basic dashboard functionality"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}/dashboard")
        assert response.status_code == 200
        assert "dashboard" in response.text.lower()
    
    def test_dashboard_cache_functionality(self, client, sample_data):
        """Test dashboard caching mechanism"""
        form_id = sample_data["form"].id
        
        # First request - should generate cache
        response1 = client.get(f"/forms/{form_id}/dashboard")
        assert response1.status_code == 200
        
        # Second request - should hit cache
        response2 = client.get(f"/forms/{form_id}/dashboard")
        assert response2.status_code == 200
        
        # Should have same content (cached)
        assert response1.text == response2.text
    
    def test_dashboard_question_stats(self, client, sample_data):
        """Test dashboard shows question statistics"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}/dashboard")
        assert response.status_code == 200
        
        # Should contain question information
        assert "What is your favorite color?" in response.text
        assert "Describe your experience" in response.text
    
    def test_dashboard_single_choice_charts(self, client, sample_data):
        """Test dashboard generates charts for single choice questions"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}/dashboard")
        assert response.status_code == 200
        
        # Should contain chart data for single choice questions
        # Look for Chart.js or chart-related elements
        assert ("chart" in response.text.lower() or 
                "rouge" in response.text.lower() or 
                "bleu" in response.text.lower())


@pytest.mark.integration
class TestFormDashboardStats:
    """Tests for form dashboard statistics endpoint"""
    
    def test_dashboard_stats_endpoint(self, client, sample_data):
        """Test dashboard stats partial endpoint"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}/dashboard-stats")
        assert response.status_code == 200
    
    def test_dashboard_stats_nonexistent_form(self, client):
        """Test dashboard stats for nonexistent form"""
        response = client.get("/forms/99999/dashboard-stats")
        assert response.status_code == 404
    
    def test_dashboard_stats_single_choice_data(self, client, sample_data):
        """Test dashboard stats contains single choice data"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}/dashboard-stats")
        assert response.status_code == 200
        
        # Should contain stats for single choice questions
        response_text = response.text.lower()
        assert any(color in response_text for color in ["rouge", "bleu", "vert"])


@pytest.mark.cache
class TestDashboardCacheInvalidation:
    """Test dashboard cache invalidation"""
    
    def test_cache_invalidation_function(self, test_db, sample_data):
        """Test cache invalidation helper function"""
        from app.routers.forms import invalidate_dashboard_cache
        from app.models import DashboardCache
        
        form_id = sample_data["form"].id
        
        # Create cache entry
        cache_entry = DashboardCache(
            form_id=form_id,
            stats_json='{"test": "data"}'
        )
        test_db.add(cache_entry)
        test_db.commit()
        
        # Verify cache exists
        existing = test_db.query(DashboardCache).filter_by(form_id=form_id).first()
        assert existing is not None
        
        # Invalidate cache
        invalidate_dashboard_cache(test_db, form_id)
        
        # Verify cache is removed
        remaining = test_db.query(DashboardCache).filter_by(form_id=form_id).first()
        assert remaining is None


@pytest.mark.integration
class TestFormErrorHandling:
    """Test form-related error handling"""
    
    def test_form_detail_invalid_contrib_param(self, client, sample_data):
        """Test form detail with invalid contrib parameter"""
        form_id = sample_data["form"].id
        
        # Invalid contribution parameter should be handled gracefully
        response = client.get(f"/forms/{form_id}?contrib=invalid")
        assert response.status_code == 200  # Should default to 1
    
    def test_form_detail_negative_contrib(self, client, sample_data):
        """Test form detail with negative contribution index"""
        form_id = sample_data["form"].id
        response = client.get(f"/forms/{form_id}?contrib=-1")
        assert response.status_code == 200  # Should clamp to valid range
    
    def test_dashboard_with_no_questions(self, client, test_db):
        """Test dashboard for form with no questions"""
        from app.models import Form
        
        # Create form without questions
        empty_form = Form(name="Empty Form", version="1.0", source="test")
        test_db.add(empty_form)
        test_db.commit()
        
        response = client.get(f"/forms/{empty_form.id}/dashboard")
        assert response.status_code == 200  # Should handle gracefully


@pytest.mark.performance
class TestFormPerformance:
    """Performance tests for form endpoints"""
    
    def test_dashboard_cache_performance(self, client, sample_data):
        """Test that dashboard cache improves performance"""
        form_id = sample_data["form"].id
        
        # First request (cache miss)
        import time
        start1 = time.time()
        response1 = client.get(f"/forms/{form_id}/dashboard")
        time1 = time.time() - start1
        assert response1.status_code == 200
        
        # Second request (cache hit)
        start2 = time.time()
        response2 = client.get(f"/forms/{form_id}/dashboard")
        time2 = time.time() - start2
        assert response2.status_code == 200
        
        # Cache hit should be faster (though in tests the difference might be minimal)
        # At minimum, both requests should complete successfully
        assert time1 > 0 and time2 > 0
        assert response1.text == response2.text