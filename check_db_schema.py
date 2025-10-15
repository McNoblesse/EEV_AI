"""Check current database schema"""
from sqlalchemy import inspect, text
from config.database import engine

def check_schema():
    inspector = inspect(engine)
    
    # Get conversations table columns
    print("=" * 60)
    print("CONVERSATIONS TABLE COLUMNS:")
    print("=" * 60)
    
    columns = inspector.get_columns('conversations')
    for col in columns:
        print(f"  {col['name']:30} {col['type']}")
    
    print("\n" + "=" * 60)
    print("ALL TABLES:")
    print("=" * 60)
    tables = inspector.get_table_names()
    for table in tables:
        print(f"  - {table}")

if __name__ == "__main__":
    check_schema()