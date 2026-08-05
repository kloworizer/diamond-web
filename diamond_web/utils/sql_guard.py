"""Read-only SQL guard for the Chat (Ollama) assistant.

The chat assistant lets a local LLM write SQL against the application
database. Nothing the model produces is trusted: every statement passes
through :func:`validate_select` before :func:`run_readonly_query` executes it
on a connection that cannot write.

Four independent layers keep the assistant inside its sandbox:

1. **Single statement, SELECT only** — ``sqlparse`` must see exactly one
   statement and classify it as ``SELECT``. Anything else (INSERT, UPDATE,
   DELETE, DDL, PRAGMA, ATTACH, multi-statement payloads) is rejected.
2. **Identifier allowlist** — every identifier in the query must be an
   allowed table, a column of an allowed table, an alias/CTE declared inside
   the query itself, or a whitelisted function. Unknown identifiers such as
   ``auth_user``, ``password`` or ``sqlite_master`` therefore never pass.
3. **Hard denylist** — credential-bearing names are additionally rejected
   wherever they appear, including in alias position.
4. **Read-only connection** — SQLite is opened with ``mode=ro`` plus
   ``PRAGMA query_only``; other backends run inside a transaction that is
   always rolled back.
"""

import re
import sqlite3
import time
from pathlib import Path

import sqlparse
from sqlparse import tokens as T

from django.conf import settings
from django.db import connection, transaction


class SQLGuardError(Exception):
    """Raised when a statement is not a safe, allowlisted read-only query."""


# ---------------------------------------------------------------------------
# Sandbox definition
# ---------------------------------------------------------------------------

# Business tables the assistant may read. This is the security boundary:
# anything absent here is invisible to the assistant. Authentication tables
# (auth_user, auth_group, auth_user_groups, auth_permission, …), the session
# store and Django's internal bookkeeping tables are deliberately excluded so
# that passwords, permissions and group membership can never be reached.
# Add new *business* tables here when the schema grows.
ALLOWED_TABLES = frozenset({
    'backup_data',
    'bentuk_data',
    'cara_penyampaian',
    'dasar_hukum',
    'detil_tanda_terima',
    'docx_template',
    'durasi_jatuh_tempo',
    'ilap',
    'ilap_kpp',
    'jenis_data_ilap',
    'jenis_prioritas_data',
    'jenis_tabel',
    'kanwil',
    'kategori_ilap',
    'kategori_wilayah',
    'kirim_pide_temp',
    'klasifikasi_jenis_data',
    'kpp',
    'media_backup',
    'periode_jenis_data',
    'periode_pengiriman',
    'pic',
    'sequence_tanda_terima',
    'status_data',
    'status_penelitian',
    'tanda_terima_data',
    'tiket',
    'tiket_action',
    'tiket_pic',
})

# Names that must never appear in a query, in any position. The allowlist in
# layer 2 already blocks these; this is a second, independent net that also
# covers alias position and any tokenizer quirk.
DENIED_IDENTIFIERS = frozenset({
    'auth_user',
    'auth_group',
    'auth_permission',
    'auth_group_permissions',
    'auth_user_groups',
    'auth_user_user_permissions',
    'django_session',
    'django_admin_log',
    'django_content_type',
    'django_migrations',
    'sqlite_master',
    'sqlite_schema',
    'sqlite_temp_master',
    'sqlite_sequence',
    'pg_catalog',
    'pg_shadow',
    'pg_authid',
    'pg_user',
    'information_schema',
    # Credential-bearing / privilege columns.
    'password',
    'session_data',
    'session_key',
    'is_superuser',
    'is_staff',
    'user_permissions',
    # SQLite functions that touch the filesystem or extend the engine.
    'load_extension',
    'readfile',
    'writefile',
    'edit',
    'fts3_tokenizer',
})

# Statement-level keywords that have no place in a read-only query. Layer 1
# already rejects non-SELECT statements, but SQLite accepts some of these in
# expression position, so they are refused explicitly.
DENIED_KEYWORDS = frozenset({
    'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'MERGE', 'UPSERT',
    'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME',
    'GRANT', 'REVOKE', 'ATTACH', 'DETACH', 'PRAGMA', 'VACUUM', 'REINDEX',
    'BEGIN', 'COMMIT', 'ROLLBACK', 'SAVEPOINT', 'RELEASE',
    'COPY', 'CALL', 'EXEC', 'EXECUTE', 'DO', 'SET', 'RETURNING', 'INTO',
})

