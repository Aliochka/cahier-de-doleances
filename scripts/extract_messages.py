#!/usr/bin/env python3
"""
Extract translatable messages from the application
"""
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def extract_messages():
    """Extract messages to .pot file"""
    print("Extracting messages...")
    
    # Change to project root directory
    os.chdir(PROJECT_ROOT)
    
    # Run pybabel extract
    cmd = [
        'pybabel', 'extract',
        '-F', 'babel.cfg',
        '-k', '_',
        '-k', 'ngettext:1,2',
        '-o', 'translations/messages.pot',
        '.'
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Messages extracted to translations/messages.pot")
        if result.stdout:
            print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error extracting messages: {e}")
        if e.stderr:
            print(e.stderr)
        sys.exit(1)

if __name__ == "__main__":
    extract_messages()