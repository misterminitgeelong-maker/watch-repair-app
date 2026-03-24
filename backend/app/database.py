from sqlmodel import Session, SQLModel, create_engine

from .config import settings


def _normalize_database_url(raw_url: str) -> str:
    # Force SQLAlchemy to use psycopg v3 for generic postgres URLs.
    if raw_url.startswith("postgresql+psycopg2://"):
        return raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+psycopg://", 1)
    if raw_url.startswith("postgresql://") and "+" not in raw_url.split("://", 1)[0]:
        return raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw_url


database_url = _normalize_database_url(settings.database_url)

_connect_args = {}
if database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(database_url, echo=False, connect_args=_connect_args)


def create_db_and_tables() -> None:
    """
    Explicit helper for local/test bootstrapping only.
    Production schema changes are managed via Alembic migrations.
    """
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
