# src/api/dependencies.py
from src.core.config import get_settings
from src.infrastructure.adapters.mariadb.database_context import DatabaseContext

settings = get_settings()

# Unified Relational Context
_db_context = DatabaseContext(str(settings.mariadb_url))


def get_db_context() -> DatabaseContext:
    """Dependency provider for the MariaDB unit of work."""
    return _db_context
