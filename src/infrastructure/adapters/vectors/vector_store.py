# src/infrastructure/adapters/vectors/vector_database_context.py


import lancedb


class VectorDatabaseContext:
    def __init__(self, settings: Settings):
        self.settings = settings
        # Engine for DB
        self.db_uri = str(settings.lance_db_path)
        # Engine for Vectors

    async def get_connection(self):

        return await lancedb.connect(str(self.db_uri))