# Functions the assistant may call. Anything else is an unknown identifier.
ALLOWED_FUNCTIONS = frozenset({
    'abs', 'avg', 'cast', 'ceil', 'ceiling', 'char_length', 'coalesce',
    'concat', 'count', 'date', 'datetime', 'date_part', 'date_trunc', 'extract',
    'floor', 'group_concat', 'ifnull', 'iif', 'instr', 'julianday', 'length',
    'lower', 'ltrim', 'max', 'min', 'nullif', 'now', 'printf', 'random',
    'replace', 'round', 'rtrim', 'strftime', 'string_agg', 'substr',
    'substring', 'sum', 'time', 'to_char', 'trim', 'typeof', 'unicode',
    'upper', 'row_number', 'rank', 'dense_rank', 'lag', 'lead',
})

# Identifier characters sqlparse hands back with their quoting still attached.
_QUOTE_CHARS = '"`[]'

# Matches ``WITH name AS (`` and ``, name AS (`` so common table expressions
# can be treated as locally declared names.
_CTE_RE = re.compile(r'(?:\bWITH\b|,)\s+([A-Za-z_][\w$]*)\s+AS\s*\(', re.IGNORECASE)

_MAX_SQL_LENGTH = 4000

_schema_cache = None


def _normalize_identifier(value):
    """Strip quoting from a raw identifier token and lower-case it."""
    return value.strip(_QUOTE_CHARS).strip("'").lower()


def _is_identifier_token(token):
    """Return True when ``token`` carries an identifier name.

    Double-quoted identifiers are tokenized as ``String.Symbol`` rather than
    ``Name``, so both are treated as identifiers.
    """
    return token.ttype in T.Name or token.ttype is T.String.Symbol


def get_schema():
    """Return ``{table: [column, ...]}`` for every allowed table.

    The schema is introspected from the live database (so it never drifts from
    the real columns) and cached for the lifetime of the process.
    """
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    schema = {}
    with connection.cursor() as cursor:
        existing = set(connection.introspection.table_names(cursor))
        for table in sorted(ALLOWED_TABLES & existing):
            description = connection.introspection.get_table_description(cursor, table)
            schema[table] = [col.name for col in description]

    _schema_cache = schema
    return schema


def get_schema_prompt():
    """Render the allowed schema as compact ``table(col, col, …)`` lines.

    This is what the model is shown; tables outside the allowlist are simply
    never mentioned, so the model has no reason to reference them.
    """
    return '\n'.join(
        f'{table}({", ".join(columns)})'
        for table, columns in get_schema().items()
    )


def _allowed_vocabulary():
    """Return the set of identifiers that are legal anywhere in a query."""
    schema = get_schema()
    vocabulary = set(schema)
    for columns in schema.values():
        vocabulary.update(col.lower() for col in columns)
    vocabulary |= ALLOWED_FUNCTIONS
    return vocabulary


def _collect_local_names(tokens):
    """Return names the query declares itself: table aliases and CTE names.

    An alias is an identifier that directly follows another identifier
    (``FROM tiket t``) or the ``AS`` keyword (``COUNT(*) AS jml``). Such names
    are local to the query and cannot reference a table, so they are exempt
    from the allowlist check.
    """
    local = set()
    previous = None
    for token in tokens:
        if _is_identifier_token(token):
            follows_identifier = previous is not None and _is_identifier_token(previous)
            follows_as = (
                previous is not None
                and previous.ttype in T.Keyword
                and previous.value.upper() == 'AS'
            )
            if follows_identifier or follows_as:
                local.add(_normalize_identifier(token.value))
        previous = token
    return local


def _significant_tokens(statement):
    """Flatten a statement, dropping whitespace and comments."""
    return [
        token for token in statement.flatten()
        if not token.is_whitespace and token.ttype not in T.Comment
    ]


