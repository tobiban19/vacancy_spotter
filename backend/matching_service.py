"""
Matching Engine & Filtering Service for Vacancy Spotter SaaS.
Handles stop-word filtering, keyword match scoring, vacancy intent classification, and draft response generation.
"""

import json
import logging
import re
from typing import Any

import httpx

from config import settings
from models import UserProfileDTO

log = logging.getLogger("matching_service")


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


def _normalize_profile(user_profile: UserProfileDTO | dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we need from either a DTO or a dict."""
    if isinstance(user_profile, dict):
        return {
            "first_name": user_profile.get("first_name", "Фрилансер"),
            "experience_years": user_profile.get("experience_years", 1),
            "bio_summary": user_profile.get("bio_summary", ""),
            "software_stack": user_profile.get("software_stack", []),
        }
    return {
        "first_name": getattr(user_profile, "first_name", "Фрилансер"),
        "experience_years": getattr(user_profile, "experience_years", 1),
        "bio_summary": getattr(user_profile, "bio_summary", ""),
        "software_stack": getattr(user_profile, "software_stack", []),
    }


def _generate_template_reply(
    user_profile: UserProfileDTO | dict[str, Any],
    custom_instruction: str = "",
) -> str:
    """Local template-based fallback reply (no network call)."""
    p = _normalize_profile(user_profile)
    exp_str = _format_experience_years(p["experience_years"])
    lines = [f"Здравствуйте! Меня зовут {p['first_name']}. Мой опыт работы — {exp_str}."]

    stack = p["software_stack"]
    if stack:
        stack_str = ", ".join(str(s) for s in stack if s) if isinstance(stack, list) else str(stack)
        if stack_str:
            lines.append(f"Стек / инструменты: {stack_str}.")

    bio = (p["bio_summary"] or "").strip()
    if bio:
        lines.append(bio)

    instruction = (custom_instruction or "").strip()
    if instruction:
        lines.append(f"📌 Дополнение: {instruction}")

    lines.append("Заинтересовал ваш проект! Буду рад обсудить детали и приступить к выполнению.")
    return "\n\n".join(lines)


async def _generate_draft_reply_ai(
    user_profile: UserProfileDTO | dict[str, Any],
    job_text: str,
    custom_instruction: str = "",
) -> str:
    """Generate a draft reply via OpenRouter LLM. Raises on any failure."""
    p = _normalize_profile(user_profile)
    exp_str = _format_experience_years(p["experience_years"])
    stack = p["software_stack"]
    stack_str = ", ".join(str(s) for s in stack if s) if isinstance(stack, list) else str(stack or "")

    system_prompt = (
        "Ты — помощник фрилансера. Твоя задача — написать короткое, вежливое и "
        "естественное сопроводительное письмо в ответ на вакансию/заказ в Telegram. "
        "Пиши на русском, от первого лица, без воды. До 120 слов. Не выдумывай "
        "навыки или опыт, которых нет в профиле. Начни с приветствия и имени."
    )

    user_prompt = (
        f"Профиль кандидата:\n"
        f"- Имя: {p['first_name']}\n"
        f"- Опыт: {exp_str}\n"
        f"- Стек/инструменты: {stack_str or 'не указан'}\n"
        f"- О себе: {(p['bio_summary'] or '').strip() or 'не указано'}\n\n"
        f"Текст вакансии:\n\"\"\"\n{(job_text or '').strip()[:2000]}\n\"\"\"\n"
    )
    if (custom_instruction or "").strip():
        user_prompt += f"\nПожелание к отклику: {custom_instruction.strip()}\n"
    user_prompt += "\nНапиши готовый отклик."

    api_key = settings.openrouter_api_key.get_secret_value()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        # OpenRouter ranking headers (optional but recommended).
        "HTTP-Referer": "https://vacancy-spotter.app",
        "X-Title": "Vacancy Spotter",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 350,
    }

    timeout = httpx.Timeout(settings.openrouter_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            content=json.dumps(payload),
        )
    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter returned no choices")
    content = (choices[0].get("message", {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("OpenRouter returned empty content")
    return content


async def generate_draft_reply(
    user_profile: UserProfileDTO | dict[str, Any],
    job_text: str = "",
    custom_instruction: str = "",
) -> str:
    """
    Generates a personalized draft reply for a job posting.

    Uses the OpenRouter LLM when OPENROUTER_API_KEY is configured, which
    actually accounts for the vacancy text (job_text). On any error, or when
    no key is set, gracefully falls back to the local template reply.
    """
    api_key = settings.openrouter_api_key.get_secret_value()
    if not api_key:
        return _generate_template_reply(user_profile, custom_instruction)

    try:
        return await _generate_draft_reply_ai(user_profile, job_text, custom_instruction)
    except Exception as exc:
        log.warning("AI draft generation failed, falling back to template: %s", exc)
        return _generate_template_reply(user_profile, custom_instruction)


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
