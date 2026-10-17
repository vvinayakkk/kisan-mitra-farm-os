import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

import psycopg2
from psycopg2.extras import execute_batch

from skyview.data import object_storage


def migrate(database_url, assistant_root, raw_root):
    if not object_storage.enabled():
        raise ValueError("ASSISTANT_S3_BUCKET is required")
    roots = {
        "artifacts": (Path(assistant_root), "assistant"),
        "attachments": (Path(assistant_root), "assistant"),
        "raw_objects": (Path(raw_root), "raw"),
    }
    with psycopg2.connect(database_url) as connection:
        with connection.cursor() as cursor:
            candidates = []
            missing = {}
            for table, (root, namespace) in roots.items():
                cursor.execute(f"SELECT id,object_uri FROM sv3.{table}")
                missing[table] = 0
                for identifier, value in cursor:
                    if not value or value.startswith("s3://"):
                        continue
                    parsed = urlparse(value)
                    if parsed.scheme == "demo":
                        missing[table] += 1
                        continue
                    path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(value)
                    if not path.is_relative_to(root.resolve()):
                        raise ValueError(f"Unexpected {table} asset path")
                    if not path.is_file():
                        missing[table] += 1
                        continue
                    candidates.append((table, identifier, path, root, namespace))

            def upload(item):
                table, identifier, path, root, namespace = item
                return table, identifier, object_storage.put(path, root, namespace)

            with ThreadPoolExecutor(max_workers=8) as pool:
                uploaded = list(pool.map(upload, candidates))
            for table in roots:
                records = [(uri, identifier) for name, identifier, uri in uploaded if name == table]
                if records:
                    execute_batch(
                        cursor,
                        f"UPDATE sv3.{table} SET object_uri=%s WHERE id=%s",
                        records,
                        page_size=100,
                    )
                print(f"{table}: {len(records)} copied, {missing[table]} source files unavailable")


if __name__ == "__main__":
    migrate(
        os.environ["V3_DATABASE_URL"],
        os.environ["ASSISTANT_STORAGE_DIR"],
        os.environ["V3_RAW_STORAGE_DIR"],
    )
