# tests/test_basic.py
"""Basic tests to verify test infrastructure works"""
import pytest


def test_basic_math():
    """Basic test to verify pytest works"""
    assert 1 + 1 == 2


def test_app_import():
    """Test that we can import the application"""
    from app.app import app
    assert app is not None


def test_cache_functions_import():
    """Test that we can import cache functions"""
    from app.routers.search import get_cache_ttl_minutes, get_cache_key
    
    # Test basic functionality  
    assert get_cache_ttl_minutes(1) == 5  # Now caches rare queries for 5 min
    assert get_cache_key("test", "cursor") == "search:test:cursor"


@pytest.mark.cache
def test_cache_logic_only():
    """Test cache logic without database"""
    from app.routers.search import get_cache_ttl_minutes
    
    # Test the TTL logic (optimized for production)
    assert get_cache_ttl_minutes(1) == 5      # 5 min cache for rare (< 5) - optimized
    assert get_cache_ttl_minutes(5) == 15     # 15 min for medium (5-19) - increased
    assert get_cache_ttl_minutes(20) == 30    # 30 min for popular (20-99) - increased
    assert get_cache_ttl_minutes(100) == 45   # 45 min for very popular (100-999) - increased
    assert get_cache_ttl_minutes(1000) == 60  # 1 hour for timeline (1000+) - new


@pytest.mark.scroll
def test_template_logic():
    """Test that templates exist"""
    from pathlib import Path
    
    template_dir = Path("app/templates/partials")
    assert template_dir.exists()
    
    # Check critical templates exist
    assert (template_dir / "_answers_list.html").exists()
    assert (template_dir / "_answers_list_append.html").exists()
    assert (template_dir / "_question_answers_list.html").exists()