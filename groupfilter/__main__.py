import uvloop

uvloop.install()

import asyncio  # noqa
from pyropatch import pyropatch  # noqa
from pyrogram import Client, idle, __version__  # noqa
from pyrogram.raw.all import layer  # noqa
from groupfilter import APP_ID, API_HASH, BOT_TOKEN, PM_SUPPORT, LOGGER  # noqa


app = None

if PM_SUPPORT:
    plugins = {"root": "groupfilter.plugins"}
else:
    plugins = {"root": "groupfilter.plugins", "exclude": ["serve_pm"]}


async def main():
    global app
    app = Client(
        name="groupfilter",
        api_id=APP_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins=plugins,
    )
    async with app:
        me = await app.get_me()
        LOGGER.info(
            "%s - @%s - Pyrogram v%s (Layer %s) - Started...",
            me.first_name,
            me.username,
            __version__,
            layer,
        )
        await idle()
        LOGGER.info("%s - @%s - Stopped !!!", me.first_name, me.username)


# uvloop.run(main())
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
