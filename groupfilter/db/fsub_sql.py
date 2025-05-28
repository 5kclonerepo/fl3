from contextlib import contextmanager
from sqlalchemy import create_engine, func
from sqlalchemy import Column, TEXT, BigInteger, Numeric, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from groupfilter import DB_URL, LOGGER
import inspect


BASE = declarative_base()


class ForceSub(BASE):
    __tablename__ = "forcesub"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    chat_id = Column(Numeric)
    chat_title = Column(TEXT)
    chat_link = Column(TEXT)
    join_count = Column(Numeric)
    target = Column(Numeric)
    is_req = Column(Boolean)
    is_active = Column(Boolean)
    is_done = Column(Boolean)
    is_queue = Column(Boolean)

    def __init__(
        self,
        chat_id,
        chat_title,
        chat_link,
        join_count,
        target,
        is_req,
        is_active,
        is_done,
        is_queue,
    ):
        self.chat_id = chat_id
        self.chat_title = chat_title
        self.chat_link = chat_link
        self.join_count = join_count
        self.target = target
        self.is_req = is_req
        self.is_active = is_active
        self.is_done = is_done
        self.is_queue = is_queue


class FsubReq(BASE):
    __tablename__ = "fsubreq"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    chat_id = Column(Numeric)
    fileid = Column(TEXT)
    msg_id = Column(BigInteger)

    def __init__(self, user_id, chat_id, fileid, msg_id):
        self.user_id = user_id
        self.chat_id = chat_id
        self.fileid = fileid
        self.msg_id = msg_id


class FsubReg(BASE):
    __tablename__ = "fsubreg"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger)
    chat_id = Column(Numeric)
    fileid = Column(TEXT)
    msg_id = Column(BigInteger)

    def __init__(self, user_id, chat_id, fileid, msg_id):
        self.user_id = user_id
        self.chat_id = chat_id
        self.fileid = fileid
        self.msg_id = msg_id


def start() -> scoped_session:
    engine = create_engine(
        DB_URL,
        client_encoding="utf8",
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=50,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=True,
        pool_use_lifo=True,
    )
    BASE.metadata.bind = engine
    BASE.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()


@contextmanager
def session_scope():
    try:
        yield SESSION
        SESSION.commit()
    except Exception as e:
        SESSION.rollback()
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        LOGGER.error("Database error occurred in function '%s': %s", caller_name, str(e))
        raise
    finally:
        SESSION.close()


async def set_force_sub(
    chat_id,
    chat_title,
    chat_link,
    join_count,
    target,
    is_req,
    is_active=True,
    is_done=False,
    is_queue=False,
):
    try:
        with session_scope() as session:
            sub = session.query(ForceSub).filter(ForceSub.chat_id == chat_id).first()
            if not sub:
                sub = ForceSub(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    chat_link=chat_link,
                    join_count=join_count,
                    target=target,
                    is_req=is_req,
                    is_active=is_active,
                    is_done=is_done,
                    is_queue=is_queue,
                )
                session.add(sub)
                return True
            else:
                return "exists"
    except Exception as e:
        LOGGER.error("Error setting Force Sub channel: %s", str(e))
        return False


async def update_force_sub(
    chat_id=None,
    chat_title=None,
    chat_link=None,
    join_count=None,
    target=None,
    is_req=None,
    is_active=None,
    is_done=None,
    is_queue=None,
):
    try:
        with session_scope() as session:
            sub = session.query(ForceSub).filter(ForceSub.chat_id == chat_id).first()
            if sub:
                if chat_link is not None:
                    sub.chat_link = chat_link
                if chat_title is not None:
                    sub.chat_title = chat_title
                if join_count is not None:
                    sub.join_count = join_count
                if target is not None:
                    sub.target = target
                if is_req is not None:
                    sub.is_req = is_req
                if is_active is not None:
                    sub.is_active = is_active
                if is_done is not None:
                    sub.is_done = is_done
                if is_queue is not None:
                    sub.is_queue = is_queue
                return True
            else:
                return False
    except Exception as e:
        LOGGER.error("Error updating Force Sub channel: %s", str(e))
        return False


async def get_force_sub(chat_id):
    try:
        with session_scope() as session:
            sub = session.query(ForceSub).filter(ForceSub.chat_id == chat_id).first()
            if sub is None:
                return None
            return {
                "chat_id": sub.chat_id,
                "chat_title": sub.chat_title,
                "chat_link": sub.chat_link,
                "join_count": sub.join_count,
                "target": sub.target,
                "is_active": sub.is_active,
                "is_queue": sub.is_queue,
                "is_done": sub.is_done,
                "is_req": sub.is_req
            }
    except Exception as e:
        LOGGER.error("Error getting Force Sub channel: %s", str(e))
        return None


