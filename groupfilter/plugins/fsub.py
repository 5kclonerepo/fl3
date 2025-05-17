from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery,
    Message,
    LinkPreviewOptions,
)
from pyrogram.enums import ParseMode, ChatMemberStatus
from pyrogram.errors import UserNotParticipant, QueryIdInvalid, UserIsBlocked
from groupfilter import LOGGER, ADMINS
from groupfilter.db.fsub_sql import (
    set_force_sub,
    get_force_sub,
    update_force_sub,
    get_pen_force_subs,
    get_nxt_pen_force_sub,
    get_act_force_subs_count,
    get_active_force_subs,
    get_all_force_subs,
    rm_force_sub,
    clear_force_subs,
    add_fsub_req_user,
    is_req_user,
    add_fsub_reg_user,
    remove_fsub_users,
    get_fsubreq_users_count,
    get_fsubreg_users_count,
)
from groupfilter.db.settings_sql import get_admin_settings
from groupfilter.utils.util_support import notify_admins


@Client.on_message(
    filters.private & filters.command(["setfsub"]) & filters.user(ADMINS)
)
async def force_sub(bot, message):
    data = message.text.split()
    chat_id = message.chat.id
    if len(data) == 2:
        channel = data[-1]
    else:
        await message.reply_text(
            "Please send in proper format `/setfsub channel_id`", quote=True
        )
        return

    if not channel.startswith("-100"):
        await message.reply_text("Please check channel ID again", quote=True)
        return

    exists = await get_force_sub(chat_id=channel)
    if exists:
        await message.reply_text(
            "Channel already exists in Force Subscription list, use /rmfsub to remove",
            quote=True,
        )
        return

    fsub_conf = await message.reply_text(
        "Please confirm that you want to set Request or Regular Force Subscription",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🙏 Request", callback_data="cfs_req"),
                    InlineKeyboardButton("🫂 Regular", callback_data="cfs_reg"),
                ]
            ]
        ),
    )

    try:
        conf_cb = await bot.listen_callback(chat_id, fsub_conf.id, timeout=300)
    except TimeoutError:
        await fsub_conf.reply_text(
            "Request timed out, please /start again.", quote=True
        )
        return

    if conf_cb.data == "cfs_req":
        reqc = True
    elif conf_cb.data == "cfs_reg":
        reqc = False

    await fsub_conf.delete()
    limit_conf = await message.reply_text(
        "Please confirm that you want to set joining members limit.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Yes", callback_data="lim_yes"),
                    InlineKeyboardButton("❌ No", callback_data="lim_no"),
                ]
            ]
        ),
    )

    try:
        lim_cb = await bot.listen_callback(message.chat.id, limit_conf.id, timeout=300)
    except TimeoutError:
        await limit_conf.reply_text(
            "Request timed out, please /start again.", quote=True
        )
        return

    await limit_conf.delete()
    if lim_cb.data == "lim_yes":
        lim_cnt = await bot.send_message(
            chat_id,
            "Please enter the target number of members to join the channel.",
        )
        try:
            lim_txt = await bot.listen_message(
                message.chat.id, filters=filters.text, timeout=300
            )
        except TimeoutError:
            await lim_cnt.reply_text(
                "Request timed out, please /start again.", quote=True
            )
            return
        limit = int(lim_txt.text)
        await lim_cnt.delete()
    else:
        limit = 0

    try:
        limit = int(limit)
    except ValueError:
        await message.reply_text(
            "Please enter a valid number. Start the process again.", quote=True
        )
        return

    act_conf = await message.reply_text(
        "Please confirm that if you want to enable it now or put in the queue.",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🤝 Enable Now", callback_data="ena_yes"),
                    InlineKeyboardButton("🫷 Put In Queue", callback_data="ena_no"),
                ]
            ]
        ),
    )

    try:
        lim_cb = await bot.listen_callback(message.chat.id, act_conf.id, timeout=300)
    except TimeoutError:
        await act_conf.reply_text("Request timed out, please /start again.", quote=True)
        return

    if lim_cb.data == "ena_yes":
        act = True
        que = False
    else:
        act = False
        que = True

    await act_conf.delete()
    try:
        link = await bot.create_chat_invite_link(
            int(channel), creates_join_request=reqc
        )
        LOGGER.info(
            "Created invite link for %s : Req: %s : Details: %s", channel, reqc, link
        )
        inv_link = link.invite_link
    except Exception as e:
        LOGGER.error("Error creating invite link for %s: %s", channel, e)
        await message.reply_text(
            f" Error while creating channel invite link: {str(e)}", quote=True
        )
        return

    try:
        chat = await bot.get_chat(int(channel))
        name = chat.title
    except Exception as e:
        await message.reply_text(
            f" Error while getting channel name: {str(e)}", quote=True
        )
        return

    set_sub = await set_force_sub(
        chat_id=int(channel),
        chat_title=name,
        chat_link=inv_link,
        join_count=0,
        target=limit,
        is_req=link.creates_join_request,
        is_active=act,
        is_queue=que,
    )
    status = "Active Now" if act else "In Queue" if que else "Unable to Find"
    if set_sub:
        await message.reply_text(
            f">**Force Subscription Set:-**\n**Chat ID:** `{channel}`\n**Chat Name:** `{name}`\n**Invite link:** {link.invite_link}\n**Join Request:** `{link.creates_join_request}` \n**Target:** `{limit}` \n**Status** `{status}`",
            quote=True,
        )
    else:
        await message.reply_text(
            "Failed to set Force Subscription, please try again or check logs for more info.",
            quote=True,
        )


