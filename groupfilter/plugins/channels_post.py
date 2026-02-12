import re
import requests
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
    OMDB_API_KEY,
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

FONT_MAP = {
    "regular": "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    "mono": "𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
    "smallcaps": "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢABCDEFGHIJKLMNOPQRSTUVWXYZ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
}


def textchanger(text, font_type="regular"):
    if not text:
        return text
    source_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    target_chars = FONT_MAP.get(font_type, FONT_MAP["regular"])
    return text.translate(str.maketrans(source_chars, target_chars))


temp = {}
imdb = Cinemagoer()


@Client.on_message(filters.command("channelpost") & filters.user(ADMINS))
async def channelpost(bot, message):
    if not POST_CHANNELS:
        return await message.reply_text("No channels found to post to.")
    try:
        query = message.text.split(" ", 1)
        if len(query) < 2:
            return await message.reply_text("**Usage:** /channelpost movie_name")
        file_name = query[1].strip()
        movie_details = await get_poster(file_name)
        if not movie_details:
            return await message.reply_text(
                f"No results found for {file_name} on IMDB."
            )

        temp["current_movie"] = {"details": movie_details, "name": file_name}
        print(temp)
        language_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(lang, callback_data=f"lang_{code}_{file_name}")]
                for code, lang in LANGUAGES.items()
            ]
        )
        await message.reply_text(
            "Select the languages for this movie:", reply_markup=language_markup
        )
    except Exception as e:
        LOGGER.error(f"Error in channelpost: {e}")
        await message.reply_text(f"Error: {e}")


@Client.on_callback_query(filters.regex(r"^lang_"))
async def language_selection(bot, query):
    _, lang_code, file_name = query.data.split("_")
    selected = temp.setdefault("selected_languages", [])
    if lang_code == "multi":
        selected.clear()
        selected.append("Multi-Language")
    elif LANGUAGES[lang_code] in selected:
        selected.remove(LANGUAGES[lang_code])
    else:
        selected = [lang for lang in selected if lang != "Multi-Language"]
        selected.append(LANGUAGES[lang_code])
        temp["selected_languages"] = selected

    language_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"{'✅ ' if lang in selected else ''}{lang}",
                    callback_data=f"lang_{code}_{file_name}",
                )
            ]
            for code, lang in LANGUAGES.items()
        ]
        + [
            [
                InlineKeyboardButton(
                    "Next: Choose Font ➡️", callback_data=f"fontsel_{file_name}"
                )
            ]
        ]
    )
    await query.message.edit_text(
        "Select the languages for this movie:", reply_markup=language_markup
    )


@Client.on_callback_query(filters.regex(r"^fontsel_"))
async def font_selection(bot, query):
    _, file_name = query.data.split("_")
    if not temp.get("selected_languages"):
        return await query.message.edit_text(
            "❌ Please select at least one language first."
        )

    font_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(name, callback_data=f"font_{code}_{file_name}")]
            for code, name in FONT_TYPES.items()
        ]
    )
    await query.message.edit_text(
        "Select the font style for the movie details:", reply_markup=font_markup
    )


