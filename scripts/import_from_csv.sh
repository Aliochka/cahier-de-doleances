#!/usr/bin/env bash
set -euo pipefail

# === Config ===
EXPORT_DIR="${1:-./exports}"          # dossier des CSV (argument 1 ou ./exports)
DB_URL="${DATABASE_URL:-}"             # doit être défini dans l'env
PSQL=(psql "$DB_URL" -v ON_ERROR_STOP=1 -q -X)

# Si tu veux forcer le nettoyage avant import: export FORCE_TRUNCATE=1
FORCE_TRUNCATE="${FORCE_TRUNCATE:-0}"

# === Helpers ===
die() { echo "❌ $*" >&2; exit 1; }
info(){ echo -e "👉 $*"; }
ok()  { echo -e "✅ $*"; }

require_file() { [[ -f "$1" ]] || die "Fichier introuvable: $1"; }
require_db()   { [[ -n "$DB_URL" ]] || die "DATABASE_URL non défini dans l'environnement."; }

count_table() { "${PSQL[@]}" -c "SELECT COUNT(*) FROM $1;" | tr -d ' \n' || true; }

copy_table() {
  local table="$1"; shift
  local cols="$1"; shift
  local file="$1"; shift

  require_file "$file"
  info "Import $table ← $(basename "$file")"
  # \copy attend l'ordre des colonnes donné ici. Les CSV exportés via sqlite3 suivent ce même ordre.
  "${PSQL[@]}" -c "\copy $table ($cols) FROM '$file' CSV HEADER"
  local n; n="$(count_table "$table")"
  ok "Import $table terminé — lignes: $n"
}

empty_or_exit() {
  local t="$1"
  local n; n="$(count_table "$t")"
  if [[ "$n" != "0" ]]; then
    if [[ "$FORCE_TRUNCATE" == "1" ]]; then
      info "TRUNCATE $t (FORCE_TRUNCATE=1)"
      "${PSQL[@]}" -c "TRUNCATE TABLE $t;"
    else
      die "La table $t contient déjà $n lignes. Annule. (export FORCE_TRUNCATE=1 pour vider)"
    fi
  fi
}

# === Début ===
require_db
[[ -d "$EXPORT_DIR" ]] || die "Dossier exports introuvable: $EXPORT_DIR"

info "Pré-flight: vérification que les tables sont vides (ou TRUNCATE si FORCE_TRUNCATE=1)…"
for t in contribution_topics topic_aliases topics answer_options answers contributions options questions authors forms; do
  empty_or_exit "$t"
done
ok "Pré-flight OK."

# Petits réglages de session pour accélérer un peu
"${PSQL[@]}" -c "SET statement_timeout=0;"
"${PSQL[@]}" -c "SET maintenance_work_mem='512MB';"
"${PSQL[@]}" -c "SET synchronous_commit=off;"
"${PSQL[@]}" -c "SET work_mem='64MB';"
"${PSQL[@]}" -c "SET client_min_messages=warning;"

# === Import dans le bon ordre ===
copy_table "forms"               "id,name,version,source" \
           "$EXPORT_DIR/forms.csv"

copy_table "authors"             "id,source_author_id,name,email_hash,zipcode,city,age_range,gender" \
           "$EXPORT_DIR/authors.csv"

copy_table "questions"           "id,form_id,question_code,prompt,section,position,type,options_json" \
           "$EXPORT_DIR/questions.csv"

copy_table "options"             "id,question_id,code,label,position,meta_json" \
           "$EXPORT_DIR/options.csv"

# contributions.csv doit avoir 'submitted_at' déjà nettoyé (KO -> NULL) au format YYYY-MM-DD HH:MM:SS
copy_table "contributions"       "id,source_contribution_id,author_id,form_id,source,theme_id,submitted_at,title,import_batch_id,raw_hash,raw_json" \
           "$EXPORT_DIR/contributions.csv"

copy_table "answers"             "id,contribution_id,question_id,position,text,value_json" \
           "$EXPORT_DIR/answers.csv"

copy_table "answer_options"      "answer_id,option_id" \
           "$EXPORT_DIR/answer_options.csv"

copy_table "topics"              "id,slug,label,parent_id,depth,sort_order,meta_json" \
           "$EXPORT_DIR/topics.csv"

copy_table "topic_aliases"       "id,topic_id,alias" \
           "$EXPORT_DIR/topic_aliases.csv"

copy_table "contribution_topics" "contribution_id,topic_id" \
           "$EXPORT_DIR/contribution_topics.csv"

# === Sanity checks ===
info "Sanity checks…"
"${PSQL[@]}" -c "SELECT 'contributions' AS t, COUNT(*) AS n FROM contributions
          UNION ALL SELECT 'answers', COUNT(*) FROM answers
          UNION ALL SELECT 'authors', COUNT(*) FROM authors
          UNION ALL SELECT 'questions', COUNT(*) FROM questions
          UNION ALL SELECT 'options', COUNT(*) FROM options
          UNION ALL SELECT 'topics', COUNT(*) FROM topics;"

"${PSQL[@]}" -c "SELECT MIN(submitted_at) AS min_ts, MAX(submitted_at) AS max_ts
          FROM contributions WHERE submitted_at IS NOT NULL;"

ok "Import CSV terminé 🎉
Prochaine étape : appliquer la migration des FKs + index (post_import_fks_idx), puis la FTS Postgres."
