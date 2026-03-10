from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import inspect, text

from .config import settings

_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, echo=False, connect_args=_connect_args)


def _ensure_runtime_columns() -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    if "repairjob" not in table_names:
        return

    columns = {col["name"] for col in inspector.get_columns("repairjob")}
    if "cost_cents" in columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE repairjob ADD COLUMN cost_cents INTEGER NOT NULL DEFAULT 0"))


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_runtime_columns()


def get_session():
    with Session(engine) as session:
        yield session
