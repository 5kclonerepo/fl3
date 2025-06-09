import os
import sys
import asyncio
import time
import shutil
import random
from psutil import cpu_percent, virtual_memory, disk_usage
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from groupfilter.db.broadcast_sql import add_user
from groupfilter.utils.constants import STARTMSG, HELPMSG
from groupfilter import (
    LOGGER,
    ADMINS,
    START_MSG,
    HELP_MSG,
    START_KB,
    PM_SUPPORT,
)
from sample_const import (
    HELP_MOD_KB,
    PROMO_HLP_MSG,
    FSUB_HLP_MSG,
    FLTR_HLP_MSG,
    BAN_HLP_MSG,
    CUST_MSG_HLP_MSG,
    CAP_HLP_MSG,
    DEL_HLP_MSG,
    INDX_HLP_MSG,
    SET_HLP_MSG,
    UTIL_HLP_MSG,
    HELP_BK_KB,
    get_start_kb,
    START_IMG
)
from groupfilter.utils.util_support import humanbytes, get_db_size
from groupfilter.plugins.serve import get_files, scheduler
from groupfilter.plugins.fsub import get_inline_fsub

if PM_SUPPORT:
    from groupfilter.plugins.serve_pm import filter_pm


@Client.on_message(filters.command(["start"]))
async def start(bot, update):
    user_id = update.from_user.id
    name = update.from_user.first_name if update.from_user.first_name else " "
    user_name = (
        "@" + update.from_user.username if update.from_user.username else None
    )
    await add_user(user_id, user_name)
    if len(update.command) == 1:
        try:
            start_msg = START_MSG.format(update.from_user.mention, bot.me.mention)
        except Exception as e:
            LOGGER.warning(e)
            start_msg = STARTMSG.format(name, user_id)

        # await bot.send_message(
        #     chat_id=update.chat.id,
        #     text=start_msg,
        #     reply_to_message_id=update.reply_to_message_id,
        #     reply_markup=get_start_kb(bot.me.username),
        # )
        strt_img = random.choice(START_IMG)
        await bot.send_photo(
            chat_id=update.chat.id,
            photo=strt_img,
            caption=start_msg,
            reply_to_message_id=update.reply_to_message_id,
            reply_markup=get_start_kb(bot.me.username),
        )
    elif len(update.command) == 2:
        try:
            src = update.command[1].split("_")
            if src[0] == "search":
                if PM_SUPPORT:
                    term = update.command[1].split("search_", 1)[-1].replace("_", " ")
                    await filter_pm(bot, update, search=term)
                else:
                    await update.reply_text(
                        text="**PM mode is deactivated**",
                        quote=True,
                    )
            elif update.command[1].startswith("fs_"):
                await get_inline_fsub(bot, update)
            else:
                await get_files(bot, update)
            await update.delete()
        except Exception as e:
            LOGGER.warning(e)


@Client.on_message(filters.command(["help"]))
async def help_m(bot, update):
    try:
        help_msg = HELP_MSG
    except Exception as e:
        LOGGER.warning(e)
        help_msg = HELPMSG

    await bot.send_message(
        chat_id=update.chat.id,
        text=help_msg,
        reply_to_message_id=update.reply_to_message_id,
        reply_markup=HELP_MOD_KB,
    )