@Client.on_message(filters.private & filters.command(["rmfsub"]) & filters.user(ADMINS))
async def rm_fsub(bot, message):
    data = message.text.split()
    if len(data) == 2:
        channel = data[-1]
    else:
        await message.reply_text(
            "Please send in proper format `/setfsub channel_id`", quote=True
        )
        return

    if not channel.startswith("-100"):
        await message.reply_text("Please check channel ID again", quote=True)
        return

    rm_sub = await rm_force_sub(int(channel))
    if rm_sub:
        await message.reply_text(
            f"Force Subscription channel `{channel}` removed", quote=True
        )
    else:
        await message.reply_text(
            "Failed to remove Force Subscription, please try again or check logs for more info.",
            quote=True,
        )


@Client.on_message(
    filters.private & filters.command(["rmallfsub"]) & filters.user(ADMINS)
)
async def rm_all_fsub(bot, message):
    clear_ms = await message.reply_text(
        "Please conifirm that you want to remove all Force Subscription channels",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Yes", callback_data="rm_all_yes"),
                    InlineKeyboardButton("❌ No", callback_data="rm_all_no"),
                ]
            ]
        ),
    )
    try:
        clear_cb = await bot.listen_callback(message.chat.id, clear_ms.id, timeout=300)
    except TimeoutError:
        await clear_ms.reply_text("Request timed out, please /start again.", quote=True)
        return
    if clear_cb.data == "rm_all_no":
        await clear_ms.edit_text("Operation Cancelled")
        return

    await clear_ms.delete()
    rm_sub = await clear_force_subs()
    if rm_sub:
        await message.reply_text("All Force Subscription channels removed", quote=True)
    else:
        await message.reply_text(
            "Failed to remove Force Subscription, please try again or check logs for more info.",
            quote=True,
        )


