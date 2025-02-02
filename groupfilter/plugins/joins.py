from pyrogram import Client
from groupfilter import LOGGER
from groupfilter.plugins.serve import send_file
from groupfilter.db.settings_sql import get_admin_settings
from groupfilter.db.fsub_sql import (
    get_force_sub,
    update_force_sub,
    get_act_force_subs_count,
    get_nxt_pen_force_sub,
    rem_fsub_req_file,
    rem_fsub_reg_file,
    is_req_user,
    is_reg_user,
)
from groupfilter.utils.util_support import notify_admins


@Client.on_chat_join_request()
async def new_join_req(bot, update):
    curr_chat_id = update.chat.id
    user_id = update.from_user.id
    fsub = await get_force_sub(curr_chat_id)
    if fsub:
        if fsub.is_active:
            admin_settings = await get_admin_settings()
            link = fsub.chat_link
            join_count = fsub.join_count
            target = fsub.target
            if update.invite_link and link == update.invite_link.invite_link:
                user_det = await is_req_user(int(user_id), int(curr_chat_id))
                if user_det:
                    join_count = update.invite_link.pending_join_request_count
                    await process_fsub(
                        bot, update, curr_chat_id, join_count, target, link
                    )
                    LOGGER.debug(
                        f"Req: {curr_chat_id} : {user_id} : {join_count} : {link} : {update.invite_link.pending_join_request_count}"
                    )
                    file_id = user_det.fileid
                    msg_id = user_det.msg_id
                    if file_id and file_id != "fsub":
                        await send_file(admin_settings, bot, update, user_id, file_id)
                    try:
                        await bot.delete_messages(chat_id=user_id, message_ids=[msg_id])
                    except Exception:
                        pass
                    await rem_fsub_req_file(user_id, curr_chat_id)
        else:
            await process_pending_fsub(bot)


@Client.on_chat_member_updated()
async def new_joins(bot, update):
    try:
        user_id = update.new_chat_member.user.id
    except AttributeError:
        return
    curr_chat_id = update.chat.id
    fsub = await get_force_sub(curr_chat_id)
    if fsub:
        if fsub.is_active:
            admin_settings = await get_admin_settings()
            link = fsub.chat_link
            join_count = fsub.join_count
            target = fsub.target
            if update.invite_link and link == update.invite_link.invite_link:
                user_det = await is_reg_user(int(user_id), int(curr_chat_id))
                if user_det:
                    join_count += 1
                    await process_fsub(
                        bot, update, curr_chat_id, join_count, target, link
                    )
                    LOGGER.debug(
                        f"Join: {curr_chat_id} : {user_id} : {join_count} : {link}"
                    )
                    file_id = user_det.fileid
                    msg_id = user_det.msg_id
                    if file_id and file_id != "fsub":
                        await send_file(admin_settings, bot, update, user_id, file_id)
                    try:
                        await bot.delete_messages(chat_id=user_id, message_ids=[msg_id])
                    except Exception:
                        pass
                    await rem_fsub_reg_file(user_id, curr_chat_id)
        else:
            await process_pending_fsub(bot)


async def process_fsub(bot, update, curr_chat_id, join_count, target, link):
    if target and join_count >= target:
        await update_force_sub(
            chat_id=curr_chat_id,
            join_count=join_count,
            is_done=True,
            is_active=False,
            is_queue=False,
        )
        await bot.revoke_chat_invite_link(chat_id=curr_chat_id, invite_link=link)
        LOGGER.info(
            "Force Sub channel %s has been completed and removed from active list with joins %s.",
            curr_chat_id,
            join_count,
        )
        msg = f">**Force Sub Completed - Removed from active list.**\n**Chat ID:** `{curr_chat_id}`\n**Join Count:** `{join_count}`\n**Revoked invite:** {link}"
        await notify_admins(bot, msg)
    else:
        await update_force_sub(curr_chat_id, join_count=join_count)


async def process_pending_fsub(bot):
    penfsub = await get_nxt_pen_force_sub()
    actfsubcount = await get_act_force_subs_count()
    admin_settings = await get_admin_settings()
    if admin_settings:
        if admin_settings.fsub_channel:
            if actfsubcount:
                if actfsubcount >= admin_settings.fsub_channel:
                    return False

    if penfsub:
        await update_force_sub(chat_id=penfsub.chat_id, is_active=True, is_queue=False)
        LOGGER.info(
            "Force Sub channel %s has been added to active list.",
            penfsub.chat_id,
        )
        msg = f"\n>**Force Sub Auto Added From Queue:**\n**Chat ID:** `{penfsub.chat_id}`\n**Name:** `{penfsub.chat_title}`\n**Link:** {penfsub.chat_link}\n**Join Request:** `{penfsub.is_req}`\n**Target:** `{penfsub.target}`"
        await notify_admins(bot, msg)
        return True
