#!/bin/bash
# Script de vérification de l'alignement modèles/BDD
# Usage: ./scripts/check-alignment.sh

set -e

echo "🔍 Vérification de l'alignement modèles SQLAlchemy ↔ PostgreSQL"
echo "💡 Le script charge automatiquement DATABASE_URL depuis le fichier .env"
echo ""

# Lancer le script Python (il charge automatiquement le .env)
python scripts/check_model_alignment.py