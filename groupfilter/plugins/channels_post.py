import re
from imdb import Cinemagoer
from pyrogram import Client, filters, enums
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LinkPreviewOptions,
)
from groupfilter import (
    LOGGER,
    ADMINS,
    POST_CHANNELS,
    MAX_LIST_ELM,
    LONG_IMDB_DESCRIPTION,
)

LANGUAGES = {
    "mal": "Malayalam",
    "tam": "Tamil",
    "kan": "Kannada",
    "hin": "Hindi",
    "eng": "English",
    "tel": "Telugu",
    "kor": "Korean",
    "chi": "Chinese",
    "jap": "Japanese",
    "multi": "Multi-Language",
}

FONT_TYPES = {
    "regular": "Regular Font",
    "mono": "𝙼𝚘𝚗𝚘𝚜𝚙𝚊𝚌𝚎 𝙵𝚘𝚗𝚝",
    "smallcaps": "Sᴍᴀʟʟ Cᴀᴘꜱ F𝚘𝚗𝚝",
}

FONT_REGULAR = ["abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"]
FONT_MONO = ["𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"]
FONT_SMALLCAPS = ["ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"]


def textchanger(text, font_type="regular"):
    if not text:
        return text
    regular_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    if font_type == "mono":
        font_chars = "".join(FONT_MONO)
    elif font_type == "smallcaps":
        font_chars = "".join(FONT_SMALLCAPS)
    else:  # regular
        font_chars = "".join(FONT_REGULAR)

    translation_table = str.maketrans(regular_chars, font_chars)
    converted_text = text.translate(translation_table)
    return converted_text


temp = {}
imdb = Cinemagoer()


@Client.on_message(filters.command("channelpost") & filters.user(ADMINS))
async def channelpost(bot, message):
    if not POST_CHANNELS:
        return await message.reply_text("No channels found to post to.")
    try:
        query = message.text.split(" ", 1)
        if len(query) < 2:
            return await message.reply_text(
                "**Usage:** /channelpost movie_name\n\nExample: /channelpost Money Heist"
            )
        file_name = query[1].strip()
        movie_details = await get_poster(file_name)
        if not movie_details:
            return await message.reply_text(
                f"No results found for {file_name} on IMDB."
            )
        language_buttons = []
        for code, lang in LANGUAGES.items():
            language_buttons.append(
                [InlineKeyboardButton(lang, callback_data=f"lang_{code}_{file_name}")]
            )
        language_markup = InlineKeyboardMarkup(language_buttons)
        temp["current_movie"] = {"details": movie_details, "name": file_name}
        await message.reply_text(
            "Select the languages for this movie:", reply_markup=language_markup
        )
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")
        LOGGER.error(f"Error in channelpost: {str(e)}")


