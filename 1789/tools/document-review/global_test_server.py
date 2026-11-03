"""Browser fixture over the full corpus, private cloned journals and temporary corrections."""

import argparse
import tempfile
from pathlib import Path

from collection import discover
from reviewlib import PRIVATE, Store
from server import ReviewServer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17898)
    p.add_argument("--corpus-directory", type=Path, help="Immutable generation to test before activation")
    args = p.parse_args()
    directory = args.corpus_directory or discover()
    if directory is None:
        raise SystemExit("Build the local corpus first")
    with tempfile.TemporaryDirectory(prefix="1789-global-ui-test-") as temp:
        root = Path(temp)
        for name in ["decisions.jsonl", "article-decisions.jsonl"]:
            (root / name).write_bytes((PRIVATE / name).read_bytes())
        server = ReviewServer(
            args.port,
            Store(root / "decisions.jsonl"),
            root / "article-decisions.jsonl",
            root / "exports",
            corpus_directory=directory,
            override_directory=root / "overrides",
        )
        print("Global synthetic fixture ready at http://127.0.0.1:" + str(args.port), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
