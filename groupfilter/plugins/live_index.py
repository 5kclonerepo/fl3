import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from groupfilter import DB_CHANNELS, LOGGER
from groupfilter.db.files_sql import save_file
from groupfilter.utils.helpers import clean_text
from groupfilter.plugins.serve import clear_cache

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.chat(DB_CHANNELS) & media_filter)
async def live_index(bot, message):
    try:
        for file_type in ("document", "video", "audio"):
            media = getattr(message, file_type, None)
            caption = message.caption
            if media:
                caption = message.caption
                file_name = media.file_name
                media.file_type = file_type
                media.caption = clean_text(caption) or clean_text(file_name)
                await save_file(media)
                break
            await asyncio.sleep(0.5)
        await clear_cache(bot, mess=False)
    except FloodWait as e:
        LOGGER.warning("Floodwait while live index. Sleeping for %s seconds", e.value)
        await asyncio.sleep(e.value)
        await live_index(bot, message)
    except Exception as e:
        LOGGER.warning("Error occurred while saving file: %s", str(e))
