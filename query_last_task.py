import asyncio
from src.db.connection import get_db
from sqlalchemy import text
import json

def get_last_failed():
    with get_db() as db:
        rows = db.execute(text("SELECT id, input_data, error_message, output_data FROM tasks ORDER BY id DESC LIMIT 5")).fetchall()
        for r in rows:
            print(f"Task {r[0]}: Error: {r[2]}")
            if r[3]:
                print(f"Output: {json.dumps(r[3], indent=2)}")

get_last_failed()
