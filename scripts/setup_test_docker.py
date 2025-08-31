#!/usr/bin/env python3
"""
Setup isolated test database with Docker - SAFE approach
"""
import subprocess
import sys
import os
import time


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
        return True


def main():
    """Setup isolated test database with Docker"""
    print("🐳 Setting up ISOLATED test database with Docker")
    print("=" * 60)
    
    # Check if Docker is available
    if not run_command("which docker", "Checking Docker installation"):
        print("\n❌ Docker not installed. Alternatives:")
        print("1. Install Docker: https://docs.docker.com/get-docker/")
        print("2. Use sudo for PostgreSQL: sudo -u postgres createdb test_cahier_doleances")
        print("3. Use SQLite fallback (limited compatibility)")
        return False
    
    # Stop existing test container if any
    run_command("docker stop test-postgres-cahier", "Stopping existing test container", check=False)
    run_command("docker rm test-postgres-cahier", "Removing existing test container", check=False)
    
    # Start PostgreSQL test container
    print("\n🚀 Starting isolated PostgreSQL test container...")
    cmd = """
    docker run -d \
      --name test-postgres-cahier \
      -e POSTGRES_PASSWORD=testpass \
      -e POSTGRES_USER=testuser \
      -e POSTGRES_DB=test_cahier_doleances \
      -p 5433:5432 \
      postgres:15
    """
    
    if not run_command(cmd, "Starting PostgreSQL container"):
        return False
    
    # Wait for PostgreSQL to be ready
    print("⏳ Waiting for PostgreSQL to start...")
    max_attempts = 30
    for i in range(max_attempts):
        if run_command("docker exec test-postgres-cahier pg_isready -U testuser", "Checking PostgreSQL readiness", check=False):
            break
        time.sleep(1)
        print(f"   Attempt {i+1}/{max_attempts}")
    else:
        print("❌ PostgreSQL failed to start in time")
        return False
    
    # Create tables
    print("\n📋 Creating test schema and data...")
    
    # Create schema script
    schema_script = '''
import os
from sqlalchemy import create_engine
from app.models import Base

# Connect to test container
engine = create_engine("postgresql://testuser:testpass@localhost:5433/test_cahier_doleances")

# Create all tables
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

print("✅ Schema created")
'''
    
    with open('/tmp/create_test_schema.py', 'w') as f:
        f.write(schema_script)
    
    if not run_command("python /tmp/create_test_schema.py", "Creating database schema"):
        return False
    
    # Create test data
    data_script = '''
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import *

# Connect to test container
engine = create_engine("postgresql://testuser:testpass@localhost:5433/test_cahier_doleances")
Session = sessionmaker(bind=engine)

with Session() as db:
    # Create comprehensive test data
    form = Form(name="Test Form", version="1.0", source="test")
    db.add(form)
    db.flush()
    
    # Questions
    q1 = Question(form_id=form.id, question_code="Q1", prompt="What is your favorite color?", type="single_choice", position=1)
    q2 = Question(form_id=form.id, question_code="Q2", prompt="Describe your experience", type="text", position=2)
    q3 = Question(form_id=form.id, question_code="Q3", prompt="Rate our service", type="single_choice", position=3)
    db.add_all([q1, q2, q3])
    db.flush()
    
    # Options for single choice questions
    opts = [
        Option(question_id=q1.id, code="RED", label="Rouge", position=1),
        Option(question_id=q1.id, code="BLUE", label="Bleu", position=2),
        Option(question_id=q1.id, code="GREEN", label="Vert", position=3),
        Option(question_id=q3.id, code="EXCELLENT", label="Excellent", position=1),
        Option(question_id=q3.id, code="GOOD", label="Bien", position=2),
        Option(question_id=q3.id, code="AVERAGE", label="Moyen", position=3),
    ]
    db.add_all(opts)
    db.flush()
    
    # Authors
    authors = [
        Author(name="Alice Dupont", email_hash="hash1", zipcode="75001", city="Paris"),
        Author(name="Bob Martin", email_hash="hash2", zipcode="69001", city="Lyon"),
        Author(name="Claire Durand", email_hash="hash3", zipcode="13001", city="Marseille"),
    ]
    db.add_all(authors)
    db.flush()
    
    # Contributions and answers
    for i, author in enumerate(authors):
        contrib = Contribution(author_id=author.id, form_id=form.id, source="test", title=f"Contribution {i+1}")
        db.add(contrib)
        db.flush()
        
        # Answers
        answers = [
            Answer(contribution_id=contrib.id, question_id=q1.id, text=["Rouge", "Bleu", "Vert"][i], position=1),
            Answer(contribution_id=contrib.id, question_id=q2.id, text=f"Mon expérience avec le service numéro {i+1}. " + ("Très positive! " * (i+1)), position=1),
            Answer(contribution_id=contrib.id, question_id=q3.id, text=["Excellent", "Bien", "Moyen"][i], position=1),
        ]
        db.add_all(answers)
    
    # Search stats for cache testing
    search_stats = [
        SearchStats(query_text="service", search_count=25),
        SearchStats(query_text="expérience", search_count=15),
        SearchStats(query_text="positive", search_count=8),
        SearchStats(query_text="rare_query", search_count=1),
    ]
    db.add_all(search_stats)
    
    db.commit()

print("✅ Test data created")
'''
    
    with open('/tmp/create_test_data.py', 'w') as f:
        f.write(data_script)
    
    if not run_command("python /tmp/create_test_data.py", "Creating test data"):
        return False
    
    # Cleanup temp files
    os.unlink('/tmp/create_test_schema.py')
    os.unlink('/tmp/create_test_data.py')
    
    print("\n" + "=" * 60)
    print("🎉 Isolated test database ready!")
    print("\n✅ What's running:")
    print("• Docker container: test-postgres-cahier")
    print("• PostgreSQL: localhost:5433 (isolated port)")
    print("• Database: test_cahier_doleances")
    print("• User: testuser / Pass: testpass")
    
    print("\n🧪 Test it:")
    print("export TEST_DATABASE_URL='postgresql://testuser:testpass@localhost:5433/test_cahier_doleances'")
    print("python scripts/run_tests.py --critical")
    print("python -m pytest tests/test_cache.py -v")
    
    print("\n🛑 Stop when done:")
    print("docker stop test-postgres-cahier")
    print("docker rm test-postgres-cahier")
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        print("\n💡 Fallback options if Docker fails:")
        print("1. Use existing working basic tests: python scripts/run_tests.py --critical")
        print("2. Manual PostgreSQL setup with sudo")
        print("3. SQLite fallback (limited compatibility)")
        sys.exit(1)