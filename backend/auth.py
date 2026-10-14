"""
Authentication module for Vacancy Spotter SaaS Telegram Mini App.
Contains Telegram WebApp initData HMAC-SHA256 verification functions.
"""

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import parse_qsl


import time

def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int | None = None,
) -> dict[str, Any] | None:
    """
    Verifies Telegram Mini App initData string against Telegram bot token using HMAC-SHA256.

    Args:
        init_data: Raw initData query string sent by Telegram WebApp.
        bot_token: Telegram Bot API Token.
        max_age_seconds: Optional max allowed age of the auth_date in seconds (replay protection).

    Returns:
        dict containing parsed initData fields (with 'user' parsed as dict if present)
        or None if validation fails or hash is invalid.
    """
    if not init_data or not bot_token:
        return None

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed:
            return None

        hash_check = parsed.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash.lower(), hash_check.lower()):
            return None

        if max_age_seconds is not None and "auth_date" in parsed:
            auth_date = int(parsed["auth_date"])
            now = int(time.time())
            if auth_date > now + 300 or now - auth_date > max_age_seconds:
                return None

        if "user" in parsed:
            try:
                parsed["user"] = json.loads(parsed["user"])
            except (json.JSONDecodeError, TypeError):
                pass

        return parsed
    except Exception:
        return None


def extract_telegram_user(init_data: str, bot_token: str, max_age_seconds: int | None = None) -> dict[str, Any] | None:
    """Convenience helper that verifies initData and returns the parsed user dict directly."""
    res = verify_telegram_init_data(init_data, bot_token, max_age_seconds=max_age_seconds)
    if res and isinstance(res.get("user"), dict):
        return res["user"]
    return None
