from pyrogram import Client, filters
from pyrogram.errors import QueryIdInvalid
from groupfilter import PM_SUPPORT, GROUP_SUPPORT, LOGGER


if not PM_SUPPORT and GROUP_SUPPORT:

    @Client.on_callback_query(filters.regex(r"^pmfile#(.+)$"))
    async def get_pm_files_qry_hndlr(bot, query):
        if not query.message:
            try:
                await query.answer("")
            except Exception:
                pass
            return
        try:
            await query.answer("PM mode is disabled", cache_time=10)
        except QueryIdInvalid:
            return

    @Client.on_callback_query(filters.regex(r"^(nxt_pgg|prev_pgg) \d+ \d+ .+$"))
    async def pages_pm_qry_hndlr(bot, query):
        if not query.message:
            try:
                await query.answer("")
            except Exception:
                pass
            return
        try:
            await query.answer("PM mode is disabled", cache_time=10)
        except QueryIdInvalid:
            return


if not GROUP_SUPPORT and PM_SUPPORT:

    @Client.on_callback_query(filters.regex(r"^file#(.+)#(\d+)$"))
    async def get_files_qry_hndlr(bot, query):
        if not query.message:
            try:
                await query.answer("")
            except Exception:
                pass
            return
        try:
            await query.answer("Group mode is disabled", cache_time=10)
        except QueryIdInvalid:
            return

    @Client.on_callback_query(filters.regex(r"^(nxt_pg|prev_pg) \d+ \d+ .+$"))
    async def pages_qry_hndlr(bot, query):
        if not query.message:
            try:
                await query.answer("")
            except Exception:
                pass
            return
        try:
            await query.answer("Group mode is disabled", cache_time=10)
        except QueryIdInvalid:
            return


@Client.on_callback_query()
async def general_callback_handler(bot, query):
    chat_info = f"{query.message.chat.id} | {query.message.chat.title}" if query.message and hasattr(query.message, 'chat') else "Unknown chat"
    LOGGER.debug(
        f"General handler received callback from {query.from_user.id} | {query.from_user.first_name} | Chat: {chat_info} | Data: {query.data}"
    )
    try:
        await query.answer()
        LOGGER.debug(f"Successfully answered callback query: {query.id}")
    except Exception as e:
        LOGGER.error(f"Error acknowledging callback {query.id}: {e}")
