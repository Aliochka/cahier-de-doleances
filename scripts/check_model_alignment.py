#!/usr/bin/env python3
"""
Script de vérification de l'alignement entre les modèles SQLAlchemy et la base de données PostgreSQL.

Usage:
    python scripts/check_model_alignment.py

Variables d'environnement:
    DATABASE_URL: URL de connexion PostgreSQL (obligatoire)
"""

import os
import sys
from typing import Any, Dict, List

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Inspector

# Charger les variables d'environnement depuis .env
# override=True pour donner priorité au .env sur les variables d'environnement existantes
load_dotenv(override=True)

# Ajouter le répertoire parent au path pour importer les modèles
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import Base  # noqa: E402 — standalone script adds repository root first


def get_database_url() -> str:
    """Récupère l'URL de la base de données depuis les variables d'environnement."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ Erreur: Variable d'environnement DATABASE_URL non définie")
        print("Solutions:")
        print("  1. Ajouter DATABASE_URL dans votre fichier .env")
        print(
            "  2. Ou exporter la variable: export DATABASE_URL='postgresql://user:pass@localhost/dbname'"
        )
        print("  3. Vérifier que le fichier .env existe dans le répertoire racine")
        sys.exit(1)

    # Normaliser l'URL pour SQLAlchemy 2.0
    if database_url.startswith("postgresql+psycopg2://"):
        database_url = database_url.replace("postgresql+psycopg2://", "postgresql://")
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://")

    return database_url


def get_db_structure(inspector: Inspector) -> Dict[str, Dict[str, Any]]:
    """Extrait la structure des tables depuis la base de données."""
    structure = {}

    for table_name in inspector.get_table_names():
        columns = {}
        for col in inspector.get_columns(table_name):
            columns[col["name"]] = {
                "type": str(col["type"]),
                "nullable": col["nullable"],
                "default": col["default"],
                "primary_key": col.get("primary_key", False),
            }

        # Récupérer les clés primaires
        pk_info = inspector.get_pk_constraint(table_name)
        if pk_info and pk_info["constrained_columns"]:
            for pk_col in pk_info["constrained_columns"]:
                if pk_col in columns:
                    columns[pk_col]["primary_key"] = True

        # Récupérer les clés étrangères
        fks = {}
        for fk in inspector.get_foreign_keys(table_name):
            for col in fk["constrained_columns"]:
                fks[col] = {
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"],
                }

        structure[table_name] = {"columns": columns, "foreign_keys": fks}

    return structure


def get_model_structure() -> Dict[str, Dict[str, Any]]:
    """Extrait la structure des modèles SQLAlchemy."""
    structure = {}

    for table_name, table in Base.metadata.tables.items():
        columns = {}
        fks = {}

        for col in table.columns:
            columns[col.name] = {
                "type": str(col.type),
                "nullable": col.nullable,
                "default": col.default,
                "primary_key": col.primary_key,
            }

            # Vérifier les clés étrangères
            if col.foreign_keys:
                for fk in col.foreign_keys:
                    fks[col.name] = {
                        "referred_table": fk.column.table.name,
                        "referred_columns": [fk.column.name],
                    }

        structure[table_name] = {"columns": columns, "foreign_keys": fks}

    return structure


def normalize_type(type_str: str) -> str:
    """Normalise les types SQL pour la comparaison."""
    type_str = type_str.upper()

    # Mappings des types
    mappings = {
        "CHARACTER VARYING": "VARCHAR",
        "BIGINT": "BIGINT",
        "INTEGER": "INTEGER",
        "TEXT": "TEXT",
        "TIMESTAMP WITHOUT TIME ZONE": "DATETIME",
        "TIMESTAMP": "DATETIME",
        "DATETIME": "DATETIME",
    }

    for db_type, normalized in mappings.items():
        if db_type in type_str:
            return normalized

    return type_str


def compare_structures(db_structure: Dict, model_structure: Dict) -> List[str]:
    """Compare les structures et retourne la liste des différences."""
    differences = []

    # Tables à ignorer (gérées automatiquement)
    ignored_tables = {"alembic_version"}

    db_tables = set(db_structure.keys()) - ignored_tables
    model_tables = set(model_structure.keys()) - ignored_tables

    # Tables manquantes
    if db_tables - model_tables:
        differences.append(
            f"❌ Tables présentes en BDD mais absentes des modèles: {db_tables - model_tables}"
        )

    if model_tables - db_tables:
        differences.append(
            f"❌ Tables présentes dans les modèles mais absentes en BDD: {model_tables - db_tables}"
        )

    # Colonnes à ignorer (générées automatiquement par triggers/extensions)
    ignored_columns = {
        "text_tsv",
        "prompt_tsv",
        "tsv_prompt",
        "prompt_unaccent",
        "name_unaccent",
        "tsv_name",
    }

    # Comparer les tables communes
    for table_name in db_tables & model_tables:
        db_table = db_structure[table_name]
        model_table = model_structure[table_name]

        db_cols = set(db_table["columns"].keys()) - ignored_columns
        model_cols = set(model_table["columns"].keys()) - ignored_columns

        # Colonnes manquantes
        if db_cols - model_cols:
            differences.append(
                f"❌ Table '{table_name}': colonnes en BDD mais absentes du modèle: {db_cols - model_cols}"
            )

        if model_cols - db_cols:
            differences.append(
                f"❌ Table '{table_name}': colonnes dans le modèle mais absentes en BDD: {model_cols - db_cols}"
            )

        # Comparer les types des colonnes communes
        for col_name in db_cols & model_cols:
            db_col = db_table["columns"][col_name]
            model_col = model_table["columns"][col_name]

            db_type = normalize_type(db_col["type"])
            model_type = normalize_type(model_col["type"])

            if db_type != model_type:
                differences.append(
                    f"⚠️  Table '{table_name}', colonne '{col_name}': type différent (BDD: {db_type}, Modèle: {model_type})"
                )

            if db_col["nullable"] != model_col["nullable"]:
                differences.append(
                    f"⚠️  Table '{table_name}', colonne '{col_name}': nullable différent (BDD: {db_col['nullable']}, Modèle: {model_col['nullable']})"
                )

    return differences


def main():
    """Fonction principale."""
    print("🔍 Vérification de l'alignement modèles SQLAlchemy ↔ Base de données PostgreSQL")
    print("=" * 80)

    try:
        database_url = get_database_url()
        engine = create_engine(database_url)
        inspector = inspect(engine)

        print("📊 Extraction de la structure de la base de données...")
        db_structure = get_db_structure(inspector)

        print("🏗️  Extraction de la structure des modèles SQLAlchemy...")
        model_structure = get_model_structure()

        print("⚖️  Comparaison des structures...")
        differences = compare_structures(db_structure, model_structure)

        print("=" * 80)

        if not differences:
            print("✅ Parfait! Les modèles SQLAlchemy sont alignés avec la base de données.")
            sys.exit(0)
        else:
            print(f"❌ {len(differences)} différence(s) détectée(s):")
            print()
            for diff in differences:
                print(f"  {diff}")

            print()
            print("🔧 Actions recommandées:")
            print("  1. Mettre à jour les modèles SQLAlchemy dans app/models.py")
            print("  2. Ou créer une migration Alembic si la BDD doit changer")
            print("  3. Relancer ce script pour vérifier")

            sys.exit(1)

    except Exception as e:
        print(f"💥 Erreur lors de la vérification: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
