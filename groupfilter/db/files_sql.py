import re
import threading
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import create_engine, func, and_, or_
from sqlalchemy import Column, TEXT, Numeric, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.pool import QueuePool

# from sqlalchemy.pool import StaticPool
from groupfilter import DB_URL, LOGGER, BOT_TOKEN
from groupfilter.utils.helpers import unpack_new_file_id
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from groupfilter.db.redis import NamespacedRedis
import inspect
from contextlib import contextmanager
import sqlite3

BASE = declarative_base()
executor = ThreadPoolExecutor(max_workers=10)


def get_redis_client(token: str) -> NamespacedRedis:
    namespace = token[-10:]
    return NamespacedRedis(
        namespace, host="localhost", port=6379, db=0, decode_responses=True
    )


token = BOT_TOKEN[-6:]
redis_client = get_redis_client(token)

try:
    redis_client.config_set("maxmemory", "500mb")
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
    # You can skip this after initial DB setup
    BASE.metadata.create_all(engine)
    return scoped_session(sessionmaker(bind=engine, autoflush=False))


SESSION = start()
INSERTION_LOCK = threading.RLock()


@contextmanager
def session_scope():
    try:
        yield SESSION
        SESSION.commit()
    except Exception as e:
        SESSION.rollback()
        caller_frame = inspect.currentframe().f_back
        caller_name = caller_frame.f_code.co_name if caller_frame else "unknown"
        LOGGER.error(
            "Database error occurred in function '%s': %s", caller_name, str(e)
        )
        raise
    finally:
        SESSION.close()


async def save_file(media):
    file_id, file_ref = unpack_new_file_id(media.file_id)
    with INSERTION_LOCK:
        try:
            file = SESSION.query(Files).filter_by(file_id=file_id).one()
            LOGGER.warning("%s is already saved in the database", media.file_name)
            return "duplicate"
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
                return "duplicate"
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
    key = cache_key(query, page, per_page)
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor, fetch_filter_results_sync, query, page, per_page
    )
    redis_client.setex(key, 86400, json.dumps(result))
    return result


def fetch_filter_results_sync(query, page, per_page):
    try:
        offset = (page - 1) * per_page
        search = [word for word in query.split()]
        conditions = [
            Files.search_vector.op("@@")(func.plainto_tsquery("simple", term))
            if len(term) <= 2
            else or_(
                Files.search_vector.op("@@")(func.plainto_tsquery("simple", term)),
                Files.search_vector.op("@@")(func.to_tsquery("simple", f"{term}:*")),
            )
            for term in search
        ]
        combined_condition = and_(*conditions)

        with session_scope() as session:
            files_query = (
                session.query(Files).filter(combined_condition).order_by(Files.id.desc())
            )
            total_count = (
                session.query(func.count(Files.file_id)).filter(combined_condition).scalar()
            )
            files = files_query.offset(offset).limit(per_page).all()

            return {
                "files": [
                    {
                        "file_name": file.file_name,
                        "file_id": file.file_id,
                        "file_ref": file.file_ref,
                        "file_size": str(int(file.file_size)),
                        "file_type": file.file_type,
                        "mime_type": file.mime_type,
                        "caption": file.caption,
                    }
                    for file in files
                ],
                "total_count": total_count,
            }
    except Exception as e:
        LOGGER.warning("Error occurred while retrieving filter results: %s", str(e))
        return {"files": [], "total_count": 0}


