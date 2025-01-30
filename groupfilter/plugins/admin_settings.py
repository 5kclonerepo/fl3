import json
from pyrogram import Client, filters
from groupfilter.db.settings_sql import (
    get_admin_settings,
    set_repair_mode,
    set_auto_delete,
    set_custom_caption,
    set_force_sub,
    set_channel_link,
    get_link,
    set_captionplus,
    set_info_msg,
    set_info_img,
    set_del_msg,
    set_del_img,
    set_unavail_msg,
    set_unavail_img,
    set_button_delete,
    set_join_request,
    set_fsub_msg,
    set_fsub_img,
)
from groupfilter.db.ban_sql import is_banned, ban_user, unban_user
from groupfilter.db.filters_sql import add_filter, rem_filter, list_filters
from groupfilter.db.files_sql import count_files
from groupfilter.db.broadcast_sql import count_users
from groupfilter import ADMINS, DB_CHANNELS


@Client.on_message(
    filters.private & filters.command(["autodelete"]) & filters.user(ADMINS)
)
async def auto_delete_(bot, update):
    data = update.text.split()
    if len(data) == 2:
        dur = data[-1]
        if dur.lower() == "off":
            dur = 0

        await set_auto_delete(int(dur))

        if dur:
            await update.reply_text(f"File auto delete set to `{dur}` seconds")
        else:
            await update.reply_text("File auto delete disabled")

    else:
        await update.reply_text("Please send in proper format `/autodelete seconds`")


@Client.on_message(
    filters.private & filters.command(["repairmode"]) & filters.user(ADMINS)
)
async def repair_mode_(bot, update):
    data = update.text.split()
    if len(data) == 2:
        toggle = data[-1]
        if toggle.lower() == "off":
            mode = False
        elif toggle.lower() == "on":
            mode = True
        else:
            await update.reply_text(
                "Please send in proper format `/repairmode <on/off>`"
            )
            return
        await set_repair_mode(mode)
        await update.reply_text(f"Repair mode set to `{toggle.upper()}`")

    else:
        await update.reply_text("Please send in proper format `/repairmode on/off`")


@Client.on_message(
    filters.private & filters.command(["adminsettings"]) & filters.user(ADMINS)
)
async def admin_settings_(bot, update):
    user_id = update.from_user.id
    admin_settings = await get_admin_settings()
    auto_delete = admin_settings.auto_delete
    custom_caption = admin_settings.custom_caption
    fsub_channel = admin_settings.fsub_channel
    invite_link = admin_settings.channel_link
    join_req = admin_settings.join_req
    caption_uname = admin_settings.caption_uname
    repair_mode = admin_settings.repair_mode
    info_msg = admin_settings.info_msg
    info_img = admin_settings.info_img
    del_msg = admin_settings.del_msg
    del_img = admin_settings.del_img
    notfound_msg = admin_settings.notfound_msg
    notfound_img = admin_settings.notfound_img
    fsub_msg = admin_settings.fsub_msg
    fsub_img = admin_settings.fsub_img
    btn_del = admin_settings.btn_del

    admins = ""
    dbchannel = ""
    for admin in ADMINS:
        admins += "\n" + "`" + str(admin) + "`"
    for channel in DB_CHANNELS:
        dbchannel += "\n" + "`" + str(channel) + "`"

    if auto_delete:
        auto_delete = f"{auto_delete} seconds"
    else:
        auto_delete = "Disabled"

    if not custom_caption:
        custom_caption = "Disabled"

    if not fsub_channel:
        fsub_channel = "Disabled"

    if not caption_uname:
        caption_uname = "Disabled"

    if not invite_link:
        invite_link = "Disabled"

    if join_req:
        join_req = "Enabled"
    else:
        join_req = "Disabled"

    if repair_mode:
        repair_mode = "Enabled"
    else:
        repair_mode = "Disabled"

    if not info_msg:
        info_msg = "Disabled"

    if info_img:
        info_img = "Enabled"
    else:
        info_img = "Disabled"

    if not del_msg:
        del_msg = "Disabled"

    if del_img:
        del_img = "Enabled"
    else:
        del_img = "Disabled"

    if not notfound_msg:
        notfound_msg = "Disabled"

    if notfound_img:
        notfound_img = "Enabled"
    else:
        notfound_img = "Disabled"

    if btn_del:
        btn_del = f"{btn_del} seconds"
    else:
        btn_del = "Disabled"

    if not fsub_msg:
        fsub_msg = "Disabled"

    if fsub_img:
        fsub_img = "Enabled"
    else:
        fsub_img = "Disabled"

    await bot.send_message(
        chat_id=user_id,
        text=f"**Below are your current settings.**\n\n**Repair Mode:** `{repair_mode}`\n**Auto Delete:** `{auto_delete}`\n**Button Delete:** `{btn_del}`\n**Custom Caption:** `{custom_caption}`\n**Force Sub:** `{fsub_channel}`\n**Channel Link:** `{invite_link}`\n**Join Request:** `{join_req}`\n**Caption Username:** `{caption_uname}`\n**Info Message:** `{info_msg}`\n**Info Image:** `{info_img}`\n**Delete Message:** `{del_msg}`\n**Delete Image:** `{del_img}`\n**Not Found Message:** `{notfound_msg}`\n**Not Found Image:** `{notfound_img}`\nfsub Message:** `{fsub_msg}`\n**fsub Image:** `{fsub_img}`\n**Admins:** {admins} \n**DB Channels:** {dbchannel}",
    )


