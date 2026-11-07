"""Explicit local phase-1 commands. No production configuration is ever loaded."""

import argparse
import json
from pathlib import Path

from .artifacts import DECISIONS, REFERENCE, Artifacts
from .editorial import load_decisions, replay
from .safety import Destination
from .storage import apply_editorial, import_collection, migrate, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["validate-artifacts", "migrate", "import", "verify", "apply-editorial"]
    )
    parser.add_argument("--url")
    parser.add_argument("--expected-data-directory")
    parser.add_argument("--expected-system-id")
    parser.add_argument("--collection", type=Path, default=REFERENCE)
    parser.add_argument("--decisions", type=Path, default=DECISIONS)
    parser.add_argument("--previous-decisions", type=Path)
    args = parser.parse_args()
    destination = None
    try:
        if args.action == "validate-artifacts":
            artifacts = Artifacts(args.collection)
            projection = replay(artifacts, load_decisions(args.decisions))
            result = dict(artifacts.counts(), editorial_hash=projection["hash"], status="valid")
        else:
            if not all((args.url, args.expected_data_directory, args.expected_system_id)):
                parser.error("Explicit URL, expected data directory and system identifier required")
            destination = Destination(
                args.url, args.expected_data_directory, args.expected_system_id
            )
            if args.action == "migrate":
                migrate(destination)
                result = {"migration": "doc_0001"}
            else:
                artifacts = Artifacts(args.collection)
                bundle = load_decisions(args.decisions)
                if args.action == "import":
                    result = import_collection(destination, artifacts, bundle)
                elif args.action == "apply-editorial":
                    if args.previous_decisions is None:
                        parser.error("--previous-decisions required for explicit editorial replay")
                    result = apply_editorial(
                        destination, artifacts, load_decisions(args.previous_decisions), bundle
                    )
                else:
                    with destination.transaction(readonly=True) as c:
                        result = verify(c, artifacts, bundle)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        # Never print a raw DB exception that may contain a URL or historical text.
        detail = str(exc) if isinstance(exc, (ValueError, KeyError)) else type(exc).__name__
        print(json.dumps({"status": "failed", "reason": detail}, ensure_ascii=False))
        return 1
    finally:
        if destination:
            destination.close()


if __name__ == "__main__":
    raise SystemExit(main())
