use anyhow::{Context, Result};
use clap::{Parser, Subcommand};
use csv::StringRecord;
use flate2::read::GzDecoder;
use glob::glob;
use postgres::{Client, NoTls, Row};
use regex::Regex;
use serde::Deserialize;
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{
    borrow::Cow,
    collections::{HashMap, HashSet},
    env,
    fs::File,
    io::{BufRead, BufReader, Read},
    path::PathBuf,
    time::Instant,
};
use zip::read::ZipArchive;
use std::io::Cursor;
use once_cell::sync::Lazy;

#[derive(Parser)]
#[command(name = "gdn_ingest", version, about = "Ingestion Grand Débat (Rust + PostgreSQL)")]
struct Cli {
    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand)]
enum Cmd {
    /// Ingérer des CSV selon un mapping YAML
    Ingest {
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
        #[arg(long, default_value = ",")]
        delimiter: char,
        /// Mode validation uniquement (pas d'écriture DB)
        #[arg(long, default_value_t = false)]
        dry_run: bool,
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
    position: Option<i32>,
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
    position: Option<i32>,
    #[serde(default)]
    meta: Option<serde_json::Value>,
    #[serde(default)]
    source_column: Option<String>,
}

fn main() -> Result<()> {
    dotenv::dotenv().ok(); // Charger .env si disponible
    
    let cli = Cli::parse();
    match cli.cmd {
        Cmd::Ingest { csv, mapping, batch, commit_every, log_every, delimiter, dry_run } => {
           run_ingest(csv, mapping, batch, commit_every, log_every, delimiter, dry_run)
        }
    }
}

fn get_database_url() -> Result<String> {
    env::var("DATABASE_URL")
        .with_context(|| "DATABASE_URL manquante dans .env")
        .and_then(|url| {
            if url.starts_with("postgresql") || url.starts_with("postgres") {
                // Convertir URL SQLAlchemy vers postgres crate
                let clean_url = url
                    .replace("postgresql+psycopg2://", "postgres://")
                    .replace("postgresql://", "postgres://");
                Ok(clean_url)
            } else {
                anyhow::bail!("DATABASE_URL doit commencer par 'postgresql' ou 'postgres', trouvé: {}", url)
            }
        })
}

fn open_conn() -> Result<Client> {
    let db_url = get_database_url()?;
    println!("[db] Connexion à PostgreSQL via .env");
    let client = Client::connect(&db_url, NoTls)?;
    Ok(client)
}

fn sniff_delimiter<R: Read>(mut r: R) -> std::io::Result<(Vec<u8>, u8)> {
    use std::io::Read;
    let mut buf = vec![0u8; 8192];
    let n = r.read(&mut buf)?;
    buf.truncate(n);
    let sample = std::str::from_utf8(&buf).unwrap_or("");
    let count = |c: char| sample.matches(c).count();
    let mut best = (count(','), b',');
    for (c, b) in [( ';', b';'), ('\t', b'\t')] {
        let k = count(c);
        if k > best.0 { best = (k, b); }
    }
    Ok((buf, best.1))
}

// ---------- Validation préventive ----------

fn validate_mapping(mapping: &Mapping) -> Result<()> {
    println!("[validation] Vérification de la configuration YAML...");
    
    let mut errors = Vec::new();
    let mut warnings = Vec::new();
    
    for (i, qm) in mapping.questions.iter().enumerate() {
        let qpos = format!("question[{}] '{}' ({})", i, qm.code, qm.qtype);
        
        // ⚠️ VALIDATION CRITIQUE: single_choice avec options_from_values
        if qm.qtype == "single_choice" {
            if qm.options_from_values {
                if qm.options.is_empty() {
                    errors.push(format!(
                        "{}: single_choice + options_from_values=true SANS options prédéfinies!",
                        qpos
                    ));
                    errors.push(format!(
                        "  → RISQUE: Chaque réponse unique créera une option séparée"
                    ));
                    errors.push(format!(
                        "  → SOLUTION: Ajouter des options prédéfinies OU utiliser options_from_values=false"
                    ));
                } else {
                    warnings.push(format!(
                        "{}: single_choice + options_from_values=true avec {} options définies",
                        qpos, qm.options.len()
                    ));
                }
            }
            
            if qm.source_column.is_none() {
                errors.push(format!("{}: single_choice nécessite source_column", qpos));
            }
        }
        
        // Validation multi_choice
        if qm.qtype == "multi_choice" {
            if !qm.options_from_values && qm.options.is_empty() {
                errors.push(format!("{}: multi_choice sans options ni options_from_values", qpos));
            }
        }
        
        // Validation free_text
        if qm.qtype == "free_text" {
            if qm.source.is_none() {
                errors.push(format!("{}: free_text nécessite 'source.columns'", qpos));
            }
        }
        
        // Validation colonnes source standard
        if matches!(qm.qtype.as_str(), "text" | "number" | "scale" | "date") {
            if qm.source_column.is_none() {
                errors.push(format!("{}: {} nécessite source_column", qpos, qm.qtype));
            }
        }
    }
    
    // Affichage résultats
    if !warnings.is_empty() {
        println!("[validation] ⚠️  {} avertissements:", warnings.len());
        for w in warnings {
            println!("  {}", w);
        }
    }
    
    if !errors.is_empty() {
        println!("[validation] ❌ {} erreurs critiques:", errors.len());
        for e in errors {
            println!("  {}", e);
        }
        anyhow::bail!("Configuration YAML invalide - corrigez les erreurs ci-dessus");
    }
    
    println!("[validation] ✅ Configuration validée");
    Ok(())
}

// ---------- Helpers SQL (PostgreSQL) ----------

struct Caches {
    qid_by_code: HashMap<String, i64>,
    opt_by_qid_label: HashMap<(i64, String), i64>,
    dyn_seen: HashSet<(i64, String)>,
}

fn preload_form(conn: &mut Client, f: &FormInfo) -> Result<i64> {
    let rows = conn.query(
        "SELECT id FROM forms WHERE name=$1 AND COALESCE(version,'')=COALESCE($2,'') AND COALESCE(source,'')=COALESCE($3,'')",
        &[&f.name, &f.version, &f.source],
    )?;
    
    if let Some(row) = rows.first() {
        return Ok(row.get(0));
    }
    
    let row = conn.query_one(
        "INSERT INTO forms(name,version,source) VALUES($1,$2,$3) RETURNING id",
        &[&f.name, &f.version, &f.source],
    )?;
    
    Ok(row.get(0))
}

fn preload_questions_and_options(conn: &mut Client, form_id: i64, mapping: &Mapping) -> Result<Caches> {
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

fn ensure_question(conn: &mut Client, form_id: i64, qm: &QuestionMap) -> Result<i64> {
    let rows = conn.query(
        "SELECT id FROM questions WHERE form_id=$1 AND question_code=$2",
        &[&form_id, &qm.code],
    )?;
    
    if let Some(row) = rows.first() {
        return Ok(row.get(0));
    }
    
    let meta_json = qm.meta.as_ref().map(|v| v.to_string());
    let row = conn.query_one(
        "INSERT INTO questions(form_id,question_code,prompt,section,position,type,options_json)
         VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",
        &[&form_id, &qm.code, &qm.prompt, &qm.section, &qm.position, &qm.qtype, &meta_json],
    )?;
    
    Ok(row.get(0))
}

// ---------- Slugify optimisé ----------
static SLUG_RE: Lazy<Regex> = Lazy::new(|| Regex::new(r"[^a-z0-9]+").unwrap());
fn slugify(s: &str) -> String {
    let lower = s.to_lowercase();
    let collapsed = SLUG_RE.replace_all(&lower, "-");
    collapsed.trim_matches('-').to_string()
}

fn ensure_dynamic_option_with_limits(
    tx: &mut postgres::Transaction, 
    caches: &mut Caches, 
    qid: i64, 
    label: &str,
    question_code: &str
) -> Result<i64> {
    if caches.dyn_seen.contains(&(qid, label.to_string())) {
        if let Some(&oid) = caches.opt_by_qid_label.get(&(qid, label.to_string())) {
            return Ok(oid);
        }
    }
    
    // 🛡️ LIMITE DE SÉCURITÉ: Vérifier le nombre d'options existantes
    let count_row = tx.query_one(
        "SELECT COUNT(*) FROM options WHERE question_id = $1", 
        &[&qid]
    )?;
    let option_count: i64 = count_row.get(0);
    
    const MAX_DYNAMIC_OPTIONS: i64 = 500; // Limite raisonnable
    
    if option_count >= MAX_DYNAMIC_OPTIONS {
        anyhow::bail!(
            "🚨 LIMITE ATTEINTE: Question '{}' a déjà {} options (limite: {})\n\
             → Probable erreur de configuration: single_choice + options_from_values\n\
             → Chaque réponse unique crée une option séparée\n\
             → SOLUTION: Définir des options prédéfinies dans le YAML",
            question_code, option_count, MAX_DYNAMIC_OPTIONS
        );
    }
    
    if option_count > 50 {
        println!(
            "⚠️  ATTENTION: Question '{}' a {} options dynamiques (réponses uniques)",
            question_code, option_count
        );
    }
    
    let code = {
        let mut c = slugify(label);
        if c.is_empty() { c = "na".into(); }
        if c.len() > 64 { c.truncate(64); }
        c
    };
    
    let oid = ensure_option_tx(tx, qid, &code, label, None)?;
    caches.opt_by_qid_label.insert((qid, label.to_string()), oid);
    caches.dyn_seen.insert((qid, label.to_string()));
    Ok(oid)
}

// ---------- Autres fonctions (adaptées pour PostgreSQL) ----------

fn ensure_option(conn: &mut Client, question_id: i64, code: &str, label: &str, position: Option<i32>) -> Result<i64> {
    let row = conn.query_one(
        "INSERT INTO options(question_id, code, label, position)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT(question_id, code) DO UPDATE SET
             label = EXCLUDED.label,
             position = COALESCE(EXCLUDED.position, options.position)
         RETURNING id",
        &[&question_id, &code, &label, &position],
    )?;
    
    Ok(row.get(0))
}

fn ensure_option_tx(tx: &mut postgres::Transaction, question_id: i64, code: &str, label: &str, position: Option<i32>) -> Result<i64> {
    let row = tx.query_one(
        "INSERT INTO options(question_id, code, label, position)
         VALUES ($1, $2, $3, $4)
         ON CONFLICT(question_id, code) DO UPDATE SET
             label = EXCLUDED.label,
             position = COALESCE(EXCLUDED.position, options.position)
         RETURNING id",
        &[&question_id, &code, &label, &position],
    )?;
    
    Ok(row.get(0))
}

fn sha256_rowjson(rec: &serde_json::Value) -> String {
    let mut hasher = Sha256::new();
    hasher.update(rec.to_string().as_bytes());
    hex::encode(hasher.finalize())
}

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
                return Ok(Box::new(Cursor::new(buf)));
            }
        }
        anyhow::bail!("zip sans CSV");
    } else {
        let f = File::open(path)?;
        Ok(Box::new(BufReader::new(f)))
    }
}

