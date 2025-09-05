#!/usr/bin/env python3
"""
Update existing translation files with new messages
"""
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.i18n import LANGUAGES

def update_translations():
    """Update .po files with new messages from .pot"""
    print("Updating translations...")
    
    # Change to project root directory
    os.chdir(PROJECT_ROOT)
    
    # Check if messages.pot exists
    pot_file = Path('translations/messages.pot')
    if not pot_file.exists():
        print("❌ messages.pot not found. Run extract_messages.py first.")
        sys.exit(1)
    
    for lang_code in LANGUAGES.keys():
        po_file = Path(f'translations/{lang_code}/LC_MESSAGES/messages.po')
        
        if not po_file.exists():
            print(f"❌ {lang_code}: .po file not found. Run init_translations.py first.")
            continue
        
        print(f"Updating {lang_code}...")
        
        # Update existing .po file
        cmd = [
            'pybabel', 'update',
            '-i', 'translations/messages.pot',
            '-d', 'translations',
            '-l', lang_code
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  ✅ {lang_code}: updated")
            if result.stdout:
                print(f"     {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {lang_code}: error - {e}")
            if e.stderr:
                print(f"     {e.stderr.strip()}")

if __name__ == "__main__":
    update_translations()