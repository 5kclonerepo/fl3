from sqlalchemy import create_engine, func
from sqlalchemy import Column, TEXT, BigInteger, Numeric, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound

# from sqlalchemy.pool import StaticPool
from groupfilter import DB_URL, LOGGER
import asyncio


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
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
        echo=False,
    )
    BASE.metadata.bind = engine

    # You can skip this after initial DB setup
    BASE.metadata.create_all(engine)

    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()
INSERTION_LOCK = asyncio.Lock()


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
        async with INSERTION_LOCK:
            session = SESSION()
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
                session.commit()
                return True
            else:
                return "exists"
    except Exception as e:
        LOGGER.warning("Error setting Force Sub channel: %s ", str(e))
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
        async with INSERTION_LOCK:
            session = SESSION()
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
                session.commit()
                return True
            else:
                return False
    except Exception as e:
        LOGGER.warning("Error updating Force Sub channel: %s ", str(e))
        return False


async def get_force_sub(chat_id):
    try:
        return await asyncio.to_thread(_get_force_sub_sync, chat_id)
    except Exception as e:
        LOGGER.warning("Error getting Force Sub channel: %s", str(e))
        return None


def _get_force_sub_sync(chat_id):
    session = SESSION()
    try:
        return session.query(ForceSub).filter(ForceSub.chat_id == chat_id).first()
    finally:
        session.close()


async def get_pen_force_subs():
    try:
        async with INSERTION_LOCK:
            session = SESSION()
            sub = (
                session.query(ForceSub)
                .filter(ForceSub.is_done == False, ForceSub.is_active == False)
                .all()
                .order_by(ForceSub.id.asc())
            )
            return sub
    except Exception as e:
        LOGGER.warning("Error getting Force Sub channel: %s ", str(e))
        return None


async def get_act_force_subs_count():
    try:
        async with INSERTION_LOCK:
            session = SESSION()
            sub = (
                session.query(ForceSub)
                .filter(ForceSub.is_done == False, ForceSub.is_active == True)
                .count()
            )
            return sub
    except Exception as e:
        LOGGER.warning("Error getting Force Sub channel: %s ", str(e))
        return None


async def get_nxt_pen_force_sub():
    try:
        async with INSERTION_LOCK:
            session = SESSION()
            sub = (
                session.query(ForceSub)
                .filter(ForceSub.is_done == False, ForceSub.is_active == False)
                .order_by(ForceSub.id.asc())
                .first()
            )
            return sub
    except Exception as e:
        LOGGER.warning("Error getting Force Sub channel: %s ", str(e))
        return None


async def get_active_force_subs():
    try:
        async with INSERTION_LOCK:
            session = SESSION()
            sub = (
                session.query(ForceSub)
                .filter(ForceSub.is_active == True, ForceSub.is_queue == False)
                .all()
            )
            return sub
    except Exception as e:
        LOGGER.warning("Error getting Force Sub channel: %s", str(e))
        return None


async def get_all_force_subs():
    try:
        async with INSERTION_LOCK:
            session = SESSION()
            sub = session.query(ForceSub).all()
            return sub
    except Exception as e:
        LOGGER.warning("Error getting Force Sub channel: %s ", str(e))
        return None


async def rm_force_sub(chat_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            result = (
                session.query(ForceSub).filter(ForceSub.chat_id == chat_id).delete()
            )
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            LOGGER.warning(
                "Error occurred while deleting Force Sub channel: %s", str(e)
            )
            return False


async def clear_force_subs():
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            result = session.query(ForceSub).delete()
            session.commit()
            return result > 0
        except Exception as e:
            session.rollback()
            LOGGER.warning(
                "Error occurred while deleting all Force Sub channels: %s", str(e)
            )
            return False


async def add_fsub_req_user(user_id, chat_id, fileid, msg_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                session.query(FsubReq)
                .filter(FsubReq.user_id == user_id, FsubReq.chat_id == chat_id)
                .one()
            )
            fltr.fileid = fileid
            fltr.msg_id = msg_id
            session.commit()
            return True
        except NoResultFound:
            fltr = FsubReq(
                user_id=user_id, chat_id=chat_id, fileid=fileid, msg_id=msg_id
            )
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
            fltr.msg_id = None
            session.commit()
            return True
        except NoResultFound:
            LOGGER.warning("File to delete not found: %s", str(user_id))
            return False


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


async def add_fsub_reg_user(user_id, chat_id, fileid, msg_id):
    async with INSERTION_LOCK:
        session = SESSION()
        try:
            fltr = (
                SESSION.query(FsubReg)
                .filter(FsubReg.user_id == user_id, FsubReg.chat_id == chat_id)
                .one()
            )
            fltr.fileid = fileid
            fltr.msg_id = msg_id
            session.commit()
            return True
        except NoResultFound:
            fltr = FsubReg(
                user_id=user_id, chat_id=chat_id, fileid=fileid, msg_id=msg_id
            )
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
            fltr.msg_id = None
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


async def get_fsubreq_users_count():
    session = SESSION()
    try:
        results = (
            session.query(FsubReq.chat_id, func.count(FsubReq.user_id).label("count"))
            .filter(FsubReq.fileid == None)
            .group_by(FsubReq.chat_id)
            .all()
        )

        return results

    finally:
        session.close()


async def get_fsubreg_users_count():
    session = SESSION()
    try:
        results = (
            session.query(FsubReg.chat_id, func.count(FsubReg.user_id).label("count"))
            .filter(FsubReg.fileid == None)
            .group_by(FsubReg.chat_id)
            .all()
        )

        return results

    finally:
        session.close()
