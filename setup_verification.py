"""
Quick Setup Script for Knowledge Base Document Ingestion
Run this script to verify dependencies and configuration
"""

import sys
import subprocess
import os

def check_python_version():
    """Check if Python version is compatible"""
    print("\n🐍 Checking Python version...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor} - Required: Python 3.8+")
        return False

def check_dependencies():
    """Check if required packages are installed"""
    print("\n📦 Checking dependencies...")
    
    required_packages = {
        'fastapi': 'FastAPI',
        'sqlalchemy': 'SQLAlchemy',
        'PyPDF2': 'PyPDF2',
        'docx': 'python-docx',
        'pytesseract': 'pytesseract',
        'pdf2image': 'pdf2image',
        'PIL': 'Pillow',
        'pinecone': 'pinecone',
        'langchain': 'langchain'
    }
    
    missing = []
    for package, name in required_packages.items():
        try:
            __import__(package)
            print(f"   ✅ {name}")
        except ImportError:
            print(f"   ❌ {name} - Not installed")
            missing.append(name)
    
    if missing:
        print("\n⚠️  Missing packages detected!")
        print("   Run: pip install -r requirements.txt")
        return False
    
    return True

def check_tesseract():
    """Check if Tesseract OCR is installed"""
    print("\n🔍 Checking Tesseract OCR...")
    try:
        result = subprocess.run(
            ['tesseract', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"   ✅ {version}")
            return True
        else:
            print("   ❌ Tesseract not found")
            return False
    except FileNotFoundError:
        print("   ❌ Tesseract not installed or not in PATH")
        print("\n   Installation instructions:")
        print("   - Windows: https://github.com/UB-Mannheim/tesseract/wiki")
        print("   - Linux: sudo apt-get install tesseract-ocr")
        print("   - macOS: brew install tesseract")
        return False
    except Exception as e:
        print(f"   ⚠️  Could not verify Tesseract: {e}")
        return False

def check_env_file():
    """Check if .env file exists and has required variables"""
    print("\n🔐 Checking environment configuration...")
    
    if not os.path.exists('.env'):
        print("   ❌ .env file not found")
        print("   Create .env file with required variables")
        return False
    
    print("   ✅ .env file exists")
    
    # Check for required variables
    required_vars = [
        'PINECONE_API_KEY',
        'GEMINI_API_KEY',
        'OPENAI_API_KEY',
        'POSTGRES_MEMORY_URL',
        'TIER1_API_KEY'
    ]
    
    optional_vars = [
        'LANGCHAIN_TRACING_V2',
        'LANGCHAIN_API_KEY',
        'LANGCHAIN_PROJECT'
    ]
    
    with open('.env', 'r') as f:
        content = f.read()
    
    missing_required = []
    for var in required_vars:
        if var not in content or f"{var}=" not in content:
            missing_required.append(var)
        else:
            # Check if value is set (not empty)
            for line in content.split('\n'):
                if line.startswith(f"{var}="):
                    value = line.split('=', 1)[1].strip()
                    if value and value != "your_key_here":
                        print(f"   ✅ {var}")
                    else:
                        print(f"   ⚠️  {var} - Set but empty")
                        missing_required.append(var)
                    break
    
    print("\n   Optional (LangSmith monitoring):")
    for var in optional_vars:
        if var in content:
            print(f"   ✅ {var}")
        else:
            print(f"   ℹ️  {var} - Not set (optional)")
    
    if missing_required:
        print(f"\n   ❌ Missing required variables: {', '.join(missing_required)}")
        return False
    
    return True

def check_database_connection():
    """Check if database connection works"""
    print("\n🗄️  Checking database connection...")
    try:
        from config.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("   ✅ Database connection successful")
            return True
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        print("   Check POSTGRES_MEMORY_URL in .env")
        return False

def check_migrations():
    """Check if migrations are applied"""
    print("\n📊 Checking database tables...")
    try:
        from config.database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        required_tables = [
            'conversations',
            'agent_sessions',
            'knowledge_base_usage',
            'escalation_logs',
            'document_uploads'
        ]
        
        missing_tables = []
        for table in required_tables:
            if table in tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} - Not found")
                missing_tables.append(table)
        
        if missing_tables:
            print("\n   ⚠️  Missing tables detected!")
            print("   Run: python -c \"from config.database import engine, Base; Base.metadata.create_all(bind=engine)\"")
            return False
        
        return True
    except Exception as e:
        print(f"   ⚠️  Could not check tables: {e}")
        return False

def main():
    """Run all checks"""
    print("=" * 60)
    print("  EEV AI - Knowledge Base Setup Verification")
    print("=" * 60)
    
    results = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'Tesseract OCR': check_tesseract(),
        'Environment Config': check_env_file(),
        'Database Connection': check_database_connection(),
        'Database Tables': check_migrations()
    }
    
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All checks passed! System is ready.")
        print("\n📝 Next steps:")
        print("   1. Start server: uvicorn main:app --reload")
        print("   2. Visit docs: http://localhost:8000/docs")
        print("   3. Test upload endpoint")
    else:
        print("\n⚠️  Some checks failed. Please fix the issues above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
