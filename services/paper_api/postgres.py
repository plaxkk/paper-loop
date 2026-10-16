"""Small DB-API adapter; application SQL stays shared with the local SQLite mode."""
from contextlib import contextmanager
import re


class Row(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def fetchone(self):
        value = self.cursor.fetchone()
        return Row(value) if value is not None else None

    def fetchall(self):
        return [Row(value) for value in self.cursor.fetchall()]

    def __iter__(self):
        return (Row(value) for value in self.cursor)


def sql(query):
    query = re.sub(r"date\((created|\?),'unixepoch'\)", r"to_char(to_timestamp(\1) AT TIME ZONE 'UTC','YYYY-MM-DD')", query)
    query = query.replace("json_array_length(pages)", "json_array_length(pages::json)")
    query = query.replace("SET amount=amount+1", "SET amount=quota.amount+1")
    query = query.replace("SET value=value+excluded.value", "SET value=aggregates.value+excluded.value")
    query = re.sub(r"WHERE 1\b", "WHERE true", query)
    return query.replace("?", "%s")


class Database:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, query, values=()):
        return Cursor(self.raw.execute(sql(query), values))


@contextmanager
def connect(settings, write=False):
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.conninfo import conninfo_to_dict
    host = conninfo_to_dict(settings.database_url).get("host", "")
    options = {"sslmode": "require"} if host not in {"localhost", "127.0.0.1", "::1"} else {}
    with psycopg.connect(settings.database_url, connect_timeout=10, prepare_threshold=None, row_factory=dict_row, **options) as raw:
        raw.execute("SET LOCAL search_path TO paper_loop, pg_catalog")
        raw.execute("SET LOCAL statement_timeout = '25s'")
        if write:
            # Preserve atomic quotas, deduplication and worker leases across functions.
            raw.execute("SELECT pg_advisory_xact_lock(79618209)")
        yield Database(raw)
