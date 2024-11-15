import re
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
    filters.private & filters.command(["customcaption"]) & filters.user(ADMINS)
)
async def custom_caption_(bot, update):
    data = update.text.split()
    caption = " ".join(data[1:])
    if len(data) >= 2:
        if caption.lower() == "off":
            caption = None

        await set_custom_caption(caption)

        if caption:
            await update.reply_text(f"Custom caption set to `{caption}`")
        else:
            await update.reply_text("Custom caption disabled")
    else:
        await update.reply_text(
            "Please send in proper format `/customcaption caption/off`"
        )


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
    if len(command_text) < 2:
        await message.reply_text(
            "Please use the correct format: `/addfilter keyword message`"
        )
        return
    text = command_text[1]
    match = re.match(r'^"(.*?)"\s+(.*)', text, re.DOTALL)
    if match:
        filter_word = match.group(1).lower()
        filter_text = match.group(2).strip()
    else:
        parts = text.split(None, 1)
        if len(parts) < 2:
            await message.reply_text(
                "Please use the correct format: `/addfilter keyword message`"
            )
            return
        filter_word = parts[0].lower()
        filter_text = parts[1].strip()

    if not filter_text:
        await message.reply_text("The filter message cannot be empty.")
        return
    added = await add_filter(filter_word, filter_text)
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
    filters.private & filters.command(["forcesub"]) & filters.user(ADMINS)
)
async def force_sub(bot, update):
    data = update.text.split()
    if len(data) == 2:
        channel = data[-1]
        if channel.lower() == "off":
            await set_channel_link(None)
            await update.reply_text("Force Subscription disabled")
            return
        request = False
    elif len(data) == 3:
        channel = data[-2]
        req = data[-1]
        if req != "request":
            await update.reply_text(
                "Please send in proper format `/forcesub channel_id request` if you want to set join request"
            )
            return
        request = True
    else:
        await update.reply_text(
            "Please send in proper format `/forcesub channel_id/off`\n`/forcesub channel_id request` for join request"
        )
        return

    if not channel.startswith("-100"):
        await update.reply_text("Please check channel ID again")
        return

    try:
        link = await bot.create_chat_invite_link(channel, creates_join_request=request)
        inv_link = link.invite_link
    except Exception as e:
        await update.reply_text(f" Error while creating channel invite link: {str(e)}")
        return

    await set_channel_link(inv_link)
    await set_force_sub(int(channel))
    await set_join_request(request)
    await update.reply_text(
        f"Force Subscription channel set to `{channel}`\nInvite link: {link.invite_link}\nJoin Request: {request}"
    )


@Client.on_message(
    filters.private & filters.command(["checklink"]) & filters.user(ADMINS)
)
async def testlink(bot, update):
    link = await get_link()
    if link:
        await update.reply_text(f"Invite link for force subscription channel: {link}")
    else:
        await update.reply_text(
            "Force Subscription is disabled, please enable it first"
        )


@Client.on_message(
    filters.private & filters.command(["setcaptionplus"]) & filters.user(ADMINS)
)
async def caption_username(bot, update):
    command_text = update.text.split(None, 1)
    if len(command_text) < 2:
        await update.reply_text(
            "Please use the correct format: `/setcaptionplus caption/off`"
        )
        return
    text = command_text[1]
    captionplus = text.strip()

    if captionplus.lower() == "off":
        captionplus = None
    await set_captionplus(captionplus)
    if captionplus:
        await update.reply_text(f"File additional caption set to:\n`{captionplus}`")
    else:
        await update.reply_text("File additional username disabled")


@Client.on_message(filters.private & filters.command(["total"]) & filters.user(ADMINS))
async def count_f(bot, update):
    count = await count_files()
    await update.reply_text(f"**Total no. of files in DB:** `{count}`")


@Client.on_message(
    filters.private & filters.command(["infomsg"]) & filters.user(ADMINS)
)
async def set_info_msg_(bot, update):    
    command_text = update.text.split(None, 1)
    if len(command_text) < 2:
        await update.reply_text(
            "Please use the correct format: `/infomsg message/off`"
        )
        return
    text = command_text[1]
    infomsg = text.strip()

    if infomsg.lower() == "off":
        infomsg = None
    await set_info_msg(infomsg)
    if infomsg:
        await update.reply_text(f"Info message set to `{infomsg}`")
    else:
        await update.reply_text("Info message disabled")
        


@Client.on_message(filters.private & filters.command(["delmsg"]) & filters.user(ADMINS))
async def set_del_msg_(bot, update):    
    command_text = update.text.split(None, 1)
    if len(command_text) < 2:
        await update.reply_text(
            "Please use the correct format: `/delmsg message/off`"
        )
        return
    text = command_text[1]
    msg = text.strip()

    if msg.lower() == "off":
        msg = None
    await set_del_msg(msg)
    if msg:
            await update.reply_text(f"Delete message set to `{msg}`")
    else:
        await update.reply_text("Delete message disabled")
        


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
async def set_unavail_msg_(bot, update):
    command_text = update.text.split(None, 1)
    if len(command_text) < 2:
        await update.reply_text(
            "Please use the correct format: `/notfoundmsg message/off`"
        )
        return
    text = command_text[1]
    msg = text.strip()

    if msg.lower() == "off":
        msg = None
    await set_unavail_msg(msg)
    if msg:
            await update.reply_text(f"Not found message set to `{msg}`")
    else:
        await update.reply_text("Not found message disabled")
    


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
async def set_fsub_msg_(bot, update):
    
    command_text = update.text.split(None, 1)
    if len(command_text) < 2:
        await update.reply_text(
            "Please use the correct format: `/fsubmsg message/off`"
        )
        return
    text = command_text[1]
    msg = text.strip()

    if msg.lower() == "off":
        msg = None
    await set_fsub_msg(msg)
    if msg:
        await update.reply_text(f"Fsub message set to `{msg}`")
    else:
        await update.reply_text("Fsub message disabled")
        

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
            image = await set_unavail_img(file_id)
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
