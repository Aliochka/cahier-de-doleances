import sqlite3

DB_PATH = "gdn.db"
CHUNK = 50000

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("Suppression de l'ancien index (s'il existe)...")
c.execute("DROP TABLE IF EXISTS contrib_fts;")

print("Création de la table FTS5...")
c.execute("""
CREATE VIRTUAL TABLE contrib_fts
USING fts5(title, text, content='contributions', content_rowid='id',
           tokenize='unicode61 remove_diacritics 2');
""")
conn.commit()

max_id = c.execute("SELECT MAX(id) FROM contributions;").fetchone()[0]
print(f"Max ID = {max_id}")

for start in range(1, max_id + 1, CHUNK):
    end = start + CHUNK - 1
    print(f"Insertion {start} → {end}...")
    c.execute(f"""
        INSERT INTO contrib_fts(rowid, title, text)
        SELECT id, IFNULL(title,''), IFNULL(text,'')
        FROM contributions
        WHERE id BETWEEN ? AND ?;
    """, (start, end))
    conn.commit()

print("Optimisation...")
c.execute("INSERT INTO contrib_fts(contrib_fts) VALUES('optimize');")
c.execute("PRAGMA optimize;")
conn.commit()

print("Index reconstruit ✅")
conn.close()
