from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.errors import UserNotParticipant
from groupfilter import LOGGER, ADMINS
from groupfilter.db.fsub_sql import (
    add_fsub_req_user,
    is_req_user,
    add_fsub_reg_user,
    remove_fsub_users,
)


async def check_fsub(
    bot, message, force_sub, link, request, user_id, file_id, admin_settings
):
    if isinstance(message, CallbackQuery):
        msg = message.message
    else:
        msg = message

    if admin_settings:
        if admin_settings.fsub_msg:
            fsub_msg = admin_settings.fsub_msg
            txt = fsub_msg
        else:
            txt = "**Please join below channel to get file!**"
        if admin_settings.fsub_img:
            fsub_img = admin_settings.fsub_img
    try:
        user = await bot.get_chat_member(int(force_sub), user_id)
        if user.status == ChatMemberStatus.BANNED:
            await msg.reply_text("Sorry, you are Banned to use me.", quote=True)
            return False
    except UserNotParticipant:
        if request:
            user_det = await is_req_user(int(user_id), int(force_sub))
            if user_det:
                if not user_det.fileid:
                    return True
            await add_fsub_req_user(int(user_id), int(force_sub), file_id)
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⚓ Request to Join", url=link)],
                ]
            )
        else:
            await add_fsub_reg_user(user_id, force_sub, file_id)
            kb = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("⚓ Join Channel", url=link)],
                    # [InlineKeyboardButton("♻️ Refresh", callback_data="joinref")],
                ]
            )
        if admin_settings:
            if admin_settings.fsub_msg and admin_settings.fsub_img:
                await msg.reply_photo(
                    photo=fsub_img,
                    caption=txt,
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN,
                    quote=True,
                )
                return False
            elif admin_settings.fsub_msg and not admin_settings.fsub_img:
                await msg.reply_text(
                    text=txt,
                    reply_markup=kb,
                    parse_mode=ParseMode.MARKDOWN,
                    quote=True,
                )
                return False
            else:
                await msg.reply_text(txt, reply_markup=kb, quote=True)
                return False
    except Exception as e:
        LOGGER.warning(e)
        await msg.reply_text(
            text="Something went wrong, please contact my support group",
            quote=True,
        )
        return False
    return True


@Client.on_message(filters.command(["clearfsubusers"]) & filters.user(ADMINS))
async def log_file(bot, message):
    rem = await remove_fsub_users()
    if rem:
        await message.reply_text("All fsub users removed from database")
    else:
        await message.reply_text("No fsub users found in database")
