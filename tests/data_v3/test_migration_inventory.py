"""Every shipped SQL file must be installed in a deterministic order."""

from data_platform.v3.layout import RUNTIME_MIGRATIONS, SQL, sql_files


def test_runtime_inventory_covers_all_sql_without_duplicates():
    names = [path.name for path in sql_files()]
    assert names[0] == "schema.sql"
    assert len(names) == len(set(names))
    assert set(names) == {path.name for path in SQL.glob("*.sql")}
    assert names[1:] == list(RUNTIME_MIGRATIONS)
    assert all(path.is_file() for path in sql_files())
