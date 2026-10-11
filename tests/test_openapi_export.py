"""Contract generation runs in a fresh process with no application test fixtures."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/export_openapi.py"
SNAPSHOT = ROOT / "frontend/contracts/openapi.json"


def run_export(*args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_offline_deterministic_contract_and_reference_closure(tmp_path):
    # Bogus deployment settings must never be consulted by the exporter.
    environment = dict(
        os.environ,
        ENV="prod",
        DATABASE_URL="postgresql://invalid.invalid/production",
        SECRET_KEY="your-secret-key-change-in-production",
        BASE_URL="https://wallace.invalid",
    )
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    for output in (first, second):
        result = run_export("--output", output, env=environment)
        assert result.returncode == 0, result.stderr
        assert "Duplicate Operation ID" not in result.stderr
    assert first.read_bytes() == second.read_bytes() == SNAPSHOT.read_bytes()
    schema = json.loads(first.read_text())
    from fastapi.openapi.models import OpenAPI

    OpenAPI.model_validate(schema)
    assert set(schema["paths"]) == {"/api/v1/forms", "/api/v1/forms/{form_id}"}
    operations = [path["get"]["operationId"] for path in schema["paths"].values()]
    assert len(set(operations)) == len(operations)
    models = schema["components"]["schemas"]
    assert set(models) == {
        "FormSummary",
        "FormDetail",
        "FormQuestion",
        "ApiError",
        "HTTPValidationError",
        "ValidationError",
    }
    for model in ("FormSummary", "FormDetail", "FormQuestion"):
        assert models[model]["properties"]["id"]["type"] == "string"
    assert models["FormQuestion"]["properties"]["form_id"]["type"] == "string"
    assert {"200", "404", "422", "408", "500", "503"} <= set(
        schema["paths"]["/api/v1/forms/{form_id}"]["get"]["responses"]
    )

    def check_refs(value):
        if isinstance(value, dict):
            if "$ref" in value:
                target = schema
                for part in value["$ref"].removeprefix("#/").split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for child in value.values():
                check_refs(child)
        elif isinstance(value, list):
            for child in value:
                check_refs(child)

    check_refs(schema)
    assert "wallace.invalid" not in first.read_text()
    assert str(ROOT) not in first.read_text()
    assert "synthetic-contract-key" not in first.read_text()


def test_check_detects_schema_drift_without_writing(tmp_path):
    target = tmp_path / "outdated.json"
    target.write_text("{}\n")
    result = run_export("--check", "--output", target)
    assert result.returncode == 1
    assert "outdated" in result.stderr
    assert target.read_text() == "{}\n"
    assert run_export("--check").returncode == 0


def test_export_rejects_attempted_database_connection(tmp_path):
    # Import in a fresh process, then explicitly attempt a DB connection.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from scripts.export_openapi import export_schema; export_schema(); import psycopg2; psycopg2.connect('dbname=contract')",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "connections are forbidden" in result.stderr
