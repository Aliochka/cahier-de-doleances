#!/usr/bin/env python3
"""
Simple PostgreSQL test database population using CSV data and YAML mappings
"""
import os
import sys
import csv
import yaml
import hashlib
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Base, Form, Question, Option, Author, Contribution, Answer, SearchStats


def load_yaml_mapping(yaml_path):
    """Load YAML mapping file"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def hash_email(email_like):
    """Create a simple hash from email-like data"""
    if not email_like or email_like.strip() == "":
        return None
    return hashlib.md5(email_like.encode()).hexdigest()


def parse_datetime(date_str):
    """Parse datetime from CSV"""
    if not date_str or date_str.strip() == "":
        return None
    try:
        # Handle format: "2019-01-22 09:38:41"
        return datetime.strptime(date_str.strip(), "%Y-%m-%d %H:%M:%S")
    except:
        return None


def clean_zipcode(zipcode):
    """Clean zipcode data"""
    if not zipcode or zipcode.strip() == "":
        return None
    # Take only first 5 digits if longer
    clean = ''.join(c for c in str(zipcode).strip() if c.isdigit())
    return clean[:5] if len(clean) >= 5 else None


def populate_from_csv(csv_path, yaml_mapping, db_session, authors_cache=None, max_rows=100):
    """Populate database from CSV using YAML mapping"""
    
    # Get form config
    form_config = yaml_mapping['form']
    defaults = yaml_mapping['defaults']
    questions_config = yaml_mapping['questions']
    
    print(f"📊 Processing: {form_config['name']}")
    
    # Create form
    form = Form(
        name=form_config['name'],
        version=form_config['version'],
        source=form_config['source']
    )
    db_session.add(form)
    db_session.flush()
    
    print(f"✅ Form created: {form.name} (ID: {form.id})")
    
    # Create questions and options
    questions_map = {}  # question_code -> Question object
    
    for q_config in questions_config:
        question = Question(
            form_id=form.id,
            question_code=q_config['code'],
            prompt=q_config['prompt'],
            type=q_config['type'],
            position=len(questions_map) + 1
        )
        db_session.add(question)
        db_session.flush()
        
        questions_map[q_config['code']] = question
        
        # Create options if single_choice
        if q_config['type'] == 'single_choice' and 'options' in q_config:
            for opt_config in q_config['options']:
                option = Option(
                    question_id=question.id,
                    code=opt_config['code'],
                    label=opt_config['label'],
                    position=opt_config['position']
                )
                db_session.add(option)
    
    db_session.flush()
    print(f"✅ Created {len(questions_map)} questions with options")
    
    # Process CSV data
    if authors_cache is None:
        authors_cache = {}  # email_hash -> Author object
    processed_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        for row_num, row in enumerate(reader, 1):
            if row_num > max_rows:  # Limit for test data
                break
                
            # Skip empty rows
            if not any(row.values()):
                continue
                
            try:
                # Get author data
                author_id = row.get(defaults['author']['source_author_id'])
                zipcode = clean_zipcode(row.get(defaults['author']['zipcode']))
                
                if not author_id:
                    continue
                
                # Use email hash as unique key across datasets
                email_hash = hash_email(author_id)
                if not email_hash:
                    continue
                
                # Create or get author
                if email_hash not in authors_cache:
                    author = Author(
                        name=f"Utilisateur {email_hash[:8]}",
                        email_hash=email_hash,
                        zipcode=zipcode
                    )
                    db_session.add(author)
                    db_session.flush()
                    authors_cache[email_hash] = author
                else:
                    author = authors_cache[email_hash]
                
                # Create contribution
                contribution = Contribution(
                    author_id=author.id,
                    form_id=form.id,
                    source=defaults['contribution']['source'],
                    title=row.get(defaults['contribution']['title'], f"Contribution {row_num}")[:255],
                    submitted_at=parse_datetime(row.get(defaults['contribution']['submitted_at']))
                )
                db_session.add(contribution)
                db_session.flush()
                
                # Create answers
                answer_position = 1
                for q_config in questions_config:
                    source_column = q_config.get('source_column')
                    if not source_column:
                        continue
                        
                    answer_text = row.get(source_column, "").strip()
                    if answer_text and answer_text != "":
                        answer = Answer(
                            contribution_id=contribution.id,
                            question_id=questions_map[q_config['code']].id,
                            text=answer_text[:2000],  # Limit length
                            position=answer_position
                        )
                        db_session.add(answer)
                        answer_position += 1
                
                processed_count += 1
                
                if processed_count % 20 == 0:
                    print(f"   Processed {processed_count} contributions...")
                    db_session.flush()  # Flush periodically
                    
            except Exception as e:
                print(f"⚠️  Error processing row {row_num}: {e}")
                continue
    
    db_session.flush()
    print(f"✅ Created {len(authors_cache)} authors and {processed_count} contributions")
    
    return processed_count


def create_search_stats(db_session):
    """Create search stats for cache testing"""
    stats_data = [
        ("cache", 25),
        ("service", 45), 
        ("expérience", 30),
        ("démocra", 80),
        ("citoyen", 95),
        ("élection", 60),
        ("participation", 40),
        ("représentation", 35),
        ("immigration", 120),
        ("laïcité", 15),
        ("engagement", 25),
        ("incivilité", 10),
        ("discrimination", 8),
        ("rare_query", 2),
        ("very_rare", 1),
    ]
    
    for query_text, search_count in stats_data:
        stats = SearchStats(
            query_text=query_text,
            search_count=search_count
        )
        db_session.add(stats)
    
    db_session.flush()
    print(f"✅ Created {len(stats_data)} search stats entries")


def main():
    """Main population script"""
    # Database connection
    db_url = "postgresql:///test_cahier_doleances"
    print(f"🔧 Using DB URL: {db_url}")
    
    # Connect to database
    try:
        engine = create_engine(db_url, echo=False)
        SessionLocal = sessionmaker(bind=engine)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Connected to: {version[:50]}...")
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    # Find mapping files and corresponding CSV files
    mappings_dir = Path(__file__).parent.parent / "ingest" / "mappings"
    data_dir = Path(__file__).parent.parent / "data" / "example"
    
    mapping_to_csv = {
        "democratie_citoyennete.yml": "democratie-et-citoyennete-tiny.csv",
        "fiscalite_depenses.yml": "la-fiscalite-et-les-depenses-publiques-tiny.csv", 
        "transition_ecologique.yml": "la-transition-ecologique-tiny.csv",
        "organisation_etat_services.yml": "organisation-de-letat-et-des-services-publics-tiny.csv"
    }
    
    total_contributions = 0
    
    with SessionLocal() as db_session:
        print("\n🚀 Starting database population...")
        
        # Global authors cache shared between datasets
        global_authors_cache = {}  # email_hash -> Author object
        
        # Process each mapping/CSV pair
        for yaml_file, csv_file in mapping_to_csv.items():
            yaml_path = mappings_dir / yaml_file
            csv_path = data_dir / csv_file
            
            if not yaml_path.exists():
                print(f"⚠️  Mapping file not found: {yaml_path}")
                continue
                
            if not csv_path.exists():
                print(f"⚠️  CSV file not found: {csv_path}")
                continue
            
            print(f"\n📁 Processing {yaml_file} -> {csv_file}")
            
            try:
                # Load mapping
                yaml_mapping = load_yaml_mapping(yaml_path)
                
                # Populate from CSV
                count = populate_from_csv(csv_path, yaml_mapping, db_session, global_authors_cache, max_rows=50)
                total_contributions += count
                
            except Exception as e:
                print(f"❌ Error processing {yaml_file}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # Create search stats
        print(f"\n📈 Creating search statistics...")
        create_search_stats(db_session)
        
        # Commit all changes
        db_session.commit()
        
        print(f"\n{'='*60}")
        print(f"🎉 Test database populated successfully!")
        print(f"✅ Total contributions: {total_contributions}")
        print(f"✅ Forms: {db_session.query(Form).count()}")
        print(f"✅ Questions: {db_session.query(Question).count()}")
        print(f"✅ Options: {db_session.query(Option).count()}")
        print(f"✅ Authors: {db_session.query(Author).count()}")
        print(f"✅ Contributions: {db_session.query(Contribution).count()}")
        print(f"✅ Answers: {db_session.query(Answer).count()}")
        print(f"✅ Search Stats: {db_session.query(SearchStats).count()}")
        
        print(f"\n🧪 Ready for testing!")
        print(f"export TEST_DATABASE_URL='{db_url}'")
        print(f"python scripts/run_tests.py --critical")
        print(f"python -m pytest tests/ -v")
        
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)