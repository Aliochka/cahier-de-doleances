#!/usr/bin/env python3
import os
import sys
import argparse
import glob
import subprocess
from pathlib import Path

DEF_DB = "sandbox.db"
DEF_DATA_DIR = "data/example"
DEF_ALEMBIC_DIR = "alembic"

# Gabarit d’appel de TA pipeline (unitaire) ; {csv_glob}, {db_path}, {mapping} seront remplis
DEF_INGEST_CMD = (
     'python ingest/gdn_ingest.py ingest --csv "{csv_glob}" --db "{db_url}" '
     '--mapping "{mapping}" --batch "sandbox_$(date +%F)" --commit-every 10000 --defer-fts'
 )

def run(cmd, env=None):
    print(f"→ {cmd}")
    try:
        res = subprocess.run(cmd, shell=isinstance(cmd, str), env=env, check=True)
        return res.returncode
    except subprocess.CalledProcessError as e:
        print(f"✖ Command failed with code {e.returncode}")
        return e.returncode

def main():
    ap = argparse.ArgumentParser(description="Create/refresh sandbox.db with Alembic + multi-mapping CSV ingestion.")
    ap.add_argument("--db", default=DEF_DB, help="SQLite DB filename/path (default: sandbox.db)")
    ap.add_argument("--data-dir", default=DEF_DATA_DIR, help="Directory with test CSVs (default: data/example)")
    ap.add_argument("--alembic-dir", default=DEF_ALEMBIC_DIR, help="Alembic directory (default: alembic)")
    ap.add_argument("--ingest-cmd", default=DEF_INGEST_CMD,
                    help='Command template for ingestion. Use {csv_glob}, {db_path}, {mapping}.')
    ap.add_argument("--csv-pattern", default="*.csv", help="Glob pattern for CSVs if you use --mapping-only mode.")
    ap.add_argument("--keep-db", action="store_true", help="Do not delete existing DB before running.")
    ap.add_argument("--ingest-pairs", action="append", default=[],
                    help='Repeatable. Format: CSV_GLOB::MAPPING_PATH  (ex: data/example/alpha*.csv::ingest/mappings/alpha.json)')
    ap.add_argument("--mapping-only", action="store_true",
                    help="If set, run a single ingestion using --csv-pattern from --data-dir and the first mapping in --ingest-pairs.")
    args = ap.parse_args()

    db_path = Path(args.db)
    data_dir = Path(args.data_dir)

    # 0) Reset DB (unless --keep-db)
    if db_path.exists() and not args.keep_db:
        print(f"• Removing existing DB: {db_path}")
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) Alembic migrations
    env = os.environ.copy()
    env.setdefault("GDN_DB_PATH", str(db_path))
    env.setdefault("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")

    if not Path("alembic.ini").exists():
        print("⚠ alembic.ini not found at repo root. Ensure Alembic is configured, then re-run.")
        return 2

    db_url = f"sqlite:///{db_path.as_posix()}"
    code = run(["alembic", "-x", f"db_url={db_url}", "upgrade", "head"], env=env)
    if code != 0:
        return code

    # 2) Ingestion(s)
    pairs = args.ingest_pairs or []
    if args.mapping_only:
        if not pairs:
            print("✖ --mapping-only requires at least one --ingest-pairs to provide a mapping.")
            return 2
        first_mapping = pairs[0].split("::", 1)[-1].strip()
        csv_glob = str((data_dir / args.csv_pattern).as_posix())
        csv_files = glob.glob(csv_glob)
        if not csv_files:
            print(f"⚠ No CSVs found at {csv_glob}. Skipping ingestion.")
            return 0
        
        db_url = f"sqlite:///{db_path.as_posix()}"
        cmd = args.ingest_cmd.format(csv_glob=csv_glob, db_url=db_url, mapping=first_mapping)

        return run(cmd, env=env)

    if not pairs:
        print("⚠ No --ingest-pairs provided. Nothing to ingest. (DB schema created.)")
        print("   Example: --ingest-pairs 'data/example/A*.csv::ingest/mappings/A.json'")
        return 0

    for pair in pairs:
        try:
            csv_glob, mapping = pair.split("::", 1)
        except ValueError:
            print(f"✖ Invalid --ingest-pairs entry: {pair}. Expected format CSV_GLOB::MAPPING_PATH")
            return 2
        csv_glob = csv_glob.strip()
        mapping = mapping.strip()

        csv_files = glob.glob(csv_glob)
        if not csv_files:
            print(f"⚠ No CSVs found for {csv_glob}. Skipping this pair.")
            continue

        db_url = f"sqlite:///{db_path.as_posix()}"
        cmd = args.ingest_cmd.format(csv_glob=csv_glob, db_url=db_url, mapping=mapping)
        code = run(cmd, env=env)
        if code != 0:
            return code

    print(f"✅ Sandbox ready at {db_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
