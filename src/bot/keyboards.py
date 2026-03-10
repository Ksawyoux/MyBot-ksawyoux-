"""
src/bot/keyboards.py — Inline keyboards for approvals
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    """Return [✅ Approve] and [❌ Reject] buttons for a given approval ID."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{approval_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{approval_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_resolved_keyboard(status: str) -> InlineKeyboardMarkup:
    """Return a disabled button showing the resolution."""
    icon = "✅ Approved" if status == "approved" else "❌ Rejected"
    keyboard = [[InlineKeyboardButton(icon, callback_data="resolved")]]
    return InlineKeyboardMarkup(keyboard)