@Client.on_message(filters.private & filters.command(["ban"]) & filters.user(ADMINS))
async def banuser(bot, update):
    data = update.text.split()
    if len(data) == 2:
        user_id = data[-1]
        banned = await is_banned(int(user_id))
        if not banned:
            await ban_user(int(user_id))
            await update.reply_text(f"User {user_id} banned")
        else:
            await update.reply_text(f"User {user_id} is already banned")

    else:
        await update.reply_text("Please send in proper format `/ban user_id`")


@Client.on_message(filters.private & filters.command(["unban"]) & filters.user(ADMINS))
async def unbanuser(bot, update):
    data = update.text.split()
    if len(data) == 2:
        user_id = data[-1]
        banned = await is_banned(int(user_id))
        if banned:
            await unban_user(int(user_id))
            await update.reply_text(f"User {user_id} unbanned")
        else:
            await update.reply_text(f"User {user_id} is not in ban list")
    else:
        await update.reply_text("Please send in proper format `/unban user_id`")


@Client.on_message(
    filters.private & filters.command("addfilter") & filters.user(ADMINS)
)
async def addfilter(client, message):
    command_text = message.text.split(None, 1)
    if len(command_text) < 2 and not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: `/addfilter keyword` and reply to the message with the filter text."
        )
        return
    
    reply_msg = message.reply_to_message    
    media_type = None
    file_id = None

    if reply_msg.text:
        media_type = "text"
        file_id = None
        filter_text = reply_msg.text.markdown
    elif reply_msg.photo:
        media_type = "photo"
        file_id = reply_msg.photo.file_id
        filter_text = reply_msg.caption.markdown
    elif reply_msg.video:
        media_type = "video"
        file_id = reply_msg.video.file_id
        filter_text = reply_msg.caption.markdown
    elif reply_msg.animation:
        media_type = "animation"
        file_id = reply_msg.animation.file_id
        filter_text = reply_msg.caption.markdown
    elif reply_msg.sticker:
        media_type = "sticker"
        file_id = reply_msg.sticker.file_id
        filter_text = None
    else:
        await message.reply_text("Unsupported format, please reply to a message with text, photo, video, gif or sticker.")
        return

    filter_word = command_text[1].lower()
    buttons = reply_msg.reply_markup
    if buttons:
        button_data = [
            [{"text": button.text, "url": button.url} for button in row]
            for row in buttons.inline_keyboard
        ]
        btn_json = json.dumps(button_data)
    else:
        btn_json = None

    added = await add_filter(filter_word, filter_text, btn_json, media_type, file_id)
    if added:
        await message.reply_text(f"Filter `{filter_word}` added successfully.")
    else:
        await message.reply_text(f"Filter `{filter_word}` already exists.")


