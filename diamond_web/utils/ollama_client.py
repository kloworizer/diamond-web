"""Minimal Ollama HTTP client for the Chat menu.

Talks to a local Ollama server over its REST API using only the standard
library, so the project gains no new dependency. All connection details come
from ``.env`` via ``config.settings`` (``OLLAMA_BASE_URL``, ``OLLAMA_MODEL``,
``OLLAMA_TIMEOUT``, …).
"""

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when the Ollama server is unreachable or returns an error."""


def _base_url():
    return getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434').rstrip('/')


def is_enabled():
    """Return True when the Chat feature is switched on in ``.env``."""
    return getattr(settings, 'OLLAMA_ENABLED', True)


def _describe_http_error(status, detail):
    """Turn an Ollama error body into an actionable message.

    The most common failure on a CPU-only host is the model runner aborting
    because the KV cache allocation (num_ctx * OLLAMA_NUM_PARALLEL) does not
    fit in RAM. Ollama reports that only as "exit status 2", so the cause is
    spelled out here.
    """
    lowered = detail.lower()
    if 'terminated' in lowered or 'exit status' in lowered or 'memory' in lowered:
        num_ctx = getattr(settings, 'OLLAMA_NUM_CTX', 4096)
        return (
            f'Model gagal dimuat oleh Ollama (HTTP {status}). Penyebab paling umum '
            f'adalah RAM tidak cukup untuk KV cache pada OLLAMA_NUM_CTX={num_ctx}. '
            f'Turunkan OLLAMA_NUM_CTX di .env (mis. 2048), tutup aplikasi lain, '
            f'atau gunakan model yang lebih kecil. Detail: {detail}'
        )
    return f'Ollama membalas HTTP {status}: {detail}'


def _request(path, payload=None, method='GET', timeout=None):
    """Send a JSON request to the Ollama server and decode the JSON reply."""
    url = f'{_base_url()}{path}'
    timeout = timeout or getattr(settings, 'OLLAMA_TIMEOUT', 120)

    data = None
    headers = {'Accept': 'application/json'}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')[:300]
        raise OllamaError(_describe_http_error(exc.code, detail or exc.reason)) from exc
    except urllib.error.URLError as exc:
        raise OllamaError(
            f'Tidak dapat terhubung ke Ollama di {_base_url()} ({exc.reason}). '
            'Pastikan Ollama sedang berjalan.'
        ) from exc
    except TimeoutError as exc:
        raise OllamaError(
            f'Ollama tidak merespons dalam {timeout} detik. Permintaan pertama '
            'setelah Ollama idle harus memuat model lebih dulu sehingga jauh '
            'lebih lambat — coba ulangi, atau naikkan OLLAMA_TIMEOUT di .env.'
        ) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise OllamaError('Respons Ollama bukan JSON yang valid.') from exc


def list_models():
    """Return the model names installed on the Ollama server."""
    payload = _request('/api/tags', timeout=10)
    return [model.get('name', '') for model in payload.get('models', [])]


def test_connection():
    """Check that Ollama is reachable and the configured model is installed.

    Returns:
        dict: ``{'ok', 'message', 'models'}``. ``ok`` is False when the server
        is unreachable or the configured model is missing.
    """
    model = getattr(settings, 'OLLAMA_MODEL', '')
    try:
        models = list_models()
    except OllamaError as exc:
        return {'ok': False, 'message': str(exc), 'models': []}

    # Ollama reports tags as "name:tag"; an untagged config means ":latest".
    wanted = model if ':' in model else f'{model}:latest'
    if wanted not in models and model not in models:
        return {
            'ok': False,
            'message': (
                f'Terhubung ke Ollama, tetapi model "{model}" belum terpasang. '
                f'Jalankan: ollama pull {model}'
            ),
            'models': models,
        }

    return {
        'ok': True,
        'message': f'Terhubung ke Ollama. Model "{model}" siap digunakan.',
        'models': models,
    }


def chat(messages, json_mode=False, timeout=None):
    """Send a chat completion request and return the assistant's text.

    Args:
        messages: List of ``{'role': ..., 'content': ...}`` dicts.
        json_mode: When True, ask Ollama to constrain the reply to valid JSON.
        timeout: Per-request timeout in seconds; defaults to ``OLLAMA_TIMEOUT``.

    Returns:
        str: The assistant message content.

    Raises:
        OllamaError: On connection failure or a malformed response.
    """
    payload = {
        'model': getattr(settings, 'OLLAMA_MODEL', 'llama3.1:8b'),
        'messages': messages,
        'stream': False,
        'options': {
            'temperature': getattr(settings, 'OLLAMA_TEMPERATURE', 0.0),
            'num_ctx': getattr(settings, 'OLLAMA_NUM_CTX', 8192),
        },
    }
    if json_mode:
        payload['format'] = 'json'

    response = _request('/api/chat', payload=payload, method='POST', timeout=timeout)
    content = (response.get('message') or {}).get('content')
    if not content:
        raise OllamaError('Ollama mengembalikan respons kosong.')
    return content.strip()