@Client.on_message(
    filters.private & filters.command(["getallfsub"]) & filters.user(ADMINS)
)
async def get_all_fsub(bot, message):
    all_sub = await get_all_force_subs()
    if all_sub:
        msg = ""
        active = "**✧ Active Now:-**\n"
        que = "**✧ In Queue:-**\n"
        comp = "**✧ Completed:-**\n"
        for sub in all_sub:
            if sub["is_done"]:
                comp += f">✧ **Chat ID:**`{sub['chat_id']}`\n>**Name:** `{sub['chat_title']}`\n>**Link:** {sub['chat_link']}\n>**Join Request:** `{sub['is_req']}`\n>**Joins:** `{sub['join_count']}`\n>**Target:** `{sub['target']}`\n>**Remove:** `/rmfsub {sub['chat_id']}`\n\n"
            if sub["is_queue"]:
                que += f">✧ **Chat ID:**`{sub['chat_id']}`\n>**Name:** `{sub['chat_title']}`\n>**Link:** {sub['chat_link']}\n>**Join Request:** `{sub['is_req']}`\n>**Joins:** `{sub['join_count']}`\n>**Target:** `{sub['target']}`\n>**Remove:** `/rmfsub {sub['chat_id']}`\n\n"
            if sub["is_active"]:
                active += f">✧ **Chat ID:**`{sub['chat_id']}`\n>**Name:** `{sub['chat_title']}`\n>**Link:** {sub['chat_link']}\n>**Join Request:** `{sub['is_req']}`\n>**Joins:** `{sub['join_count']}`\n>**Target:** `{sub['target']}`\n>**Remove:** `/rmfsub {sub['chat_id']}`\n\n"
            msg = active + que + comp
        await message.reply_text(
            msg, quote=True, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    else:
        await message.reply_text(
            "No Force Subscription channels found in database", quote=True
        )


@Client.on_message(
    filters.private & filters.command(["getactivefsub"]) & filters.user(ADMINS)
)
async def get_active_fsub(bot, message):
    all_sub = await get_active_force_subs()
    if all_sub:
        msg = ""
        for sub in all_sub:
            msg += f">✧ **Chat ID:**`{sub['chat_id']}`\n>**Name:** `{sub['chat_title']}`\n>**Link:** {sub['chat_link']}\n>**Join Request:** `{sub['is_req']}`\n>**Joins:** `{sub['join_count']}`\n>**Target:** `{sub['target']}`\n>**Remove:** `/rmfsub {sub['chat_id']}`\n\n"
        await message.reply_text(
            msg, quote=True, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    else:
        await message.reply_text(
            "No Active Force Subscription channels found in database", quote=True
        )


@Client.on_message(
    filters.private & filters.command(["getpendingfsub"]) & filters.user(ADMINS)
)
async def get_pending_fsub(bot, message):
    all_sub = await get_pen_force_subs()
    if all_sub:
        msg = ""
        for sub in all_sub:
            msg += f">✧ **Chat ID:**`{sub['chat_id']}`\n>**Name:** `{sub['chat_title']}`\n>**Link:** {sub['chat_link']}\n>**Join Request:** `{sub['is_req']}`\n>**Joins:** `{sub['join_count']}`\n>**Target:** `{sub['target']}`\n>**Remove:** `/rmfsub {sub['chat_id']}`\n\n"
        await message.reply_text(
            msg, quote=True, link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
    else:
        await message.reply_text(
            "No Pending Force Subscription channels found in database", quote=True
        )


@Client.on_message(filters.command(["activatefsub"]) & filters.user(ADMINS))
async def activate_fsub(bot, message):
    data = message.text.split()
    if len(data) == 2:
        channel = data[-1]
    else:
        await message.reply_text(
            "Please send in proper format `/activatefsub channel_id`", quote=True
        )
        return

    if not channel.startswith("-100"):
        await message.reply_text("Please check channel ID again", quote=True)
        return

    pen_fsub = await get_force_sub(int(channel))
    if pen_fsub:
        if pen_fsub["is_queue"]:
            await update_force_sub(chat_id=int(channel), is_active=True, is_queue=False)
            await message.reply_text(
                f"Force Subscription channel `{channel}` has been activated", quote=True
            )
        else:
            await message.reply_text(
                f"Force Subscription channel `{channel}` is already active.", quote=True
            )
    else:
        await message.reply_text(
            "Failed to activate Force Subscription, please try again or check logs for more info.",
            quote=True,
        )


@Client.on_message(filters.command(["deactivatefsub"]) & filters.user(ADMINS))
async def deactivate_fsub(bot, message):
    data = message.text.split()
    if len(data) == 2:
        channel = data[-1]
    else:
        await message.reply_text(
            "Please send in proper format `/deactivatefsub channel_id`", quote=True
        )
        return

    if not channel.startswith("-100"):
        await message.reply_text("Please check channel ID again", quote=True)
        return

    pen_fsub = await get_force_sub(int(channel))
    if pen_fsub:
        if pen_fsub.is_active:
            await update_force_sub(chat_id=int(channel), is_active=False)
            await message.reply_text(
                f"Force Subscription channel `{channel}` has been deactivated",
                quote=True,
            )
        else:
            await message.reply_text(
                f"Force Subscription channel `{channel}` is already inactive.",
                quote=True,
            )
    else:
        await message.reply_text(
            "Failed to deactivate Force Subscription, please try again or check logs for more info.",
            quote=True,
        )


@Client.on_message(filters.command(["updatefsubtarget"]) & filters.user(ADMINS))
async def update_fsub_target(bot, message):
    data = message.text.split()
    if len(data) == 3:
        channel = data[-2]
        target = data[-1]
    else:
        await message.reply_text(
            "Please send in proper format `/updatefsubtarget channel_id target`",
            quote=True,
        )
        return

    if not channel.startswith("-100"):
        await message.reply_text("Please check channel ID again", quote=True)
        return

    fsub = await get_force_sub(int(channel))
    if fsub:
        await update_force_sub(chat_id=int(channel), target=int(target))
        await message.reply_text(
            f"Force Subscription channel `{channel}` target has been updated to `{target}`",
            quote=True,
        )
    else:
        await message.reply_text(
            "Failed to update Force Subscription target, please try again or check logs for more info.",
        )


@Client.on_message(filters.command(["clearfsubusers"]) & filters.user(ADMINS))
async def clear_fsub_users(bot, message):
    rem = await remove_fsub_users()
    if rem:
        await message.reply_text("All fsub users removed from database", quote=True)
    else:
        await message.reply_text("No fsub users found in database", quote=True)


@Client.on_message(filters.command(["checkfsubusers"]) & filters.user(ADMINS))
async def check_fsub_users(bot, message):
    msg = ""
    req_count = await get_fsubreq_users_count()
    msg += "**Request Channel:**\n"
    for chat in req_count:
        msg += f"✧ `{chat['chat_id']}`: `{chat['count']}`\n"
    reg_count = await get_fsubreg_users_count()
    msg += "\n**Regular Channel:**\n"
    for chat in reg_count:
        msg += f"✧ `{chat['chat_id']}`: `{chat['count']}`\n"
    if msg:
        await message.reply_text(msg, quote=True)
    else:
        await message.reply_text("No fsub users found in database", quote=True)


async def is_fsub(bot, query, user_id, file_id, admin_settings):
    f_sub = await get_active_force_subs()
    actfsubcount = await get_act_force_subs_count() or 0
    fsublimit = admin_settings["fsub_channel"] or 2

    if f_sub:
        if actfsubcount < fsublimit:
            pen_fsub = await get_nxt_pen_force_sub()
            await activate_pending_force_sub(bot, pen_fsub)

        for chats in f_sub:
            if not await process_force_sub(
                bot, query, chats, user_id, file_id, admin_settings
            ):
                return False
        return True
    else:
        pen_fsub = await get_nxt_pen_force_sub()
        if pen_fsub:
            activated_fsub = await activate_pending_force_sub(bot, pen_fsub)
            if activated_fsub:
                if not await process_force_sub(
                    bot,
                    query,
                    activated_fsub,
                    user_id,
                    file_id,
                    admin_settings,
                ):
                    return False
        return True


async def process_force_sub(bot, query, chats, user_id, file_id, admin_settings):
    force_sub = chats["chat_id"]
    link = chats["chat_link"]
    request = chats["is_req"]
    sub_conf = await check_fsub(
        bot,
        query,
        force_sub,
        link,
        request,
        user_id,
        file_id,
        admin_settings,
    )
    if not sub_conf:
        return False
    return True


async def activate_pending_force_sub(bot, pen_fsub):
    if pen_fsub:
        await update_force_sub(
            chat_id=pen_fsub["chat_id"], is_active=True, is_queue=False
        )
        LOGGER.info(
            "Force Sub channel %s has been added to active list.", pen_fsub["chat_id"]
        )
        msg = (
            f"\nForce Sub channel {pen_fsub['chat_id']} has been added to active list."
        )
        await notify_admins(bot, msg)
        return pen_fsub


async def check_fsub(
    bot, message, force_sub, link, request, user_id, file_id, admin_settings
):
    if isinstance(message, CallbackQuery):
        msg = message.message
    else:
        msg = message

    if admin_settings:
        txt = admin_settings["fsub_msg"] or "**Please join below channel to get file!**"
        fsub_img = getattr(admin_settings, "fsub_img", None)

    try:
        user = await bot.get_chat_member(int(force_sub), user_id)
        if user.status == ChatMemberStatus.BANNED:
            await msg.reply_text(
                "Sorry, you are Banned in subscription channel. Please contact admin.",
                quote=True,
            )
            return False
    except UserNotParticipant:
        user_det = await is_req_user(int(user_id), int(force_sub))
        if user_det and not user_det["fileid"]:
            return True

        if request:
            btn_txt = "⚓ Request to Join"
        else:
            btn_txt = "⚓ Join Channel"

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_txt, url=link)]])

        if admin_settings and admin_settings["fsub_msg"] and admin_settings["fsub_img"]:
            sub_msg = await msg.reply_photo(
                photo=fsub_img,
                caption=txt,
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
                quote=True,
            )
        elif admin_settings and admin_settings["fsub_msg"]:
            sub_msg = await msg.reply_text(
                text=txt,
                reply_markup=kb,
                parse_mode=ParseMode.MARKDOWN,
                quote=True,
            )
        else:
            sub_msg = await msg.reply_text(txt, reply_markup=kb, quote=True)

        if request:
            await add_fsub_req_user(user_id, force_sub, file_id, sub_msg.id)  # todo
        else:
            await add_fsub_reg_user(user_id, force_sub, file_id, sub_msg.id)  # todo
        return False

    except Exception as e:
        LOGGER.warning(e)
        await msg.reply_text(
            text="Something went wrong, please contact my support group",
            quote=True,
        )
        return False
    return True


