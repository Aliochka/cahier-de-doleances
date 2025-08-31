# playwright.config.py
import os
from playwright.sync_api import Playwright

# Playwright configuration
config = {
    "testDir": "e2e/tests",
    "timeout": 30000,  # 30 seconds per test
    "retries": 2 if os.getenv("CI") else 1,
    "workers": 2 if os.getenv("CI") else 4,
    
    "use": {
        "headless": True if os.getenv("CI") else False,
        "viewport": {"width": 1280, "height": 720},
        "ignoreHTTPSErrors": True,
        "screenshot": "only-on-failure",
        "video": "retain-on-failure",
        "trace": "retain-on-failure",
    },
    
    "projects": [
        {
            "name": "chromium",
            "use": {"channel": "chromium"},
        },
        # Can add more browsers later
        # {
        #     "name": "firefox",
        #     "use": {"channel": "firefox"},
        # },
        # {
        #     "name": "webkit",
        #     "use": {"channel": "webkit"},
        # },
    ],
    
    "webServer": {
        "command": "python -m uvicorn app.app:app --host localhost --port 8002",
        "port": 8002,
        "timeout": 120000,
        "env": {"ENV": "test"},
    } if not os.getenv("CI") else None,
}