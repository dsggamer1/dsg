from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base, SchemaVersion


class Database:
    def __init__(self, url):
        self.engine = create_engine(url, pool_pre_ping=True, connect_args={'check_same_thread': False, 'timeout': 30} if url.startswith('sqlite') else {})
        if url.startswith('sqlite'):
            @event.listens_for(self.engine, 'connect')
            def sqlite_settings(conn, _):
                conn.execute('PRAGMA foreign_keys=ON')
                conn.execute('PRAGMA journal_mode=WAL')
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self):
        Base.metadata.create_all(self.engine)
        with self.transaction() as session:
            version = session.get(SchemaVersion, 1)
            if version and version.version != 1:
                raise RuntimeError('Unsupported schema version; use documented migration procedure')
            if not version:
                session.add(SchemaVersion(id=1, version=1))

    @contextmanager
    def transaction(self):
        with self.sessions() as session:
            try:
                # Serialize writes on SQLite. PostgreSQL uses transaction-scoped advisory
                # locking across both bot and web processes to preserve multi-row invariants.
                if self.engine.dialect.name == 'sqlite':
                    session.connection().exec_driver_sql('BEGIN IMMEDIATE')
                elif self.engine.dialect.name == 'postgresql':
                    session.connection().exec_driver_sql('SELECT pg_advisory_xact_lock(740219830)')
                yield session
                session.commit()
            except BaseException:
                session.rollback()
                raise


if __name__ == '__main__':
    from .config import settings
    Database(settings().database_url).initialize()
    print('NEX CODEX schema v1 ready')