async def is_inline_fsub(bot, query, user_id, admin_settings):
    f_sub = await get_active_force_subs()
    actfsubcount = await get_act_force_subs_count()
    fsublimit = admin_settings["fsub_channel"] or 2

    if f_sub:
        if actfsubcount < fsublimit:
            pen_fsub = await get_nxt_pen_force_sub()
            await activate_pending_force_sub(bot, pen_fsub)

        for chats in f_sub:
            if not await process_inline_force_sub(bot, query, chats, user_id):
                return False
        return True
    else:
        pen_fsub = await get_nxt_pen_force_sub()
        if pen_fsub:
            activated_fsub = await activate_pending_force_sub(bot, pen_fsub)
            if activated_fsub:
                if not await process_inline_force_sub(
                    bot,
                    query,
                    activated_fsub,
                    user_id,
                ):
                    return False
        return True


async def process_inline_force_sub(bot, query, chats, user_id):
    force_sub = chats["chat_id"]
    link = chats["chat_link"]
    request = chats["is_req"]
    s_no = str(chats["id"])
    sub_conf = await check_inline_fsub(
        bot,
        query,
        force_sub,
        link,
        request,
        user_id,
        s_no,
    )
    if not sub_conf:
        return False
    return True


async def check_inline_fsub(bot, query, force_sub, link, request, user_id, s_no):
    try:
        user = await bot.get_chat_member(int(force_sub), user_id)
        if user.status == ChatMemberStatus.BANNED:
            await query.answer(
                results=[],
                switch_pm_text="You are banned to use this bot",
                switch_pm_parameter="fs_bn",
                cache_time=1,
            )
            return False
    except UserNotParticipant:
        if request:
            user_det = await is_req_user(int(user_id), int(force_sub))
            if user_det:
                if not user_det.fileid:
                    return True
            sw_param = f"fs_req_{s_no}"
        else:
            sw_param = f"fs_reg_{s_no}"
        inpt = "⚓ Tap Me to Join Channel"

        try:
            await query.answer(
                results=[],
                cache_time=1,
                switch_pm_text=inpt,
                switch_pm_parameter=sw_param,
            )
            return False
        except QueryIdInvalid:
            pass
    except Exception as e:
        LOGGER.warning(e)
        await query.answer(
            results=[],
            switch_pm_text="Something went wrong, please contact my support group",
            switch_pm_parameter="fs_er",
            cache_time=1,
        )
        return False
    return True


