"""
Matching Engine & Filtering Service for Vacancy Spotter SaaS.
Handles stop-word filtering, keyword match scoring, vacancy intent classification, and draft response generation.
"""

import re
from typing import Any
from models import UserProfileDTO


def is_vacancy_post(text: str) -> tuple[bool, float, list[str]]:
    """
    Classifies whether a text post has vacancy/hiring intent.
    Returns (is_vacancy: bool, confidence_score: float, matched_triggers: list[str]).
    """
    if not text or not text.strip():
        return False, 0.0, []

    text_lower = text.lower()
    matched_triggers: list[str] = []

    vacancy_keywords = [
        "ищу", "нужен", "нужна", "нужны", "требуется", "требуются", "ищем",
        "вакансия", "вакансии", "заказ", "заказы", "оплата", "бюджет", "тз",
        "в команду", "отклик", "отклики", "портфолио", "резюме", "в лс",
        "руб", "рублей", "р.", "$", "usd", "eur", "€"
    ]

    non_vacancy_keywords = [
        "кто знает", "подскажите", "как сделать", "посоветуйте", "оцените",
        "где скачать", "проблема с", "почему не", "как решить", "помогите с"
    ]

    for kw in vacancy_keywords:
        if kw in text_lower:
            matched_triggers.append(kw)

    contact_matches = re.findall(r'(@[a-zA-Z0-9_]{3,}|t\.me/[a-zA-Z0-9_]+|https?://[^\s]+)', text)
    for contact in contact_matches:
        if contact not in matched_triggers:
            matched_triggers.append(contact)

    matched_negatives = [kw for kw in non_vacancy_keywords if kw in text_lower]

    pos_count = len(matched_triggers)
    neg_count = len(matched_negatives)

    if pos_count == 0:
        return False, 0.0, []

    score = min(1.0, pos_count * 0.35)
    if neg_count > 0:
        score = max(0.0, score - neg_count * 0.25)

    score = round(score, 2)
    is_vacancy = score >= 0.3 and pos_count > neg_count

    return is_vacancy, score, matched_triggers


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


def generate_draft_reply(
    user_profile: UserProfileDTO | dict[str, Any],
    job_text: str = "",
    custom_instruction: str = ""
) -> str:
    """
    Generates a personalized, professional draft reply for a job posting.
    Accepts either a UserProfileDTO instance or a dict, and optional custom_instruction.
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

    if custom_instruction and custom_instruction.strip():
        lines.append(f"📌 Дополнение: {custom_instruction.strip()}")

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