@Client.on_message(
    filters.private & filters.command(["delfilter"]) & filters.user(ADMINS)
)
async def delfilter(bot, update):
    data = update.text.split()
    if len(data) >= 2:
        fltr = " ".join(data[1:])
        rem = await rem_filter(fltr)
        if rem:
            await update.reply_text(f"Filter `{fltr}` removed")
        else:
            await update.reply_text(f"Filter `{fltr}` not found")
    else:
        await update.reply_text("Please send in proper format `/delfilter filter`")


@Client.on_message(
    filters.private & filters.command(["listfilters"]) & filters.user(ADMINS)
)
async def list_filter(bot, update):
    fltr = await list_filters()
    fltr_msg = ""
    if fltr:
        for fltrs in fltr:
            fltr_msg += "\n" + "`" + fltrs + "`"
        await update.reply_text(f"**Available Filters:** {fltr_msg}")
    else:
        await update.reply_text("No filters found")


@Client.on_message(
    filters.private & filters.command(["customcaption"]) & filters.user(ADMINS)
)
async def custom_caption_(bot, message):
    command_text = message.text.split(None, 1)
    if len(command_text) == 2:
        if command_text[1].lower() == "off":
            await set_custom_caption(None)
            await message.reply_text("Custom caption disabled")
        else:
            await message.reply_text(
                "Please use the correct format: `/customcaption off`"
            )
        return

    if len(command_text) > 2 or not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: reply to a message with `/customcaption` or `/customcaption off`"
        )
        return

    caption = message.reply_to_message.text.markdown
    await set_custom_caption(caption)
    await message.reply_text(f"Custom caption set to {caption}")


@Client.on_message(
    filters.private & filters.command(["captionplus"]) & filters.user(ADMINS)
)
async def caption_plus(bot, message):
    command_text = message.text.split(None, 1)
    if len(command_text) == 2:
        if command_text[1].lower() == "off":
            await set_captionplus(None)
            await message.reply_text("Additional caption disabled")
        else:
            await message.reply_text(
                "Please use the correct format: `/captionplus off`"
            )
        return

    if len(command_text) > 2 or not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: reply to a message with `/captionplus` or `/captionplus off`"
        )
        return

    caption = message.reply_to_message.text.markdown
    await set_captionplus(caption)
    await message.reply_text(f"Additional caption set to {caption}")


@Client.on_message(
    filters.private & filters.command(["setfsub"]) & filters.user(ADMINS)
)
async def force_sub(bot, update):
    data = update.text.split()
    if len(data) == 2:
        channel = data[-1]
        if channel.lower() == "off":
            await set_channel_link(None)
            await update.reply_text("Force Subscription disabled")
            return
    else:
        await update.reply_text(
            "Please send in proper format `/setfsub channel_id/off`"
        )
        return

    if not channel.startswith("-100"):
        await update.reply_text("Please check channel ID again")
        return

    try:
        link = await bot.create_chat_invite_link(
            int(channel), creates_join_request=False
        )
        inv_link = link.invite_link
    except Exception as e:
        await update.reply_text(f" Error while creating channel invite link: {str(e)}")
        return

    await set_channel_link(inv_link)
    await set_force_sub(int(channel))
    await set_join_request(False)
    await update.reply_text(
        f"Force Subscription channel set to `{channel}`\nInvite link: {link.invite_link}\nJoin Request: False"
    )

