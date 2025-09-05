#!/usr/bin/env python3
"""
Initialize translation files for supported languages
"""
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.i18n import LANGUAGES

def init_translations():
    """Initialize .po files for all languages"""
    print("Initializing translations...")
    
    # Change to project root directory
    os.chdir(PROJECT_ROOT)
    
    # Check if messages.pot exists
    pot_file = Path('translations/messages.pot')
    if not pot_file.exists():
        print("❌ messages.pot not found. Run extract_messages.py first.")
        sys.exit(1)
    
    for lang_code in LANGUAGES.keys():
        print(f"Initializing {lang_code}...")
        
        po_dir = Path(f'translations/{lang_code}/LC_MESSAGES')
        po_dir.mkdir(parents=True, exist_ok=True)
        po_file = po_dir / 'messages.po'
        
        if po_file.exists():
            print(f"  {lang_code}: .po file already exists, skipping...")
            continue
        
        # Initialize new .po file
        cmd = [
            'pybabel', 'init',
            '-i', 'translations/messages.pot',
            '-d', 'translations',
            '-l', lang_code
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  ✅ {lang_code}: initialized")
            if result.stdout:
                print(f"     {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {lang_code}: error - {e}")
            if e.stderr:
                print(f"     {e.stderr.strip()}")

if __name__ == "__main__":
    init_translations()