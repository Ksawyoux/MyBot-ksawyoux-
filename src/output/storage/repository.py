from typing import Optional, List, Dict, Any
import json
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.output.core.envelope import OutputEnvelope
from src.db.connection import get_db

class OutputRepository:
    """Handles persistence of output envelopes to the database"""
    
    def save(self, envelope: OutputEnvelope, platform: str = "telegram", platform_msg_id: Optional[str] = None) -> bool:
        """Saves the output to the database"""
        if not envelope.task_id:
            return False # Need task_id to attach to history
            
        with get_db() as db:
            envelope_dict = envelope.model_dump(mode='json')
            
            # 1. Update tasks table
            db.execute(text("""
                UPDATE tasks 
                SET output_data = :output_data, 
                    output_text = :output_text 
                WHERE id = :task_id
            """), {
                "output_data": json.dumps(envelope_dict),
                "output_text": envelope.content.primary.text or "",
                "task_id": envelope.task_id
            })
            
            # 2. Insert into output_history
            db.execute(text("""
                INSERT INTO output_history 
                (task_id, sequence_number, output_envelope, rendered_for, telegram_msg_id) 
                VALUES (:task_id, :sequence_number, :output_envelope, :rendered_for, :telegram_msg_id)
            """), {
                "task_id": envelope.task_id,
                "sequence_number": envelope.sequence_number,
                "output_envelope": json.dumps(envelope_dict),
                "rendered_for": platform,
                "telegram_msg_id": platform_msg_id
            })
            
            db.commit()
            return True

    def get_latest_by_task(self, task_id: str) -> Optional[OutputEnvelope]:
        """Retrieves the latest output for a task"""
        with get_db() as db:
            result = db.execute(text("""
                SELECT output_envelope 
                FROM output_history 
                WHERE task_id = :task_id 
                ORDER BY sequence_number DESC, created_at DESC 
                LIMIT 1
            """), {"task_id": task_id}).fetchone()
            
            if result and result[0]:
                return OutputEnvelope.model_validate(result[0])
            return None
