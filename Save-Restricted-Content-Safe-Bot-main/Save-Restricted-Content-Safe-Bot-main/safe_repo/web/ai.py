import os
import threading
import time
from collections import deque
from urllib.parse import urlparse

import requests
from flask import jsonify, request, session

MAX_QUESTION_LENGTH = 2000
MAX_REQUESTS_PER_HOUR = 10
REQUEST_TIMEOUT = (5, 25)
_request_times = {}
_request_lock = threading.Lock()


def _provider_config():
    session_secret = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if len(session_secret) < 32:
        return None
    base_url = os.environ.get("AI_API_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("AI_MODEL", "").strip()
    parsed = urlparse(base_url)
    local_http = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    valid_url = parsed.scheme == "https" or (parsed.scheme == "http" and local_http)
    if not parsed.netloc or not valid_url or not model:
        return None
    return {
        "base_url": base_url,
        "model": model,
        "api_key": os.environ.get("AI_API_KEY", "").strip(),
        "provider": os.environ.get("AI_PROVIDER_NAME", "configured AI provider").strip(),
    }


def ai_page_config():
    return {"enabled": _provider_config() is not None, "authenticated": bool(session.get("user_id"))}


def _consume_rate_limit(user_id):
    now = time.monotonic()
    cutoff = now - 3600
    with _request_lock:
        for key in list(_request_times):
            timestamps = _request_times[key]
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if not timestamps:
                del _request_times[key]
        timestamps = _request_times.setdefault(user_id, deque())
        if len(timestamps) >= MAX_REQUESTS_PER_HOUR:
            return False
        timestamps.append(now)
        return True


def ai_chat():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "error": "Please log in to use the study assistant."}), 401

    config = _provider_config()
    if not config:
        return jsonify({"success": False, "error": "The AI assistant is not configured."}), 503

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Send a JSON object with a question."}), 400
    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"success": False, "error": "Enter a question first."}), 400
    question = question.strip()
    if len(question) > MAX_QUESTION_LENGTH:
        return jsonify({"success": False, "error": "Questions must be 2,000 characters or fewer."}), 400
    if data.get("consent") is not True:
        return jsonify({"success": False, "error": "Consent is required before sending a question."}), 400
    if not _consume_rate_limit(str(user_id)):
        return jsonify({"success": False, "error": "You have reached the limit of 10 questions per hour."}), 429

    headers = {"Content-Type": "application/json"}
    if config["api_key"]:
        headers["Authorization"] = f"Bearer {config['api_key']}"
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "You are a helpful study assistant. Answer clearly in the language used by the student. You only receive the student's current question; do not claim access to their account, saved media, or website activity."},
            {"role": "user", "content": question},
        ],
        "max_tokens": 700,
        "temperature": 0.4,
    }

    try:
        response = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        answer = response.json()["choices"][0]["message"]["content"]
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Empty AI response")
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
        return jsonify({"success": False, "error": "The AI provider could not answer right now. Please try again later."}), 502

    result = jsonify({"success": True, "answer": answer[:10000], "provider": config["provider"]})
    result.headers["Cache-Control"] = "no-store"
    return result