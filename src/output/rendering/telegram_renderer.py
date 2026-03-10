from typing import Any, Dict, Optional, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.output.core.envelope import OutputEnvelope, ContentBlock
from src.output.core.types import TransparencyTier, BlockType, ListStyle
from src.output.rendering.renderer_base import BaseRenderer, RenderedMessage
from src.output.rendering.utils import escape_markdown_v2, escape_markdown_v2_code, truncate_text, escape_markdown_v2_reserving_format

class TelegramRenderedMessage(RenderedMessage):
    """Specific format for a rendered message on Telegram"""
    def __init__(
        self, 
        text: str, 
        keyboard: Optional[InlineKeyboardMarkup] = None,
        file_attachment: Optional[Dict[str, Any]] = None,
        parse_mode: str = "MarkdownV2"
    ):
        self.text = text
        self.keyboard = keyboard
        self.file_attachment = file_attachment
        self.parse_mode = parse_mode

class TelegramRenderer(BaseRenderer):
    """Renders OutputEnvelopes into Telegram-compatible messages"""
    
    MAX_MESSAGE_LENGTH = 4096
    
    def render(self, envelope: OutputEnvelope) -> TelegramRenderedMessage:
        text_parts = []
        
        # We assume the transparency filter has already stripped non-visible elements
        # based on tier preferences
        
        # Primary Content
        text_parts.append(self._render_block(envelope.content.primary))
        
        # Supplementary Content
        for block in envelope.content.supplementary:
            if block.collapsible and block.collapsed_preview:
                text_parts.append(escape_markdown_v2(block.collapsed_preview) + " \\(Expand\\)") 
                # Note: Expand functionality would rely on Telegram features or separate messages
            else:
                text_parts.append(self._render_block(block))
                
        # Transparency Layer
        transparency_parts = []
        if envelope.transparency.reasoning:
            transparency_parts.append(
                "*\U0001f9e0 Reasoning:*\n" + escape_markdown_v2(envelope.transparency.reasoning)
            )
        
        if envelope.transparency.execution_trace and envelope.transparency.execution_trace.steps:
            transparency_parts.append("*\U0001f4cb Execution Trace:*")
            for step in envelope.transparency.execution_trace.steps:
                icon = "pending"
                if step.status == "completed": icon = "\u2705"
                elif step.status == "failed": icon = "\u274c"
                elif step.status == "running": icon = "\U0001f504"
                transparency_parts.append(f"{icon} {escape_markdown_v2(step.description)}")
                if step.details:
                    for k, v in step.details.items():
                        transparency_parts.append(f"  \u251c\u2500 {escape_markdown_v2(str(k))}: {escape_markdown_v2(str(v))}")
        
        if envelope.transparency.resources_used:
            transparency_parts.append(
                "*\U0001f4ca Resources:*\n" + 
                escape_markdown_v2(", ".join(f"{k}: {v}" for k, v in envelope.transparency.resources_used.items()))
            )
            
        if transparency_parts:
            text_parts.append("\n\\-\\-\\-\n" + "\n\n".join(transparency_parts))
            
        # Metadata
        if envelope.metadata and not envelope.rendering.collapse_metadata:
            meta_str = " | ".join(f"{k}: {v}" for k, v in envelope.metadata.items())
            text_parts.append("\n\\-\\-\\-\n_*" + escape_markdown_v2(meta_str) + "*_")

        # Combine text
        full_text = "\n\n".join(text_parts)
        
        # Handle Truncation
        file_attachment = None
        if len(full_text) > self.MAX_MESSAGE_LENGTH:
            full_text = truncate_text(full_text, 4000)
            # Future enhancement: Attach a file if the message is too long
            
        # Keyboard construction
        keyboard = self._build_keyboard(envelope.interactions.quick_actions, envelope.interactions.required_action)

        return TelegramRenderedMessage(
            text=full_text,
            keyboard=keyboard
        )
        
    def _render_block(self, block: ContentBlock) -> str:
        """Render a single content block into MarkdownV2"""
        if block.block_type == BlockType.TEXT:
            if not block.text: return ""
            if not block.markdown_enabled:
                return escape_markdown_v2(block.text)
            else:
                return escape_markdown_v2_reserving_format(block.text)
            
        elif block.block_type == BlockType.LIST:
            if not block.items: return ""
            lines = []
            for i, item in enumerate(block.items, 1):
                prefix = "\u2022 "
                if block.list_style == ListStyle.NUMBERED:
                    prefix = f"{i}\\. "
                elif block.list_style == ListStyle.CHECKLIST:
                    prefix = "[x] " if item.checked else "[ ] "
                lines.append(prefix + escape_markdown_v2(item.text))
            return "\n".join(lines)
            
        elif block.block_type == BlockType.CODE:
            if not block.code: return ""
            lang = block.language or ""
            return f"```{lang}\n{escape_markdown_v2_code(block.code)}\n```"
            
        elif block.block_type == BlockType.CARD:
            lines = []
            if block.title:
                lines.append(f"*{escape_markdown_v2(block.title)}*")
            if block.subtitle:
                lines.append(f"_{escape_markdown_v2(block.subtitle)}_")
            if block.body:
                lines.append(escape_markdown_v2(block.body))
            return "\n".join(lines)
            
        elif block.block_type == BlockType.DIVIDER:
            return "\\-\\-\\-\n"
            
        return ""

    def _build_keyboard(self, quick_actions: List[Any], required_action: Optional[Any]) -> Optional[InlineKeyboardMarkup]:
        if not quick_actions and not required_action:
            return None
            
        rows = []
        current_row = []
        
        # We roughly try to fit 2-3 buttons on a row
        all_actions = []
        if required_action:
            all_actions.append(required_action)
        all_actions.extend(quick_actions)
        
        for action in all_actions:
            if not action.enabled:
                continue
                
            label = f"{action.icon} {action.label}" if action.icon else action.label
            callback_data = action.handler.callback_data or f"action:{action.action_id}"
            url = action.handler.url
            
            button = InlineKeyboardButton(text=label, callback_data=callback_data if not url else None, url=url)
            current_row.append(button)
            
            if len(current_row) >= 2:
                rows.append(current_row)
                current_row = []
                
        if current_row:
            rows.append(current_row)
            
        return InlineKeyboardMarkup(rows) if rows else None