@Client.on_message(
    filters.private & filters.command(["setreqfsub"]) & filters.user(ADMINS)
)
async def req_force_sub(bot, update):
    data = update.text.split()
    if len(data) == 2:
        channel = data[-1]
        if channel.lower() == "off":
            await set_channel_link(None)
            await update.reply_text("Force Subscription disabled")
            return
    else:
        await update.reply_text(
            "Please send in proper format `/setreqfsub channel_id/off`"
        )
        return

    if not channel.startswith("-100"):
        await update.reply_text("Please check channel ID again")
        return

    try:
        link = await bot.create_chat_invite_link(
            int(channel), creates_join_request=True
        )
        inv_link = link.invite_link
    except Exception as e:
        await update.reply_text(f" Error while creating channel invite link: {str(e)}")
        return

    await set_channel_link(inv_link)
    await set_force_sub(int(channel))
    await set_join_request(True)
    await update.reply_text(
        f"Force Subscription channel set to `{channel}`\nInvite link: {link.invite_link}\nJoin Request: True"
    )


@Client.on_message(
    filters.private & filters.command(["setfsub2"]) & filters.user(ADMINS)
)
async def force_sub2(bot, update):
    data = update.text.split()
    if len(data) == 2:
        channel = data[-1]
        if channel.lower() == "off":
            await set_channel_link(None, add=True)
            await update.reply_text("Force Subscription 2 disabled")
            return
    else:
        await update.reply_text(
            "Please send in proper format `/setfsub2 channel_id/off`"
        )
        return

    if not channel.startswith("-100"):
        await update.reply_text("Please check channel ID again")
        return

    try:
        link = await bot.create_chat_invite_link(
            int(channel), creates_join_request=False
        )
        inv_link = link.invite_link
    except Exception as e:
        await update.reply_text(f" Error while creating channel invite link: {str(e)}")
        return

    await set_channel_link(inv_link, add=True)
    await set_force_sub(int(channel), add=True)
    await set_join_request(False, add=True)
    await update.reply_text(
        f"Force Subscription 2 channel set to `{channel}`\nInvite link: {link.invite_link}\nJoin Request: False"
    )


@Client.on_message(
    filters.private & filters.command(["setreqfsub2"]) & filters.user(ADMINS)
)
async def req_force_sub2(bot, update):
    data = update.text.split()
    if len(data) == 2:
        channel = data[-1]
        if channel.lower() == "off":
            await set_channel_link(None, add=True)
            await update.reply_text("Force Subscription 2 disabled")
            return
    else:
        await update.reply_text(
            "Please send in proper format `/setreqfsub2 channel_id/off`"
        )
        return

    if not channel.startswith("-100"):
        await update.reply_text("Please check channel ID again")
        return

    try:
        link = await bot.create_chat_invite_link(
            int(channel), creates_join_request=True
        )
        inv_link = link.invite_link
    except Exception as e:
        await update.reply_text(f" Error while creating channel invite link: {str(e)}")
        return

    await set_channel_link(inv_link, add=True)
    await set_force_sub(int(channel), add=True)
    await set_join_request(True, add=True)
    await update.reply_text(
        f"Force Subscription 2 channel set to `{channel}`\nInvite link: {link.invite_link}\nJoin Request: True"
    )

@Client.on_message(
    filters.private & filters.command(["checklink"]) & filters.user(ADMINS)
)
async def testlink(bot, update):
    link1, link2 = await get_link()
    if link1 and link2:
        await update.reply_text(
            f"Invite link for force subscription channel 1: {link1}\nInvite link 2 for force subscription channel 2: {link2}"
        )
    elif link1:
        await update.reply_text(
            f"Invite link for force subscription channel 1: {link1}"
        )
    elif link2:
        await update.reply_text(
            f"Invite link for force subscription channel 2: {link2}"
        )
    else:
        await update.reply_text(
            "Force Subscription is disabled, please enable it first"
        )


@Client.on_message(filters.private & filters.command(["total"]) & filters.user(ADMINS))
async def count_f(bot, update):
    file_count = await count_files()
    user_count = await count_users()
    await update.reply_text(
        f"**Total no. of files in DB:** `{file_count}`\n**Total no. of users in DB:** `{user_count}`"
    )


