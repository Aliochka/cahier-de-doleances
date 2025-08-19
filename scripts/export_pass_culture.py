import sqlite3
import csv

db_path = "gdn.db"
output_csv = "analyse/pass_culture.csv"

conn = sqlite3.connect(db_path)
cur = conn.cursor()

query = """
SELECT rowid, title, text
FROM contrib_fts
WHERE contrib_fts MATCH '"pass culture"';
"""

cur.execute(query)
rows = cur.fetchall()

with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "title", "text"])
    writer.writerows(rows)

print(f"{len(rows)} résultats exportés vers {output_csv}")
