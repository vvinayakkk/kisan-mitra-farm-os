"""Read-only, table-by-table parity check after a PostgreSQL restore."""

import os
from dataclasses import dataclass

import psycopg2
from psycopg2 import sql


@dataclass(frozen=True)
class Signature:
    count: int = 0
    xor: int = 0
    total: int = 0

    def add(self, digest: str) -> "Signature":
        value = int(digest, 16)
        return Signature(self.count + 1, self.xor ^ value, (self.total + value) % (1 << 128))


def tables(connection):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='sv3' AND c.relkind IN ('r','p')
              AND NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid=c.oid)
            ORDER BY c.relname
        """)
        return [row[0] for row in cursor]


def signature(connection, table):
    result = Signature()
    with connection.cursor(name="verify_" + table) as cursor:
        cursor.itersize = 10000
        cursor.execute(sql.SQL("SELECT md5(to_jsonb(t)::text) FROM {} t").format(sql.Identifier("sv3", table)))
        for row in cursor:
            result = result.add(row[0])
    return result


def verify(source_url, target_url):
    if not source_url or not target_url or source_url == target_url:
        raise ValueError("Distinct source and target PostgreSQL URLs are required")
    with psycopg2.connect(source_url) as source, psycopg2.connect(target_url) as target:
        for connection in (source, target):
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cursor.execute("SET TIME ZONE 'UTC'")
        source_tables, target_tables = tables(source), tables(target)
        if source_tables != target_tables:
            missing = sorted(set(source_tables) - set(target_tables))
            extra = sorted(set(target_tables) - set(source_tables))
            raise RuntimeError(f"Table inventory differs: missing={missing}, extra={extra}")
        failures = []
        for table in source_tables:
            before, after = signature(source, table), signature(target, table)
            print(f"{table}: {before.count} → {after.count}")
            if before != after:
                failures.append(table)
        if failures:
            raise RuntimeError("Row parity failed for: " + ", ".join(failures))
        print(f"Verified {len(source_tables)} tables with matching row counts and row-content signatures")


if __name__ == "__main__":
    verify(os.getenv("V3_SOURCE_DATABASE_URL"), os.getenv("V3_TARGET_DATABASE_URL"))