@Client.on_message(
    filters.private & filters.command(["infomsg"]) & filters.user(ADMINS)
)
async def set_info_msg_(bot, message):
    command_text = message.text.split(None, 1)
    if len(command_text) == 2:
        if command_text[1].lower() == "off":
            await set_info_msg(None)
            await message.reply_text("Info message disabled")
        else:
            await message.reply_text("Please use the correct format: `/infomsg off`")
        return

    if len(command_text) > 2 or not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: reply to a message with `/infomsg` or `/infomsg off`"
        )
        return

    infomsg = message.reply_to_message.text.markdown
    await set_info_msg(infomsg)
    await message.reply_text(f"Info message set to {infomsg}")


@Client.on_message(filters.private & filters.command(["delmsg"]) & filters.user(ADMINS))
async def set_del_msg_(bot, message):
    command_text = message.text.split(None, 1)
    if len(command_text) == 2:
        if command_text[1].lower() == "off":
            await set_del_msg(None)
            await message.reply_text("Delete message disabled")
        else:
            await message.reply_text("Please use the correct format: `/delmsg off`")
        return

    if len(command_text) > 2 or not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: reply to a message with `/delmsg` or `/delmsg off`"
        )
        return

    delmsg = message.reply_to_message.text.markdown
    await set_del_msg(delmsg)
    await message.reply_text(f"Delete message set to {delmsg}")


@Client.on_message(
    filters.private & filters.command(["infoimg"]) & filters.user(ADMINS)
)
async def set_info_img_(bot, message):
    data = message.text.split()
    msg = " ".join(data[1:])
    if len(data) >= 2:
        if msg.lower() == "off":
            msg = None
            await set_info_img(msg)
            await message.reply_text("Info image removed successfully.", quote=True)
        else:
            await message.reply_text(
                "Please send in proper format `/infoimg off` or reply /infoimg to an image to set",
                quote=True,
            )
    else:
        if not message.reply_to_message:
            await message.reply_text(
                "Send this as a reply to the image.",
                quote=True,
            )
            return
        try:
            file_id = str(message.reply_to_message.photo.file_id)
            image = await set_info_img(file_id)
        except AttributeError:
            await message.reply_text(
                "Please reply to a image only (not document).", quote=True
            )
            return
        if image:
            await message.reply_text("Info image updated successfully.", quote=True)
        else:
            await message.reply_text(
                "Error adding Info image, please contact support.", quote=True
            )


@Client.on_message(filters.private & filters.command(["delimg"]) & filters.user(ADMINS))
async def set_del_img_(bot, message):
    data = message.text.split()
    msg = " ".join(data[1:])
    if len(data) >= 2:
        if msg.lower() == "off":
            msg = None
            await set_info_img(msg)
            await message.reply_text("Delete image removed successfully.", quote=True)
        else:
            await message.reply_text(
                "Please send in proper format `/delimg off` or reply /delimg to an image to set",
                quote=True,
            )
    else:
        if not message.reply_to_message:
            await message.reply_text(
                "Send this as a reply to the image.",
                quote=True,
            )
            return
        try:
            file_id = str(message.reply_to_message.photo.file_id)
            image = await set_del_img(file_id)
        except AttributeError:
            await message.reply_text(
                "Please reply to a image only (not document).", quote=True
            )
            return
        if image:
            await message.reply_text("Delete image updated successfully.", quote=True)
        else:
            await message.reply_text(
                "Error adding Delete image, please contact support.", quote=True
            )


@Client.on_message(
    filters.private & filters.command(["notfoundmsg"]) & filters.user(ADMINS)
)
async def set_unavail_msg_(bot, message):
    command_text = message.text.split(None, 1)
    if len(command_text) == 2:
        if command_text[1].lower() == "off":
            await set_unavail_msg(None)
            await message.reply_text("Not Found message disabled")
        else:
            await message.reply_text(
                "Please use the correct format: `/notfoundmsg off`"
            )
        return

    if len(command_text) > 2 or not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: reply to a message with `/notfoundmsg` or `/notfoundmsg off`"
        )
        return

    unavlmsg = message.reply_to_message.text.markdown
    await set_unavail_msg(unavlmsg)
    await message.reply_text(f"Not Found message set to {unavlmsg}")


