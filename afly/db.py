"""SQLite persistence: every signup attempt and resulting account."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, create_engine, func, select
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Signup(Base):
    __tablename__ = "signups"
    id = Column(Integer, primary_key=True)
    target_id = Column(String(64), index=True, nullable=False)
    status = Column(String(32), index=True, nullable=False)  # pending|ok|failed|verified
    email = Column(String(255))
    username = Column(String(255))
    password = Column(String(255))
    proxy = Column(String(255))
    user_agent = Column(Text)
    note = Column(Text)
    payout_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, server_default=func.now())
    verified_at = Column(DateTime, nullable=True)


class DB:
    def __init__(self, path: str = "data/afly.sqlite3"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    def record(self, **kwargs) -> Signup:
        with self.Session() as s:
            row = Signup(**kwargs)
            s.add(row)
            s.commit()
            s.refresh(row)
            return row

    def update(self, sid: int, **kwargs) -> None:
        with self.Session() as s:
            row = s.get(Signup, sid)
            if not row:
                return
            for k, v in kwargs.items():
                setattr(row, k, v)
            if kwargs.get("status") == "verified":
                row.verified_at = dt.datetime.utcnow()
            s.commit()

    def count_today(self, target_id: str) -> int:
        start = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        with self.Session() as s:
            stmt = select(func.count(Signup.id)).where(
                Signup.target_id == target_id, Signup.created_at >= start
            )
            return int(s.execute(stmt).scalar_one())

    def last_attempt(self, target_id: str) -> Optional[dt.datetime]:
        with self.Session() as s:
            stmt = (
                select(Signup.created_at)
                .where(Signup.target_id == target_id)
                .order_by(Signup.created_at.desc())
                .limit(1)
            )
            res = s.execute(stmt).scalar_one_or_none()
            return res

    def totals(self):
        with self.Session() as s:
            stmt = select(
                Signup.target_id,
                func.count(Signup.id),
                func.sum(Signup.payout_usd),
            ).group_by(Signup.target_id)
            return s.execute(stmt).all()
