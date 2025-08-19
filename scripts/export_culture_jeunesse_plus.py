import sqlite3
import csv

db_path = "gdn.db"
output_csv = "culture_jeunesse_plus.csv"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Liste élargie de mots-clés liés à la jeunesse et dispositifs culturels
query = """
SELECT rowid, title, text
FROM contrib_fts
WHERE contrib_fts MATCH '
    culture AND (
        jeunesse OR jeune* OR étudiant* OR etudiant*
        OR "pass culture" OR "Pass Culture"
        OR mjc OR "maison des jeunes"
        OR scout* OR "colonie" OR "colonies de vacances"
        OR "éducation populaire" OR "centre social"
        OR "foyer des jeunes" OR université OR lycéen* OR collégien*
        OR "animation socio-culturelle"
    )';
"""

cur.execute(query)
rows = cur.fetchall()

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "title", "text"])
    writer.writerows(rows)

print(f"{len(rows)} résultats exportés vers {output_csv}")
