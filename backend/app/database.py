from sqlalchemy import text
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


def _ensure_performance_indexes() -> None:
    # Cross-database (SQLite/Postgres) indexes for high-frequency tenant filters and sorts.
    index_statements = [
        # Repair jobs
        "CREATE INDEX IF NOT EXISTS idx_repairjob_tenant_created ON repairjob (tenant_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_repairjob_tenant_status_created ON repairjob (tenant_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_repairjob_tenant_customer_account_status ON repairjob (tenant_id, customer_account_id, status)",
        # Shoe jobs
        "CREATE INDEX IF NOT EXISTS idx_shoerepairjob_tenant_created ON shoerepairjob (tenant_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_shoerepairjob_tenant_status_created ON shoerepairjob (tenant_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_shoerepairjob_tenant_customer_account_status ON shoerepairjob (tenant_id, customer_account_id, status)",
        # Auto key jobs
        "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_scheduled_created ON autokeyjob (tenant_id, scheduled_at, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_status_scheduled ON autokeyjob (tenant_id, status, scheduled_at)",
        "CREATE INDEX IF NOT EXISTS idx_autokeyjob_tenant_assigned_scheduled ON autokeyjob (tenant_id, assigned_user_id, scheduled_at)",
        # Quotes / invoices / payments
        "CREATE INDEX IF NOT EXISTS idx_quote_tenant_status_sent ON quote (tenant_id, status, sent_at)",
        "CREATE INDEX IF NOT EXISTS idx_invoice_tenant_status_created ON invoice (tenant_id, status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_payment_tenant_status_created ON payment (tenant_id, status, created_at DESC)",
        # Tenant/inbox activity
        "CREATE INDEX IF NOT EXISTS idx_tenanteventlog_tenant_type_created ON tenanteventlog (tenant_id, event_type, created_at DESC)",
        # Customer account billing
        "CREATE INDEX IF NOT EXISTS idx_customeraccountmembership_tenant_account_created ON customeraccountmembership (tenant_id, customer_account_id, created_at)",
        "CREATE INDEX IF NOT EXISTS idx_customeraccountinvoice_tenant_account_created ON customeraccountinvoice (tenant_id, customer_account_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_customeraccountinvoiceline_tenant_invoice_created ON customeraccountinvoiceline (tenant_id, customer_account_invoice_id, created_at)",
    ]
    with engine.begin() as conn:
        for stmt in index_statements:
            conn.execute(text(stmt))


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)
    _ensure_performance_indexes()


def get_session():
    with Session(engine) as session:
        yield session