@Client.on_message(
    filters.private & filters.command(["notfoundimg"]) & filters.user(ADMINS)
)
async def set_unavail_img_(bot, message):
    data = message.text.split()
    msg = " ".join(data[1:])
    if len(data) >= 2:
        if msg.lower() == "off":
            msg = None
            await set_unavail_img(msg)
            await message.reply_text(
                "Not found image removed successfully.", quote=True
            )
        else:
            await message.reply_text(
                "Please send in proper format `/notfoundimg off` or reply /notfoundimg to an image to set",
                quote=True,
            )
    else:
        if not message.reply_to_message:
            await message.reply_text(
                "Send this as a reply to the image.",
                quote=True,
            )
            return
        try:
            file_id = str(message.reply_to_message.photo.file_id)
            image = await set_unavail_img(file_id)
        except AttributeError:
            await message.reply_text(
                "Please reply to a image only (not document).", quote=True
            )
            return
        if image:
            await message.reply_text(
                "Not found image updated successfully.", quote=True
            )
        else:
            await message.reply_text(
                "Error adding Not found image, please contact support.", quote=True
            )


@Client.on_message(
    filters.private & filters.command(["fsubmsg"]) & filters.user(ADMINS)
)
async def set_fsub_msg_(bot, message):
    command_text = message.text.split(None, 1)
    if len(command_text) == 2:
        if command_text[1].lower() == "off":
            await set_fsub_msg(None)
            await message.reply_text("Fsub message disabled")
        else:
            await message.reply_text("Please use the correct format: `/fsubmsg off`")
        return

    if len(command_text) > 2 or not message.reply_to_message:
        await message.reply_text(
            "Please use the correct format: reply to a message with `/fsubmsg` or `/fsubmsg off`"
        )
        return

    fsubmsg = message.reply_to_message.text.markdown
    await set_fsub_msg(fsubmsg)
    await message.reply_text(f"Fsub message set to {fsubmsg}")


@Client.on_message(
    filters.private & filters.command(["fsubimg"]) & filters.user(ADMINS)
)
async def set_fsub_img_(bot, message):
    data = message.text.split()
    msg = " ".join(data[1:])
    if len(data) >= 2:
        if msg.lower() == "off":
            msg = None
            await set_fsub_img(msg)
            await message.reply_text("Fsub image removed successfully.", quote=True)
        else:
            await message.reply_text(
                "Please send in proper format `/fsubimg off` or reply /fsubimg to an image to set",
                quote=True,
            )
    else:
        if not message.reply_to_message:
            await message.reply_text(
                "Send this as a reply to the image.",
                quote=True,
            )
            return
        try:
            file_id = str(message.reply_to_message.photo.file_id)
            image = await set_fsub_img(file_id)
        except AttributeError:
            await message.reply_text(
                "Please reply to a image only (not document).", quote=True
            )
            return
        if image:
            await message.reply_text("Fsub image updated successfully.", quote=True)
        else:
            await message.reply_text(
                "Error adding Fsub image, please contact support.", quote=True
            )


@Client.on_message(
    filters.private & filters.command(["buttondel"]) & filters.user(ADMINS)
)
async def button_delete_(bot, update):
    data = update.text.split()
    if len(data) == 2:
        dur = data[-1]
        if dur.lower() == "off":
            dur = 0

        await set_button_delete(int(dur))

        if dur:
            await update.reply_text(f"File button delete set to `{dur}` seconds")
        else:
            await update.reply_text("File button delete disabled")

    else:
        await update.reply_text("Please send in proper format `/buttondel seconds`")
