"""One inventory for the v3 schema, runtime SQL, and curated inputs."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
SQL = ROOT / "sql"
CATALOG = ROOT / "catalog"

RUNTIME_MIGRATIONS = (
    "roles.sql",
    "roles-runtime.sql",
    "assistant-runtime.sql",
    "application-runtime.sql",
    "onboarding-runtime.sql",
    "workflows-runtime.sql",
    "shared-work-runtime.sql",
    "exchange-runtime.sql",
    "companion-runtime.sql",
    "companion-plans-runtime.sql",
    "support-folder-runtime.sql",
    "whatsapp-runtime.sql",
    "market-read-runtime.sql",
    "station-read-runtime.sql",
)


def sql_files():
    """Return ordered, executable SQL paths for a fresh v3 database."""
    return (SQL / "schema.sql", *(SQL / name for name in RUNTIME_MIGRATIONS))
