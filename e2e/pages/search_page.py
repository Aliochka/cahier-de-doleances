# e2e/pages/search_page.py
"""Page objects for search functionality"""
from playwright.sync_api import Page, expect


class SearchAnswersPage:
    """Page object for search answers page"""
    
    def __init__(self, page: Page):
        self.page = page
        self.search_input = page.locator('input[name="q"]')
        self.search_loading = page.locator('.search-loading')
        self.answers_list = page.locator('#answers-list')
        self.load_more_sentinel = page.locator('.search-load-more-sentinel, .load-more-sentinel')
    
    def navigate_to(self, base_url: str):
        """Navigate to search answers page"""
        self.page.goto(f"{base_url}/search/answers")
    
    def search(self, query: str):
        """Perform a search"""
        self.search_input.fill(query)
        # HTMX will trigger automatically, wait for response
        self.page.wait_for_timeout(500)  # Brief wait for debounce
    
    def wait_for_results(self):
        """Wait for search results to load"""
        # Wait for loading indicator to disappear
        expect(self.search_loading).to_be_hidden()
        # Wait for results container to be visible
        expect(self.answers_list).to_be_visible()
    
    def get_answer_cards(self):
        """Get all answer card elements"""
        return self.answers_list.locator('[class*="answer"], [class*="card"]').all()
    
    def scroll_to_load_more(self):
        """Scroll to trigger infinite scroll"""
        if self.load_more_sentinel.count() > 0:
            self.load_more_sentinel.scroll_into_view_if_needed()
            self.page.wait_for_timeout(1000)  # Wait for HTMX to load more content
    
    def has_load_more_trigger(self) -> bool:
        """Check if there's a load more trigger visible"""
        return self.load_more_sentinel.count() > 0 and self.load_more_sentinel.is_visible()


class SearchQuestionsPage:
    """Page object for search questions page"""
    
    def __init__(self, page: Page):
        self.page = page
        self.forms_section = page.locator('[class*="forms"]').first
        self.questions_section = page.locator('[class*="questions"]').first
    
    def navigate_to(self, base_url: str):
        """Navigate to search questions page"""
        self.page.goto(f"{base_url}/search/questions")
    
    def wait_for_sections_to_load(self):
        """Wait for both sections to load"""
        # Wait for either forms or questions section to be visible
        expect(self.page.locator('body')).to_be_visible()


class QuestionDetailPage:
    """Page object for question detail page"""
    
    def __init__(self, page: Page):
        self.page = page
        self.answers_list = page.locator('#answers-list')
        self.load_more_sentinel = page.locator('.load-more-sentinel')
        self.search_input = page.locator('input[name="q"]')
    
    def navigate_to(self, base_url: str, question_id: int, slug: str = "question"):
        """Navigate to question detail page"""
        self.page.goto(f"{base_url}/questions/{question_id}-{slug}")
    
    def search_within_answers(self, query: str):
        """Search within question answers"""
        if self.search_input.count() > 0:
            self.search_input.fill(query)
            self.page.wait_for_timeout(500)
    
    def scroll_to_load_more_answers(self):
        """Scroll to load more answers"""
        if self.load_more_sentinel.count() > 0:
            self.load_more_sentinel.scroll_into_view_if_needed()
            self.page.wait_for_timeout(1000)
    
    def get_answer_count(self) -> int:
        """Get number of visible answers"""
        return self.answers_list.locator('[class*="answer"], [class*="card"]').count()