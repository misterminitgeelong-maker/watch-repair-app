"""Shared helpers for paginated list endpoints."""
from fastapi import Response
from sqlmodel import Session, func, select

TOTAL_COUNT_HEADER = "X-Total-Count"


def query_total(session: Session, query) -> int:
    return int(session.exec(select(func.count()).select_from(query.subquery())).one())


def set_total_count(response: Response, total: int) -> None:
    response.headers[TOTAL_COUNT_HEADER] = str(int(total))
