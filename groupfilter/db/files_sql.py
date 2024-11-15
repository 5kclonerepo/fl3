import re
import threading
import json
from sqlalchemy import create_engine, func, and_
from sqlalchemy import Column, TEXT, Numeric, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.pool import StaticPool
from groupfilter import DB_URL, LOGGER, BOT_TOKEN
from groupfilter.utils.helpers import unpack_new_file_id, STOP_WORDS
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from groupfilter.db.redis import NamespacedRedis

BASE = declarative_base()


def get_redis_client(token: str) -> NamespacedRedis:
    namespace = token[-10:]
    return NamespacedRedis(
        namespace, host="localhost", port=6379, db=0, decode_responses=True
    )


token = BOT_TOKEN[-6:]
redis_client = get_redis_client(token)

try:
    redis_client.config_set("maxmemory", "300mb")
    redis_client.config_set("maxmemory-policy", "allkeys-lru")
except Exception as e:
    LOGGER.warning("Error occurred while setting Redis configuration: %s", str(e))


class Files(BASE):
    __tablename__ = "files"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    file_name = Column(TEXT)
    file_id = Column(TEXT)
    file_ref = Column(TEXT)
    file_size = Column(Numeric)
    file_type = Column(TEXT)
    mime_type = Column(TEXT)
    caption = Column(TEXT)
    search_vector = Column(TSVECTOR)

    def __init__(
        self,
        file_name,
        file_id,
        file_ref,
        file_size,
        file_type,
        mime_type,
        caption,
        search_vector,
    ):
        self.file_name = file_name
        self.file_id = file_id
        self.file_ref = file_ref
        self.file_size = file_size
        self.file_type = file_type
        self.mime_type = mime_type
        self.caption = caption
        self.search_vector = search_vector

    def __repr__(self):
        return f"<File(file_name={self.file_name}, file_id={self.file_id})>"


Index("idx_files_search_vector", Files.search_vector, postgresql_using="gin")


def start() -> scoped_session:
    engine = create_engine(DB_URL, client_encoding="utf8", poolclass=StaticPool)
    BASE.metadata.bind = engine
    BASE.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()
INSERTION_LOCK = threading.RLock()


async def save_file(media):
    file_id, file_ref = unpack_new_file_id(media.file_id)
    with INSERTION_LOCK:
        try:
            file = SESSION.query(Files).filter_by(file_id=file_id).one()
            LOGGER.warning("%s is already saved in the database", media.file_name)
        except NoResultFound:
            try:
                file = (
                    SESSION.query(Files)
                    .filter_by(file_name=media.file_name, file_size=media.file_size)
                    .one()
                )
                LOGGER.warning(
                    "%s : %s is already saved in the database",
                    media.file_name,
                    media.file_size,
                )
            except NoResultFound:
                cleaned_fn = clean_text(media.file_name) if media.file_name else ""
                cleaned_cp = clean_text(media.caption) if media.caption else ""
                search_vector = func.to_tsvector(
                    "simple",
                    func.coalesce(cleaned_fn, "") + " " + func.coalesce(cleaned_cp, ""),
                )
                file = Files(
                    file_name=media.file_name,
                    file_id=file_id,
                    file_ref=file_ref,
                    file_size=media.file_size,
                    file_type=media.file_type,
                    mime_type=media.mime_type,
                    caption=media.caption if media.caption else None,
                    search_vector=search_vector,
                )
                LOGGER.info("%s is saved in database", media.file_name)
                SESSION.add(file)
                SESSION.commit()
                return True
            except Exception as e:
                LOGGER.warning(
                    "Error occurred while saving file in database: %s", str(e)
                )
                SESSION.rollback()
                return False
        except Exception as e:
            LOGGER.warning("Error occurred while saving file in database: %s", str(e))
            SESSION.rollback()
            return False


def cache_key(query, page, per_page):
    return f"search:{token}:{query.lower()}:{page}:{per_page}"