async def get_precise_filter_results(query, page=1, per_page=10):
    key = cache_key(query, page, per_page)
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)
    try:
        offset = (page - 1) * per_page
        search = query.split()

        conditions = [Files.search_vector.match(f'"{word}"') for word in search]
        combined_condition = and_(*conditions)

        with session_scope() as session:
            files_query = (
                session.query(Files)
                .filter(combined_condition)
                .order_by(Files.id.desc())
            )
            total_count_query = session.query(func.count(Files.file_id)).filter(
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
                        "file_size": str(int(file.file_size)),
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


async def get_last_results(page=1, per_page=10):
    key = cache_key("", page, per_page)
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)
    try:
        offset = (page - 1) * per_page
        with session_scope() as session:
            files_query = session.query(Files).order_by(Files.id.desc())
            total_count_query = session.query(func.count(Files.file_id))
            total_count = total_count_query.scalar()
            files = files_query.offset(offset).limit(per_page).all()

            result = {
                "files": [
                    {
                        "file_name": file.file_name,
                        "file_id": file.file_id,
                        "file_ref": file.file_ref,
                        "file_size": str(int(file.file_size)),
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
        LOGGER.warning("Error occurred while retrieving last file results: %s", str(e))
        return {"files": [], "total_count": 0}


async def get_inline_filter_results(query, page=1, per_page=10):
    if not query.strip():
        return {"files": [], "total_count": 0}

    key = cache_key(query, page, per_page)
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)

    try:
        offset = (page - 1) * per_page
        search = [clean_query(word) for word in query.split() if clean_query(word)]
        # contains_stop_word = any(word.lower() in STOP_WORDS for word in search)
        # if contains_stop_word:
        #     conditions = [Files.file_name.ilike(f"%{term}%") for term in search]
        # else:
        #     conditions = [
        #         Files.search_vector.op("@@")(
        #             func.to_tsquery(f"{term}" if len(term) <= 1 else f"{term}:*")
        #         )
        #         for term in search
        #     ]
        conditions = [
            Files.search_vector.op("@@")(func.plainto_tsquery("simple", term))
            if len(term) <= 2  # Only use plainto_tsquery for short terms
            else or_(
                Files.search_vector.op("@@")(func.plainto_tsquery("simple", term)),
                Files.search_vector.op("@@")(
                    func.to_tsquery("simple", f"{term}:*")
                ),
            )
            for term in search
        ]
        combined_condition = and_(*conditions)
        
        with session_scope() as session:
            files_query = (
                session.query(Files)
                .filter(combined_condition)
                .order_by(Files.id.desc())
            )
            total_count_query = session.query(func.count(Files.file_id)).filter(
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
                        "file_size": str(int(file.file_size)),
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
        LOGGER.warning(
            "Error occurred while retrieving filter results: %s : query: %s",
            str(e),
            query,
        )
        return {"files": [], "total_count": 0}


async def get_file_details(file_id):
    try:
        with session_scope() as session:
            file_details = session.query(Files).filter_by(file_id=file_id).all()
            return [
                {
                    "file_name": file_details.file_name,
                    "file_id": file_details.file_id,
                    "file_ref": file_details.file_ref,
                    "file_size": str(int(file_details.file_size)),
                    "file_type": file_details.file_type,
                    "caption": file_details.caption,
                }
                for file_details in file_details
            ]
    except Exception as e:
        LOGGER.warning("Error occurred while retrieving file details: %s", str(e))
        return []


async def delete_file(media):
    file_id, file_ref = unpack_new_file_id(media.file_id)
    try:
        with INSERTION_LOCK:
            with session_scope() as session:
                file = session.query(Files).filter_by(file_id=file_id).first()
                if file:
                    session.delete(file)
                    return True
                LOGGER.warning("File to delete not found: %s", str(file_id))
                return "Not Found"
    except Exception as e:
        LOGGER.warning("Error occurred while deleting file: %s", str(e))
        return False


async def count_files():
    try:
        with INSERTION_LOCK:
            with session_scope() as session:
                total_count = session.query(Files).count()
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


async def get_existing_files_cache():
    try:
        with INSERTION_LOCK:
            existing_files_data = {}
            batch_size = 25000
            offset = 0
            total_loaded = 0

            while True:
                with session_scope() as session:
                    files = session.query(Files).offset(offset).limit(batch_size).all()
                    if not files:
                        break

                    for file in files:
                        file_key = file.file_id
                        LOGGER.debug(f"Loading file with key: {file_key}")
                        existing_files_data[file_key] = {
                            "file_name": file.file_name,
                            "file_id": file.file_id,
                            "file_ref": file.file_ref,
                            "file_size": str(int(file.file_size)),
                            "file_type": file.file_type,
                            "mime_type": file.mime_type,
                            "caption": file.caption,
                        }
                    loaded_count = len(files)
                    LOGGER.info(f"Loaded {loaded_count} files from the database")
                    total_loaded += loaded_count
                    offset += batch_size
                    if loaded_count < batch_size:
                        break
            LOGGER.info(f"Total files loaded: {total_loaded}")
            return existing_files_data
    except Exception as e:
        LOGGER.error(f"Error getting existing files: {e}")
        return {}


async def save_new_files(new_files_data, DB_SEMAPHORE):
    saved = 0
    errors = 0
    try:
        for file_id, file_data in new_files_data.items():
            try:
                if isinstance(file_data, str):
                    file_data = json.loads(file_data)

                cleaned_fn = (
                    clean_text(file_data["file_name"]) if file_data["file_name"] else ""
                )
                cleaned_cp = (
                    clean_text(file_data["caption"]) if file_data["caption"] else ""
                )
                search_vector = func.to_tsvector(
                    "simple",
                    func.coalesce(cleaned_fn, "") + " " + func.coalesce(cleaned_cp, ""),
                )

                async with DB_SEMAPHORE:
                    with INSERTION_LOCK:
                        with session_scope() as session:
                            file = Files(
                                file_name=file_data["file_name"],
                                file_id=file_data["file_id"],
                                file_ref=file_data["file_ref"],
                                file_size=str(int(file_data["file_size"])),
                                file_type=file_data["file_type"],
                                mime_type=file_data["mime_type"],
                                caption=file_data["caption"],
                                search_vector=search_vector,
                            )
                            session.add(file)
                            saved += 1
                            LOGGER.info(f"Indexed file to DB: {file_data['file_name']}")
            except Exception as e:
                errors += 1
                LOGGER.error(f"Error saving file to DB: {e}")
                LOGGER.error(f"File data that caused error: {file_data}")
    except Exception as e:
        LOGGER.error(f"Error in batch save: {e}")
        errors += len(new_files_data)

    return saved, errors


@contextmanager
def get_temp_db():
    temp_db_path = "temp_index.db"
    try:
        conn = sqlite3.connect(temp_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS existing_files (
                file_key TEXT PRIMARY KEY,
                file_data TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS new_files (
                file_key TEXT PRIMARY KEY,
                file_data TEXT
            )
        """)
        yield conn
    finally:
        conn.close()


async def save_to_temp_db(files_data, table_name):
    with get_temp_db() as conn:
        cursor = conn.cursor()
        for file_key, file_data in files_data.items():
            try:
                file_key = str(file_key)
                LOGGER.debug(f"Saving file with key: {file_key}")

                if isinstance(file_data, dict):
                    file_data = json.dumps(file_data)

                cursor.execute(
                    f"""
                    INSERT OR IGNORE INTO {table_name} 
                    (file_key, file_data)
                    VALUES (?, ?)
                """,
                    (file_key, file_data),
                )
                LOGGER.debug(f"File saved successfully: {file_key}")
            except Exception as e:
                LOGGER.error(f"Error saving to temp DB: {e}")
                LOGGER.error(f"Failed file key: {file_key}")
                continue
        LOGGER.debug("Saved %s files to temp DB", len(files_data))

        conn.commit()


async def check_file_exists(file_key, table_name):
    with get_temp_db() as conn:
        cursor = conn.cursor()
        file_key = str(file_key)
        LOGGER.debug(f"Checking file existence for key: {file_key}")
        cursor.execute(f"SELECT 1 FROM {table_name} WHERE file_key = ?", (file_key,))
        result = cursor.fetchone() is not None
        LOGGER.debug(f"File exists check result: {result}")
        return result


async def get_new_files():
    with get_temp_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_key, file_data FROM new_files")
        return {row[0]: json.loads(row[1]) for row in cursor.fetchall()}


async def search_files_by_name(search_term):
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            search = [word for word in search_term.split()]
            conditions = [
                Files.search_vector.op("@@")(func.plainto_tsquery("simple", term))
                if len(term) <= 2
                else or_(
                    Files.search_vector.op("@@")(func.plainto_tsquery("simple", term)),
                    Files.search_vector.op("@@")(func.to_tsquery("simple", f"{term}:*")),
                )
                for term in search
            ]
            combined_condition = and_(*conditions)

            with session_scope() as session:
                files = session.query(Files).filter(combined_condition).order_by(Files.id.desc()).all()
                return [
                    {
                        "file_name": file.file_name,
                        "file_id": file.file_id,
                        "file_ref": file.file_ref,
                        "file_size": str(int(file.file_size)),
                        "file_type": file.file_type,
                        "mime_type": file.mime_type,
                        "caption": file.caption,
                    }
                    for file in files
                ]
        except Exception as e:
            LOGGER.warning(f"Error occurred while searching files by name (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                LOGGER.error(f"All attempts failed when searching for '{search_term}': {str(e)}")
    return []


async def delete_files_by_name(search_term):
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            search = [word for word in search_term.split()]
            conditions = [
                Files.search_vector.op("@@")(func.plainto_tsquery("simple", term))
                if len(term) <= 2
                else or_(
                    Files.search_vector.op("@@")(func.plainto_tsquery("simple", term)),
                    Files.search_vector.op("@@")(func.to_tsquery("simple", f"{term}:*")),
                )
                for term in search
            ]
            combined_condition = and_(*conditions)

            with session_scope() as session:
                files = session.query(Files).filter(combined_condition).all()
                if not files:
                    return 0, 0
                
                deleted_count = 0
                failed_count = 0
                
                for file in files:
                    try:
                        session.delete(file)
                        deleted_count += 1
                    except Exception as e:
                        LOGGER.warning(f"Error deleting file {file.file_name}: {str(e)}")
                        failed_count += 1
                        
                return deleted_count, failed_count
                
        except Exception as e:
            LOGGER.warning(f"Error occurred while deleting files by name (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                LOGGER.error(f"All attempts failed when deleting files for '{search_term}': {str(e)}")
    return 0, 0


async def clear_files():
    try:
        with INSERTION_LOCK:
            with session_scope() as session:
                session.query(Files).delete()
    except Exception as e:
        LOGGER.warning("Error occurred while clearing files: %s", str(e))
