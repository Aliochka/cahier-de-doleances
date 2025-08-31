#!/usr/bin/env python3
"""
Setup script for testing environment
"""
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description, check=True):
    """Run a command and handle errors"""
    print(f"📦 {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0 and check:
        print(f"❌ Failed: {description}")
        print(f"Error: {result.stderr}")
        return False
    else:
        print(f"✅ {description}")
        if result.stdout.strip():
            print(f"   {result.stdout.strip()}")
        return True


def main():
    """Setup testing environment"""
    print("🚀 Setting up testing environment for Cahier de Doléances")
    print("=" * 60)
    
    # Check Python version
    if sys.version_info < (3, 10):
        print("❌ Python 3.10+ is required")
        sys.exit(1)
    
    success = True
    
    # Install development dependencies
    success &= run_command(
        "pip install -r requirements-dev.txt",
        "Installing development dependencies"
    )
    
    # Install pre-commit
    success &= run_command(
        "pip install pre-commit",
        "Installing pre-commit"
    )
    
    # Setup pre-commit hooks
    success &= run_command(
        "pre-commit install",
        "Setting up pre-commit hooks"
    )
    
    # Install Playwright browsers
    success &= run_command(
        "playwright install chromium",
        "Installing Playwright browsers"
    )
    
    # Create test database (if using PostgreSQL locally)
    run_command(
        "createdb test_cahier_doleances",
        "Creating test database (optional)",
        check=False
    )
    
    # Run critical tests to verify setup
    success &= run_command(
        "python -m pytest tests/ -m 'cache or scroll' --no-cov -x -q",
        "Running critical tests to verify setup"
    )
    
    print("\n" + "=" * 60)
    
    if success:
        print("🎉 Testing environment setup complete!")
        print("\nNext steps:")
        print("1. Run tests: python scripts/run_tests.py --quick")
        print("2. Run critical tests: python scripts/run_tests.py --critical")
        print("3. Run E2E tests: python -m pytest e2e/ --browser=chromium")
        print("4. Check coverage: python scripts/run_tests.py --coverage")
    else:
        print("💥 Setup encountered some issues!")
        print("Please check the errors above and resolve them.")
        sys.exit(1)


if __name__ == "__main__":
    main()