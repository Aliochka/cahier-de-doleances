# e2e/conftest.py
import pytest
from playwright.sync_api import Browser, BrowserContext, Page
import subprocess
import time
import requests
import os


@pytest.fixture(scope="session")
def test_server():
    """Start test server for E2E tests"""
    # Start FastAPI server in background
    env = os.environ.copy()
    env['ENV'] = 'test'
    
    server_process = subprocess.Popen([
        "python", "-m", "uvicorn", 
        "app.app:app", 
        "--host", "localhost", 
        "--port", "8001",
        "--reload"
    ], env=env)
    
    # Wait for server to start
    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get("http://localhost:8001", timeout=1)
            if response.status_code in [200, 404]:  # 404 is OK, means server is responding
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            time.sleep(1)
    else:
        server_process.terminate()
        pytest.fail("Test server failed to start")
    
    yield "http://localhost:8001"
    
    # Cleanup
    server_process.terminate()
    server_process.wait()


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context for E2E tests"""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture
def page_with_test_data(page: Page, test_server):
    """Page fixture with test server and basic navigation"""
    page.goto(test_server)
    return page