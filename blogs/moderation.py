import logging
import os
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# api-inference.huggingface.co was deprecated; router.huggingface.co/hf-inference is current.
HF_MODEL_URL = "https://router.huggingface.co/hf-inference/models/KoalaAI/Text-Moderation"
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3

LABEL_DESCRIPTIONS = {
    "S": "sexual content",
    "H": "hate speech",
    "V": "violence",
    "HR": "harassment",
    "SH": "self-harm content",
    "S3": "sexual content involving minors",
    "H2": "hateful and threatening content",
    "V2": "graphic violence",
}

FLAG_THRESHOLD = 0.5


def _classify_text(text, api_key):
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": text[:2000]}

    for attempt in range(1, MAX_RETRIES + 1):
        response = requests.post(
            HF_MODEL_URL, headers=headers, json=payload, timeout=20)

        if response.status_code == 503:
            logger.warning(
                "Hugging Face model is loading (attempt %s/%s); retrying...",
                attempt, MAX_RETRIES,
            )
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        response.raise_for_status()
        data = response.json()

        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            return data[0]
        return data

    raise RuntimeError("Hugging Face model did not become ready in time.")


def check_blog_content(title, short_description, blog_body):
    api_key = getattr(settings, "HUGGINGFACE_API_KEY",
                      None) or os.environ.get("HUGGINGFACE_API_KEY")
    if not api_key:
        logger.error(
            "HUGGINGFACE_API_KEY not configured; flagging post for manual review.")
        return {"verdict": "flagged", "reason": "AI moderation not configured."}

    combined_text = f"{title}\n\n{short_description}\n\n{blog_body}"

    try:
        results = _classify_text(combined_text, api_key)
    except Exception:
        logger.exception(
            "AI moderation check failed; flagging post for manual review.")
        return {"verdict": "flagged", "reason": "AI moderation check failed (see logs)."}

    flagged_labels = [
        item for item in results
        if item.get("label") != "OK" and item.get("score", 0) >= FLAG_THRESHOLD
    ]

    if not flagged_labels:
        return {"verdict": "approved", "reason": "No unsafe content detected."}

    flagged_labels.sort(key=lambda item: item.get("score", 0), reverse=True)
    top = flagged_labels[0]
    description = LABEL_DESCRIPTIONS.get(top.get("label"), top.get("label"))
    reason = f"Detected possible {description} (confidence {top.get('score', 0):.0%})."

    return {"verdict": "flagged", "reason": reason}
