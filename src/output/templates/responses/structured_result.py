import ast
import json
from typing import Any, Dict, List, Optional, Union

from src.output.core.envelope import OutputEnvelope, ContentBlock, ContentLayer, ListItem, StateConfig
from src.output.core.types import OutputType, TaskCategory, TaskStatus, BlockType, ListStyle
from src.output.templates.base_template import BaseTemplate

class StructuredResultTemplate(BaseTemplate):
    """
    Intelligently formats structured data (lists, dicts, or strings containing JSON) 
    into a beautiful Telegram response.
    """
    def __init__(self, data: Any, task_id: Optional[str] = None):
        self.data = data
        self.task_id = task_id

    def _parse_data(self) -> Any:
        """Attempt to parse data if it's a string, otherwise return as is."""
        if isinstance(self.data, str):
            # Try JSON first
            try:
                return json.loads(self.data)
            except (json.JSONDecodeError, TypeError):
                # Try Python literal eval (often CrewAI results look like strings of Python dicts)
                try:
                    return ast.literal_eval(self.data)
                except (ValueError, SyntaxError):
                    return self.data
        return self.data

    def render(self, transparency_tier=None, user_context=None) -> OutputEnvelope:
        parsed_data = self._parse_data()
        
        supplementary_blocks = []
        primary_text = ""

        if isinstance(parsed_data, dict) and "emails" in parsed_data:
            # Specific handling for email lists
            primary_text = "📧 *Recent Emails Found*"
            emails = parsed_data["emails"]
            if not emails:
                primary_text = "📧 No emails found."
            else:
                for email in emails:
                    subject = email.get("subject", "No Subject")
                    sender = email.get("from", "Unknown Sender")
                    date = email.get("date", "")
                    preview = email.get("body_preview", "")
                    
                    # Create a card-like block for each email
                    card = ContentBlock(
                        block_type=BlockType.CARD,
                        title=subject,
                        subtitle=f"From: {sender}\nDate: {date}",
                        body=preview,
                        collapsible=True,
                        collapsed_preview=f"📧 {subject[:40]}..."
                    )
                    supplementary_blocks.append(card)
        
        elif isinstance(parsed_data, list):
            # Generic list handling
            primary_text = "📋 *Results*"
            items = []
            for item in parsed_data:
                items.append(ListItem(text=str(item)))
            
            supplementary_blocks.append(ContentBlock(
                block_type=BlockType.LIST,
                items=items,
                list_style=ListStyle.BULLET
            ))
            
        elif isinstance(parsed_data, dict):
            # Generic dict handling
            primary_text = "🔍 *Details Found*"
            items = []
            for k, v in parsed_data.items():
                items.append(ListItem(text=f"*{k}*: {v}"))
            
            supplementary_blocks.append(ContentBlock(
                block_type=BlockType.LIST,
                items=items,
                list_style=ListStyle.BULLET
            ))
        else:
            # Fallback to plain text
            primary_text = str(parsed_data)

        return OutputEnvelope(
            task_id=self.task_id,
            type=OutputType.RESPONSE,
            category=TaskCategory.COMPLEX,
            content=ContentLayer(
                primary=ContentBlock(block_type=BlockType.TEXT, text=primary_text),
                supplementary=supplementary_blocks
            ),
            state=StateConfig(
                status=TaskStatus.COMPLETED,
                is_final=True
            )
        )
