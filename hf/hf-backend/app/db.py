from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

engine = create_engine(settings.postgres_dsn, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

def ensure_indexes(conn):
    statements = [
        # Speed up common filters
        """CREATE INDEX IF NOT EXISTS ix_models_author_id ON models(author_id);""",
        """CREATE INDEX IF NOT EXISTS ix_models_license ON models(license);""",
        """CREATE INDEX IF NOT EXISTS ix_models_pipeline_tag ON models(pipeline_tag);""",
        """CREATE INDEX IF NOT EXISTS ix_models_downloads ON models(downloads DESC);""",
        """CREATE INDEX IF NOT EXISTS ix_models_likes ON models(likes DESC);""",
        """CREATE INDEX IF NOT EXISTS ix_models_last_modified ON models(last_modified);""",
        # Tags
        """CREATE INDEX IF NOT EXISTS ix_model_tags_tag ON model_tags(tag);""",
        """CREATE INDEX IF NOT EXISTS ix_model_tags_model ON model_tags(model_id);""",
        # Simple trigram-ish ILIKE friendly by splitting (optional if pg_trgm not installed)
        # You can also add a GIN index on jsonb if you query models.raw
    ]
    for ddl in statements:
        conn.execute(text(ddl))
