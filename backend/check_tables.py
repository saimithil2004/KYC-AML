from app.core.database import SessionLocalSync
from sqlalchemy import inspect

db = SessionLocalSync()
try:
    inspector = inspect(db.bind)
    for table in ['regulations', 'policy_rules']:
        print(f"Table {table}:")
        for col in inspector.get_columns(table):
            print(f"  {col['name']}: {col['type']}")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
