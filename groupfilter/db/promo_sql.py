import threading
from sqlalchemy import create_engine
from sqlalchemy import Column, TEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.pool import StaticPool
from groupfilter import DB_URL


BASE = declarative_base()


class Promos(BASE):
    __tablename__ = "promos"
    link = Column(TEXT, primary_key=True)
    text = Column(TEXT)

    def __init__(self, link, text):
        self.link = link
        self.text = text


def start() -> scoped_session:
    engine = create_engine(DB_URL, client_encoding="utf8", poolclass=StaticPool)
    BASE.metadata.bind = engine
    BASE.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()
INSERTION_LOCK = threading.RLock()


async def add_promo(link, text):
    with INSERTION_LOCK:
        try:
            promo = SESSION.query(Promos).filter(Promos.link.ilike(link)).one()
        except NoResultFound:
            promo = Promos(link=link, text=text)
            SESSION.add(promo)
            SESSION.commit()
            return True


async def del_promo(link):
    with INSERTION_LOCK:
        try:
            promo = SESSION.query(Promos).filter(Promos.link.ilike(link)).one()
            SESSION.delete(promo)
            SESSION.commit()
            return True
        except NoResultFound:
            return False


async def get_promos():
    with INSERTION_LOCK:
        try:
            promos = SESSION.query(Promos).all()
            ads_list = [{"btn_txt": promo.text, "link": promo.link} for promo in promos]
            return ads_list
        except NoResultFound:
            return None
