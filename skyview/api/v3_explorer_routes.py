"""Read-only classic explorer compatibility: authenticated owned rows, no SQL console."""

import math

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from skyview.api.v3_routes import Owner
from skyview.data.v3 import db

router = APIRouter(prefix="/admin", tags=["Owned farm data explorer"])
TABLES = (
    "farms",
    "plots",
    "crop_cycles",
    "tasks",
    "expenses",
    "resources",
    "stations",
    "soil_samples",
    "soil_indicators",
    "farm_operations",
    "disease_cases",
)


def _identifier(value):

    return '"' + value.replace('"', '""') + '"'


def _columns(conn, table):
    return [
        dict(row)
        for row in conn.execute(
            text("""SELECT a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type,
      NOT a.attnotnull AS nullable,pg_get_expr(ad.adbin,ad.adrelid) AS default,
      coalesce(a.attnum=ANY(i.indkey),false) AS primary_key
      FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class c ON c.oid=a.attrelid
      JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
      LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid=c.oid AND ad.adnum=a.attnum
      LEFT JOIN pg_catalog.pg_index i ON i.indrelid=c.oid AND i.indisprimary
      WHERE n.nspname='sv3' AND c.relname=:table AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum"""),
            {"table": table},
        ).mappings()
    ]


@router.get("/tables")
def tables(owner: Owner):
    with db.connection(owner) as conn:
        records = []
        for table in TABLES:
            columns = _columns(conn, table)
            count = conn.execute(
                text(f"SELECT count(*) FROM sv3.{_identifier(table)}")
            ).scalar_one()
            records.append(
                {
                    "name": table,
                    "row_count": count,
                    "columns": columns,
                    "primary_key": [c["name"] for c in columns if c["primary_key"]],
                    "sample_columns": [c["name"] for c in columns[:5]],
                }
            )
    return {"tables": records, "scope": "authenticated farmer only", "read_only": True}


@router.get("/tables/{table}")
def table_records(
    table: str,
    owner: Owner,
    page: int = Query(1, ge=1, le=1000000),
    page_size: int = Query(50, ge=1, le=200),
    desc: bool = False,
    order_by: str | None = None,
    search: str | None = Query(None, max_length=200),
    filter_column: str | None = None,
    filter_value: str | None = Query(None, max_length=500),
):
    if table not in TABLES:
        raise HTTPException(404, "Table is not available in the owned farm explorer")
    with db.connection(owner) as conn:
        columns = _columns(conn, table)
        names = {column["name"] for column in columns}
        if order_by is not None and order_by not in names:
            raise HTTPException(400, "Unknown sorting column")
        if filter_column is not None and filter_column not in names:
            raise HTTPException(400, "Unknown filter column")
        if (filter_column is None) != (filter_value is None):
            raise HTTPException(400, "Filter column and value are required together")
        clauses = []
        params = {}
        if filter_column is not None:
            clauses.append(f"CAST({_identifier(filter_column)} AS text)=:filter_value")
            params["filter_value"] = filter_value
        if search:
            escaped = (
                search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            clauses.append(
                "("
                + " OR ".join(
                    f"CAST({_identifier(name)} AS text) ILIKE :search ESCAPE E'\\\\'"
                    for name in sorted(names)
                )
                + ")"
            )
            params["search"] = "%" + escaped + "%"
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        relation = "sv3." + _identifier(table)
        total = conn.execute(
            text(f"SELECT count(*) FROM {relation}{where}"), params
        ).scalar_one()
        primary = [column["name"] for column in columns if column["primary_key"]]
        sorting = [order_by] if order_by else primary or [columns[0]["name"]]
        sorting.extend(name for name in primary if name not in sorting)
        order = ", ".join(
            _identifier(name) + (" DESC" if desc else " ASC") + " NULLS LAST"
            for name in sorting
        )
        data = (
            conn.execute(
                text(
                    f"SELECT * FROM {relation}{where} ORDER BY {order} LIMIT :limit OFFSET :offset"
                ),
                {**params, "limit": page_size, "offset": (page - 1) * page_size},
            )
            .mappings()
            .all()
        )
    return {
        "table": table,
        "columns": columns,
        "records": [dict(row) for row in data],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_rows": total,
            "total_pages": max(1, math.ceil(total / page_size)),
        },
        "filters": {
            "search": search,
            "filter_column": filter_column,
            "filter_value": filter_value,
            "order_by": order_by,
            "desc": desc,
        },
        "scope": "authenticated farmer only",
        "read_only": True,
    }
