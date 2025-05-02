import re
import json
import asyncio
import random
from datetime import datetime, timedelta
from apscheduler.triggers.date import DateTrigger
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
    LinkPreviewOptions,
)
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    MessageNotModified,
    ButtonDataInvalid,
    MediaEmpty,
    QueryIdInvalid,
    MessageIdInvalid,
    FloodWait,
    UserIsBlocked,
)
from groupfilter.db.files_sql import (
    get_filter_results,
    get_file_details,
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
from groupfilter.plugins.serve import scheduler, del_message, get_size, trim_button_text
from groupfilter import LOGGER, DELIVERY_CHANNELS


DELIVERY = 0


@Client.on_message(
    ~filters.regex(r"^\/") & filters.text & filters.incoming & filters.private
)
async def filter_pm(bot, message, search=None):
    if not message.from_user:
        return

    user_id = message.from_user.id
    chat_id = message.chat.id

    if not search:
        if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return

    admin_settings = await get_admin_settings()
    if admin_settings:
        if admin_settings["repair_mode"]:
            await message.reply_text("Bot is in repair mode.", quote=True)
            return

    fltr = await is_filter(message.text)
    if fltr:
        btns = None
        if fltr["buttons"]:
            btn_data = json.loads(fltr["buttons"])
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
                fltr["file_id"], caption=fltr["message"], reply_markup=btns
            )
        elif fltr["media_type"] == "video":
            await message.reply_video(
                fltr["file_id"], caption=fltr["message"], reply_markup=btns
            )
        elif fltr["media_type"] == "animation":
            await message.reply_animation(
                fltr["file_id"], caption=fltr["message"], reply_markup=btns
            )
        elif fltr["media_type"] == "sticker":
            await message.reply_sticker(fltr["file_id"])
        elif fltr["media_type"] == "text":
            await message.reply_text(
                text=fltr["message"],
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
        try:
            src = await message.reply_text(
                text=f"⏳ Searching for `{search}`",
                quote=True,
            )
        except UserIsBlocked:
            return

    elif 2 < len(message.text) < 100:
        search = message.text
        search = clean_text(search)
    else:
        return

    page_no = 1
    me = bot.me
    username = me.username
    result, btn = await get_pm_result(search, page_no, user_id, username, chat_id)

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
            if admin_settings["notfound_msg"] and admin_settings["notfound_img"]:
                nf_msg = await message.reply_photo(
                    photo=admin_settings["notfound_img"],
                    caption=admin_settings["notfound_msg"],
                    quote=True,
                )
            elif admin_settings["notfound_msg"] and not admin_settings["notfound_img"]:
                nf_msg = await message.reply_text(admin_settings["notfound_msg"])
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

    if admin_settings["btn_del"]:
        run_time = datetime.now() + timedelta(seconds=int(admin_settings["btn_del"]))
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


@Client.on_callback_query(filters.regex(r"^(nxt_pgg|prev_pgg) \d+ \d+ .+$"))
async def pages(bot, query):
    user_id = query.from_user.id
    chat_id = query.message.chat.id
    org_user_id, page_no, search = query.data.split(maxsplit=3)[1:]
    org_user_id = int(org_user_id)
    page_no = int(page_no)
    me = bot.me
    username = me.username

    if org_user_id != user_id:
        await query.answer(text="Not your button")
        return
    else:
        try:
            await query.answer("")
        except Exception:
            pass

    result, btn = await get_pm_result(search, page_no, user_id, username, chat_id)

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
        if admin_settings["notfound_msg"] and admin_settings["notfound_img"]:
            nf_msg = await query.message.reply_photo(
                photo=admin_settings["notfound_img"],
                caption=admin_settings["notfound_msg"],
                quote=True,
            )
        elif admin_settings["notfound_msg"] and not admin_settings["notfound_img"]:
            nf_msg = await query.message.reply_text(admin_settings["notfound_msg"])
        else:
            nf_msg = "No results found.\nOr retry with the correct spelling 🤐"
            await query.message.reply_text(nf_msg)


async def get_pm_result(search, page_no, user_id, username, chat_id):
    search_settings = await get_search_settings(chat_id)
    files = await get_filter_results(query=search, page=page_no)
    count = int(files["total_count"])

    button_mode = "ON" if search_settings and search_settings["button_mode"] else "OFF"
    link_mode = "ON" if search_settings and search_settings["link_mode"] else "OFF"

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
            file_name = clean_fname(file_name)
            file_name = clean_se(file_name)
            file_size = get_size(file["file_size"])
            if link_mode == "ON":
                index += 1
                btn_count += 1
                filename = f"**{index}.** [{file_name}](https://t.me/{username}/?start=pm_{file_id}) -\n`[{file_size}]`"
                result += "\n" + filename
                if btn_count == len(files["files"]) // 2 and ads_list:
                    current_ad = ads_list[ad_index]
                    AD_TEXT = current_ad["text"]
                    AD_URL = current_ad["link"]
                    AD_KB = f"**AD.** [{AD_TEXT}]({AD_URL})"
                    result += "\n" + AD_KB
            else:
                tr_f_name = trim_button_text(file_name)
                filename = f"[{file_size}] {tr_f_name}"
                btn_kb = InlineKeyboardButton(
                    text=filename,
                    callback_data=f"pmfile#{file_id}",
                )
                btn.append([btn_kb])
                btn_count += 1
                if btn_count == len(files["files"]) // 2 and ads_list:
                    current_ad = ads_list[ad_index]
                    AD_TEXT = current_ad["text"]
                    AD_URL = current_ad["link"]
                    AD_KB = InlineKeyboardButton(text=f"{AD_TEXT}", url=f"{AD_URL}")
                    # ad_index = (ad_index + 1) % len(ads_list)
                    btn.append([AD_KB])

        nxt_kb_cb = trim_button_text(f"nxt_pgg {user_id} {page + 1} {search}", nod=True)
        prev_kb_cb = trim_button_text(
            f"prev_pgg {user_id} {page - 1} {search}", nod=True
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

        if link_mode == "ON":
            result += "\n__Tap on the file name and then start to download.__"
        else:
            result += "\n🔻__Tap on the file button and then start to download.__🔻"

        return result, btn

    return None, None


@Client.on_callback_query(filters.regex(r"^pmfile#(.+)$"))
async def get_pm_files(bot, query):
    user_id = query.from_user.id
    if isinstance(query, CallbackQuery):
        cbq = True
        try:
            file_id = query.data.split("#")[1]
            await query.answer("Sending file...", cache_time=10)
        except QueryIdInvalid:
            await bot.send_message(
                user_id,
                text="Please don't spam the buttons or search again as the button you tapped might have been been expired if it is an old one.",
                reply_to_message_id=query.message.reply_to_message_id,
            )
    elif isinstance(query, Message):
        cbq = False
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

    await send_pm_file(admin_settings, bot, query, user_id, file_id, cbq)


async def send_pm_file(admin_settings, bot, query, user_id, file_id, cbq):
    filedetails = await get_file_details(file_id)
    f_caption = ""
    usr_msg = None
    for files in filedetails:
        caption = files["caption"]
        file_name = files["file_name"]
        file_size = get_size(files["file_size"])
        if admin_settings["custom_caption"]:
            f_caption = admin_settings["custom_caption"]
        else:
            f_caption = f"{files['file_name']}"

    if admin_settings["caption_uname"]:
        f_caption = f_caption + "\n\n" + admin_settings["caption_uname"]

    if "{file_name}" in f_caption:
        f_caption = f_caption.replace("{file_name}", file_name)
    if "{caption}" in f_caption:
        f_caption = f_caption.replace("{caption}", caption)
    if "{file_size}" in f_caption:
        f_caption = f_caption.replace("{file_size}", file_size)

    info = None
    if admin_settings["info_msg"] and admin_settings["info_img"]:
        if cbq:
            info = await query.message.reply_photo(
                chat_id=user_id,
                photo=admin_settings["info_img"],
                caption=admin_settings["info_msg"],
            )
        else:
            info = await query.reply_photo(
                photo=admin_settings["info_img"],
                caption=admin_settings["info_msg"],
                quote=True,
            )
    elif admin_settings["info_msg"] and not admin_settings["info_img"]:
        if cbq:
            info = await query.message.reply_text(admin_settings["info_msg"])
        else:
            info = await query.reply_text(admin_settings["info_msg"])

    try:
        if cbq:
            if DELIVERY_CHANNELS:
                delcn = DELIVERY_CHANNELS[DELIVERY]
                try:
                    usr_msg = await bot.send_cached_media(
                        chat_id=delcn,
                        file_id=file_id,
                        caption=f_caption,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    LOGGER.warning("Error occurred while sending file: %s : Channel - %s", str(e), delcn)
                    if DELIVERY < len(DELIVERY_CHANNELS) - 1:
                        DELIVERY += 1
                    else:
                        DELIVERY = 0
                    delcn = DELIVERY_CHANNELS[DELIVERY]
                    usr_msg = await bot.send_cached_media(
                        chat_id=delcn,
                        file_id=file_id,
                        caption=f_caption,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                from_channel = usr_msg.chat.id
                msg_id = usr_msg.id
                try:
                    clink = int(delcn)
                    channel_link_id = str(clink).replace("-100", "", 1)
                    url=f"t.me/c/{channel_link_id}/{msg_id}"
                except Exception:
                    channel_link = delcn
                    url=f"t.me/{channel_link}/{msg_id}"
                link_kb = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "Get File", url=url
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
                delcn = DELIVERY_CHANNELS[DELIVERY]
                try:
                    usr_msg = await bot.send_cached_media(
                        chat_id=delcn,
                        file_id=file_id,
                        caption=f_caption,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    LOGGER.warning("Error occurred while sending file: %s : Channel - %s", str(e), delcn)
                    if DELIVERY < len(DELIVERY_CHANNELS) - 1:
                        DELIVERY += 1
                    else:
                        DELIVERY = 0
                    delcn = DELIVERY_CHANNELS[DELIVERY]
                    usr_msg = await bot.send_cached_media(
                        chat_id=delcn,
                        file_id=file_id,
                        caption=f_caption,
                        parse_mode=ParseMode.MARKDOWN,
                    )
            else:
                msg = await query.message.reply_cached_media(
                    file_id=file_id,
                    caption=f_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    quote=True,
                )
    except MediaEmpty:
        LOGGER.warning("File not found: %s", str(file_id))
        return
    except AttributeError:
        await query.answer("Try with new search again", show_alert=True)
        return

    if admin_settings["auto_delete"]:
        try:
            usr_msg = None
            delay_dur = admin_settings["auto_delete"]
            delay = delay_dur / 60 if delay_dur > 60 else delay_dur
            delay = round(delay, 2)
            minsec = str(delay) + " mins" if delay_dur > 60 else str(delay) + " secs"
            if admin_settings["del_msg"] and admin_settings["del_img"]:
                disc = await msg.reply_photo(
                    photo=admin_settings["del_img"],
                    caption=admin_settings["del_msg"],
                    quote=True,
                )
            elif admin_settings["del_msg"] and not admin_settings["del_img"]:
                del_msg = admin_settings["del_msg"]
                disc = await msg.reply_text(del_msg)
            else:
                del_msg = f"Please save the file to your saved messages, it will be deleted in {minsec}"
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
