"""
Authentication module for Vacancy Spotter SaaS Telegram Mini App.
Contains Telegram WebApp initData HMAC-SHA256 verification functions.
"""

import hashlib
import hmac
import json
from typing import Any
from urllib.parse import parse_qsl


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict[str, Any] | None:
    """
    Verifies Telegram Mini App initData string against Telegram bot token using HMAC-SHA256.

    Args:
        init_data: Raw initData query string sent by Telegram WebApp.
        bot_token: Telegram Bot API Token.

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

        if "user" in parsed:
            try:
                parsed["user"] = json.loads(parsed["user"])
            except (json.JSONDecodeError, TypeError):
                pass

        return parsed
    except Exception:
        return None
