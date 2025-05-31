from pyrogram import Client
from pyrogram.errors import QueryIdInvalid
from pyrogram.enums import ParseMode
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultCachedDocument,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from groupfilter.db.files_sql import get_filter_results, get_last_results
from groupfilter.db.settings_sql import get_admin_settings
from groupfilter.db.ban_sql import is_banned
# from groupfilter.utils.helpers import clean_fname, clean_se
from groupfilter.plugins.fsub import is_inline_fsub
from groupfilter import LOGGER, INLINE_ADMIN_ONLY, ADMINS


@Client.on_inline_query()
async def answer(bot, query):
    results = []
    user_id = query.from_user.id
    mention = query.from_user.mention(style=ParseMode.MARKDOWN)
    string = query.query.strip()
    offset = query.offset

    if INLINE_ADMIN_ONLY:
        if user_id not in ADMINS:
            return

    if await is_banned(user_id):
        await query.answer(
            results=[
                InlineQueryResultArticle(
                    title="You are banned to use this bot",
                    input_message_content=InputTextMessageContent(
                        "You can't use this bot",
                    ),
                )
            ],
            cache_time=1,
        )
        return


    admin_settings = await get_admin_settings()
    
    if not await is_inline_fsub(bot, query, user_id, admin_settings):
        return

    if offset == "":
        page_no = 1
    else:
        try:
            page_no = int(offset)
        except ValueError:
            page_no = 1

    try:
        files, count = await get_inline_result(search=string, page_no=page_no)
    except TypeError:
        return

    reply_markup = get_reply_markup(string)
    
    f_caption = ""
    for file in files:
        caption = file["caption"]
        file_name = file["file_name"]Add commentMore actions
        file_size = get_size(file["file_size"])
        if admin_settings["custom_caption"]:
            f_caption = admin_settings["custom_caption"]
        else:Add commentMore actions
            f_caption = f"{file['file_name']}"
            
        if "{file_name}" in f_caption:
            f_caption = f_caption.replace("{file_name}", file_name)
        if "{caption}" in f_caption:
            f_caption = f_caption.replace("{caption}", caption)
        if "{file_size}" in f_caption:
            f_caption = f_caption.replace("{file_size}", file_size)
        if "{mention}" in f_caption:
            f_caption = f_caption.replace("{mention}", mention)
            
        reply_markup = get_reply_markup(string)
        results.append(
            InlineQueryResultCachedDocument(
                title=file_name,
                document_file_id=file["file_id"],
                caption=f_caption,
                description=f'Size: {file_size}\nType: {file["file_type"]}',
                description=f'Size: {size}\nType: {file["file_type"]}',
                reply_markup=reply_markup,
            )
        )
    if results:
        switch_pm_text = f"📂 Results - {count}"
        if string:
            switch_pm_text += f" for {string}"

        next_offset = str(page_no + 1) if len(results) == 10 else ""

        try:
            await query.answer(
                results=results,
                is_personal=True,
                cache_time=10,
                switch_pm_text=switch_pm_text,
                switch_pm_parameter="start",
                next_offset=next_offset,
            )
        except QueryIdInvalid:
            pass
        except Exception as e:
            LOGGER.exception(str(e))
    else:
        switch_pm_text = "❌ No results"
        if string:
            switch_pm_text += f' for "{string}"'

        try:
            await query.answer(
                results=[],
                is_personal=True,
                cache_time=10,
                switch_pm_text=switch_pm_text,
                switch_pm_parameter="okay",
            )
        except QueryIdInvalid:
            pass
        except Exception as e:
            LOGGER.exception(str(e))


def get_reply_markup(query):
    buttons = [
        [InlineKeyboardButton("🔎 Search Again", switch_inline_query_current_chat=query)]
    ]
    return InlineKeyboardMarkup(buttons)


async def get_inline_result(search, page_no=1):
    if search.strip() == "":
        files = await get_last_results(page=page_no)
    else:
        files = await get_filter_results(query=search, page=page_no)

    if files["files"]:
        return files["files"], files["total_count"]
    return [], 0


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size)
    i = 0
    while size >= 1024.0 and i < len(units):
        i += 1
        size /= 1024.0
    return f"{size:.2f} {units[i]}"
