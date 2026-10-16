"""Export the registered v1 API in a synthetic, network-disabled process."""

import argparse
import json
import os
import socket
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend/contracts/openapi.json"


def export_schema() -> dict:
    # Dedicated CLI only: never inherit deployment secrets or read .env files.
    os.environ.clear()
    os.environ.update(
        PYTHON_DOTENV_DISABLED="1",
        ENV="test",
        BASE_URL="http://localhost:8000",
        DATABASE_URL="postgresql://contract:synthetic@127.0.0.1:1/contract",
        SECRET_KEY="synthetic-contract-key-not-for-authentication",
        LOGIN_EMAIL_ENABLED="false",
    )

    def forbidden(*args, **kwargs):
        raise RuntimeError("Network and database connections are forbidden during contract export")

    socket.socket.connect = forbidden
    socket.socket.connect_ex = forbidden
    socket.getaddrinfo = forbidden
    import psycopg2

    psycopg2.connect = forbidden
    sys.path.insert(0, str(ROOT))
    from app.app import app

    # Generate from the real application, including future registered API routers.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Duplicate Operation ID .*", category=UserWarning)
        schema = app.openapi()
    schema["paths"] = {
        path: value for path, value in schema["paths"].items() if path.startswith("/api/v1/")
    }
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "head", "post", "put", "patch", "delete", "options", "trace"}
    ]
    if len(operation_ids) != len(set(operation_ids)):
        raise ValueError("Duplicate operation IDs in /api/v1")

    # Retain the transitive closure of components referenced by public operations.
    components = schema.pop("components", {})
    retained: dict = {}

    def visit(value):
        if isinstance(value, dict):
            reference = value.get("$ref")
            if reference is not None:
                if not reference.startswith("#/components/"):
                    raise ValueError(f"Unsupported contract reference: {reference}")
                section, name = reference[len("#/components/") :].split("/", 1)
                name = name.replace("~1", "/").replace("~0", "~")
                group = retained.setdefault(section, {})
                if name not in group:
                    group[name] = components[section][name]
                    visit(group[name])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(schema)
    if retained:
        schema["components"] = retained
    return schema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=TARGET)
    parser.add_argument(
        "--check", action="store_true", help="Compare without modifying the snapshot"
    )
    args = parser.parse_args()
    document = json.dumps(export_schema(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not args.output.is_file() or args.output.read_text(encoding="utf-8") != document:
            parser.exit(
                1, "OpenAPI snapshot is outdated. Run pnpm contract:generate in frontend.\n"
            )
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(document, encoding="utf-8")


if __name__ == "__main__":
    main()
