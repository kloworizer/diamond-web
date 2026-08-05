"""Chat — a read-only database assistant backed by a local Ollama model.

The user asks a question in plain language. A local LLM turns it into a single
SQL ``SELECT``, which is validated and executed by
:mod:`diamond_web.utils.sql_guard` against an allowlist of business tables.
The rows are then handed back to the model to phrase an answer.

The model is never trusted with database access: it only proposes SQL text.
Authentication tables (passwords, groups, permissions, sessions) are outside
the allowlist, so no prompt can reach them, and every query runs on a
connection that cannot write.
"""

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from ..utils import ollama_client
from ..utils.ollama_client import OllamaError
from ..utils.sql_guard import (
    ALLOWED_TABLES,
    SQLGuardError,
    get_schema_prompt,
    run_readonly_query,
)

logger = logging.getLogger(__name__)

MAX_QUESTION_LENGTH = 1000

# Instructions for the SQL-writing step. The guard enforces these rules
# independently — the prompt only makes the model likely to comply on the
# first try instead of being rejected.
SQL_SYSTEM_PROMPT = """\
Kamu adalah asisten data untuk aplikasi Diamond (aplikasi penghimpunan dan \
pengolahan data eksternal DJP). Tugasmu mengubah pertanyaan pengguna menjadi \
SATU query SQL SELECT untuk database {vendor}.

ATURAN WAJIB:
1. Hanya SELECT. Dilarang INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, \
ATTACH, PRAGMA, atau perintah apa pun yang mengubah data.
2. Hanya satu perintah per query. Jangan gunakan tanda titik koma untuk \
menggabungkan perintah.
3. Hanya boleh menggunakan tabel dan kolom yang tercantum pada SKEMA di bawah. \
Tabel lain TIDAK ADA dan tidak boleh disebut.
4. Data kredensial dan hak akses pengguna (password, grup, permission, sesi) \
tidak tersedia. Jika pengguna memintanya, jawab bahwa data itu tidak dapat \
diakses — jangan mencoba membuat query untuk itu.
5. Selalu batasi hasil dengan LIMIT {max_rows} kecuali query sudah berupa \
agregasi yang menghasilkan sedikit baris.
6. Gunakan JOIN bila perlu, dan beri alias kolom agar hasilnya mudah dibaca.

SKEMA YANG DIIZINKAN:
{schema}

Jawab HANYA dengan objek JSON berikut:
{{"sql": "<query SELECT>", "explanation": "<penjelasan singkat 1 kalimat>"}}

Jika pertanyaan tidak membutuhkan data dari database (misalnya sapaan atau \
pertanyaan umum), atau meminta data yang tidak diizinkan, jawab dengan:
{{"sql": null, "message": "<jawaban atau alasan singkat dalam Bahasa Indonesia>"}}
"""

# Instructions for the answer-writing step.
#
# This is sent as a follow-up *user* turn continuing the same conversation
# rather than as a fresh system prompt. Ollama caches the prompt prefix, and
# a llama.cpp server with a single slot (the default) can only hold one
# prefix at a time — alternating two different system prompts made every call
# reprocess ~1500 tokens and pushed round-trips past two minutes on CPU.
# Continuing the conversation keeps the cached prefix valid, so only the new
# turn is processed.
ANSWER_INSTRUCTION = """\
Query di atas sudah dijalankan. Sekarang jawab pertanyaan tadi dalam Bahasa \
Indonesia biasa — BUKAN JSON, tanpa blok kode.

Jawab maksimal 3 kalimat. Tabel hasil sudah ditampilkan ke pengguna, jadi \
JANGAN menyebutkan ulang seluruh baris — cukup rangkum temuan utamanya \
(misalnya nilai tertinggi, total, atau polanya). Hanya gunakan angka yang \
ada pada hasil; jangan mengarang. Jika hasil kosong, katakan datanya tidak \
ditemukan. Jika hasil dipotong karena batas baris, sebutkan bahwa yang \
ditampilkan hanya sebagian.

HASIL QUERY (JSON): {results}
"""


