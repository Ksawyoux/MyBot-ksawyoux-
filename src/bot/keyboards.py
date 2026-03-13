"""
src/bot/keyboards.py — Inline keyboards for approvals and skills
"""

import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

SKILLS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skills")

def get_all_skills() -> list[str]:
    """Return a sorted list of all available skills by scanning the skills directory."""
    if not os.path.exists(SKILLS_DIR):
        return []
    
    skills = []
    for entry in os.scandir(SKILLS_DIR):
        if entry.is_dir() and not entry.name.startswith("__"):
            skills.append(entry.name)
            
    return sorted(skills)

def get_skills_keyboard(page: int = 0, skills_per_page: int = 15) -> InlineKeyboardMarkup:
    """Return a paginated keyboard of all available skills."""
    skills = get_all_skills()
    total_skills = len(skills)
    
    start_idx = page * skills_per_page
    end_idx = min(start_idx + skills_per_page, total_skills)
    
    current_page_skills = skills[start_idx:end_idx]
    
    keyboard = []
    # Add skills in rows of 2 for better layout
    for i in range(0, len(current_page_skills), 2):
        row = []
        skill1 = current_page_skills[i]
        # We use a truncated name for display if it's very long, but full name for callback data
        display_name1 = skill1.replace("-", " ").title()
        row.append(InlineKeyboardButton(display_name1, callback_data=f"select_skill_{skill1}"))
        
        if i + 1 < len(current_page_skills):
            skill2 = current_page_skills[i+1]
            display_name2 = skill2.replace("-", " ").title()
            row.append(InlineKeyboardButton(display_name2, callback_data=f"select_skill_{skill2}"))
            
        keyboard.append(row)
        
    # Pagination row
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"skills_page_{page-1}"))
    
    # Add indicator like "1/3"
    total_pages = (total_skills + skills_per_page - 1) // skills_per_page
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data="ignore_pagination"))
        
    if end_idx < total_skills:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"skills_page_{page+1}"))
        
    if nav_row:
        keyboard.append(nav_row)
        
    # Clear skill button always at the bottom
    keyboard.append([InlineKeyboardButton("❌ Clear Active Skill", callback_data="clear_skill")])
    
    return InlineKeyboardMarkup(keyboard)

def get_approval_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    """Return [ APPROVE ] and [ REJECT ] buttons for a given approval ID."""
    keyboard = [
        [
            InlineKeyboardButton("APPROVE", callback_data=f"approve_{approval_id}"),
            InlineKeyboardButton("REJECT", callback_data=f"reject_{approval_id}"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_resolved_keyboard(status: str) -> InlineKeyboardMarkup:
    """Return a disabled button showing the resolution."""
    icon = "APPROVED" if status == "approved" else "REJECTED"
    keyboard = [[InlineKeyboardButton(icon, callback_data="resolved")]]
    return InlineKeyboardMarkup(keyboard)
