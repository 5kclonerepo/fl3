import re
import asyncio
import time
import json
import os
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import MessageMediaType
from groupfilter import ADMINS, LOGGER
from groupfilter.db.files_sql import (
    save_file,
    delete_file,
    get_existing_files_cache,
    save_to_temp_db,
    check_file_exists,
    get_new_files,
    save_new_files,
)
from groupfilter.utils.helpers import clean_text, unpack_new_file_id
from groupfilter.plugins.serve import clear_cache


lock = asyncio.Lock()
media_filter = filters.document | filters.video | filters.audio
index_task = None
link_pattern = r"https://t\.me/c/(\d+)/(\d+)"

CONCURRENT_BATCH_SIZE = 100
MAX_REQUESTS_PER_MINUTE = 20
REQUEST_INTERVAL = 60 / MAX_REQUESTS_PER_MINUTE
last_request_time = 0
consecutive_flood_waits = 0
flood_wait_backoff = 1.0
DB_SEMAPHORE = asyncio.Semaphore(20)


async def rate_limited_request():
    global last_request_time, consecutive_flood_waits, flood_wait_backoff
    current_time = time.time()
    elapsed = current_time - last_request_time
    wait_time = max(REQUEST_INTERVAL, REQUEST_INTERVAL * flood_wait_backoff) - elapsed
    if wait_time > 0:
        await asyncio.sleep(wait_time)
    last_request_time = time.time()


@Client.on_message(
    filters.private & filters.forwarded & filters.user(ADMINS) & media_filter
)
async def index_files(bot, message):
    global index_task
    user_id = message.from_user.id
    if lock.locked():
        await message.reply("Wait until the previous process completes.")
    else:
        try:
            last_msg_id = message.forward_from_message_id
            if message.forward_from_chat.username:
                chat_id = message.forward_from_chat.username
            else:
                chat_id = message.forward_from_chat.id
            try:
                await bot.get_messages(chat_id=chat_id, message_ids=last_msg_id)
            except Exception as e:
                await message.reply(f"Error while indexing: `{e}`")
                return

            kb = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Proceed",
                            callback_data=f"index {chat_id} {2} {last_msg_id}",
                        ),
                        InlineKeyboardButton("Cancel", callback_data="can-index"),
                    ]
                ]
            )
            await bot.send_message(
                user_id,
                "Please confirm if you want to start indexing",
                reply_markup=kb,
            )
        except Exception as e:
            await message.reply_text(
                f"Unable to start indexing, either the channel is private and bot is not an admin in the forwarded chat, or you forwarded the message as copy.\nError caused due to <code>{e}</code>"
            )


@Client.on_message(
    filters.private & filters.user(ADMINS) & filters.command("indexlink")
)
async def manual_index(bot, message):
    global index_task
    if lock.locked():
        await message.reply("Wait until the previous process completes.")
        return

    user_id = message.from_user.id
    args = message.text.split()[1:]

    if not args or len(args) > 2:
        await message.reply("Invalid format. Use:\n/indexlink <link> <link>")
        return
    try:
        chat_id, start_msg_id, last_msg_id = extract_links(args)
        try:
            await bot.get_messages(chat_id=chat_id, message_ids=last_msg_id)
        except Exception as e:
            await message.reply(f"Error while indexing: `{e}`")
            return
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Proceed",
                        callback_data=f"index {chat_id} {start_msg_id} {last_msg_id}",
                    ),
                    InlineKeyboardButton("Cancel", callback_data="can-index"),
                ]
            ]
        )
        await bot.send_message(
            user_id,
            f"Chat ID: `{chat_id}`\nStart Message ID: `{start_msg_id}`\nLast Message ID: `{last_msg_id}`\nPlease confirm if you want to start indexing.",
            reply_markup=kb,
        )
    except Exception as e:
        await message.reply(f"Error on manual indexing: `{e}`")


