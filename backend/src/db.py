import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
_url=os.environ['DATABASE_URL']
_extra={} if _url.startswith('sqlite') else {'isolation_level':'READ COMMITTED'}
engine = create_engine(_url, pool_pre_ping=True,**_extra)
Session = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
def db_session():
    with Session() as s:
        yield s
