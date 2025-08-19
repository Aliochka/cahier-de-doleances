use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use csv::StringRecord;
use flate2::read::GzDecoder;
use glob::glob;
use regex::Regex;
use rusqlite::{params, Connection, ToSql};
use serde::Deserialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    borrow::Cow,
    collections::{HashMap, HashSet},
    fs::File,
    io::{BufRead, BufReader, Read},
    path::PathBuf,
    time::Instant,
};
use zip::read::ZipArchive;
use std::io::Cursor;
use once_cell::sync::Lazy;

#[derive(Parser)]
#[command(name = "gdn_ingest", version, about = "Ingestion Grand Débat (Rust)")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Ingérer des CSV selon un mapping YAML
    Ingest {
        /// sqlite:///gdn.db  (ou chemin fichier ex: gdn.db)
        #[arg(long)]
        db: String,
        /// Un ou plusieurs chemins/globs CSV
        #[arg(long)]
        csv: Vec<String>,
        /// Mapping YAML
        #[arg(long)]
        mapping: PathBuf,
        /// Nom de batch
        #[arg(long, default_value = "import_rust")]
        batch: String,
        /// Commit toutes les N lignes
        #[arg(long, default_value_t = 10_000)]
        commit_every: usize,
        /// Logs toutes les N lignes
        #[arg(long, default_value_t = 2_000)]
        log_every: usize,
        /// Désactive les triggers FTS5 pendant l’ingestion puis rebuild
        #[arg(long, default_value_t = false)]
        defer_fts: bool,
    },
    /// Reconstruire answers_fts
    RebuildFts {
        #[arg(long)]
        db: String,
    },
}

#[derive(Deserialize, Debug)]
struct Mapping {
    form: FormInfo,
    #[serde(default)]
    defaults: Defaults,
    questions: Vec<QuestionMap>,
}

#[derive(Deserialize, Debug, Default)]
struct Defaults {
    #[serde(default)]
    author: AuthorMap,
    #[serde(default)]
    contribution: ContributionMap,
}

#[derive(Deserialize, Debug, Default, PartialEq)]
struct AuthorMap {
    source_author_id: Option<String>,
    name: Option<String>,
    email_hash: Option<String>,
    zipcode: Option<String>,
    city: Option<String>,
    age_range: Option<String>,
    gender: Option<String>,
}

#[derive(Deserialize, Debug, Default)]
struct ContributionMap {
    source_contribution_id: Option<String>,
    submitted_at: Option<String>,
    title: Option<String>,
    source: Option<String>,
}

#[derive(Deserialize, Debug)]
struct FormInfo {
    name: String,
    #[serde(default)]
    version: Option<String>,
    #[serde(default)]
    source: Option<String>,
}

#[derive(Deserialize, Debug)]
#[serde(rename_all = "snake_case")]
struct QuestionMap {
    code: String,
    prompt: String,
    #[serde(rename = "type")]
    qtype: String, // "text", "free_text", "single_choice", "multi_choice", "number","scale","date"
    #[serde(default)]
    section: Option<String>,
    #[serde(default)]
    position: Option<i64>,
    #[serde(default)]
    meta: Option<serde_json::Value>,

    // text/number/scale/date/single_choice (source unique)
    #[serde(default)]
    source_column: Option<String>,

    // free_text (concat colonnes)
    #[serde(default)]
    source: Option<FreeTextSource>,

    // multi_choice / statique
    #[serde(default)]
    options: Vec<OptionSpec>,

    // dynamiques
    #[serde(default)]
    options_from_values: bool,
    #[serde(default)]
    delimiter: Option<String>,
}

#[derive(Deserialize, Debug)]
struct FreeTextSource {
    columns: Vec<String>,
    #[serde(default = "default_joiner")]
    joiner: String,
}
fn default_joiner() -> String { "\n\n".into() }

