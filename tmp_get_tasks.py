import sys
import os
import json
from src.db.connection import engine
from sqlalchemy import text

try:
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, input_data, output_data FROM tasks ORDER BY id DESC LIMIT 2")).fetchall()
        
        ret = []
        for r in res:
            try:
                out = json.loads(r[2]) if isinstance(r[2], str) else r[2]
            except:
                out = str(r[2])
            
            try:
                inp = json.loads(r[1]) if isinstance(r[1], str) else r[1]
            except:
                inp = str(r[1])
                
            ret.append({"id": r[0], "input": inp, "output": out})
            
        print(json.dumps(ret, indent=2))
except Exception as e:
    print(f"Error: {e}")