// ---------- run_ingest (version PostgreSQL) ----------

fn run_ingest(
    csv_globs: Vec<String>,
    mapping_path: PathBuf,
    batch: String,
    commit_every: usize,
    log_every: usize,
    delimiter: char,
    dry_run: bool,
) -> Result<()> {
    // mapping
    let mapping_str = std::fs::read_to_string(&mapping_path)
        .with_context(|| format!("lecture mapping {:?}", mapping_path))?;
    let mapping: Mapping = serde_yaml::from_str(&mapping_str)?;

    // 🔍 VALIDATION CRITIQUE
    validate_mapping(&mapping)?;

    if dry_run {
        println!("[dry-run] Mode validation uniquement - aucune écriture DB");
        return Ok(());
    }

    // connex + form + caches
    let mut conn = open_conn()?;
    let form_id = preload_form(&mut conn, &mapping.form)?;
    let mut caches = preload_questions_and_options(&mut conn, form_id, &mapping)?;
    
    println!(
        "[ingest] form id={} name='{}' version='{}'", 
        form_id, 
        mapping.form.name, 
        mapping.form.version.as_deref().unwrap_or("")
    );

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
        let mut reader = open_any(&path)?;
        let (primed, delim_auto) = sniff_delimiter(&mut reader)?;
        let delim = if delimiter == ',' || delimiter == ';' || delimiter == '\t' {
            delimiter as u8
        } else {
            delim_auto
        };
        let cursor = std::io::Cursor::new(primed);
        let chained = cursor.chain(reader);
        let mut rdr = csv::ReaderBuilder::new()
            .delimiter(delim)
            .has_headers(true)
            .flexible(true)
            .from_reader(chained);

        let headers = rdr.headers()?.clone();

        // transactions par batch
        let mut pending = 0usize;
        let mut tx = conn.transaction()?;

        for rec in rdr.records() {
            let rec = rec?;
            
            // skip trashed (logique inchangée)
            let mut is_trashed = false;
            if let Some(ix) = headers.iter().position(|h| h == "trashed") {
                if let Some(v) = rec.get(ix) {
                    let s = v.trim().to_lowercase();
                    is_trashed = matches!(s.as_str(), "1" | "true" | "yes" | "vrai");
                }
            }
            if !is_trashed {
                if let Some(ix) = headers.iter().position(|h| h == "trashedStatus") {
                    if let Some(v) = rec.get(ix) {
                        let s = v.trim().to_lowercase();
                        if !s.is_empty() && s != "kept" { is_trashed = true; }
                    }
                }
            }
            if is_trashed {
                continue;
            }

            // raw_json pour audit + hash
            let mut rowmap = serde_json::Map::new();
            for (i, h) in headers.iter().enumerate() {
                if let Some(v) = rec.get(i) {
                    rowmap.insert(h.to_string(), serde_json::Value::String(v.to_string()));
                }
            }
            let raw_json = serde_json::Value::Object(rowmap);
            let row_hash = sha256_rowjson(&raw_json);

            // Créer ou récupérer la contribution
            let reference = rec.get(headers.iter().position(|h| h == "reference").unwrap_or(0))
                .map(|s| s.trim().to_string())
                .unwrap_or_else(|| format!("import_{}", total));
            
            // Insérer la contribution (simple, sans auteur pour l'instant)
            let contrib_id: i64 = tx.query_one(
                "INSERT INTO contributions (form_id, source_contribution_id, raw_json) 
                 VALUES ($1, $2, $3)
                 ON CONFLICT (source_contribution_id) DO UPDATE SET raw_json = EXCLUDED.raw_json
                 RETURNING id",
                &[&form_id, &reference, &raw_json.to_string()]
            )?.get(0);
            
            // questions - LOGIQUE CORRIGÉE
            for qm in &mapping.questions {
                let qid = *caches.qid_by_code.get(&qm.code).expect("qid");
                match qm.qtype.as_str() {
                    "single_choice" => {
                        if let Some(col) = &qm.source_column {
                            if let Some(ix) = headers.iter().position(|h| h == col) {
                                if let Some(v) = rec.get(ix) { 
                                    let raw = v.trim();
                                    if !raw.is_empty() {
                                        let oid = if qm.options_from_values {
                                            // 🛡️ VERSION SÉCURISÉE avec limites
                                            ensure_dynamic_option_with_limits(&mut tx, &mut caches, qid, raw, &qm.code)?
                                        } else {
                                            if let Some(oid) = caches.opt_by_qid_label.get(&(qid, raw.to_string())) {
                                                *oid
                                            } else {
                                                // ⚠️ FALLBACK SÉCURISÉ: Créer l'option manquante mais avec avertissement
                                                println!(
                                                    "⚠️  Question '{}': Réponse '{}' non trouvée dans options prédéfinies, création dynamique",
                                                    qm.code, raw
                                                );
                                                ensure_dynamic_option_with_limits(&mut tx, &mut caches, qid, raw, &qm.code)?
                                            }
                                        };
                                        // Créer l'answer avec l'option sélectionnée
                                        let answer_id: i64 = tx.query_one(
                                            "INSERT INTO answers (contribution_id, question_id, position) 
                                             VALUES ($1, $2, $3)
                                             ON CONFLICT (contribution_id, question_id, position) 
                                             DO UPDATE SET contribution_id = EXCLUDED.contribution_id
                                             RETURNING id",
                                            &[&contrib_id, &qid, &1i32]
                                        )?.get(0);
                                        
                                        // Créer la liaison answer_option
                                        tx.execute(
                                            "INSERT INTO answer_options (answer_id, option_id) 
                                             VALUES ($1, $2)
                                             ON CONFLICT (answer_id, option_id) DO NOTHING",
                                            &[&answer_id, &oid]
                                        )?;
                                    }
                                }
                            }
                        }
                    }
                    "text" | "number" | "scale" | "date" => {
                        if let Some(col) = &qm.source_column {
                            if let Some(ix) = headers.iter().position(|h| h == col) {
                                if let Some(v) = rec.get(ix) { 
                                    let raw = v.trim();
                                    if !raw.is_empty() {
                                        // Créer la réponse texte directement
                                        tx.execute(
                                            "INSERT INTO answers (contribution_id, question_id, position, \"text\") 
                                             VALUES ($1, $2, $3, $4)
                                             ON CONFLICT (contribution_id, question_id, position) 
                                             DO UPDATE SET \"text\" = EXCLUDED.\"text\"",
                                            &[&contrib_id, &qid, &1i32, &raw]
                                        )?;
                                    }
                                }
                            }
                        }
                    }
                    // ... autres types de questions
                    _ => {
                        // Types de questions non encore implémentés
                    }
                }
            }

            pending += 1;
            total += 1;

            if pending % commit_every == 0 {
                tx.commit()?;
                println!("  … {total} lignes (commit)");
                tx = conn.transaction()?;
                pending = 0;
            } else if pending % log_every == 0 {
                println!("  … {total}");
            }
        }

        tx.commit()?;
        println!("  ✓ terminé pour {path} (total {total})");
    }

    println!("[ingest] OK — {total} lignes en {:?}.", t0.elapsed());
    Ok(())
}