"""Export reviewed source units locally, never PostgreSQL or vector indexes."""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parents[1] / "tools/1789-document-review"
sys.path.insert(0, str(TOOL))
from articles import Articles  # noqa: E402
from reviewlib import Store  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-journal", type=Path)
    parser.add_argument("--article-journal", type=Path)
    parser.add_argument("--output", type=Path, default=HERE / "data")
    args = parser.parse_args()
    engine = Articles(Store(args.parent_journal), args.article_journal)
    import json

    print(json.dumps(engine.write_export(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
