import asyncio
import re
import json
import random
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
    LinkPreviewOptions,
    ChatJoinRequest,
    ChatMemberUpdated,
)
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    MessageNotModified,
    ButtonDataInvalid,
    QueryIdInvalid,
    MediaEmpty,
    MessageIdInvalid,
    FloodWait,
)
from groupfilter.db.files_sql import (
    get_filter_results,
    get_file_details,
    # get_precise_filter_results,
    redis_client,
)
from groupfilter.db.settings_sql import (
    get_search_settings,
    get_admin_settings,
)
from groupfilter.db.ban_sql import is_banned
from groupfilter.db.filters_sql import is_filter
from groupfilter.db.promo_sql import get_promos
from groupfilter.plugins.fsub import is_fsub
from groupfilter.utils.helpers import clean_text, clean_fname, clean_se
from groupfilter import LOGGER, ADMINS, AUTH_GRPS, DELIVERY_CHANNELS
from __main__ import app


jobstores = {"default": SQLAlchemyJobStore(url="sqlite:///jobs.sqlite")}
scheduler = AsyncIOScheduler(jobstores=jobstores)
scheduler.start()

DELIVERY = 0


@Client.on_message(
    ~filters.regex(r"^\/") & filters.text & filters.group & filters.incoming
)
async def filter_(bot, message, search=None):
    if not message.from_user:
        return

    if AUTH_GRPS:
        if message.chat.id not in AUTH_GRPS:
            try:
                await bot.send_message(
                    message.chat.id, "This chat is not authorized to use me!!! BYE!"
                )
            except Exception:
                pass
            try:
                await bot.leave_chat(message.chat.id)
                LOGGER.info("Left unauthorized chat: %s", message.chat.id)
            except Exception:
                LOGGER.warning("Failed to leave chat: %s", message.chat.id)
            # for admin in ADMINS:
            #     try:
            #         await bot.send_message(
            #             admin,
            #             f"Left unauthorized chat.\nID:{message.chat.id}\nName: {message.chat.title}",
            #             disable_notification=True,
            #         )
            #     except Exception:
            #         pass

    user_id = message.from_user.id
    chat_id = message.chat.id

    if not search:
        if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return

    admin_settings = await get_admin_settings()
    if admin_settings:
        if admin_settings.repair_mode:
            await message.reply_text("Bot is in repair mode.", quote=True)
            return

    fltr = await is_filter(message.text)
    if fltr:
        btns = None
        if fltr.buttons:
            btn_data = json.loads(fltr.buttons)
            btns = [
                [
                    InlineKeyboardButton(text=button["text"], url=button["url"])
                    for button in row
                ]
                for row in btn_data
            ]
            btns = InlineKeyboardMarkup(btns)
        if fltr.media_type == "photo":
            await message.reply_photo(
                fltr.file_id, caption=fltr.message, reply_markup=btns
            )
        elif fltr.media_type == "video":
            await message.reply_video(
                fltr.file_id, caption=fltr.message, reply_markup=btns
            )
        elif fltr.media_type == "animation":
            await message.reply_animation(
                fltr.file_id, caption=fltr.message, reply_markup=btns
            )
        elif fltr.media_type == "sticker":
            await message.reply_sticker(fltr.file_id)
        elif fltr.media_type == "text":
            await message.reply_text(
                text=fltr.message,
                quote=True,
                reply_markup=btns,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await message.reply_text(
                "Unable to send the custom filter, please contact the admin.",
            )
        return

    src = None
    if search:
        src = await message.reply_text(
            text=f"⏳ Searching for `{search}`",
            quote=True,
        )
    elif 2 < len(message.text) < 100:
        search = message.text
        search = clean_text(search)
    else:
        return

    page_no = 1
    me = bot.me
    username = me.username
    result, btn = await get_result(search, page_no, user_id, username, chat_id)

    btn_msg = None
    nf_msg = None
    try:
        if result:
            if btn:
                btn_msg = await message.reply_text(
                    f"{result}",
                    reply_markup=InlineKeyboardMarkup(btn),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                    quote=True,
                )
            else:
                btn_msg = await message.reply_text(
                    f"{result}",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                    quote=True,
                )
        else:
            if admin_settings.notfound_msg and admin_settings.notfound_img:
                nf_msg = await message.reply_photo(
                    photo=admin_settings.notfound_img,
                    caption=admin_settings.notfound_msg,
                    quote=True,
                )
            elif admin_settings.notfound_msg and not admin_settings.notfound_img:
                nf_msg = await message.reply_text(admin_settings.notfound_msg)
            else:
                msg = "No results found.\nOr retry with the correct spelling 🤐"
                nf_msg = await message.reply_text(msg)
        if src:
            await src.delete()
    except ButtonDataInvalid as e:
        LOGGER.error(btn)
        LOGGER.error("ButtonDataInvalid: %s", str(e))
    except Exception as e:
        LOGGER.warning("Error occurred while sending message: %s", str(e))

    if admin_settings.btn_del:
        run_time = datetime.now() + timedelta(seconds=int(admin_settings.btn_del))
        trigger = DateTrigger(run_date=run_time)
        if btn_msg:
            scheduler.add_job(
                del_message,
                trigger,
                args=[btn_msg.chat.id, btn_msg.id],
                max_instances=500000,
                misfire_grace_time=200,
            )
        if nf_msg:
            scheduler.add_job(
                del_message,
                trigger,
                args=[nf_msg.chat.id, nf_msg.id],
                max_instances=500000,
                misfire_grace_time=200,
            )


@Client.on_callback_query(filters.regex(r"^(nxt_pg|prev_pg) \d+ \d+ .+$"))
async def pages(bot, query):
    if isinstance(query, CallbackQuery):
        if query.message:
            if query.message.empty:
                try:
                    await query.answer("Try with new search again", show_alert=True)
                    return
                except QueryIdInvalid:
                    return
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    org_user_id, page_no, search = query.data.split(maxsplit=3)[1:]
    org_user_id = int(org_user_id)
    page_no = int(page_no)
    me = bot.me
    username = me.username

    if org_user_id != user_id:
        try:
            await query.answer(text="Not your button")
        except QueryIdInvalid:
            return
        return
    else:
        try:
            await query.answer("")
        except QueryIdInvalid:
            pass

    result, btn = await get_result(search, page_no, user_id, username, chat_id)

    if result:
        try:
            if btn:
                await query.message.edit(
                    f"{result}",
                    reply_markup=InlineKeyboardMarkup(btn),
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            else:
                await query.message.edit(
                    f"{result}",
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
        except FloodWait as e:
            LOGGER.warning(
                "FloodWait while editing message. Sleeping for %s seconds", e.value
            )
            await asyncio.sleep(e.value)
            await pages(bot, query)
        except ButtonDataInvalid as e:
            LOGGER.error(btn)
            LOGGER.error("ButtonDataInvalid: %s", str(e))
        except (MessageNotModified, MessageIdInvalid):
            pass
    else:
        admin_settings = await get_admin_settings()
        if admin_settings.notfound_msg and admin_settings.notfound_img:
            nf_msg = await query.message.reply_photo(
                photo=admin_settings.notfound_img,
                caption=admin_settings.notfound_msg,
                quote=True,
            )
        elif admin_settings.notfound_msg and not admin_settings.notfound_img:
            nf_msg = await query.message.reply_text(admin_settings.notfound_msg)
        else:
            nf_msg = "No results found.\nOr retry with the correct spelling 🤐"
            await query.message.reply_text(nf_msg)


async def get_result(search, page_no, user_id, username, chat_id):
    search_settings = await get_search_settings(chat_id)

    if search_settings and search_settings.precise_mode:
        # files = await get_precise_filter_results(query=search, page=page_no)
        precise_search = "Enabled"
    else:
        pass

    files = await get_filter_results(query=search, page=page_no)
    precise_search = "Disabled"

    count = int(files["total_count"])

    button_mode = "ON" if search_settings and search_settings.button_mode else "OFF"
    link_mode = "ON" if search_settings and search_settings.link_mode else "OFF"
    list_mode = "ON" if search_settings and search_settings.list_mode else "OFF"

    if list_mode == "ON" and link_mode == "OFF":
        search_md = "List Button"
    elif list_mode == "OFF" and link_mode == "ON":
        search_md = "HyperLink"
    else:
        search_md = "Button"

    ads_list = await get_promos()
    if ads_list:
        ad_index = random.randint(0, len(ads_list) - 1)

    if files["files"]:
        btn = []
        index = (page_no - 1) * 10
        crnt_pg = index // 10 + 1
        tot_pg = (count + 10 - 1) // 10
        btn_count = 0
        result = f"**Search Query:** `{search}`\n**Total Results:** `{count}`\n**Page:** `{crnt_pg}/{tot_pg}`\n"
        page = page_no

        for file in files["files"]:
            file_id = file["file_id"]
            file_name = file["file_name"]
            if not file_name:
                continue
            file_name = clean_fname(file_name)
            file_name = clean_se(file_name)
            file_size = get_size(file["file_size"])
            if link_mode == "ON":
                index += 1
                btn_count += 1
                filename = f"**{index}.** [{file_name}](https://t.me/{username}/?start={file_id}_{user_id}) -\n`[{file_size}]`"
                result += "\n" + filename
                if btn_count == len(files["files"]) // 2 and ads_list:
                    current_ad = ads_list[ad_index]
                    AD_TEXT = current_ad["btn_txt"]
                    AD_URL = current_ad["link"]
                    AD_KB = f"**AD.** [{AD_TEXT}]({AD_URL})"
                    result += "\n" + AD_KB
            elif list_mode == "ON":
                index += 1
                btn_count += 1
                filename = f"**{index}.** `{file_name}` - `[{file_size}]`"
                result += "\n" + filename
                btn_kb = InlineKeyboardButton(
                    text=f"{index}", callback_data=f"file#{file_id}#{user_id}"
                )

                if btn_count == 1 or btn_count == 6:
                    btn.append([btn_kb])
                elif 6 > btn_count > 1:
                    btn[0].append(btn_kb)
                else:
                    btn[1].append(btn_kb)
            else:
                tr_f_name = trim_button_text(file_name)
                filename = f"[{file_size}] {tr_f_name}"
                btn_kb = InlineKeyboardButton(
                    text=filename,
                    callback_data=f"file#{file_id}#{user_id}",
                )
                btn.append([btn_kb])
                btn_count += 1
                if btn_count == len(files["files"]) // 2 and ads_list:
                    current_ad = ads_list[ad_index]
                    AD_TEXT = current_ad["btn_txt"]
                    AD_URL = current_ad["link"]
                    AD_KB = InlineKeyboardButton(text=f"{AD_TEXT}", url=f"{AD_URL}")
                    # ad_index = (ad_index + 1) % len(ads_list)
                    btn.append([AD_KB])

        nxt_kb_cb = trim_button_text(f"nxt_pg {user_id} {page + 1} {search}", nod=True)
        prev_kb_cb = trim_button_text(
            f"prev_pg {user_id} {page - 1} {search}", nod=True
        )

        nxt_kb = InlineKeyboardButton(
            text="Next >>",
            callback_data=nxt_kb_cb,
        )
        prev_kb = InlineKeyboardButton(
            text="<< Previous",
            callback_data=prev_kb_cb,
        )

        kb = []
        if crnt_pg == 1 and tot_pg > 1:
            kb = [nxt_kb]
        elif crnt_pg > 1 and crnt_pg < tot_pg:
            kb = [prev_kb, nxt_kb]
        elif tot_pg > 1:
            kb = [prev_kb]

        if kb:
            btn.append(kb)

        if list_mode == "ON":
            result += "\n🔻__Tap on the corresponding file number button and then start to download.__🔻"
        elif link_mode == "ON":
            result += "\n__Tap on the file name and then start to download.__"
        else:
            result += "\n🔻__Tap on the file button and then start to download.__🔻"

        return result, btn

    return None, None


@Client.on_callback_query(filters.regex(r"^file#(.+)#(\d+)$"))
async def get_files(bot, query):
    user_id = query.from_user.id
    if isinstance(query, CallbackQuery):
        if query.message:
            if query.message.empty:
                try:
                    await query.answer("Try with new search again", show_alert=True)
                    return
                except QueryIdInvalid:
                    return
        mesg = query.message
        org_user_id = query.data.split("#")[2]
        # chat_id = query.data.split("#")[3]
        if int(org_user_id) != int(user_id):
            try:            
                await query.answer(text="Not your button")
            except QueryIdInvalid:
                return
            return
        file_id = query.data.split("#")[1]
        b_username = bot.me.username
        try:
            await query.answer(
                url=f"https://t.me/{b_username}?start={file_id}_{user_id}",
            )
        except QueryIdInvalid:
            try:
                await query.message.edit_text("Please search again")
            except (MessageNotModified, MessageIdInvalid):
                pass
        return
    elif isinstance(query, Message):
        mesg = query
        file_query = query.text.split()[1]
        fid_sp = file_query.split("_")
        file_id = "_".join(fid_sp[:-1])
        if not file_id or fid_sp[0].startswith(("search", "start", " ")):
            return

        if not file_query.startswith(("search", "start")):
            org_user_id = file_query.split("_")[-1]
            try:
                if int(org_user_id) != int(user_id):
                    await query.reply_text(text="Not your button")
                    return
            except ValueError:
                return

    if await is_banned(user_id):
        await mesg.reply_text("You are banned. You can't use this bot.", quote=True)
        return

    admin_settings = await get_admin_settings()

    if not await is_fsub(bot, query, user_id, file_id, admin_settings):
        return

    await send_file(admin_settings, bot, query, user_id, file_id)


async def send_file(admin_settings, bot, query, user_id, file_id):
    global DELIVERY
    usr_msg = None
    filedetails = await get_file_details(file_id)
    f_caption = ""
    for files in filedetails:
        f_caption = files.caption
        if admin_settings.custom_caption:
            f_caption = admin_settings.custom_caption
        elif f_caption is None:
            f_caption = f"{files.file_name}"
        # f_caption = "`" + f_caption + "`"
        f_caption = "**" + f_caption + "**"

    if admin_settings.caption_uname:
        f_caption = f_caption + "\n\n" + "**" + admin_settings.caption_uname + "**"

    if isinstance(query, CallbackQuery):
        mesg = query.message
    elif isinstance(query, Message):
        mesg = query

    info = None
    if admin_settings.info_msg and admin_settings.info_img:
        if isinstance(query, (ChatJoinRequest, ChatMemberUpdated)):
            info = await bot.send_photo(
                chat_id=user_id,
                photo=admin_settings.info_img,
                caption=admin_settings.info_msg,
            )
        else:
            info = await mesg.reply_photo(
                photo=admin_settings.info_img,
                caption=admin_settings.info_msg,
                quote=True,
            )
    elif admin_settings.info_msg and not admin_settings.info_img:
        if isinstance(query, (ChatJoinRequest, ChatMemberUpdated)):
            info = await bot.send_message(user_id, admin_settings.info_msg)
        elif isinstance(query, CallbackQuery):
            info = await query.message.reply_text(admin_settings.info_msg)
        else:
            info = await query.reply_text(admin_settings.info_msg)

    try:
        if isinstance(query, (ChatJoinRequest, ChatMemberUpdated)):
            if DELIVERY_CHANNELS:
                usr_msg = await bot.send_cached_media(
                    chat_id=DELIVERY_CHANNELS[DELIVERY],
                    file_id=file_id,
                    caption=f_caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
                from_channel = usr_msg.chat.id
                msg_id = usr_msg.id
                channel_link_id = str(from_channel).replace("-100", "", 1)
                link_kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Get File", url=f"t.me/c/{channel_link_id}/{msg_id}"
                            )
                        ]
                    ]
                )
                msg = await bot.send_message(
                    chat_id=user_id,
                    text="Tap below button to get file.",
                    reply_markup=link_kb,
                )
            else:
                msg = await bot.send_cached_media(
                    chat_id=user_id,
                    file_id=file_id,
                    caption=f_caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
        else:
            if DELIVERY_CHANNELS:
                usr_msg = await bot.send_cached_media(
                    chat_id=DELIVERY_CHANNELS[DELIVERY],
                    file_id=file_id,
                    caption=f_caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
                from_channel = usr_msg.chat.id
                msg_id = usr_msg.id
                channel_link_id = str(from_channel).replace("-100", "", 1)
                link_kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Get File", url=f"t.me/c/{channel_link_id}/{msg_id}"
                            )
                        ]
                    ]
                )
                msg = await mesg.reply_text(
                    text="Tap below button to get file.",
                    reply_markup=link_kb,
                    quote=True,
                )
            else:
                msg = await mesg.reply_cached_media(
                    file_id=file_id,
                    caption=f_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    quote=True,
                )
        if DELIVERY_CHANNELS:
            if DELIVERY < len(DELIVERY_CHANNELS) - 1:
                DELIVERY += 1
            else:
                DELIVERY = 0
    except MediaEmpty:
        LOGGER.warning("File not found: %s", str(file_id))
        return
    except AttributeError:
        await query.answer("Try with new search again", show_alert=True)
        return

    if admin_settings.auto_delete:
        try:
            delay_dur = admin_settings.auto_delete
            delay = delay_dur / 60 if delay_dur > 60 else delay_dur
            delay = round(delay, 2)
            minsec = str(delay) + " mins" if delay_dur > 60 else str(delay) + " secs"
            if admin_settings.del_msg and admin_settings.del_img:
                if isinstance(query, (ChatJoinRequest, ChatMemberUpdated)):
                    disc = await bot.send_photo(
                        chat_id=user_id,
                        photo=admin_settings.del_img,
                        caption=admin_settings.del_msg,
                    )
                else:
                    disc = await msg.reply_photo(
                        photo=admin_settings.del_img,
                        caption=admin_settings.del_msg,
                        quote=True,
                    )
            elif admin_settings.del_msg and not admin_settings.del_img:
                del_msg = admin_settings.del_msg
                if isinstance(query, (ChatJoinRequest, ChatMemberUpdated)):
                    disc = await bot.send_message(user_id, del_msg)
                else:
                    disc = await msg.reply_text(del_msg)
            else:
                del_msg = f"Please save the file to your saved messages, it will be deleted in {minsec}"
                if isinstance(query, (ChatJoinRequest, ChatMemberUpdated)):
                    disc = await bot.send_message(user_id, del_msg)
                else:
                    disc = await msg.reply_text(del_msg)
            run_time = datetime.now() + timedelta(seconds=int(delay_dur))
            trigger = DateTrigger(run_date=run_time)
            if info:
                scheduler.add_job(
                    del_message,
                    trigger,
                    args=[info.chat.id, info.id],
                    max_instances=500000,
                    misfire_grace_time=100,
                )
            txt = "File has been deleted"
            scheduler.add_job(
                del_message,
                trigger,
                args=[msg.chat.id, msg.id, txt],
                max_instances=500000,
                misfire_grace_time=100,
            )
            scheduler.add_job(
                del_message,
                trigger,
                args=[disc.chat.id, disc.id],
                max_instances=500000,
                misfire_grace_time=200,
            )
            if usr_msg:
                scheduler.add_job(
                    del_message,
                    trigger,
                    args=[usr_msg.chat.id, usr_msg.id],
                    max_instances=500000,
                    misfire_grace_time=200,
                )
        except AttributeError as e:
            LOGGER.warning("Error occurred while deleting file: %s", str(e))


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return f"{size:.2f} {units[i]}"


@Client.on_message(
    filters.private & filters.command(["clearcache"]) & filters.user(ADMINS)
)
async def clear_cache(bot, message=None, mess=True):
    redis_client.flushall()
    if mess:
        LOGGER.warning("Stored cache cleared")
        await message.reply_text("Stored cache cleared", quote=True)


async def del_message(chat_id: int, message_id: int, txt=None):
    try:
        await app.delete_messages(chat_id=chat_id, message_ids=message_id)
        if txt:
            await app.send_message(chat_id=chat_id, text=txt)
    except Exception as e:
        LOGGER.warning(
            "Failed to delete message: %s : %s : %s", chat_id, message_id, str(e)
        )


def trim_button_text(text, nod=False, max_length=64):
    if len(text) > max_length:
        if nod:
            return text[:max_length]
        return text[: max_length - 3] + "..."
    return text