#[derive(Deserialize, Debug)]
struct OptionSpec {
    code: String,
    label: String,
    #[serde(default)]
    position: Option<i64>,
    #[serde(default)]
    meta: Option<serde_json::Value>,
    #[serde(default)]
    source_column: Option<String>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Ingest { db, csv, mapping, batch, commit_every, log_every, defer_fts } => {
            run_ingest(db, csv, mapping, batch, commit_every, log_every, defer_fts)
        }
        Cmd::RebuildFts { db } => rebuild_fts(db),
    }
}

fn open_conn(db: &str) -> Result<Connection> {
    // accepte "sqlite:///gdn.db" ou "gdn.db"
    let path = db.strip_prefix("sqlite:///").unwrap_or(db);
    let conn = Connection::open(path)?;
    // PRAGMAs perfs
    conn.execute_batch(
        r#"
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=NORMAL;
        PRAGMA temp_store=MEMORY;
        PRAGMA cache_size=-200000;
    "#,
    )?;
    Ok(conn)
}

fn rebuild_fts(db: String) -> Result<()> {
    let conn = open_conn(&db)?;
    conn.execute(
        "INSERT INTO answers_fts(answers_fts) VALUES('rebuild');",
        [],
    )?;
    println!("[fts] answers_fts rebuild OK");
    Ok(())
}

// ---------- Helpers SQL (IDs & caches) ----------

struct Caches {
    qid_by_code: HashMap<String, i64>,
    // options statiques: (question_id, label) -> option_id
    opt_by_qid_label: HashMap<(i64, String), i64>,
    // options dynamiques déjà créées: (question_id, label)
    dyn_seen: HashSet<(i64, String)>,
}

fn preload_form(conn: &Connection, f: &FormInfo) -> Result<i64> {
    let mut q = conn.prepare("SELECT id FROM forms WHERE name=?1 AND ifnull(version,'')=ifnull(?2,'') AND ifnull(source,'')=ifnull(?3,'')")?;
    if let Ok(mut rows) = q.query(params![&f.name, &f.version, &f.source]) {
        if let Some(r) = rows.next()? { return Ok(r.get(0)?); }
    }
    conn.execute(
        "INSERT INTO forms(name,version,source) VALUES(?1,?2,?3)",
        params![&f.name, &f.version, &f.source],
    )?;
    Ok(conn.last_insert_rowid())
}

fn preload_questions_and_options(conn: &Connection, form_id: i64, mapping: &Mapping) -> Result<Caches> {
    let mut caches = Caches {
        qid_by_code: HashMap::new(),
        opt_by_qid_label: HashMap::new(),
        dyn_seen: HashSet::new(),
    };
    // questions
    for qm in &mapping.questions {
        let qid = ensure_question(conn, form_id, qm)?;
        caches.qid_by_code.insert(qm.code.clone(), qid);
        // options statiques
        for opt in &qm.options {
            let oid = ensure_option(conn, qid, &opt.code, &opt.label, opt.position)?;
            caches.opt_by_qid_label.insert((qid, opt.label.clone()), oid);
        }
    }
    Ok(caches)
}

fn ensure_question(conn: &Connection, form_id: i64, qm: &QuestionMap) -> Result<i64> {
    let mut q = conn.prepare("SELECT id FROM questions WHERE form_id=?1 AND question_code=?2")?;
    if let Ok(mut rows) = q.query(params![form_id, &qm.code]) {
        if let Some(r) = rows.next()? { return Ok(r.get(0)?); }
    }
    conn.execute(
        "INSERT INTO questions(form_id,question_code,prompt,section,position,type,options_json)
         VALUES(?1,?2,?3,?4,?5,?6,?7)",
        params![
            form_id,
            &qm.code,
            &qm.prompt,
            &qm.section,
            &qm.position,
            &qm.qtype,
            &qm.meta.as_ref().map(|v| v.to_string())
        ],
    )?;
    Ok(conn.last_insert_rowid())
}

// ---------- Slugify optimisé (regex compilée une seule fois) ----------
static SLUG_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"[^a-z0-9]+").unwrap());
fn slugify(s: &str) -> String {
    let lower = s.to_lowercase();
    let collapsed = SLUG_RE.replace_all(&lower, "-");
    collapsed.trim_matches('-').to_string()
}