@Client.on_callback_query(filters.regex(r"^hlp_(.+)$"))
async def help_mod(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    mod = query.data.split("_")[1]
    if mod == "promo":
        await query.message.edit_text(PROMO_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "fsub":
        await query.message.edit_text(FSUB_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "fltr":
        await query.message.edit_text(FLTR_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "ban":
        await query.message.edit_text(BAN_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "cstmsg":
        await query.message.edit_text(CUST_MSG_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "ccptn":
        await query.message.edit_text(CAP_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "del":
        await query.message.edit_text(DEL_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "indx":
        await query.message.edit_text(INDX_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "sets":
        await query.message.edit_text(SET_HLP_MSG, reply_markup=HELP_BK_KB)
    elif mod == "utls":
        await query.message.edit_text(UTIL_HLP_MSG, reply_markup=HELP_BK_KB)


@Client.on_callback_query(filters.regex(r"^back_m$"))
async def back(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    user_id = query.from_user.id
    name = query.from_user.first_name if query.from_user.first_name else " "
    try:
        start_msg = START_MSG.format(name, user_id)
    except Exception as e:
        LOGGER.warning(e)
        start_msg = STARTMSG
    try:
        await query.message.edit_text(start_msg, reply_markup=START_KB)
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^help_cb$"))
async def help_cb(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    try:
        help_msg = HELP_MSG
    except Exception as e:
        LOGGER.warning(e)
        help_msg = HELPMSG
    await query.message.edit_text(help_msg, reply_markup=HELP_MOD_KB)


@Client.on_callback_query(filters.regex(r"^helpmod_cb$"))
async def help_mod_cb(bot, query):
    try:
        await query.answer("")
    except Exception:
        pass
    await query.message.edit_text(HELP_MSG, reply_markup=HELP_MOD_KB)


@Client.on_message(filters.command(["restart"]) & filters.user(ADMINS))
async def restart(bot, update):
    LOGGER.warning("Restarting bot using /restart command")
    msg = await update.reply_text(text="__Restarting.....__")
    scheduler.shutdown(wait=False)
    await asyncio.sleep(5)
    await msg.edit("__Bot restarted !__")
    os.execv(sys.executable, ["python3", "-m", "groupfilter"] + sys.argv)


@Client.on_message(filters.command(["logs"]) & filters.user(ADMINS))
async def log_file(bot, update):
    logs_msg = await update.reply("__Sending logs, please wait...__")
    try:
        await update.reply_document("logs.txt")
    except Exception as e:
        await update.reply(str(e))
    await logs_msg.delete()


@Client.on_message(filters.command(["server"]) & filters.user(ADMINS))
async def server_stats(bot, update):
    sts = await update.reply_text("__Calculating, please wait...__")
    total, used, free = shutil.disk_usage(".")
    ram = virtual_memory()
    start_t = time.time()
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000

    ping = f"{time_taken_s:.3f} ms"
    total = humanbytes(total)
    used = humanbytes(used)
    free = humanbytes(free)
    t_ram = humanbytes(ram.total)
    u_ram = humanbytes(ram.used)
    f_ram = humanbytes(ram.available)
    cpu_usage = cpu_percent()
    ram_usage = virtual_memory().percent
    used_disk = disk_usage("/").percent
    db_size = get_db_size()

    stats_msg = f"--**BOT STATS**--\n`Ping: {ping}`\n\n--**SERVER DETAILS**--\n`Disk Total/Used/Free: {total}/{used}/{free}\nDisk usage: {used_disk}%\nRAM Total/Used/Free: {t_ram}/{u_ram}/{f_ram}\nRAM Usage: {ram_usage}%\nCPU Usage: {cpu_usage}%`\n\n--**DATABASE DETAILS**--\n`Size: {db_size} MB`"
    try:
        await sts.edit(stats_msg)
    except Exception as e:
        await update.reply_text(str(e))


@Client.on_message(filters.command(["getfileid"]) & filters.incoming & filters.private)
async def getfileid(bot, update):
    msg = update.reply_to_message
    if msg is None:
        await update.reply_text("Reply to a file to get its file_id.")
        return
    if msg.animation:
        await update.reply_text(f"File ID: `{msg.animation.file_id}`")
    elif msg.document:
        await update.reply_text(f"File ID: `{msg.document.file_id}`")
    elif msg.video:
        await update.reply_text(f"File ID: `{msg.video.file_id}`")
    elif msg.audio:
        await update.reply_text(f"File ID: `{msg.audio.file_id}`")
    elif msg.sticker:
        await update.reply_text(f"File ID: `{msg.sticker.file_id}`")
    elif msg.photo:
        await update.reply_text(f"File ID: `{msg.photo.file_id}`")
    elif msg.voice:
        await update.reply_text(f"File ID: `{msg.voice.file_id}`")
    elif msg.video_note:
        await update.reply_text(f"File ID: `{msg.video_note.file_id}`")
