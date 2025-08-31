#!/usr/bin/env python3
"""
Basic testing setup that actually works
"""
import subprocess
import sys
import os


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
            # Show first few lines only
            lines = result.stdout.strip().split('\n')[:3]
            for line in lines:
                print(f"   {line}")
        return True


def main():
    """Setup basic testing that works"""
    print("🚀 Setting up WORKING testing environment")
    print("=" * 50)
    
    success = True
    
    # Install basic test dependencies
    success &= run_command(
        "pip install pytest httpx beautifulsoup4 psutil",
        "Installing basic test dependencies"
    )
    
    # Test that our critical tests work
    success &= run_command(
        "python scripts/run_tests.py --critical",
        "Testing critical functionality"
    )
    
    # Test quick tests
    success &= run_command(
        "python scripts/run_tests.py --quick",
        "Testing basic functionality"
    )
    
    # Setup simple pre-commit (optional)
    if success:
        install_precommit = input("Install pre-commit hooks? (y/N): ").lower().startswith('y')
        if install_precommit:
            success &= run_command("pip install pre-commit", "Installing pre-commit")
            # Copy simple config
            success &= run_command(
                "cp .pre-commit-config-simple.yaml .pre-commit-config.yaml",
                "Setting up simple pre-commit config"
            )
            success &= run_command("pre-commit install", "Installing pre-commit hooks")
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 Basic testing environment ready!")
        print("\n✅ What works:")
        print("• python scripts/run_tests.py --critical   # Essential cache+scroll tests")
        print("• python scripts/run_tests.py --quick      # Basic functionality tests")
        print("• pytest tests/test_basic.py -v            # Individual basic tests")
        print("• pytest tests/test_cache.py::TestCacheIntelligence::test_popularity_based_ttl")
        print("\n🛡️  Pre-commit protection:")
        print("• git commit automatically runs critical tests")
        print("• Prevents breaking cache/scroll functionality")
        print("\n🚀 Next steps to expand:")
        print("• Fix database fixtures for full integration tests")
        print("• Add more endpoint-specific tests")
        print("• Setup Playwright for E2E tests")
    else:
        print("💥 Setup had issues - but basic tests should still work")
        print("Try: python scripts/run_tests.py --critical")


if __name__ == "__main__":
    main()