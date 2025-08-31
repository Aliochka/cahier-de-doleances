#!/usr/bin/env python3
"""
Setup test database for full integration tests
"""
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd, description, check=True):
    """Run a command and handle errors"""
    print(f"🔧 {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        if check:
            print(f"❌ Failed: {description}")
            print(f"Error: {result.stderr}")
            return False
        else:
            print(f"⚠️  {description} (non-critical)")
            return True
    else:
        print(f"✅ {description}")
        if result.stdout.strip():
            lines = result.stdout.strip().split('\n')[:2]
            for line in lines:
                if line.strip():
                    print(f"   {line}")
        return True


def main():
    """Setup test database"""
    print("🚀 Setting up PostgreSQL test database")
    print("=" * 50)
    
    success = True
    
    # Check if PostgreSQL is installed
    success &= run_command("which psql", "Checking PostgreSQL installation")
    if not success:
        print("\n❌ PostgreSQL not installed. Please install:")
        print("   # Ubuntu/Debian: sudo apt install postgresql postgresql-contrib")
        print("   # macOS: brew install postgresql")
        print("   # Or use Docker: docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres")
        return
    
    # Check if PostgreSQL is running
    success &= run_command("pg_isready", "Checking PostgreSQL server", check=False)
    
    # Create test database
    print("\n🗄️  Setting up test database...")
    
    # Drop if exists (ignore errors)
    run_command("dropdb test_cahier_doleances", "Dropping existing test database", check=False)
    
    # Create new test database
    success &= run_command("createdb test_cahier_doleances", "Creating test database")
    
    if success:
        # Test connection and create tables
        print("\n📋 Creating database schema...")
        
        # Set environment variable for test
        env = os.environ.copy()
        env['TEST_DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/test_cahier_doleances'
        
        # Create tables using our models
        create_tables_script = '''
import os
os.environ["TEST_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/test_cahier_doleances"

from app.models import Base
from sqlalchemy import create_engine

engine = create_engine(os.environ["TEST_DATABASE_URL"])
Base.metadata.create_all(bind=engine)
print("✅ Tables created successfully")
'''
        
        with open('/tmp/create_test_tables.py', 'w') as f:
            f.write(create_tables_script)
        
        success &= run_command("python /tmp/create_test_tables.py", "Creating database tables")
        
        # Clean up
        os.unlink('/tmp/create_test_tables.py')
    
    if success:
        print("\n📊 Adding some test data...")
        
        # Create test data script
        test_data_script = '''
import os
os.environ["TEST_DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/test_cahier_doleances"

from app.models import *
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(os.environ["TEST_DATABASE_URL"])
Session = sessionmaker(bind=engine)

with Session() as db:
    # Create test form
    form = Form(name="Test Form", version="1.0", source="test")
    db.add(form)
    db.flush()
    
    # Create questions
    q1 = Question(form_id=form.id, question_code="Q1", prompt="What is your favorite color?", type="single_choice", position=1)
    q2 = Question(form_id=form.id, question_code="Q2", prompt="Describe your experience", type="text", position=2)
    db.add_all([q1, q2])
    db.flush()
    
    # Create options
    opt1 = Option(question_id=q1.id, code="RED", label="Rouge", position=1)
    opt2 = Option(question_id=q1.id, code="BLUE", label="Bleu", position=2) 
    opt3 = Option(question_id=q1.id, code="GREEN", label="Vert", position=3)
    db.add_all([opt1, opt2, opt3])
    db.flush()
    
    # Create authors
    author1 = Author(name="Test User 1", email_hash="hash1", zipcode="75001")
    author2 = Author(name="Test User 2", email_hash="hash2", zipcode="75002")
    db.add_all([author1, author2])
    db.flush()
    
    # Create contributions
    contrib1 = Contribution(author_id=author1.id, form_id=form.id, source="test", title="Test Contribution 1")
    contrib2 = Contribution(author_id=author2.id, form_id=form.id, source="test", title="Test Contribution 2")
    db.add_all([contrib1, contrib2])
    db.flush()
    
    # Create answers
    answer1 = Answer(contribution_id=contrib1.id, question_id=q1.id, text="Rouge", position=1)
    answer2 = Answer(contribution_id=contrib2.id, question_id=q1.id, text="Bleu", position=1)
    answer3 = Answer(contribution_id=contrib1.id, question_id=q2.id, text="J'ai eu une expérience très positive avec ce service.", position=1)
    answer4 = Answer(contribution_id=contrib2.id, question_id=q2.id, text="Le service pourrait être amélioré au niveau de la rapidité.", position=1)
    
    db.add_all([answer1, answer2, answer3, answer4])
    
    # Create search stats for cache tests
    stats1 = SearchStats(query_text="cache", search_count=10)
    stats2 = SearchStats(query_text="popular", search_count=25)
    stats3 = SearchStats(query_text="rare", search_count=1)
    db.add_all([stats1, stats2, stats3])
    
    db.commit()
    
print("✅ Test data created successfully")
'''
        
        with open('/tmp/create_test_data.py', 'w') as f:
            f.write(test_data_script)
        
        success &= run_command("python /tmp/create_test_data.py", "Creating test data")
        
        # Clean up
        os.unlink('/tmp/create_test_data.py')
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 Test database setup complete!")
        print("\n✅ What's ready:")
        print("• PostgreSQL test database: test_cahier_doleances")
        print("• All tables created with proper schema")
        print("• Sample data for testing")
        print("\n🧪 Test the setup:")
        print("export TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/test_cahier_doleances'")
        print("python -m pytest tests/test_cache.py -v")
        print("python scripts/run_tests.py --critical")
    else:
        print("💥 Setup had issues!")
        print("💡 Try manual setup:")
        print("1. Install PostgreSQL")
        print("2. Start PostgreSQL service")  
        print("3. createdb test_cahier_doleances")
        print("4. Run this script again")


if __name__ == "__main__":
    main()