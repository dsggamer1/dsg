from contextlib import contextmanager
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker
from .models import Base, SchemaVersion, uid


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
        # Reject future schema versions before changing anything.
        if inspect(self.engine).has_table('schema_version'):
            with self.engine.connect() as conn:
                version=conn.execute(text('SELECT version FROM schema_version WHERE id=1')).scalar()
                if version not in (None,1,2):
                    raise RuntimeError('Unsupported schema version')
        Base.metadata.create_all(self.engine)
        with self.transaction() as session:
            if 'code' not in {c['name'] for c in inspect(session.connection()).get_columns('products')}:
                session.execute(text('ALTER TABLE products ADD COLUMN code VARCHAR(16)'))
            rows=session.execute(text('SELECT id, guild_id, code FROM products')).all()
            used={(row.guild_id,row.code) for row in rows if row.code}
            for row in rows:
                if row.code:
                    continue
                code=uid()[:8]
                while (row.guild_id,code) in used:
                    code=uid()[:8]
                used.add((row.guild_id,code))
                session.execute(text('UPDATE products SET code=:code WHERE id=:id'),{'code':code,'id':row.id})
            session.execute(text("UPDATE products SET category='bot' WHERE category='source'"))
            session.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_product_guild_code ON products (guild_id, code)'))
            version=session.get(SchemaVersion,1)
            if not version:
                session.add(SchemaVersion(id=1,version=2))
            else:
                version.version=2

    @contextmanager
    def transaction(self):
        with self.sessions() as session:
            try:
                # Serialize writes on SQLite. PostgreSQL uses transaction-scoped advisory
                # locking across concurrent bot operations to preserve multi-row invariants.
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
    print('NEX CODEX schema v2 ready')