async def get_pen_force_subs():
    try:
        with session_scope() as session:
            subs = (
                session.query(ForceSub)
                .filter(ForceSub.is_done == False, ForceSub.is_active == False)
                .order_by(ForceSub.id.asc())
                .all()
            )
            return [{
                "chat_id": sub.chat_id,
                "chat_title": sub.chat_title,
                "chat_link": sub.chat_link,
                "join_count": sub.join_count,
                "target": sub.target,
                "is_req": sub.is_req,
                "is_active": sub.is_active,
                "is_done": sub.is_done,
                "is_queue": sub.is_queue
            } for sub in subs]
    except Exception as e:
        LOGGER.error("Error getting Force Sub channel: %s", str(e))
        return None



async def get_act_force_subs_count():
    try:
        with session_scope() as session:
            sub = (
                session.query(ForceSub)
                .filter(ForceSub.is_done == False, ForceSub.is_active == True)
                .count()
            )
            return sub
    except Exception as e:
        LOGGER.error("Error getting Force Sub channel: %s", str(e))
        return None


async def get_nxt_pen_force_sub():
    try:
        with session_scope() as session:
            sub = (
                session.query(ForceSub)
                .filter(ForceSub.is_done == False, ForceSub.is_active == False)
                .order_by(ForceSub.id.asc())
                .first()
            )
            if sub is None:
                return None
            return {
                "chat_id": sub.chat_id,
                "chat_title": sub.chat_title,
                "chat_link": sub.chat_link,
                "join_count": sub.join_count,
                "target": sub.target,
                "is_req": sub.is_req,
                "is_active": sub.is_active,
                "is_done": sub.is_done,
                "is_queue": sub.is_queue
            }
    except Exception as e:
        LOGGER.error("Error getting next pending Force Sub channel: %s", str(e))
        return None


async def get_active_force_subs():
    try:
        with session_scope() as session:
            subs = (
                session.query(ForceSub)
                .filter(ForceSub.is_active == True, ForceSub.is_queue == False)
                .all()
            )
            return [{
                "id": sub.id,
                "chat_id": sub.chat_id,
                "chat_title": sub.chat_title,
                "chat_link": sub.chat_link,
                "join_count": sub.join_count,
                "target": sub.target,
                "is_active": sub.is_active,
                "is_queue": sub.is_queue,
                "is_done": sub.is_done,
                "is_req": sub.is_req
            } for sub in subs]
    except Exception as e:
        LOGGER.error("Error getting Force Sub channel: %s", str(e))
        return None


async def get_all_force_subs():
    try:
        with session_scope() as session:
            subs = session.query(ForceSub).all()
            return [{
                "chat_id": sub.chat_id,
                "chat_title": sub.chat_title,
                "chat_link": sub.chat_link,
                "join_count": sub.join_count,
                "target": sub.target,
                "is_active": sub.is_active,
                "is_queue": sub.is_queue,
                "is_done": sub.is_done,
                "is_req": sub.is_req
            } for sub in subs]
    except Exception as e:
        LOGGER.error("Error getting Force Sub channel: %s", str(e))
        return None


async def rm_force_sub(chat_id):
    try:
        with session_scope() as session:
            result = (
                session.query(ForceSub).filter(ForceSub.chat_id == chat_id).delete()
            )
            return result > 0
    except Exception as e:
        LOGGER.error("Error removing Force Sub channel: %s", str(e))
        return False


async def clear_force_subs():
    try:
        with session_scope() as session:
            result = session.query(ForceSub).delete()
            return result > 0
    except Exception as e:
        LOGGER.error("Error clearing Force Sub channels: %s", str(e))
        return False


async def add_fsub_req_user(user_id, chat_id, fileid, msg_id):
    try:
        with session_scope() as session:
            fltr = session.query(FsubReq).filter_by(user_id=user_id, chat_id=chat_id).first()
            if fltr:
                fltr.fileid = fileid
                fltr.msg_id = msg_id
                return True
            fltr = FsubReq(user_id=user_id, chat_id=chat_id, fileid=fileid, msg_id=msg_id)
            session.add(fltr)
            return True
    except Exception as e:
        LOGGER.error("Error adding Fsub request user: %s", str(e))
        return False