async def get_inline_fsub(bot, update):
    if isinstance(update, CallbackQuery):
        msg = update.message
    elif isinstance(update, Message):
        msg = update

    try:
        await msg.delete()
    except Exception as e:
        LOGGER.warning(e)

    user_id = update.from_user.id
    cmd = update.command[1]
    mode = cmd.split("_")[1]
    if mode.startswith("re"):
        cnl = cmd.split("_")[2]

        f_sub = await get_active_force_subs()
        if f_sub:
            for chats in f_sub:
                if chats["id"] == int(cnl):
                    force_sub = chats["chat_id"]
                    link = chats["chat_link"]
                    request = chats["is_req"]
                    break
        else:
            return

        admin_settings = await get_admin_settings()
        if admin_settings:
            if admin_settings["fsub_msg"]:
                fsub_msg = admin_settings["fsub_msg"]
                txt = fsub_msg
            else:
                txt = "**Please join below channel to use me inline!**"
            if admin_settings["fsub_img"]:
                fsub_img = admin_settings["fsub_img"]
            else:
                fsub_img = None

            if mode == "req":
                btn_txt = "⚓ Request to Join channel to use me inline."
            else:
                btn_txt = "⚓ Join Channel to use me inline."

            kb = InlineKeyboardMarkup([[InlineKeyboardButton(btn_txt, url=link)]])

            try:
                if (
                    admin_settings
                    and admin_settings["fsub_msg"]
                    and admin_settings["fsub_img"]
                ):
                    sub_msg = await msg.reply_photo(
                        photo=fsub_img,
                        caption=txt,
                        reply_markup=kb,
                        parse_mode=ParseMode.MARKDOWN,
                        quote=True,
                    )
                elif admin_settings and admin_settings["fsub_msg"]:
                    sub_msg = await msg.reply_text(
                        text=txt,
                        reply_markup=kb,
                        parse_mode=ParseMode.MARKDOWN,
                        quote=True,
                    )
                else:
                    sub_msg = await msg.reply_text(txt, reply_markup=kb, quote=True)
            except UserIsBlocked:
                return
            except Exception as e:
                LOGGER.warning(e)
                return

            if request:
                await add_fsub_req_user(
                    user_id, force_sub, fileid="fsub", msg_id=sub_msg.id
                )
            else:
                await add_fsub_reg_user(
                    user_id, force_sub, fileid="fsub", msg_id=sub_msg.id
                )
    elif mode.startswith("bn"):
        await msg.reply_text("You are banned to use this bot", quote=True)
        return
    elif mode.startswith("er"):
        await msg.reply_text(
            "Something went wrong, please contact my support group", quote=True
        )
        return


# Add the missing callback handlers for the force subscription buttons
@Client.on_callback_query(filters.regex(r"^cfs_(req|reg)$"))
async def handle_fsub_type_cb(bot, query):
    await query.answer()


@Client.on_callback_query(filters.regex(r"^lim_(yes|no)$"))
async def handle_fsub_limit_cb(bot, query):
    await query.answer()


@Client.on_callback_query(filters.regex(r"^ena_(yes|no)$"))
async def handle_fsub_enable_cb(bot, query):
    await query.answer()


@Client.on_callback_query(filters.regex(r"^rm_all_(yes|no)$"))
async def handle_rm_all_fsub_cb(bot, query):
    await query.answer()
