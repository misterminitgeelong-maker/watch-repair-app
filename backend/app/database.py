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

    with engine.begin() as conn:
        if "repairjob" in table_names:
            repairjob_columns = {col["name"] for col in inspector.get_columns("repairjob")}
            if "cost_cents" not in repairjob_columns:
                conn.execute(text("ALTER TABLE repairjob ADD COLUMN cost_cents INTEGER NOT NULL DEFAULT 0"))
            if "pre_quote_cents" not in repairjob_columns:
                conn.execute(text("ALTER TABLE repairjob ADD COLUMN pre_quote_cents INTEGER NOT NULL DEFAULT 0"))
            if "status_token" not in repairjob_columns:
                conn.execute(text("ALTER TABLE repairjob ADD COLUMN status_token TEXT"))
                conn.execute(text("UPDATE repairjob SET status_token = id WHERE status_token IS NULL OR status_token = ''"))

        if "customer" in table_names:
            customer_columns = {col["name"] for col in inspector.get_columns("customer")}
            if "address" not in customer_columns:
                conn.execute(text("ALTER TABLE customer ADD COLUMN address TEXT"))
            if "notes" not in customer_columns:
                conn.execute(text("ALTER TABLE customer ADD COLUMN notes TEXT"))


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_runtime_columns()


def get_session():
    with Session(engine) as session:
        yield session