fn ensure_dynamic_option(conn: &Connection, caches: &mut Caches, qid: i64, label: &str) -> Result<i64> {
    if caches.dyn_seen.contains(&(qid, label.to_string())) {
        if let Some(&oid) = caches.opt_by_qid_label.get(&(qid, label.to_string())) {
            return Ok(oid);
        }
    }
    let code = {
        let mut c = slugify(label);
        if c.is_empty() { c = "na".into(); }
        if c.len() > 64 { c.truncate(64); }
        c
    };
    let oid = ensure_option(conn, qid, &code, label, None)?;
    caches.opt_by_qid_label.insert((qid, label.to_string()), oid);
    caches.dyn_seen.insert((qid, label.to_string()));
    Ok(oid)
}

// ---------- Indexes uniques nécessaires aux UPSERT ----------
fn ensure_ingest_indexes(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        r#"
        -- contributions: dédup par raw_hash
        CREATE UNIQUE INDEX IF NOT EXISTS idx_contributions_rawhash
            ON contributions(raw_hash);

        -- answers: une ligne par (contribution, question)
        CREATE UNIQUE INDEX IF NOT EXISTS idx_answers_unique
            ON answers(contribution_id, question_id);

        -- options: code unique dans une question
        CREATE UNIQUE INDEX IF NOT EXISTS idx_options_unique
            ON options(question_id, code);

        -- answer_options: éviter les doublons
        CREATE UNIQUE INDEX IF NOT EXISTS idx_answer_options_unique
            ON answer_options(answer_id, option_id);

        -- authors: clés optionnelles (si présentes)
        CREATE UNIQUE INDEX IF NOT EXISTS idx_authors_emailhash
            ON authors(email_hash);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_authors_source_author_id
            ON authors(source_author_id);
        "#
    )?;
    Ok(())
}

// ---------- Auteur / Contribution ----------

// Authors — UPSERT + RETURNING si une clé est dispo
fn get_or_create_author(conn: &Connection, amap: &AuthorMap, row: &StringRecord, headers: &csv::StringRecord) -> Result<Option<i64>> {
    if amap == &AuthorMap::default() { return Ok(None); }
    let col_val = |name: &Option<String>| -> Option<Cow<'_, str>> {
        name.as_ref().and_then(|n| headers.iter().position(|h| h == n).and_then(|i| row.get(i).map(Cow::from)))
    };
    let email_hash = col_val(&amap.email_hash).map(|s| s.into_owned());
    let source_author_id = col_val(&amap.source_author_id).map(|s| s.into_owned());

    let name = col_val(&amap.name).map(|s| s.into_owned());
    let zipcode = col_val(&amap.zipcode).map(|s| s.into_owned());
    let city = col_val(&amap.city).map(|s| s.into_owned());
    let age_range = col_val(&amap.age_range).map(|s| s.into_owned());
    let gender = col_val(&amap.gender).map(|s| s.into_owned());

    if email_hash.is_some() {
        let mut stmt = conn.prepare(
            r#"
            INSERT INTO authors(source_author_id, name, email_hash, zipcode, city, age_range, gender)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
            ON CONFLICT(email_hash) DO UPDATE SET
                source_author_id = COALESCE(authors.source_author_id, excluded.source_author_id),
                name            = COALESCE(authors.name,            excluded.name),
                zipcode         = COALESCE(authors.zipcode,         excluded.zipcode),
                city            = COALESCE(authors.city,            excluded.city),
                age_range       = COALESCE(authors.age_range,       excluded.age_range),
                gender          = COALESCE(authors.gender,          excluded.gender)
            RETURNING id
            "#
        )?;
        let id: i64 = stmt.query_row(
            params![
                source_author_id.as_deref(),
                name.as_deref(),
                email_hash.as_deref(),
                zipcode.as_deref(),
                city.as_deref(),
                age_range.as_deref(),
                gender.as_deref(),
            ],
            |r| r.get(0),
        )?;
        return Ok(Some(id));
    }

    if source_author_id.is_some() {
        let mut stmt = conn.prepare(
            r#"
            INSERT INTO authors(source_author_id, name, email_hash, zipcode, city, age_range, gender)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)
            ON CONFLICT(source_author_id) DO UPDATE SET
                email_hash      = COALESCE(authors.email_hash,      excluded.email_hash),
                name            = COALESCE(authors.name,            excluded.name),
                zipcode         = COALESCE(authors.zipcode,         excluded.zipcode),
                city            = COALESCE(authors.city,            excluded.city),
                age_range       = COALESCE(authors.age_range,       excluded.age_range),
                gender          = COALESCE(authors.gender,          excluded.gender)
            RETURNING id
            "#
        )?;
        let id: i64 = stmt.query_row(
            params![
                source_author_id.as_deref(),
                name.as_deref(),
                email_hash.as_deref(),
                zipcode.as_deref(),
                city.as_deref(),
                age_range.as_deref(),
                gender.as_deref(),
            ],
            |r| r.get(0),
        )?;
        return Ok(Some(id));
    }

    // Pas de clé → on insère naïvement
    conn.execute(
        "INSERT INTO authors(source_author_id,name,email_hash,zipcode,city,age_range,gender)
         VALUES(?1,?2,?3,?4,?5,?6,?7)",
        params![
            source_author_id.as_deref(),
            name.as_deref(),
            email_hash.as_deref(),
            zipcode.as_deref(),
            city.as_deref(),
            age_range.as_deref(),
            gender.as_deref(),
        ],
    )?;
    Ok(Some(conn.last_insert_rowid()))
}