@Client.on_callback_query(filters.regex(r"^lang_"))
async def language_selection(bot, query):
    await query.answer()
    _, lang_code, file_name = query.data.split("_")
    if "selected_languages" not in temp:
        temp["selected_languages"] = []
    if lang_code == "multi":
        temp["selected_languages"] = ["Multi-Language"]
    elif lang_code in LANGUAGES:
        if LANGUAGES[lang_code] in temp["selected_languages"]:
            temp["selected_languages"].remove(LANGUAGES[lang_code])
        else:
            if "Multi-Language" in temp["selected_languages"]:
                temp["selected_languages"].remove("Multi-Language")
            temp["selected_languages"].append(LANGUAGES[lang_code])
    language_buttons = []
    for code, lang in LANGUAGES.items():
        button_text = f"✅ {lang}" if lang in temp["selected_languages"] else lang
        language_buttons.append(
            [
                InlineKeyboardButton(
                    button_text, callback_data=f"lang_{code}_{file_name}"
                )
            ]
        )
    language_buttons.append(
        [
            InlineKeyboardButton(
                "Next: Choose Font ➡️", callback_data=f"fontsel_{file_name}"
            )
        ]
    )
    language_markup = InlineKeyboardMarkup(language_buttons)
    await query.message.edit_text(
        "Select the languages for this movie:", reply_markup=language_markup
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^fontsel_"))
async def font_selection(bot, query):
    await query.answer()
    _, file_name = query.data.split("_")

    if "selected_languages" not in temp or not temp["selected_languages"]:
        return await query.message.edit_text(
            "❌ Please select at least one language first."
        )

    font_buttons = []
    for code, font_name in FONT_TYPES.items():
        font_buttons.append(
            [InlineKeyboardButton(font_name, callback_data=f"font_{code}_{file_name}")]
        )

    font_markup = InlineKeyboardMarkup(font_buttons)
    await query.message.edit_text(
        "Select the font style for the movie details:", reply_markup=font_markup
    )


@Client.on_callback_query(filters.regex(r"^font_"))
async def font_choice(bot, query):
    await query.answer()
    _, font_code, file_name = query.data.split("_")

    if font_code in FONT_TYPES:
        temp["selected_font"] = font_code
        await preview_movie_details(bot, query)
    else:
        await query.answer("Invalid font selection.", show_alert=True)


async def preview_movie_details(bot, query):
    await query.answer("Please confirm...")
    movie_details = temp["current_movie"]["details"]
    file_name = temp["current_movie"]["name"]
    selected_languages = (
        ", ".join(temp["selected_languages"]) if "selected_languages" in temp else "N/A"
    )
    selected_font = temp.get("selected_font", "regular")

    movie_title = movie_details.get("title", "N/A")
    rating = movie_details.get("rating", "N/A")
    genres = movie_details.get("genres", "N/A")
    year = movie_details.get("year", "N/A")
    url = movie_details.get("url", "N/A")
    rating = movie_details.get("rating", "N/A")


    preview_text = (
        f"✅ {textchanger(movie_title, selected_font)} ({textchanger(str(year), selected_font)})\n\n"
        f"🎙️ Audio: {textchanger(selected_languages, selected_font)}\n\n"
        f"📽️ Genre: {textchanger(genres, selected_font)}\n\n"
        f"⭐ [{textchanger('IMDB Info', selected_font)}]({url}) | "
        f">**{textchanger('Rating:', selected_font)} {textchanger(str(rating), selected_font)}**"
    )
    confirm_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Yes, Post", callback_data=f"post_yes_{file_name}"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ No, Cancel", callback_data=f"post_no_{file_name}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back to Font Selection", callback_data=f"fontsel_{file_name}"
                )
            ],
        ]
    )
    await query.message.edit_text(
        preview_text,
        reply_markup=confirm_markup,
        parse_mode=enums.ParseMode.MARKDOWN,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@Client.on_callback_query(filters.regex(r"^post_(yes|no)_"))
async def post_to_channels(bot, query):
    action, file_name = query.data.split("_")[1], query.data.split("_")[2]
    if action == "yes":
        await query.answer("✎ Pᴏsᴛɪɴɢ Iᴛ Oɴ Tʜᴇ Cʜᴀɴɴᴇʟ...")
        movie_details = await get_poster(file_name)
        if not movie_details:
            return await query.message.reply_text(
                f"No results found for {file_name} on IMDB."
            )
        movie_title = movie_details.get("title", "N/A")
        rating = movie_details.get("rating", "N/A")
        genres = movie_details.get("genres", "N/A")
        year = movie_details.get("year", "N/A")
        url = movie_details.get("url", "N/A")
        selected_languages = (
            ", ".join(temp["selected_languages"])
            if "selected_languages" in temp
            else "N/A"
        )
        selected_font = temp.get("selected_font", "regular")

        custom_link = f"https://t.me/{bot.me.username}?start=search_{file_name.replace(' ', '_').lower()}"
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Gᴇᴛ Tʜᴇ Fɪʟᴇ... 🔎", url=custom_link)],
                [
                    InlineKeyboardButton("👨‍💻 Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ", url="https://t.me/Ct_updatez"),
                    InlineKeyboardButton("📢 Mᴀɪɴ Cʜᴀɴɴᴇʟ", url="https://t.me/CT_Arena")
                ]
            ]
        )
        caption = (
            f"**✅ {textchanger(movie_title, selected_font)} ({textchanger(str(year), selected_font)})**\n\n"
            f"**🎙️ Audio: {textchanger(selected_languages, selected_font)}**\n\n"
            f"**📽️ Genres: {textchanger(genres, selected_font)}**\n\n"
            f"**⭐ [{textchanger('IMDB Info')}]({url})**"
            f">**{textchanger('Rating:', selected_font)} {textchanger(str(rating), selected_font)}**"
        )
        for channel_id in POST_CHANNELS:
            try:
                await bot.send_message(
                    chat_id=channel_id,
                    text=caption,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.MARKDOWN,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
            except Exception as e:
                await query.message.reply_text(
                    f"Error posting to channel {channel_id}: {str(e)}"
                )
                LOGGER.error(f"Error posting to channel {channel_id}: {str(e)}")
        await query.message.edit_text(
            "✅ Mᴏᴠɪᴇ ᴅᴇᴛᴀɪʟs sᴜᴄᴄᴇssғᴜʟʟʏ ᴘᴏsᴛᴇᴅ ɪɴ ᴄʜᴀɴɴᴇʟ..."
        )
        temp.clear()
    elif action == "no":
        await query.answer("Cancelling...")
        await query.message.edit_text(
            "❌ Mᴏᴠɪᴇ ᴅᴇᴛᴀɪʟs Pᴏsᴛɪɴɢ Cᴀɴᴄᴇʟʟᴇᴅ..."
        )
        temp.clear()


async def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r"[1-2]\d{3}$", query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r"[1-2]\d{3}", file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
        else:
            year = None
        movieid = imdb.search_movie(title.lower(), results=10)
        if not movieid:
            return None
        if year:
            filtered = list(filter(lambda k: str(k.get("year")) == str(year), movieid))
            if not filtered:
                filtered = movieid
        else:
            filtered = movieid
        movieid = list(
            filter(lambda k: k.get("kind") in ["movie", "tv series"], filtered)
        )
        if not movieid:
            movieid = filtered
        if bulk:
            return movieid
        movieid = movieid[0].movieID
    else:
        movieid = query
    movie = imdb.get_movie(movieid)
    if movie.get("original air date"):
        date = movie["original air date"]
    elif movie.get("year"):
        date = movie.get("year")
    else:
        date = "N/A"
    plot = ""
    if not LONG_IMDB_DESCRIPTION:
        plot = movie.get("plot")
        if plot and len(plot) > 0:
            plot = plot[0]
    else:
        plot = movie.get("plot outline")
    if plot and len(plot) > 800:
        plot = plot[0:800] + "..."

    return {
        "title": movie.get("title"),
        "votes": movie.get("votes"),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get("box office"),
        "localized_title": movie.get("localized title"),
        "kind": movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(movie.get("runtimes")),
        "countries": list_to_str(movie.get("countries")),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_str(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer": list_to_str(movie.get("writer")),
        "producer": list_to_str(movie.get("producer")),
        "composer": list_to_str(movie.get("composer")),
        "cinematographer": list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        "release_date": date,
        "year": movie.get("year"),
        "genres": list_to_str(movie.get("genres")),
        "poster": movie.get("full-size cover url"),
        "plot": plot,
        "rating": str(movie.get("rating")),
        "url": f"https://www.imdb.com/title/tt{movieid}",
    }


def list_to_str(k):
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    elif MAX_LIST_ELM:
        k = k[: int(MAX_LIST_ELM)]
        return " ".join(f"{elem}, " for elem in k)
    else:
        return " ".join(f"{elem}, " for elem in k)
