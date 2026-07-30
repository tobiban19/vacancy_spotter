"""
Matching Engine & Filtering Service for Vacancy Spotter SaaS.
Handles stop-word filtering, keyword match scoring, and draft response generation.
"""

from typing import Any
from models import UserProfileDTO


def should_filter_by_stop_words(text: str, stop_words: list[str]) -> bool:
    """
    Checks whether the job post text contains any user-defined stop words.
    Case-insensitive matching. Returns True if post should be filtered out.
    """
    if not text or not stop_words:
        return False
    text_lower = text.lower()
    for word in stop_words:
        cleaned_word = word.strip().lower()
        if cleaned_word and cleaned_word in text_lower:
            return True
    return False


def _format_experience_years(years: int) -> str:
    """Helper to format experience years in Russian plural forms."""
    if 11 <= (years % 100) <= 14:
        return f"{years} лет"
    last_digit = years % 10
    if last_digit == 1:
        return f"{years} год"
    if 2 <= last_digit <= 4:
        return f"{years} года"
    return f"{years} лет"


def generate_draft_reply(user_profile: UserProfileDTO | dict[str, Any], job_text: str = "") -> str:
    """
    Generates a personalized, professional draft reply for a job posting.
    Accepts either a UserProfileDTO instance or a dict.
    """
    if isinstance(user_profile, dict):
        first_name = user_profile.get("first_name", "Фрилансер")
        experience_years = user_profile.get("experience_years", 1)
        bio_summary = user_profile.get("bio_summary", "")
        software_stack = user_profile.get("software_stack", [])
    else:
        first_name = getattr(user_profile, "first_name", "Фрилансер")
        experience_years = getattr(user_profile, "experience_years", 1)
        bio_summary = getattr(user_profile, "bio_summary", "")
        software_stack = getattr(user_profile, "software_stack", [])

    exp_str = _format_experience_years(experience_years)
    lines = [f"Здравствуйте! Меня зовут {first_name}. Мой опыт работы — {exp_str}."]

    if software_stack:
        if isinstance(software_stack, list):
            stack_str = ", ".join(str(s) for s in software_stack if s)
        else:
            stack_str = str(software_stack)
        if stack_str:
            lines.append(f"Стек / инструменты: {stack_str}.")

    if bio_summary and bio_summary.strip():
        lines.append(bio_summary.strip())

    lines.append("Заинтересовал ваш проект! Буду рад обсудить детали и приступить к выполнению.")
    return "\n\n".join(lines)


def calculate_match_score(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    """
    Calculates match score between job text and target keywords.
    Returns (score between 0.0 and 1.0, list of matched keywords).
    """
    if not text or not keywords:
        return 0.0, []
    text_lower = text.lower()
    matched = [kw for kw in keywords if kw.strip().lower() in text_lower]
    score = round(len(matched) / len(keywords), 2)
    return score, matched