// Contributions — UPSERT + RETURNING sur raw_hash
fn get_or_create_contribution(conn: &Connection, cmap: &ContributionMap, form_id: i64, author_id: Option<i64>, batch: &str, raw_json: &str, row_hash: &str, row: &StringRecord, headers: &csv::StringRecord) -> Result<i64> {
    let val = |name: &Option<String>| -> Option<String> {
        name.as_ref().and_then(|n| headers.iter().position(|h| h == n).and_then(|i| row.get(i).map(|s| s.to_string())))
    };
    let mut stmt = conn.prepare(
        r#"
        INSERT INTO contributions(
            source_contribution_id, author_id, form_id, source, submitted_at, title,
            import_batch_id, raw_hash, raw_json
        )
        VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
        ON CONFLICT(raw_hash) DO UPDATE SET id=id
        RETURNING id
        "#
    )?;
    let id: i64 = stmt.query_row(
        params![
            val(&cmap.source_contribution_id).as_deref(),
            &author_id as &dyn ToSql,
            &form_id,
            cmap.source.as_deref(),
            val(&cmap.submitted_at).as_deref(),
            val(&cmap.title).as_deref(),
            batch,
            row_hash,
            raw_json,
        ],
        |r| r.get(0),
    )?;
    Ok(id)
}

fn query_scalar<T: rusqlite::types::FromSql>(
    conn: &Connection,
    sql: &str,
    p: impl rusqlite::Params,
) -> Result<Option<T>> {
    let mut stmt = conn.prepare(sql)?;
    let mut rows = stmt.query(p)?;
    if let Some(r) = rows.next()? {
        Ok(Some(r.get(0)?))
    } else {
        Ok(None)
    }
}

// ---------- Answers (optimisées) ----------

fn upsert_answer_get_id(conn: &Connection, contribution_id: i64, question_id: i64) -> Result<i64> {
    // Crée la ligne si absente, sinon met à jour à l'identique pour retourner l'id
    let mut stmt = conn.prepare(
        r#"
        INSERT INTO answers(contribution_id, question_id, position, text, value_json)
        VALUES (?1, ?2, 1, NULL, NULL)
        ON CONFLICT(contribution_id, question_id) DO UPDATE SET position = answers.position
        RETURNING id
        "#
    )?;
    let id: i64 = stmt.query_row(params![contribution_id, question_id], |r| r.get(0))?;
    Ok(id)
}