def validate_select(sql):
    """Validate ``sql`` as a safe, read-only, allowlisted SELECT.

    Args:
        sql: Raw SQL text, typically produced by the language model.

    Returns:
        str: The statement stripped of trailing whitespace and semicolon,
        ready to execute.

    Raises:
        SQLGuardError: If the statement is empty, is not a single SELECT,
            uses a forbidden keyword, or references any identifier outside
            the allowed schema.
    """
    if not sql or not sql.strip():
        raise SQLGuardError('Query kosong.')

    if len(sql) > _MAX_SQL_LENGTH:
        raise SQLGuardError(
            f'Query terlalu panjang (maksimal {_MAX_SQL_LENGTH} karakter).'
        )

    cleaned = sqlparse.format(sql, strip_comments=True).strip().rstrip(';').strip()
    if not cleaned:
        raise SQLGuardError('Query kosong setelah komentar dihapus.')

    statements = [s for s in sqlparse.parse(cleaned) if str(s).strip()]
    if len(statements) != 1:
        raise SQLGuardError(
            'Hanya satu perintah SELECT yang diizinkan per query.'
        )

    statement = statements[0]
    if statement.get_type() != 'SELECT':
        raise SQLGuardError(
            'Hanya perintah SELECT yang diizinkan — query ini akan mengubah '
            'atau membaca data di luar izin.'
        )

    tokens = _significant_tokens(statement)
    local_names = _collect_local_names(tokens)
    local_names |= {name.lower() for name in _CTE_RE.findall(cleaned)}
    vocabulary = _allowed_vocabulary() | local_names

    for token in tokens:
        if token.ttype is T.Name.Placeholder:
            raise SQLGuardError('Parameter/placeholder tidak diizinkan.')

        if token.ttype in T.Keyword and token.value.upper() in DENIED_KEYWORDS:
            raise SQLGuardError(
                f'Kata kunci "{token.value.upper()}" tidak diizinkan — '
                'chatbot hanya boleh membaca data.'
            )

        if not _is_identifier_token(token):
            continue

        name = _normalize_identifier(token.value)
        if name in DENIED_IDENTIFIERS:
            raise SQLGuardError(
                f'Akses ke "{name}" ditolak — data kredensial dan hak akses '
                'pengguna tidak dapat dibaca oleh chatbot.'
            )
        if name not in vocabulary:
            raise SQLGuardError(
                f'Identifier "{name}" tidak dikenal atau berada di luar tabel '
                'yang diizinkan.'
            )

    return cleaned


def _run_sqlite_readonly(sql, max_rows, timeout):
    """Execute ``sql`` on a second SQLite connection opened read-only.

    Returns ``None`` when the database cannot be opened this way (in-memory
    test databases, for example) so the caller can fall back.
    """
    name = str(settings.DATABASES['default']['NAME'])
    if ':memory:' in name or name.startswith('file:'):
        return None

    path = Path(name)
    if not path.exists():
        return None

    uri = f'file:{path.as_posix()}?mode=ro'
    conn = sqlite3.connect(uri, uri=True, timeout=timeout)
    try:
        conn.execute('PRAGMA query_only = ON')

        # Abort the query if it outruns the budget; the handler is polled
        # every N virtual-machine instructions and a non-zero return aborts.
        deadline = time.monotonic() + timeout
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)

        cursor = conn.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        rows = cursor.fetchmany(max_rows + 1)
        return columns, rows
    finally:
        conn.close()


def _run_via_django(sql, max_rows):
    """Execute ``sql`` on the Django connection inside a rolled-back transaction.

    Used for non-SQLite backends and for test databases that cannot be
    reopened read-only. The statement has already been validated as a SELECT,
    and the transaction is discarded regardless of outcome.
    """
    with transaction.atomic():
        try:
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute(sql)
                columns = [d[0] for d in cursor.description or []]
                rows = cursor.fetchmany(max_rows + 1)
            return columns, rows
        finally:
            transaction.set_rollback(True)


def run_readonly_query(sql, max_rows=None, timeout=None):
    """Validate and execute ``sql``, returning at most ``max_rows`` rows.

    Args:
        sql: Raw SQL from the model. Re-validated here, so callers cannot
            skip :func:`validate_select` by accident.
        max_rows: Row cap. Defaults to ``settings.CHAT_MAX_ROWS``.
        timeout: Seconds the query may run. Defaults to
            ``settings.CHAT_QUERY_TIMEOUT``.

    Returns:
        dict: ``{'sql', 'columns', 'rows', 'row_count', 'truncated'}`` where
        ``rows`` is a list of lists and ``truncated`` says whether the result
        was cut off at ``max_rows``.

    Raises:
        SQLGuardError: If validation fails or the database rejects the query.
    """
    max_rows = max_rows or getattr(settings, 'CHAT_MAX_ROWS', 200)
    timeout = timeout or getattr(settings, 'CHAT_QUERY_TIMEOUT', 15)

    safe_sql = validate_select(sql)

    try:
        result = None
        if connection.vendor == 'sqlite':
            result = _run_sqlite_readonly(safe_sql, max_rows, timeout)
        if result is None:
            result = _run_via_django(safe_sql, max_rows)
        columns, rows = result
    except sqlite3.Error as exc:
        raise SQLGuardError(f'Query gagal dijalankan: {exc}') from exc
    except Exception as exc:  # database errors vary by backend
        raise SQLGuardError(f'Query gagal dijalankan: {exc}') from exc

    truncated = len(rows) > max_rows
    rows = rows[:max_rows]

    return {
        'sql': safe_sql,
        'columns': columns,
        'rows': [[_to_display(value) for value in row] for row in rows],
        'row_count': len(rows),
        'truncated': truncated,
    }


def _to_display(value):
    """Coerce a database value into something JSON-serialisable."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return '<binary>'
    return str(value)
