#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ingestion Grand Débat → SQLite (modèle normalisé) — version optimisée
- Caches questions/options (réduit les SELECT)
- PRAGMA SQLite (WAL, cache) sur la connexion
- Option --defer-fts : désactive les triggers FTS pendant l'ingestion,
  puis reconstruit l'index et recrée les triggers (gros boost de perfs)
- Fusion des doublons (même contribution/question) au lieu de violer l'unicité
- Commit par batch (par défaut 10000)

Usage :
  python gdn_ingest.py ingest \
    --db sqlite:///sandbox.db \
    --csv data/organisation-de-letat-et-des-services-publics.csv \
    --mapping ingest/mappings/organisation_etat_services.yml \
    --batch org_etat_services_$(date +%F) \
    --commit-every 10000 \
    --defer-fts

  python gdn_ingest.py rebuild-fts --db sqlite:///sandbox.db
"""
from __future__ import annotations
import argparse, csv, glob, gzip, hashlib, io, json, os, re, sys, zipfile
from collections import defaultdict
from typing import Dict, Any, Iterable, Optional, List
from contextlib import contextmanager

# Augmente la taille max d'un champ CSV (défaut 128 Ko)
try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)

try:
    import yaml
except ImportError:
    print("pyyaml est requis : pip install pyyaml", file=sys.stderr); sys.exit(1)

try:
    from slugify import slugify as _slugify
    def slugify(x: str) -> str:
        return _slugify(x or "", lowercase=True, separator="-")
except Exception:
    def slugify(x: str) -> str:
        s = (x or "").strip().lower()
        s = re.sub(r"\s+", "-", s)
        s = re.sub(r"[^a-z0-9\-_\/]+", "", s)
        return s

from sqlalchemy import create_engine, event, select, text as sql_text
from sqlalchemy.orm import Session

# Import des modèles depuis l'app (assume que ce script est lancé à la racine du repo)
sys.path.append(os.getcwd())
from app.models import (
    Author, Contribution, Answer, Form, Question, Option,
    AnswerOption, Topic, TopicAlias, ContributionTopic
)

# -------------------- Connexion & PRAGMA --------------------

def make_engine(url: str, apply_pragmas: bool = True):
    engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
    if apply_pragmas:
        @event.listens_for(engine, "connect")
        def set_sqlite_pragmas(dbapi_connection, connection_record):
            cur = dbapi_connection.cursor()
            try:
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA synchronous=NORMAL")
                cur.execute("PRAGMA temp_store=MEMORY")
                cur.execute("PRAGMA cache_size=-200000")  # ~200 Mo
                # cur.execute("PRAGMA mmap_size=268435456")  # 256 Mo si supporté
            finally:
                cur.close()
    return engine

# -------------------- IO CSV --------------------

def open_any(path: str) -> Iterable[Dict[str, str]]:
    """Ouvre CSV (plain/gz/zip) et yield des dict-rows UTF-8."""
    def _reader(fileobj):
        buf = io.TextIOWrapper(fileobj, encoding="utf-8-sig", newline="")
        dr = csv.DictReader(buf)
        for row in dr:
            yield { (k or "").strip(): (v or "").strip() for k, v in row.items() }

    if path.endswith(".gz"):
        with gzip.open(path, "rb") as f:
            for row in _reader(f): yield row
    elif path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith(".csv"):
                    with z.open(name) as f:
                        for row in _reader(f): yield row
                    break
    else:
        with open(path, "rb") as f:
            for row in _reader(f): yield row

# -------------------- Utils --------------------

def sha256_of_row(row: Dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

def truthy(val: str | None) -> bool:
    if val is None: return False
    s = val.strip().lower()
    return s in {"1","true","vrai","yes","oui","y","x","checked"} or (s.isdigit() and int(s)>0)

@contextmanager
def session_scope(engine):
    s = Session(engine)
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()

# -------------------- FTS Triggers helpers --------------------

FTS_TRIGGERS = {
    "ai": """
        CREATE TRIGGER IF NOT EXISTS answers_ai AFTER INSERT ON answers BEGIN
          INSERT INTO answers_fts(rowid, text) VALUES (new.id, new.text);
        END;
    """,
    "ad": """
        CREATE TRIGGER IF NOT EXISTS answers_ad AFTER DELETE ON answers BEGIN
          INSERT INTO answers_fts(answers_fts, rowid, text) VALUES ('delete', old.id, old.text);
        END;
    """,
    "au": """
        CREATE TRIGGER IF NOT EXISTS answers_au AFTER UPDATE ON answers BEGIN
          INSERT INTO answers_fts(answers_fts, rowid, text) VALUES ('delete', old.id, old.text);
          INSERT INTO answers_fts(rowid, text) VALUES (new.id, new.text);
        END;
    """,
}

DEF_DROP_TRIGGERS = [
    "DROP TRIGGER IF EXISTS answers_au;",
    "DROP TRIGGER IF EXISTS answers_ad;",
    "DROP TRIGGER IF EXISTS answers_ai;",
]

def drop_fts_triggers(s: Session):
    for stmt in DEF_DROP_TRIGGERS:
        s.execute(sql_text(stmt))

def create_fts_triggers(s: Session):
    for k, ddl in FTS_TRIGGERS.items():
        s.execute(sql_text(ddl))

def rebuild_fts(s: Session):
    s.execute(sql_text("INSERT INTO answers_fts(answers_fts) VALUES('rebuild');"))

# -------------------- Mapping helpers --------------------

def get_or_create_form(s: Session, form_info: Dict[str, Any]) -> Form:
    q = s.execute(select(Form).where(
        Form.name==form_info.get("name"),
        Form.version==form_info.get("version"),
        Form.source==form_info.get("source"),
    )).scalars().first()
    if q: return q
    f = Form(name=form_info.get("name","Grand Débat"),
             version=form_info.get("version"),
             source=form_info.get("source"))
    s.add(f); s.flush()
    return f

# caches globaux sur une ingestion
class Caches:
    def __init__(self):
        self.q_by_code: dict[str, Question] = {}
        self.static_opt_by_label: dict[int, dict[str, Option]] = defaultdict(dict)
        self.dynamic_opt_seen: dict[int, set[str]] = defaultdict(set)

# Précharger questions + options statiques
def preload_questions_and_options(s: Session, form: Form, mapping: Dict[str, Any]) -> Caches:
    caches = Caches()
    for qm in mapping.get("questions", []):
        code = qm["code"]
        q = s.execute(select(Question).where(Question.form_id==form.id, Question.question_code==code)).scalars().first()
        if not q:
            q = Question(
                form_id=form.id,
                question_code=code,
                prompt=qm.get("prompt") or code,
                section=qm.get("section"),
                position=qm.get("position"),
                type=qm["type"],
                options_json=json.dumps(qm.get("meta") or {}, ensure_ascii=False)
            )
            s.add(q); s.flush()
        caches.q_by_code[code] = q
        # options statiques
        for opt in (qm.get("options") or []):
            o = s.execute(select(Option).where(Option.question_id==q.id, Option.code==opt["code"]))\
                .scalars().first()
            if not o:
                o = Option(question_id=q.id, code=opt["code"], label=opt["label"],
                           position=opt.get("position"), meta_json=json.dumps(opt.get("meta") or {}, ensure_ascii=False))
                s.add(o); s.flush()
            caches.static_opt_by_label[q.id][o.label] = o
    return caches

# auteur / contribution
def get_or_create_author(s: Session, amap: Dict[str, Any], row: Dict[str, str]) -> Optional[Author]:
    if not amap: return None
    email_hash_col = amap.get("email_hash")
    email_hash = row.get(email_hash_col) if email_hash_col else None
    source_author_id_col = amap.get("source_author_id")
    source_author_id = row.get(source_author_id_col) if source_author_id_col else None
    q = None
    if email_hash:
        q = s.execute(select(Author).where(Author.email_hash==email_hash)).scalars().first()
    elif source_author_id:
        q = s.execute(select(Author).where(Author.source_author_id==source_author_id)).scalars().first()
    if q: return q
    a = Author(
        source_author_id=source_author_id,
        name=row.get(amap.get("name")) if amap.get("name") else None,
        email_hash=email_hash,
        zipcode=row.get(amap.get("zipcode")) if amap.get("zipcode") else None,
        city=row.get(amap.get("city")) if amap.get("city") else None,
        age_range=row.get(amap.get("age_range")) if amap.get("age_range") else None,
        gender=row.get(amap.get("gender")) if amap.get("gender") else None,
    )
    s.add(a); s.flush()
    return a

def get_or_create_contribution(s: Session, cmap: Dict[str, Any], row: Dict[str,str], form: Form, author: Optional[Author], import_batch_id: str) -> Contribution:
    raw_hash = sha256_of_row(row)
    ex = s.execute(select(Contribution).where(Contribution.raw_hash==raw_hash)).scalars().first()
    if ex: return ex
    c = Contribution(
        source_contribution_id=row.get(cmap.get("source_contribution_id")) if cmap.get("source_contribution_id") else None,
        author_id=author.id if author else None,
        form_id=form.id,
        source=cmap.get("source") or None,
        theme_id=None,
        submitted_at=row.get(cmap.get("submitted_at")) if cmap.get("submitted_at") else None,
        title=row.get(cmap.get("title")) if cmap.get("title") else None,
        import_batch_id=import_batch_id,
        raw_hash=raw_hash,
        raw_json=json.dumps(row, ensure_ascii=False),
    )
    s.add(c); s.flush()
    return c

# -------------------- Ensure helpers (anti-doublon) --------------------

def find_answer(s: Session, contribution_id: int, question_id: int):
    return s.execute(select(Answer).where(Answer.contribution_id==contribution_id, Answer.question_id==question_id)).scalars().first()

def ensure_text_answer(s: Session, contribution_id: int, question_id: int, text_value: str, joiner: str = "\n\n"):
    if not text_value:
        return
    ex = find_answer(s, contribution_id, question_id)
    if ex:
        if ex.text:
            if text_value not in ex.text:
                ex.text = f"{ex.text}{joiner}{text_value}"
        else:
            ex.text = text_value
        return
    s.add(Answer(contribution_id=contribution_id, question_id=question_id, position=1, text=text_value))

def ensure_single_choice(s: Session, contribution_id: int, q: Question, option: Option):
    ex = find_answer(s, contribution_id, q.id)
    if not ex:
        ex = Answer(contribution_id=contribution_id, question_id=q.id, position=1)
        s.add(ex); s.flush()
    existing = s.execute(select(AnswerOption).where(AnswerOption.answer_id==ex.id)).scalars().all()
    if existing:
        if not any(ao.option_id == option.id for ao in existing):
            for ao in existing:
                s.delete(ao)
            s.flush()
            s.add(AnswerOption(answer_id=ex.id, option_id=option.id))
    else:
        s.add(AnswerOption(answer_id=ex.id, option_id=option.id))

def ensure_multi_choice(s: Session, contribution_id: int, q: Question, options: list[Option]):
    if not options:
        return
    ex = find_answer(s, contribution_id, q.id)
    if not ex:
        ex = Answer(contribution_id=contribution_id, question_id=q.id, position=1)
        s.add(ex); s.flush()
    existing_ids = {ao.option_id for ao in s.execute(select(AnswerOption).where(AnswerOption.answer_id==ex.id)).scalars().all()}
    for o in options:
        if o and o.id not in existing_ids:
            s.add(AnswerOption(answer_id=ex.id, option_id=o.id))

# dynamic options cache
def get_or_create_dynamic_option_cached(s: Session, caches: Caches, q: Question, raw_value: str) -> Optional[Option]:
    lab = (raw_value or "").strip()
    if not lab:
        return None
    if lab in caches.dynamic_opt_seen[q.id]:
        return s.execute(select(Option).where(Option.question_id==q.id, Option.label==lab)).scalars().first()
    code = slugify(lab)[:64] or "na"
    o = s.execute(select(Option).where(Option.question_id==q.id, Option.code==code)).scalars().first()
    if not o:
        o = Option(question_id=q.id, code=code, label=lab)
        s.add(o); s.flush()
    caches.dynamic_opt_seen[q.id].add(lab)
    return o

# -------------------- Ingestion d'une ligne --------------------

def ingest_answers_for_row(s: Session, row: Dict[str,str], form: Form, mapping: Dict[str,Any], contribution: Contribution, *, caches: Caches):
    with s.no_autoflush:
        for qm in mapping.get("questions", []):
            q = caches.q_by_code[qm["code"]]
            qtype = qm["type"]

            if qtype == "free_text":
                src = (qm.get("source") or {})
                cols = src.get("columns") or []
                joiner = src.get("joiner") or "\n\n"
                parts = [row.get(col, "").strip() for col in cols if row.get(col)]
                text_value = joiner.join([p for p in parts if p])
                ensure_text_answer(s, contribution.id, q.id, text_value, joiner=joiner)

            elif qtype == "text":
                col = qm.get("source_column")
                val = row.get(col, "").strip() if col else ""
                ensure_text_answer(s, contribution.id, q.id, val)

            elif qtype in {"number", "scale", "date"}:
                col = qm.get("source_column")
                val = row.get(col, "").strip() if col else ""
                if val:
                    ex = find_answer(s, contribution.id, q.id)
                    vjson = json.dumps({"value": val}, ensure_ascii=False)
                    if ex:
                        ex.value_json = vjson
                    else:
                        s.add(Answer(contribution_id=contribution.id, question_id=q.id, position=1, value_json=vjson))

            elif qtype == "single_choice":
                col = qm.get("source_column")
                raw = row.get(col, "").strip() if col else ""
                if not raw:
                    continue
                if qm.get("options_from_values"):
                    o = get_or_create_dynamic_option_cached(s, caches, q, raw)
                else:
                    o = caches.static_opt_by_label.get(q.id, {}).get(raw)
                    if not o:
                        o = get_or_create_dynamic_option_cached(s, caches, q, raw)
                if o:
                    ensure_single_choice(s, contribution.id, q, o)

            elif qtype == "multi_choice":
                selected: list[Option] = []
                # booléens par option
                for opt in (qm.get("options") or []):
                    col = opt.get("source_column")
                    if col and truthy(row.get(col)):
                        o = caches.static_opt_by_label.get(q.id, {}).get(opt["label"])
                        if not o:
                            o = s.execute(select(Option).where(Option.question_id==q.id, Option.code==opt["code"]))\
                                  .scalars().first()
                            if not o:
                                o = Option(question_id=q.id, code=opt["code"], label=opt["label"], position=opt.get("position"))
                                s.add(o); s.flush()
                            caches.static_opt_by_label[q.id][o.label] = o
                        selected.append(o)
                # colonne séparée avec délimiteur
                if qm.get("options_from_values"):
                    delim = qm.get("delimiter", ";")
                    col = qm.get("source_column")
                    raw = row.get(col, "").strip() if col else ""
                    if raw:
                        parts = [p.strip() for p in raw.split(delim) if p.strip()]
                        for p in parts:
                            o = get_or_create_dynamic_option_cached(s, caches, q, p)
                            if o: selected.append(o)
                ensure_multi_choice(s, contribution.id, q, selected)
            else:
                pass

# -------------------- Commandes --------------------

def cmd_ingest(args):
    engine = make_engine(args.db, apply_pragmas=not args.no_pragmas)

    with session_scope(engine) as s:
        with open(args.mapping, "r", encoding="utf-8") as f:
            mapping = yaml.safe_load(f)
        form = get_or_create_form(s, mapping.get("form") or {})
        caches = preload_questions_and_options(s, form, mapping)
        print(f"[ingest] Form id={form.id} name={form.name!r} version={form.version!r}")

        if args.defer_fts:
            print("[fts] désactivation des triggers FTS…")
            drop_fts_triggers(s)

    files: List[str] = []
    for pat in args.csv:
        files.extend(glob.glob(pat))

    total = 0
    processed = 0

    for path in files:
        print(f"[ingest] Fichier: {path}")
        with session_scope(engine) as s:
            with open(args.mapping, "r", encoding="utf-8") as f:
                mapping = yaml.safe_load(f)
            form = get_or_create_form(s, mapping.get("form") or {})
            amap = (mapping.get("defaults") or {}).get("author") or {}
            cmap = (mapping.get("defaults") or {}).get("contribution") or {}
            caches = preload_questions_and_options(s, form, mapping)

            for i, row in enumerate(open_any(path), start=1):
                author = get_or_create_author(s, amap, row)
                contrib = get_or_create_contribution(s, cmap, row, form, author, args.batch)
                ingest_answers_for_row(s, row, form, mapping, contrib, caches=caches)

                if i % args.commit_every == 0:
                    s.commit()
                    processed += args.commit_every
                    print(f"  … {processed} lignes (commit)", flush=True)
            total += i

    if args.defer_fts:
        print("[fts] reconstruction de answers_fts + recréation des triggers…")
        with session_scope(engine) as s:
            rebuild_fts(s)
            create_fts_triggers(s)

    print(f"[ingest] Terminé. Lignes traitées ~ {total}")

def cmd_rebuild_fts(args):
    engine = make_engine(args.db)
    with session_scope(engine) as s:
        rebuild_fts(s)
    print("[fts] answers_fts rebuild OK")


def main():
    p = argparse.ArgumentParser(description="Ingestion Grand Débat (SQLite) — optimisée")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest", help="ingérer des CSV")
    p_ing.add_argument("--db", required=True, help="sqlite:///gdn.db")
    p_ing.add_argument("--csv", nargs="+", required=True, help="chemin(s) ou globs")
    p_ing.add_argument("--mapping", required=True, help="YAML de mapping")
    p_ing.add_argument("--batch", default="import_"+os.environ.get("USER","user"), help="import_batch_id")
    p_ing.add_argument("--commit-every", type=int, default=10000, help="commit périodique")
    p_ing.add_argument("--defer-fts", action="store_true", help="désactive les triggers FTS pendant l'ingestion puis rebuild à la fin")
    p_ing.add_argument("--no-pragmas", action="store_true", help="ne pas appliquer les PRAGMA SQLite (débug)")
    p_ing.set_defaults(func=cmd_ingest)

    p_fts = sub.add_parser("rebuild-fts", help="reconstruire l'index FTS")
    p_fts.add_argument("--db", required=True)
    p_fts.set_defaults(func=cmd_rebuild_fts)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()