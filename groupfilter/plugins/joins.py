from pyrogram import Client
from pyrogram.types import ChatMember
from groupfilter import LOGGER
from groupfilter.plugins.serve import send_file
from groupfilter.db.settings_sql import get_admin_settings
from groupfilter.db.fsub_sql import (
    rem_fsub_req_file,
    rem_fsub_reg_file,
    is_req_user,
    is_reg_user,
)


@Client.on_chat_join_request()
async def new_join_req(bot, update):
    chat_id = update.chat.id
    user_id = update.from_user.id
    admin_settings = await get_admin_settings()
    if admin_settings:
        fsub = admin_settings.fsub_channel
        request = admin_settings.join_req
        link = admin_settings.channel_link
        if link and request:
            if int(fsub) != chat_id:
                return
            user_det = await is_req_user(int(user_id), int(chat_id))
            if user_det:
                file_id = user_det.fileid
                await send_file(admin_settings, bot, update, user_id, file_id)
                await rem_fsub_req_file(user_id, chat_id)
            else:
                LOGGER.info(
                    "Unable to find user details from db: %s : %s. Skipping file send.",
                    str(chat_id),
                    str(user_id),
                )


@Client.on_chat_member_updated()
async def new_joins(bot, update):
    # if not await member_joined(bot, update):
    #     return
    try:
        user_id = update.new_chat_member.user.id
    except AttributeError:
        return
    chat_id = update.chat.id
    fsub = None
    admin_settings = await get_admin_settings()
    if admin_settings:
        fsub = admin_settings.fsub_channel
        link = admin_settings.channel_link
        if link:
            if int(fsub) != chat_id:
                return
            user_det = await is_reg_user(int(user_id), int(chat_id))
            if user_det:
                file_id = user_det.fileid
                await send_file(admin_settings, bot, update, user_id, file_id)
                await rem_fsub_reg_file(user_id, chat_id)
            else:
                LOGGER.info(
                    "Unable to find user details from db: %s : %s",
                    str(chat_id),
                    str(user_id),
                )


async def member_joined(bot, update):
    result = await on_status_change(bot, update)
    if result is None:
        return False
    was_member, is_member = result
    if was_member or not is_member:
        return False
    return True


async def on_status_change(bot, update):
    old_chat_member = update.old_chat_member
    new_chat_member = update.new_chat_member

    try:
        old_status = old_chat_member.status
    except AttributeError:
        old_status = None

    try:
        new_status = new_chat_member.status
    except AttributeError:
        new_status = None

    try:
        old_is_member = old_status in [
            ChatMember.MEMBER,
            ChatMember.OWNER,
            ChatMember.ADMINISTRATOR,
        ] or (old_status == ChatMember.RESTRICTED and old_chat_member.is_member)
    except AttributeError:
        old_is_member = False

    try:
        new_is_member = new_status in [
            ChatMember.MEMBER,
            ChatMember.OWNER,
            ChatMember.ADMINISTRATOR,
        ] or (new_status == ChatMember.RESTRICTED and new_chat_member.is_member)
    except AttributeError:
        new_is_member = False

    if old_status == new_status and old_is_member == new_is_member:
        return None

    return old_is_member, new_is_member
