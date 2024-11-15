from sqlalchemy import create_engine
from sqlalchemy import Column, TEXT, BigInteger, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.pool import StaticPool
from groupfilter import DB_URL, LOGGER
import asyncio


BASE = declarative_base()


class FsubReq(BASE):
    __tablename__ = "fsubreq"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    chat_id = Column(Numeric)
    fileid = Column(TEXT)

    def __init__(self, user_id, chat_id, fileid):
        self.user_id = user_id
        self.chat_id = chat_id
        self.fileid = fileid


class FsubReg(BASE):
    __tablename__ = "fsubreg"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    chat_id = Column(Numeric)
    fileid = Column(TEXT)

    def __init__(self, user_id, chat_id, fileid):
        self.user_id = user_id
        self.chat_id = chat_id
        self.fileid = fileid


def start() -> scoped_session:
    engine = create_engine(DB_URL, client_encoding="utf8", poolclass=StaticPool)
    BASE.metadata.bind = engine
    BASE.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()
INSERTION_LOCK = asyncio.Lock()


async def add_fsub_req_user(user_id, chat_id, fileid):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                session.query(FsubReq)
                .filter(FsubReq.user_id == user_id, FsubReq.chat_id == chat_id)
                .one()
            )
            fltr.fileid = fileid
            session.commit()
            return True
        except NoResultFound:
            fltr = FsubReq(user_id=user_id, chat_id=chat_id, fileid=fileid)
            session.add(fltr)
            session.commit()
            return True


async def is_req_user(user_id, chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                session.query(FsubReq).filter_by(user_id=user_id, chat_id=chat_id).one()
            )
            return fltr
        except NoResultFound:
            return False


async def rem_fsub_req_file(user_id, chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                session.query(FsubReq)
                .filter(FsubReq.user_id == user_id, FsubReq.chat_id == chat_id)
                .one()
            )
            fltr.fileid = None
            session.commit()
            return True
        except NoResultFound:
            LOGGER.warning("File to delete not found: %s", str(user_id))
            return False


async def remove_fsub_users():
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            session.query(FsubReq).delete()
            session.commit()
            session.query(FsubReg).delete()
            session.commit()
            LOGGER.warning("Removed all fsub users")
            return True
        except Exception as e:
            session.rollback()
            LOGGER.warning("Error removing fsub users: %s", str(e))
            return False
        finally:
            session.close()


async def delete_group_req_id(chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            result = session.query(FsubReq).filter(FsubReq.chat_id == chat_id).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            LOGGER.warning(
                "Error occurred while deleting user requests of chat: %s", str(e)
            )
            return False


async def add_fsub_reg_user(user_id, chat_id, fileid):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                SESSION.query(FsubReg)
                .filter(FsubReg.user_id == user_id, FsubReg.chat_id == chat_id)
                .one()
            )
            fltr.fileid = fileid
            session.commit()
            return True
        except NoResultFound:
            fltr = FsubReg(user_id=user_id, chat_id=chat_id, fileid=fileid)
            session.add(fltr)
            session.commit()
            return True


async def is_reg_user(user_id, chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                session.query(FsubReg)
                .filter(FsubReg.user_id == user_id, FsubReg.chat_id == chat_id)
                .one()
            )
            return fltr
        except NoResultFound:
            return False


async def rem_fsub_reg_file(user_id, chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                session.query(FsubReg)
                .filter(FsubReg.user_id == user_id, FsubReg.chat_id == chat_id)
                .one()
            )
            fltr.fileid = None
            session.commit()
            return True
        except NoResultFound:
            LOGGER.warning("File to delete not found: %s", str(user_id))
            return False


async def delete_fsub_reg_id(user_id, chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            result = (
                session.query(FsubReg)
                .filter(FsubReg.user_id == user_id, FsubReg.chat_id == chat_id)
                .delete()
            )
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            LOGGER.warning(
                "Error occurred while deleting user requests of chat: %s", str(e)
            )
            return False