@Client.on_callback_query(filters.regex(r"^index -?\d+ \d+ \d+"))
async def start_index(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    global index_task
    user_id = query.from_user.id
    chat_id, start_msg_id, last_msg_id = map(int, query.data.split()[1:])

    await query.message.delete()
    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Cancel", callback_data="cancel_index"),
            ]
        ]
    )
    msg = await bot.send_message(
        user_id,
        "🔄 **Starting indexing process...**\n\n"
        "Loading files from database...\n"
        "This will take a while if the database has a lot of files.\n"
        "Please be patient until the process is complete.\n\n"
        "__Files will be updated only after the index is complete__",
        reply_markup=kb,
    )

    index_task = asyncio.create_task(
        index_files_task(bot, msg, chat_id, start_msg_id, last_msg_id)
    )


async def index_files_task(bot, msg, chat_id, start_msg_id, last_msg_id):
    global index_task, consecutive_flood_waits, flood_wait_backoff
    global last_request_time

    total_files = 0
    current = int(start_msg_id)
    saved = 0
    dup = 0
    unsup = 0
    errors = 0
    deleted = 0
    no_media = 0
    processed = 0
    total = last_msg_id + 1

    semaphore = asyncio.Semaphore(CONCURRENT_BATCH_SIZE)

    try:
        existing_files_data = await get_existing_files_cache()
        if existing_files_data:
            await save_to_temp_db(existing_files_data, "existing_files")
            LOGGER.info(f"Saved {len(existing_files_data)} existing files to temp DB")

    except Exception as e:
        LOGGER.error(f"Error saving existing files to temp DB: {e}")
        await msg.edit(f"Error saving existing files to temp DB: {e}")
        return

    start_time = time.time()
    status_update_time = time.time()

    async def process_message(message):
        nonlocal saved, dup, unsup, errors, deleted, no_media, total_files
        if message and not message.empty:
            if message.media:
                if message.media in [
                    MessageMediaType.VIDEO,
                    MessageMediaType.AUDIO,
                    MessageMediaType.DOCUMENT,
                ]:
                    media = getattr(message, message.media.value, None)
                    if media:
                        file_id, file_ref = unpack_new_file_id(media.file_id)

                        if await check_file_exists(file_id, "existing_files"):
                            dup += 1
                            return

                        if await check_file_exists(file_id, "new_files"):
                            dup += 1
                            return

                        media.file_type = message.media.value
                        media.caption = (
                            message.caption.markdown
                            if message.caption
                            else clean_text(media.file_name)
                        )

                        new_file_data = {
                            "file_name": media.file_name,
                            "file_id": file_id,
                            "file_ref": file_ref,
                            "file_size": str(int(media.file_size)),
                            "file_type": media.file_type,
                            "mime_type": media.mime_type,
                            "caption": media.caption,
                        }

                        await save_to_temp_db({file_id: new_file_data}, "new_files")
                        saved += 1
                        total_files += 1
                    else:
                        unsup += 1
                else:
                    unsup += 1
            else:
                no_media += 1
        else:
            deleted += 1

    async def process_batch(message_ids):
        nonlocal deleted
        nonlocal processed
        async with semaphore:
            messages = await bot.get_messages(chat_id=chat_id, message_ids=message_ids)
            tasks = []
            for message in messages:
                if message and not message.empty:
                    tasks.append(process_message(message))
                else:
                    deleted += 1
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            processed += int(len(messages))
            LOGGER.info("Processed %s messages", processed)

    async with lock:
        try:
            while current < total:
                try:
                    await rate_limited_request()

                    remaining = total - current
                    batch_size = min(CONCURRENT_BATCH_SIZE, remaining)
                    message_ids = list(range(current, current + batch_size))

                    await process_batch(message_ids)

                    consecutive_flood_waits = max(0, consecutive_flood_waits - 1)
                    if consecutive_flood_waits == 0:
                        flood_wait_backoff = max(1.0, flood_wait_backoff * 0.8)

                    current_time = time.time()
                    if current_time - status_update_time >= 30:
                        elapsed = current_time - start_time
                        speed = current / elapsed if elapsed > 0 else 0

                        if elapsed >= 3600:
                            hours = int(elapsed // 3600)
                            minutes = int((elapsed % 3600) // 60)
                            seconds = int(elapsed % 60)
                            elapsed_str = f"{hours}h {minutes}m {seconds}s"
                        elif elapsed >= 60:
                            minutes = int(elapsed // 60)
                            seconds = int(elapsed % 60)
                            elapsed_str = f"{minutes}m {seconds}s"
                        else:
                            elapsed_str = f"{int(elapsed)}s"

                        status_text = (
                            "⌛ **Indexing Progress**\n\n"
                            f"📊 Total messages processed: `{current}`\n"
                            f"⏱️ Elapsed time: `{elapsed_str}`\n"
                            f"⚡ Speed: `{int(speed)} msg/sec`\n\n"
                            f"📥 Saved: `{saved}`\n"
                            f"🔁 Duplicates: `{dup}`\n"
                            f"🗑️ Deleted: `{deleted}`\n"
                            f"📭 Non-media: `{no_media + unsup}`\n"
                            f"⚠️ Errors: `{errors}`\n"
                            f"➕ Remaining: `{remaining}`\n"
                            f"🔄 Batch size: `{CONCURRENT_BATCH_SIZE}`"
                        )

                        try:
                            await msg.edit(
                                status_text,
                                reply_markup=InlineKeyboardMarkup(
                                    [
                                        [
                                            InlineKeyboardButton(
                                                "Cancel", callback_data="cancel_index"
                                            )
                                        ]
                                    ]
                                ),
                            )
                            status_update_time = current_time
                        except FloodWait as e:
                            LOGGER.warning(
                                f"FloodWait in status update: {e.value} seconds"
                            )
                            await asyncio.sleep(e.value)
                        except Exception as e:
                            LOGGER.error(f"Error updating status: {e}")

                    current += batch_size
                    await asyncio.sleep(0.1)

                except FloodWait as e:
                    consecutive_flood_waits += 1
                    flood_wait_backoff = min(10.0, flood_wait_backoff * 1.5)
                    LOGGER.warning(
                        f"FloodWait encountered: Waiting for {e.value} seconds (backoff: {flood_wait_backoff:.2f}x)"
                    )
                    await asyncio.sleep(e.value)
                    continue

                except Exception as e:
                    LOGGER.error(f"Error processing batch: {e}")
                    errors += batch_size
                    current += batch_size
                    await asyncio.sleep(2)
                    continue

            try:
                new_files = await get_new_files()
                LOGGER.info(f"New files: {len(new_files)}")
                if new_files:
                    new_saved, new_errors = await save_new_files(
                        new_files, DB_SEMAPHORE
                    )
                    saved = new_saved
                    errors += new_errors
            except Exception as e:
                LOGGER.error(f"Error saving new files to main DB: {e}")
                errors += len(new_files)

            total_time = time.time() - start_time
            if total_time >= 3600:
                hours = int(total_time // 3600)
                minutes = int((total_time % 3600) // 60)
                seconds = int(total_time % 60)
                elapsed_str = f"{hours}h {minutes}m {seconds}s"
            elif total_time >= 60:
                minutes = int(total_time // 60)
                seconds = int(total_time % 60)
                elapsed_str = f"{minutes}m {seconds}s"
            else:
                elapsed_str = f"{int(total_time)}s"
            avg_speed = total / total_time if total_time > 0 else 0

            final_status = (
                "✅ **Indexing completed!**\n\n"
                f"📊 Total messages: `{total}`\n"
                f"⏱️ Total time: `{elapsed_str}`\n"
                f"⚡ Average speed: `{int(avg_speed)} msg/sec`\n\n"
                f"📁 Successfully saved: `{saved}`\n"
                f"🔁 Duplicates skipped: `{dup}`\n"
                f"🗑️ Deleted messages skipped: `{deleted}`\n"
                f"📭 Non-media messages skipped: `{no_media + unsup}`\n"
                f"⚠️ Errors occurred: `{errors}`"
            )

            retry_count = 3
            while retry_count > 0:
                try:
                    await msg.edit(final_status)
                    LOGGER.info(f"Final status update: {final_status}")
                    break
                except FloodWait as e:
                    LOGGER.warning(f"FloodWait in final update: {e.value} seconds")
                    await asyncio.sleep(e.value)
                    retry_count -= 1
                except Exception as e:
                    LOGGER.error(f"Error in final status update: {e}")
                    retry_count -= 1
                    await asyncio.sleep(5)

            await clear_cache(bot, mess=False)

        except asyncio.CancelledError:
            LOGGER.info("Indexing task was cancelled.")
            await msg.edit("Indexing process was cancelled.")
        except Exception as e:
            LOGGER.exception(e)
            await msg.edit(f"Error while indexing: {e}")
        finally:
            temp_db_path = "temp_index.db"
            if os.path.exists(temp_db_path):
                try:
                    os.remove(temp_db_path)
                    LOGGER.info("Temporary SQLite database deleted successfully")
                except Exception as e:
                    LOGGER.error(f"Error deleting temporary SQLite database: {e}")
            index_task = None


@Client.on_callback_query(filters.regex(r"^cancel_index"))
async def cancel_indexing(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    global index_task
    user_id = query.from_user.id
    if index_task and not index_task.done():
        index_task.cancel()
        await query.message.edit("Indexing cancelled.")
        LOGGER.info("User requested cancellation of indexing.. : %s", user_id)
    else:
        await query.message.edit("No active indexing process to cancel.")


@Client.on_message(filters.command(["index"]) & filters.user(ADMINS))
async def index_comm(bot, update):
    await update.reply(
        "Now please forward the last message of the channel you want to index & follow the steps. Bot must be admin of the channel if the channel is private."
    )


@Client.on_message(filters.command(["delete"]) & filters.user(ADMINS))
async def delete_files(bot, message):
    if not message.reply_to_message:
        await message.reply("Please reply to a file to delete")
    org_msg = message.reply_to_message
    try:
        for file_type in ("document", "video", "audio"):
            media = getattr(org_msg, file_type, None)
            if media:
                del_file = await delete_file(media)
                if del_file == "Not Found":
                    await message.reply(f"`{media.file_name}` not found in database")
                elif del_file == True:
                    await message.reply(f"`{media.file_name}` deleted from database")
                else:
                    await message.reply(
                        f"Error occurred while deleting `{media.file_name}`, please check logs for more info"
                    )
                break
    except Exception as e:
        LOGGER.warning("Error occurred while deleting file: %s", str(e))


@Client.on_callback_query(filters.regex(r"^can-index$"))
async def cancel_index(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    await query.message.delete()


def extract_links(links):
    if len(links) == 1:
        match = re.match(link_pattern, links[0])
        if not match:
            raise ValueError("Invalid link format.")
        channel_id, last_msg_id = match.groups()
        chat_id = f"-100{channel_id}"
        return chat_id, 2, last_msg_id

    elif len(links) == 2:
        match1 = re.match(link_pattern, links[0])
        match2 = re.match(link_pattern, links[1])
        if not match1 or not match2:
            raise ValueError("Invalid link format.")
        channel_id1, start_msg_id = match1.groups()
        channel_id2, last_msg_id = match2.groups()
        if channel_id1 != channel_id2:
            raise ValueError("Links belong to different channels.")
        chat_id = f"-100{channel_id1}"
        return chat_id, start_msg_id, last_msg_id

    raise ValueError("Invalid number of links provided.")
