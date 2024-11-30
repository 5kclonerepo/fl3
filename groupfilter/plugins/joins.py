from pyrogram import Client
from pyrogram.types import ChatMember, ChatJoinRequest
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
        fsub = admin_settings.fsub_channel if admin_settings.fsub_channel else 0
        fsub2 = admin_settings.fsub_channel2 if admin_settings.fsub_channel2 else 0
        request = admin_settings.join_req if admin_settings.join_req else None
        request2 = admin_settings.join_req2 if admin_settings.join_req2 else None
        link = admin_settings.channel_link if admin_settings.channel_link else None
        link2 = admin_settings.channel_link2 if admin_settings.channel_link2 else None
        if update.invite_link:
            inv_link = update.invite_link.invite_link
        else:
            return
        if (
            link
            or link2
            and request
            or request2
            and str(inv_link) in [str(link), str(link2)]
        ):
            if chat_id not in [int(fsub), int(fsub2)]:
                return
            user_det = await is_req_user(int(user_id), int(chat_id))
            if user_det:
                file_id = user_det.fileid
                msg_id = user_det.msg_id
                if file_id and file_id != "fsub":
                    await send_file(admin_settings, bot, update, user_id, file_id)
                try:
                    await bot.delete_messages(chat_id=user_id, message_ids=[msg_id])
                except Exception:
                    pass
                await rem_fsub_req_file(user_id, chat_id)


@Client.on_chat_member_updated()
async def new_joins(bot, update):
    # if not await member_joined(bot, update):
    #     return
    try:
        user_id = update.new_chat_member.user.id
    except AttributeError:
        return
    chat_id = update.chat.id
    admin_settings = await get_admin_settings()
    if admin_settings:
        fsub = admin_settings.fsub_channel if admin_settings.fsub_channel else 0
        fsub2 = admin_settings.fsub_channel2 if admin_settings.fsub_channel2 else 0
        link = admin_settings.channel_link if admin_settings.channel_link else None
        link2 = admin_settings.channel_link2 if admin_settings.channel_link2 else None
        if update.invite_link:
            inv_link = update.invite_link.invite_link
        else:
            return
        if link or link2 and str(inv_link) in [str(link), str(link2)]:
            if chat_id not in [int(fsub), int(fsub2)]:
                return
            user_det = await is_reg_user(int(user_id), int(chat_id))
            if user_det:
                file_id = user_det.fileid
                msg_id = user_det.msg_id
                if file_id and file_id != "fsub":
                    await send_file(admin_settings, bot, update, user_id, file_id)
                try:
                    await bot.delete_messages(chat_id=user_id, message_ids=[msg_id])
                except Exception:
                    pass
                await rem_fsub_reg_file(user_id, chat_id)