def _extract_json(text):
    """Parse a JSON object from a model reply, tolerating stray prose/fences.

    Ollama's ``format: json`` normally returns clean JSON, but smaller models
    occasionally wrap it in markdown fences or add a sentence.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def _build_sql_messages(question, history, repair=None):
    """Assemble the message list for the SQL-generation call.

    Args:
        question: The user's current question.
        history: Prior ``{'role', 'content'}`` turns, already trimmed.
        repair: Guard error text from a rejected attempt, if this is a retry.
    """
    system = SQL_SYSTEM_PROMPT.format(
        vendor='SQLite' if 'sqlite' in settings.DATABASES['default']['ENGINE'] else 'PostgreSQL',
        schema=get_schema_prompt(),
        max_rows=getattr(settings, 'CHAT_MAX_ROWS', 200),
    )
    messages = [{'role': 'system', 'content': system}]
    messages.extend(history)
    messages.append({'role': 'user', 'content': question})

    if repair:
        messages.append({
            'role': 'user',
            'content': (
                f'Query sebelumnya ditolak oleh validator dengan alasan: {repair}\n'
                'Perbaiki query agar hanya menggunakan tabel dan kolom pada SKEMA, '
                'dan tetap balas dalam format JSON yang sama.'
            ),
        })
    return messages


def _clean_history(raw_history):
    """Sanitise client-supplied history into trimmed model messages.

    The browser posts back the visible conversation, so it is treated as
    untrusted input: roles are constrained, content is truncated, and only the
    most recent turns are kept to bound the prompt size.
    """
    if not isinstance(raw_history, list):
        return []

    turns = getattr(settings, 'CHAT_HISTORY_TURNS', 6)
    messages = []
    for item in raw_history[-(turns * 2):]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        content = item.get('content')
        if role not in ('user', 'assistant') or not isinstance(content, str):
            continue
        messages.append({'role': role, 'content': content[:MAX_QUESTION_LENGTH]})
    return messages


@login_required
def chat_index(request):
    """Render the Chat page."""
    context = {
        'ollama_enabled': ollama_client.is_enabled(),
        'ollama_model': getattr(settings, 'OLLAMA_MODEL', ''),
        'ollama_base_url': getattr(settings, 'OLLAMA_BASE_URL', ''),
        'allowed_tables': sorted(ALLOWED_TABLES),
        'max_rows': getattr(settings, 'CHAT_MAX_ROWS', 200),
    }
    return render(request, 'chat/index.html', context)


@login_required
@require_POST
def chat_test_connection(request):
    """Report whether the configured Ollama server and model are reachable."""
    if not ollama_client.is_enabled():
        return JsonResponse({
            'ok': False,
            'message': 'Fitur Chat dinonaktifkan (OLLAMA_ENABLED=False).',
        })
    return JsonResponse(ollama_client.test_connection())


@login_required
@require_POST
def chat_ask(request):
    """Answer a natural-language question using a guarded read-only query.

    Expects a JSON body with ``question`` and an optional ``history`` list.

    Returns:
        JsonResponse: ``{'ok', 'answer', 'sql', 'columns', 'rows',
        'row_count', 'truncated'}``. On failure, ``ok`` is False and
        ``message`` explains why; the HTTP status stays 200 for handled
        errors so the UI can render them as chat replies.
    """
    if not ollama_client.is_enabled():
        return JsonResponse({
            'ok': False,
            'message': 'Fitur Chat dinonaktifkan (OLLAMA_ENABLED=False).',
        })

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'message': 'Format permintaan tidak valid.'}, status=400)

    question = (payload.get('question') or '').strip()
    if not question:
        return JsonResponse({'ok': False, 'message': 'Pertanyaan tidak boleh kosong.'}, status=400)
    if len(question) > MAX_QUESTION_LENGTH:
        return JsonResponse({
            'ok': False,
            'message': f'Pertanyaan terlalu panjang (maksimal {MAX_QUESTION_LENGTH} karakter).',
        }, status=400)

    history = _clean_history(payload.get('history'))

    # --- Step 1: ask the model for SQL, with one repair attempt -------------
    repair = None
    result = None
    explanation = ''
    last_error = None
    sql_messages = None
    sql_reply = ''

    for _ in range(2):
        sql_messages = _build_sql_messages(question, history, repair)
        try:
            raw = ollama_client.chat(sql_messages, json_mode=True)
        except OllamaError as exc:
            return JsonResponse({'ok': False, 'message': str(exc)})
        sql_reply = raw

        parsed = _extract_json(raw)
        if parsed is None:
            last_error = 'Balasan model bukan JSON yang valid.'
            repair = last_error
            continue

        sql = parsed.get('sql')
        if not sql:
            # The model decided no database access is needed (or refused).
            message = parsed.get('message') or 'Pertanyaan ini tidak memerlukan data dari database.'
            return JsonResponse({'ok': True, 'answer': message, 'sql': None})

        explanation = parsed.get('explanation') or ''
        try:
            result = run_readonly_query(sql)
            break
        except SQLGuardError as exc:
            last_error = str(exc)
            repair = last_error
            logger.info('Chat query ditolak untuk user %s: %s', request.user, last_error)

    if result is None:
        return JsonResponse({
            'ok': False,
            'message': f'Tidak dapat menyusun query yang aman untuk pertanyaan ini. {last_error or ""}'.strip(),
        })

    # --- Step 2: let the model phrase an answer from the rows ---------------
    # Only a sample goes to the model: a full 200-row result would overflow
    # the context window and slow every answer down. The browser still gets
    # the complete result set below.
    sample_size = getattr(settings, 'CHAT_MAX_ROWS_TO_MODEL', 30)
    sample = result['rows'][:sample_size]
    # Rows go out as labelled records rather than positional arrays. Small
    # models routinely mismatch a value to the wrong column when given
    # parallel "columns"/"rows" lists, which produced confidently wrong
    # summaries; {"column": value} pairs keep each number attached to its name.
    records = [dict(zip(result['columns'], row)) for row in sample]
    result_payload = json.dumps({
        'rows': records,
        'row_count': result['row_count'],
        'rows_shown_to_model': len(records),
        'truncated': result['truncated'] or len(records) < result['row_count'],
    }, ensure_ascii=False, default=str)

    # Continue the step-1 conversation so its cached prefix stays valid.
    answer_messages = sql_messages + [
        {'role': 'assistant', 'content': sql_reply},
        {'role': 'user', 'content': ANSWER_INSTRUCTION.format(results=result_payload)},
    ]

    try:
        answer = ollama_client.chat(answer_messages)
    except OllamaError as exc:
        # The data is already available — show it even if phrasing failed.
        answer = (
            f'Query berhasil dijalankan ({result["row_count"]} baris), '
            f'tetapi jawaban naratif gagal dibuat: {exc}'
        )

    return JsonResponse({
        'ok': True,
        'answer': answer,
        'sql': result['sql'],
        'explanation': explanation,
        'columns': result['columns'],
        'rows': result['rows'],
        'row_count': result['row_count'],
        'truncated': result['truncated'],
    })
