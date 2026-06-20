import hashlib
import json
import logging

import requests
from django.conf import settings

from .models import BlogContentAnalysis

logger = logging.getLogger(__name__)

HF_CHAT_URL = 'https://router.huggingface.co/v1/chat/completions'
HF_CLASSIFICATION_URL = (
    'https://router.huggingface.co/hf-inference/models/{model}'
)

SYSTEM_PROMPT = """You are an English writing editor. Analyze the supplied blog
content and return only one valid JSON object with this exact shape:
{
  "grammar_score": 0,
  "vocabulary_score": 0,
  "grammar_errors": [
    {"original": "", "suggestion": "", "explanation": ""}
  ],
  "spelling_errors": [
    {"original": "", "suggestion": "", "explanation": ""}
  ],
  "suggestions": [""],
  "summary": ""
}
Scores must be integers from 0 to 100. Keep each list concise, use empty lists
when no issue exists, and never include Markdown or text outside the JSON."""


def _clamp_score(value):
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _normalize_issue_list(value):
    normalized = []
    if not isinstance(value, list):
        return normalized
    for item in value[:20]:
        if isinstance(item, str):
            normalized.append({
                'original': item[:250],
                'suggestion': '',
                'explanation': '',
            })
        elif isinstance(item, dict):
            normalized.append({
                'original': str(item.get('original', ''))[:250],
                'suggestion': str(item.get('suggestion', ''))[:250],
                'explanation': str(item.get('explanation', ''))[:500],
            })
    return normalized


def _extract_json(raw_content):
    """Accept plain JSON or JSON wrapped in a model's Markdown/code chatter."""
    if isinstance(raw_content, dict):
        return raw_content
    if not isinstance(raw_content, str):
        raise ValueError('Writing model returned no text content.')

    start = raw_content.find('{')
    if start < 0:
        raise ValueError('Writing model response did not contain JSON.')
    result, _ = json.JSONDecoder().raw_decode(raw_content[start:])
    if not isinstance(result, dict):
        raise ValueError('Writing model JSON was not an object.')
    return result


def _request_quality_analysis(text, api_key, model):
    response = requests.post(
        HF_CHAT_URL,
        headers={'Authorization': f'Bearer {api_key}'},
        json={
            'model': model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': text},
            ],
            'temperature': 0.1,
            'max_tokens': 900,
        },
        timeout=settings.HF_ANALYZER_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload['choices'][0]['message']['content']
    data = _extract_json(content)
    return {
        'grammar_score': _clamp_score(data.get('grammar_score')),
        'vocabulary_score': _clamp_score(data.get('vocabulary_score')),
        'grammar_errors': _normalize_issue_list(data.get('grammar_errors')),
        'spelling_errors': _normalize_issue_list(data.get('spelling_errors')),
        'suggestions': [
            str(item)[:500] for item in data.get('suggestions', [])[:20]
            if isinstance(item, (str, int, float))
        ] if isinstance(data.get('suggestions'), list) else [],
        'summary': str(data.get('summary', ''))[:2000],
    }


def _request_ai_percentage(text, api_key, model):
    response = requests.post(
        HF_CLASSIFICATION_URL.format(model=model),
        headers={'Authorization': f'Bearer {api_key}'},
        json={'inputs': text[:4000]},
        timeout=settings.HF_ANALYZER_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list) and payload and isinstance(payload[0], list):
        payload = payload[0]
    if not isinstance(payload, list):
        raise ValueError('AI detector returned an unexpected response.')

    # The default detector uses Fake/Real. LABEL_0 is retained as a fallback
    # for providers that omit the model's configured label names.
    for item in payload:
        label = str(item.get('label', '')).lower()
        if label in {'fake', 'ai', 'ai-generated', 'label_0'}:
            return round(max(0, min(1, float(item.get('score', 0)))) * 100, 2)
    raise ValueError('AI detector response had no AI-generated label.')


def analyze_blog_content(post):
    """Analyze and persist the latest result without blocking post workflow."""
    api_key = settings.HUGGINGFACE_API_KEY
    quality_model = settings.HF_WRITING_ANALYSIS_MODEL
    detector_model = settings.HF_AI_DETECTOR_MODEL
    text = (
        f'Title: {post.title}\n\n'
        f'Short description: {post.short_description}\n\n'
        f'Blog body:\n{post.blog_body}'
    )[:8000]
    content_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    defaults = {
        'content_hash': content_hash,
        'quality_model': quality_model,
        'detector_model': detector_model,
        'grammar_score': None,
        'vocabulary_score': None,
        'grammar_errors': [],
        'spelling_errors': [],
        'suggestions': [],
        'summary': '',
        'ai_generated_percentage': None,
        'error_message': '',
    }

    if not api_key:
        defaults.update({
            'status': 'unavailable',
            'error_message': 'HUGGINGFACE_API_KEY is not configured.',
        })
        analysis, _ = BlogContentAnalysis.objects.update_or_create(
            blog=post, defaults=defaults)
        return analysis

    errors = []
    quality_succeeded = False
    detector_succeeded = False
    try:
        defaults.update(_request_quality_analysis(text, api_key, quality_model))
        quality_succeeded = True
    except Exception as exc:
        logger.exception('Writing-quality analysis failed for blog id=%s', post.pk)
        errors.append(f'Writing analysis failed: {exc}')

    try:
        defaults['ai_generated_percentage'] = _request_ai_percentage(
            text, api_key, detector_model)
        detector_succeeded = True
    except Exception as exc:
        logger.exception('AI-text detection failed for blog id=%s', post.pk)
        errors.append(f'AI detection failed: {exc}')

    if quality_succeeded and detector_succeeded:
        defaults['status'] = 'success'
    elif quality_succeeded or detector_succeeded:
        defaults['status'] = 'partial'
    else:
        defaults['status'] = 'failed'
    defaults['error_message'] = ' '.join(errors)[:2000]

    analysis, _ = BlogContentAnalysis.objects.update_or_create(
        blog=post, defaults=defaults)
    return analysis
