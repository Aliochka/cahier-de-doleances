"""Execute the real Bash guard with simulated mounts/UIDs and inert binaries.

Only dummy files under tmp_path are used. No PostgreSQL process is started and
no database, Docker daemon, root privileges or existing mount is accessed.
"""

import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "deploy/postgres/existing-cluster.sh"


@pytest.fixture
def guard(tmp_path):
    cluster = tmp_path / "cluster"
    (cluster / "global").mkdir(parents=True)
    (cluster / "PG_VERSION").write_text("17\n")
    (cluster / "global/pg_control").write_text("inert control-file fixture\n")
    (tmp_path / "ssd-mounted").touch()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    for name, content in {
        "postgres": """#!/bin/bash
if [[ "${1:-}" == --version ]]; then
    echo "${TEST_SERVER_VERSION:-postgres (PostgreSQL) 17.11 (Debian)}"
else
    printf '%s\\n' postgres "$@" > "$TEST_EXEC_LOG"
fi
""",
        "gosu": """#!/bin/bash
printf '%s\\n' gosu "$@" > "$TEST_EXEC_LOG"
""",
    }.items():
        binary = binaries / name
        binary.write_text(content)
        binary.chmod(0o700)

    # Bash functions virtualize only reads of fixed mount paths and numeric
    # identities. The tested script itself is sourced unchanged; exec targets
    # the inert executables above, never a real server or privilege helper.
    harness = tmp_path / "harness.sh"
    harness.write_text("""#!/bin/bash
map_path() {
    case "$1" in
        /var/lib/postgresql/data*) printf '%s%s' "$TEST_CLUSTER" "${1#/var/lib/postgresql/data}" ;;
        /run/ssd-mounted) printf '%s/ssd-mounted' "$TEST_ROOT" ;;
        *) printf '%s' "$1" ;;
    esac
}
test() {
    if [[ "$#" == 2 && ( "$1" == -f || "$1" == -d || "$1" == -r ) ]]; then
        builtin test "$1" "$(map_path "$2")"
    else
        builtin test "$@"
    fi
}
cat() { /usr/bin/cat "$(map_path "$1")"; }
stat() {
    [[ "$1" == -c && "$2" == %u:%g ]] || return 90
    if [[ "$3" == "${TEST_BAD_OWNER_PATH:-}" ]]; then
        echo "${TEST_BAD_OWNER:-1000:999}"
    else
        echo 999:999
    fi
}
id() {
    case "$*" in
        '-u postgres'|'-g postgres') echo 999 ;;
        '-u') echo "${TEST_UID:-0}" ;;
        '-g') echo "${TEST_GID:-0}" ;;
        *) return 91 ;;
    esac
}
guard_script="$1"
shift
source "$guard_script"
""")
    log = tmp_path / "exec.log"

    def run(*args, variables=None):
        env = {
            "PATH": f"{binaries}:/usr/bin:/bin",
            "PGDATA": "/var/lib/postgresql/data",
            "PG_VERSION": "17.11-1.pgdg13+2",
            "TEST_ROOT": str(tmp_path),
            "TEST_CLUSTER": str(cluster),
            "TEST_EXEC_LOG": str(log),
        }
        for key, value in (variables or {}).items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        result = subprocess.run(
            ["/bin/bash", str(harness), str(GUARD), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result, log.read_text().splitlines() if log.exists() else []

    return run, cluster, tmp_path


@pytest.mark.parametrize("sql_user", ["cahier", "postgres", "", None])
@pytest.mark.parametrize("command", [(), ("postgres",)])
def test_sql_role_is_not_an_os_owner_or_command(guard, sql_user, command):
    run, _, _ = guard
    result, executed = run(*command, variables={"POSTGRES_USER": sql_user})
    assert result.returncode == 0, result.stderr
    assert executed == ["gosu", "postgres", "postgres", "-D", "/var/lib/postgresql/data"]


def test_preserves_server_arguments(guard):
    run, _, _ = guard
    result, executed = run("postgres", "-c", "max_connections=80")
    assert result.returncode == 0, result.stderr
    assert executed == [
        "gosu",
        "postgres",
        "postgres",
        "-c",
        "max_connections=80",
        "-D",
        "/var/lib/postgresql/data",
    ]


def test_matching_nonroot_uid_and_gid_can_start(guard):
    run, _, _ = guard
    result, executed = run(variables={"TEST_UID": "999", "TEST_GID": "999"})
    assert result.returncode == 0, result.stderr
    assert executed == ["postgres", "-D", "/var/lib/postgresql/data"]


@pytest.mark.parametrize(
    "variables, message",
    [
        ({"PGDATA": None}, "PGDATA"),
        ({"PGDATA": ""}, "PGDATA"),
        ({"PGDATA": "/other"}, "PGDATA"),
        ({"PG_VERSION": None}, "image must declare"),
        ({"PG_VERSION": ""}, "image must declare"),
        ({"PG_VERSION": "18.1"}, "image must declare"),
        ({"PG_VERSION": "17.12"}, "image must declare"),
        ({"TEST_SERVER_VERSION": "postgres (PostgreSQL) 18.1"}, "server binary"),
        ({"TEST_SERVER_VERSION": "postgres (PostgreSQL) 17.110"}, "server binary"),
        ({"TEST_UID": "1000", "TEST_GID": "999"}, "process must run"),
        ({"TEST_UID": "999", "TEST_GID": "1000"}, "process must run"),
    ],
)
def test_incompatible_environment_cannot_start(guard, variables, message):
    run, _, _ = guard
    result, executed = run(variables=variables)
    assert result.returncode != 0
    assert message in result.stderr
    assert executed == []


@pytest.mark.parametrize("path", ["", "/PG_VERSION", "/global/pg_control"])
@pytest.mark.parametrize("owner", ["1000:999", "999:1000"])
def test_incompatible_cluster_ownership_cannot_start(guard, path, owner):
    run, _, _ = guard
    result, executed = run(
        variables={
            "TEST_BAD_OWNER_PATH": f"/var/lib/postgresql/data{path}",
            "TEST_BAD_OWNER": owner,
        }
    )
    assert result.returncode != 0
    assert "ownership mismatch" in result.stderr
    assert executed == []


@pytest.mark.parametrize("missing", ["PG_VERSION", "global/pg_control", "ssd-mounted"])
def test_missing_cluster_or_ssd_marker_cannot_start(guard, missing):
    run, cluster, tmp_path = guard
    path = tmp_path / missing if missing == "ssd-mounted" else cluster / missing
    path.unlink()  # Only deletes this test's dummy file, never a database file.
    result, executed = run()
    assert result.returncode != 0
    assert "existing-cluster:" in result.stderr
    assert executed == []


def test_wrong_cluster_major_cannot_start(guard):
    run, cluster, _ = guard
    (cluster / "PG_VERSION").write_text("16\n")
    result, executed = run()
    assert result.returncode != 0
    assert "cluster must be PostgreSQL 17" in result.stderr
    assert executed == []


def test_absent_cluster_directory_is_never_initialized(guard):
    run, cluster, _ = guard
    cluster.rename(cluster.with_name("unused-fixture"))
    result, executed = run()
    assert result.returncode != 0
    assert "cluster directory is missing" in result.stderr
    assert executed == []


@pytest.mark.parametrize("command", ["bash", "initdb", "docker-entrypoint.sh", "-c", ""])
def test_other_commands_cannot_bypass_guard(guard, command):
    run, _, _ = guard
    result, executed = run(command)
    assert result.returncode != 0
    assert "only the postgres server command" in result.stderr
    assert executed == []


def test_compose_override_supplies_command_and_preserves_mounts():
    service = yaml.safe_load((ROOT / "deploy/postgres/compose.pgvector.override.yml").read_text())[
        "services"
    ]["postgres"]
    assert service["entrypoint"] == ["bash", "/usr/local/bin/existing-cluster.sh"]
    assert service["command"] == ["postgres"]
    assert service["environment"] == {"PGDATA": "/var/lib/postgresql/data"}
    assert [(v["source"], v["target"]) for v in service["volumes"]] == [
        ("/data/postgresql/pg17/data", "/var/lib/postgresql/data"),
        ("/data/postgresql/.ssd-mounted", "/run/ssd-mounted"),
    ]
    assert all(v["bind"]["create_host_path"] is False for v in service["volumes"])
    assert service["volumes"][1]["read_only"] is True
