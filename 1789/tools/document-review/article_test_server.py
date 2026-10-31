"""Loopback browser-test fixture; every decision journal is synthetic and temporary."""

import argparse
import tempfile
from pathlib import Path

from reviewlib import Store
from server import ReviewServer
from test_articles import synthetic_parents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=17895)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cahier-articles-browser-") as directory:
        root = Path(directory)
        store = Store(root / "parents.jsonl")
        synthetic_parents(store, store.journal)
        server = ReviewServer(args.port, store, root / "articles.jsonl", root / "exports")
        print(f"Synthetic fixture ready: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