async def is_req_user(user_id, chat_id):
    try:
        with session_scope() as session:
            fltr = session.query(FsubReq).filter_by(user_id=user_id, chat_id=chat_id).first()
            if fltr:
                return {
                    "user_id": fltr.user_id,
                    "chat_id": fltr.chat_id,
                    "fileid": fltr.fileid,
                    "msg_id": fltr.msg_id
                }
            return False
    except Exception as e:
        LOGGER.error("Error checking Fsub request user: %s", str(e))
        return False


async def rem_fsub_req_file(user_id, chat_id):
    try:
        with session_scope() as session:
            fltr = session.query(FsubReq).filter_by(user_id=user_id, chat_id=chat_id).first()
            if fltr:
                fltr.fileid = None
                fltr.msg_id = None
                return True
            LOGGER.warning("File to delete not found: %s", str(user_id))
            return False
    except Exception as e:
        LOGGER.error("Error removing Fsub request file: %s", str(e))
        return False


async def delete_group_req_id(chat_id):
    try:
        with session_scope() as session:
            result = session.query(FsubReq).filter(FsubReq.chat_id == chat_id).delete()
            return result > 0
    except Exception as e:
        LOGGER.error("Error deleting group request ID: %s", str(e))
        return False


async def add_fsub_reg_user(user_id, chat_id, fileid, msg_id):
    try:
        with session_scope() as session:
            fltr = session.query(FsubReg).filter_by(user_id=user_id, chat_id=chat_id).first()
            if fltr:
                fltr.fileid = fileid
                fltr.msg_id = msg_id
                return True
            fltr = FsubReg(user_id=user_id, chat_id=chat_id, fileid=fileid, msg_id=msg_id)
            session.add(fltr)
            return True
    except Exception as e:
        LOGGER.error("Error adding Fsub registered user: %s", str(e))
        return False


async def is_reg_user(user_id, chat_id):
    try:
        with session_scope() as session:
            fltr = session.query(FsubReg).filter_by(user_id=user_id, chat_id=chat_id).first()
            if fltr:
                return {
                    "user_id": fltr.user_id,
                    "chat_id": fltr.chat_id,
                    "fileid": fltr.fileid,
                    "msg_id": fltr.msg_id
                }
            return False
    except Exception as e:
        LOGGER.error("Error checking Fsub registered user: %s", str(e))
        return False


async def rem_fsub_reg_file(user_id, chat_id):
    try:
        with session_scope() as session:
            fltr = session.query(FsubReg).filter_by(user_id=user_id, chat_id=chat_id).first()
            if fltr:
                fltr.fileid = None
                fltr.msg_id = None
                return True
            LOGGER.warning("File to delete not found: %s", str(user_id))
            return False
    except Exception as e:
        LOGGER.error("Error removing Fsub registered file: %s", str(e))
        return False


async def delete_fsub_reg_id(user_id, chat_id):
    try:
        with session_scope() as session:
            result = (
                session.query(FsubReg)
                .filter(FsubReg.user_id == user_id, FsubReg.chat_id == chat_id)
                .delete()
            )
            return result > 0
    except Exception as e:
        LOGGER.error("Error deleting Fsub registered ID: %s", str(e))
        return False


async def remove_fsub_users():
    try:
        with session_scope() as session:
            session.query(FsubReq).delete()
            session.query(FsubReg).delete()
            LOGGER.warning("Removed all fsub users")
            return True
    except Exception as e:
        LOGGER.error("Error removing fsub users: %s", str(e))
        return False


async def get_fsubreq_users_count():
    try:
        with session_scope() as session:
            results = (
                session.query(
                    FsubReq.chat_id, func.count(FsubReq.user_id).label("count")
                )
                .filter(FsubReq.fileid == None)
                .group_by(FsubReq.chat_id)
                .all()
            )
            return [{
                "chat_id": result.chat_id,
                "count": result.count
            } for result in results]
    except Exception as e:
        LOGGER.error("Error getting Fsub request users count: %s", str(e))
        return []


async def get_fsubreg_users_count():
    try:
        with session_scope() as session:
            results = (
                session.query(
                    FsubReg.chat_id, func.count(FsubReg.user_id).label("count")
                )
                .filter(FsubReg.fileid == None)
                .group_by(FsubReg.chat_id)
                .all()
            )
            return [{
                "chat_id": result.chat_id,
                "count": result.count
            } for result in results]
    except Exception as e:
        LOGGER.error("Error getting Fsub registered users count: %s", str(e))
        return []
