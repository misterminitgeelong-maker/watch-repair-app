from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import inspect, text

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


def _ensure_runtime_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "repairjob" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("repairjob")}
    with engine.begin() as conn:
        if "cost_cents" not in columns:
            conn.execute(text("ALTER TABLE repairjob ADD COLUMN cost_cents INTEGER NOT NULL DEFAULT 0"))
        if "pre_quote_cents" not in columns:
            conn.execute(text("ALTER TABLE repairjob ADD COLUMN pre_quote_cents INTEGER NOT NULL DEFAULT 0"))
        if "status_token" not in columns:
            conn.execute(text("ALTER TABLE repairjob ADD COLUMN status_token TEXT"))
            conn.execute(text("UPDATE repairjob SET status_token = id WHERE status_token IS NULL OR status_token = ''"))


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_runtime_columns()


def get_session():
    with Session(engine) as session:
        yield session
