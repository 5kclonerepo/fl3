import re
import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from groupfilter import ADMINS, LOGGER
from groupfilter.db.files_sql import save_file, delete_file
from groupfilter.utils.helpers import clean_text
from groupfilter.plugins.serve import clear_cache


lock = asyncio.Lock()
media_filter = filters.document | filters.video | filters.audio
index_task = None
link_pattern = r"https://t\.me/c/(\d+)/(\d+)"


@Client.on_message(filters.private & filters.user(ADMINS) & media_filter)
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
            await bot.get_messages(chat_id, last_msg_id)

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
        await message.reply("Invalid format. Use:\n/indexlink <link> [<link>]")
        return
    try:
        chat_id, start_msg_id, last_msg_id = extract_links(args)
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
        "Processing Index...⏳\nCount will be updated after every 200 files.",
        reply_markup=kb,
    )

    index_task = asyncio.create_task(
        index_files_task(bot, msg, chat_id, start_msg_id, last_msg_id)
    )


async def index_files_task(bot, msg, chat_id, start_msg_id, last_msg_id):
    global index_task

    total_files = 0
    current = int(start_msg_id)
    counter = 0
    saved = 0
    total = last_msg_id + 1

    async with lock:
        try:
            while current < total:
                try:
                    message = await bot.get_messages(
                        chat_id=chat_id, message_ids=current, replies=0
                    )
                except FloodWait as e:
                    LOGGER.warning("FloodWait while indexing, Error: %s", str(e))
                    await asyncio.sleep(e.value)
                    continue
                except asyncio.CancelledError:
                    LOGGER.info("Indexing task was cancelled.")
                    await msg.edit("Indexing process was cancelled.")
                    return
                except Exception as e:
                    LOGGER.warning("Error occurred while fetching message: %s", str(e))
                    continue

                try:
                    for file_type in ("document", "video", "audio"):
                        media = getattr(message, file_type, None)                      
                        if media:
                            caption = message.caption
                            file_name = media.file_name
                            media.file_type = file_type
                            media.caption = clean_text(caption) or clean_text(file_name)
                            save = await save_file(media)
                            if save:
                                saved += 1
                            total_files += 1
                            break
                except Exception as e:
                    LOGGER.warning("Error occurred while saving file: %s", str(e))

                current += 1
                counter += 1
                if counter == 200:
                    try:
                        kb = InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton("Cancel", callback_data="cancel_index"),
                                ]
                            ]
                        )
                        await msg.edit(
                            f"Total messages fetched: {current}\nTotal messages processed: {total_files}", reply_markup=kb
                        )
                        LOGGER.info("Total messages & files processed: %s : %s", current, total_files)
                    except FloodWait as e:
                        LOGGER.warning(
                            "FloodWait while editing count message, sleeping for: %s seconds",
                            str(e.value),
                        )
                        await asyncio.sleep(e.value)
                    counter -= 200

            await clear_cache(bot, mess=False)
        except asyncio.CancelledError:
            LOGGER.info("Indexing task was cancelled.")
            await msg.edit("Indexing process was cancelled.")
        except Exception as e:
            LOGGER.exception(e)
            await msg.edit(f"Error while indexing: {e}")
        else:
            LOGGER.info("Complete: Total files saved: %s", saved)
            await msg.edit(f"Complete: Total {saved} Files Saved To Database!")
        finally:
            index_task = None


@Client.on_callback_query(filters.regex(r"^cancel_index"))
async def cancel_indexing(bot, query):
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
            if not media:
                break
            del_file = await delete_file(media)
            if del_file == "Not Found":
                await message.reply(f"`{media.file_name}` not found in database")
            elif del_file == True:
                await message.reply(f"`{media.file_name}` deleted from database")
            else:
                await message.reply(
                    f"Error occurred while deleting `{media.file_name}`, please check logs for more info"
                )
    except Exception as e:
        LOGGER.warning("Error occurred while deleting file: %s", str(e))


@Client.on_callback_query(filters.regex(r"^can-index$"))
async def cancel_index(bot, query):
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
