"""Launch the existing loopback-only documentary review tool from its new location."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools/document-review"))
from server import main  # noqa: E402

if __name__ == "__main__":
    main()
