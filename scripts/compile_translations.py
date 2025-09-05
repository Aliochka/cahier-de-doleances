#!/usr/bin/env python3
"""
Compile translation files (.po to .mo)
"""
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.i18n import LANGUAGES

def compile_translations():
    """Compile .po files to .mo files"""
    print("Compiling translations...")
    
    # Change to project root directory
    os.chdir(PROJECT_ROOT)
    
    for lang_code in LANGUAGES.keys():
        po_file = Path(f'translations/{lang_code}/LC_MESSAGES/messages.po')
        
        if not po_file.exists():
            print(f"❌ {lang_code}: .po file not found. Run init_translations.py first.")
            continue
        
        print(f"Compiling {lang_code}...")
        
        # Compile .po to .mo
        cmd = [
            'pybabel', 'compile',
            '-d', 'translations',
            '-l', lang_code
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  ✅ {lang_code}: compiled")
            if result.stdout:
                print(f"     {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"  ❌ {lang_code}: error - {e}")
            if e.stderr:
                print(f"     {e.stderr.strip()}")

    # Reload translations in the application
    print("\n🔄 Reloading translations...")
    try:
        from app.i18n import load_translations
        load_translations()
        print("✅ Translations reloaded")
    except Exception as e:
        print(f"❌ Error reloading translations: {e}")

if __name__ == "__main__":
    compile_translations()