async def get_filter_results(query, page=1, per_page=10):
    if not query.strip():
        return {"files": [], "total_count": 0}

    key = cache_key(query, page, per_page)
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)

    try:
        with INSERTION_LOCK:
            offset = (page - 1) * per_page
            search = [clean_query(word) for word in query.split() if clean_query(word)]
            contains_stop_word = any(word.lower() in STOP_WORDS for word in search)
            if contains_stop_word:
                conditions = [Files.file_name.ilike(f"%{term}%") for term in search]
            else:
                conditions = [
                    Files.search_vector.op("@@")(
                        func.to_tsquery(f"{term}" if len(term) <= 1 else f"{term}:*")
                    )
                    for term in search
                ]
            combined_condition = and_(*conditions)
            files_query = (
                SESSION.query(Files)
                .filter(combined_condition)
                .order_by(Files.id.desc())
            )
            total_count_query = SESSION.query(func.count(Files.file_id)).filter(
                combined_condition
            )

            total_count = total_count_query.scalar()
            files = files_query.offset(offset).limit(per_page).all()

            result = {
                "files": [
                    {
                        "file_name": file.file_name,
                        "file_id": file.file_id,
                        "file_ref": file.file_ref,
                        "file_size": str(file.file_size),
                        "file_type": file.file_type,
                        "mime_type": file.mime_type,
                        "caption": file.caption,
                    }
                    for file in files
                ],
                "total_count": total_count,
            }
            redis_client.setex(key, 86400, json.dumps(result))
            return result

    except Exception as e:
        SESSION.rollback()
        LOGGER.warning(
            "Error occurred while retrieving filter results: %s : query: %s",
            str(e),
            query,
        )
        return {"files": [], "total_count": 0}


async def get_precise_filter_results(query, page=1, per_page=10):
    key = cache_key(query, page, per_page)
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)
    try:
        with INSERTION_LOCK:
            offset = (page - 1) * per_page
            search = query.split()

            conditions = [Files.search_vector.match(f'"{word}"') for word in search]
            combined_condition = and_(*conditions)

            files_query = (
                SESSION.query(Files)
                .filter(combined_condition)
                .order_by(Files.id.desc())
            )
            total_count_query = SESSION.query(func.count(Files.file_id)).filter(
                combined_condition
            )
            total_count = total_count_query.scalar()
            files = files_query.offset(offset).limit(per_page).all()

            result = {
                "files": [
                    {
                        "file_name": file.file_name,
                        "file_id": file.file_id,
                        "file_ref": file.file_ref,
                        "file_size": str(file.file_size),
                        "file_type": file.file_type,
                        "mime_type": file.mime_type,
                        "caption": file.caption,
                    }
                    for file in files
                ],
                "total_count": total_count,
            }
            redis_client.setex(key, 86400, json.dumps(result))
            return result
    except Exception as e:
        LOGGER.warning("Error occurred while retrieving filter results: %s", str(e))
        return {"files": [], "total_count": 0}


async def get_file_details(file_id):
    try:
        with INSERTION_LOCK:
            file_details = SESSION.query(Files).filter_by(file_id=file_id).all()
            return file_details
    except Exception as e:
        LOGGER.warning("Error occurred while retrieving file details: %s", str(e))
        return []


async def delete_file(media):
    file_id, file_ref = unpack_new_file_id(media.file_id)
    try:
        with INSERTION_LOCK:
            file = SESSION.query(Files).filter_by(file_id=file_id).first()
            if file:
                SESSION.delete(file)
                SESSION.commit()
                return True
            return "Not Found"
            LOGGER.warning("File to delete not found: %s", str(file_id))
    except Exception as e:
        LOGGER.warning("Error occurred while deleting file: %s", str(e))
        SESSION.rollback()
        return False


async def count_files():
    try:
        with INSERTION_LOCK:
            total_count = SESSION.query(Files).count()
            return total_count
    except Exception as e:
        LOGGER.warning("Error occurred while counting files: %s", str(e))
        return 0


def clean_text(text):
    return re.sub(r"[._\[\]{}()<>|;:'\",?!`~@#$%^&+=\\]", " ", text)


def clean_query(query):
    clean = re.sub(r"[&|!()<>:*._]", "", query)
    clean = re.sub(r"^[\'\"]+", "", clean)
    return clean
