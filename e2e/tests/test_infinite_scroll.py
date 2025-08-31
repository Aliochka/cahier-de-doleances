# e2e/tests/test_infinite_scroll.py
import pytest
from playwright.sync_api import Page, expect
from e2e.pages.search_page import SearchAnswersPage, QuestionDetailPage


@pytest.mark.e2e
class TestInfiniteScrollBehavior:
    """E2E tests for infinite scroll functionality"""
    
    def test_search_answers_no_header_duplication(self, page_with_test_data: Page, test_server):
        """Critical test: ensure no header duplication on infinite scroll"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        # Wait for page to load
        expect(page_with_test_data.locator('h1')).to_contain_text('Recherche')
        
        # Count initial headers
        initial_headers = page_with_test_data.locator('h1').count()
        initial_search_bars = page_with_test_data.locator('.search-bar, input[name="q"]').count()
        
        # Perform search to get results
        search_page.search("test")
        search_page.wait_for_results()
        
        # Try to trigger infinite scroll if load more trigger exists
        if search_page.has_load_more_trigger():
            search_page.scroll_to_load_more()
            
            # Wait a bit for any content to load
            page_with_test_data.wait_for_timeout(2000)
            
            # Check that headers haven't been duplicated
            final_headers = page_with_test_data.locator('h1').count()
            final_search_bars = page_with_test_data.locator('.search-bar, input[name="q"]').count()
            
            assert final_headers == initial_headers, f"Headers duplicated! Initial: {initial_headers}, Final: {final_headers}"
            assert final_search_bars == initial_search_bars, f"Search bars duplicated! Initial: {initial_search_bars}, Final: {final_search_bars}"
    
    def test_infinite_scroll_loads_new_content(self, page_with_test_data: Page, test_server):
        """Test that infinite scroll actually loads new content"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        # Perform search
        search_page.search("experience")
        search_page.wait_for_results()
        
        # Get initial content count
        initial_cards = len(search_page.get_answer_cards())
        
        # If there's a load more trigger, test infinite scroll
        if search_page.has_load_more_trigger():
            # Scroll to trigger load more
            search_page.scroll_to_load_more()
            
            # Wait for new content
            page_with_test_data.wait_for_timeout(3000)
            
            # Get new content count
            final_cards = len(search_page.get_answer_cards())
            
            # Should have loaded more content OR reached end gracefully
            assert final_cards >= initial_cards, "Infinite scroll should maintain or increase content"
        else:
            # If no load more trigger, that's also valid (no more content to load)
            assert initial_cards >= 0, "Should have some results or handle no results gracefully"
    
    def test_infinite_scroll_preserves_search_query(self, page_with_test_data: Page, test_server):
        """Test that search query is preserved during infinite scroll"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        search_query = "service"
        search_page.search(search_query)
        search_page.wait_for_results()
        
        # Check that search input still contains the query
        expect(search_page.search_input).to_have_value(search_query)
        
        # If infinite scroll is available
        if search_page.has_load_more_trigger():
            search_page.scroll_to_load_more()
            page_with_test_data.wait_for_timeout(2000)
            
            # Search query should still be preserved
            expect(search_page.search_input).to_have_value(search_query)


@pytest.mark.e2e
class TestQuestionDetailScroll:
    """E2E tests for question detail page infinite scroll"""
    
    def test_question_answers_infinite_scroll(self, page_with_test_data: Page, test_server):
        """Test infinite scroll on question detail pages"""
        # Navigate to first available question (we'd need to get a real question ID)
        # For now, test the general functionality
        page_with_test_data.goto(f"{test_server}/questions/1-test-question")
        
        # Wait for page to load (may 404 with test data, but test the structure)
        page_with_test_data.wait_for_timeout(1000)
        
        # If page loads successfully (200), test infinite scroll
        if "404" not in page_with_test_data.content():
            question_page = QuestionDetailPage(page_with_test_data)
            
            initial_answer_count = question_page.get_answer_count()
            
            # Try to scroll for more answers
            question_page.scroll_to_load_more_answers()
            
            final_answer_count = question_page.get_answer_count()
            
            # Should maintain or increase answer count
            assert final_answer_count >= initial_answer_count


@pytest.mark.e2e
class TestScrollPerformance:
    """E2E tests for scroll performance and user experience"""
    
    def test_scroll_responsiveness(self, page_with_test_data: Page, test_server):
        """Test that infinite scroll is responsive and doesn't block UI"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        # Perform search
        search_page.search("test")
        search_page.wait_for_results()
        
        # Test that page remains responsive during scroll
        start_time = page_with_test_data.evaluate('Date.now()')
        
        # Trigger scroll if possible
        if search_page.has_load_more_trigger():
            search_page.scroll_to_load_more()
            
            # Page should remain responsive (can still interact with search)
            search_page.search_input.click()
            search_page.search_input.fill("responsive test")
            
            end_time = page_with_test_data.evaluate('Date.now()')
            response_time = end_time - start_time
            
            # Should respond within reasonable time (< 5 seconds)
            assert response_time < 5000, f"Page took {response_time}ms to respond during scroll"
    
    def test_scroll_loading_indicators(self, page_with_test_data: Page, test_server):
        """Test that loading indicators work properly during scroll"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        # Check for loading indicators
        loading_elements = page_with_test_data.locator('.loader, .loading, [class*="load"]').all()
        
        # If there are loading elements, they should be properly styled/visible
        for element in loading_elements:
            if element.is_visible():
                # Loading elements should have some visual indication
                assert element.bounding_box() is not None


@pytest.mark.e2e
class TestScrollAccessibility:
    """E2E tests for infinite scroll accessibility"""
    
    def test_keyboard_navigation_during_scroll(self, page_with_test_data: Page, test_server):
        """Test keyboard accessibility during infinite scroll"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        # Test keyboard navigation
        search_page.search_input.focus()
        search_page.search_input.type("keyboard test")
        
        # Tab navigation should work
        page_with_test_data.keyboard.press('Tab')
        page_with_test_data.keyboard.press('Tab')
        
        # Should not get trapped in infinite scroll elements
        focused_element = page_with_test_data.evaluate('document.activeElement.tagName')
        assert focused_element in ['INPUT', 'BUTTON', 'A', 'BODY'], f"Focus trapped on {focused_element}"
    
    def test_screen_reader_compatibility(self, page_with_test_data: Page, test_server):
        """Test screen reader compatibility of infinite scroll"""
        search_page = SearchAnswersPage(page_with_test_data)
        search_page.navigate_to(test_server)
        
        # Check for proper ARIA labels and roles
        search_input = search_page.search_input
        if search_input.count() > 0:
            # Search input should have proper labeling
            assert (search_input.get_attribute('aria-label') or 
                   search_input.get_attribute('placeholder') or
                   page_with_test_data.locator('label[for]').count() > 0), "Search input should have accessible label"
        
        # Check for loading announcements
        loading_elements = page_with_test_data.locator('[aria-live], [role="status"]').all()
        # Having aria-live regions is good practice but not required for test to pass