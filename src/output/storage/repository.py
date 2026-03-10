from typing import Optional, List, Dict, Any
import json
from src.output.core.envelope import OutputEnvelope
from src.db.connection import get_db
from src.db.models import TaskModel, OutputHistory

class OutputRepository:
    """Handles persistence of output envelopes to the database"""
    
    def save(self, envelope: OutputEnvelope, platform: str = "telegram", platform_msg_id: Optional[str] = None) -> bool:
        """Saves the output to the database"""
        if not envelope.task_id:
            return False # Need task_id to attach to history
            
        with get_db() as db:
            envelope_dict = envelope.model_dump(mode='json')
            
            # 1. Update tasks table
            task = db.query(TaskModel).filter(TaskModel.id == int(envelope.task_id)).first()
            if task:
                task.output_data = envelope_dict
                task.output_text = envelope.content.primary.text or ""
            
            # 2. Insert into output_history
            msg_id = None
            if platform_msg_id is not None:
                try:
                    msg_id = int(platform_msg_id)
                except ValueError:
                    pass
                    
            history = OutputHistory(
                task_id=int(envelope.task_id),
                sequence_number=envelope.sequence_number,
                output_envelope=envelope_dict,
                rendered_for=platform,
                telegram_msg_id=msg_id
            )
            db.add(history)
            
            db.commit()
            return True

    def get_latest_by_task(self, task_id: str) -> Optional[OutputEnvelope]:
        """Retrieves the latest output for a task"""
        if not task_id or not task_id.isdigit():
            return None
            
        with get_db() as db:
            result = db.query(OutputHistory).filter(
                OutputHistory.task_id == int(task_id)
            ).order_by(
                OutputHistory.sequence_number.desc(),
                OutputHistory.created_at.desc()
            ).first()
            
            if result and result.output_envelope:
                return OutputEnvelope.model_validate(result.output_envelope)
            return None
