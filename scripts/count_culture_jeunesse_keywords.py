import sqlite3
import csv

db_path = "gdn.db"
output_csv = "culture_jeunesse_counts.csv"

keywords = {
    "jeunesse": "jeunesse OR jeune*",
    "étudiant": "étudiant* OR etudiant*",
    "pass_culture": "\"pass culture\" OR \"Pass Culture\"",
    "mjc": "mjc OR \"maison des jeunes\"",
    "scouts": "scout*",
    "colonies": "colonie OR \"colonies de vacances\"",
    "education_populaire": "\"éducation populaire\"",
    "centre_social": "\"centre social\"",
    "foyer_jeunes": "\"foyer des jeunes\"",
    "université": "université",
    "lycéen": "lycéen*",
    "collégien": "collégien*",
    "animation_socioculturelle": "\"animation socio-culturelle\""
}

conn = sqlite3.connect(db_path)
cur = conn.cursor()

results = []

for label, expr in keywords.items():
    query = f"""
    SELECT COUNT(*) 
    FROM contrib_fts
    WHERE contrib_fts MATCH 'culture AND ({expr})';
    """
    cur.execute(query)
    count = cur.fetchone()[0]
    results.append((label, count))

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["keyword", "count"])
    writer.writerows(results)

print(f"Tableau exporté vers {output_csv}")
for label, count in results:
    print(f"{label:25s} {count}")
