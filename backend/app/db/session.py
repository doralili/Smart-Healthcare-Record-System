from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql.psycopg2 import PGDialect_psycopg2
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings


def _open_gauss_server_version_info(self, connection):
    return (9, 2)


PGDialect_psycopg2._get_server_version_info = _open_gauss_server_version_info

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