fn ensure_text_answer(conn: &Connection, contribution_id: i64, question_id: i64, text_value: &str, joiner: &str) -> Result<()> {
    if text_value.trim().is_empty() { return Ok(()); }
    let aid = upsert_answer_get_id(conn, contribution_id, question_id)?;
    conn.execute(
        r#"
        UPDATE answers
        SET text = CASE
            WHEN text IS NULL OR length(trim(text))=0 THEN ?2
            WHEN instr(text, ?2)=0 THEN text || ?3 || ?2
            ELSE text
        END
        WHERE id = ?1
        "#,
        params![aid, text_value.trim(), joiner],
    )?;
    Ok(())
}

fn ensure_value_answer(conn: &Connection, contribution_id: i64, question_id: i64, value_json: &str) -> Result<()> {
    let aid = upsert_answer_get_id(conn, contribution_id, question_id)?;
    conn.execute("UPDATE answers SET value_json=?2 WHERE id=?1", params![aid, value_json])?;
    Ok(())
}

fn ensure_single_choice(conn: &Connection, contribution_id: i64, question_id: i64, option_id: i64) -> Result<()> {
    let aid = upsert_answer_get_id(conn, contribution_id, question_id)?;
    // remplace l'option
    conn.execute("DELETE FROM answer_options WHERE answer_id=?1", params![aid])?;
    conn.execute("INSERT OR IGNORE INTO answer_options(answer_id, option_id) VALUES(?1,?2)",
        params![aid, option_id])?;
    Ok(())
}

fn ensure_multi_choice(conn: &Connection, contribution_id: i64, question_id: i64, option_ids: &[i64]) -> Result<()> {
    if option_ids.is_empty() { return Ok(()); }
    let aid = upsert_answer_get_id(conn, contribution_id, question_id)?;
    for oid in option_ids {
        conn.execute("INSERT OR IGNORE INTO answer_options(answer_id, option_id) VALUES(?1,?2)", params![aid, oid])?;
    }
    Ok(())
}

// ---------- CSV utils ----------

enum AnyReader {
    Plain(BufReader<File>),
    Gz(BufReader<GzDecoder<File>>),
    Zip(Box<dyn Read>),
}
fn open_any(path: &str) -> Result<Box<dyn Read>> {
    if path.ends_with(".gz") {
        let f = File::open(path)?;
        let gz = GzDecoder::new(f);
        Ok(Box::new(BufReader::new(gz)))
    } else if path.ends_with(".zip") {
        let f = File::open(path)?;
        let mut zip = ZipArchive::new(f)?;
        for i in 0..zip.len() {
            let name = zip.by_index(i)?.name().to_lowercase();
            if name.ends_with(".csv") {
                let mut zf = zip.by_index(i)?;
                let mut buf = Vec::new();
                zf.read_to_end(&mut buf)?;
                // Cursor<Vec<u8>> vit assez longtemps (corrige E0597)
                return Ok(Box::new(Cursor::new(buf)));
            }
        }
        anyhow::bail!("zip sans CSV");
    } else {
        let f = File::open(path)?;
        Ok(Box::new(BufReader::new(f)))
    }
}

fn sha256_rowjson(rec: &serde_json::Value) -> String {
    let mut hasher = Sha256::new();
    hasher.update(rec.to_string().as_bytes());
    hex::encode(hasher.finalize())
}

// ---------- Options (UPSERT + RETURNING) ----------

fn ensure_option(conn: &Connection, question_id: i64, code: &str, label: &str, position: Option<i64>) -> Result<i64> {
    let mut stmt = conn.prepare(
        r#"
        INSERT INTO options(question_id, code, label, position)
        VALUES (?1, ?2, ?3, ?4)
        ON CONFLICT(question_id, code) DO UPDATE SET
            label = excluded.label,
            position = COALESCE(excluded.position, options.position)
        RETURNING id
        "#
    )?;
    let id: i64 = stmt.query_row(params![question_id, code, label, &position], |r| r.get(0))?;
    Ok(id)
}

// ---------- run_ingest ----------