@Client.on_callback_query(filters.regex(r"^font_"))
async def font_choice(bot, query):
    _, font_code, file_name = query.data.split("_")
    if font_code not in FONT_TYPES:
        return await query.answer("Invalid font selection.", show_alert=True)

    temp["selected_font"] = font_code
    preview_text, markup = await preview_movie_details(bot, query)
    await query.message.edit_text(
        preview_text,
        reply_markup=markup,
        parse_mode=enums.ParseMode.MARKDOWN,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def preview_movie_details(bot, query=None, for_post=False, custom_link=None):
    details = temp["current_movie"]["details"]
    print(details)
    file_name = temp["current_movie"]["name"]
    languages = ", ".join(temp.get("selected_languages", [])) or "N/A"
    font = temp.get("selected_font", "regular")

    def fmt(text):
        return textchanger(text, font)

    caption = (
        f"**✅ {fmt(details.get('title', 'N/A'))} ({fmt(str(details.get('year', 'N/A')))})**\n\n"
        f"**🎙️ Audio: {fmt(languages)}**\n\n"
        f"**📽️ Genre: {fmt(details.get('genres', 'N/A'))}**\n\n"
        f"**⭐ [{fmt('IMDB Info')}]({details.get('url')}) | {fmt('Rating:')} {fmt(str(details.get('rating', 'N/A')))}**"
    )

    if for_post:
        return caption
    return caption, InlineKeyboardMarkup(
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


@Client.on_callback_query(filters.regex(r"^post_(yes|no)_"))
async def post_to_channels(bot, query):
    action, file_name = query.data.split("_")[1:]
    if action == "yes":
        await query.answer("✎ Pᴏsᴛɪɴɢ...")
        link = f"https://t.me/{bot.me.username}?start=search_{file_name.replace(' ', '_').lower()}"
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Gᴇᴛ Tʜᴇ Fɪʟᴇ... 🔎", url=link)],
                [
                    InlineKeyboardButton(
                        "👨‍💻 Uᴘᴅᴀᴛᴇ Cʜᴀɴɴᴇʟ", url="https://t.me/+uTx_KlV3Ea0zZGM1"
                    ),
                    InlineKeyboardButton(
                        "📢 Mᴀɪɴ Cʜᴀɴɴᴇʟ", url="https://t.me/+M_hu1vNsbhgyZTQ1"
                    ),
                ],
            ]
        )
        caption = await preview_movie_details(bot, for_post=True)
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
                LOGGER.error(f"Error posting to channel {channel_id}: {e}")
        await query.message.edit_text("✅ Movie details successfully posted.")
        temp.clear()
    else:
        await query.answer("Cancelled.")
        await query.message.edit_text("❌ Movie posting cancelled.")
        temp.clear()


async def get_poster(query, bulk=False, id=False, file=None):
    if not OMDB_API_KEY:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r"[1-2]\d{3}$", query)
            if year:
                year = year[0]
                title = title.replace(year, "").strip()
            elif file:
                year_match = re.findall(r"[1-2]\d{3}", file)
                year = year_match[0] if year_match else None
            else:
                year = None

            movies = imdb.search_movie(title, results=10)
            print(movies)
            if not movies:
                return None
            filtered = (
                [m for m in movies if str(m.get("year")) == year] if year else movies
            )
            filtered = [
                m for m in filtered if m.get("kind") in ["movie", "tv series"]
            ] or filtered
            if bulk:
                return filtered
            movieid = filtered[0].movieID
        else:
            movieid = query

        movie = imdb.get_movie(movieid)
        plot = (
            movie.get("plot outline")
            if LONG_IMDB_DESCRIPTION
            else (movie.get("plot") or [""])[0]
        )
        plot = (plot[:800] + "...") if plot and len(plot) > 800 else plot

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
            "release_date": movie.get("original air date")
            or movie.get("year")
            or "N/A",
            "year": movie.get("year"),
            "genres": list_to_str(movie.get("genres")),
            "poster": movie.get("full-size cover url"),
            "plot": plot,
            "rating": str(movie.get("rating")),
            "url": f"https://www.imdb.com/title/tt{movieid}",
        }
    else:
        title = query
        year_match = re.findall(r"[1-2]\d{3}$", query)
        if year_match:
            year = year_match[0]
            title = title.replace(year, "").strip()
        elif file:
            year_match = re.findall(r"[1-2]\d{3}", file)
            year = year_match[0] if year_match else None
        else:
            year = None

        params = {
            "t": title,
            "apikey": OMDB_API_KEY,
        }
        if year:
            params["y"] = year

        response = requests.get("https://www.omdbapi.com/", params=params)
        if response.status_code != 200:
            return None

        data = response.json()
        if data.get("Response") != "True":
            return None

        return {
            "title": data.get("Title"),
            "year": data.get("Year"),
            "genres": data.get("Genre"),
            "rating": data.get("imdbRating"),
            "url": f"https://www.imdb.com/title/{data.get('imdbID')}",
            "poster": data.get("Poster"),
            "plot": data.get("Plot"),
        }


def list_to_str(items):
    if not items:
        return "N/A"
    if MAX_LIST_ELM:
        items = items[: int(MAX_LIST_ELM)]
    return ", ".join(str(item) for item in items)
