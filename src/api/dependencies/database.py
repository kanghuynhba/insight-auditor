from src.domain.config import get_settings
from src.store._sql import DatabaseContext

settings = get_settings()

_db_context = DatabaseContext(str(settings.mariadb_url))


def get_db_context() -> DatabaseContext:
    return _db_context