fn run_ingest(db: String, csv_globs: Vec<String>, mapping_path: PathBuf, batch: String, commit_every: usize, log_every: usize, defer_fts: bool) -> Result<()> {
    // mapping
    let mapping_str = std::fs::read_to_string(&mapping_path)
        .with_context(|| format!("lecture mapping {:?}", mapping_path))?;
    let mapping: Mapping = serde_yaml::from_str(&mapping_str)?;

    // connex + form + caches
    let conn = open_conn(&db)?;
    // ⚠️ Ajout : index uniques nécessaires aux UPSERT
    ensure_ingest_indexes(&conn)?;

    let form_id = preload_form(&conn, &mapping.form)?;
    let mut caches = preload_questions_and_options(&conn, form_id, &mapping)?;
    println!("[ingest] form id={form_id} name='{}' version='{}'", mapping.form.name, mapping.form.version.as_deref().unwrap_or(""));

    if defer_fts {
        println!("[fts] désactivation des triggers FTS…");
        conn.execute_batch("DROP TRIGGER IF EXISTS answers_au; DROP TRIGGER IF EXISTS answers_ad; DROP TRIGGER IF EXISTS answers_ai;")?;
    }

    // expand globs
    let mut files = Vec::<String>::new();
    for g in csv_globs {
        for entry in glob(&g)? {
            files.push(entry?.to_string_lossy().into_owned());
        }
    }

    let t0 = Instant::now();
    let mut total = 0usize;

    for path in files {
        println!("[ingest] fichier: {path}");
        // open & csv reader
        let reader = open_any(&path)?;
        let mut rdr = csv::ReaderBuilder::new().from_reader(reader);

        let headers = rdr.headers()?.clone();

        // transactions par batch
        let mut pending = 0usize;
        let mut tx = conn.unchecked_transaction()?;

        for rec in rdr.records() {
            let rec = rec?;
            // raw_json pour audit + hash
            let mut rowmap = serde_json::Map::new();
            for (i, h) in headers.iter().enumerate() {
                if let Some(v) = rec.get(i) {
                    rowmap.insert(h.to_string(), serde_json::Value::String(v.to_string()));
                }
            }
            let raw_json = serde_json::Value::Object(rowmap);
            let row_hash = sha256_rowjson(&raw_json);

            // auteur + contribution
            let author_id = get_or_create_author(&tx, &mapping.defaults.author, &rec, &headers)?;
            let contrib_id = get_or_create_contribution(&tx, &mapping.defaults.contribution, form_id, author_id, &batch, &raw_json.to_string(), &row_hash, &rec, &headers)?;

            // questions
            for qm in &mapping.questions {
                let qid = *caches.qid_by_code.get(&qm.code).expect("qid");
                match qm.qtype.as_str() {
                    "free_text" => {
                        if let Some(src) = &qm.source {
                            let mut parts = Vec::new();
                            for c in &src.columns {
                                if let Some(ix) = headers.iter().position(|h| h == c) {
                                    if let Some(v) = rec.get(ix) { if !v.trim().is_empty() { parts.push(v.trim()); } }
                                }
                            }
                            if !parts.is_empty() {
                                let joiner = &src.joiner;
                                let val = parts.join(joiner);
                                ensure_text_answer(&tx, contrib_id, qid, &val, joiner)?;
                            }
                        }
                    }
                    "text" => {
                        if let Some(col) = &qm.source_column {
                            if let Some(ix) = headers.iter().position(|h| h == col) {
                                if let Some(v) = rec.get(ix) { if !v.trim().is_empty() {
                                    ensure_text_answer(&tx, contrib_id, qid, v.trim(), "\n\n")?;
                                }}
                            }
                        }
                    }
                    "number" | "scale" | "date" => {
                        if let Some(col) = &qm.source_column {
                            if let Some(ix) = headers.iter().position(|h| h == col) {
                                if let Some(v) = rec.get(ix) { if !v.trim().is_empty() {
                                    let vjson = json!({"value": v.trim()}).to_string();
                                    ensure_value_answer(&tx, contrib_id, qid, &vjson)?;
                                }}
                            }
                        }
                    }
                    "single_choice" => {
                        if let Some(col) = &qm.source_column {
                            if let Some(ix) = headers.iter().position(|h| h == col) {
                                if let Some(v) = rec.get(ix) { let raw = v.trim();
                                    if !raw.is_empty() {
                                        let oid = if qm.options_from_values {
                                            ensure_dynamic_option(&tx, &mut caches, qid, raw)?
                                        } else {
                                            if let Some(oid) = caches.opt_by_qid_label.get(&(qid, raw.to_string())) {
                                                *oid
                                            } else {
                                                ensure_dynamic_option(&tx, &mut caches, qid, raw)?
                                            }
                                        };
                                        ensure_single_choice(&tx, contrib_id, qid, oid)?;
                                    }
                                }
                            }
                        }
                    }
                    "multi_choice" => {
                        let mut oids = Vec::<i64>::new();
                        // 1) options booléennes
                        for opt in &qm.options {
                            if let Some(col) = &opt.source_column {
                                if let Some(ix) = headers.iter().position(|h| h == col) {
                                    if let Some(v) = rec.get(ix) {
                                        let s = v.trim().to_lowercase();
                                        let truthy = matches!(s.as_str(), "1" | "true" | "vrai" | "yes" | "oui" | "y" | "x" | "checked") ||
                                            s.parse::<i64>().map(|n| n>0).unwrap_or(false);
                                        if truthy {
                                            let oid = if let Some(oid) = caches.opt_by_qid_label.get(&(qid, opt.label.clone())) {
                                                *oid
                                            } else {
                                                ensure_option(&tx, qid, &opt.code, &opt.label, opt.position)?
                                            };
                                            oids.push(oid);
                                        }
                                    }
                                }
                            }
                        }
                        // 2) colonne unique avec délimiteur
                        if qm.options_from_values {
                            if let Some(col) = &qm.source_column {
                                if let Some(ix) = headers.iter().position(|h| h == col) {
                                    if let Some(v) = rec.get(ix) {
                                        let delim = qm.delimiter.as_deref().unwrap_or(";");
                                        for p in v.split(delim).map(|s| s.trim()).filter(|s| !s.is_empty()) {
                                            let oid = ensure_dynamic_option(&tx, &mut caches, qid, p)?;
                                            oids.push(oid);
                                        }
                                    }
                                }
                            }
                        }
                        ensure_multi_choice(&tx, contrib_id, qid, &oids)?;
                    }
                    _ => {}
                }
            }

            pending += 1;
            total += 1;

            if pending % commit_every == 0 {
                tx.commit()?;
                println!("  … {total} lignes (commit)");
                // nouvelle transaction
                tx = conn.unchecked_transaction()?;
                pending = 0;
            } else if pending % log_every == 0 {
                println!("  … {total}"); // log sans commit
            }
        }

        // flush fin de fichier
        tx.commit()?;
        println!("  ✓ terminé pour {path} (total {total})");
    }

    if defer_fts {
        println!("[fts] rebuild + recréation des triggers");
        conn.execute("INSERT INTO answers_fts(answers_fts) VALUES('rebuild')", [])?;
        conn.execute_batch(r#"
            CREATE TRIGGER IF NOT EXISTS answers_ai AFTER INSERT ON answers BEGIN
              INSERT INTO answers_fts(rowid, text) VALUES (new.id, new.text);
            END;
            CREATE TRIGGER IF NOT EXISTS answers_ad AFTER DELETE ON answers BEGIN
              INSERT INTO answers_fts(answers_fts, rowid, text) VALUES ('delete', old.id, old.text);
            END;
            CREATE TRIGGER IF NOT EXISTS answers_au AFTER UPDATE ON answers BEGIN
              INSERT INTO answers_fts(answers_fts, rowid, text) VALUES ('delete', old.id, old.text);
              INSERT INTO answers_fts(rowid, text) VALUES (new.id, new.text);
            END;
        "#)?;
    }

    println!("[ingest] OK — {total} lignes en {:?}.", t0.elapsed());
    Ok(())
}
